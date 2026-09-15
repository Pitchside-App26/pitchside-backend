"""Backtest grading: closes the loop results_log.sqlite3 was built for but
that, until now, nothing ever ran. Fills in actual_value for every logged
prop once its real game is over, then reports hit rate broken down enough
to catch distortions -- not just an overall number, which grading week 1 by
hand already showed can be badly misleading on its own (individual
defender "under 0.5 sacks" props went 6/6 purely because sacks are a rare
event for any one player, inflating the naive overall hit rate well above
what the props that actually carry information were doing).

    python grade_results.py            # grade every ungraded (season, week)
    python grade_results.py --report   # skip grading, just report on what's
                                        # already graded

Every actual value used here comes from the same fetch_all_stats() /
derive_stats_from_pbp.py fallback run_weekly.py already relies on -- no
separate, unverified data path for grading vs. projecting.
"""
import argparse
import logging
import sqlite3

import nfl_data_py as nfl
import pandas as pd

from config import RESULTS_DB_PATH
from fetch_schedule import load_schedule_seasons
from fetch_stats import fetch_all_stats
from results_log import grade_week

logger = logging.getLogger(__name__)


def _ungraded_season_weeks(db_path: str = RESULTS_DB_PATH) -> list[tuple[int, int]]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT DISTINCT season, week FROM weekly_output WHERE actual_value IS NULL ORDER BY season, week"
        )
        return cur.fetchall()
    finally:
        conn.close()


def _ungraded_pairs(season: int, week: int, db_path: str = RESULTS_DB_PATH) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """SELECT DISTINCT player_id, stat_col FROM weekly_output
               WHERE season=? AND week=? AND actual_value IS NULL AND player_id IS NOT NULL""",
            (season, week),
        )
        return {(pid, stat) for pid, stat in cur.fetchall()}
    finally:
        conn.close()


def _completed_teams(season: int, week: int) -> set[str]:
    """Teams whose week-`week` game already has a final score logged --
    grading a player as a hard 0 for a game that hasn't been played yet
    would be wrong, not just premature."""
    schedule = load_schedule_seasons([season])
    wk = schedule[(schedule["week"] == week) & schedule["home_score"].notna()]
    return set(wk["home_team"]).union(set(wk["away_team"]))


def _match_actual(
    team: str | None,
    stat_col: str,
    completed_teams: set[str],
    offense_by_player: dict,
    defense_by_player: dict,
    player_id: str,
) -> float | None:
    """Pure matching logic, split out from the network-fetching in
    build_actuals_for_week so it's directly testable: None means "leave
    ungraded, game not final yet"; 0.0 means "game's over, player just has
    no row for this stat" (didn't record any, or didn't play -- this engine
    has no injury/inactive feed yet to tell the two apart, see README)."""
    if team not in completed_teams:
        return None
    row = offense_by_player.get(player_id) or defense_by_player.get(player_id)
    value = row.get(stat_col) if row else None
    return float(value) if value is not None else 0.0


def build_actuals_for_week(season: int, week: int, needed: set[tuple[str, str]]) -> dict[tuple[str, str], float]:
    """{(player_id, stat_col): actual_value}, only for pairs in `needed`
    whose team's game is confirmed final -- see _match_actual for the
    matching rule itself."""
    completed = _completed_teams(season, week)
    if not completed:
        return {}

    stats = fetch_all_stats(season)
    offense = stats["offense"]
    offense = offense[(offense["season"] == season) & (offense["week"] == week)]
    defense = stats["defense"]
    defense = defense[(defense["season"] == season) & (defense["week"] == week)]

    offense_by_player = offense.set_index("player_id").to_dict("index") if not offense.empty else {}
    defense_by_player = defense.set_index("player_id").to_dict("index") if not defense.empty else {}

    roster = nfl.import_seasonal_rosters([season])[["player_id", "team"]].drop_duplicates("player_id")
    team_by_player = dict(zip(roster["player_id"], roster["team"]))

    actuals = {}
    for player_id, stat_col in needed:
        value = _match_actual(
            team_by_player.get(player_id), stat_col, completed, offense_by_player, defense_by_player, player_id
        )
        if value is not None:
            actuals[(player_id, stat_col)] = value

    return actuals


def grade_all_ungraded(db_path: str = RESULTS_DB_PATH) -> int:
    total_graded = 0
    for season, week in _ungraded_season_weeks(db_path):
        needed = _ungraded_pairs(season, week, db_path)
        if not needed:
            continue
        actuals = build_actuals_for_week(season, week, needed)
        if not actuals:
            logger.info("Season %s week %s: no completed games yet -- nothing to grade.", season, week)
            continue
        n = grade_week(season, week, actuals, db_path)
        logger.info(
            "Season %s week %s: graded %d logged row(s) covering %d distinct player/stat pair(s).",
            season, week, n, len(actuals),
        )
        total_graded += n
    return total_graded


def _direction_hit(direction: str, line: float, actual: float) -> str:
    if actual == line:
        return "push"
    if direction == "over":
        return "hit" if actual > line else "miss"
    return "hit" if actual < line else "miss"


def _summarize(rows: pd.DataFrame, label: str) -> None:
    if rows.empty:
        return
    hits = (rows["outcome"] == "hit").sum()
    misses = (rows["outcome"] == "miss").sum()
    decisive = hits + misses
    rate = f"{hits / decisive:.1%}" if decisive else "n/a"
    print(f"  {label:<28} n={len(rows):<4} hit={hits:<4} miss={misses:<4} hit-rate={rate}")


def print_report(db_path: str = RESULTS_DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM weekly_output WHERE actual_value IS NOT NULL", conn
        )
    finally:
        conn.close()

    if df.empty:
        print("No graded props yet.")
        return

    df["outcome"] = [
        _direction_hit(d, l, a) for d, l, a in zip(df["direction"], df["line"], df["actual_value"])
    ]

    n_weeks = df[["season", "week"]].drop_duplicates().shape[0]
    n_runs = df["logged_at"].nunique()
    print(f"=== Backtest report: {len(df)} graded rows across {n_weeks} week(s), {n_runs} logged run(s) ===")
    if n_runs > n_weeks:
        print(
            f"({n_runs} runs for {n_weeks} week(s) -- more than one run per week means some of "
            f"this is duplicate dev/test runs on the same real games, not independent weekly picks. "
            f"Once this runs on schedule (one real run per week), that goes away on its own.)"
        )
    print()

    print("Overall:")
    _summarize(df, "all graded props")
    print()

    print("By stat (checks for a metric that's structurally easy/hard to hit, not model skill):")
    for stat, group in df.groupby("stat_col"):
        _summarize(group, stat)
    print()

    print("By confidence tier:")
    for conf, group in df.groupby("confidence"):
        _summarize(group, conf)
    print()

    print("By |edge_score| bucket (a real model should do BETTER in higher buckets, not just differently):")
    bins = [0, 0.25, 0.5, 1.0, float("inf")]
    labels = ["0.00-0.25", "0.25-0.50", "0.50-1.00", "1.00+"]
    df["edge_bucket"] = pd.cut(df["edge_score"].abs(), bins=bins, labels=labels, right=False)
    for bucket, group in df.groupby("edge_bucket", observed=True):
        _summarize(group, str(bucket))


def main():
    parser = argparse.ArgumentParser(description="Grade logged props against real results and report hit rate.")
    parser.add_argument("--report", action="store_true", help="skip grading, just report on what's already graded")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if not args.report:
        n = grade_all_ungraded()
        logger.info("Graded %d prop(s) this run.", n)
    print_report()


if __name__ == "__main__":
    main()
