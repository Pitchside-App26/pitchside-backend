"""
LLM commentary layer — the only place in the agent that calls Claude.

The deterministic pipeline (scanner.py) finds bets.  This module explains
them in plain English and flags anything that looks off.  It never invents
stats, never recommends bets the code didn't flag, never inflates confidence.
"""
from __future__ import annotations

import logging
import os

import anthropic

from .config import COMMENTARY_MODEL
from .staking import BettingSlip

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the analysis layer of a no-vig football value-betting tool. You do not pick bets — deterministic code already did, by comparing each bookmaker's price to a vig-stripped sharp probability from Pinnacle and Betfair Exchange. Your only job is to explain the card clearly and flag anything that looks wrong.

For each bet you are given: fixture, market, selection, bookmaker, price taken, fair price, edge%, and the de-vigged true probability.

For each, write two or three plain sentences: what the bet is, where the value comes from (the gap between the taken price and the fair price), and the single biggest reason it might be a trap (stale line, thin market, obvious correlation, or a price that looks too good to be real). Be blunt about weak edges — a 3% edge is marginal and you say so.

Rules: never inflate confidence; never invent stats, form, or team news you weren't given; never recommend a bet the code didn't flag; never suggest an accumulator the code didn't build. If a bet's edge is barely over threshold or the market looks thin, say it's borderline rather than dressing it up. End with one line: total stake, number of bets, and a reminder that closing-line value, not this week's result, is the scoreboard."""


def _format_slips_for_prompt(slips: list[BettingSlip]) -> str:
    lines: list[str] = []
    for i, slip in enumerate(slips, 1):
        if slip.slip_type == "single":
            leg = slip.legs[0]
            lines.append(
                f"{i}. [{slip.label}] {leg.fixture} | {leg.market} | {leg.selection} "
                f"@ {leg.soft_odds:.2f} ({leg.book}) | "
                f"fair price: {leg.fair_odds:.2f} | "
                f"edge: {leg.edge * 100:.1f}% | "
                f"true prob: {leg.true_p * 100:.1f}% | "
                f"stake: £{slip.stake:.0f}"
            )
        else:
            legs_desc = " + ".join(
                f"{b.fixture} {b.selection} @ {b.soft_odds:.2f}"
                for b in slip.legs
            )
            lines.append(
                f"{i}. [{slip.label}] {legs_desc} | "
                f"combined odds: {slip.combined_odds:.2f} ({slip.legs[0].book}) | "
                f"combined edge: {slip.combined_edge * 100:.1f}% | "
                f"stake: £{slip.stake:.0f}"
            )
    return "\n".join(lines)


def generate_commentary(
    slips: list[BettingSlip],
    total_stake: float,
    api_key: str | None = None,
) -> str:
    """
    Call Claude to generate the plain-English weekly card commentary.
    Returns the full text.  Falls back to a brief stub if the API is
    unavailable (so the rest of the pipeline still completes).
    """
    if not slips:
        return "No value bets identified this week. No stake committed."

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        log.warning("ANTHROPIC_API_KEY not set — skipping LLM commentary.")
        return _fallback_commentary(slips, total_stake)

    bet_block = _format_slips_for_prompt(slips)
    user_message = (
        f"Here is this week's betting card ({len(slips)} bet(s), "
        f"£{total_stake:.0f} total stake):\n\n{bet_block}\n\n"
        "Please provide your analysis."
    )

    try:
        client = anthropic.Anthropic(api_key=key)
        message = client.messages.create(
            model=COMMENTARY_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text
    except anthropic.APIError as exc:
        log.error("Claude API error: %s — using fallback commentary.", exc)
        return _fallback_commentary(slips, total_stake)


def _fallback_commentary(slips: list[BettingSlip], total_stake: float) -> str:
    """Minimal stub used when the API is unavailable."""
    lines = ["=== Commentary unavailable (API key missing or API error) ===", ""]
    for i, slip in enumerate(slips, 1):
        if slip.slip_type == "single":
            leg = slip.legs[0]
            lines.append(
                f"{i}. {leg.fixture} | {leg.selection} @ {leg.soft_odds:.2f} "
                f"({leg.book}) | edge {leg.edge * 100:.1f}%"
            )
        else:
            legs = " + ".join(f"{b.selection}" for b in slip.legs)
            lines.append(f"{i}. {slip.label}: {legs} | edge {slip.combined_edge * 100:.1f}%")

    lines += [
        "",
        f"Total stake: £{total_stake:.0f} across {len(slips)} bet(s).",
        "Scoreboard: closing-line value over hundreds of bets, not this week's result.",
    ]
    return "\n".join(lines)
