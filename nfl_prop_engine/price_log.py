"""Per-leg prices of confirmed football slips, for the goals report.

Every football leg Dan confirms on a bet-slip issue becomes one row in
football_goals/data/placed_legs.csv: the match, market and the price he
got. The goals report reads it to test whether the bookmaker's price picks
legs that land better than its own ratings do. No stake, returns or bet
reference is ever written: the repo is public.

A re-confirmed issue replaces that issue's rows. Rows with an issue number
of 0 or below are hand-entered seeds and are never touched here.
"""
import csv
import os
from datetime import datetime, timezone

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "football_goals", "data", "placed_legs.csv")

# The goals report's columns first; the last four keep each leg's place on
# its slip.
COLUMNS = ["issue", "confirmed_at", "date", "competition", "game", "market", "side", "line", "odds_text",
           "book_price", "bookmaker", "slip", "leg", "bet_type", "bet_builder_group"]


def _rows(issue: int, draft: dict, confirmed_at: str) -> list[dict]:
    rows = []
    for slip_no, slip in enumerate(draft["slips"], start=1):
        if slip.get("sport") != "football":
            continue
        for leg_no, leg in enumerate(slip["legs"], start=1):
            rows.append({
                "issue": issue, "confirmed_at": confirmed_at, "date": leg.get("date") or "",
                "competition": leg.get("competition") or "", "game": leg.get("game") or "",
                "market": leg.get("market") or "", "side": leg.get("side") or "",
                "line": "" if leg.get("book_line") is None else leg["book_line"],
                "odds_text": leg.get("odds_text") or "",
                "book_price": "" if leg.get("book_price") is None else leg["book_price"],
                "bookmaker": slip.get("bookmaker") or "", "slip": slip_no, "leg": leg_no,
                "bet_type": slip.get("bet_type") or "", "bet_builder_group": leg.get("bet_builder_group") or "",
            })
    return rows


def record(issue: int, draft: dict, path: str | None = None, now: datetime | None = None) -> int:
    """Writes this issue's football legs (replacing any earlier ones from
    it); returns how many. An issue with no football slip leaves the file
    alone."""
    path = path or PATH
    confirmed_at = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    new = _rows(issue, draft, confirmed_at)
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            columns = list(reader.fieldnames or COLUMNS)
            kept = [row for row in reader if str(row.get("issue")) != str(issue)]
    except FileNotFoundError:
        if not new:
            return 0
        columns, kept = list(COLUMNS), []
    if not new and len(kept) == _count(path):
        return 0
    columns += [c for c in COLUMNS if c not in columns]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept + new)
    return len(new)


def _count(path: str) -> int:
    with open(path, newline="") as f:
        return sum(1 for _ in csv.DictReader(f))
