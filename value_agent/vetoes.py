"""
Veto layer.

Odds find the bet; stats only kill obviously broken ones.

At launch (no stats API), vetoes are:
  1. Low-confidence flag from cross-check (Pinnacle vs Betfair disagree materially)
  2. Stale odds — the soft book's last_update timestamp is too old
  3. Wildly out-of-line price — soft odds more than MAX_SOFT_DRIFT_RATIO away
     from *every* other soft book, suggesting a data error not genuine value
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Soft-book odds are treated as stale if they haven't updated within this window.
MAX_STALE_MINUTES = 120

# If a soft book's price for an outcome is more than this ratio above the
# *median* soft price for the same outcome, flag it as likely a feed error.
MAX_SOFT_DRIFT_RATIO = 1.40   # i.e. 40% above median is suspicious

# Minimum number of soft books quoting an outcome before we trust it
MIN_SOFT_BOOK_QUOTES = 2


@dataclass
class VetoResult:
    vetoed: bool
    reason: str = ""


def veto_low_confidence(low_confidence: bool, delta: float) -> VetoResult:
    """Veto if Pinnacle and Betfair disagree materially on true_p."""
    if low_confidence:
        return VetoResult(
            vetoed=True,
            reason=f"Low confidence: Pinnacle/Betfair true_p differ by {delta:.3f}",
        )
    return VetoResult(vetoed=False)


def veto_stale_odds(last_update_iso: str | None) -> VetoResult:
    """Veto if the soft book's odds haven't been updated recently."""
    if last_update_iso is None:
        return VetoResult(vetoed=True, reason="Missing odds timestamp")

    try:
        updated = datetime.fromisoformat(last_update_iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return VetoResult(vetoed=True, reason=f"Unparseable timestamp: {last_update_iso}")

    age = datetime.now(timezone.utc) - updated
    if age > timedelta(minutes=MAX_STALE_MINUTES):
        return VetoResult(
            vetoed=True,
            reason=f"Stale odds: last updated {int(age.total_seconds() / 60)}m ago",
        )
    return VetoResult(vetoed=False)


def veto_outlier_price(
    candidate_odds: float,
    all_soft_prices: list[float],
) -> VetoResult:
    """
    Veto if the candidate soft price is implausibly higher than other books.
    A price that looks miles better than every other soft book is usually a
    feed error, not genuine value.
    """
    if len(all_soft_prices) < MIN_SOFT_BOOK_QUOTES:
        return VetoResult(
            vetoed=True,
            reason=(
                f"Insufficient quotes: only {len(all_soft_prices)} soft book(s) pricing "
                "this outcome — can't sanity-check the price"
            ),
        )

    median_price = sorted(all_soft_prices)[len(all_soft_prices) // 2]
    if median_price <= 1.0:
        return VetoResult(vetoed=False)

    ratio = candidate_odds / median_price
    if ratio > MAX_SOFT_DRIFT_RATIO:
        return VetoResult(
            vetoed=True,
            reason=(
                f"Outlier price: {candidate_odds:.2f} is {ratio:.2f}× the "
                f"median soft price {median_price:.2f} — likely a data error"
            ),
        )
    return VetoResult(vetoed=False)


def apply_all_vetoes(
    low_confidence: bool,
    confidence_delta: float,
    soft_last_update: str | None,
    candidate_odds: float,
    all_soft_prices: list[float],
) -> VetoResult:
    """
    Run all veto checks in priority order.  Returns the first firing veto,
    or VetoResult(vetoed=False) if all pass.
    """
    checks = [
        veto_low_confidence(low_confidence, confidence_delta),
        veto_stale_odds(soft_last_update),
        veto_outlier_price(candidate_odds, all_soft_prices),
    ]
    for result in checks:
        if result.vetoed:
            log.debug("Vetoed: %s", result.reason)
            return result
    return VetoResult(vetoed=False)
