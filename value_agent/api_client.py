"""
OddsPapi / The Odds API client.

All network calls go through this module.  The API key is read from
ODDS_API_KEY in the environment.  Every response includes remaining-requests
headers; we log them so the caller knows how close to the 250/month cap we are.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

from .config import (
    CROSS_CHECK_SHARP,
    FIXTURE_LOOKAHEAD_DAYS,
    LEAGUES,
    MARKETS,
    ODDS_API_BASE_URL,
    ODDS_FORMAT,
    ODDS_REGION,
    PRIMARY_SHARP,
    SHARP_BOOKS,
    SOFT_BOOKS_CONFIGURED,
)

log = logging.getLogger(__name__)


class OddsAPIError(RuntimeError):
    pass


class OddsAPIClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ODDS_API_KEY", "")
        if not self.api_key:
            raise OddsAPIError(
                "ODDS_API_KEY not set. Export it before running the agent."
            )
        self._session = requests.Session()
        self._session.params = {"apiKey": self.api_key}  # type: ignore[assignment]
        self.requests_remaining: int | None = None
        self.requests_used: int | None = None

    # ── internal ──────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{ODDS_API_BASE_URL}{path}"
        resp = self._session.get(url, params=params or {}, timeout=30)
        self._log_quota(resp)
        if resp.status_code == 422:
            raise OddsAPIError(f"Unprocessable request to {path}: {resp.text}")
        if resp.status_code == 429:
            raise OddsAPIError("OddsAPI rate limit / quota exhausted (429).")
        resp.raise_for_status()
        return resp.json()

    def _log_quota(self, resp: requests.Response) -> None:
        remaining = resp.headers.get("x-requests-remaining")
        used = resp.headers.get("x-requests-used")
        if remaining is not None:
            self.requests_remaining = int(remaining)
        if used is not None:
            self.requests_used = int(used)
        if self.requests_remaining is not None:
            log.info(
                "OddsAPI quota: %s used, %s remaining",
                self.requests_used,
                self.requests_remaining,
            )
            if self.requests_remaining < 20:
                log.warning(
                    "QUOTA WARNING: only %s requests remaining this month.",
                    self.requests_remaining,
                )

    # ── public methods ────────────────────────────────────────────────────────

    def list_bookmakers(self) -> list[dict]:
        """
        Returns all bookmakers available in the feed.
        Used by verify_books() to determine which of our configured books
        are actually present.
        """
        return self._get("/sports/soccer_england_premier_league/odds", params={
            "regions": ODDS_REGION,
            "markets": "h2h",
            "oddsFormat": ODDS_FORMAT,
            "bookmakers": ",".join(SHARP_BOOKS + SOFT_BOOKS_CONFIGURED),
            "dateFormat": "iso",
        })

    def get_bookmaker_keys(self) -> set[str]:
        """
        Return the set of bookmaker keys the feed will actually respond with
        for at least one current PL fixture.  This is our verification step.
        """
        try:
            fixtures = self._get(
                "/sports/soccer_england_premier_league/odds",
                params={
                    "regions": ODDS_REGION,
                    "markets": "h2h",
                    "oddsFormat": ODDS_FORMAT,
                    "bookmakers": ",".join(SHARP_BOOKS + SOFT_BOOKS_CONFIGURED),
                    "dateFormat": "iso",
                },
            )
        except requests.HTTPError:
            return set()

        keys: set[str] = set()
        for fixture in fixtures:
            for bm in fixture.get("bookmakers", []):
                keys.add(bm["key"])
        return keys

    def get_odds_for_sport(
        self,
        sport_key: str,
        bookmaker_keys: list[str],
        markets: list[str] | None = None,
    ) -> list[dict]:
        """
        Fetch all upcoming odds for a sport in a single API call.
        Returns the raw fixture list with embedded bookmaker odds.
        """
        markets_param = ",".join(markets or MARKETS)
        bm_param = ",".join(bookmaker_keys)

        # commenceTimeTo limits results to FIXTURE_LOOKAHEAD_DAYS from now
        cutoff = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff += timedelta(days=FIXTURE_LOOKAHEAD_DAYS)

        return self._get(
            f"/sports/{sport_key}/odds",
            params={
                "regions": ODDS_REGION,
                "markets": markets_param,
                "oddsFormat": ODDS_FORMAT,
                "bookmakers": bm_param,
                "dateFormat": "iso",
                "commenceTimeTo": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    def get_closing_odds(self, sport_key: str, event_id: str) -> dict | None:
        """
        Fetch the current (or closing) Pinnacle odds for a specific event.
        Used post-kick-off to record CLV.
        """
        try:
            data = self._get(
                f"/sports/{sport_key}/events/{event_id}/odds",
                params={
                    "regions": ODDS_REGION,
                    "markets": "h2h",
                    "oddsFormat": ODDS_FORMAT,
                    "bookmakers": PRIMARY_SHARP,
                    "dateFormat": "iso",
                },
            )
        except (OddsAPIError, requests.HTTPError):
            return None
        return data
