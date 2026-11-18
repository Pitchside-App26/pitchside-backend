import json
from datetime import date

import pandas as pd
import pytest

from tracker_bets import Schedule, merge, publish, teams_in, tracker_bets

GAMES = pd.DataFrame([
    {"away_team": "SF", "home_team": "DAL", "gameday": "2026-11-15"},
    {"away_team": "KC", "home_team": "ATL", "gameday": "2026-11-15"},
    {"away_team": "LA", "home_team": "ARI", "gameday": "2026-11-15"},
    {"away_team": "NYG", "home_team": "WAS", "gameday": "2026-11-16"},
])
SCHEDULE = Schedule(GAMES)
ROSTER = {"Brock Purdy": "SF", "Kyren Williams": "LA", "Javonte Williams": "DAL"}


def _leg(player="", market="other", side="other", line=None, game=None, team=None, text=""):
    return {"player": player, "player_raw": player, "team": team, "game": game, "market": market,
            "market_text": text, "side": side, "book_line": line, "odds_text": None, "book_price": None,
            "bet_builder_group": None}


def _draft(*legs, bookmaker="Ladbrokes", bet_type="bet_builder"):
    return {"version": 1, "week": 10, "warnings": [], "slips": [{
        "bet_type": bet_type, "bookmaker": bookmaker, "stake_gbp": 7.5, "total_odds_text": "20/1",
        "total_odds_decimal": 21.0, "potential_returns_gbp": 157.5, "legs": list(legs)}]}


def test_team_names_and_nicknames_are_read_in_order():
    assert teams_in("San Francisco 49ers @ Dallas Cowboys") == ["SF", "DAL"]
    assert teams_in("Jets v Giants") == ["NYJ", "NYG"]
    assert teams_in("Kansas City Chiefs") == ["KC"]


def test_a_slip_becomes_a_tracker_bet_with_espn_games():
    draft = _draft(
        _leg("Brock Purdy", "player_pass_yds", "over", 260.5, game="San Francisco 49ers @ Dallas Cowboys"),
        _leg("Javonte Williams", "player_rush_yds", "over", 61.5),                  # game from the roster
        _leg("Christian McCaffrey", "player_anytime_td", "yes", game="49ers @ Cowboys"),
        _leg(market="moneyline", team="Kansas City Chiefs", text="Moneyline"),
        _leg(market="game_total", side="over", line=41, game="Los Angeles Rams @ Arizona Cardinals"),
        _leg(market="game_total", side="under", line=40.5, game="Giants @ Commanders"),
    )
    [bet] = tracker_bets(12, draft, SCHEDULE, ROSTER)
    assert (bet["id"], bet["book"], bet["kind"], bet["odds"]) == ("issue-12-slip-1", "Ladbrokes", "Bet Builder", "20/1")
    assert bet["dates"] == ["20261115", "20261116"]
    assert bet["legs"] == [
        {"type": "player", "game": "SF@DAL", "player": "Brock Purdy", "stat": "passingYards", "side": "over", "line": 260.5},
        {"type": "player", "game": "SF@DAL", "player": "Javonte Williams", "stat": "rushingYards", "side": "over", "line": 61.5},
        {"type": "anytime_td", "game": "SF@DAL", "player": "Christian McCaffrey"},
        {"type": "moneyline", "game": "KC@ATL", "team": "KC"},
        {"type": "total", "game": "LAR@ARI", "side": "over", "line": 41},  # nflverse LA -> ESPN LAR
        {"type": "total", "game": "NYG@WSH", "side": "under", "line": 40.5},
    ]


def test_legs_the_tracker_cant_follow_are_kept_as_not_tracked():
    [bet] = tracker_bets(1, _draft(
        _leg("Brock Purdy", "other", text="First TD scorer"),
        _leg("Nobody Known", "player_receptions", "over", 4.5),
    ), SCHEDULE, ROSTER)
    assert bet["legs"][0] == {"type": "other", "game": "SF@DAL", "label": "Brock Purdy First TD scorer",
                              "note": "can't be followed live"}
    assert bet["legs"][1]["type"] == "other" and bet["legs"][1]["note"] == "game not found"


def test_nothing_identifying_the_slip_is_written(tmp_path):
    path = tmp_path / "bets.json"
    publish(3, _draft(_leg("Brock Purdy", "player_pass_yds", "over", 260.5)), SCHEDULE, ROSTER, str(path),
            today=date(2026, 11, 15))
    bet = json.loads(path.read_text())["bets"][0]
    assert set(bet) == {"id", "book", "kind", "odds", "dates", "legs"}


def test_a_reconfirmed_slip_replaces_its_bets_and_old_bets_drop_off():
    existing = {"note": "x", "bets": [
        {"id": "issue-3-slip-1", "dates": ["20261115"], "legs": []},
        {"id": "issue-2-slip-1", "dates": ["20261115"], "legs": []},
        {"id": "old", "date": "20261020", "legs": []},
        {"id": "undated", "legs": []},
    ]}
    merged = merge(existing, 3, [{"id": "issue-3-slip-1", "dates": ["20261115"], "legs": ["new"]}], date(2026, 11, 15))
    assert [b["id"] for b in merged["bets"]] == ["issue-3-slip-1", "issue-2-slip-1", "undated"]
    assert merged["bets"][0]["legs"] == ["new"] and merged["note"] == "x"


def test_publish_reports_how_many_legs_are_followed(tmp_path):
    path = tmp_path / "bets.json"
    n = publish(4, _draft(_leg("Brock Purdy", "player_pass_yds", "over", 260.5), _leg("X", "other")),
                SCHEDULE, ROSTER, str(path), today=date(2026, 11, 15))
    assert n == 1


def test_football_competitions_map_to_the_tracker_leagues():
    from tracker_bets import football_league
    assert football_league("Sky Bet League One") == "eng.3"
    assert football_league("Scottish League Two") == "ls:sco4"
    assert football_league("Vanarama National League") == "eng.5"
    assert football_league("National League South") == "ls:south"
    assert football_league("Scottish Premiership") == "sco.1"
    assert football_league("Serie A") is None and football_league(None) is None


def test_football_legs_become_live_legs_or_are_kept_as_not_tracked():
    from tracker_bets import football_leg
    base = {"game": "Stockport County v Bolton Wanderers", "competition": None, "date": "2026-11-21",
            "side": "other", "book_line": None, "market_text": "x"}
    assert football_leg({**base, "market": "match_result", "team": "Bolton"})[0]["pick"] == "away"
    assert football_leg({**base, "market": "match_result", "team": "Draw"})[0]["pick"] == "draw"
    assert football_leg({**base, "market": "goal_both_halves", "side": "yes"})[0]["type"] == "gibh"
    assert "league" not in football_leg({**base, "market": "btts", "side": "no"})[0]
    assert football_leg({**base, "market": "other"})[0]["type"] == "other"
    assert football_leg({**base, "game": "Stockport", "market": "btts", "side": "yes"})[0]["type"] == "other"
