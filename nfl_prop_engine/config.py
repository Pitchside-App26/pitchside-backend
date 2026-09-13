"""Shared constants and settings for the NFL prop ranking engine.

Everything marked VERIFIED below was confirmed by directly pulling the
underlying nflverse data during development (not assumed from docs or
memory). Everything marked NEEDS LIVE VERIFICATION could not be checked
during development because this environment's network egress does not
reach the-odds-api.com -- confirm these against your own account before
trusting the ranked output.
"""
import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# The Odds API
# ---------------------------------------------------------------------------
# NEEDS LIVE VERIFICATION: base URL / path shape. This matches the public v4
# docs as of this writing but the-odds-api.com's own docs are the source of
# truth -- re-check before relying on this in season.
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
SPORT_KEY = "americanfootball_nfl"
REGIONS = "us"

# Offense market keys. VERIFIED historically correct against The Odds API's
# NFL market list, but not re-confirmed live in this session -- run
# verify_markets.py once against your own key before the season starts.
OFFENSE_MARKETS = {
    "player_pass_yds": {"stat_col": "passing_yards", "position_group": "QB"},
    "player_pass_tds": {"stat_col": "passing_tds", "position_group": "QB"},
    "player_pass_completions": {"stat_col": "completions", "position_group": "QB"},
    "player_pass_interceptions": {"stat_col": "interceptions", "position_group": "QB"},
    "player_rush_yds": {"stat_col": "rushing_yards", "position_group": "RB"},
    "player_rush_attempts": {"stat_col": "carries", "position_group": "RB"},
    "player_reception_yds": {"stat_col": "receiving_yards", "position_group": "WR"},
    "player_receptions": {"stat_col": "receptions", "position_group": "WR"},
}

# Defensive market keys. NEEDS LIVE VERIFICATION -- these are the most likely
# correct keys based on how sportsbooks actually offer defensive props
# (combined tackles+assists is standard; separate "solo tackles" and "passes
# defended" markets are far less commonly offered and may not exist on this
# API at all). Do not assume all of these resolve -- run verify_markets.py.
DEFENSE_MARKETS = {
    "player_tackles_assists": {"stat_col": "def_tackles", "position_group": "DEF"},
    "player_sacks": {"stat_col": "def_sacks", "position_group": "DEF"},
    "player_defensive_interceptions": {"stat_col": "def_interceptions", "position_group": "DEF"},
    # Passes defended is offered by very few books on this API, if any.
    # Uncomment and confirm the key name with verify_markets.py if you find it.
    # "player_passes_defended": {"stat_col": "def_pass_defended", "position_group": "DEF"},
}

ALL_MARKETS = {**OFFENSE_MARKETS, **DEFENSE_MARKETS}

# ---------------------------------------------------------------------------
# nflverse data sources
# ---------------------------------------------------------------------------
# VERIFIED by direct download during development: nfl_data_py 0.3.3's
# import_weekly_data() only returns OFFENSE stats (confirmed by inspecting
# its source -- it reads a single "player_stats_{year}.parquet" asset).
# Defense and kicking live in SEPARATE assets under the same GitHub release
# that nfl_data_py does not yet expose, so we pull those directly.
NFLVERSE_RELEASE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"
DEFENSE_STATS_URL = NFLVERSE_RELEASE_BASE + "/player_stats/player_stats_def_{season}.parquet"
KICKING_STATS_URL = NFLVERSE_RELEASE_BASE + "/player_stats/player_stats_kicking_{season}.parquet"

# VERIFIED: nfl_data_py.import_schedules() reads http://www.habitatring.com/games.csv,
# which is a plain HTTP mirror of the same data published as a GitHub release
# asset below. If import_schedules() ever fails (e.g. that mirror is down or
# blocked by a restrictive network), fetch_schedule.py falls back to this URL,
# which was confirmed reachable and schema-identical during development
# (has spread_line, total_line, roof, etc.).
SCHEDULES_FALLBACK_URL = NFLVERSE_RELEASE_BASE + "/schedules/games.parquet"

# ---------------------------------------------------------------------------
# Projection engine tuning
# ---------------------------------------------------------------------------
SHRINKAGE_K = 4  # "games" of shrinkage strength -- starting point, tune against real results
ROOKIE_DRAFT_SLOT_WINDOW = 20  # +/- picks considered "similar draft slot"
ROOKIE_MIN_GAMES_FOR_PRIOR = 1  # analog players need at least 1 of games 1-3 logged
MIN_COMBINED_GAMES_FOR_VETERAN_PROJECTION = 3

# Position-group mapping between nflverse (fine-grained) and stat markets
# (coarse: QB/RB/WR/TE/DEF). WR and TE are pooled into the same opponent
# "allowed" pool per the spec's stated limitation (no slot/outside splits).
POSITION_GROUP_MAP = {
    "QB": "QB",
    "RB": "RB", "FB": "RB",
    "WR": "WR", "TE": "WR",
    "CB": "DEF", "FS": "DEF", "SS": "DEF", "ILB": "DEF", "OLB": "DEF",
    "MLB": "DEF", "DE": "DEF", "DT": "DEF", "NT": "DEF", "LB": "DEF", "DB": "DEF", "S": "DEF",
}


def get_current_nfl_season(today: date | None = None) -> int:
    """NFL seasons are named by the calendar year they kick off in.
    Jan/Feb games (playoffs/Super Bowl) belong to the season that started
    the previous fall."""
    today = today or date.today()
    return today.year - 1 if today.month <= 2 else today.year


NAME_OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "name_overrides.json")
ODDS_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
RESULTS_DB_PATH = os.path.join(os.path.dirname(__file__), "results_log.sqlite3")
