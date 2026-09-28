"""Analyst sweep (Week 4 upgrade spec, Requirement 7). Calls the Claude
API once per GAME (not once per player, to keep cost down) with web
search, asking for that game's published player-prop picks as real,
sourced JSON -- never a guess dressed up as a pick.

This calls a SEPARATE Anthropic account from the one running this
engine's own development -- its own API key (ANTHROPIC_API_KEY, a repo
secret), its own billing, its own spend cap (config.ANALYST_SWEEP's
spend_cap_usd, set to $15/month). Model is Sonnet 5 by config default --
structured extraction against a schema, not deep reasoning, so the
cheaper tier was the deliberate choice over Opus.

This module's only job is getting real picks out of the model and
matching them to a candidate leg. Independence dedup, the contested-leg
flag, and the crowding flag all happen in summarize_sources() below --
none of it is guessed, all of it is arithmetic over what the model
actually reported finding.
"""
import json
import logging
from dataclasses import dataclass, field

import anthropic
from rapidfuzz import fuzz

from config import ANALYST_SWEEP

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are researching published NFL player-prop picks for a specific game, for a bettor who wants to know what independent analysts are saying -- not your own opinion or a prediction of your own.

Search the web for this week's published player-prop picks from these outlets: {outlets}.

Only report a pick if you found a real, specific, dated article or post naming a player, a market, a side (over/under), and a line. Never infer, guess, or invent a pick that isn't backed by something you actually found. If a source is paywalled and you can't see which side they picked, still list it with side "unknown" and note that in track_record -- don't guess the side.

Ignore anything published more than {max_age_days} days ago, or about a different week than the one asked about.

Return ONLY a JSON array (no other text, no markdown code fences) where each element has exactly these fields: outlet, analyst, player, market, side, line, price, book, publish_date, url, track_record.

Use null for any field you don't have real information for. If you found no real picks for this game, return an empty array: []
"""


def fetch_analyst_picks(game_description: str, week: int, api_key: str | None = None) -> list[dict]:
    """game_description: e.g. "New England Patriots at New York Jets, NFL
    Week 4 2026". Returns raw pick dicts (validated only as far as "is
    this the JSON shape asked for" -- matching to an actual candidate leg
    happens in match_picks_to_candidate below). api_key=None resolves
    ANTHROPIC_API_KEY from the environment, same as the SDK default.

    A failed call (bad key, rate limit, spend cap hit) logs a warning and
    returns an empty list rather than crashing the whole sweep over one
    game -- the Sources gate then just fails for that game's props, which
    is the correct, safe outcome for "couldn't verify", not a crash.
    """
    client = anthropic.Anthropic(api_key=api_key)
    system = SYSTEM_PROMPT.format(
        outlets=", ".join(ANALYST_SWEEP["outlets"]),
        max_age_days=ANALYST_SWEEP["max_age_days"],
    )
    try:
        response = client.messages.create(
            model=ANALYST_SWEEP["model"],
            # 16000 (not 4096): Sonnet 5 runs adaptive thinking on by
            # default, and thinking + the web_search tool's own turns share
            # this same max_tokens budget with the final text/JSON. A tight
            # cap risks stop_reason="max_tokens" before any real output is
            # written, which looks identical to "found nothing" downstream.
            max_tokens=16000,
            system=system,
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user", "content": f"Game: {game_description}. NFL Week {week}."}],
        )
    except anthropic.APIError as exc:
        logger.warning("Analyst sweep API call failed for %r (%s) -- skipping this game.", game_description, exc)
        return []

    block_types = [block.type for block in response.content]
    logger.info(
        "Analyst sweep response for %r: stop_reason=%s, blocks=%s",
        game_description, response.stop_reason, block_types,
    )
    if response.stop_reason == "max_tokens":
        logger.warning(
            "Analyst sweep for %r hit max_tokens before finishing -- output was likely "
            "truncated. Consider raising max_tokens further.", game_description,
        )

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        logger.warning(
            "Analyst sweep for %r got no text block back (stop_reason=%s, blocks=%s) -- "
            "nothing to parse.", game_description, response.stop_reason, block_types,
        )
    picks = parse_picks_json(text, game_description)
    if not picks and text.strip():
        logger.info("Analyst sweep for %r raw text (first 2000 chars): %s", game_description, text[:2000])
    return picks


def parse_picks_json(text: str, game_description: str = "") -> list[dict]:
    """Pulled out of fetch_analyst_picks so it's testable without a real
    API call. Tolerant of the model wrapping its JSON in a markdown fence
    despite being told not to -- a real, observed model behavior, not a
    hypothetical."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        picks = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Analyst sweep for %r returned non-JSON output -- skipping.", game_description)
        return []
    if not isinstance(picks, list):
        logger.warning("Analyst sweep for %r returned JSON that wasn't a list -- skipping.", game_description)
        return []
    return picks


def _same_player(pick_name: str | None, candidate_name: str, threshold: int = 85) -> bool:
    if not pick_name:
        return False
    return fuzz.token_sort_ratio(pick_name, candidate_name) >= threshold


def match_picks_to_candidate(
    picks: list[dict], player: str, market: str, line: float, line_tolerance: float = 2.0
) -> list[dict]:
    """A pick at a different line still counts if it's within tolerance
    (per the spec) -- the analyst may have picked before the line moved
    to what bet365 or the US consensus now shows."""
    matched = []
    for pick in picks:
        if not _same_player(pick.get("player"), player):
            continue
        if pick.get("market") != market:
            continue
        pick_line = pick.get("line")
        if pick_line is None or abs(float(pick_line) - line) > line_tolerance:
            continue
        matched.append(pick)
    return matched


@dataclass
class AnalystConsensus:
    over_sources: list[dict] = field(default_factory=list)  # deduped by analyst
    under_sources: list[dict] = field(default_factory=list)  # deduped by analyst
    contested: bool = False
    crowded: bool = False

    @property
    def n_over_sources(self) -> int:
        return len(self.over_sources)


def _dedup_by_analyst(picks: list[dict]) -> list[dict]:
    """Count each ANALYST once, even when their piece is syndicated across
    multiple outlets -- an Action Network article republished on Yahoo is
    one source, not two. Keyed on a normalized analyst name; a pick with
    no analyst name at all is kept as-is (can't dedupe what isn't
    identified), so it always counts as its own source."""
    seen = set()
    result = []
    for pick in picks:
        analyst = pick.get("analyst")
        key = analyst.strip().lower() if analyst else None
        if key is None or key not in seen:
            result.append(pick)
            if key is not None:
                seen.add(key)
    return result


def summarize_sources(matched_picks: list[dict], crowding_flag_outlets: int = ANALYST_SWEEP["crowding_flag_outlets"]) -> AnalystConsensus:
    """The spec's Requirement 7 aggregation: independence dedup, the
    contested flag (any analyst on the under), and the crowding flag (4+
    independent OUTLETS backing the over -- outlets, not analysts, per
    the spec's own wording, a deliberately different unit than the
    analyst-count used for the Sources gate itself)."""
    over = _dedup_by_analyst([p for p in matched_picks if p.get("side") == "over"])
    under = _dedup_by_analyst([p for p in matched_picks if p.get("side") == "under"])
    outlets = {p["outlet"] for p in over if p.get("outlet")}
    return AnalystConsensus(
        over_sources=over,
        under_sources=under,
        contested=len(under) > 0,
        crowded=len(outlets) >= crowding_flag_outlets,
    )
