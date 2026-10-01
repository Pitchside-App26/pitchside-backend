"""Leg quality gates (Week 4 upgrade spec, Requirements 3-4). Each gate
returns a GateResult -- pass/fail plus a one-line reason -- so the report
can show exactly why a leg was excluded, per the spec's own requirement
that "a failed gate excludes the leg, and the report states which gate
failed and why."

Requirement 3 (Line/Price/Movement) plus Requirement 4's six gates all
live here. Matchup and Game-script reuse the existing engine's own
opponent_stats.py / game_context.py math directly rather than
recomputing it -- same opponent-allowed and spread/total signal the
projection itself already uses, just gated instead of blended.
"""
import statistics
from dataclasses import dataclass

from config import (
    GAME_SCRIPT_PASSING_MIN_TOTAL,
    GAME_SCRIPT_RUSHING_MAX_DOG,
    LINE_MOVEMENT_FLAG,
    LINE_THRESHOLD,
    MIN_PRICE_DECIMAL,
    MIN_SOURCES,
    OUTLIER_MIN_PCT_OF_LINE,
    PASS_VOLUME_STATS,
    ROLE_CHANGE_FLAG_POINTS,
    RUSH_VOLUME_STATS,
    market_kind_for,
)


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


# --- Requirement 4: leg quality gates ---------------------------------------

def form_gate(recent_values: list[float], line: float) -> GateResult:
    """Last FORM_WINDOW games (reaching into the prior season if needed --
    the caller assembles that combined, most-recent-first list before
    calling). Passes only if BOTH the hit rate and the median clear the
    line -- either one failing means recent form doesn't support the over.
    Exact ties don't count as a hit, same convention as compute_hit_rate()
    in rank_props.py (a push isn't a win)."""
    if not recent_values:
        return GateResult("form", False, "no game history available")
    decisive = [v for v in recent_values if v != line]
    hit_rate = sum(1 for v in decisive if v > line) / len(decisive) if decisive else 0.0
    median = statistics.median(recent_values)
    if hit_rate >= 0.5 and median >= line:
        return GateResult("form", True, f"hit rate {hit_rate:.0%}, median {median:g} vs. line {line:g} over {len(recent_values)} games")
    return GateResult("form", False, f"hit rate {hit_rate:.0%}, median {median:g} vs. line {line:g} over {len(recent_values)} games")


def outlier_gate(recent_values: list[float], line: float) -> GateResult:
    """The Jahmyr Gibbs check: 104 yards/game from one 156-yard game and one
    52-yard game is not a trend. Drops the single best game from the
    window and requires the REMAINING average to still clear
    OUTLIER_MIN_PCT_OF_LINE of the line -- needs at least 2 games (one to
    drop, one to judge on)."""
    if len(recent_values) < 2:
        return GateResult("outlier", False, "fewer than 2 games -- can't drop an outlier and still judge the rest")
    remaining = sorted(recent_values)[:-1]  # drop the single highest value
    remaining_avg = statistics.mean(remaining)
    threshold = OUTLIER_MIN_PCT_OF_LINE * line
    if remaining_avg >= threshold:
        return GateResult("outlier", True, f"excl. best game, remaining avg {remaining_avg:.1f} clears {threshold:.1f} ({OUTLIER_MIN_PCT_OF_LINE:.0%} of line)")
    return GateResult("outlier", False, f"excl. best game, remaining avg {remaining_avg:.1f} is below {threshold:.1f} ({OUTLIER_MIN_PCT_OF_LINE:.0%} of line)")


def role_change_flag(current_share_pct: float | None, prior_share_pct: float | None) -> GateResult:
    """FLAG, not a pass/fail gate -- a real snap/route share swing needs a
    human look, not an auto-exclude. Real snap-count data isn't wired in
    yet (see README: nflverse's snap counts key on pfr_player_id, needing
    an ID crosswalk that was deliberately deferred) -- this function is
    the comparison logic, ready for real data once that crosswalk exists.
    None inputs mean "no share data available yet", not a role change."""
    if current_share_pct is None or prior_share_pct is None:
        return GateResult("role", True, "no snap/route share data available yet")
    delta = current_share_pct - prior_share_pct
    if abs(delta) < ROLE_CHANGE_FLAG_POINTS:
        return GateResult("role", True, f"share steady ({prior_share_pct:.0f}% -> {current_share_pct:.0f}%)")
    direction = "up" if delta > 0 else "down"
    return GateResult("role", True, f"FLAGGED: role share moved {direction} {abs(delta):.0f}pts ({prior_share_pct:.0f}% -> {current_share_pct:.0f}%) -- manual review")


def matchup_gate(opp_factor: float) -> GateResult:
    """Reuses opponent_stats.blended_opponent_factor()'s own output --
    >1.0 means the opponent allows more than league average at this stat,
    which is what an over needs. Same number the projection engine's own
    opponent adjustment is already built from, just gated instead of
    blended in. Decided on the same 2-decimal figure the reason shows: a
    real Week 4 run had a defence at 0.9998x failing as "better than
    average" while displaying 1.00x."""
    shown = round(opp_factor, 2)
    if shown >= 1.0:
        return GateResult("matchup", True, f"opponent allows {shown:.2f}x league average -- at or worse than average")
    return GateResult("matchup", False, f"opponent allows {shown:.2f}x league average -- better than average, working against the over")


def game_script_gate(stat_col: str, team_spread_value: float | None, total_line: float | None) -> GateResult:
    """Rushing overs need the team favored or a dog by no more than
    GAME_SCRIPT_RUSHING_MAX_DOG; passing/receiving overs need the team to
    be an underdog OR a high enough total. Stats outside both volume sets
    (defensive props) aren't covered by this gate -- passes through
    neutrally rather than guessing at a rule the spec doesn't define for
    them."""
    if team_spread_value is None:
        return GateResult("game_script", False, "no spread data available")
    if stat_col in RUSH_VOLUME_STATS:
        if team_spread_value >= -GAME_SCRIPT_RUSHING_MAX_DOG:
            return GateResult("game_script", True, f"team spread {team_spread_value:+.1f} -- favored or a small enough dog for rushing volume")
        return GateResult("game_script", False, f"team spread {team_spread_value:+.1f} -- too big an underdog for rushing volume")
    if stat_col in PASS_VOLUME_STATS:
        is_dog = team_spread_value < 0
        high_total = total_line is not None and total_line >= GAME_SCRIPT_PASSING_MIN_TOTAL
        if is_dog or high_total:
            reason = "underdog" if is_dog else f"total {total_line:g} clears {GAME_SCRIPT_PASSING_MIN_TOTAL:g}"
            return GateResult("game_script", True, f"{reason} -- supports passing/receiving volume")
        return GateResult("game_script", False, f"favored by {team_spread_value:.1f} with total {total_line}, below {GAME_SCRIPT_PASSING_MIN_TOTAL:g} -- game script works against passing volume")
    return GateResult("game_script", True, "game-script gate not defined for this stat")


def injury_gate(injury_status: str | None) -> GateResult:
    """Stricter than the main ranking engine's rule on purpose: the general
    page still shows Questionable/Doubtful players (flagged, for someone
    to weigh themselves), but a real-money accumulator leg needs a clean
    injury report -- ANY report status fails this gate, not just Out."""
    if injury_status is None:
        return GateResult("injury", True, "not on the injury report")
    return GateResult("injury", False, f"listed {injury_status} on the injury report")


def teammate_injury_flag(teammates_out: list[str]) -> GateResult:
    """FLAG, not a gate -- a teammate being ruled out can change this
    player's volume (a backup WR seeing more targets with WR1 out), but
    doesn't invalidate the leg by itself. Simplification worth naming:
    this flags ANY teammate marked Out on the same team, not just one
    whose specific role would plausibly shift volume onto this player --
    that needs depth-chart/position reasoning beyond what's wired up yet.
    """
    if not teammates_out:
        return GateResult("teammate_injury", True, "no teammates ruled out this week")
    return GateResult(
        "teammate_injury", True,
        f"FLAGGED: teammate(s) out this week ({', '.join(teammates_out)}) -- may change this player's volume",
    )


def sources_gate(n_over_sources: int, min_sources: int = MIN_SOURCES) -> GateResult:
    """Needs analyst_sweep.summarize_sources()'s n_over_sources -- count of
    independent analysts (syndication-deduped) backing the over. This is
    the gate that was deferred until the analyst sweep existed to feed it."""
    if n_over_sources >= min_sources:
        return GateResult("sources", True, f"{n_over_sources} independent analyst(s) backing the over")
    return GateResult(
        "sources", False,
        f"only {n_over_sources} independent analyst(s) backing the over (need {min_sources})",
    )
