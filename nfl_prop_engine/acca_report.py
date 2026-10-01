"""Week 4 accumulator report, built inside the weekly run from data that run
already fetched: the per-book US lines (before they're collapsed to one),
the projections, recent games, opponent factors, spreads/totals and the
injury report. Writes the "accumulator" section of site/data.json.

The bet365 line and price can't be checked automatically (no feed carries
UK bet365 NFL props), so they become targets instead: each suggested leg
says the worst bet365 line and price to accept. Every other gate is
evaluated at that worst acceptable line, so any line Dan takes within the
target has passed them.
"""
import logging
import os
from dataclasses import dataclass, field
from fractions import Fraction
from urllib.parse import urlparse

from accumulator import Candidate, build_accumulator
from config import (
    ANALYST_SWEEP,
    LINE_THRESHOLD,
    MIN_PRICE_DECIMAL,
    ODDS_API_TEAM_NAME_TO_ABBR,
    STAKE_GBP,
    STAT_LABELS,
    market_kind_for,
)
from leg_gates import (
    GateResult,
    form_gate,
    game_script_gate,
    injury_gate,
    matchup_gate,
    outlier_gate,
    sources_gate,
    teammate_injury_flag,
)
from pricing import american_to_decimal, fair_probability_avg, us_consensus_line

logger = logging.getLogger(__name__)

ABBR_TO_TEAM_NAME = {abbr: name for name, abbr in ODDS_API_TEAM_NAME_TO_ABBR.items()}
NOT_CHECKED = [
    "bet365 line and price: check each leg's target on bet365 before betting.",
    "Line movement: needs an earlier snapshot of the line, which isn't recorded yet.",
    "Role change: snap and route share data isn't wired in yet.",
    "Weather: not built yet (phase 2 of the spec).",
]


@dataclass
class LegContext:
    """What the weekly run already knows about one prop."""
    event_id: str
    odds_player_name: str
    market: str
    player: str
    stat_col: str
    team: str
    opponent: str
    home_team: str
    away_team: str
    kickoff: str
    projection: float
    opp_factor: float | None
    team_spread: float | None
    total_line: float | None
    injury_status: str | None
    recent_values: list[float]
    teammates_out: list[str] = field(default_factory=list)

    @property
    def game(self) -> str:
        return f"{self.away_team} @ {self.home_team}"

    @property
    def game_description(self) -> str:
        away = ABBR_TO_TEAM_NAME.get(self.away_team, self.away_team)
        home = ABBR_TO_TEAM_NAME.get(self.home_team, self.home_team)
        return f"{away} at {home}"


@dataclass
class Leg:
    ctx: LegContext
    consensus_line: float | None
    n_books: int
    fair_prob: float | None
    max_line: float | None
    gates: list[GateResult]
    flags: list[str]
    sources: dict = field(default_factory=lambda: {"over": [], "under": []})
    contested: bool = False
    crowded: bool = False

    @property
    def failed(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed]

    @property
    def score(self) -> float:
        if not self.max_line:
            return float("-inf")
        return (self.ctx.projection - self.max_line) / self.max_line


def consensus_by_prop(per_book_rows: list[dict]) -> dict[tuple, dict]:
    """{(event_id, market, odds player name): {line, fair_prob, n_books}}
    from every US book's own line and prices, before the weekly run
    collapses them to a single book."""
    grouped: dict[tuple, list[dict]] = {}
    for row in per_book_rows:
        grouped.setdefault((row["event_id"], row["market"], row["player_name"]), []).append(row)

    result = {}
    for key, rows in grouped.items():
        points = [r.get("point") for r in rows]
        pairs = [(american_to_decimal(r.get("over_price")), american_to_decimal(r.get("under_price"))) for r in rows]
        result[key] = {
            "line": us_consensus_line(points),
            "fair_prob": fair_probability_avg(pairs),
            "n_books": sum(1 for p in points if p is not None),
        }
    return result


def _market_gate(consensus_line: float | None, n_books: int, fair_prob: float | None) -> GateResult:
    if consensus_line is None:
        return GateResult("market", False, f"only {n_books} US book(s) quote this line, too thin to set a target")
    if fair_prob is None:
        return GateResult("market", False, "no US book quotes both sides, so there's no fair price")
    return GateResult("market", True, f"{n_books} US books, consensus {consensus_line:g}")


def _model_gate(projection: float, max_line: float) -> GateResult:
    if projection > max_line:
        return GateResult("model", True, f"projection {projection:.1f} is above the max line {max_line:g}")
    return GateResult("model", False, f"projection {projection:.1f} doesn't clear the max line {max_line:g}")


def evaluate_leg(ctx: LegContext, consensus: dict | None) -> Leg:
    """Every gate that can run before the analyst sweep, at the worst line
    Dan would be told to accept."""
    consensus = consensus or {"line": None, "fair_prob": None, "n_books": 0}
    line = consensus["line"]
    gates = [_market_gate(line, consensus["n_books"], consensus["fair_prob"])]
    max_line = None
    if gates[0].passed:
        max_line = line + LINE_THRESHOLD[market_kind_for(ctx.stat_col)]
        gates += [
            _model_gate(ctx.projection, max_line),
            form_gate(ctx.recent_values, max_line),
            outlier_gate(ctx.recent_values, max_line),
        ]
    gates += [
        matchup_gate(ctx.opp_factor) if ctx.opp_factor is not None
        else GateResult("matchup", False, "no opponent data for this projection"),
        game_script_gate(ctx.stat_col, ctx.team_spread, ctx.total_line),
        injury_gate(ctx.injury_status),
    ]
    flags = []
    teammates = teammate_injury_flag(ctx.teammates_out)
    if teammates.reason.startswith("FLAGGED"):
        flags.append(teammates.reason.removeprefix("FLAGGED: "))
    return Leg(ctx, line, consensus["n_books"], consensus["fair_prob"], max_line, gates, flags)


def _safe_source(pick: dict) -> dict:
    """Analyst picks come from web search, so only plain, length-capped
    text and http(s) links reach the page."""
    url = str(pick.get("url") or "")
    if urlparse(url).scheme not in ("http", "https"):
        url = ""
    return {
        "outlet": str(pick.get("outlet") or "")[:80],
        "analyst": str(pick.get("analyst") or "")[:80],
        "url": url[:500],
    }


def apply_sources(legs: list[Leg], picks_by_game: dict[str, list[dict]] | None, skipped_reason: dict[str, str]) -> None:
    from analyst_sweep import match_picks_to_candidate, summarize_sources

    for leg in legs:
        game = leg.ctx.game_description
        if picks_by_game is None or game not in picks_by_game:
            leg.gates.append(GateResult("sources", False, skipped_reason.get(game, "analyst sweep didn't run")))
            continue
        matched = match_picks_to_candidate(picks_by_game[game], leg.ctx.player, leg.ctx.market, leg.consensus_line)
        consensus = summarize_sources(matched)
        leg.gates.append(sources_gate(consensus.n_over_sources))
        leg.sources = {
            "over": [_safe_source(p) for p in consensus.over_sources],
            "under": [_safe_source(p) for p in consensus.under_sources],
        }
        leg.contested = consensus.contested
        leg.crowded = consensus.crowded
        if consensus.contested:
            leg.flags.append("Contested: an analyst backs the under. Review before betting.")
        if consensus.crowded:
            leg.flags.append("Crowded: 4+ outlets back this over, so the line may already have moved.")


def _fractional(decimal_odds: float) -> str:
    frac = Fraction(decimal_odds - 1).limit_denominator(20)
    return "evens" if frac == 1 else f"{frac.numerator}/{frac.denominator}"


def _leg_record(leg: Leg, bet_builder_games: set[str] | None = None) -> dict:
    ctx = leg.ctx
    return {
        "player": ctx.player,
        "team": ctx.team,
        "opponent": ctx.opponent,
        "game": ctx.game,
        "kickoff": ctx.kickoff,
        "stat": ctx.stat_col,
        "stat_label": STAT_LABELS.get(ctx.stat_col, ctx.stat_col),
        "side": "over",
        "consensus_line": leg.consensus_line,
        "n_books": leg.n_books,
        "max_line": leg.max_line,
        "min_price_decimal": MIN_PRICE_DECIMAL,
        "min_price_fractional": _fractional(MIN_PRICE_DECIMAL),
        "fair_prob": round(leg.fair_prob, 3) if leg.fair_prob is not None else None,
        "projection": round(ctx.projection, 1),
        "bet_builder": bool(bet_builder_games and ctx.game in bet_builder_games),
        "gates": [{"gate": g.gate, "passed": g.passed, "reason": g.reason} for g in leg.gates],
        "flags": leg.flags,
        "sources": leg.sources,
    }


def build_acca_report(
    contexts: list[LegContext],
    per_book_rows: list[dict],
    week: int,
    season: int,
    sweep=None,
    api_key_present: bool | None = None,
) -> dict:
    """sweep(game_descriptions, week, max_workers) -> ({game: picks}, usage);
    defaults to analyst_sweep.sweep_games. Injected so tests never call the
    Claude API."""
    consensus = consensus_by_prop(per_book_rows)
    bookmakers = sorted({r["bookmaker"] for r in per_book_rows if r.get("bookmaker")})
    legs = [evaluate_leg(ctx, consensus.get((ctx.event_id, ctx.market, ctx.odds_player_name))) for ctx in contexts]

    # The sweep costs money and minutes per game, so it only covers games
    # where a leg survived every other gate, most surviving legs first.
    surviving = [leg for leg in legs if not leg.failed]
    per_game: dict[str, int] = {}
    for leg in surviving:
        per_game[leg.ctx.game_description] = per_game.get(leg.ctx.game_description, 0) + 1
    ranked_games = sorted(per_game, key=lambda g: per_game[g], reverse=True)
    to_sweep = ranked_games[: ANALYST_SWEEP["max_games"]]
    skipped = {g: f"analyst sweep capped at {ANALYST_SWEEP['max_games']} games; this one wasn't swept" for g in ranked_games[len(to_sweep):]}

    if api_key_present is None:
        api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))
    sweep_info = {"ran": False, "games": [], "usage": None, "note": ""}
    picks_by_game = None
    if not ANALYST_SWEEP["enabled"]:
        sweep_info["note"] = "analyst sweep is turned off in config"
    elif not api_key_present:
        sweep_info["note"] = "no ANTHROPIC_API_KEY in this run, so the analyst sweep didn't run"
    elif to_sweep:
        if sweep is None:
            from analyst_sweep import sweep_games as sweep
        picks_by_game, usage = sweep(
            [f"{g}, NFL Week {week} {season}" for g in to_sweep], week, max_workers=ANALYST_SWEEP["max_workers"]
        )
        picks_by_game = {g.rsplit(", NFL Week", 1)[0]: picks for g, picks in picks_by_game.items()}
        sweep_info.update(ran=True, games=to_sweep, usage=usage)
    else:
        sweep_info["note"] = "no leg survived the other gates, so there was nothing to sweep"
    if not sweep_info["ran"]:
        skipped.update({g: sweep_info["note"] for g in per_game})
    apply_sources(surviving, picks_by_game, skipped)

    candidates, by_candidate = [], {}
    for leg in surviving:
        candidate = Candidate(
            player=leg.ctx.player, game=leg.ctx.game, market=leg.ctx.market, side="over",
            line=leg.max_line, price_decimal=1 / leg.fair_prob, fair_prob=leg.fair_prob,
            gates=leg.gates, score=leg.score,
        )
        candidates.append(candidate)
        by_candidate[id(candidate)] = leg
    result = build_accumulator(candidates)
    builder_games = set(result.bet_builder_groups)
    chosen = [by_candidate[id(c)] for c in result.legs]

    near_misses = sorted((leg for leg in legs if len(leg.failed) == 1), key=lambda leg: leg.score, reverse=True)[:10]
    excluded = [leg for leg in legs if leg.failed]
    failure_counts: dict[str, int] = {}
    for leg in excluded:
        for gate in leg.failed:
            failure_counts[gate.gate] = failure_counts.get(gate.gate, 0) + 1

    return {
        "mode": result.mode,
        "stake_gbp": STAKE_GBP,
        "legs": [_leg_record(leg, builder_games) for leg in chosen],
        "combined_fair_odds": round(result.combined_odds, 2) if result.combined_odds else None,
        "combined_probability": round(result.combined_probability, 4) if result.combined_probability else None,
        "n_candidates": len(legs),
        "n_passed": sum(1 for c in candidates if c.passed_all),
        "near_misses": [_leg_record(leg) for leg in near_misses],
        "excluded": [
            {
                "player": leg.ctx.player,
                "stat_label": STAT_LABELS.get(leg.ctx.stat_col, leg.ctx.stat_col),
                "game": leg.ctx.game,
                "consensus_line": leg.consensus_line,
                "failed": [{"gate": g.gate, "reason": g.reason} for g in leg.failed],
            }
            for leg in sorted(excluded, key=lambda leg: (leg.ctx.player, leg.ctx.stat_col))
        ],
        "gate_failure_counts": dict(sorted(failure_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "analyst_sweep": sweep_info,
        "bookmakers_seen": bookmakers,
        "bet365_in_feed": any("bet365" in b for b in bookmakers),
        "not_checked": NOT_CHECKED,
    }
