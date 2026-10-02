"""Which fixtures each market covers (set under `markets:` in config.yaml).

Every fixture is still analysed and recorded in the history; a market's
table, accumulator and track record only use the fixtures in its scope."""
from __future__ import annotations

import logging

from .leagues import LEAGUES

log = logging.getLogger(__name__)
CONFIG_KEY = {"o15": "over_1_5", "gibh": "gibh"}
_warned: set = set()


def rules(cfg: dict, market: str) -> dict:
    r = (cfg.get("markets") or {}).get(CONFIG_KEY[market]) or {}
    kos = [str(k).strip() for k in (r.get("kickoffs") or [])]
    excl = [str(x).strip() for x in (r.get("exclude_leagues") or [])]
    known = {lg.name for lg in LEAGUES}
    for x in excl:
        if x not in known and x not in _warned:
            _warned.add(x)
            log.warning("config: '%s' under markets/%s/exclude_leagues isn't a league name; known: %s",
                        x, CONFIG_KEY[market], ", ".join(sorted(known)))
    return {"kickoffs": kos, "exclude_leagues": excl}


def in_scope(cfg: dict, market: str, league_name: str, kickoff) -> bool:
    r = rules(cfg, market)
    if league_name in r["exclude_leagues"]:
        return False
    if r["kickoffs"]:
        ko = "" if kickoff is None or kickoff != kickoff else str(kickoff).strip()  # NaN-safe
        return ko in r["kickoffs"]
    return True


def describe(cfg: dict, market: str) -> str:
    """One line for the page, e.g. '15:00 kick-offs only; excludes National League North'."""
    r = rules(cfg, market)
    parts = []
    if r["kickoffs"]:
        parts.append(" / ".join(r["kickoffs"]) + " kick-offs only")
    if r["exclude_leagues"]:
        parts.append("excludes " + ", ".join(r["exclude_leagues"]))
    return "; ".join(parts) or "all fixtures"
