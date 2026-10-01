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

# Defensive market keys. Live-checked with verify_markets.py on 2026-09-13
# against 3 games kicking off that same day (as real a test as it gets --
# not a "too early, no props posted yet" false negative):
#   player_tackles_assists          -- CONFIRMED, has real data
#   player_sacks                    -- CONFIRMED, has real data
#   player_defensive_interceptions  -- CONFIRMED NOT OFFERED by any book on
#       any of the 3 games checked; removed below. Sportsbooks on this API
#       apparently just don't offer a "will this defender record an
#       interception" prop -- re-run verify_markets.py periodically if you
#       want to check whether that changes.
DEFENSE_MARKETS = {
    "player_tackles_assists": {"stat_col": "def_tackles", "position_group": "DEF"},
    "player_sacks": {"stat_col": "def_sacks", "position_group": "DEF"},
    # Passes defended is offered by very few books on this API, if any.
    # Uncomment and confirm the key name with verify_markets.py if you find it.
    # "player_passes_defended": {"stat_col": "def_pass_defended", "position_group": "DEF"},
}

ALL_MARKETS = {**OFFENSE_MARKETS, **DEFENSE_MARKETS}

# CONFIRMED BUG, found running against a real live week: The Odds API
# identifies teams by full name ("New York Giants"), while nflverse (and
# so the rest of this codebase) uses short codes ("NYG"). A live run
# comparing these directly always found zero matching events, even for a
# real live week with 16 real games. This is the standard, stable 32-team
# mapping between the two -- confirmed against real event names returned
# live (e.g. "Detroit Lions vs New Orleans Saints", "Philadelphia Eagles
# vs Washington Commanders").
ODDS_API_TEAM_NAME_TO_ABBR = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}

# Human-readable labels for the frontend -- stat_col values are internal
# (match nflverse's own column names), these are what a viewer sees.
STAT_LABELS = {
    "passing_yards": "Pass Yds",
    "passing_tds": "Pass TDs",
    "completions": "Completions",
    "interceptions": "INTs Thrown",
    "rushing_yards": "Rush Yds",
    "carries": "Carries",
    "receiving_yards": "Rec Yds",
    "receptions": "Receptions",
    "def_tackles": "Tackles",
    "def_sacks": "Sacks",
    "def_interceptions": "INTs",
}

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

# VERIFIED the hard way: nflverse's pre-aggregated player_stats release can
# lag real time by more than a full season (it had nothing past 2024 while
# live 2026 games were already being played), but the underlying raw
# play-by-play release does not -- confirmed play_by_play_2025.parquet and
# play_by_play_2026.parquet both exist and are current. derive_stats_from_pbp.py
# uses this as a fallback to compute the same per-player weekly totals
# ourselves when the pre-built file isn't available yet for a season.
PLAY_BY_PLAY_URL = NFLVERSE_RELEASE_BASE + "/pbp/play_by_play_{season}.parquet"

# ---------------------------------------------------------------------------
# Projection engine tuning
# ---------------------------------------------------------------------------
SHRINKAGE_K = 4  # "games" of shrinkage strength -- starting point, tune against real results
ROOKIE_DRAFT_SLOT_WINDOW = 20  # +/- picks considered "similar draft slot"
ROOKIE_MIN_GAMES_FOR_PRIOR = 1  # analog players need at least 1 of games 1-3 logged
MIN_COMBINED_GAMES_FOR_VETERAN_PROJECTION = 3

# Which stat columns get the game-context (spread/total) adjustment in
# game_context.py, and how. Sets, not a single "offense" bucket, because
# rushing and passing/receiving volume move in OPPOSITE directions off the
# same spread (a big favorite runs more and throws less; a big underdog does
# the reverse) -- see game_context.apply_game_context. Defensive stats are
# deliberately left out for now: their real relationship to game script
# (tackle opportunities scale with the OPPONENT's plays run, not this team's
# own implied total) is a different, more complex mechanism this first pass
# doesn't attempt to guess at.
RUSH_VOLUME_STATS = {"rushing_yards", "carries"}
PASS_VOLUME_STATS = {
    "passing_yards", "passing_tds", "completions", "interceptions",
    "receiving_yards", "receptions",
}

# Both starting points, same as SHRINKAGE_K above -- unvalidated until
# results_log.sqlite3 has enough graded weeks to actually tune them.
GAME_ENV_WEIGHT = 0.2  # how much this team's implied total (vs. league-average) scales volume
GAME_SCRIPT_WEIGHT = 0.15  # how much the spread tilts the rush/pass mix
GAME_SCRIPT_SCALE = 10.0  # points of spread that reach the full script tilt; clipped beyond this

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

# ---------------------------------------------------------------------------
# Accumulator engine (Week 4 upgrade spec) -- see docs/week4-upgrade-spec.md
# ---------------------------------------------------------------------------
# Written after both Week 3 accumulators lost. The failures were: under legs
# that depended on game script, lines taken after they'd moved (bet365 sat
# well above the US market on several), filler legs added just to reach six,
# and picks leaning on a single analyst. This section's settings exist to
# make each of those a gate a leg can fail, not a judgment call made in the
# moment.
SIDES = ["over"]  # config, not a constant someone forgot to make configurable -- flip deliberately, not by accident
UNDERS_WATCHLIST = False  # True -> unders get their own report section, never the accumulator builder
ONE_PLAY_MARKETS = False  # longest rush/reception, anytime TD -- excluded from accumulators; one play decides them

LINE_THRESHOLD = {"yards": 2.0, "counts": 0.0}  # bet365 line must be <= US consensus + this, or the leg fails
MIN_PRICE_DECIMAL = 1.80  # bet365 over price must clear this (~4/5) or the leg fails regardless of the line
LINE_MOVEMENT_FLAG = {"yards": 3.0, "counts": 1.0}  # flag (not fail) if the consensus line moved this much since the opener

FORM_WINDOW = 6  # games of recent form the Form/Outlier gates look at, reaching into the prior season if needed
FORM_MIN_HIT_RATE = 0.5  # Form gate: fraction of the last FORM_WINDOW games clearing the line
OUTLIER_MIN_PCT_OF_LINE = 0.90  # Outlier gate: average of the OTHER games (best one dropped) must reach this % of the line -- the Jahmyr Gibbs check: 104/game from a 156 and a 52 is not a trend
ROLE_CHANGE_FLAG_POINTS = 15.0  # Role gate: snap/route share swing (percentage points) vs. prior season that gets flagged for manual review
GAME_SCRIPT_RUSHING_MAX_DOG = 3.0  # Game-script gate, rushing overs: team must be favored, or an underdog by no more than this many points
GAME_SCRIPT_PASSING_MIN_TOTAL = 45.0  # Game-script gate, passing/receiving overs: pass unless the team is an underdog OR the total is at least this

MIN_SOURCES = 2  # Sources gate: independent analysts (from the sweep) backing the over
MAX_LEGS = 6

# One accumulator per Sunday window (Dan, 1 Oct), by Eastern kickoff time
# (nflverse's gametime). Games outside both windows (London mornings,
# Thursday/Sunday/Monday nights) are still ranked but never used for an acca.
ACCA_WINDOWS = {
    "early": {"label": "Early games", "start_et": "13:00", "end_et": "14:00"},
    "late": {"label": "Late games", "start_et": "16:00", "end_et": "17:00"},
}
# Dan's call (1 Oct): when fewer than MAX_LEGS legs pass every gate in a
# window, top the acca up with legs that failed exactly one gate, marked as
# fillers on the page and in the log. This departs from the spec's
# "never pad" rule; set False to go back to it.
FILL_WITH_NEAR_MISSES = True
MAX_LEGS_PER_GAME = 2  # same-game pairs are tagged as bet-builder legs -- bet365 prices those separately
STAKE_GBP = 5.0  # flat stake; never rises after a loss

TIMEZONE = "Europe/London"  # display only -- everything is stored in UTC
ODDS_API_REGIONS_ACCA = ["us"]
CREDIT_CAP = 500  # print the estimated credit cost (events x markets x regions) and refuse to run over this

# Which LINE_THRESHOLD/LINE_MOVEMENT_FLAG entry a stat uses -- yardage props
# get more tolerance than count props, per the spec (2.0 yards vs 0.0 for
# receptions/attempts, since a single reception is a much bigger relative
# swing than a single yard).
YARDAGE_STATS = {"passing_yards", "rushing_yards", "receiving_yards"}
COUNT_STATS = {"completions", "interceptions", "carries", "receptions", "passing_tds"}


def market_kind_for(stat_col: str) -> str:
    if stat_col in YARDAGE_STATS:
        return "yards"
    return "counts"  # anything not explicitly yardage is treated as a count stat


ANALYST_SWEEP = {
    "enabled": True,
    # False (since 1 Oct): analyst backing is shown and logged per leg but
    # doesn't exclude anything. Turn back into a gate (MIN_SOURCES backers
    # required) if graded results show backed legs hit more -- see the
    # accumulator section of grade_results.py's report.
    "sources_gate": False,
    "model": "claude-sonnet-5",  # structured extraction against a schema, not deep reasoning -- Sonnet over Opus on cost
    # Only games that still have a leg after every other gate are swept; this
    # caps how many, keeping the games with the most surviving legs. The
    # first live run cost $0.84 for one game (~300k input tokens of search
    # results), so 3 keeps a weekly run near $2.50, inside the $15/month cap.
    "max_games": 3,
    "max_workers": 4,
    "max_continuations": 3,  # resumes after stop_reason="pause_turn"
    # List prices, used only to log an estimated cost per run.
    "usd_per_mtok_input": 2.0,
    "usd_per_mtok_output": 10.0,
    "usd_per_web_search": 0.01,
    "max_age_days": 7,
    "crowding_flag_outlets": 4,  # 4+ independent outlets backing a leg -> flag as crowded (the line has likely already moved)
    "flag_contested": True,  # any analyst backing the under -> flag the leg for manual review (the Mayfield lesson)
    "spend_cap_usd": 15.0,  # hard monthly cap on the separate console.anthropic.com account this calls -- see README
    "min_picks_for_scorecard": 5,  # an analyst's hit rate only shows once they have this many logged picks
    "outlets": [
        "Action Network", "Covers", "SI", "FanDuel Research", "Sharp Football Analysis",
        "SportsBettingDime", "SBR", "Fantasy Life", "VSiN", "RotoWire", "ESPN",
        "Dimers", "Action Network player projections",
    ],
}

# Bet-slip intake: Dan opens a GitHub issue with a screenshot of the slip he
# actually placed; the bet-slip workflow reads it with the Claude API, posts
# what it parsed for him to check, and only logs it once he replies "confirm".
BET_SLIP = {
    "model": "claude-sonnet-5",  # same account/key/spend cap as the analyst sweep; the confirm step, not model tier, is the accuracy backstop
    "label": "bet-slip",
    "max_images": 4,
    "max_image_bytes": 5_000_000,  # Claude API per-image limit
}
