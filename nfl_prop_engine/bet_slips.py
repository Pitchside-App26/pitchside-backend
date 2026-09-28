"""Bet-slip intake: turns screenshots of a placed bet365 slip into a draft
Dan checks before anything is logged.

The model only transcribes what the image shows. Everything that can be
done deterministically happens here instead: odds conversion, matching
player names to the nflverse roster, and arithmetic cross-checks (leg odds
multiplied together vs the slip's total, stake x odds vs potential returns)
that flag a likely misread before Dan is asked to confirm.

The GitHub side (fetching the issue, posting comments) lives in
bet_slip_bot.py; this module has no network access except the Claude call.
"""
import base64
import html
import json
import re
from html.parser import HTMLParser
from math import prod
from urllib.parse import urlparse

import anthropic

from config import ALL_MARKETS, BET_SLIP, STAT_LABELS
from fetch_bet365 import FractionalOddsError, parse_fractional_odds
from match_players import match_name
from pricing import american_to_decimal

BOT_LOGIN = "github-actions[bot]"
DRAFT_MARKER_RE = re.compile(r"<!-- bet-slip-draft:([A-Za-z0-9+/=]+) -->")
STATUS_MARKER = "<!-- bet-slip-status -->"

MARKET_KEYS = [*ALL_MARKETS.keys(), "player_anytime_td", "other"]
LEG_SIDES = ["over", "under", "yes", "no", "other"]
BET_TYPES = ["single", "accumulator", "bet_builder", "other"]

COMMANDS = {
    "confirm": {"confirm", "confirmed", "correct", "looks good", "yes", "y", "\N{THUMBS UP SIGN}"},
    "cancel": {"cancel", "discard", "ignore"},
    "retry": {"retry", "reread", "re-read", "reparse"},
}


class SlipParseError(Exception):
    pass


def _nullable(json_type: str) -> dict:
    return {"anyOf": [{"type": json_type}, {"type": "null"}]}


LEG_SCHEMA = {
    "type": "object",
    "properties": {
        "player": {"type": "string"},
        "team": _nullable("string"),
        "event": _nullable("string"),
        "market_text": {"type": "string"},
        "market": {"type": "string", "enum": MARKET_KEYS},
        "side": {"type": "string", "enum": LEG_SIDES},
        "line": _nullable("number"),
        "odds": _nullable("string"),
        "bet_builder_group": _nullable("string"),
    },
    "required": ["player", "team", "event", "market_text", "market", "side", "line", "odds", "bet_builder_group"],
    "additionalProperties": False,
}

SLIP_SCHEMA = {
    "type": "object",
    "properties": {
        "bet_type": {"type": "string", "enum": BET_TYPES},
        "stake_gbp": _nullable("number"),
        "total_odds": _nullable("string"),
        "potential_returns_gbp": _nullable("number"),
        "legs": {"type": "array", "items": LEG_SCHEMA},
    },
    "required": ["bet_type", "stake_gbp", "total_odds", "potential_returns_gbp", "legs"],
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_bet_slip": {"type": "boolean"},
        "week": _nullable("integer"),
        "slips": {"type": "array", "items": SLIP_SCHEMA},
        "unclear": _nullable("string"),
    },
    "required": ["is_bet_slip", "week", "slips", "unclear"],
    "additionalProperties": False,
}

_MARKET_GUIDE = "\n".join(
    f"- {key}: {STAT_LABELS.get(spec['stat_col'], spec['stat_col'])}" for key, spec in ALL_MARKETS.items()
)

SYSTEM_PROMPT = f"""You transcribe screenshots of NFL bets a bettor has already placed with bet365 (UK), so they can be logged for results tracking. Transcribe exactly what the screenshots show. Never guess.

Rules:
- Each placed bet is one slip. A single, an accumulator, and a bet builder are each one slip. Several screenshots may show different parts of the same long slip: merge them, and list a selection that appears in two screenshots only once.
- Each selection is one leg. For a bet builder (or a bet builder inside an accumulator), give its selections the same bet_builder_group label ("BB1", "BB2", ...). Set a leg's odds to null when the slip only prices the group as a whole.
- Copy odds exactly as displayed ("5/6", "evens", "1.83"). Never convert or calculate odds.
- Stakes and returns are in GBP. Give numbers without the currency symbol.
- market_text is the market name as shown on the slip. market is the closest match from this list:
{_MARKET_GUIDE}
- player_anytime_td: anytime touchdown scorer
- other: anything else (match result, spread, totals, first TD scorer, longest reception, and so on)
- side is over/under for line markets, yes/no for yes/no markets such as anytime TD, other otherwise. line is the number for over/under markets, null otherwise.
- team and event: fill them in only if the slip shows them.
- If any part is cut off or unreadable, use null for that value and say what in "unclear". A null is far better than a guess.
- If the screenshots show no placed bet at all, set is_bet_slip to false and slips to [].
- week: null, unless the bettor's correction states the NFL week.
"""


def _correction_text(previous: dict | None, correction: str | None, notes: str | None) -> str:
    parts = ["Transcribe the placed bet(s) in these screenshots."]
    if notes:
        parts.append(f"The bettor's own notes on the issue:\n{notes}")
    if previous is not None:
        parts.append(
            "Your previous transcription was:\n"
            + json.dumps({"week": previous.get("week"), "slips": previous.get("slips", [])}, indent=1)
        )
    if correction:
        parts.append(
            "The bettor replied with this correction. Apply it; where it conflicts with the screenshot, "
            f"the bettor is right:\n{correction}"
        )
    return "\n\n".join(parts)


def parse_slip_images(
    images: list[tuple[str, bytes]],
    previous: dict | None = None,
    correction: str | None = None,
    notes: str | None = None,
    api_key: str | None = None,
) -> dict:
    """images: [(media_type, raw_bytes)]. Returns the model's transcription
    matching RESPONSE_SCHEMA. Raises SlipParseError on any failure, so the
    caller can tell Dan on the issue instead of logging nothing silently."""
    content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(data).decode()},
        }
        for media_type, data in images
    ]
    content.append({"type": "text", "text": _correction_text(previous, correction, notes)})

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=BET_SLIP["model"],
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        )
    except anthropic.APIError as exc:
        raise SlipParseError(f"Claude API call failed: {exc}") from exc

    if response.stop_reason != "end_turn":
        raise SlipParseError(f"Claude stopped early (stop_reason={response.stop_reason})")
    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SlipParseError("Claude returned output that wasn't valid JSON") from exc


def odds_to_decimal(raw: str | None) -> float | None:
    """Converts odds as displayed (fractional, decimal, or American) to
    decimal. None when absent or unreadable -- never a guess."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if re.fullmatch(r"[+-]\d+(\.\d+)?", text):
        return round(american_to_decimal(float(text)), 4)
    try:
        value = parse_fractional_odds(text)
    except FractionalOddsError:
        return None
    return round(value, 4) if value > 1.0 else None


def _money(value: float | None) -> str:
    return "?" if value is None else f"£{value:,.2f}"


def normalize(parsed: dict, week: int | None, roster_names: list[str] | None, overrides: dict | None = None) -> dict:
    """Turns the model's transcription into the draft Dan confirms: decimal
    odds, roster-matched player names, and warnings for anything that looks
    misread. The draft is exactly what gets logged on confirm."""
    warnings = []
    if parsed.get("unclear"):
        warnings.append(f"Hard to read: {parsed['unclear']}")
    if parsed.get("week") is not None:
        week = parsed["week"]
    if week is None:
        warnings.append("Couldn't work out the NFL week. Reply e.g. `week is 4`.")

    slips = []
    for slip_no, slip in enumerate(parsed.get("slips", []), start=1):
        legs = []
        for leg_no, leg in enumerate(slip["legs"], start=1):
            raw_name = leg["player"].strip()
            player = raw_name
            if roster_names:
                matched, _, _ = match_name(raw_name, roster_names, overrides)
                if matched:
                    player = matched
                else:
                    warnings.append(f"Slip {slip_no} leg {leg_no}: couldn't match \"{raw_name}\" to an NFL roster name.")

            price = odds_to_decimal(leg["odds"])
            if leg["odds"] and price is None:
                warnings.append(f"Slip {slip_no} leg {leg_no}: couldn't read the odds \"{leg['odds']}\".")
            if leg["side"] in ("over", "under") and leg["line"] is None:
                warnings.append(f"Slip {slip_no} leg {leg_no}: over/under bet with no line.")

            legs.append({
                "player": player,
                "player_raw": raw_name,
                "game": leg["event"],
                "market": leg["market"],
                "market_text": leg["market_text"],
                "side": leg["side"],
                "book_line": leg["line"],
                "odds_text": leg["odds"],
                "book_price": price,
                "bet_builder_group": leg["bet_builder_group"],
            })

        total = odds_to_decimal(slip["total_odds"])
        stake = slip["stake_gbp"]
        returns = slip["potential_returns_gbp"]
        if not legs:
            warnings.append(f"Slip {slip_no}: no selections found.")

        leg_prices = [leg["book_price"] for leg in legs]
        if (
            slip["bet_type"] == "accumulator" and total and legs
            and all(p is not None for p in leg_prices)
            and not any(leg["bet_builder_group"] for leg in legs)
        ):
            combined = prod(leg_prices)
            if abs(combined - total) / total > 0.05:
                warnings.append(
                    f"Slip {slip_no}: the leg odds multiply to {combined:.2f} but the slip's total is {total:.2f}. "
                    "One of them is probably misread."
                )
        if stake and total and returns and abs(stake * total - returns) / returns > 0.02:
            warnings.append(
                f"Slip {slip_no}: {_money(stake)} at {total:.2f} should return {_money(stake * total)}, "
                f"but the slip shows {_money(returns)}. Check the stake, odds and returns."
            )

        slips.append({
            "bet_type": slip["bet_type"],
            "stake_gbp": stake,
            "total_odds_text": slip["total_odds"],
            "total_odds_decimal": total,
            "potential_returns_gbp": returns,
            "legs": legs,
        })

    if not parsed.get("is_bet_slip", True) or not slips:
        warnings.append("No placed bet found in the screenshot(s).")

    return {"version": 1, "week": week, "slips": slips, "warnings": warnings}


def _market_label(leg: dict) -> str:
    spec = ALL_MARKETS.get(leg["market"])
    if spec:
        return STAT_LABELS.get(spec["stat_col"], spec["stat_col"])
    if leg["market"] == "player_anytime_td":
        return "Anytime TD"
    return leg["market_text"]


def _bet_label(leg: dict) -> str:
    label = _market_label(leg)
    if leg["side"] in ("over", "under"):
        line = "?" if leg["book_line"] is None else f"{leg['book_line']:g}"
        return f"{label} {leg['side']} {line}"
    if leg["side"] in ("yes", "no"):
        return f"{label}: {leg['side']}"
    return label


def _odds_label(text: str | None, decimal: float | None) -> str:
    if text is None:
        return "–"
    if decimal is None:
        return f"{text} (?)"
    return f"{text} ({decimal:.2f})"


def _cell(text: str) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def encode_draft(draft: dict) -> str:
    payload = base64.standard_b64encode(json.dumps(draft, separators=(",", ":")).encode()).decode()
    return f"<!-- bet-slip-draft:{payload} -->"


def render_draft_comment(draft: dict) -> str:
    week = "?" if draft["week"] is None else draft["week"]
    lines = [f"### Bet slip read: Week {week}", ""]
    for slip_no, slip in enumerate(draft["slips"], start=1):
        kind = slip["bet_type"].replace("_", " ").capitalize()
        lines.append(
            f"**Slip {slip_no}: {kind}**, stake {_money(slip['stake_gbp'])}, "
            f"odds {_odds_label(slip['total_odds_text'], slip['total_odds_decimal'])}, "
            f"returns {_money(slip['potential_returns_gbp'])}"
        )
        lines += ["", "| # | Player | Bet | Odds |", "|---|---|---|---|"]
        for leg_no, leg in enumerate(slip["legs"], start=1):
            player = leg["player"]
            if leg["player_raw"] != leg["player"]:
                player += f" (slip: {leg['player_raw']})"
            if leg["bet_builder_group"]:
                player += f" [{leg['bet_builder_group']}]"
            lines.append(
                f"| {leg_no} | {_cell(player)} | {_cell(_bet_label(leg))} | "
                f"{_cell(_odds_label(leg['odds_text'], leg['book_price']))} |"
            )
        lines.append("")

    if draft["warnings"]:
        lines.append("**Check these before confirming:**")
        lines += [f"- {w}" for w in draft["warnings"]]
        lines.append("")

    lines.append(
        "Reply **confirm** to log this, **cancel** to discard it, or describe what's wrong "
        "(e.g. `leg 2 line is 64.5`, `stake was £10`, `week is 5`) and I'll read it again."
    )
    lines += ["", encode_draft(draft)]
    return "\n".join(lines)


def status_comment(message: str) -> str:
    """Bot replies that aren't a draft still carry a marker, so a duplicate
    intake run (GitHub can send both "opened" and "labeled" for one new
    issue) can tell the issue has already been handled."""
    return f"{message}\n\n{STATUS_MARKER}"


def _is_bot(comment: dict) -> bool:
    user = comment.get("user") or {}
    return user.get("login") == BOT_LOGIN and user.get("type") == "Bot"


def latest_draft(comments: list[dict]) -> dict | None:
    """Only the workflow's own comments are trusted. Anyone can comment on a
    public repo, so a draft-shaped comment from anyone else is ignored."""
    draft = None
    for comment in comments:
        if not _is_bot(comment):
            continue
        match = DRAFT_MARKER_RE.search(comment.get("body") or "")
        if match:
            draft = json.loads(base64.standard_b64decode(match.group(1)))
    return draft


def reply_command(comment: dict) -> str:
    """What an owner's reply asks for. A reply that's only a screenshot means
    "read it again, including this"."""
    text = strip_images(comment.get("body"))
    if not text and extract_image_urls(comment.get("body_html")):
        return "retry"
    return classify_command(text)


def unprocessed_change_before(comments: list[dict], owner: str, comment_id: int) -> bool:
    """True if the owner asked for a change (a correction, a retry, a new
    screenshot) after the latest draft and before `comment_id`, and no newer
    draft answered it. GitHub drops a queued run when a newer one arrives, so
    without this check "confirm" could log a draft that predates a
    correction that was never processed."""
    last_draft = max(
        (i for i, c in enumerate(comments) if _is_bot(c) and DRAFT_MARKER_RE.search(c.get("body") or "")),
        default=-1,
    )
    for comment in comments[last_draft + 1:]:
        if comment.get("id") == comment_id:
            break
        if (comment.get("user") or {}).get("login") == owner and reply_command(comment) in ("correction", "retry"):
            return True
    return False


def already_handled(comments: list[dict]) -> bool:
    return any(
        _is_bot(c) and (DRAFT_MARKER_RE.search(c.get("body") or "") or STATUS_MARKER in (c.get("body") or ""))
        for c in comments
    )


def classify_command(body: str) -> str:
    text = re.sub(r"[\s.!]+$", "", body.strip().lower())
    for command, words in COMMANDS.items():
        if text in words:
            return command
    return "correction"


class _ImgSrcParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.srcs = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            src = dict(attrs).get("src")
            if src:
                self.srcs.append(html.unescape(src))


def _is_uploaded_image(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    if parsed.hostname in ("private-user-images.githubusercontent.com", "user-images.githubusercontent.com"):
        return True
    return parsed.hostname == "github.com" and parsed.path.startswith("/user-attachments/assets/")


def extract_image_urls(body_html: str | None) -> list[str]:
    """Image URLs from an issue's rendered HTML, limited to files uploaded to
    GitHub itself -- so the workflow never fetches an arbitrary URL someone
    put in the issue text."""
    parser = _ImgSrcParser()
    parser.feed(body_html or "")
    seen = []
    for url in parser.srcs:
        if _is_uploaded_image(url) and url not in seen:
            seen.append(url)
    return seen


def detect_media_type(data: bytes) -> str | None:
    """From the file's own bytes, since GitHub's storage often serves images
    as application/octet-stream. Returns "heic" for iPhone HEIC photos
    (the Claude API doesn't accept them) so the caller can say so."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"hevc"):
        return "heic"
    return None


def strip_images(body_markdown: str | None) -> str:
    """The issue's text without image markup, passed to the model as Dan's
    notes (e.g. "stake was £10")."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body_markdown or "")
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.IGNORECASE)
    return text.strip()[:2000]
