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


def test_a_shared_name_resolves_to_the_player_in_this_game():
    from run_weekly import rows_for_matched_player

    df = pd.DataFrame([
        {"player_id": "LA1", "player_display_name": "Byron Young", "team": "LA", "season": 2026, "week": 1, "def_sacks": 1.0},
        {"player_id": "LA1", "player_display_name": "Byron Young", "team": "LA", "season": 2026, "week": 2, "def_sacks": 2.0},
        {"player_id": "PHI1", "player_display_name": "Byron Young", "team": "PHI", "season": 2026, "week": 2, "def_sacks": 0.0},
        {"player_id": "X", "player_display_name": "Someone Else", "team": "LA", "season": 2026, "week": 2, "def_sacks": 0.0},
    ])
    rows = rows_for_matched_player(df, "Byron Young", {"LA", "SF"}, "team")
    assert set(rows["player_id"]) == {"LA1"} and len(rows) == 2
    assert set(rows_for_matched_player(df, "Byron Young", {"PHI", "DAL"}, "team")["player_id"]) == {"PHI1"}
    assert len(rows_for_matched_player(df, "Someone Else", {"NE"}, "team")) == 1


def test_window_games_and_their_players_feed_the_analyst_search(monkeypatch):
    from run_weekly import players_on_teams, run_analyst_search, window_team_games

    games = pd.DataFrame([
        {"home_team": "PHI", "away_team": "LA", "weekday": "Sunday", "gametime": "13:00"},
        {"home_team": "CAR", "away_team": "DET", "weekday": "Sunday", "gametime": "20:20"},
    ])
    team_games = window_team_games(games, {"PHI": "early", "LA": "early", "CAR": None, "DET": None})
    assert set(team_games) == {"PHI", "LA"}
    assert team_games["LA"].description == "Los Angeles Rams at Philadelphia Eagles"
    offense = pd.DataFrame([
        {"player_id": "1", "player_display_name": "Kyren Williams", "recent_team": "LA", "season": 2026, "week": 3},
        {"player_id": "2", "player_display_name": "Moved Away", "recent_team": "LA", "season": 2025, "week": 9},
        {"player_id": "2", "player_display_name": "Moved Away", "recent_team": "DET", "season": 2026, "week": 3},
    ])
    assert [p.name for p in players_on_teams({"LA", "PHI"}, offense)] == ["Kyren Williams"]

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    picks, info, by_game = run_analyst_search(games, {"PHI": "early", "LA": "early"}, 4, 2026, offense)
    assert (picks, by_game, info["ran"]) == ([], None, False)
    assert "ANTHROPIC_API_KEY" in info["note"]


def test_a_failing_analyst_search_never_stops_the_run(monkeypatch):
    import run_weekly

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(run_weekly, "fetch_slate_picks", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    games = pd.DataFrame([{"home_team": "PHI", "away_team": "LA", "weekday": "Sunday", "gametime": "13:00"}])
    picks, info, by_game = run_weekly.run_analyst_search(games, {"PHI": "early", "LA": "early"}, 4, 2026)
    assert (picks, by_game, info["ran"]) == ([], None, False)
    assert "failed (RuntimeError)" in info["note"]
