import pytest

from leg_gates import (
    form_gate,
    game_script_gate,
    injury_gate,
    line_gate,
    matchup_gate,
    movement_flag,
    outlier_gate,
    price_gate,
    role_change_flag,
    sources_gate,
    teammate_injury_flag,
)


# --- Real Week 3 failures named in the upgrade spec -- the reason this
# module exists at all. Both accumulators that week lost partly because
# these three legs were taken on lines bet365 had already drifted away
# from the US market on.

def test_maye_week3_fails_line_gate():
    result = line_gate(bet365_line=222.5, consensus_line=214.5, stat_col="passing_yards")
    assert result.passed is False
    assert result.gate == "line"


def test_garrett_wilson_week3_fails_line_gate():
    result = line_gate(bet365_line=76.5, consensus_line=65.5, stat_col="receiving_yards")
    assert result.passed is False


def test_pollard_week3_fails_line_gate():
    result = line_gate(bet365_line=61.5, consensus_line=48.5, stat_col="rushing_yards")
    assert result.passed is False


# --- General gate behavior ---------------------------------------------

def test_line_gate_passes_within_yardage_threshold():
    # 2.0 yard tolerance -- exactly at the limit passes
    result = line_gate(bet365_line=216.5, consensus_line=214.5, stat_col="passing_yards")
    assert result.passed is True


def test_line_gate_fails_thin_market_with_no_consensus():
    result = line_gate(bet365_line=222.5, consensus_line=None, stat_col="passing_yards")
    assert result.passed is False
    assert "thin market" in result.reason


def test_line_gate_count_stats_use_zero_tolerance():
    # Receptions/attempts get 0.0 tolerance, not the 2.0 yardage allowance
    assert line_gate(bet365_line=5.5, consensus_line=5.5, stat_col="receptions").passed is True
    assert line_gate(bet365_line=6.5, consensus_line=5.5, stat_col="receptions").passed is False


def test_price_gate_default_minimum_is_1_80():
    assert price_gate(1.80).passed is True
    assert price_gate(1.79).passed is False


def test_movement_flag_never_fails_a_leg_on_its_own():
    # Even a big move still reports passed=True -- it's a flag, not a gate
    result = movement_flag(opener_line=200.0, consensus_line=214.5, stat_col="passing_yards")
    assert result.passed is True
    assert "FLAGGED" in result.reason


def test_movement_flag_reports_steady_line_below_threshold():
    result = movement_flag(opener_line=213.0, consensus_line=214.5, stat_col="passing_yards")
    assert result.passed is True
    assert "steady" in result.reason


def test_movement_flag_handles_missing_opener():
    result = movement_flag(opener_line=None, consensus_line=214.5, stat_col="passing_yards")
    assert result.passed is True
    assert "no opener" in result.reason


# --- Requirement 4 gates -------------------------------------------------

def test_form_gate_passes_on_strong_recent_form():
    result = form_gate([60, 70, 55, 80, 65, 75], line=50.0)
    assert result.passed is True


def test_form_gate_fails_below_50_percent_hit_rate():
    result = form_gate([40, 45, 60, 42, 38, 44], line=50.0)  # only 1 of 6 clears the line
    assert result.passed is False


def test_form_gate_fails_on_no_history():
    assert form_gate([], line=50.0).passed is False


def test_form_gate_excludes_pushes_from_hit_rate():
    # Two exact ties at the line, one real hit, one real miss -- hit rate
    # among the two decisive games is 50%, which still passes.
    result = form_gate([50.0, 50.0, 60.0, 40.0], line=50.0)
    assert result.passed is True


def test_outlier_gate_is_the_gibbs_check():
    # 156 and 52 average to 104 -- looks like a real trend against a 90
    # line, but drop the 156 and the remaining 52 is nowhere near 90% of
    # the line.
    result = outlier_gate([156.0, 52.0], line=90.0)
    assert result.passed is False


def test_outlier_gate_passes_on_genuine_consistency():
    result = outlier_gate([95.0, 100.0, 105.0, 98.0], line=90.0)
    assert result.passed is True


def test_outlier_gate_fails_with_fewer_than_two_games():
    assert outlier_gate([100.0], line=90.0).passed is False
    assert outlier_gate([], line=90.0).passed is False


def test_role_change_flag_neutral_below_threshold():
    result = role_change_flag(current_share_pct=62.0, prior_share_pct=58.0)
    assert result.passed is True
    assert "steady" in result.reason


def test_role_change_flag_flags_big_swing_but_still_passes():
    result = role_change_flag(current_share_pct=75.0, prior_share_pct=55.0)
    assert result.passed is True  # a flag, never an auto-exclude
    assert "FLAGGED" in result.reason


def test_role_change_flag_neutral_without_data():
    result = role_change_flag(None, None)
    assert result.passed is True
    assert "no snap/route share data" in result.reason


def test_matchup_gate_passes_at_or_worse_than_average():
    assert matchup_gate(opp_factor=1.0).passed is True
    assert matchup_gate(opp_factor=1.3).passed is True


def test_matchup_gate_fails_below_average():
    assert matchup_gate(opp_factor=0.7).passed is False
    assert matchup_gate(opp_factor=0.99).passed is False


def test_matchup_gate_treats_a_rounding_hair_below_average_as_average():
    # Real Week 4 value for NE's run defence: shown as 1.00x, so it must not fail as "better than average".
    result = matchup_gate(opp_factor=0.9997868114852506)
    assert result.passed is True
    assert "1.00x" in result.reason


def test_game_script_gate_rushing_favorite_passes():
    result = game_script_gate("rushing_yards", team_spread_value=6.0, total_line=42.0)
    assert result.passed is True


def test_game_script_gate_rushing_big_dog_fails():
    result = game_script_gate("rushing_yards", team_spread_value=-10.0, total_line=48.0)
    assert result.passed is False


def test_game_script_gate_passing_underdog_passes_regardless_of_total():
    result = game_script_gate("passing_yards", team_spread_value=-7.0, total_line=38.0)
    assert result.passed is True


def test_game_script_gate_passing_favorite_needs_high_total():
    fails = game_script_gate("passing_yards", team_spread_value=3.0, total_line=40.0)
    assert fails.passed is False
    passes = game_script_gate("passing_yards", team_spread_value=3.0, total_line=46.0)
    assert passes.passed is True


def test_game_script_gate_neutral_for_unclassified_stats():
    result = game_script_gate("def_sacks", team_spread_value=3.0, total_line=40.0)
    assert result.passed is True


def test_injury_gate_passes_only_with_no_report_status():
    assert injury_gate(None).passed is True
    assert injury_gate("Questionable").passed is False
    assert injury_gate("Doubtful").passed is False
    assert injury_gate("Out").passed is False


def test_teammate_injury_flag_never_excludes():
    clean = teammate_injury_flag([])
    assert clean.passed is True
    flagged = teammate_injury_flag(["Some Other Player"])
    assert flagged.passed is True
    assert "FLAGGED" in flagged.reason


def test_sources_gate_default_minimum_is_two():
    assert sources_gate(2).passed is True
    assert sources_gate(1).passed is False
    assert sources_gate(0).passed is False


# --- unders: each gate's mirror image -----------------------------------------

def test_form_gate_for_an_under_needs_most_games_below_the_line():
    assert form_gate([40, 45, 70, 38, 50, 42], 52.5, side="under").passed
    assert not form_gate([60, 65, 70, 38, 50, 58], 52.5, side="under").passed


def test_outlier_gate_for_an_under_drops_the_worst_game():
    # 4, 40, 42, 44: the 4 is a one-off dud; the rest average 42, under 52.5 / 0.9.
    assert outlier_gate([4, 40, 42, 44], 52.5, side="under").passed
    # Without the dud the rest average 62 -- the under leaned on one quiet game.
    assert not outlier_gate([4, 60, 62, 64], 52.5, side="under").passed


def test_matchup_gate_for_an_under_wants_a_tough_defence():
    assert matchup_gate(0.85, side="under").passed
    assert matchup_gate(1.0, side="under").passed
    assert not matchup_gate(1.12, side="under").passed


def test_game_script_for_an_under_is_the_overs_opposite():
    # A rushing over needs the team favored or a small dog; a 7-point dog suits the rushing under.
    assert game_script_gate("rushing_yards", -7.0, 44.0, side="under").passed
    assert not game_script_gate("rushing_yards", 3.0, 44.0, side="under").passed
    # Favored with a low total works against passing volume, so suits a passing under.
    assert game_script_gate("passing_yards", 4.0, 40.5, side="under").passed
    assert not game_script_gate("passing_yards", -3.0, 40.5, side="under").passed
    # Undefined for defensive stats either way.
    assert game_script_gate("def_tackles", 3.0, 40.5, side="under").passed
    assert not game_script_gate("rushing_yards", None, 44.0, side="under").passed
