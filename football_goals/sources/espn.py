"""ESPN's public JSON (no key): fixture status for a date (to catch
postponements), half-time scores via per-match summaries, and the
published league table used for validation. Covers ENG1-5 and SCO1-2;
it has no Scottish League One/Two or National League North/South."""
from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..http_cache import fetch

log = logging.getLogger(__name__)
SITE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer"
UK = ZoneInfo("Europe/London")
OFF_STATUSES = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED", "STATUS_ABANDONED",
                "STATUS_SUSPENDED", "STATUS_FORFEIT", "STATUS_DELAYED"}
DONE_STATUSES = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN"}


def scoreboard(slug: str, on: date) -> list[dict]:
    r = fetch(f"{SITE}/{slug}/scoreboard", params={"dates": on.strftime("%Y%m%d")})
    out = []
    for e in r.json().get("events", []):
        comp = e["competitions"][0]
        sides = {c["homeAway"]: c for c in comp["competitors"]}
        ko = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(UK)
        if ko.date() != on:
            continue
        out.append({
            "id": e["id"],
            "home": sides["home"]["team"]["displayName"],
            "away": sides["away"]["team"]["displayName"],
            "status": e["status"]["type"]["name"],
            "kickoff": ko.strftime("%H:%M"),
            "home_score": sides["home"].get("score"),
            "away_score": sides["away"].get("score"),
        })
    return out


def halftime(slug: str, event_id: str) -> tuple[int, int] | None:
    """(home, away) half-time goals from the match summary's first-period line scores."""
    r = fetch(f"{SITE}/{slug}/summary", params={"event": event_id})
    comp = r.json().get("header", {}).get("competitions", [{}])[0]
    ht = {}
    for c in comp.get("competitors", []):
        ls = c.get("linescores") or []
        if not ls:
            return None
        ht[c["homeAway"]] = int(float(ls[0].get("displayValue", ls[0].get("value"))))
    if set(ht) != {"home", "away"}:
        return None
    return ht["home"], ht["away"]


def standings(slug: str) -> dict[str, dict]:
    """Published table: {team: {gp, gf, ga}}."""
    r = fetch(f"{STANDINGS}/{slug}/standings")
    j = r.json()
    groups = j.get("children") or [j]
    out = {}
    for g in groups:
        for entry in (g.get("standings") or {}).get("entries", []):
            stats = {s.get("name"): s.get("value") for s in entry.get("stats", [])}
            out[entry["team"]["displayName"]] = {
                "gp": int(stats.get("gamesPlayed") or 0),
                "gf": int(stats.get("pointsFor") or 0),
                "ga": int(stats.get("pointsAgainst") or 0),
            }
    return out
