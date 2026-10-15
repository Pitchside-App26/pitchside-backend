"""Durable weekly logging, per the spec's explicit warning that this is a
heuristic blend, not a backtested model -- the ranking is only as good as
its track record, and that track record can't be checked later unless
every week's output is logged now. SQLite, stdlib only.
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from config import RESULTS_DB_PATH
from pricing import no_vig_probability
from rank_props import RankedProp

SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_output (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    player_id TEXT,
    player_name TEXT,
    stat_col TEXT,
    line REAL,
    projection REAL,
    edge_score REAL,
    direction TEXT,
    hit_rate REAL,
    sample_size INTEGER,
    method TEXT,
    confidence TEXT,
    actual_value REAL,
    graded_at TEXT
);
"""


# Every over the accumulator report evaluated, whether or not it passed, with
# its gate result and analyst backing. Graded later, this answers "do
# analyst-backed legs hit more?" -- the test for turning the Sources check
# back into a gate -- and "do the gates themselves pick better overs?".
ACCA_SCHEMA = """
CREATE TABLE IF NOT EXISTS acca_legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    player_id TEXT,
    player_name TEXT,
    stat_col TEXT,
    market TEXT,
    game TEXT,
    window TEXT,
    consensus_line REAL,
    max_line REAL,
    projection REAL,
    fair_prob REAL,
    passed_gates INTEGER NOT NULL,
    failed_gates TEXT,
    selected INTEGER NOT NULL,
    filler INTEGER NOT NULL DEFAULT 0,
    sources_checked INTEGER NOT NULL,
    n_over_sources INTEGER,
    n_under_sources INTEGER,
    actual_value REAL,
    graded_at TEXT
);
"""


# Every analyst pick the slate-wide search found (analyst_picks.py), judged
# at the analyst's own line and side when graded: does following analysts
# beat the market, and does the engine agreeing with them help?
ANALYST_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyst_picks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    player_id TEXT,
    player_name TEXT,
    team TEXT,
    stat_col TEXT,
    market TEXT,
    game TEXT,
    window TEXT,
    side TEXT,
    line REAL,
    price TEXT,
    outlet TEXT,
    analyst TEXT,
    url TEXT,
    publish_date TEXT,
    engine_status TEXT,
    engine_projection REAL,
    actual_value REAL,
    graded_at TEXT
);
"""


# The fun slips' legs and spares (milestone_slips.py): each judged on
# whether he reached the milestone ("5+ receptions" = threshold 5).
SLIP_SCHEMA = """
CREATE TABLE IF NOT EXISTS slip_legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    window TEXT,
    player_id TEXT,
    player_name TEXT,
    stat_col TEXT,
    threshold REAL,
    main_line REAL,
    over_prob REAL,
    chance REAL,
    role TEXT,
    actual_value REAL,
    graded_at TEXT
);
"""


# Columns added after acca_legs first shipped, so a database created by an
# earlier run gets them too (CREATE TABLE IF NOT EXISTS won't add them).
ACCA_ADDED_COLUMNS = {"window": "TEXT", "filler": "INTEGER NOT NULL DEFAULT 0", "side": "TEXT"}
# Prices logged since 4 Oct: both sides at the logged line, the book, and the
# no-vig chance of the over. Before that only the line was kept, so earlier
# weeks can be judged on hit rate but not on profit.
WEEKLY_ADDED_COLUMNS = {"over_price": "REAL", "under_price": "REAL", "bookmaker": "TEXT", "market_over_prob": "REAL"}


# Set by grading on every table. void: the player took no snaps, so a
# bookmaker would void the bet -- left out of every hit rate instead of
# counting as a 0 (which wrongly scored a win for every under on an injured
# player). snap_pct: his share of his unit's snaps that week, so "played but
# recorded nothing" can be told apart from "barely played".
RESULT_COLUMNS = {"void": "INTEGER NOT NULL DEFAULT 0", "snap_pct": "REAL"}

# One row per prop: a re-run of the same week replaces its rows instead of
# adding more. Weeks 1 and 2 were logged several times before this, which
# counted those weeks two to five times over in every total.
UNIQUE_KEYS = {
    "weekly_output": ("season", "week", "player_id", "stat_col"),
    "acca_legs": ("season", "week", "player_id", "stat_col", "side"),
    "analyst_picks": ("season", "week", "player_id", "stat_col", "side", "outlet", "analyst"),
    "slip_legs": ("season", "week", "player_id", "stat_col"),
}


def _add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for column, decl in columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _one_row_per_prop(conn: sqlite3.Connection, table: str) -> None:
    """Keeps the latest row for each prop (highest id) and adds the unique
    index that keeps it that way. Runs once per database."""
    index = f"ux_{table}_prop"
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (index,)).fetchone():
        return
    key = ", ".join(UNIQUE_KEYS[table])
    with conn:
        conn.execute(f"DELETE FROM {table} WHERE id NOT IN (SELECT MAX(id) FROM {table} GROUP BY {key})")
        conn.execute(f"CREATE UNIQUE INDEX {index} ON {table} ({key})")


def _connect(db_path: str = RESULTS_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.execute(ACCA_SCHEMA)
    conn.execute(ANALYST_SCHEMA)
    conn.execute(SLIP_SCHEMA)
    _add_columns(conn, "acca_legs", ACCA_ADDED_COLUMNS)
    _add_columns(conn, "weekly_output", WEEKLY_ADDED_COLUMNS)
    for table in UNIQUE_KEYS:
        _add_columns(conn, table, RESULT_COLUMNS)
    with conn:  # rows from before unders joined the slips (6 Oct) are overs
        conn.execute("UPDATE acca_legs SET side = 'over' WHERE side IS NULL")
    for table in UNIQUE_KEYS:
        _one_row_per_prop(conn, table)
    return conn


def log_acca_legs(rows: list[dict], season: int, week: int, db_path: str = RESULTS_DB_PATH) -> int:
    logged_at = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            """INSERT OR REPLACE INTO acca_legs
               (logged_at, season, week, player_id, player_name, stat_col, market, game, window, consensus_line,
                max_line, projection, fair_prob, passed_gates, failed_gates, selected, filler, sources_checked,
                n_over_sources, n_under_sources, side)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    logged_at, season, week, r["player_id"], r["player_name"], r["stat_col"], r["market"],
                    r["game"], r.get("window"), r["consensus_line"], r["max_line"], r["projection"], r["fair_prob"],
                    int(r["passed_gates"]), r["failed_gates"], int(r["selected"]), int(r.get("filler", False)),
                    int(r["sources_checked"]), r["n_over_sources"], r["n_under_sources"], r.get("side", "over"),
                )
                for r in rows
            ],
        )
    conn.close()
    return len(rows)


def graded_props(db_path: str = RESULTS_DB_PATH):
    """Every graded, non-void ranked prop: what the fun slips' chances are
    estimated from (milestone_slips.ChanceModel)."""
    import pandas as pd

    conn = _connect(db_path)
    try:
        return pd.read_sql_query(
            "SELECT season, week, stat_col, line, actual_value FROM weekly_output "
            "WHERE actual_value IS NOT NULL AND void = 0", conn)
    finally:
        conn.close()


def log_slip_legs(rows: list[dict], season: int, week: int, db_path: str = RESULTS_DB_PATH) -> int:
    logged_at = datetime.now(timezone.utc).isoformat()
    cols = ["window", "player_id", "player_name", "stat_col", "threshold", "main_line", "over_prob", "chance", "role"]
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO slip_legs (logged_at, season, week, {', '.join(cols)}) "
            f"VALUES ({', '.join('?' * (3 + len(cols)))})",
            [(logged_at, season, week, *(r.get(c) for c in cols)) for r in rows],
        )
    conn.close()
    return len(rows)


def grade_slip_week(season: int, week: int, actuals: dict, db_path: str = RESULTS_DB_PATH, overwrite: bool = False) -> int:
    """Same results as grade_week, applied to the fun slips' legs."""
    return _grade_table("slip_legs", season, week, actuals, db_path, overwrite)


def log_analyst_picks(rows: list[dict], season: int, week: int, db_path: str = RESULTS_DB_PATH) -> int:
    logged_at = datetime.now(timezone.utc).isoformat()
    cols = ["player_id", "player_name", "team", "stat_col", "market", "game", "window", "side", "line", "price",
            "outlet", "analyst", "url", "publish_date", "engine_status", "engine_projection"]
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO analyst_picks (logged_at, season, week, {', '.join(cols)}) "
            f"VALUES ({', '.join('?' * (3 + len(cols)))})",
            [(logged_at, season, week, *(r.get(c) for c in cols)) for r in rows],
        )
    conn.close()
    return len(rows)


@dataclass(frozen=True)
class Outcome:
    """A graded prop: the stat he recorded (0 if he played and recorded
    nothing), or value None when he took no snaps and the bet is void."""
    value: float | None
    snap_pct: float | None = None

    @property
    def void(self) -> bool:
        return self.value is None


VOID = Outcome(None, 0.0)


def _as_outcome(result) -> Outcome:
    return result if isinstance(result, Outcome) else Outcome(float(result))


def _grade_table(
    table: str, season: int, week: int, results: dict, db_path: str, overwrite: bool,
) -> int:
    """results: {(player_id, stat_col): Outcome or a plain number}. Only
    rows not yet graded unless overwrite (a regrade)."""
    conn = _connect(db_path)
    graded_at = datetime.now(timezone.utc).isoformat()
    pending = "" if overwrite else " AND actual_value IS NULL AND void = 0"
    count = 0
    with conn:
        cur = conn.execute(f"SELECT id, player_id, stat_col FROM {table} WHERE season=? AND week=?{pending}", (season, week))
        for row_id, player_id, stat_col in cur.fetchall():
            result = results.get((player_id, stat_col))
            if result is None:
                continue
            outcome = _as_outcome(result)
            conn.execute(
                f"UPDATE {table} SET actual_value=?, void=?, snap_pct=?, graded_at=? WHERE id=?",
                (outcome.value, int(outcome.void), outcome.snap_pct, graded_at, row_id),
            )
            count += 1
    conn.close()
    return count


def grade_analyst_week(season: int, week: int, actuals: dict, db_path: str = RESULTS_DB_PATH, overwrite: bool = False) -> int:
    """Same results as grade_week, applied to the analyst_picks log."""
    return _grade_table("analyst_picks", season, week, actuals, db_path, overwrite)


def grade_acca_week(season: int, week: int, actuals: dict, db_path: str = RESULTS_DB_PATH, overwrite: bool = False) -> int:
    """Same results as grade_week, applied to the acca_legs log."""
    return _grade_table("acca_legs", season, week, actuals, db_path, overwrite)


def log_weekly_output(ranked: list[RankedProp], season: int, week: int, db_path: str = RESULTS_DB_PATH) -> int:
    logged_at = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            """INSERT OR REPLACE INTO weekly_output
               (logged_at, season, week, player_id, player_name, stat_col, line, projection,
                edge_score, direction, hit_rate, sample_size, method, confidence,
                over_price, under_price, bookmaker, market_over_prob)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    logged_at, season, week, p.player_id, p.player_name, p.stat_col, p.line,
                    p.projection, p.edge_score, p.direction, p.hit_rate, p.sample_size,
                    p.method, p.confidence,
                    p.over_price, p.under_price, p.bookmaker, no_vig_probability(p.over_price, p.under_price),
                )
                for p in ranked
            ],
        )
    conn.close()
    return len(ranked)


def grade_week(season: int, week: int, actuals: dict, db_path: str = RESULTS_DB_PATH, overwrite: bool = False) -> int:
    """actuals: {(player_id, stat_col): Outcome or a plain number}. Call
    this once real results are in, to close the loop on whether the ranking
    is worth trusting."""
    return _grade_table("weekly_output", season, week, actuals, db_path, overwrite)
