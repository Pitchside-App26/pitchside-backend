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
"""
import logging

import nfl_data_py as nfl
import pandas as pd

from config import DEFENSE_STATS_URL

logger = logging.getLogger(__name__)


def fetch_offense_weekly(seasons: list[int]) -> pd.DataFrame:
    df = nfl.import_weekly_data(seasons)
    return df[df["season_type"] == "REG"].reset_index(drop=True)


def fetch_defense_weekly(seasons: list[int]) -> pd.DataFrame:
    frames = []
    for season in seasons:
        try:
            frames.append(pd.read_parquet(DEFENSE_STATS_URL.format(season=season)))
        except Exception as exc:
            logger.warning("No defense stats file for season %s (%s)", season, exc)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df[df["season_type"] == "REG"].reset_index(drop=True)


def fetch_draft_picks(seasons: list[int] | None = None) -> pd.DataFrame:
    """Round/pick + bio data, used for the rookie draft-analog projection.
    Confirmed columns: season, round, pick, gsis_id, position, college, age,
    plus career box-score totals (games, pass_yards, rec_yards, def_sacks,
    etc.) -- NOT college stats, so this alone can't drive a college-stat
    translation model (that's the larger project the spec explicitly defers).
    """
    df = nfl.import_draft_picks(seasons or [])
    return df


def fetch_all_stats(current_season: int) -> dict[str, pd.DataFrame]:
    seasons = [current_season - 1, current_season]
    return {
        "offense": fetch_offense_weekly(seasons),
        "defense": fetch_defense_weekly(seasons),
        "draft_picks": fetch_draft_picks(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_all_stats(2024)
    for name, df in data.items():
        print(f"{name}: {df.shape}")
        print(df.head(2).to_string())
        print()
