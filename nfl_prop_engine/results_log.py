"""Durable weekly logging, per the spec's explicit warning that this is a
heuristic blend, not a backtested model -- the ranking is only as good as
its track record, and that track record can't be checked later unless
every week's output is logged now. SQLite, stdlib only.
"""
import sqlite3
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


# Columns added after acca_legs first shipped, so a database created by an
# earlier run gets them too (CREATE TABLE IF NOT EXISTS won't add them).
ACCA_ADDED_COLUMNS = {"window": "TEXT", "filler": "INTEGER NOT NULL DEFAULT 0"}
# Prices logged since 4 Oct: both sides at the logged line, the book, and the
# no-vig chance of the over. Before that only the line was kept, so earlier
# weeks can be judged on hit rate but not on profit.
WEEKLY_ADDED_COLUMNS = {"over_price": "REAL", "under_price": "REAL", "bookmaker": "TEXT", "market_over_prob": "REAL"}


def _add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for column, decl in columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _connect(db_path: str = RESULTS_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.execute(ACCA_SCHEMA)
    conn.execute(ANALYST_SCHEMA)
    _add_columns(conn, "acca_legs", ACCA_ADDED_COLUMNS)
    _add_columns(conn, "weekly_output", WEEKLY_ADDED_COLUMNS)
    return conn


def log_acca_legs(rows: list[dict], season: int, week: int, db_path: str = RESULTS_DB_PATH) -> int:
    logged_at = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            """INSERT INTO acca_legs
               (logged_at, season, week, player_id, player_name, stat_col, market, game, window, consensus_line,
                max_line, projection, fair_prob, passed_gates, failed_gates, selected, filler, sources_checked,
                n_over_sources, n_under_sources)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    logged_at, season, week, r["player_id"], r["player_name"], r["stat_col"], r["market"],
                    r["game"], r.get("window"), r["consensus_line"], r["max_line"], r["projection"], r["fair_prob"],
                    int(r["passed_gates"]), r["failed_gates"], int(r["selected"]), int(r.get("filler", False)),
                    int(r["sources_checked"]), r["n_over_sources"], r["n_under_sources"],
                )
                for r in rows
            ],
        )
    conn.close()
    return len(rows)


def log_analyst_picks(rows: list[dict], season: int, week: int, db_path: str = RESULTS_DB_PATH) -> int:
    logged_at = datetime.now(timezone.utc).isoformat()
    cols = ["player_id", "player_name", "team", "stat_col", "market", "game", "window", "side", "line", "price",
            "outlet", "analyst", "url", "publish_date", "engine_status", "engine_projection"]
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            f"INSERT INTO analyst_picks (logged_at, season, week, {', '.join(cols)}) "
            f"VALUES ({', '.join('?' * (3 + len(cols)))})",
            [(logged_at, season, week, *(r.get(c) for c in cols)) for r in rows],
        )
    conn.close()
    return len(rows)


def grade_analyst_week(season: int, week: int, actuals: dict[tuple[str, str], float], db_path: str = RESULTS_DB_PATH) -> int:
    """Same actuals as grade_week, applied to the analyst_picks log."""
    conn = _connect(db_path)
    graded_at = datetime.now(timezone.utc).isoformat()
    count = 0
    with conn:
        cur = conn.execute(
            "SELECT id, player_id, stat_col FROM analyst_picks WHERE season=? AND week=? AND actual_value IS NULL",
            (season, week),
        )
        for row_id, player_id, stat_col in cur.fetchall():
            actual = actuals.get((player_id, stat_col))
            if actual is not None:
                conn.execute("UPDATE analyst_picks SET actual_value=?, graded_at=? WHERE id=?", (actual, graded_at, row_id))
                count += 1
    conn.close()
    return count


def grade_acca_week(season: int, week: int, actuals: dict[tuple[str, str], float], db_path: str = RESULTS_DB_PATH) -> int:
    """Same actuals as grade_week, applied to the acca_legs log."""
    conn = _connect(db_path)
    graded_at = datetime.now(timezone.utc).isoformat()
    count = 0
    with conn:
        cur = conn.execute(
            "SELECT id, player_id, stat_col FROM acca_legs WHERE season=? AND week=? AND actual_value IS NULL",
            (season, week),
        )
        for row_id, player_id, stat_col in cur.fetchall():
            actual = actuals.get((player_id, stat_col))
            if actual is not None:
                conn.execute("UPDATE acca_legs SET actual_value=?, graded_at=? WHERE id=?", (actual, graded_at, row_id))
                count += 1
    conn.close()
    return count


def log_weekly_output(ranked: list[RankedProp], season: int, week: int, db_path: str = RESULTS_DB_PATH) -> int:
    logged_at = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            """INSERT INTO weekly_output
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


def grade_week(season: int, week: int, actuals: dict[tuple[str, str], float], db_path: str = RESULTS_DB_PATH) -> int:
    """actuals: {(player_id, stat_col): actual_value}. Call this once real
    results are in, to close the loop on whether the ranking is worth
    trusting past week one."""
    conn = _connect(db_path)
    graded_at = datetime.now(timezone.utc).isoformat()
    count = 0
    with conn:
        cur = conn.execute(
            "SELECT id, player_id, stat_col FROM weekly_output WHERE season=? AND week=?",
            (season, week),
        )
        for row_id, player_id, stat_col in cur.fetchall():
            actual = actuals.get((player_id, stat_col))
            if actual is not None:
                conn.execute(
                    "UPDATE weekly_output SET actual_value=?, graded_at=? WHERE id=?",
                    (actual, graded_at, row_id),
                )
                count += 1
    conn.close()
    return count
