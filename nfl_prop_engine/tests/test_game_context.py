import pytest

from game_context import (
    apply_game_context,
    environment_factor,
    script_tilt,
    team_implied_total,
    team_spread,
)


def test_team_spread_home_uses_line_directly():
    assert team_spread(2.5, is_home=True) == 2.5


def test_team_spread_away_is_negated():
    assert team_spread(2.5, is_home=False) == -2.5


def test_team_spread_none_without_data():
    assert team_spread(None, is_home=True) is None


def test_team_implied_total_matches_real_kc_den_week1_line():
    # Real 2026 week 1 line: KC (home) -2.5... i.e. spread_line=+2.5,
    # total_line=42.5 -- confirmed sign convention against actual results
    # (see game_context.py's module docstring).
    assert team_implied_total(42.5, 2.5, is_home=True) == pytest.approx(22.5)
    assert team_implied_total(42.5, 2.5, is_home=False) == pytest.approx(20.0)


def test_team_implied_total_none_with_missing_line():
    assert team_implied_total(None, 2.5, is_home=True) is None
    assert team_implied_total(42.5, None, is_home=True) is None


def test_environment_factor_above_and_below_average():
    assert environment_factor(25.0, 20.0) == pytest.approx(1.25)
    assert environment_factor(15.0, 20.0) == pytest.approx(0.75)


def test_environment_factor_none_with_missing_input():
    assert environment_factor(None, 20.0) is None
    assert environment_factor(25.0, None) is None
    assert environment_factor(25.0, 0) is None


def test_script_tilt_clips_beyond_scale():
    assert script_tilt(20.0, scale=10.0) == 1.0
    assert script_tilt(-20.0, scale=10.0) == -1.0
    assert script_tilt(5.0, scale=10.0) == pytest.approx(0.5)


def test_script_tilt_neutral_without_spread():
    assert script_tilt(None) == 0.0


def test_apply_game_context_boosts_rush_for_favorite_tilt():
    # Favored team (positive tilt) -> rushing volume up.
    value = apply_game_context(100.0, "rushing_yards", env_factor=None, tilt=0.5, env_weight=0.2, script_weight=0.2)
    assert value == pytest.approx(100.0 * 1.10)


def test_apply_game_context_suppresses_pass_for_favorite_tilt():
    # Same favorite tilt -> passing/receiving volume down, not up.
    value = apply_game_context(100.0, "passing_yards", env_factor=None, tilt=0.5, env_weight=0.2, script_weight=0.2)
    assert value == pytest.approx(100.0 * 0.90)


def test_apply_game_context_applies_environment_to_both_directions():
    value = apply_game_context(100.0, "rushing_yards", env_factor=1.5, tilt=0.0, env_weight=0.2, script_weight=0.2)
    assert value == pytest.approx(100.0 * 1.10)  # 1 + 0.2*(1.5-1)


def test_apply_game_context_leaves_defensive_stats_unchanged():
    # def_sacks/def_tackles aren't in either volume set yet (see config.py) --
    # this game's script/environment shouldn't move them at all.
    value = apply_game_context(2.0, "def_sacks", env_factor=1.5, tilt=0.9, env_weight=0.2, script_weight=0.2)
    assert value == 2.0
