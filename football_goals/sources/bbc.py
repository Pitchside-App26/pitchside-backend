"""BBC Sport league tables (no key), used only as an independent published
table to validate leagues ESPN doesn't cover. The page embeds its data as
JSON in window.__INITIAL_DATA__; every club row carries name, matchesPlayed,
goalsScoredFor and goalsScoredAgainst."""
from __future__ import annotations

import json
import re

from ..http_cache import fetch

BASE = "https://www.bbc.co.uk/sport/football"


def parse_table(html: str) -> dict[str, dict]:
    m = re.search(r'window\.__INITIAL_DATA__\s*=\s*("(?:[^"\\]|\\.)*")', html)
    if not m:
        raise ValueError("BBC table page has no embedded data (page layout may have changed)")
    data = json.loads(json.loads(m.group(1)))
    out: dict[str, dict] = {}

    def walk(o):
        if isinstance(o, dict):
            if {"name", "matchesPlayed", "goalsScoredFor", "goalsScoredAgainst"} <= o.keys():
                out[o["name"]] = {"gp": int(o["matchesPlayed"]), "gf": int(o["goalsScoredFor"]),
                                  "ga": int(o["goalsScoredAgainst"])}
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    if not out:
        raise ValueError("BBC table page had no club rows")
    return out


def table(slug: str) -> dict[str, dict]:
    return parse_table(fetch(f"{BASE}/{slug}/table").text)
