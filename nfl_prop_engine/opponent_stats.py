"""Opponent-allowed rate tables, shared by offense and defense projections.

For an offense stat (e.g. WR receiving_yards), nflverse's weekly data already
carries an `opponent_team` column, so "allowed by team X" is a direct
groupby. VERIFIED: the defense file (player_stats_def_*.parquet) does NOT
carry opponent_team -- confirmed by inspecting its columns during
development -- so defensive rows need an opponent looked up from the
schedule before the same aggregation works. That's what add_opponent_column
is for.
"""
import statistics

import pandas as pd


def add_opponent_column(weekly_df: pd.DataFrame, schedule_df: pd.DataFrame, team_col: str = "team") -> pd.DataFrame:
    home = schedule_df[["season", "week", "home_team", "away_team"]].rename(
        columns={"home_team": team_col, "away_team": "opponent_team"}
    )
    away = schedule_df[["season", "week", "home_team", "away_team"]].rename(
        columns={"away_team": team_col, "home_team": "opponent_team"}
    )
    lookup = pd.concat([home, away], ignore_index=True)
    return weekly_df.merge(lookup, on=["season", "week", team_col], how="left")


def allowed_rate_table(weekly_df: pd.DataFrame, stat_col: str, season: int) -> tuple[pd.Series, float, int]:
    """weekly_df must already have an opponent_team column and be
    pre-filtered to the relevant position group and season.

    Returns (allowed_per_game by opponent_team, league_avg_allowed_per_game,
    n_league_team_games) -- the last value is "how many current-season
    league-wide games of data exist," used to weight prior-season blending
    for the opponent side per the spec (not just one team's game count).
    """
    df = weekly_df[weekly_df["season"] == season]
    if df.empty or df["opponent_team"].isna().all():
        return pd.Series(dtype=float), float("nan"), 0

    per_game = df.groupby(["week", "opponent_team"])[stat_col].sum().reset_index()
    allowed = per_game.groupby("opponent_team")[stat_col].mean()
    league_avg = per_game[stat_col].mean()
    n_league_team_games = len(per_game)
    return allowed, league_avg, n_league_team_games


def blended_opponent_factor(
    opponent_team: str,
    current_allowed: pd.Series,
    current_league_avg: float,
    n_current_league_games: int,
    prior_allowed: pd.Series,
    prior_league_avg: float,
    k: int,
) -> float:
    """Same shrinkage idea as the player-side blend, but weighted by
    league-wide current-season sample size rather than one team's game
    count -- in weeks 1-2 that number is tiny, so this correctly leans
    almost entirely on last year's defensive numbers.
    """
    prior_weight = k / (n_current_league_games + k)

    cur_allowed = current_allowed.get(opponent_team, current_league_avg) if not current_allowed.empty else None
    cur_league_avg = current_league_avg if current_league_avg == current_league_avg else None  # NaN check

    pri_allowed = prior_allowed.get(opponent_team) if not prior_allowed.empty else None
    pri_league_avg = prior_league_avg if prior_league_avg == prior_league_avg else None

    if cur_allowed is None and pri_allowed is None:
        return 1.0  # no data at all -- neutral factor rather than a fabricated number

    if cur_allowed is None:
        # No games played yet this season (week 1) -- lean entirely on prior season.
        blended_allowed = pri_allowed
        blended_league_avg = pri_league_avg
    elif pri_allowed is None:
        blended_allowed = cur_allowed
        blended_league_avg = cur_league_avg
    else:
        blended_allowed = (1 - prior_weight) * cur_allowed + prior_weight * pri_allowed
        blended_league_avg = (1 - prior_weight) * cur_league_avg + prior_weight * pri_league_avg

    if not blended_league_avg:
        return 1.0
    return blended_allowed / blended_league_avg
