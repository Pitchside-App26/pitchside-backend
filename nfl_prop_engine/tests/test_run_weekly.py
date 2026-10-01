import pandas as pd
import pytest

from fetch_schedule import game_window, window_uk_kickoffs
from run_weekly import players_out_by_team


def test_players_out_by_team_uses_each_players_latest_team():
    offense = pd.DataFrame([
        {"player_id": "1", "player_display_name": "Stefon Diggs", "recent_team": "HOU", "season": 2025, "week": 10},
        {"player_id": "1", "player_display_name": "Stefon Diggs", "recent_team": "NE", "season": 2026, "week": 2},
        {"player_id": "2", "player_display_name": "Healthy Guy", "recent_team": "NE", "season": 2026, "week": 2},
        {"player_id": "3", "player_display_name": "Questionable Guy", "recent_team": "BUF", "season": 2026, "week": 2},
    ])
    defense = pd.DataFrame([
        {"player_id": "9", "player_display_name": "Matt Milano", "team": "BUF", "season": 2026, "week": 3},
    ])
    report = {"1": "Out", "3": "Questionable", "9": "Out"}
    assert players_out_by_team(report, offense, defense) == {"NE": ["Stefon Diggs"], "BUF": ["Matt Milano"]}


def test_players_out_by_team_with_no_injuries():
    offense = pd.DataFrame(columns=["player_id", "player_display_name", "recent_team", "season", "week"])
    assert players_out_by_team({}, offense) == {}



@pytest.mark.parametrize("weekday, gametime, window", [
    ("Sunday", "13:00", "early"), ("Sunday", "16:05", "late"), ("Sunday", "16:25", "late"),
    ("Sunday", "09:30", None), ("Sunday", "20:20", None), ("Thursday", "13:00", None), ("Monday", "20:15", None),
    ("Sunday", None, None),
])
def test_game_window(weekday, gametime, window):
    assert game_window(weekday, gametime) == window


def test_uk_kickoff_times_follow_both_clock_changes():
    games = pd.DataFrame([
        {"weekday": "Sunday", "gameday": "2026-10-04", "gametime": "13:00", "home_team": "BUF", "away_team": "NE"},
        {"weekday": "Sunday", "gameday": "2026-10-04", "gametime": "16:05", "home_team": "MIN", "away_team": "MIA"},
        {"weekday": "Sunday", "gameday": "2026-10-04", "gametime": "16:25", "home_team": "LV", "away_team": "KC"},
    ])
    assert window_uk_kickoffs(games) == {"early": "18:00", "late": "21:05/21:25"}
    # 25 Oct 2026: UK has gone back to GMT, the US hasn't yet -- a 4-hour gap for one week.
    games["gameday"] = "2026-10-25"
    assert window_uk_kickoffs(games)["early"] == "17:00"
    games["gameday"] = "2026-11-08"
    assert window_uk_kickoffs(games)["early"] == "18:00"
