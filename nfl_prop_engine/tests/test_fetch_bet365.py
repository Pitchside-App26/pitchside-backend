import pytest

from fetch_bet365 import FractionalOddsError, import_bet365_csv, parse_fractional_odds


def test_fractional_odds_matches_spec_examples():
    # Exact conversions named in the Week 4 upgrade spec's acceptance criteria.
    assert round(parse_fractional_odds("20/23"), 2) == 1.87
    assert round(parse_fractional_odds("5/4"), 2) == 2.25
    assert round(parse_fractional_odds("10/11"), 2) == 1.91
    assert parse_fractional_odds("evens") == 2.0


def test_fractional_odds_case_and_whitespace_insensitive():
    assert parse_fractional_odds("Evens") == 2.0
    assert parse_fractional_odds(" EVS ") == 2.0
    assert round(parse_fractional_odds(" 20 / 23 "), 2) == 1.87


def test_fractional_odds_accepts_already_decimal_values():
    assert parse_fractional_odds(1.91) == 1.91
    assert parse_fractional_odds("1.91") == 1.91


def test_fractional_odds_rejects_garbage():
    with pytest.raises(FractionalOddsError):
        parse_fractional_odds("not odds")


def test_fractional_odds_rejects_zero_denominator():
    with pytest.raises(FractionalOddsError):
        parse_fractional_odds("5/0")


def test_import_bet365_csv_parses_rows(tmp_path):
    csv_path = tmp_path / "bet365_week4.csv"
    csv_path.write_text(
        "player,market,line,over_price\n"
        "Drake Maye,player_pass_yds,214.5,10/11\n"
        "Garrett Wilson,player_reception_yds,65.5,evens\n"
    )
    rows = import_bet365_csv(str(csv_path))
    assert len(rows) == 2
    assert rows[0]["player_name"] == "Drake Maye"
    assert rows[0]["market"] == "player_pass_yds"
    assert rows[0]["point"] == 214.5
    assert round(rows[0]["price"], 2) == 1.91
    assert rows[0]["bookmaker"] == "bet365"
    assert rows[1]["price"] == 2.0


def test_import_bet365_csv_raises_on_missing_column(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("player,market,line\nDrake Maye,player_pass_yds,214.5\n")
    with pytest.raises(ValueError, match="missing required column"):
        import_bet365_csv(str(csv_path))
