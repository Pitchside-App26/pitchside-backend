import csv

import pandas as pd

from football_goals import history, prices

COLS = ["issue", "confirmed_at", "date", "competition", "game", "market", "side", "line", "odds_text",
        "book_price", "bookmaker", "slip", "leg", "bet_type", "bet_builder_group"]


def _hist():
    rows = [
        ("2026-11-21", "Queen of Sth", "Cove Rangers", "graded", 82.0, "True"),
        ("2026-11-21", "King's Lynn Town", "Spennymoor Town", "graded", 80.5, "False"),
        ("2026-11-21", "Forfar", "Spartans", "pending", 85.0, ""),
        ("2026-11-21", "Barrow", "Eastleigh", "void", 81.0, ""),
    ]
    return pd.DataFrame([dict(zip(["report_date", "home", "away", "status", "o15_combined", "o15_hit"], r))
                         for r in rows], columns=history.COLUMNS)


def _write(path, legs):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for n, (game, odds, price, *rest) in enumerate(legs, 1):
            market, side, line = rest or ("match_goals", "over", 1.5)
            w.writerow({"issue": 70, "date": "2026-11-21", "game": game, "market": market, "side": side,
                        "line": line, "odds_text": odds, "book_price": price, "slip": 1, "leg": n})


def test_legs_match_bookmaker_names_and_count_once(tmp_path):
    p = tmp_path / "placed_legs.csv"
    _write(p, [("Queen of the South v Cove Rangers", "1/7", 1.143),
               ("Kings Lynn v Spennymoor", "1/6", 1.167),
               ("Queen of the South v Cove Rangers", "1/8", 1.125),     # same fixture on a second slip
               ("Forfar Athletic v Spartans", "2/11", 1.182),           # not played yet
               ("Barrow v Eastleigh", "1/6", 1.167),                    # postponed: void, left out
               ("Arsenal v Chelsea", "1/5", 1.2),                       # not in the report
               ("Queen of the South v Cove Rangers", "4/5", 1.8, "btts", "yes", "")])   # not an Over 1.5 leg
    m = prices.matched_legs(_hist(), p)
    assert sorted((x["price"], x["won"]) for x in m["legs"]) == [(1.143, True), (1.167, False)]
    assert m["waiting"] == 1 and m["unmatched"] == ["Arsenal v Chelsea"]


def test_section_is_empty_until_a_priced_leg_is_graded(tmp_path):
    assert prices.section(_hist(), tmp_path / "missing.csv") == ""
    p = tmp_path / "placed_legs.csv"
    _write(p, [("Forfar Athletic v Spartans", "2/11", 1.182)])
    assert prices.section(_hist(), p) == ""
    _write(p, [("Queen of the South v Cove Rangers", "1/7", 1.143)])
    html = prices.section(_hist(), p)
    assert "Prices v ratings" in html and "2/15 to 1/6" in html and "1/1" in html


def test_the_seed_rows_match_the_history(tmp_path):
    with open(prices.PATH, newline="") as f:          # hand-entered seeds: issue 0 or below
        seeds = [r for r in csv.DictReader(f) if int(r["issue"]) in (0, -1)]
    p = tmp_path / "seeds.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(seeds[0]))
        w.writeheader()
        w.writerows(seeds)
    m = prices.matched_legs(history.load(), p)
    assert len(seeds) == 40 and len(m["legs"]) == 39 and not m["unmatched"]   # 40 legs, one void
