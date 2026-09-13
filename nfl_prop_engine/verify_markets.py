"""One-time verification tool: confirms which market keys in config.py
actually resolve on your real The Odds API account, before you build the
rest of the week's run on top of them.

This could not be run during development -- this sandbox's network egress
does not reach the-odds-api.com at all. Every market key in config.py is a
best-effort guess (OFFENSE_MARKETS from public docs I'm fairly confident
about; DEFENSE_MARKETS considerably less so -- passes-defended in
particular may not be offered by any book on this API). Run this yourself
before the season starts.

COST WARNING: this queries markets one at a time against a single real
event so a bad key can't silently poison a batched request, which means it
spends roughly 1 credit per candidate market key (currently ~11) = ~11
credits. That's a one-time cost against your 500/month free tier, not a
per-week cost -- don't run it every week.

Usage:
    python verify_markets.py
"""
import logging

from config import ALL_MARKETS, DEFENSE_MARKETS, OFFENSE_MARKETS
from fetch_odds import OddsApiError, _get, list_events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_market(event_id: str, market_key: str) -> tuple[bool, str]:
    try:
        resp = _get(
            f"/sports/americanfootball_nfl/events/{event_id}/odds",
            {"regions": "us", "markets": market_key, "oddsFormat": "american"},
        )
        data = resp.json()
        has_data = any(
            m.get("key") == market_key
            for b in data.get("bookmakers", [])
            for m in b.get("markets", [])
        )
        return has_data, "has data" if has_data else "200 OK but no bookmaker offers it"
    except OddsApiError as exc:
        return False, str(exc)


def main():
    events = list_events()
    if not events:
        print("No upcoming NFL events found -- try again closer to a game week.")
        return
    event = events[0]
    print(f"Verifying markets against: {event['home_team']} vs {event['away_team']} ({event['id']})\n")

    print("=== OFFENSE_MARKETS ===")
    for key in OFFENSE_MARKETS:
        ok, detail = check_market(event["id"], key)
        print(f"  {'OK ' if ok else 'BAD'}  {key:35s} {detail}")

    print("\n=== DEFENSE_MARKETS (unverified guesses -- check these closely) ===")
    for key in DEFENSE_MARKETS:
        ok, detail = check_market(event["id"], key)
        print(f"  {'OK ' if ok else 'BAD'}  {key:35s} {detail}")

    print(
        "\nFor any BAD key: check the current market list at "
        "the-odds-api.com/sports-odds-data/betting-markets.html and update "
        "config.py. For a key you're not sure exists, that page's NFL "
        "section (not theoddsapi.com -- confirm you're on the right site) "
        "is the source of truth, not this script's guesses."
    )


if __name__ == "__main__":
    main()
