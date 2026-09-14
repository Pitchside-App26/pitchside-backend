"""Step 4: match odds-API player names to nflverse player_display_name.

The odds API and nflverse will not always agree on formatting (suffixes,
nicknames, "Gabe" vs "Gabriel", etc). Resolution order:
  1. name_overrides.json exact match (persistent, human-curated)
  2. rapidfuzz fuzzy match against the candidate pool, restricted to players
     on the two teams in this event (cuts down both the search space and the
     chance of a wrong-but-plausible fuzzy hit)
  3. no match -> flagged, never silently dropped
"""
import json
import logging

import pandas as pd
from rapidfuzz import fuzz, process

from config import NAME_OVERRIDES_PATH

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 85  # 0-100; below this we'd rather flag than guess


def load_overrides() -> dict[str, str]:
    with open(NAME_OVERRIDES_PATH) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def match_name(
    odds_api_name: str,
    candidate_names: list[str],
    overrides: dict[str, str] | None = None,
) -> tuple[str | None, float, str]:
    """Returns (matched_name, score, method). matched_name is None if nothing
    cleared the threshold -- callers must handle that, not skip it silently.
    """
    overrides = overrides if overrides is not None else load_overrides()

    if odds_api_name in overrides:
        override_target = overrides[odds_api_name]
        if override_target in candidate_names:
            return override_target, 100.0, "override"
        logger.warning(
            "Override for %r points to %r, which isn't in this event's "
            "candidate pool -- falling back to fuzzy match.",
            odds_api_name, override_target,
        )

    if not candidate_names:
        return None, 0.0, "no_candidates"

    result = process.extractOne(odds_api_name, candidate_names, scorer=fuzz.token_sort_ratio)
    if result is None:
        return None, 0.0, "no_match"
    matched_name, score, _ = result
    if score >= FUZZY_MATCH_THRESHOLD:
        return matched_name, score, "fuzzy"
    return None, score, "below_threshold"


def match_props_to_players(
    odds_df: pd.DataFrame,
    roster_df: pd.DataFrame,
    name_col_odds: str = "player_name",
    name_col_roster: str = "player_display_name",
    team_col_roster: str = "recent_team",
) -> pd.DataFrame:
    """odds_df needs a `team` column (the team the prop's event involves,
    used to scope which candidates are eligible) plus name_col_odds.
    Returns odds_df with matched_player, match_score, match_method columns.
    """
    overrides = load_overrides()
    matched_names, scores, methods = [], [], []

    for _, row in odds_df.iterrows():
        candidates = roster_df.loc[
            roster_df[team_col_roster].isin(row["candidate_teams"]), name_col_roster
        ].unique().tolist()
        name, score, method = match_name(row[name_col_odds], candidates, overrides)
        matched_names.append(name)
        scores.append(score)
        methods.append(method)

    result = odds_df.copy()
    result["matched_player"] = matched_names
    result["match_score"] = scores
    result["match_method"] = methods

    unmatched = result[result["matched_player"].isna()]
    if not unmatched.empty:
        logger.warning(
            "%d player prop(s) could not be matched to an nflverse player: %s",
            len(unmatched), unmatched[name_col_odds].tolist(),
        )
    return result
