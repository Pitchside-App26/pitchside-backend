"""Step 3: player stats + draft picks for the projection engine.

Pulls last season plus the current one (see projection_engine.py for why:
early weeks need last year's data to blend against).

IMPORTANT, confirmed by direct download during development (not assumed):
nfl_data_py 0.3.3's import_weekly_data() only returns OFFENSE stats. The
spec's premise that nflverse bundles offense+defense+kicking into one file
is NOT true of the current package -- inspecting its source shows it reads
a single "player_stats_{year}.parquet" asset. Defense and kicking are
published as SEPARATE assets in the same GitHub release
(player_stats_def_{year}.parquet, player_stats_kicking_{year}.parquet),
which this module pulls directly with pandas.read_parquet since nfl_data_py
doesn't expose them. Verified real columns as of this writing:
  offense: passing_yards, passing_tds, completions, interceptions,
           rushing_yards, carries, receiving_yards, receptions, receiving_tds, ...
  defense: def_tackles, def_tackles_solo, def_sacks, def_interceptions,
           def_pass_defended, def_tds, ...

ALSO CONFIRMED (the hard way, running against a live current week): this
pre-aggregated player_stats release can lag real time by more than a full
season -- it had nothing past 2024 while live 2026 games were already
being played. The underlying raw play-by-play release did NOT have that
gap (play_by_play_2025/2026.parquet both existed and were current), so
each fetch function falls back to deriving the same stats from play-by-play
via derive_stats_from_pbp.py when the pre-built file 404s for a season.
"""
import logging

import nfl_data_py as nfl
import pandas as pd

from config import DEFENSE_STATS_URL
from derive_stats_from_pbp import derive_defense_weekly, derive_offense_weekly

logger = logging.getLogger(__name__)


def fetch_offense_weekly(seasons: list[int]) -> pd.DataFrame:
    """Fetches one season at a time rather than nfl_data_py's default
    single call for the whole list -- a single missing year 404s the
    entire batched call, taking every other requested year down with it."""
    frames = []
    for season in seasons:
        try:
            frames.append(nfl.import_weekly_data([season]))
        except Exception as exc:
            logger.warning(
                "No pre-built offense stats for season %s (%s) -- deriving from play-by-play instead.",
                season, exc,
            )
            try:
                frames.append(derive_offense_weekly(season))
            except Exception as pbp_exc:
                logger.warning("Play-by-play fallback also failed for season %s (%s)", season, pbp_exc)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "season_type" in df.columns:
        df = df[df["season_type"] == "REG"]
    return df.reset_index(drop=True)


def fetch_defense_weekly(seasons: list[int]) -> pd.DataFrame:
    frames = []
    for season in seasons:
        try:
            frames.append(pd.read_parquet(DEFENSE_STATS_URL.format(season=season)))
        except Exception as exc:
            logger.warning(
                "No pre-built defense stats for season %s (%s) -- deriving from play-by-play instead.",
                season, exc,
            )
            try:
                frames.append(derive_defense_weekly(season))
            except Exception as pbp_exc:
                logger.warning("Play-by-play fallback also failed for season %s (%s)", season, pbp_exc)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "season_type" in df.columns:
        df = df[df["season_type"] == "REG"]
    return df.reset_index(drop=True)


def fetch_draft_picks(seasons: list[int] | None = None) -> pd.DataFrame:
    """Round/pick + bio data, used for the rookie draft-analog projection.
    Confirmed columns: season, round, pick, gsis_id, position, college, age,
    plus career box-score totals (games, pass_yards, rec_yards, def_sacks,
    etc.) -- NOT college stats, so this alone can't drive a college-stat
    translation model (that's the larger project the spec explicitly defers).
    """
    df = nfl.import_draft_picks(seasons or [])
    return df


def fetch_receiving_usage(seasons: list[int]) -> pd.DataFrame:
    """Next Gen Stats receiving data -- targets and target share, CONFIRMED
    against real 2026 week 1 data to carry `player_gsis_id` directly (no ID
    crosswalk needed, unlike snap counts which key on pfr_player_id).
    Informational only right now (see explain.py) -- not folded into the
    projection itself, since usage-based projection would need real
    backtesting before trusting it the way the existing formula is.

    CONFIRMED real-data gotcha: nflverse includes a week=0 row per player
    alongside the real per-week rows -- a season-to-date aggregate, not an
    actual game (checked directly: week 0 and week 1 had the identical row
    count and, in week 1, identical target totals, since "season to date"
    and "week 1" are the same thing that early). Left in, this would
    silently double-count and skew any average computed from these rows
    once more real weeks exist -- dropped here before it reaches anything
    that averages by player.
    """
    frames = []
    for season in seasons:
        try:
            df = nfl.import_ngs_data("receiving", [season])
            df = df[df["week"] != 0]
            frames.append(df.rename(columns={"player_gsis_id": "player_id"}))
        except Exception as exc:
            logger.warning("No NGS receiving data for season %s (%s) -- skipping usage context.", season, exc)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def fetch_all_stats(current_season: int) -> dict[str, pd.DataFrame]:
    seasons = [current_season - 1, current_season]
    return {
        "offense": fetch_offense_weekly(seasons),
        "defense": fetch_defense_weekly(seasons),
        "draft_picks": fetch_draft_picks(),
        "receiving_usage": fetch_receiving_usage(seasons),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_all_stats(2024)
    for name, df in data.items():
        print(f"{name}: {df.shape}")
        print(df.head(2).to_string())
        print()
