"""Step 2: live prop lines from The Odds API.

NEEDS LIVE VERIFICATION: this environment's network egress does not reach
the-odds-api.com (confirmed by testing during development -- both direct
requests and WebFetch were blocked), so none of this could be exercised
against a real response here. Before relying on it:
  1. Run verify_markets.py once with a real ODDS_API_KEY to confirm which
     market keys in config.py actually resolve (especially the DEFENSE_MARKETS
     ones -- see the warning there).
  2. Save one real event-odds response with save_raw_response() and check it
     matches the shape parse_event_odds() expects (documented inline below).

Credit budgeting per the spec: the /events list call is free; each
per-event odds call costs markets_requested x regions_requested credits.
With ~4 offense markets x 1 region = 4 credits/event, and up to ~14
events/week in season, budget carefully against the 500/month free tier --
that's why development happens against cached JSON, not live calls.
"""
import json
import logging
import os
import time
from datetime import date

import requests

from config import ODDS_API_BASE, ODDS_API_KEY, ODDS_CACHE_DIR, REGIONS, SPORT_KEY

logger = logging.getLogger(__name__)


class OddsApiError(RuntimeError):
    pass


def _get(path: str, params: dict) -> requests.Response:
    if not ODDS_API_KEY:
        raise OddsApiError("ODDS_API_KEY is not set (check your .env file).")
    resp = requests.get(f"{ODDS_API_BASE}{path}", params={**params, "apiKey": ODDS_API_KEY}, timeout=15)
    remaining = resp.headers.get("x-requests-remaining")
    used = resp.headers.get("x-requests-used")
    if remaining is not None:
        logger.info("Odds API credits used=%s remaining=%s", used, remaining)
    if resp.status_code != 200:
        raise OddsApiError(f"{resp.status_code} from {path}: {resp.text[:500]}")
    return resp


def list_events() -> list[dict]:
    """Does not count against quota per The Odds API docs -- reconfirm this
    hasn't changed before assuming it's free in a given billing period."""
    resp = _get(f"/sports/{SPORT_KEY}/events", {})
    return resp.json()


def _cache_path(event_id: str) -> str:
    os.makedirs(ODDS_CACHE_DIR, exist_ok=True)
    return os.path.join(ODDS_CACHE_DIR, f"{event_id}.json")


def fetch_event_odds(event_id: str, markets: list[str], use_cache: bool = False) -> dict:
    """Costs len(markets) * len(REGIONS.split(',')) credits. Set use_cache=True
    during development to replay a saved response instead of spending credits.
    """
    cache_path = _cache_path(event_id)
    if use_cache and os.path.exists(cache_path):
        logger.info("Loading cached odds for event %s", event_id)
        with open(cache_path) as f:
            return json.load(f)

    resp = _get(
        f"/sports/{SPORT_KEY}/events/{event_id}/odds",
        {"regions": REGIONS, "markets": ",".join(markets), "oddsFormat": "american"},
    )
    data = resp.json()
    save_raw_response(event_id, data)
    return data


def save_raw_response(event_id: str, data: dict) -> str:
    path = _cache_path(event_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def fetch_all_event_odds(
    event_ids: list[str], markets: list[str], use_cache: bool = False, pause_seconds: float = 0.5
) -> dict[str, dict]:
    """Sequential, with a small pause between live calls to be a reasonable
    API citizen -- there's no documented rate limit requiring this, it's
    just cheap insurance."""
    results = {}
    for event_id in event_ids:
        results[event_id] = fetch_event_odds(event_id, markets, use_cache=use_cache)
        if not use_cache:
            time.sleep(pause_seconds)
    return results


def parse_event_odds(raw: dict) -> list[dict]:
    """Flattens one event-odds response into rows.

    Expected shape (per The Odds API v4 public docs for player props --
    NOT independently confirmed against a live response in this session):
      { id, commence_time, home_team, away_team,
        bookmakers: [ { key, title, markets: [ { key, outcomes: [
          { name: "Over"|"Under", description: <player name>, price, point } ] } ] } ] }
    """
    rows = []
    event_id = raw.get("id")
    home_team = raw.get("home_team")
    away_team = raw.get("away_team")
    for bookmaker in raw.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            for outcome in market.get("outcomes", []):
                rows.append({
                    "event_id": event_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "bookmaker": bookmaker.get("key"),
                    "market": market.get("key"),
                    "player_name": outcome.get("description"),
                    "side": outcome.get("name"),
                    "point": outcome.get("point"),
                    "price": outcome.get("price"),
                })
    return rows


def pivot_over_under(rows: list[dict]) -> list[dict]:
    """One row per (event, market, player, bookmaker), carrying BOTH sides'
    price. The old code kept only the Over row on the reasoning that "Over
    and Under share the same point, one row is enough" -- true for the
    line, but Over and Under almost never share the same American odds
    (the vig split isn't even), so that also silently threw away the price
    of whichever side actually gets bet. `point` is the same at a given
    book regardless of which side's row it's read from, by construction.
    """
    from collections import defaultdict

    grouped: dict = defaultdict(dict)
    for r in rows:
        key = (r["event_id"], r["market"], r["player_name"], r["bookmaker"])
        entry = grouped[key]
        entry.setdefault("event_id", r["event_id"])
        entry.setdefault("home_team", r["home_team"])
        entry.setdefault("away_team", r["away_team"])
        entry.setdefault("bookmaker", r["bookmaker"])
        entry.setdefault("market", r["market"])
        entry.setdefault("player_name", r["player_name"])
        if r["point"] is not None:
            entry["point"] = r["point"]
        if r["side"] == "Over":
            entry["over_price"] = r["price"]
        elif r["side"] == "Under":
            entry["under_price"] = r["price"]
    return list(grouped.values())


def consolidate_lines(rows: list[dict], preferred_book: str = "draftkings") -> list[dict]:
    """Multiple books can quote slightly different lines (and prices) for
    the same prop. Prefer one consistent book when it has a line;
    otherwise take the median point across books offering that (event,
    market, player) -- prices from that first book are kept as-is rather
    than also medianed, since American odds don't average meaningfully the
    way a yardage line does. This is a simplifying design choice, not
    something the spec mandates -- revisit if book selection turns out to
    matter for accuracy. Expects rows already pivoted by pivot_over_under
    (no more "side" field -- both prices live on one row).
    """
    import statistics
    from collections import defaultdict

    grouped = defaultdict(list)
    for row in rows:
        key = (row["event_id"], row["market"], row["player_name"])
        grouped[key].append(row)

    consolidated = []
    for key, group in grouped.items():
        preferred = [r for r in group if r["bookmaker"] == preferred_book]
        if preferred:
            consolidated.append(preferred[0])
        else:
            points = [r["point"] for r in group if r.get("point") is not None]
            if not points:
                continue
            base = dict(group[0])
            base["point"] = statistics.median(points)
            base["bookmaker"] = f"median_of_{len(points)}_books"
            consolidated.append(base)
    return consolidated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    events = list_events()
    print(f"{len(events)} events this week")
    for e in events[:3]:
        print(e["id"], e["home_team"], "vs", e["away_team"], e["commence_time"])
