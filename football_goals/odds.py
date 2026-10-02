"""Optional Over 1.5 prices from The Odds API (the same ODDS_API_KEY secret as
the NFL engine). The 1.5 line is only in the 'alternate_totals' market,
which is priced per match (1 credit per match). Only real quoted prices are
shown -- nothing is ever estimated."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from .http_cache import FetchError, fetch
from .names import best_match

log = logging.getLogger(__name__)
BASE = "https://api.the-odds-api.com/v4/sports"


def over15_prices(league, fixtures, on: date, region: str = "uk"):
    """{(home, away): {"price": best decimal price, "book": bookmaker}} for one league."""
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ODDS_API_KEY secret is not set")
    if not league.odds_key:
        return {}
    start = datetime(on.year, on.month, on.day) - timedelta(hours=2)
    r = fetch(f"{BASE}/{league.odds_key}/events", params={
        "apiKey": key, "commenceTimeFrom": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commenceTimeTo": (start + timedelta(hours=28)).strftime("%Y-%m-%dT%H:%M:%SZ")})
    clubs = {t for f in fixtures for t in (f["home"], f["away"])}
    out = {}
    for ev in r.json():
        h, a = best_match(ev["home_team"], clubs), best_match(ev["away_team"], clubs)
        if not h or not a or not any(f["home"] == h and f["away"] == a for f in fixtures):
            continue
        try:
            rr = fetch(f"{BASE}/{league.odds_key}/events/{ev['id']}/odds", params={
                "apiKey": key, "regions": region, "markets": "alternate_totals", "oddsFormat": "decimal"})
        except FetchError as e:
            log.warning("odds for %s v %s unavailable: %s", h, a, e)
            continue
        best = None
        for bk in rr.json().get("bookmakers", []):
            for mk in bk.get("markets", []):
                for o in mk.get("outcomes", []):
                    if o.get("name") == "Over" and o.get("point") == 1.5:
                        if best is None or o["price"] > best["price"]:
                            best = {"price": o["price"], "book": bk.get("title", bk.get("key"))}
        if best:
            out[(h, a)] = best
        log.info("odds credits remaining: %s", rr.headers.get("x-requests-remaining"))
    return out
