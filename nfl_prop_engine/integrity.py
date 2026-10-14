"""Checks on the results log that fail loudly, so a broken feed or a grading
bug turns the weekly grading run red instead of quietly skewing every hit
rate (as counting injured players as 0 and logging weeks twice both did).

    python grade_results.py --check

Errors fail the run; warnings are printed but don't. Both also go to the
GitHub job summary when run on Actions.
"""
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

from config import ANALYST_PICKS, RESULTS_DB_PATH
from results_log import UNIQUE_KEYS, _connect

# Stats where a player who was on the field for most of his team's snaps
# rarely finishes on exactly 0 (it happens -- a receiver targeted twice who
# catches neither -- but in about 5% of cases, not 10%+). A week above the
# limit means the stats feed is losing players, not that they all blanked.
VOLUME_STATS = ("receiving_yards", "receptions", "rushing_yards", "carries", "passing_yards", "completions")
FULL_TIME_SNAP_PCT = 0.5
MAX_FULL_TIME_ZERO_SHARE = 0.10
# Above this share of a week's props void, the snap-sheet matching is broken
# (a normal week voids 0-2% -- the odd late scratch).
MAX_VOID_SHARE = 0.05
# Ungraded this long after logging means the stats or snap sheet never came.
MAX_DAYS_UNGRADED = 9


@dataclass(frozen=True)
class Problem:
    level: str  # "error" fails the run; "warning" doesn't
    message: str


def _duplicates(conn: sqlite3.Connection) -> list[Problem]:
    problems = []
    for table, key in UNIQUE_KEYS.items():
        cols = ", ".join(key)
        n = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM {table} GROUP BY {cols} HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        if n:
            problems.append(Problem("error", f"{table}: {n} prop(s) logged more than once in the same week"))
    return problems


def _stale(conn: sqlite3.Connection, now: datetime) -> list[Problem]:
    cutoff = (now - timedelta(days=MAX_DAYS_UNGRADED)).isoformat()
    rows = conn.execute(
        "SELECT season, week, COUNT(*) FROM weekly_output WHERE actual_value IS NULL AND void = 0 AND logged_at < ? "
        "GROUP BY season, week", (cutoff,),
    ).fetchall()
    return [Problem("error", f"{season} week {week}: {n} prop(s) still ungraded {MAX_DAYS_UNGRADED}+ days after "
                             "logging (stats or snap counts never arrived)") for season, week, n in rows]


def _week_shares(df: pd.DataFrame) -> list[Problem]:
    problems = []
    for (season, week), wk in df.groupby(["season", "week"]):
        settled = wk[wk["actual_value"].notna() | (wk["void"] == 1)]
        if settled.empty:
            continue
        void_share = (settled["void"] == 1).mean()
        if void_share > MAX_VOID_SHARE:
            problems.append(Problem("error", f"{season} week {week}: {void_share:.0%} of props void (normal is 0-2%) "
                                             "-- the snap-count matching is probably broken"))
        played = settled[(settled["void"] == 0) & settled["stat_col"].isin(VOLUME_STATS)
                         & (settled["snap_pct"] >= FULL_TIME_SNAP_PCT)]
        if len(played) >= 20:
            zero_share = (played["actual_value"] == 0).mean()
            if zero_share > MAX_FULL_TIME_ZERO_SHARE:
                problems.append(Problem("error", f"{season} week {week}: {zero_share:.0%} of full-time players graded 0 "
                                                 "on a volume stat (normal is ~5%) -- the stats feed is losing players"))
        missing_snaps = ((settled["void"] == 0) & settled["snap_pct"].isna()).sum()
        if missing_snaps:
            problems.append(Problem("warning", f"{season} week {week}: {missing_snaps} graded prop(s) have no snap share "
                                               "(graded before snap counts were used -- run a regrade)"))
    return problems


def _analyst_feed(conn: sqlite3.Connection) -> list[Problem]:
    if not ANALYST_PICKS["enabled"]:
        return []
    latest = conn.execute("SELECT season, week FROM weekly_output ORDER BY season DESC, week DESC LIMIT 1").fetchone()
    if latest is None:
        return []
    n = conn.execute("SELECT COUNT(*) FROM analyst_picks WHERE season=? AND week=?", latest).fetchone()[0]
    if n == 0:
        return [Problem("error", f"{latest[0]} week {latest[1]}: the analyst feed logged no picks (the search failed "
                                 "or found nothing usable -- see that Sunday's run log)")]
    return []


def find_problems(db_path: str = RESULTS_DB_PATH, now: datetime | None = None) -> list[Problem]:
    now = now or datetime.now(timezone.utc)
    conn = _connect(db_path)
    try:
        df = pd.read_sql_query("SELECT season, week, stat_col, actual_value, void, snap_pct FROM weekly_output", conn)
        return _duplicates(conn) + _stale(conn, now) + _week_shares(df) + _analyst_feed(conn)
    finally:
        conn.close()


def report(problems: list[Problem]) -> int:
    """Prints the problems (and adds them to the GitHub job summary);
    returns the exit code: 1 if any is an error."""
    lines = [f"- **{p.level.upper()}**: {p.message}" for p in problems] or ["- No problems found."]
    text = "### Results log checks\n" + "\n".join(lines) + "\n"
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(text)
    return 1 if any(p.level == "error" for p in problems) else 0
