from config import ODDS_API_TEAM_NAME_TO_ABBR


def test_odds_api_team_map_covers_all_32_teams_uniquely():
    assert len(ODDS_API_TEAM_NAME_TO_ABBR) == 32
    assert len(set(ODDS_API_TEAM_NAME_TO_ABBR.values())) == 32


def test_odds_api_team_map_matches_real_confirmed_events():
    # Spot-checked against real event names returned live by the Odds API.
    assert ODDS_API_TEAM_NAME_TO_ABBR["Detroit Lions"] == "DET"
    assert ODDS_API_TEAM_NAME_TO_ABBR["New Orleans Saints"] == "NO"
    assert ODDS_API_TEAM_NAME_TO_ABBR["Washington Commanders"] == "WAS"
    assert ODDS_API_TEAM_NAME_TO_ABBR["New York Giants"] == "NYG"
    assert ODDS_API_TEAM_NAME_TO_ABBR["Dallas Cowboys"] == "DAL"
    assert ODDS_API_TEAM_NAME_TO_ABBR["Kansas City Chiefs"] == "KC"
    assert ODDS_API_TEAM_NAME_TO_ABBR["Denver Broncos"] == "DEN"
