"""Step 5: the core projection logic.

Implements the veteran shrinkage/blend formula plus two extensions for thin
early-season samples: opponent-side shrinkage (weighted by league-wide
sample size, not one team's game count) and a draft-slot analog for
rookies. Does not attempt college-stat translation -- see the module
docstring note near ROOKIE path below for why.
"""
import statistics
from dataclasses import dataclass

import pandas as pd

from config import (
    MIN_COMBINED_GAMES_FOR_VETERAN_PROJECTION,
    ROOKIE_DRAFT_SLOT_WINDOW,
    ROOKIE_MIN_GAMES_FOR_PRIOR,
    SHRINKAGE_K,
)
from opponent_stats import blended_opponent_factor


@dataclass
class Projection:
    player_id: str
    player_name: str
    stat_col: str
    projection: float
    season_std: float
    n_current_games: int
    n_prior_games: int
    method: str  # "veteran" | "rookie_prior" | "thin_sample"
    confidence: str  # "normal" | "low"

    # Everything below is optional and populated per method -- not part of
    # the core math, just carried along so explain.py can describe how a
    # number was actually reached instead of guessing from the final value.
    current_season_avg: float | None = None
    prior_season_avg: float | None = None
    last5_avg: float | None = None
    blended_season_avg: float | None = None
    baseline: float | None = None
    opp_factor: float | None = None
    opponent_team: str | None = None
    team_changed: bool = False
    prior_weight: float | None = None
    n_analog_players: int | None = None
    analog_position: str | None = None
    analog_pick: int | None = None


def _team_changed(current_rows: pd.DataFrame, prior_rows: pd.DataFrame, team_col: str) -> bool:
    if current_rows.empty or prior_rows.empty:
        return False
    current_team = current_rows.sort_values("week").iloc[-1][team_col]
    prior_team = prior_rows[team_col].mode().iat[0]
    return current_team != prior_team


def _season_std(current_values: list[float], prior_values: list[float], league_fallback_std: float) -> float:
    """stdev needs >=2 points. With fewer, fall back to prior-season stdev,
    then to a precomputed league-wide fallback for this stat/position --
    returning 0 here would silently overstate confidence in rank_props.py's
    edge score (division by a fake zero-width band).
    """
    if len(current_values) >= 2:
        return statistics.stdev(current_values)
    if len(prior_values) >= 2:
        return statistics.stdev(prior_values)
    return league_fallback_std


def league_fallback_std(weekly_df: pd.DataFrame, stat_col: str, min_games: int = 2) -> float:
    """Median per-player stdev across everyone with enough games this
    season, used only for the rare player who has <2 games in both the
    current and prior season but still clears the veteran-projection bar
    via blending (e.g. 1 prior-season game + 2 current-season games)."""
    stds = (
        weekly_df.groupby("player_id")[stat_col]
        .agg(lambda s: statistics.stdev(s) if len(s) >= min_games else None)
        .dropna()
    )
    return float(stds.median()) if not stds.empty else 0.0


def project_veteran(
    player_id: str,
    player_name: str,
    stat_col: str,
    current_rows: pd.DataFrame,
    prior_rows: pd.DataFrame,
    opponent_team: str,
    opp_current_allowed: pd.Series,
    opp_current_league_avg: float,
    n_current_league_games: int,
    opp_prior_allowed: pd.Series,
    opp_prior_league_avg: float,
    team_col: str,
    league_fallback: float,
    k: int = SHRINKAGE_K,
) -> Projection:
    current_values = current_rows.sort_values("week")[stat_col].tolist()
    prior_values = prior_rows[stat_col].tolist()
    n = len(current_values)

    current_season_avg = statistics.mean(current_values) if current_values else 0.0
    prior_season_avg = statistics.mean(prior_values) if prior_values else None
    team_changed = _team_changed(current_rows, prior_rows, team_col)

    prior_weight = k / (n + k)
    if team_changed:
        prior_weight /= 2

    blended_season_avg = (1 - prior_weight) * current_season_avg + prior_weight * (
        prior_season_avg if prior_season_avg is not None else current_season_avg
    )

    # With zero current-season games (anyone in a not-yet-played week-1 game,
    # or a player back from injury), current_season_avg is 0 with nothing
    # real behind it -- falling back to it here would silently cut the
    # blended baseline roughly in half. blended_season_avg already folds in
    # the prior season properly, so that's the right thing to fall back to.
    last5 = current_values[-5:] if current_values else []
    last5_avg = statistics.mean(last5) if last5 else blended_season_avg
    baseline = 0.5 * blended_season_avg + 0.5 * last5_avg

    opp_factor = blended_opponent_factor(
        opponent_team,
        opp_current_allowed, opp_current_league_avg, n_current_league_games,
        opp_prior_allowed, opp_prior_league_avg,
        k,
    )

    projection = baseline * (1 + 0.25 * (opp_factor - 1))
    std = _season_std(current_values, prior_values, league_fallback)

    combined_games = n + len(prior_values)
    method = "veteran" if combined_games >= MIN_COMBINED_GAMES_FOR_VETERAN_PROJECTION else "thin_sample"
    confidence = "normal" if method == "veteran" else "low"

    return Projection(
        player_id=player_id, player_name=player_name, stat_col=stat_col,
        projection=projection, season_std=std,
        n_current_games=n, n_prior_games=len(prior_values),
        method=method, confidence=confidence,
        current_season_avg=current_season_avg, prior_season_avg=prior_season_avg,
        last5_avg=last5_avg, blended_season_avg=blended_season_avg, baseline=baseline,
        opp_factor=opp_factor, opponent_team=opponent_team, team_changed=team_changed,
        prior_weight=prior_weight,
    )


# --- Rookie path -----------------------------------------------------------
# Deliberately NOT translating college box-score stats (spec's call: scheme
# and competition-level gaps make a naive numeric translation more likely to
# mislead than help; that's a separate, larger project involving a second
# data source and a real translation model). Instead: median games-1-3
# per-game production of previously-drafted players at a similar position
# and draft slot, tagged low confidence.

def find_draft_analogs(draft_picks_df: pd.DataFrame, position: str, pick: int, window: int = ROOKIE_DRAFT_SLOT_WINDOW) -> pd.DataFrame:
    return draft_picks_df[
        (draft_picks_df["position"] == position)
        & (draft_picks_df["pick"].between(pick - window, pick + window))
        & draft_picks_df["gsis_id"].notna()
    ]


def rookie_analog_baseline(
    draft_picks_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    stat_col: str,
    position: str,
    pick: int | None,
    window: int = ROOKIE_DRAFT_SLOT_WINDOW,
) -> tuple[float | None, int]:
    """Returns (baseline, n_analog_players). baseline is None if no analogs
    had any qualifying games -- callers must not display a number in that case.

    Undrafted rookies (pick is None) aren't addressed by the spec; as a
    disclosed extension, they fall back to using every rookie at the
    position regardless of slot, since "similar draft slot" is undefined
    for a player with no draft slot at all.
    """
    if pick is not None:
        pool = find_draft_analogs(draft_picks_df, position, pick, window)
    else:
        pool = draft_picks_df[(draft_picks_df["position"] == position) & draft_picks_df["gsis_id"].notna()]

    values = []
    for _, prow in pool.iterrows():
        rookie_games = weekly_df[
            (weekly_df["player_id"] == prow["gsis_id"]) & (weekly_df["season"] == prow["season"])
        ].sort_values("week").head(3)
        if len(rookie_games) >= ROOKIE_MIN_GAMES_FOR_PRIOR:
            values.append(rookie_games[stat_col].mean())

    if not values:
        return None, 0
    return statistics.median(values), len(values)


def project_rookie(
    player_id: str,
    player_name: str,
    stat_col: str,
    position: str,
    pick: int | None,
    draft_picks_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
) -> Projection | None:
    baseline, n_analogs = rookie_analog_baseline(draft_picks_df, weekly_df, stat_col, position, pick)
    if baseline is None:
        return None  # no basis at all -- never show a number with nothing behind it

    std = league_fallback_std(weekly_df, stat_col)
    return Projection(
        player_id=player_id, player_name=player_name, stat_col=stat_col,
        projection=baseline, season_std=std,
        n_current_games=0, n_prior_games=0,
        method="rookie_prior", confidence="low",
        n_analog_players=n_analogs, analog_position=position, analog_pick=pick,
    )
