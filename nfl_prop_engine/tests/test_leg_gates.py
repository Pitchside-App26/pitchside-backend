import pytest

from leg_gates import line_gate, movement_flag, price_gate


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
