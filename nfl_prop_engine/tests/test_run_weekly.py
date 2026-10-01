import pandas as pd

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
