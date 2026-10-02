"""Match one source's club names to another's (e.g. ESPN's "Peterborough
United" to football-data's "Peterboro") within a single league's clubs."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_DROP = {"fc", "afc", "the", "town", "city", "united", "utd", "athletic", "ath", "rovers", "rvs",
         "county", "harriers", "albion", "wanderers", "hotspur", "and", "&", "football", "club"}
_ALIASES = {
    "man": "manchester", "nottm": "nottingham", "sheffield weds": "sheffield wednesday",
    "peterboro": "peterborough", "inverness c": "inverness caledonian thistle",
    "queen of sth": "queen of the south", "airdrie": "airdrieonians", "mk dons": "milton keynes dons",
    "wolves": "wolverhampton", "spurs": "tottenham", "qpr": "queens park rangers",
    "west brom": "west bromwich", "bristol rvs": "bristol rovers", "hearts": "heart of midlothian",
    "st johnstone": "saint johnstone", "st mirren": "saint mirren", "raith rvs": "raith rovers",
}


def normalise(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9& ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for k, v in _ALIASES.items():
        s = re.sub(rf"\b{re.escape(k)}\b", v, s)
    return s


def _core(name: str) -> str:
    words = [w for w in normalise(name).split() if w not in _DROP]
    return " ".join(words) or normalise(name)


def score(a: str, b: str) -> float:
    ca, cb = _core(a), _core(b)
    full = SequenceMatcher(None, normalise(a), normalise(b)).ratio()
    if normalise(a) == normalise(b):
        return 1.0
    if ca == cb:  # "Manchester City" vs "Man City": decided by the dropped words
        return 0.9 + 0.09 * full
    s = SequenceMatcher(None, ca, cb).ratio()
    if ca.split()[0] == cb.split()[0]:
        s = max(s, 0.8)  # same leading word ("Sheffield ..." vs "Sheffield ...") is decided below
        s += 0.1 * SequenceMatcher(None, ca, cb).ratio()
    if ca in cb or cb in ca:
        s = max(s, 0.85)
    return min(s, 0.99)


def best_match(name: str, candidates, min_score: float = 0.72) -> str | None:
    """Best candidate for `name`, or None if nothing is close enough / it's ambiguous."""
    ranked = sorted(((score(name, c), c) for c in candidates), reverse=True)
    if not ranked or ranked[0][0] < min_score:
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.01 and ranked[0][0] < 1.0:
        return None
    return ranked[0][1]
