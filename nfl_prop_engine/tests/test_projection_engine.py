import pandas as pd
import pytest

from projection_engine import (
    _season_std,
    _team_changed,
    find_draft_analogs,
    project_rookie,
    project_veteran,
    rookie_analog_baseline,
)


def _rows(weeks, values, team="KC"):
    return pd.DataFrame({"week": weeks, "yards": values, "team": [team] * len(weeks)})


def test_team_changed_true_when_last_current_team_differs_from_prior():
    current = _rows([1, 2], [50, 60], team="SF")
    prior = _rows([1, 2, 3], [40, 45, 50], team="KC")
    assert _team_changed(current, prior, "team") is True


def test_team_changed_false_when_no_prior_data():
    current = _rows([1], [50], team="SF")
    prior = pd.DataFrame(columns=["week", "yards", "team"])
    assert _team_changed(current, prior, "team") is False


def test_season_std_uses_current_when_enough_points():
    assert _season_std([10, 20, 30], [], league_fallback_std=999) == pytest.approx(10.0)


def test_season_std_falls_back_to_prior_then_league():
    assert _season_std([10], [10, 20, 30], league_fallback_std=999) == pytest.approx(10.0)
    assert _season_std([10], [10], league_fallback_std=42) == 42


def test_project_veteran_blends_toward_prior_season_for_thin_current_sample():
    # n=1 current game, k=4 -> prior_weight = 4/5 = 0.8, so the blended
    # season avg should sit much closer to the prior-season average than
    # to this season's single data point.
    current = _rows([1], [10.0])
    prior = _rows(list(range(1, 6)), [40.0] * 5)
    empty_series = pd.Series(dtype=float)

    proj = project_veteran(
        player_id="p1", player_name="Test Player", stat_col="yards",
        current_rows=current, prior_rows=prior,
        opponent_team="LAC",
        opp_current_allowed=empty_series, opp_current_league_avg=float("nan"), n_current_league_games=0,
        opp_prior_allowed=empty_series, opp_prior_league_avg=float("nan"),
        team_col="team", league_fallback=5.0, k=4,
    )
    # opp_factor should be neutral (1.0) since there's no opponent data at all,
    # so projection == baseline == 0.5*blended_season_avg + 0.5*last5_avg
    # blended_season_avg = 0.2*10 + 0.8*40 = 34; last5_avg = 10 (only 1 game)
    # baseline = 0.5*34 + 0.5*10 = 22
    assert proj.projection == pytest.approx(22.0)


def test_project_veteran_method_tagging_by_combined_sample_size():
    empty_series = pd.Series(dtype=float)
    current = _rows([1], [10.0])
    prior = _rows(list(range(1, 6)), [40.0] * 5)
    proj = project_veteran(
        "p1", "Test Player", "yards", current, prior, "LAC",
        empty_series, float("nan"), 0, empty_series, float("nan"),
        "team", 5.0, k=4,
    )
    assert proj.method == "veteran"
    assert proj.confidence == "normal"

    thin_current = _rows([1], [10.0])
    thin_prior = pd.DataFrame(columns=["week", "yards", "team"])
    thin_proj = project_veteran(
        "p2", "Thin Player", "yards", thin_current, thin_prior, "LAC",
        empty_series, float("nan"), 0, empty_series, float("nan"),
        "team", 5.0, k=4,
    )
    assert thin_proj.method == "thin_sample"
    assert thin_proj.confidence == "low"


def test_project_veteran_zero_current_games_uses_prior_season_not_zero():
    # A player with a full, healthy prior season but zero games so far this
    # season (week 1 not yet played, or back from injury) should project
    # close to their real prior-season average -- not get cut roughly in
    # half by a last-5-games fallback with no real data behind it.
    empty_current = pd.DataFrame(columns=["week", "yards", "team"])
    prior = _rows(list(range(1, 18)), [250.0] * 17)
    empty_series = pd.Series(dtype=float)

    proj = project_veteran(
        "p1", "Dak-like Player", "yards", empty_current, prior, "NYG",
        empty_series, float("nan"), 0, empty_series, float("nan"),
        "team", 50.0, k=4,
    )
    assert proj.projection == pytest.approx(250.0)


def test_project_veteran_opponent_factor_moves_projection():
    empty_series = pd.Series(dtype=float)
    current = _rows([1, 2, 3], [20.0, 20.0, 20.0])
    prior = pd.DataFrame(columns=["week", "yards", "team"])

    allowed_tough = pd.Series({"LAC": 10.0})  # allows half the league average -> tough matchup
    proj = project_veteran(
        "p1", "Test Player", "yards", current, prior, "LAC",
        allowed_tough, 20.0, 100, empty_series, float("nan"),
        "team", 5.0, k=4,
    )
    # opp_factor = 10/20 = 0.5 -> projection = baseline * (1 + 0.25*(0.5-1)) = baseline*0.875
    assert proj.projection == pytest.approx(20.0 * 0.875)


def test_find_draft_analogs_respects_window_and_position():
    draft_df = pd.DataFrame({
        "position": ["WR", "WR", "RB", "WR"],
        "pick": [10, 50, 12, 200],
        "gsis_id": ["a", "b", "c", "d"],
        "season": [2020, 2020, 2020, 2020],
    })
    analogs = find_draft_analogs(draft_df, position="WR", pick=15, window=20)
    assert set(analogs["gsis_id"]) == {"a"}


def test_rookie_analog_baseline_uses_median_of_games_1_to_3():
    draft_df = pd.DataFrame({
        "position": ["WR", "WR"],
        "pick": [10, 12],
        "gsis_id": ["a", "b"],
        "season": [2023, 2023],
    })
    weekly_df = pd.DataFrame({
        "player_id": ["a", "a", "a", "b", "b"],
        "season": [2023, 2023, 2023, 2023, 2023],
        "week": [1, 2, 3, 1, 2],
        "yards": [10, 20, 30, 100, 100],
    })
    baseline, n = rookie_analog_baseline(draft_df, weekly_df, "yards", "WR", pick=11, window=5)
    # player a's games 1-3 avg = 20, player b's games 1-2 avg = 100 -> median of [20, 100] = 60
    assert baseline == pytest.approx(60.0)
    assert n == 2


def test_project_rookie_returns_none_without_any_analog_data():
    draft_df = pd.DataFrame({"position": [], "pick": [], "gsis_id": [], "season": []})
    weekly_df = pd.DataFrame({"player_id": [], "season": [], "week": [], "yards": []})
    result = project_rookie("z", "Zero Data", "yards", "WR", 5, draft_df, weekly_df)
    assert result is None
