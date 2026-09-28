"""One-off smoke test for analyst_sweep.py -- confirms ANTHROPIC_API_KEY
actually works end to end against one real upcoming game, before anything
more gets built on top of the sweep. Not part of the main pipeline and not
on any schedule; run manually via the smoke-test-analyst-sweep workflow.

Costs exactly one real Claude API call (with web search) against the
account behind ANTHROPIC_API_KEY -- picks the current week's real first
game from the free nflverse schedule (no Odds API credits needed), so this
runs even while the odds account is out of quota.
"""
import json
import logging

from analyst_sweep import fetch_analyst_picks
from config import ODDS_API_TEAM_NAME_TO_ABBR, get_current_nfl_season
from fetch_schedule import fetch_week_games

logging.basicConfig(level=logging.INFO)

ABBR_TO_TEAM_NAME = {abbr: name for name, abbr in ODDS_API_TEAM_NAME_TO_ABBR.items()}


def main():
    season = get_current_nfl_season()
    games = fetch_week_games(season)
    if games.empty:
        print("No games found for the current week -- nothing to test against.")
        return

    week = int(games["week"].iloc[0])
    # A "current" week stays current until ALL its games finish, so the
    # week's game list can include already-played games (confirmed: picking
    # index 0 grabbed Thursday's game after it had already happened).
    # Sorting by date/time and taking the last one is the best available
    # proxy for "still upcoming" without a score column to filter on.
    row = games.sort_values(["gameday", "gametime"]).iloc[-1]
    away = ABBR_TO_TEAM_NAME.get(row["away_team"], row["away_team"])
    home = ABBR_TO_TEAM_NAME.get(row["home_team"], row["home_team"])
    game_description = f"{away} at {home}, NFL Week {week} {season}"

    print(f"Smoke-testing the analyst sweep against a real game: {game_description}\n")

    picks = fetch_analyst_picks(game_description, week)

    print(f"\n=== Got {len(picks)} pick(s) back ===\n")
    print(json.dumps(picks, indent=2))

    if not picks:
        print(
            "\nZero picks isn't necessarily broken -- it can mean the model genuinely "
            "found nothing published yet for this game, or found sources but nothing "
            "specific enough to report. What matters here is that the call itself "
            "succeeded (check the log lines above for an API error, which would print "
            "before this point)."
        )


if __name__ == "__main__":
    main()
