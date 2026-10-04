"""What analysts are tipping this week, from ONE web search over the whole
Sunday slate (replacing the per-game analyst sweep, which cost ~$0.84 a
game and found no backers for any slip leg on its first live Sunday).

Analysts mostly publish slate-wide "best props" articles, so one search
over the main outlets collects most of their picks. Each pick is matched
to a real player and game, shown on the page in its own panel (never used
to pick legs), compared with what the engine thinks of the same prop, and
logged so the Tuesday grading run can say whether following analysts beats
the market.
"""
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from rapidfuzz import fuzz

from analyst_sweep import _source_key, estimate_cost_usd, normalize_market, normalize_side, search_for_picks
from config import ALL_MARKETS, ANALYST_PICKS, ANALYST_SWEEP, STAT_LABELS

logger = logging.getLogger(__name__)

SLATE_PROMPT = """You are collecting published NFL player-prop picks for a bettor who wants to see what analysts are tipping -- not your own opinion or predictions.

Find this week's published player-prop picks (over/under on a player's passing, rushing or receiving yards, receptions, completions, carries, touchdown passes, interceptions thrown, tackles or sacks) for these games:
{games}

Start with these outlets: {outlets}. Their weekly "best player props" or "prop picks" articles usually cover several games at once, so prefer those over one search per game.

Only report a pick you actually found in a real, dated article or post that names a player, a market, a side (over or under) and a line. Never infer, guess or invent a pick. Skip anytime-touchdown, first-touchdown, longest-play and combined markets (such as rushing + receiving yards). Skip picks for games not listed, and anything published more than {max_age_days} days ago or about a different week.

Return ONLY a JSON array (no other text) where each element has exactly these fields: outlet, analyst, player, team, market, side, line, price, publish_date, url. Use null for anything you don't have. If you found nothing, return []."""


@dataclass
class PlayerRef:
    player_id: str
    name: str
    team: str


@dataclass
class GameRef:
    game: str  # "KC @ LV", as the engine writes it
    description: str  # "Kansas City Chiefs at Las Vegas Raiders", as LegContext.game_description writes it
    window: str


def fetch_slate_picks(game_lines: list[str], week: int, season: int, api_key: str | None = None) -> tuple[list[dict], dict]:
    system = SLATE_PROMPT.format(
        games="\n".join(f"- {g}" for g in game_lines),
        outlets=", ".join(ANALYST_SWEEP["outlets"]),
        max_age_days=ANALYST_SWEEP["max_age_days"],
    )
    picks, usage = search_for_picks(
        system, f"NFL Week {week}, {season} season: collect the published player-prop picks for the games listed.",
        f"Week {week} slate", max_searches=ANALYST_PICKS["max_searches"],
        max_continuations=ANALYST_PICKS["max_continuations"], api_key=api_key, model=ANALYST_PICKS["model"],
    )
    usage = {**usage, "estimated_cost_usd": round(estimate_cost_usd(usage), 2)}
    return picks, usage


def _safe_url(url) -> str:
    url = str(url or "")
    return url[:500] if urlparse(url).scheme in ("http", "https") else ""


def _text(value, limit: int = 80) -> str:
    return str(value or "").strip()[:limit]


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def match_player(name: str | None, players: list[PlayerRef], team_hint: str | None = None, threshold: int = 85) -> PlayerRef | None:
    """Best fuzzy match on name; when two players clear the threshold, the
    one on the team the article named wins."""
    if not name:
        return None
    scored = [(fuzz.token_sort_ratio(name, p.name), p) for p in players]
    scored = [(s, p) for s, p in scored if s >= threshold]
    if not scored:
        return None
    hint = (team_hint or "").strip().upper()
    scored.sort(key=lambda sp: (sp[0], sp[1].team == hint), reverse=True)
    return scored[0][1]


def resolve_picks(raw_picks: list[dict], players: list[PlayerRef], team_games: dict[str, GameRef]) -> tuple[list[dict], int]:
    """Clean, matched picks for games in the acca windows, one per analyst
    per prop and side, plus how many raw picks were dropped (no matching
    player, a market or side the engine doesn't cover, no line, or a game
    outside the windows)."""
    resolved, seen, dropped = [], set(), 0
    for raw in raw_picks:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        market = normalize_market(raw.get("market"))
        side = normalize_side(raw.get("side"))
        line = _float(raw.get("line"))
        player = match_player(raw.get("player"), players, raw.get("team"))
        game = team_games.get(player.team) if player else None
        if market is None or side is None or line is None or game is None:
            dropped += 1
            continue
        pick = {
            "player": player.name,
            "player_id": player.player_id,
            "team": player.team,
            "game": game.game,
            "game_description": game.description,
            "window": game.window,
            "market": market,
            "stat_col": ALL_MARKETS[market]["stat_col"],
            "stat_label": STAT_LABELS.get(ALL_MARKETS[market]["stat_col"], market),
            "side": side,
            "line": line,
            "price": _text(raw.get("price"), 12) or None,
            "outlet": _text(raw.get("outlet")),
            "analyst": _text(raw.get("analyst")),
            "url": _safe_url(raw.get("url")),
            "publish_date": _text(raw.get("publish_date"), 20) or None,
        }
        key = (pick["player_id"], market, side, _source_key(pick))
        if key in seen:
            continue
        seen.add(key)
        resolved.append(pick)
    return resolved, dropped


def picks_by_game(picks: list[dict], game_descriptions: list[str]) -> dict[str, list[dict]]:
    """For acca_report.apply_sources: every window game gets an entry, so a
    game nobody tipped reads as "0 analysts" rather than "not checked"."""
    grouped: dict[str, list[dict]] = {g: [] for g in game_descriptions}
    for pick in picks:
        grouped.setdefault(pick["game_description"], []).append(pick)
    return grouped


ENGINE_LABELS = {
    "slip_agree": "In your slip",
    "slip_against": "Against your slip",
    "engine_agree": "Engine agrees",
    "engine_disagree": "Engine disagrees",
    "unrated": "Engine didn't rate it",
}


def engine_view(pick: dict, slip_lines: dict[tuple[str, str], float], ranked: dict[tuple[str, str], dict]) -> dict:
    """How the pick sits against the slips (overs only, with the slip's max
    line, since an analyst's line can differ) and the engine's own
    projection for the same player and stat."""
    view = ranked.get((pick["player_id"], pick["stat_col"]))
    slip_line = slip_lines.get((pick["player"], pick["stat_col"]))
    if (pick["player"], pick["stat_col"]) in slip_lines:
        status = "slip_agree" if pick["side"] == "over" else "slip_against"
    elif view is None:
        status = "unrated"
    else:
        status = "engine_agree" if view["direction"] == pick["side"] else "engine_disagree"
    return {
        "status": status,
        "label": ENGINE_LABELS[status],
        "projection": round(view["projection"], 1) if view else None,
        "engine_line": view["line"] if view else None,
        "slip_line": slip_line,
    }


def build_feed(
    picks: list[dict], accumulator: dict | None, ranked: dict[tuple[str, str], dict], info: dict,
) -> dict:
    """The page's analyst_picks section. ranked: {(player_id, stat_col):
    {projection, line, direction}} from the weekly ranking."""
    slip_lines = {}
    for acca in (accumulator or {}).get("accumulators", []):
        slip_lines |= {(leg["player"], leg["stat"]): leg.get("max_line") for leg in acca.get("legs", [])}
    records = [{**{k: v for k, v in p.items() if k != "game_description"}, "engine": engine_view(p, slip_lines, ranked)}
               for p in picks]
    order = {"slip_agree": 0, "slip_against": 0, "engine_disagree": 1, "engine_agree": 2, "unrated": 3}
    records.sort(key=lambda r: (r["window"] != "early", r["game"], order[r["engine"]["status"]], r["player"]))
    return {**info, "picks": records}


def log_rows(feed: dict) -> list[dict]:
    return [
        {
            "player_id": p["player_id"], "player_name": p["player"], "team": p["team"], "stat_col": p["stat_col"],
            "market": p["market"], "game": p["game"], "window": p["window"], "side": p["side"], "line": p["line"],
            "price": p["price"], "outlet": p["outlet"], "analyst": p["analyst"], "url": p["url"],
            "publish_date": p["publish_date"], "engine_status": p["engine"]["status"],
            "engine_projection": p["engine"]["projection"],
        }
        for p in feed.get("picks", [])
    ]
