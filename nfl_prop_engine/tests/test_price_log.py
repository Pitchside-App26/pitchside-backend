import csv
from datetime import datetime, timezone

import price_log

NOW = datetime(2026, 11, 21, 9, 30, tzinfo=timezone.utc)


def _draft(price=2.1):
    leg = {"game": "Forfar Athletic v Spartans", "competition": "Scottish League Two", "date": "2026-11-21",
           "market": "match_goals", "side": "over", "book_line": 2.5, "odds_text": "11/10", "book_price": price,
           "bet_builder_group": None}
    return {"slips": [
        {"sport": "football", "bet_type": "accumulator", "bookmaker": "Spreadex", "legs": [leg]},
        {"sport": "nfl", "bet_type": "single", "bookmaker": "bet365", "legs": [{"player": "Drake Maye"}]},
    ]}


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_football_legs_are_recorded_without_any_stake(tmp_path):
    path = tmp_path / "data" / "placed_legs.csv"
    assert price_log.record(12, _draft(), str(path), now=NOW) == 1
    [row] = _rows(path)
    assert row["issue"] == "12" and row["game"] == "Forfar Athletic v Spartans" and row["book_price"] == "2.1"
    assert row["confirmed_at"] == "2026-11-21T09:30:00Z" and row["bookmaker"] == "Spreadex"
    assert not any("stake" in c or "return" in c for c in row)


def test_a_reconfirm_replaces_its_rows_and_seed_rows_are_kept(tmp_path):
    path = tmp_path / "placed_legs.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=price_log.COLUMNS[:11])
        w.writeheader()
        w.writerow({"issue": 0, "game": "Seed v Row", "book_price": 1.3})
    price_log.record(12, _draft(2.1), str(path), now=NOW)
    price_log.record(12, _draft(2.2), str(path), now=NOW)
    rows = _rows(path)
    assert [(r["issue"], r["book_price"]) for r in rows] == [("0", "1.3"), ("12", "2.2")]


def test_an_nfl_only_issue_leaves_the_file_alone(tmp_path):
    path = tmp_path / "placed_legs.csv"
    draft = {"slips": [_draft()["slips"][1]]}
    assert price_log.record(13, draft, str(path), now=NOW) == 0
    assert not path.exists()
