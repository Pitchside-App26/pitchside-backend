"""Accumulator builder (Week 4 upgrade spec, Requirement 5). Uses only legs
that passed every gate in leg_gates.py and never pads to reach a target
size -- that padding habit is one of the four concrete Week 3 failures
this whole upgrade exists to fix.
"""
import math
from dataclasses import dataclass, field

from config import MAX_LEGS, MAX_LEGS_PER_GAME, MAX_LEGS_PER_STAT, SIDES, STAKE_GBP
from leg_gates import GateResult


@dataclass
class Candidate:
    player: str
    game: str  # e.g. "NE @ NYJ" -- groups legs for the per-game cap and bet-builder tagging
    market: str
    side: str  # "over" | "under" -- explicit, not assumed, so the overs-only filter has something real to check
    line: float
    price_decimal: float
    fair_prob: float
    gates: list[GateResult]
    # Selection order. Defaults to fair_prob, but de-vigged US probabilities
    # all sit near 50%, so the weekly report passes the projection's margin
    # over the worst acceptable line instead.
    score: float | None = None

    @property
    def passed_all(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def failed_gates(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed]


def filter_by_side(candidates: list[Candidate], sides: list[str] = SIDES) -> list[Candidate]:
    """Requirement 1: 'The candidate list, report and accumulator builder
    contain overs only by default.' This is the actual enforcement point --
    config.SIDES existed before this function did, with nothing reading it."""
    return [c for c in candidates if c.side in sides]


@dataclass
class AccumulatorResult:
    legs: list[Candidate]
    mode: str  # "accumulator" | "singles" | "no_bet"
    combined_odds: float | None
    combined_probability: float | None
    stake_gbp: float
    bet_builder_groups: dict[str, list[Candidate]] = field(default_factory=dict)


def build_accumulator(
    candidates: list[Candidate],
    max_legs: int = MAX_LEGS,
    max_legs_per_game: int = MAX_LEGS_PER_GAME,
    stake_gbp: float = STAKE_GBP,
    max_legs_per_market: int = MAX_LEGS_PER_STAT,
) -> AccumulatorResult:
    """Selects gate-passing legs only, highest fair-probability first,
    respecting max_legs, max_legs_per_game, max_legs_per_market and one leg
    per player. Never adds a failing leg to
    reach max_legs -- if only 4 pass, the output is a 4-fold, not a padded
    6-fold. Fewer than 3 passing legs isn't accumulator territory (too
    correlated a bet on too little confirmed edge): outputs singles
    instead, or "no bet" if nothing passed at all.
    """
    on_side = filter_by_side(candidates)
    passing = sorted(
        (c for c in on_side if c.passed_all),
        key=lambda c: c.score if c.score is not None else c.fair_prob,
        reverse=True,
    )

    selected: list[Candidate] = []
    per_game_count: dict[str, int] = {}
    for c in passing:
        if len(selected) >= max_legs:
            break
        if per_game_count.get(c.game, 0) >= max_legs_per_game:
            continue
        # One leg per player: two overs on the same player are close to one
        # bet twice (a quiet game sinks both), which the acca's price ignores.
        if any(s.player == c.player for s in selected):
            continue
        if sum(s.market == c.market for s in selected) >= max_legs_per_market:
            continue
        selected.append(c)
        per_game_count[c.game] = per_game_count.get(c.game, 0) + 1

    bet_builder_groups = {
        game: [c for c in selected if c.game == game]
        for game, count in per_game_count.items()
        if count > 1
    }

    if len(selected) >= 3:
        combined_odds = math.prod(c.price_decimal for c in selected)
        combined_probability = math.prod(c.fair_prob for c in selected)
        return AccumulatorResult(selected, "accumulator", combined_odds, combined_probability, stake_gbp, bet_builder_groups)
    if selected:
        return AccumulatorResult(selected, "singles", None, None, stake_gbp, bet_builder_groups)
    return AccumulatorResult([], "no_bet", None, None, stake_gbp, {})
