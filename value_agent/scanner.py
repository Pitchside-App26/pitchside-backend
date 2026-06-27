"""
Main pipeline orchestrator.

Implements the 10-step pipeline from the spec:
  1  verify_books()
  2  fetch_fixtures()
  3  fetch_odds()       (folded into step 2 — one API call per sport)
  4  devig()
  5  find_value()
  6  apply_vetoes()
  7  build_slips()
  8  size_and_log()
  9  commentary()
  10 output()
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .api_client import OddsAPIClient, OddsAPIError
from .config import (
    CONDITIONAL_LEAGUES,
    CROSS_CHECK_SHARP,
    EDGE_THRESHOLD,
    FLAT_STAKE,
    LEAGUES,
    MARKETS,
    PRIMARY_SHARP,
    SHARP_BOOKS,
    SOFT_BOOKS_CONFIGURED,
    TOTALS_LINE,
)
from .devig import (
    DeVigResult,
    Outcome,
    cross_check,
    devig_proportional,
    edge as compute_edge,
    parse_btts_outcomes,
    parse_h2h_outcomes,
    parse_totals_outcomes,
)
from .staking import BankrollPausedError, BettingSlip, CandidateBet, build_slips
from .vetoes import apply_all_vetoes

log = logging.getLogger(__name__)


@dataclass
class ScanResult:
    slips: list[BettingSlip] = field(default_factory=list)
    candidates_found: int = 0
    candidates_vetoed: int = 0
    live_books: list[str] = field(default_factory=list)
    active_leagues: list[str] = field(default_factory=list)
    quota_remaining: int | None = None
    bankroll_paused: bool = False
    pause_reason: str = ""


def verify_books(client: OddsAPIClient) -> list[str]:
    """
    Step 1: query the feed to discover which of our configured soft books
    are actually present.  Halts with OddsAPIError if either sharp book
    (Pinnacle, Betfair) is absent.

    Returns the list of live soft-book keys to use for this scan.
    """
    log.info("Verifying available bookmakers …")
    live_keys = client.get_bookmaker_keys()

    for sharp in SHARP_BOOKS:
        if sharp not in live_keys:
            raise OddsAPIError(
                f"Sharp reference book '{sharp}' not found in the feed. "
                "Cannot compute true probabilities without it. Aborting."
            )

    live_soft = [k for k in SOFT_BOOKS_CONFIGURED if k in live_keys]
    missing = [k for k in SOFT_BOOKS_CONFIGURED if k not in live_keys]

    if missing:
        log.info("Soft books not in feed (dropped): %s", missing)
    log.info("Live soft books (%d): %s", len(live_soft), live_soft)
    return live_soft


def _get_market_outcomes(bookmaker: dict, market_key: str) -> list[dict] | None:
    for market in bookmaker.get("markets", []):
        if market["key"] == market_key:
            return market.get("outcomes", [])
    return None


def _get_last_update(bookmaker: dict, market_key: str) -> str | None:
    for market in bookmaker.get("markets", []):
        if market["key"] == market_key:
            return market.get("last_update")
    return None


def _parse_outcomes_for_market(
    market_key: str, raw_outcomes: list[dict]
) -> list[Outcome] | None:
    if market_key == "h2h":
        return parse_h2h_outcomes(raw_outcomes)
    if market_key == "totals":
        return parse_totals_outcomes(raw_outcomes, TOTALS_LINE)
    if market_key == "btts":
        return parse_btts_outcomes(raw_outcomes)
    return None


def _find_bookmaker(fixture: dict, key: str) -> dict | None:
    for bm in fixture.get("bookmakers", []):
        if bm["key"] == key:
            return bm
    return None


def scan(
    client: OddsAPIClient,
    balance: float,
    live_soft_books: list[str] | None = None,
) -> ScanResult:
    """
    Run the full weekly scan and return a ScanResult.

    live_soft_books: if pre-verified, pass them in; otherwise verify_books()
    is called automatically.
    """
    result = ScanResult()

    # ── Step 1: verify ────────────────────────────────────────────────────────
    if live_soft_books is None:
        live_soft_books = verify_books(client)
    result.live_books = live_soft_books
    all_books = SHARP_BOOKS + live_soft_books

    # ── Step 2+3: fetch fixtures + odds ───────────────────────────────────────
    all_candidates: list[CandidateBet] = []
    active_leagues: list[str] = []

    for sport_key, league_name in LEAGUES.items():
        log.info("Fetching odds for %s …", league_name)
        try:
            fixtures = client.get_odds_for_sport(
                sport_key, all_books, markets=MARKETS
            )
        except OddsAPIError as exc:
            log.warning("Skipping %s: %s", league_name, exc)
            continue

        if not fixtures:
            log.info("%s: no fixtures in window.", league_name)
            continue

        league_candidates = _process_league(
            fixtures, sport_key, league_name, live_soft_books
        )

        # Conditional league: only include if we actually got sharp prices
        if sport_key in CONDITIONAL_LEAGUES and not league_candidates:
            log.info(
                "%s: no sharp prices found — dropping conditional league.", league_name
            )
            continue

        all_candidates.extend(league_candidates)
        if league_candidates:
            active_leagues.append(league_name)

    result.active_leagues = active_leagues
    result.candidates_found = len(all_candidates)

    # Count vetoed (veto_reason set)
    vetoed = [c for c in all_candidates if c.veto_reason]
    result.candidates_vetoed = len(vetoed)

    qualifying = [c for c in all_candidates if not c.veto_reason]
    log.info(
        "Scan complete: %d candidates, %d vetoed, %d qualifying.",
        len(all_candidates), len(vetoed), len(qualifying),
    )

    # ── Steps 7+8: build slips ────────────────────────────────────────────────
    try:
        slips = build_slips(qualifying, balance)
        result.slips = slips
    except BankrollPausedError as exc:
        result.bankroll_paused = True
        result.pause_reason = str(exc)
        log.warning("%s", exc)

    result.quota_remaining = client.requests_remaining
    return result


def _process_league(
    fixtures: list[dict],
    sport_key: str,
    league_name: str,
    live_soft_books: list[str],
) -> list[CandidateBet]:
    candidates: list[CandidateBet] = []

    for fixture in fixtures:
        fixture_id = fixture.get("id", "")
        home = fixture.get("home_team", "?")
        away = fixture.get("away_team", "?")
        fixture_label = f"{home} vs {away}"

        pinnacle_bm = _find_bookmaker(fixture, PRIMARY_SHARP)
        betfair_bm = _find_bookmaker(fixture, CROSS_CHECK_SHARP)

        if pinnacle_bm is None:
            log.debug("No Pinnacle data for %s — skipping.", fixture_label)
            continue

        for market_key in MARKETS:
            pin_raw = _get_market_outcomes(pinnacle_bm, market_key)
            if not pin_raw:
                continue

            pin_outcomes = _parse_outcomes_for_market(market_key, pin_raw)
            if not pin_outcomes:
                continue

            # ── Step 4: de-vig ────────────────────────────────────────────────
            try:
                pin_devig = devig_proportional(pin_outcomes)
            except (ValueError, ZeroDivisionError) as exc:
                log.debug("Devig failed for %s %s: %s", fixture_label, market_key, exc)
                continue

            # Cross-check with Betfair if available
            low_confidence = False
            confidence_delta = 0.0
            if betfair_bm:
                bf_raw = _get_market_outcomes(betfair_bm, market_key)
                if bf_raw:
                    bf_outcomes = _parse_outcomes_for_market(market_key, bf_raw)
                    if bf_outcomes:
                        try:
                            bf_devig = devig_proportional(bf_outcomes)
                            cc = cross_check(pin_devig.outcomes, bf_devig.outcomes)
                            low_confidence = cc.low_confidence
                            confidence_delta = cc.delta
                        except (ValueError, ZeroDivisionError):
                            pass

            # ── Step 5: find value ────────────────────────────────────────────
            for soft_key in live_soft_books:
                soft_bm = _find_bookmaker(fixture, soft_key)
                if soft_bm is None:
                    continue

                soft_raw = _get_market_outcomes(soft_bm, market_key)
                if not soft_raw:
                    continue

                soft_outcomes = _parse_outcomes_for_market(market_key, soft_raw)
                if not soft_outcomes:
                    continue

                soft_last_update = _get_last_update(soft_bm, market_key)

                # Build a price-by-name lookup for all soft books (for outlier check)
                for outcome in soft_outcomes:
                    sel_name = outcome.name
                    soft_price = outcome.decimal_odds
                    true_p = pin_devig.outcomes.get(sel_name)
                    if true_p is None:
                        continue

                    ev = compute_edge(soft_price, true_p)
                    if ev < EDGE_THRESHOLD:
                        continue  # sub-threshold — noise

                    fair = pin_devig.fair_odds[sel_name]

                    # Gather all soft prices for this outcome (for outlier veto)
                    all_soft_prices = _collect_soft_prices(
                        fixture, market_key, sel_name, live_soft_books
                    )

                    # ── Step 6: veto ──────────────────────────────────────────
                    veto = apply_all_vetoes(
                        low_confidence=low_confidence,
                        confidence_delta=confidence_delta,
                        soft_last_update=soft_last_update,
                        candidate_odds=soft_price,
                        all_soft_prices=all_soft_prices,
                    )

                    candidate = CandidateBet(
                        fixture_id=fixture_id,
                        fixture=fixture_label,
                        league=league_name,
                        market=market_key,
                        selection=sel_name,
                        book=soft_key,
                        soft_odds=soft_price,
                        true_p=true_p,
                        fair_odds=fair,
                        edge=ev,
                        low_confidence=low_confidence,
                        veto_reason=veto.reason if veto.vetoed else "",
                    )
                    candidates.append(candidate)

    return candidates


def _collect_soft_prices(
    fixture: dict,
    market_key: str,
    selection_name: str,
    soft_books: list[str],
) -> list[float]:
    """Return all soft-book prices for a given outcome (for outlier detection)."""
    prices: list[float] = []
    for key in soft_books:
        bm = _find_bookmaker(fixture, key)
        if bm is None:
            continue
        raw = _get_market_outcomes(bm, market_key)
        if not raw:
            continue
        for o in raw:
            if o.get("name") == selection_name or (
                market_key == "totals"
                and f"{o.get('name')} {o.get('point', '')}" == selection_name
            ):
                prices.append(float(o["price"]))
    return prices
