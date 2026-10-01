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
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from math import prod
from fractions import Fraction
from urllib.parse import urlparse

from accumulator import Candidate, build_accumulator
from config import (
    ACCA_WINDOWS,
    ANALYST_SWEEP,
    FILL_WITH_NEAR_MISSES,
    LINE_THRESHOLD,
    MAX_LEGS,
    MAX_LEGS_PER_GAME,
    MAX_US_FAIR_PROB,
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
    player_id: str = ""
    window: str | None = None  # key into config.ACCA_WINDOWS, None outside both
    season_std: float | None = None  # the projection's game-to-game spread for this stat

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
    sources_checked: bool = False
    sources_note: str = "not checked: this leg had already failed another gate"
    contested: bool = False
    crowded: bool = False

    @property
    def failed(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed]

    @property
    def score(self) -> float:
        """How many of this player's usual game-to-game swings the projection
        clears the max line by -- the same standardised edge rank_props uses.
        Dividing by the line instead made every 0.5 line (pass TDs, INTs)
        outrank every yardage leg, however thin its real edge."""
        spread = self.ctx.season_std
        if not spread or spread <= 0:
            recent = self.ctx.recent_values
            spread = statistics.stdev(recent) if len(recent) >= 2 else 0
        if self.max_line is None or not spread:
            return float("-inf")
        return (self.ctx.projection - self.max_line) / spread


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def name_key(name: str | None) -> str:
    """Books don't always spell a player the same way ("Kenneth Walker III"
    vs "Kenneth Walker", "D.J. Moore" vs "DJ Moore"); this is what the
    consensus groups on, so one spelling difference doesn't split a prop
    into two thin markets."""
    words = re.sub(r"[^a-z ]", "", str(name or "").lower().replace("-", " ")).split()
    return " ".join(w for w in words if w not in _SUFFIXES)


def consensus_by_prop(per_book_rows: list[dict]) -> dict[tuple, dict]:
    """{(event_id, market, name_key(player)): {line, fair_prob, n_books}}
    from every US book's own line and prices, before the weekly run
    collapses them to a single book."""
    grouped: dict[tuple, list[dict]] = {}
    for row in per_book_rows:
        grouped.setdefault((row["event_id"], row["market"], name_key(row["player_name"])), []).append(row)

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


def _odds_gate(fair_prob: float, stat_col: str) -> GateResult:
    cap = MAX_US_FAIR_PROB[market_kind_for(stat_col)]
    fair_odds = 1 / fair_prob
    if fair_prob <= cap:
        return GateResult("odds", True, f"US fair odds {fair_odds:.2f} ({fair_prob:.0%}), room for bet365 to reach {MIN_PRICE_DECIMAL:.2f}")
    return GateResult(
        "odds", False,
        f"US fair odds {fair_odds:.2f} ({fair_prob:.0%}): too short for bet365 to offer {MIN_PRICE_DECIMAL:.2f} after its margin",
    )


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
            _odds_gate(consensus["fair_prob"], ctx.stat_col),
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


def apply_sources(
    legs: list[Leg], picks_by_game: dict[str, list[dict]] | None, skipped_reason: dict[str, str], as_gate: bool,
) -> None:
    """Records each leg's analyst backing. As a gate (the spec's original
    rule) a leg without MIN_SOURCES backers fails; as a signal (the
    default since 1 Oct) the backing is shown and logged but never
    excludes a leg."""
    from analyst_sweep import match_picks_to_candidate, summarize_sources

    for leg in legs:
        game = leg.ctx.game_description
        if picks_by_game is None or game not in picks_by_game:
            leg.sources_note = skipped_reason.get(game, "analyst sweep didn't run")
            if as_gate:
                leg.gates.append(GateResult("sources", False, leg.sources_note))
            continue
        matched = match_picks_to_candidate(picks_by_game[game], leg.ctx.player, leg.ctx.market, leg.consensus_line)
        consensus = summarize_sources(matched)
        leg.sources_checked = True
        if as_gate:
            gate = sources_gate(consensus.n_over_sources)
            leg.sources_note = gate.reason
            leg.gates.append(gate)
        else:
            leg.sources_note = f"{consensus.n_over_sources} independent analyst(s) backing the over"
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


def _leg_record(leg: Leg, bet_builder_games: set[str] | None = None, filler: bool = False) -> dict:
    ctx = leg.ctx
    return {
        "key": f"{ctx.player}|{ctx.stat_col}",
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
        "recent": [round(v, 1) for v in ctx.recent_values],
        "bet_builder": bool(bet_builder_games and ctx.game in bet_builder_games),
        "gates": [{"gate": g.gate, "passed": g.passed, "reason": g.reason} for g in leg.gates],
        "flags": leg.flags,
        "sources": leg.sources,
        "sources_checked": leg.sources_checked,
        "sources_note": leg.sources_note,
        "filler": filler,
    }


def _log_row(leg: Leg, selected: bool, filler: bool) -> dict:
    return {
        "player_id": leg.ctx.player_id or None,
        "player_name": leg.ctx.player,
        "stat_col": leg.ctx.stat_col,
        "market": leg.ctx.market,
        "game": leg.ctx.game,
        "window": leg.ctx.window,
        "consensus_line": leg.consensus_line,
        "max_line": leg.max_line,
        "projection": leg.ctx.projection,
        "fair_prob": leg.fair_prob,
        "passed_gates": not leg.failed,
        "failed_gates": ",".join(g.gate for g in leg.failed) or None,
        "selected": selected,
        "filler": filler,
        "sources_checked": leg.sources_checked,
        "n_over_sources": len(leg.sources["over"]) if leg.sources_checked else None,
        "n_under_sources": len(leg.sources["under"]) if leg.sources_checked else None,
    }


def _games_by_count(legs: list[Leg]) -> list[str]:
    counts: dict[str, int] = {}
    for leg in legs:
        counts[leg.ctx.game_description] = counts.get(leg.ctx.game_description, 0) + 1
    return sorted(counts, key=lambda g: counts[g], reverse=True)


def _games_across_windows(legs: list[Leg]) -> list[str]:
    """Games ordered so the capped analyst sweep alternates between windows
    (busiest game of each window first), rather than spending the whole
    budget on the early games and leaving the late acca unchecked."""
    per_window = [_games_by_count([leg for leg in legs if leg.ctx.window == w]) for w in ACCA_WINDOWS]
    ordered = []
    for i in range(max((len(games) for games in per_window), default=0)):
        ordered += [games[i] for games in per_window if i < len(games)]
    return ordered


def _build(surviving: list[Leg]) -> list[Leg]:
    candidates, by_candidate = [], {}
    for leg in surviving:
        candidate = Candidate(
            player=leg.ctx.player, game=leg.ctx.game, market=leg.ctx.market, side="over",
            line=leg.max_line, price_decimal=1 / leg.fair_prob, fair_prob=leg.fair_prob,
            gates=leg.gates, score=leg.score,
        )
        candidates.append(candidate)
        by_candidate[id(candidate)] = leg
    return [by_candidate[id(c)] for c in build_accumulator(candidates).legs]


SPARES_PER_WINDOW = 10
# A leg that failed one of these is never a filler or spare: Market means
# there's no consensus line to set a bet365 target from, Odds means bet365
# won't realistically offer MIN_PRICE_DECIMAL on it.
NEVER_FILL_GATES = {"market", "odds"}


def _can_fill(leg: Leg) -> bool:
    return len(leg.failed) == 1 and leg.failed[0].gate not in NEVER_FILL_GATES


def select_window(window_legs: list[Leg]) -> tuple[list[Leg], list[Leg], list[Leg]]:
    """(legs that passed every gate, fillers, spares) for one window. Fillers top
    the acca up to MAX_LEGS from legs that failed exactly one gate, best
    projection margin first, still at most MAX_LEGS_PER_GAME per game and
    one leg per player. NEVER_FILL_GATES lists the failures that rule a leg
    out as a filler."""
    chosen = _build([leg for leg in window_legs if not leg.failed])
    fillers: list[Leg] = []
    if FILL_WITH_NEAR_MISSES and len(chosen) < MAX_LEGS:
        per_game = Counter(leg.ctx.game for leg in chosen)
        players = {leg.ctx.player for leg in chosen}
        pool = sorted(
            (leg for leg in window_legs if _can_fill(leg)),
            key=lambda leg: leg.score, reverse=True,
        )
        for leg in pool:
            if len(chosen) + len(fillers) >= MAX_LEGS:
                break
            if per_game[leg.ctx.game] >= MAX_LEGS_PER_GAME or leg.ctx.player in players:
                continue
            fillers.append(leg)
            per_game[leg.ctx.game] += 1
            players.add(leg.ctx.player)
    return chosen, fillers, _spares(window_legs, chosen + fillers)


def _spares(window_legs: list[Leg], used: list[Leg]) -> list[Leg]:
    """Replacements the page offers when a leg fails the bet365 check:
    unused legs that passed every gate first, then (when fillers are on)
    unused one-gate failures, best projection margin first. The page applies
    the per-game and per-player caps itself, since they depend on which legs
    are still in."""
    used_ids = {id(leg) for leg in used}
    rest = [leg for leg in window_legs if id(leg) not in used_ids]
    passing = sorted((leg for leg in rest if not leg.failed), key=lambda leg: leg.score, reverse=True)
    near = []
    if FILL_WITH_NEAR_MISSES:
        near = sorted(
            (leg for leg in rest if _can_fill(leg)),
            key=lambda leg: leg.score, reverse=True,
        )
    return (passing + near)[:SPARES_PER_WINDOW]


def _window_record(
    key: str, kickoff_uk: str, chosen: list[Leg], fillers: list[Leg], spares: list[Leg], n_window_legs: int,
) -> dict:
    legs = chosen + fillers
    per_game = Counter(leg.ctx.game for leg in legs)
    builder_games = {game for game, n in per_game.items() if n > 1}
    filler_ids = {id(leg) for leg in fillers}
    is_acca = len(legs) >= 3
    return {
        "window": key,
        "label": ACCA_WINDOWS[key]["label"],
        "kickoff_uk": kickoff_uk,
        "mode": "accumulator" if is_acca else "singles" if legs else "no_bet",
        "legs": [_leg_record(leg, builder_games, filler=id(leg) in filler_ids) for leg in legs],
        "spares": [_leg_record(leg, filler=bool(leg.failed)) for leg in spares],
        "n_passed": len(chosen),
        "n_fillers": len(fillers),
        "n_legs_in_window": n_window_legs,
        "combined_fair_odds": round(prod(1 / leg.fair_prob for leg in legs), 2) if is_acca else None,
        "combined_probability": round(prod(leg.fair_prob for leg in legs), 4) if is_acca else None,
    }


def build_acca_report(
    contexts: list[LegContext],
    per_book_rows: list[dict],
    week: int,
    season: int,
    sweep=None,
    api_key_present: bool | None = None,
    log_rows=None,
    window_kickoffs: dict[str, str] | None = None,
) -> dict:
    """One accumulator per window in config.ACCA_WINDOWS. sweep(game_descriptions,
    week, max_workers) -> ({game: picks}, usage) defaults to
    analyst_sweep.sweep_games; injected so tests never call the Claude API.
    log_rows(rows), if given, receives one row per evaluated leg for
    results_log.log_acca_legs. window_kickoffs: {window: "18:00"} in UK time."""
    as_gate = ANALYST_SWEEP["sources_gate"]
    window_kickoffs = window_kickoffs or {}
    consensus = consensus_by_prop(per_book_rows)
    bookmakers = sorted({r["bookmaker"] for r in per_book_rows if r.get("bookmaker")})
    # One context per prop: a second spelling of the same player in the feed
    # would otherwise become a duplicate leg (and a duplicate graded row).
    unique: dict[tuple, LegContext] = {}
    for ctx in contexts:
        unique.setdefault((ctx.event_id, ctx.market, ctx.player), ctx)
    legs = [
        evaluate_leg(ctx, consensus.get((ctx.event_id, ctx.market, name_key(ctx.odds_player_name))))
        for ctx in unique.values()
    ]
    in_window = [leg for leg in legs if leg.ctx.window in ACCA_WINDOWS]
    by_window = {w: [leg for leg in in_window if leg.ctx.window == w] for w in ACCA_WINDOWS}
    by_window = {w: window_legs for w, window_legs in by_window.items() if window_legs}
    surviving = [leg for leg in in_window if not leg.failed]

    # The sweep costs money and minutes per game, so it covers few games.
    # As a gate it goes where the most legs are still alive. As a signal the
    # accumulators don't depend on it, so it goes to the games of the legs
    # actually suggested first, then the other games with surviving legs.
    selections: dict[str, tuple[list[Leg], list[Leg]]] = {}
    if as_gate:
        ranked_games = _games_across_windows(surviving)
    else:
        selections = {w: select_window(window_legs) for w, window_legs in by_window.items()}
        suggested = [leg for chosen, fillers, _ in selections.values() for leg in chosen + fillers]
        ranked_games = list(dict.fromkeys(_games_across_windows(suggested) + _games_across_windows(surviving)))
    to_sweep = ranked_games[: ANALYST_SWEEP["max_games"]]
    skipped = {
        g: f"not checked: the analyst sweep is capped at {ANALYST_SWEEP['max_games']} games per run"
        for g in ranked_games[len(to_sweep):]
    }

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
        try:
            picks_by_game, usage = sweep(
                [f"{g}, NFL Week {week} {season}" for g in to_sweep], week, max_workers=ANALYST_SWEEP["max_workers"]
            )
        except Exception as exc:  # the accas mustn't depend on a paid web-search call succeeding
            logger.exception("Analyst sweep failed")
            sweep_info["note"] = f"the analyst sweep failed ({type(exc).__name__}), so no leg was checked"
        else:
            picks_by_game = {g.rsplit(", NFL Week", 1)[0]: picks for g, picks in picks_by_game.items()}
            sweep_info.update(ran=True, games=to_sweep, usage=usage)
    else:
        sweep_info["note"] = "no leg in either window survived the other gates, so there was nothing to sweep"
    if not sweep_info["ran"]:
        skipped.update({g: sweep_info["note"] for g in ranked_games})
    extra = [leg for _, fillers, spares in selections.values() for leg in fillers + spares if leg.failed]
    apply_sources(surviving + extra, picks_by_game, skipped, as_gate)

    if as_gate:
        selections = {w: select_window(window_legs) for w, window_legs in by_window.items()}

    selected_ids = {id(leg) for chosen, fillers, _ in selections.values() for leg in chosen + fillers}
    filler_ids = {id(leg) for _, fillers, _ in selections.values() for leg in fillers}
    if log_rows is not None:
        log_rows([_log_row(leg, id(leg) in selected_ids, id(leg) in filler_ids) for leg in legs])

    unused_failures = [leg for leg in in_window if leg.failed and id(leg) not in filler_ids]
    near_misses = sorted((leg for leg in unused_failures if len(leg.failed) == 1), key=lambda leg: leg.score, reverse=True)[:10]
    failure_counts: dict[str, int] = {}
    for leg in unused_failures:
        for gate in leg.failed:
            failure_counts[gate.gate] = failure_counts.get(gate.gate, 0) + 1

    return {
        "accumulators": [
            _window_record(w, window_kickoffs.get(w, ""), *selections[w], len(by_window[w])) for w in by_window
        ],
        "fill_with_near_misses": FILL_WITH_NEAR_MISSES,
        "sources_mode": "gate" if as_gate else "signal",
        "stake_gbp": STAKE_GBP,
        "n_candidates": len(in_window),
        "n_outside_windows": len(legs) - len(in_window),
        "near_misses": [_leg_record(leg) for leg in near_misses],
        "excluded": [
            {
                "player": leg.ctx.player,
                "stat_label": STAT_LABELS.get(leg.ctx.stat_col, leg.ctx.stat_col),
                "game": leg.ctx.game,
                "consensus_line": leg.consensus_line,
                "failed": [{"gate": g.gate, "reason": g.reason} for g in leg.failed],
            }
            for leg in sorted(unused_failures, key=lambda leg: (leg.ctx.player, leg.ctx.stat_col))
        ],
        "gate_failure_counts": dict(sorted(failure_counts.items(), key=lambda kv: kv[1], reverse=True)),
        "analyst_sweep": sweep_info,
        "bookmakers_seen": bookmakers,
        "bet365_in_feed": any("bet365" in b for b in bookmakers),
        "not_checked": NOT_CHECKED,
    }
