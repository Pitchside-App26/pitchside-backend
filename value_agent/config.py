"""
All tuneable constants for the value-bet agent.
Edit EDGE_THRESHOLD, MAX_WEEKLY_STAKE, and FLAT_STAKE here — nowhere else.
"""
from __future__ import annotations

# ── Thresholds ────────────────────────────────────────────────────────────────
EDGE_THRESHOLD = 0.03        # minimum edge to recommend a single (3%)
ACCA_EDGE_THRESHOLD = 0.08   # minimum combined edge to recommend a multi (8%)

# ── Staking ───────────────────────────────────────────────────────────────────
FLAT_STAKE = 10.0            # £ per qualifying single
MAX_WEEKLY_STAKE = 100.0     # £ total exposure cap per weekly scan
MIN_BANKROLL = 50.0          # £ below which the agent pauses all recommendations

# ── Sharp reference books (data only — never staked) ─────────────────────────
# Keys must match whatever the odds feed returns in the "key" field.
PRIMARY_SHARP = "pinnacle"
CROSS_CHECK_SHARP = "betfairix"   # Betfair Exchange
SHARP_BOOKS = [PRIMARY_SHARP, CROSS_CHECK_SHARP]

# Threshold: if de-vigged Pinnacle and Betfair true_p differ by more than
# this, flag the fixture as low-confidence.
LOW_CONFIDENCE_DELTA = 0.05

# ── Soft placement books ──────────────────────────────────────────────────────
# Verified against the feed in verify_books(); any absent key is silently
# dropped from the live set.  Do not hardcode the live set — always use
# the result of verify_books().
SOFT_BOOKS_CONFIGURED = [
    "bet365",
    "skybet",
    "betfred",
    "betway",
    "unibet_uk",
    "888sport",
    "boylesports",
    "sbk",
    "livescorebets",
    "virginbet",
    "spreadex",
]

# ── Leagues in scope ──────────────────────────────────────────────────────────
# Mapping: API sport key → human label
# National League is "conditional" — dropped at runtime if the feed returns
# no sharp prices for its fixtures.
LEAGUES: dict[str, str] = {
    "soccer_england_premier_league": "English Premier League",
    "soccer_england_championship": "EFL Championship",
    "soccer_england_league1": "EFL League One",
    "soccer_england_league2": "EFL League Two",
    "soccer_scotland_premiership": "Scottish Premiership",
    "soccer_england_national_league": "National League",  # conditional
}

CONDITIONAL_LEAGUES = {"soccer_england_national_league"}

# ── Markets ───────────────────────────────────────────────────────────────────
# h2h = 1X2 match result (always included)
# totals = Over/Under 2.5 (included once h2h is stable)
# btts  = Both Teams To Score (included once h2h is stable)
MARKETS = ["h2h", "totals", "btts"]
TOTALS_LINE = 2.5   # the only Over/Under line we care about

# ── API ───────────────────────────────────────────────────────────────────────
# OddsPapi / The Odds API  (https://the-odds-api.com)
# Key is read from the environment variable ODDS_API_KEY.
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
ODDS_REGION = "uk"
ODDS_FORMAT = "decimal"

# How many days ahead to pull fixtures (weekly scan ≈ 7-8 days)
FIXTURE_LOOKAHEAD_DAYS = 8

# ── LLM ──────────────────────────────────────────────────────────────────────
# ANTHROPIC_API_KEY is read from the environment.
COMMENTARY_MODEL = "claude-sonnet-4-6"

# ── Log file ─────────────────────────────────────────────────────────────────
LOG_DB_PATH = "value_agent/data/bets.db"
