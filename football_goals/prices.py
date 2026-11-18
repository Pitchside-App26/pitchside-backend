"""Prices v ratings: do the bookmaker's prices pick Over 1.5 legs that land
more often than our ratings do?

data/placed_legs.csv holds the price of every football leg Dan has placed,
one row per leg. Confirmed bet-slip uploads write it (nfl_prop_engine/
price_log.py), and rows with an issue number of 0 or below are hand-entered
seeds. It never holds a stake. Each Over 1.5 leg is matched to the fixture in
history.csv: the same date, with club names matched loosely ("Queen of the
South" = "Queen of Sth"). Its graded result and our rating come from there.
"""
from __future__ import annotations

import csv
from html import escape
from pathlib import Path

import pandas as pd

from .names import best_match

PATH = Path(__file__).parent / "data" / "placed_legs.csv"
PRICE_BANDS = [(0, 1.13, "1/8 or shorter"), (1.13, 1.17, "2/15 to 1/6"), (1.17, 1.2, "2/11"),
               (1.2, 99, "1/5 or longer")]
RATING_BANDS = [(82, 101, "82%+"), (79, 82, "79-82%"), (0, 79, "under 79%")]


def _over_15(row: dict) -> bool:
    try:
        return (row.get("market") == "match_goals" and row.get("side") == "over"
                and float(row.get("line") or 0) == 1.5 and float(row.get("book_price") or 0) > 1)
    except ValueError:
        return False


def matched_legs(hist: pd.DataFrame, path: Path | None = None) -> dict:
    """Priced Over 1.5 legs matched to graded fixtures. The same fixture on
    two slips counts once (its first price)."""
    path = Path(path or PATH)
    out = {"legs": [], "waiting": 0, "unmatched": []}
    if not path.exists():
        return out
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if _over_15(r)]
    by_date = {d: g for d, g in hist.groupby("report_date")}
    seen = set()
    for r in rows:
        parts = (r.get("game") or "").replace(" vs ", " v ").split(" v ", 1)
        day = by_date.get(r.get("date"))
        if len(parts) != 2 or day is None:
            out["unmatched"].append(r.get("game") or "?")
            continue
        h = best_match(parts[0].strip(), set(day["home"]))
        a = best_match(parts[1].strip(), set(day["away"]))
        fx = day[(day["home"] == h) & (day["away"] == a)] if h and a else day.iloc[0:0]
        if fx.empty:
            out["unmatched"].append(r["game"])
            continue
        x = fx.iloc[0]
        key = (x["report_date"], x["home"], x["away"])
        if key in seen:
            continue
        seen.add(key)
        if x["status"] == "graded" and pd.notna(x["o15_combined"]):
            out["legs"].append({"price": float(r["book_price"]), "rating": float(x["o15_combined"]),
                                "won": str(x["o15_hit"]).lower() in ("true", "1", "1.0")})
        elif x["status"] == "pending":
            out["waiting"] += 1
    return out


def _table(legs, title, bands, value) -> str:
    rows = []
    for lo, hi, label in bands:
        g = [x for x in legs if lo <= value(x) < hi]
        if not g:
            continue
        won = sum(x["won"] for x in g)
        implied = sum(100 / x["price"] for x in g) / len(g)
        rating = sum(x["rating"] for x in g) / len(g)
        rows.append(f"<tr><td>{label}</td><td class=n>{won}/{len(g)}</td><td class=n>{100 * won / len(g):.0f}%</td>"
                    f"<td class=n>{implied:.0f}%</td><td class=n>{rating:.0f}%</td></tr>")
    return (f"<p class=label>By {title}</p><div class='card scroll'><table><thead><tr><th>{title.capitalize()}</th>"
            f"<th class=n>Legs</th><th class=n>Landed</th><th class=n>Price says</th><th class=n>We said</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>")


def section(hist: pd.DataFrame, path: Path | None = None) -> str:
    """The Results tab's "Prices v ratings" block ('' until a priced leg is graded)."""
    m = matched_legs(hist, path)
    legs = m["legs"]
    if not legs:
        return ""
    extra = []
    if m["waiting"]:
        extra.append(f"{m['waiting']} waiting for results")
    if m["unmatched"]:
        extra.append(f"{len(m['unmatched'])} not in the report's leagues or dates")
    note = (f"{len(legs)} priced Over 1.5 legs you've placed, graded" + (f" ({'; '.join(extra)})" if extra else "")
            + ". 'Price says' is the chance the bookmaker's price implies, margin included. If short prices land "
            "more often than high ratings do, rank legs by price. Read nothing into it under about 100 legs.")
    return ("<h2>Prices v ratings</h2><p class=sub style='margin:0'>" + escape(note) + "</p>"
            + _table(legs, "price", PRICE_BANDS, lambda x: x["price"])
            + _table(legs, "rating", RATING_BANDS, lambda x: x["rating"]))
