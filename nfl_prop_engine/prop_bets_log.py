"""prop_bets: durable log of legs actually PLACED (Week 4 upgrade spec,
Requirement 6) -- distinct from results_log.py's weekly_output table,
which logs every ranked prop whether or not it was bet. This only ever
holds real bets, settled against real outcomes, so the weekly review can
answer "does this process work" from actual results rather than vibes.
"""
import sqlite3
from datetime import datetime, timezone

from config import RESULTS_DB_PATH

# book_line/book_price are nullable because real slips contain legs without
# them: anytime-TD legs have no line, and bet-builder legs are priced as a
# group rather than individually. The log records what was actually bet,
# not only what the settlement code can grade.
SCHEMA = """
CREATE TABLE IF NOT EXISTS prop_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week INTEGER NOT NULL,
    placed_at TEXT NOT NULL,
    game TEXT,
    player TEXT NOT NULL,
    market TEXT NOT NULL,
    market_text TEXT,
    side TEXT NOT NULL,
    book_line REAL,
    book_price REAL,
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

# One row per placed bet (a single, an accumulator, or a bet builder); its
# legs live in prop_bets with acca_id = slip_id. Stake and total odds live
# here because accumulator P&L is decided per bet, not per leg.
SLIPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS bet_slips (
    slip_id TEXT PRIMARY KEY,
    source_issue INTEGER NOT NULL,
    week INTEGER NOT NULL,
    logged_at TEXT NOT NULL,
    bet_type TEXT NOT NULL,
    stake_gbp REAL,
    total_odds_decimal REAL,
    potential_returns_gbp REAL,
    result TEXT,
    returns_gbp REAL
);
"""

SETTLEABLE_SIDES = ("over", "under")


def _connect(db_path: str = RESULTS_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.execute(SLIPS_SCHEMA)
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
        _insert_legs(conn, legs, week, acca_id, placed_at)
    conn.close()
    return len(legs)


def _insert_legs(conn: sqlite3.Connection, legs: list[dict], week: int, acca_id: str, placed_at: str) -> None:
    conn.executemany(
        """INSERT INTO prop_bets
           (week, placed_at, game, player, market, market_text, side, book_line, book_price,
            consensus_line_at_bet, fair_prob_at_bet, acca_id, bet_builder_group, sources)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                week, placed_at, leg.get("game"), leg["player"], leg["market"], leg.get("market_text"),
                leg["side"], leg.get("book_line"), leg.get("book_price"), leg.get("consensus_line_at_bet"),
                leg.get("fair_prob_at_bet"), acca_id, leg.get("bet_builder_group"),
                ",".join(leg["sources"]) if leg.get("sources") else None,
            )
            for leg in legs
        ],
    )


class AlreadySettledError(Exception):
    pass


def replace_slips_for_issue(
    issue_number: int, week: int, slips: list[dict], db_path: str = RESULTS_DB_PATH
) -> tuple[int, int]:
    """Logs the slips parsed from one GitHub issue, replacing anything
    previously logged from that same issue -- so confirming twice, or
    correcting and re-confirming, never double-counts a bet. Refuses once
    any of that issue's bets or legs has been settled, since silently
    rewriting a graded bet would corrupt the results history.

    slips: [{bet_type, stake_gbp, total_odds_decimal, potential_returns_gbp,
    legs: [{player, market, market_text, side, book_line, book_price, game,
    bet_builder_group}]}]. Returns (slips_logged, legs_logged).
    """
    logged_at = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        with conn:
            existing = [
                row[0] for row in conn.execute("SELECT slip_id FROM bet_slips WHERE source_issue=?", (issue_number,))
            ]
            if existing:
                marks = ",".join("?" * len(existing))
                settled = conn.execute(
                    f"SELECT (SELECT COUNT(*) FROM bet_slips WHERE slip_id IN ({marks}) AND result IS NOT NULL)"
                    f" + (SELECT COUNT(*) FROM prop_bets WHERE acca_id IN ({marks}) AND result IS NOT NULL)",
                    (*existing, *existing),
                ).fetchone()[0]
                if settled:
                    raise AlreadySettledError(f"Issue #{issue_number}'s bets are already settled")
                conn.execute(f"DELETE FROM prop_bets WHERE acca_id IN ({marks})", existing)
                conn.execute("DELETE FROM bet_slips WHERE source_issue=?", (issue_number,))

            n_legs = 0
            for i, slip in enumerate(slips, start=1):
                slip_id = f"issue-{issue_number}-{i}"
                conn.execute(
                    """INSERT INTO bet_slips
                       (slip_id, source_issue, week, logged_at, bet_type, stake_gbp,
                        total_odds_decimal, potential_returns_gbp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        slip_id, issue_number, week, logged_at, slip["bet_type"], slip.get("stake_gbp"),
                        slip.get("total_odds_decimal"), slip.get("potential_returns_gbp"),
                    ),
                )
                _insert_legs(conn, slip["legs"], week, slip_id, logged_at)
                n_legs += len(slip["legs"])
    finally:
        conn.close()
    return len(slips), n_legs


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
        # Only over/under legs with a line can be graded from a stat value.
        # Anything else (anytime TD "yes", a match-result leg) would
        # otherwise fall through _settle_side's else-branch and be graded as
        # an under.
        cur = conn.execute(
            "SELECT id, player, market, side, book_line FROM prop_bets "
            "WHERE week=? AND result IS NULL AND side IN (?, ?) AND book_line IS NOT NULL",
            (week, *SETTLEABLE_SIDES),
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
