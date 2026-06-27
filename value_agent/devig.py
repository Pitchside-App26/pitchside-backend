"""
De-vigging mathematics.

All functions are pure (no I/O, no side-effects).  This module is the
mathematical core of the agent — keep it dependency-free.

Method: proportional / multiplicative de-vig.
    true_p_i = implied_p_i / sum(implied_p_j for j in market)

This is the standard first-pass method.  The Shin method handles
favourite-longshot bias better but adds complexity; upgrade path is
noted where relevant.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from .config import LOW_CONFIDENCE_DELTA, TOTALS_LINE


# ── types ─────────────────────────────────────────────────────────────────────

@dataclass
class Outcome:
    name: str           # e.g. "Arsenal", "Draw", "Over 2.5", "Yes"
    decimal_odds: float


@dataclass
class DeVigResult:
    outcomes: dict[str, float]      # outcome name → true probability
    fair_odds: dict[str, float]     # outcome name → 1/true_p
    overround: float                # sum(implied_p) − 1, i.e. the vig %
    method: str = "proportional"


class CrossCheckResult(NamedTuple):
    low_confidence: bool
    delta: float        # max absolute difference in true_p between the two books
    preferred: str      # which book's true_p we trust more (by liquidity heuristic)


# ── core maths ────────────────────────────────────────────────────────────────

def implied_prob(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError(f"Invalid decimal odds: {decimal_odds}")
    return 1.0 / decimal_odds


def devig_proportional(outcomes: list[Outcome]) -> DeVigResult:
    """Strip the bookmaker margin using the proportional method."""
    if len(outcomes) < 2:
        raise ValueError("Need at least 2 outcomes to de-vig a market.")

    implied = {o.name: implied_prob(o.decimal_odds) for o in outcomes}
    overround = sum(implied.values()) - 1.0

    total_implied = sum(implied.values())
    true_p = {name: p / total_implied for name, p in implied.items()}
    fair = {name: 1.0 / p for name, p in true_p.items()}

    return DeVigResult(
        outcomes=true_p,
        fair_odds=fair,
        overround=overround,
    )


def cross_check(
    pinnacle_true_p: dict[str, float],
    betfair_true_p: dict[str, float],
) -> CrossCheckResult:
    """
    Compare de-vigged probabilities from two sharp books.
    Returns a low_confidence flag if they disagree materially.
    The more liquid market is Pinnacle for pre-match 1X2 (by convention).
    """
    shared = set(pinnacle_true_p) & set(betfair_true_p)
    if not shared:
        return CrossCheckResult(low_confidence=True, delta=1.0, preferred="pinnacle")

    deltas = [abs(pinnacle_true_p[k] - betfair_true_p[k]) for k in shared]
    max_delta = max(deltas)

    return CrossCheckResult(
        low_confidence=max_delta > LOW_CONFIDENCE_DELTA,
        delta=max_delta,
        preferred="pinnacle",   # heuristic: Pinnacle pre-match liquidity > Betfair
    )


def edge(soft_odds: float, true_p: float) -> float:
    """
    Expected value per £1 staked.
    Positive → value bet.  Negative → mug bet.
    edge = (decimal_odds × true_probability) − 1
    """
    return (soft_odds * true_p) - 1.0


# ── market parsing ────────────────────────────────────────────────────────────

def parse_h2h_outcomes(raw_outcomes: list[dict]) -> list[Outcome]:
    """Convert API outcome list to Outcome objects for a 1X2 market."""
    return [Outcome(name=o["name"], decimal_odds=float(o["price"])) for o in raw_outcomes]


def parse_totals_outcomes(
    raw_outcomes: list[dict], line: float = TOTALS_LINE
) -> list[Outcome] | None:
    """
    Extract Over/Under outcomes at the target line only.
    Returns None if the target line is not present in the data.
    """
    filtered = [o for o in raw_outcomes if o.get("point") == line]
    if len(filtered) < 2:
        return None
    return [
        Outcome(name=f"{o['name']} {line}", decimal_odds=float(o["price"]))
        for o in filtered
    ]


def parse_btts_outcomes(raw_outcomes: list[dict]) -> list[Outcome]:
    """Convert Yes/No BTTS outcomes."""
    return [Outcome(name=o["name"], decimal_odds=float(o["price"])) for o in raw_outcomes]
