from fetch_odds import consolidate_lines, pivot_over_under


def _row(event="e1", market="player_rush_yds", player="J.K. Dobbins", side="Over",
         point=50.5, price=-115, book="draftkings"):
    return {
        "event_id": event, "home_team": "DEN", "away_team": "KC", "bookmaker": book,
        "market": market, "player_name": player, "side": side, "point": point, "price": price,
    }


def test_pivot_over_under_merges_both_sides_into_one_row():
    rows = [
        _row(side="Over", price=-115),
        _row(side="Under", price=-105),
    ]
    pivoted = pivot_over_under(rows)
    assert len(pivoted) == 1
    row = pivoted[0]
    assert row["point"] == 50.5
    assert row["over_price"] == -115
    assert row["under_price"] == -105


def test_pivot_over_under_keeps_different_books_separate():
    rows = [
        _row(side="Over", price=-115, book="draftkings"),
        _row(side="Under", price=-105, book="draftkings"),
        _row(side="Over", price=-120, book="fanduel"),
        _row(side="Under", price=-100, book="fanduel"),
    ]
    pivoted = pivot_over_under(rows)
    assert len(pivoted) == 2
    by_book = {r["bookmaker"]: r for r in pivoted}
    assert by_book["draftkings"]["over_price"] == -115
    assert by_book["fanduel"]["over_price"] == -120


def test_consolidate_lines_prefers_draftkings_and_keeps_both_prices():
    rows = pivot_over_under([
        _row(side="Over", price=-115, book="draftkings"),
        _row(side="Under", price=-105, book="draftkings"),
        _row(side="Over", price=-130, book="fanduel", point=51.5),
        _row(side="Under", price=110, book="fanduel", point=51.5),
    ])
    consolidated = consolidate_lines(rows)
    assert len(consolidated) == 1
    picked = consolidated[0]
    assert picked["bookmaker"] == "draftkings"
    assert picked["point"] == 50.5
    assert picked["over_price"] == -115
    assert picked["under_price"] == -105


def test_consolidate_lines_falls_back_to_median_point_without_preferred_book():
    rows = pivot_over_under([
        _row(side="Over", price=-115, book="fanduel", point=50.5),
        _row(side="Under", price=-105, book="fanduel", point=50.5),
        _row(side="Over", price=-120, book="betmgm", point=52.5),
        _row(side="Under", price=100, book="betmgm", point=52.5),
    ])
    consolidated = consolidate_lines(rows)
    assert len(consolidated) == 1
    assert consolidated[0]["point"] == 51.5  # median of 50.5, 52.5
    assert consolidated[0]["bookmaker"] == "median_of_2_books"
