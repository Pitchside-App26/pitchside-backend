"""
Betting card formatter.

Produces a human-readable weekly card for the terminal and/or a dict
suitable for further processing (e.g. Notion, email, webhook).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .staking import BettingSlip


_DIVIDER = "─" * 72


def format_card(
    slips: list[BettingSlip],
    commentary: str,
    balance: float,
    scan_date: str | None = None,
    active_leagues: list[str] | None = None,
    live_books: list[str] | None = None,
    quota_remaining: int | None = None,
) -> str:
    scan_date = scan_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_stake = sum(s.stake for s in slips)

    lines: list[str] = [
        "",
        "╔══════════════════════════════════════════════════════════════════════╗",
        f"║  UK FOOTBALL VALUE-BET CARD  ·  {scan_date:<36} ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        "",
    ]

    # ── metadata ──────────────────────────────────────────────────────────────
    if active_leagues:
        lines.append(f"Leagues scanned : {', '.join(active_leagues)}")
    if live_books:
        lines.append(f"Live soft books : {', '.join(live_books)}")
    if quota_remaining is not None:
        lines.append(f"API quota left  : {quota_remaining} requests this month")
    lines.append(f"Bankroll        : £{balance:.2f}")
    lines.append(f"Bets this scan  : {len(slips)}  ·  Total stake: £{total_stake:.0f}")
    lines.append("")
    lines.append(_DIVIDER)

    # ── slips ──────────────────────────────────────────────────────────────────
    if not slips:
        lines.append("")
        lines.append("  No value bets found this week.")
        lines.append("")
    else:
        for i, slip in enumerate(slips, 1):
            lines.append("")
            lines.append(f"  BET {i}  [{slip.label.upper()}]  —  stake £{slip.stake:.0f}")
            lines.append("")

            if slip.slip_type == "single":
                leg = slip.legs[0]
                lines += _format_leg(leg)
            else:
                for j, leg in enumerate(slip.legs, 1):
                    lines.append(f"    Leg {j}:")
                    lines += _format_leg(leg, indent="      ")
                combined_ev = slip.combined_edge * 100
                lines.append(
                    f"    Combined odds : {slip.combined_odds:.2f} "
                    f"·  Combined edge : {combined_ev:+.1f}%"
                )

            lines.append("")
            lines.append(_DIVIDER)

    # ── commentary ────────────────────────────────────────────────────────────
    lines.append("")
    lines.append("ANALYSIS")
    lines.append(_DIVIDER)
    lines.append("")
    for cl in commentary.splitlines():
        lines.append(f"  {cl}")
    lines.append("")

    return "\n".join(lines)


def _format_leg(leg, indent: str = "    ") -> list[str]:
    market_label = {
        "h2h": "1X2 Match Result",
        "totals": "Over/Under 2.5",
        "btts": "Both Teams To Score",
    }.get(leg.market, leg.market)

    edge_pct = leg.edge * 100
    edge_flag = "  ⚠ marginal" if leg.edge < 0.05 else ""

    return [
        f"{indent}Fixture  : {leg.fixture}  ({leg.league})",
        f"{indent}Market   : {market_label}",
        f"{indent}Selection: {leg.selection}",
        f"{indent}Bookmaker: {leg.book}",
        f"{indent}Price    : {leg.soft_odds:.2f}  (fair: {leg.fair_odds:.2f})",
        f"{indent}True prob: {leg.true_p * 100:.1f}%",
        f"{indent}Edge     : {edge_pct:+.1f}%{edge_flag}",
    ]


def to_dict(slip: BettingSlip, scan_date: str) -> dict:
    """Serialise a slip to a plain dict for downstream use (e.g. Notion)."""
    if slip.slip_type == "single":
        leg = slip.legs[0]
        return {
            "scan_date": scan_date,
            "type": slip.slip_type,
            "fixture": leg.fixture,
            "league": leg.league,
            "market": leg.market,
            "selection": leg.selection,
            "book": leg.book,
            "odds": leg.soft_odds,
            "fair_odds": leg.fair_odds,
            "true_p": leg.true_p,
            "edge_pct": round(leg.edge * 100, 2),
            "stake": slip.stake,
        }
    return {
        "scan_date": scan_date,
        "type": slip.slip_type,
        "legs": [
            {
                "fixture": b.fixture,
                "selection": b.selection,
                "book": b.book,
                "odds": b.soft_odds,
            }
            for b in slip.legs
        ],
        "combined_odds": slip.combined_odds,
        "combined_edge_pct": round(slip.combined_edge * 100, 2),
        "stake": slip.stake,
    }
