"""Orchestrator: run the full pipeline end to end for the current week.

    python run_weekly.py            # live odds calls (spends credits)
    python run_weekly.py --cache    # replay cached odds JSON from ./cache/
    python run_weekly.py --season 2024 --week 3   # backtest a past week

Suggested build order per the spec: get steps 1-4 working first (print the
raw matched player+line+stats table, no ranking math) before trusting the
projection/ranking layered on top. --raw does exactly that.
"""
import argparse
import logging

import pandas as pd

from config import (
    ALL_MARKETS,
    DEFENSE_MARKETS,
    OFFENSE_MARKETS,
    POSITION_GROUP_MAP,
    SHRINKAGE_K,
    get_current_nfl_season,
)
from fetch_odds import consolidate_lines, fetch_all_event_odds, list_events, parse_event_odds
from fetch_schedule import fetch_week_games, load_schedule_seasons, opponent_map, teams_playing
from fetch_stats import fetch_all_stats
from match_players import match_props_to_players
from opponent_stats import add_opponent_column, allowed_rate_table
from output import print_report
from projection_engine import Projection, league_fallback_std, project_rookie, project_veteran
from rank_props import build_ranked_prop, rank
from results_log import log_weekly_output

logger = logging.getLogger(__name__)


def build_odds_dataframe(season: int, week: int, use_cache: bool) -> pd.DataFrame:
    events = list_events()
    games = fetch_week_games(season, week)
    this_week_teams = teams_playing(games)
    week_events = [e for e in events if e["home_team"] in this_week_teams and e["away_team"] in this_week_teams]
    if not week_events:
        logger.warning("No matching events returned by the odds API for this week's schedule.")

    raw_by_event = fetch_all_event_odds(
        [e["id"] for e in week_events], list(ALL_MARKETS.keys()), use_cache=use_cache
    )
    rows = []
    for event_id, raw in raw_by_event.items():
        rows.extend(parse_event_odds(raw))
    rows = [r for r in rows if r["side"] == "Over"]  # Over/Under share the same point; one row per prop is enough
    rows = consolidate_lines(rows)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["candidate_teams"] = df.apply(lambda r: {r["home_team"], r["away_team"]}, axis=1)
    return df


def prep_position_group(df: pd.DataFrame, position_col: str, constant: str | None = None) -> pd.DataFrame:
    df = df.copy()
    df["position_group_mapped"] = constant if constant else df[position_col].map(POSITION_GROUP_MAP)
    return df


def build_allowed_tables(offense_df: pd.DataFrame, defense_df: pd.DataFrame, seasons: list[int]) -> dict:
    """{(stat_col, season): (allowed_series, league_avg, n_league_games)}"""
    tables = {}
    for market, info in ALL_MARKETS.items():
        stat_col, tag = info["stat_col"], info["position_group"]
        source = offense_df if market in OFFENSE_MARKETS else defense_df
        pool = source[source["position_group_mapped"] == tag]
        for season in seasons:
            tables[(stat_col, season)] = allowed_rate_table(pool, stat_col, season)
    return tables


def run(season: int, week: int | None, use_cache: bool, raw_only: bool = False) -> None:
    games = fetch_week_games(season, week)
    week = int(games["week"].iloc[0])  # resolve once so every downstream call uses the same week
    opp_map = opponent_map(games)

    stats = fetch_all_stats(season)
    # Map from nflverse's fine-grained `position` column (QB/RB/WR/TE/CB/...),
    # not its own coarser `position_group` column (DB/DL/LB/OL/...) -- the
    # latter uses a different vocabulary than POSITION_GROUP_MAP's keys and
    # would silently map QB/RB/WR/TE through by string-coincidence only,
    # while never producing "DEF" for anyone (confirmed by inspecting real
    # values: offense position_group is {DB,DL,LB,OL,QB,RB,SPEC,TE,WR}).
    offense_df = prep_position_group(stats["offense"], "position")
    schedule_multi = load_schedule_seasons([season - 1, season])
    defense_df = add_opponent_column(stats["defense"], schedule_multi, team_col="team")
    defense_df = prep_position_group(defense_df, "position", constant="DEF")
    draft_picks_df = stats["draft_picks"]

    allowed_tables = build_allowed_tables(offense_df, defense_df, [season - 1, season])

    odds_df = build_odds_dataframe(season, week, use_cache)
    if odds_df.empty:
        logger.error("No odds data available -- nothing to rank.")
        return

    offense_odds = odds_df[odds_df["market"].isin(OFFENSE_MARKETS)]
    defense_odds = odds_df[odds_df["market"].isin(DEFENSE_MARKETS)]

    offense_roster = offense_df[offense_df["season"] == season]
    defense_roster = defense_df[defense_df["season"] == season]

    matched_offense = match_props_to_players(offense_odds, offense_roster, team_col_roster="recent_team")
    matched_defense = match_props_to_players(defense_odds, defense_roster, team_col_roster="team")
    matched = pd.concat([matched_offense, matched_defense], ignore_index=True)
    matched = matched[matched["matched_player"].notna()]

    if raw_only:
        print(matched[["player_name", "matched_player", "market", "point", "match_score", "match_method"]].to_string(index=False))
        return

    ranked_props = []
    for _, row in matched.iterrows():
        market = row["market"]
        info = ALL_MARKETS[market]
        stat_col = info["stat_col"]
        is_offense = market in OFFENSE_MARKETS
        source_df = offense_df if is_offense else defense_df
        team_col = "recent_team" if is_offense else "team"

        player_rows = source_df[source_df["player_display_name"] == row["matched_player"]]
        current_rows = player_rows[player_rows["season"] == season].sort_values("week")
        prior_rows = player_rows[player_rows["season"] == season - 1].sort_values("week")

        if current_rows.empty and prior_rows.empty:
            continue
        player_id = (current_rows["player_id"].iloc[0] if not current_rows.empty else prior_rows["player_id"].iloc[0])
        player_team = current_rows[team_col].iloc[-1] if not current_rows.empty else prior_rows[team_col].mode().iat[0]
        opponent_team = opp_map.get(player_team)

        cur_allowed, cur_league_avg, n_league_games = allowed_tables[(stat_col, season)]
        pri_allowed, pri_league_avg, _ = allowed_tables[(stat_col, season - 1)]

        combined_games = len(current_rows) + len(prior_rows)
        if combined_games >= 3:
            proj = project_veteran(
                player_id, row["matched_player"], stat_col, current_rows, prior_rows,
                opponent_team, cur_allowed, cur_league_avg, n_league_games,
                pri_allowed, pri_league_avg, team_col,
                league_fallback_std(source_df[source_df["season"] == season], stat_col),
                k=SHRINKAGE_K,
            )
        elif prior_rows.empty:
            draft_row = draft_picks_df[draft_picks_df["gsis_id"] == player_id]
            position = draft_row["position"].iloc[0] if not draft_row.empty else current_rows["position"].iloc[0]
            pick = int(draft_row["pick"].iloc[0]) if not draft_row.empty else None
            proj = project_rookie(player_id, row["matched_player"], stat_col, position, pick, draft_picks_df, source_df)
            if proj is None:
                logger.warning("No rookie-analog basis for %s / %s -- skipping.", row["matched_player"], stat_col)
                continue
        else:
            proj = project_veteran(
                player_id, row["matched_player"], stat_col, current_rows, prior_rows,
                opponent_team, cur_allowed, cur_league_avg, n_league_games,
                pri_allowed, pri_league_avg, team_col,
                league_fallback_std(source_df[source_df["season"] == season], stat_col),
                k=SHRINKAGE_K,
            )

        ranked_props.append(build_ranked_prop(proj, row["point"], current_rows[stat_col].tolist()))

    ranked = rank(ranked_props)
    print_report(ranked, season, week)
    log_weekly_output(ranked, season, week)


def main():
    parser = argparse.ArgumentParser(description="NFL prop ranking engine -- weekly run")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument("--cache", action="store_true", help="replay cached odds JSON instead of live calls")
    parser.add_argument("--raw", action="store_true", help="print matched player+line table only, no projections")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    season = args.season or get_current_nfl_season()
    week = args.week  # None lets fetch_week_games figure out the current week
    run(season, week, use_cache=args.cache, raw_only=args.raw)


if __name__ == "__main__":
    main()
