"""Leg quality gates (Week 4 upgrade spec, Requirements 3-4). Each gate
returns a GateResult -- pass/fail plus a one-line reason -- so the report
can show exactly why a leg was excluded, per the spec's own requirement
that "a failed gate excludes the leg, and the report states which gate
failed and why."

This module covers the US-consensus-vs-bet365 gates (Requirement 3): Line,
Price, and the Movement flag. The Form/Outlier/Role/Matchup/Game-script/
Injury gates (Requirement 4) reuse the existing engine's own modules
(projection_engine.py, opponent_stats.py, game_context.py,
fetch_injuries.py) and are wired in run_weekly.py's accumulator path
rather than duplicated here.
"""
from dataclasses import dataclass

from config import LINE_MOVEMENT_FLAG, LINE_THRESHOLD, MIN_PRICE_DECIMAL, market_kind_for


@dataclass
class GateResult:
    gate: str
    passed: bool
    reason: str


def line_gate(bet365_line: float, consensus_line: float | None, stat_col: str) -> GateResult:
    """Passes only if bet365's line is no worse than the US consensus by
    more than the threshold for this stat's kind (yards vs. counts)."""
    if consensus_line is None:
        return GateResult("line", False, "thin market: fewer than 2 US books quoted this line")
    threshold = LINE_THRESHOLD[market_kind_for(stat_col)]
    diff = bet365_line - consensus_line
    if diff <= threshold:
        return GateResult("line", True, f"bet365 {bet365_line} vs. consensus {consensus_line} (within {threshold})")
    return GateResult(
        "line", False,
        f"bet365 {bet365_line} is {diff:.1f} above consensus {consensus_line} (limit +{threshold})",
    )


def price_gate(bet365_over_price_decimal: float) -> GateResult:
    """The bet365 over price must clear MIN_PRICE_DECIMAL regardless of
    how good the line looks -- a great line at a terrible price is still a
    bad bet."""
    if bet365_over_price_decimal >= MIN_PRICE_DECIMAL:
        return GateResult("price", True, f"{bet365_over_price_decimal:.2f} clears the {MIN_PRICE_DECIMAL} minimum")
    return GateResult(
        "price", False,
        f"{bet365_over_price_decimal:.2f} is below the {MIN_PRICE_DECIMAL} minimum",
    )


def movement_flag(opener_line: float | None, consensus_line: float | None, stat_col: str) -> GateResult:
    """A FLAG, not a pass/fail gate -- the spec lists this separately from
    Line/Price ("flag any prop whose consensus line has moved..."). Always
    reports passed=True (never excludes a leg on its own); the reason
    string says whether it moved and which direction, for the report to
    surface."""
    if opener_line is None or consensus_line is None:
        return GateResult("movement", True, "no opener snapshot recorded yet to compare against")
    threshold = LINE_MOVEMENT_FLAG[market_kind_for(stat_col)]
    delta = consensus_line - opener_line
    if abs(delta) < threshold:
        return GateResult("movement", True, f"line steady ({opener_line} -> {consensus_line})")
    direction = "up" if delta > 0 else "down"
    return GateResult(
        "movement", True,
        f"FLAGGED: line moved {direction} {abs(delta):.1f} since the opener ({opener_line} -> {consensus_line})",
    )
