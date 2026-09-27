"""prop_bets: durable log of legs actually PLACED (Week 4 upgrade spec,
Requirement 6) -- distinct from results_log.py's weekly_output table,
which logs every ranked prop whether or not it was bet. This only ever
holds real bets, settled against real outcomes, so the weekly review can
answer "does this process work" from actual results rather than vibes.
"""
import sqlite3
from datetime import datetime, timezone

from config import RESULTS_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS prop_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week INTEGER NOT NULL,
    placed_at TEXT NOT NULL,
    game TEXT,
    player TEXT NOT NULL,
    market TEXT NOT NULL,
    side TEXT NOT NULL,
    book_line REAL NOT NULL,
    book_price REAL NOT NULL,
    consensus_line_at_bet REAL,
    fair_prob_at_bet REAL,
    closing_consensus_line REAL,
    closing_fair_prob REAL,
    actual_stat REAL,
    result TEXT,
    acca_id TEXT,
    bet_builder_group TEXT,
    sources TEXT
);
"""


def _connect(db_path: str = RESULTS_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    return conn


def log_placed_legs(legs: list[dict], week: int, acca_id: str, db_path: str = RESULTS_DB_PATH) -> int:
    """legs: dicts with player, market, side, book_line, book_price, and
    optionally game/consensus_line_at_bet/fair_prob_at_bet/
    bet_builder_group/sources. Only legs Dan actually confirmed placing --
    this table is never a superset of every candidate the report
    surfaced, that's what weekly_output already covers.
    """
    placed_at = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            """INSERT INTO prop_bets
               (week, placed_at, game, player, market, side, book_line, book_price,
                consensus_line_at_bet, fair_prob_at_bet, acca_id, bet_builder_group, sources)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    week, placed_at, leg.get("game"), leg["player"], leg["market"], leg["side"],
                    leg["book_line"], leg["book_price"], leg.get("consensus_line_at_bet"),
                    leg.get("fair_prob_at_bet"), acca_id, leg.get("bet_builder_group"),
                    ",".join(leg["sources"]) if leg.get("sources") else None,
                )
                for leg in legs
            ],
        )
    conn.close()
    return len(legs)


def record_closing_snapshot(
    week: int, closing: dict[tuple[str, str], tuple[float, float]], db_path: str = RESULTS_DB_PATH
) -> int:
    """closing: {(player, market): (closing_consensus_line, closing_fair_prob)},
    from the Close snapshot. Fills in the two closing_* columns for every
    already-logged leg it has a match for."""
    conn = _connect(db_path)
    count = 0
    with conn:
        cur = conn.execute("SELECT id, player, market FROM prop_bets WHERE week=?", (week,))
        for row_id, player, market in cur.fetchall():
            values = closing.get((player, market))
            if values is not None:
                conn.execute(
                    "UPDATE prop_bets SET closing_consensus_line=?, closing_fair_prob=? WHERE id=?",
                    (values[0], values[1], row_id),
                )
                count += 1
    conn.close()
    return count


def _settle_side(side: str, line: float, actual: float) -> str:
    if actual == line:
        return "push"
    if side == "over":
        return "win" if actual > line else "loss"
    return "win" if actual < line else "loss"


def settle_week(week: int, actual_stats: dict[tuple[str, str], float | None], db_path: str = RESULTS_DB_PATH) -> int:
    """actual_stats: {(player, market): value}. A value of None means the
    player didn't take part -- voided, matching bet365's own void rule,
    never scored as a loss. A (player, market) missing entirely means
    that game hasn't finished yet: left unsettled rather than guessed at.
    Only touches rows with result IS NULL, so a re-run never re-settles
    (or silently overwrites) an already-graded leg.
    """
    conn = _connect(db_path)
    count = 0
    with conn:
        cur = conn.execute(
            "SELECT id, player, market, side, book_line FROM prop_bets WHERE week=? AND result IS NULL", (week,)
        )
        for row_id, player, market, side, line in cur.fetchall():
            if (player, market) not in actual_stats:
                continue
            actual = actual_stats[(player, market)]
            if actual is None:
                conn.execute("UPDATE prop_bets SET result=? WHERE id=?", ("void", row_id))
            else:
                result = _settle_side(side, line, actual)
                conn.execute("UPDATE prop_bets SET actual_stat=?, result=? WHERE id=?", (actual, result, row_id))
            count += 1
    conn.close()
    return count


def line_clv(book_line: float, closing_consensus_line: float | None) -> float | None:
    """Closing consensus line minus the line actually bet, for an OVER.
    Positive means we beat the close (bet a lower number than the market
    ultimately settled on)."""
    if closing_consensus_line is None:
        return None
    return closing_consensus_line - book_line
