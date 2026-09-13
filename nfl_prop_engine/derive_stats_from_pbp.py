"""Fallback: compute the same per-player weekly stats nflverse's
player_stats release would normally provide, directly from raw
play-by-play data, for seasons where that pre-built release doesn't exist
yet (confirmed real gap -- see config.PLAY_BY_PLAY_URL).

This reimplements a simplified version of the aggregation nflverse itself
runs to build player_stats in the first place. Verified against real 2026
week-1 play-by-play data during development (see module docstring in
fetch_stats.py for how the gap was found).
"""
import logging

import nfl_data_py as nfl
import pandas as pd

from config import PLAY_BY_PLAY_URL

logger = logging.getLogger(__name__)


def _load_pbp(season: int) -> pd.DataFrame:
    df = pd.read_parquet(PLAY_BY_PLAY_URL.format(season=season))
    return df[df["season_type"] == "REG"].reset_index(drop=True)


def _player_identity(season: int) -> pd.DataFrame:
    """player_id -> display name, position. Rosters are set independent of
    the stats aggregation pipeline, so this is available even in week 1."""
    roster = nfl.import_seasonal_rosters([season])
    roster = roster.rename(columns={"player_name": "player_display_name"})
    return roster[["player_id", "player_display_name", "position"]].drop_duplicates("player_id")


def _team_lookup(pbp: pd.DataFrame, id_cols: list[str]) -> pd.DataFrame:
    """One row per (season, week, player_id) with the team they were on and
    who they played, taken from whichever play(s) they were involved in."""
    frames = []
    for id_col in id_cols:
        sub = pbp[["season", "week", id_col, "posteam", "defteam"]].dropna(subset=[id_col])
        frames.append(sub.rename(columns={id_col: "player_id"}))
    if not frames:
        return pd.DataFrame(columns=["season", "week", "player_id", "recent_team", "opponent_team"])
    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby(["season", "week", "player_id"], as_index=False).agg(
        recent_team=("posteam", "first"), opponent_team=("defteam", "first")
    )


def derive_offense_weekly(season: int) -> pd.DataFrame:
    pbp = _load_pbp(season)

    passing = (
        pbp[pbp["pass_attempt"] == 1]
        .assign(passing_yards=lambda d: d["passing_yards"].fillna(0))
        .groupby(["season", "week", "passer_player_id"], as_index=False)
        .agg(
            completions=("complete_pass", "sum"),
            attempts=("pass_attempt", "sum"),
            passing_yards=("passing_yards", "sum"),
            passing_tds=("pass_touchdown", "sum"),
            interceptions=("interception", "sum"),
        )
        .rename(columns={"passer_player_id": "player_id"})
    )

    rushing = (
        pbp[pbp["rush_attempt"] == 1]
        .assign(rushing_yards=lambda d: d["rushing_yards"].fillna(0))
        .groupby(["season", "week", "rusher_player_id"], as_index=False)
        .agg(
            carries=("rush_attempt", "sum"),
            rushing_yards=("rushing_yards", "sum"),
            rushing_tds=("rush_touchdown", "sum"),
        )
        .rename(columns={"rusher_player_id": "player_id"})
    )

    receiving = (
        pbp[pbp["complete_pass"] == 1]
        .assign(receiving_yards=lambda d: d["receiving_yards"].fillna(0))
        .groupby(["season", "week", "receiver_player_id"], as_index=False)
        .agg(
            receptions=("complete_pass", "sum"),
            receiving_yards=("receiving_yards", "sum"),
            receiving_tds=("pass_touchdown", "sum"),
        )
        .rename(columns={"receiver_player_id": "player_id"})
    )

    team = _team_lookup(pbp, ["passer_player_id", "rusher_player_id", "receiver_player_id"])

    stats = team
    for frame in (passing, rushing, receiving):
        stats = stats.merge(frame, on=["season", "week", "player_id"], how="outer")

    numeric_cols = [
        "completions", "attempts", "passing_yards", "passing_tds", "interceptions",
        "carries", "rushing_yards", "rushing_tds",
        "receptions", "receiving_yards", "receiving_tds",
    ]
    for col in numeric_cols:
        if col not in stats.columns:
            stats[col] = 0
        stats[col] = stats[col].fillna(0)

    identity = _player_identity(season)
    stats = stats.merge(identity, on="player_id", how="left")
    stats["season_type"] = "REG"  # _load_pbp already filtered to REG; stamped
    # explicitly so concatenating with the pre-built file's schema elsewhere
    # doesn't turn these rows into NaN-season_type rows that a REG filter drops
    return stats


def derive_defense_weekly(season: int) -> pd.DataFrame:
    pbp = _load_pbp(season)

    def _melt(cols: list[str], value_name: str, credit: float = 1.0) -> pd.DataFrame:
        frames = []
        for col in cols:
            sub = pbp[["season", "week", col, "defteam"]].dropna(subset=[col])
            frames.append(sub.rename(columns={col: "player_id", "defteam": "team"}))
        if not frames:
            return pd.DataFrame(columns=["season", "week", "player_id", "team", value_name])
        combined = pd.concat(frames, ignore_index=True)
        combined[value_name] = credit
        return combined.groupby(["season", "week", "player_id"], as_index=False).agg(
            **{value_name: (value_name, "sum")}, team=("team", "first")
        )

    solo = _melt(["solo_tackle_1_player_id", "solo_tackle_2_player_id"], "solo_n")
    assist = _melt(
        ["assist_tackle_1_player_id", "assist_tackle_2_player_id",
         "assist_tackle_3_player_id", "assist_tackle_4_player_id"],
        "assist_n",
    )
    full_sacks = _melt(["sack_player_id"], "full_sack_n")
    half_sacks_1 = _melt(["half_sack_1_player_id"], "half_sack_n", credit=0.5)
    half_sacks_2 = _melt(["half_sack_2_player_id"], "half_sack_n", credit=0.5)
    interceptions = _melt(["interception_player_id"], "def_interceptions")

    stats = solo
    for frame in (assist, full_sacks, half_sacks_1, half_sacks_2, interceptions):
        stats = stats.merge(
            frame, on=["season", "week", "player_id"], how="outer", suffixes=("", "_dup")
        )
        if "team_dup" in stats.columns:
            stats["team"] = stats["team"].combine_first(stats.pop("team_dup"))

    for col in ["solo_n", "assist_n", "full_sack_n", "half_sack_n", "half_sack_n_dup", "def_interceptions"]:
        if col in stats.columns:
            stats[col] = stats[col].fillna(0)

    half_sack_total = stats.get("half_sack_n", 0) + stats.get("half_sack_n_dup", 0)
    stats["def_sacks"] = stats.get("full_sack_n", 0) + half_sack_total
    stats["def_tackles"] = stats.get("solo_n", 0) + stats.get("assist_n", 0)
    stats["def_interceptions"] = stats.get("def_interceptions", 0)

    identity = _player_identity(season)
    stats = stats.merge(identity, on="player_id", how="left")
    stats["season_type"] = "REG"

    keep = [
        "season", "week", "player_id", "player_display_name", "position", "team",
        "def_tackles", "def_sacks", "def_interceptions", "season_type",
    ]
    return stats[keep]
