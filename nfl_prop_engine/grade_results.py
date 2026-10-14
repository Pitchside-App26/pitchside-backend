"""Backtest grading: closes the loop results_log.sqlite3 was built for but
that, until now, nothing ever ran. Fills in actual_value for every logged
prop once its real game is over, then reports hit rate broken down enough
to catch distortions -- not just an overall number, which grading week 1 by
hand already showed can be badly misleading on its own (individual
defender "under 0.5 sacks" props went 6/6 purely because sacks are a rare
event for any one player, inflating the naive overall hit rate well above
what the props that actually carry information were doing).

    python grade_results.py            # grade every ungraded (season, week)
    python grade_results.py --regrade  # grade every logged week again from
                                        # scratch (after a grading fix)
    python grade_results.py --report   # skip grading, just report on what's
                                        # already graded
    python grade_results.py --check    # integrity checks only; exits 1 on a
                                        # problem (see integrity.py)

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
from participation import WeekParticipation, week_participation
from pricing import american_to_decimal
from results_log import VOID, Outcome, _connect, grade_acca_week, grade_analyst_week, grade_week

logger = logging.getLogger(__name__)


TABLES = ("weekly_output", "acca_legs", "analyst_picks")
PENDING = "actual_value IS NULL AND void = 0"  # not graded yet (a void row is settled)


def _ungraded_season_weeks(db_path: str = RESULTS_DB_PATH, regrade: bool = False) -> list[tuple[int, int]]:
    where = "" if regrade else f" WHERE {PENDING}"
    conn = _connect(db_path)  # creates acca_legs on an older database that predates it
    try:
        union = " UNION ".join(f"SELECT season, week FROM {t}{where}" for t in TABLES)
        return conn.execute(f"{union} ORDER BY season, week").fetchall()
    finally:
        conn.close()


def _ungraded_pairs(season: int, week: int, db_path: str = RESULTS_DB_PATH, regrade: bool = False) -> set[tuple[str, str]]:
    pending = "" if regrade else f" AND {PENDING}"
    conn = _connect(db_path)
    try:
        union = " UNION ".join(
            f"SELECT player_id, stat_col FROM {t} WHERE season=? AND week=? AND player_id IS NOT NULL{pending}"
            for t in TABLES
        )
        cur = conn.execute(union, (season, week) * len(TABLES))
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
    participation: WeekParticipation | None = None,
    pfr_id: str | None = None,
    name: str | None = None,
) -> Outcome | None:
    """Pure matching logic, split out from the network-fetching in
    build_actuals_for_week so it's directly testable. None means "leave
    ungraded for now": the game isn't final, or he has no stats and the
    week's snap sheet isn't out yet to say whether he played. Otherwise:
    - a stats row: he played; his value (0 for a stat he didn't record);
    - no stats row but he took a snap: he played and recorded nothing, 0;
    - no stats row and no snaps: he didn't play, the bet is void."""
    if team not in completed_teams:
        return None
    snaps = participation.lookup(pfr_id, name, team) if participation is not None else None
    pct = snaps.pct if snaps is not None and snaps.played else None
    row = offense_by_player.get(player_id) or defense_by_player.get(player_id)
    if row:
        value = row.get(stat_col)
        return Outcome(0.0 if value is None or pd.isna(value) else float(value), pct)
    if participation is None or not participation.reported(team):
        return None
    return Outcome(0.0, snaps.pct) if snaps.played else VOID


def _load_participation(season: int, week: int) -> WeekParticipation | None:
    """None (and a loud log line) when the snap sheet can't be read: props
    with no stats row then wait for the next run instead of guessing."""
    try:
        return week_participation(nfl.import_snap_counts([season]), week)
    except Exception as exc:
        logger.error("Couldn't read the %s snap counts (%s): players with no stats stay ungraded.", season, exc)
        return None


def build_actuals_for_week(season: int, week: int, needed: set[tuple[str, str]]) -> dict[tuple[str, str], Outcome]:
    """{(player_id, stat_col): Outcome}, only for pairs in `needed` that can
    be settled -- see _match_actual for the rule itself."""
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

    roster = nfl.import_seasonal_rosters([season])[["player_id", "pfr_id", "player_name", "team"]]
    roster = roster.drop_duplicates("player_id").set_index("player_id")
    participation = _load_participation(season, week)

    actuals = {}
    for player_id, stat_col in needed:
        info = roster.loc[player_id] if player_id in roster.index else None
        value = _match_actual(
            info["team"] if info is not None else None, stat_col, completed, offense_by_player, defense_by_player,
            player_id, participation,
            pfr_id=info["pfr_id"] if info is not None and isinstance(info["pfr_id"], str) else None,
            name=info["player_name"] if info is not None else None,
        )
        if value is not None:
            actuals[(player_id, stat_col)] = value

    return actuals


def grade_all_ungraded(db_path: str = RESULTS_DB_PATH, regrade: bool = False) -> int:
    """Grades every prop not yet settled; with regrade, every logged prop
    again from scratch (after a fix to the grading rules)."""
    total_graded = 0
    for season, week in _ungraded_season_weeks(db_path, regrade):
        needed = _ungraded_pairs(season, week, db_path, regrade)
        if not needed:
            continue
        actuals = build_actuals_for_week(season, week, needed)
        if not actuals:
            logger.info("Season %s week %s: no completed games yet -- nothing to grade.", season, week)
            continue
        n = grade_week(season, week, actuals, db_path, overwrite=regrade)
        n_acca = grade_acca_week(season, week, actuals, db_path, overwrite=regrade)
        n_analyst = grade_analyst_week(season, week, actuals, db_path, overwrite=regrade)
        n_void = sum(outcome.void for outcome in actuals.values())
        logger.info(
            "Season %s week %s: graded %d logged row(s), %d accumulator leg(s) and %d analyst pick(s) covering "
            "%d distinct player/stat pair(s), %d of them void (didn't play); %d pair(s) left for a later run.",
            season, week, n, n_acca, n_analyst, len(actuals), n_void, len(needed) - len(actuals),
        )
        total_graded += n + n_acca + n_analyst
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


def bet_profit(side: str, line: float, actual: float, american_price: float | None) -> float | None:
    """Units won or lost betting 1 unit on `side` at the logged price; None
    with no price. A push returns the stake (0)."""
    decimal = american_to_decimal(american_price)
    if decimal is None:
        return None
    outcome = _direction_hit(side, line, actual)
    return 0.0 if outcome == "push" else decimal - 1 if outcome == "hit" else -1.0


def profit_groups(df: pd.DataFrame) -> list[tuple[str, list[float]]]:
    """(label, per-bet profits) at the logged prices: every over, every
    under, and the engine's own picks. One row per player/stat/week (latest
    run), and only rows with both prices."""
    if "over_price" not in df.columns:
        return []
    df = df[df["over_price"].notna() & df["under_price"].notna()]
    df = df.sort_values("logged_at").drop_duplicates(["season", "week", "player_id", "stat_col"], keep="last")
    def profits(side_of):
        return [bet_profit(side_of(r), r.line, r.actual_value, r.over_price if side_of(r) == "over" else r.under_price)
                for r in df.itertuples()]
    return [
        ("every over", profits(lambda r: "over")),
        ("every under", profits(lambda r: "under")),
        ("the engine's picks", profits(lambda r: r.direction)),
    ]


def print_profit(df: pd.DataFrame) -> None:
    groups = profit_groups(df)
    if not groups or not groups[0][1]:
        print("No graded props with prices yet (prices are logged from 4 Oct on).")
        return
    print("At the logged prices, 1 unit a bet -- a hit rate only matters if it beats the price:")
    for label, profits in groups:
        units = sum(profits)
        print(f"  {label:<28} n={len(profits):<4} profit={units:+.2f}u  ROI={units / len(profits):+.1%}")


def print_report(db_path: str = RESULTS_DB_PATH) -> None:
    conn = _connect(db_path)  # also brings an older database up to one row per prop
    try:
        df = pd.read_sql_query(
            "SELECT * FROM weekly_output WHERE actual_value IS NOT NULL", conn
        )
        n_void = conn.execute("SELECT COUNT(*) FROM weekly_output WHERE void = 1").fetchone()[0]
    finally:
        conn.close()

    if df.empty:
        print("No graded props yet.")
        return

    df["outcome"] = [
        _direction_hit(d, l, a) for d, l, a in zip(df["direction"], df["line"], df["actual_value"])
    ]

    n_weeks = df[["season", "week"]].drop_duplicates().shape[0]
    print(f"=== Backtest report: {len(df)} graded props across {n_weeks} week(s), one row per prop per week ===")
    print(f"({n_void} more were void -- the player took no snaps -- and are left out, as a bookmaker would.)")
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
    print()
    print_profit(df)


def acca_groups(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Graded accumulator-report legs, each judged on its own side at its
    target bet365 line (max for an over, min for an under), grouped to answer two questions: do the gates
    pick better overs, and (among legs that passed) do analyst-backed ones
    hit more? A leg logged by several runs in one week counts once, from
    its latest run."""
    df = df[df["max_line"].notna()].copy()
    # Rows from before unders joined the slips (6 Oct) have no side: overs.
    df["side"] = df["side"].fillna("over") if "side" in df.columns else "over"
    df = df.sort_values("logged_at").drop_duplicates(["season", "week", "player_id", "stat_col", "side"], keep="last").copy()
    df["outcome"] = [_direction_hit(side, line, actual) for side, line, actual in zip(df["side"], df["max_line"], df["actual_value"])]
    over = df["side"] == "over"
    df["n_backers"] = df["n_over_sources"].where(over, df["n_under_sources"])
    df["n_against"] = df["n_under_sources"].where(over, df["n_over_sources"])
    passed = df[df["passed_gates"] == 1]
    checked = passed[passed["sources_checked"] == 1]
    return [
        ("passed every gate", passed),
        ("failed a gate", df[df["passed_gates"] == 0]),
        ("selected, passed every gate", df[(df["selected"] == 1) & (df["filler"] == 0)]),
        ("selected as a filler", df[df["filler"] == 1]),
        ("passed, overs", passed[passed["side"] == "over"]),
        ("passed, unders", passed[passed["side"] == "under"]),
        ("passed, 2+ analysts", checked[checked["n_backers"] >= 2]),
        ("passed, 1 analyst", checked[checked["n_backers"] == 1]),
        ("passed, 0 analysts", checked[checked["n_backers"] == 0]),
        ("passed, analyst against", checked[checked["n_against"] > 0]),
        ("passed, not checked", passed[passed["sources_checked"] == 0]),
    ]


def print_acca_report(db_path: str = RESULTS_DB_PATH) -> None:
    conn = _connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM acca_legs WHERE actual_value IS NOT NULL", conn)
    finally:
        conn.close()
    print()
    if df.empty:
        print("No graded accumulator-report legs yet.")
        return
    print("Accumulator report legs (over at the max acceptable bet365 line). Small samples mean little:")
    for label, rows in acca_groups(df):
        _summarize(rows, label)


def analyst_groups(df: pd.DataFrame, min_outlet_picks: int = 5) -> list[tuple[str, pd.DataFrame]]:
    """Graded analyst picks, each judged at the analyst's own line and side.
    A pick logged by several runs in one week counts once (latest run)."""
    df = df.sort_values("logged_at").drop_duplicates(
        ["season", "week", "player_id", "stat_col", "side", "outlet", "analyst"], keep="last").copy()
    df["outcome"] = [_direction_hit(side, line, actual) for side, line, actual in zip(df["side"], df["line"], df["actual_value"])]
    groups = [
        ("all analyst picks", df),
        ("overs", df[df["side"] == "over"]),
        ("unders", df[df["side"] == "under"]),
        ("engine agrees", df[df["engine_status"].isin(["engine_agree", "slip_agree"])]),
        ("engine disagrees", df[df["engine_status"].isin(["engine_disagree", "slip_against"])]),
    ]
    for outlet, rows in df.groupby("outlet"):
        if outlet and len(rows) >= min_outlet_picks:
            groups.append((f"outlet: {outlet[:20]}", rows))
    return groups


def print_analyst_report(db_path: str = RESULTS_DB_PATH) -> None:
    conn = _connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM analyst_picks WHERE actual_value IS NOT NULL", conn)
    finally:
        conn.close()
    print()
    if df.empty:
        print("No graded analyst picks yet.")
        return
    print("Analyst picks (at the analyst's own line and side; break-even at ~1.85 odds is 54%):")
    for label, rows in analyst_groups(df):
        _summarize(rows, label)


def main():
    parser = argparse.ArgumentParser(description="Grade logged props against real results and report hit rate.")
    parser.add_argument("--report", action="store_true", help="skip grading, just report on what's already graded")
    parser.add_argument("--regrade", action="store_true", help="grade every logged week again from scratch")
    parser.add_argument("--check", action="store_true", help="only run the integrity checks; exit 1 on a problem")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if args.check:
        from integrity import find_problems, report
        raise SystemExit(report(find_problems()))
    if not args.report:
        n = grade_all_ungraded(regrade=args.regrade)
        logger.info("Graded %d prop(s) this run.", n)
    print_report()
    print_acca_report()
    print_analyst_report()


if __name__ == "__main__":
    main()
