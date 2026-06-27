"""
Staking and bankroll management.

Rules (from spec):
  - Flat £10 per qualifying single.  No Kelly, no edge-scaling.
  - Exposure cap: MAX_WEEKLY_STAKE total per scan.
  - If bankroll < MIN_BANKROLL, pause all recommendations.
  - Accas: only if same-book, all legs +EV, combined edge ≥ ACCA_EDGE_THRESHOLD,
    legs must be in different matches (not correlated).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import combinations

from .config import (
    ACCA_EDGE_THRESHOLD,
    EDGE_THRESHOLD,
    FLAT_STAKE,
    MAX_WEEKLY_STAKE,
    MIN_BANKROLL,
)
from .devig import edge as compute_edge

log = logging.getLogger(__name__)


@dataclass
class CandidateBet:
    fixture_id: str
    fixture: str
    league: str
    market: str
    selection: str
    book: str
    soft_odds: float
    true_p: float
    fair_odds: float
    edge: float
    low_confidence: bool = False
    veto_reason: str = ""


@dataclass
class BettingSlip:
    legs: list[CandidateBet]
    stake: float
    combined_edge: float
    slip_type: str   # "single" | "double" | "treble"

    @property
    def combined_odds(self) -> float:
        result = 1.0
        for leg in self.legs:
            result *= leg.soft_odds
        return result

    @property
    def label(self) -> str:
        if len(self.legs) == 1:
            return "Single"
        if len(self.legs) == 2:
            return "Double"
        if len(self.legs) == 3:
            return "Treble"
        return f"{len(self.legs)}-fold"


class BankrollPausedError(RuntimeError):
    """Raised when bankroll is below minimum — all recommendations halted."""


def check_bankroll(balance: float) -> None:
    if balance < MIN_BANKROLL:
        raise BankrollPausedError(
            f"Bankroll £{balance:.2f} is below the minimum £{MIN_BANKROLL:.2f}. "
            "Agent paused. Top up the pot before continuing."
        )


def build_slips(
    candidates: list[CandidateBet],
    balance: float,
) -> list[BettingSlip]:
    """
    Convert qualifying candidates into betting slips.

    1. Singles first — every qualifying candidate becomes a single slip.
    2. Same-book multis — only when ≥2 candidates share a book, are in
       different matches, and the combined edge clears ACCA_EDGE_THRESHOLD.
    3. Honour MAX_WEEKLY_STAKE: stop adding slips once the cap is reached.
    """
    check_bankroll(balance)

    slips: list[BettingSlip] = []
    weekly_committed = 0.0

    # ── 1. singles ────────────────────────────────────────────────────────────
    for bet in candidates:
        if weekly_committed + FLAT_STAKE > MAX_WEEKLY_STAKE:
            log.info(
                "Weekly stake cap £%.0f reached — %d singles truncated.",
                MAX_WEEKLY_STAKE,
                len(candidates) - len(slips),
            )
            break
        slips.append(
            BettingSlip(
                legs=[bet],
                stake=FLAT_STAKE,
                combined_edge=bet.edge,
                slip_type="single",
            )
        )
        weekly_committed += FLAT_STAKE

    # ── 2. same-book multis ───────────────────────────────────────────────────
    # Group by book
    by_book: dict[str, list[CandidateBet]] = {}
    for bet in candidates:
        by_book.setdefault(bet.book, []).append(bet)

    for book, book_bets in by_book.items():
        if len(book_bets) < 2:
            continue
        # Try doubles, then trebles; stop at 3-fold per the spec's spirit
        for size in (2, 3):
            for combo in combinations(book_bets, size):
                # Must be different fixtures (no correlated legs)
                fixture_ids = [b.fixture_id for b in combo]
                if len(set(fixture_ids)) < size:
                    continue

                combined_ev = 1.0
                for b in combo:
                    combined_ev *= (b.soft_odds * b.true_p)
                combined_ev -= 1.0

                if combined_ev < ACCA_EDGE_THRESHOLD:
                    continue

                if weekly_committed + FLAT_STAKE > MAX_WEEKLY_STAKE:
                    break

                slip_type = {2: "double", 3: "treble"}[size]
                slips.append(
                    BettingSlip(
                        legs=list(combo),
                        stake=FLAT_STAKE,
                        combined_edge=combined_ev,
                        slip_type=slip_type,
                    )
                )
                weekly_committed += FLAT_STAKE

    log.info(
        "Built %d slip(s) (£%.0f total stake).",
        len(slips),
        weekly_committed,
    )
    return slips
