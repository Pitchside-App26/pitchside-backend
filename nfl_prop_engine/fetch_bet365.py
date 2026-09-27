"""Manual bet365 CSV import (Week 4 upgrade spec, Requirement 3).

Scraping bet365 is explicitly out of scope (their terms of service) --
lines come in by hand instead, via `bet365_week{N}.csv` with columns:
player, market, line, over_price. Player names are resolved against the
nflverse roster through the SAME match_players.py pipeline the live Odds
API rows already use -- no parallel normalization table, since
name_overrides.json already solves exactly this problem generically (a
"Kenneth Walker III" vs "Kenneth Walker" mismatch is the same class of
problem whether it comes from the API or a hand-typed CSV).
"""
import csv
import re

REQUIRED_COLUMNS = {"player", "market", "line", "over_price"}


class FractionalOddsError(ValueError):
    pass


def parse_fractional_odds(raw: str | float | int) -> float:
    """Converts a fractional-odds string ("20/23", "5/4", "evens") to
    decimal odds (1.869..., 2.25, 2.0). Also accepts an already-decimal
    value (a float, or a numeric string like "1.91") unchanged, in case a
    row gets entered that way instead.
    """
    if isinstance(raw, (int, float)):
        return float(raw)

    text = raw.strip().lower()
    if text in ("evens", "evs"):
        return 2.0

    match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", text)
    if match:
        numerator, denominator = int(match.group(1)), int(match.group(2))
        if denominator == 0:
            raise FractionalOddsError(f"Zero denominator in fractional odds: {raw!r}")
        return numerator / denominator + 1.0

    try:
        return float(text)
    except ValueError:
        raise FractionalOddsError(f"Unrecognised odds format: {raw!r}") from None


def import_bet365_csv(path: str) -> list[dict]:
    """Returns rows shaped like fetch_odds.parse_event_odds()'s output
    (player_name, market, point, price, bookmaker) -- the same shape, so
    bet365 rows flow through the same match_props_to_players() and gate
    pipeline as live API rows instead of a parallel code path. Raises
    ValueError immediately (not a silent skip) if a required column is
    missing, since a bet365 CSV with the wrong header would otherwise
    quietly import as all-empty.
    """
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing required column(s): {sorted(missing)}")
        for row in reader:
            rows.append({
                "player_name": row["player"].strip(),
                "market": row["market"].strip(),
                "point": float(row["line"]),
                "price": parse_fractional_odds(row["over_price"]),
                "bookmaker": "bet365",
            })
    return rows
