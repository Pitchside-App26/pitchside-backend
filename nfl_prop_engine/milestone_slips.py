"""Fun slips: one six-fold per Sunday window, built to land about 1 time in
FUN_SLIPS["target_odds"] and to go close most weeks.

Main-line props are coin flips, so a six-fold of them lands about 1 time in
64. Here every leg is a milestone ("5+ receptions", i.e. over 4.5) set
below the main line, so its chance is about (1/20)^(1/6) = 61%.

The chance of a milestone comes from what actually happened to every prop
graded so far, anchored on the market: how far above or below its line each
stat lands (actual / line, split into small and big lines), shifted so that
the main line sits where the US books' fair price puts it. Tested on weeks
it wasn't built from: legs aimed at 61% hit 63.7%, and random six-folds of
them predicted at 1 in 19 landed 1 in 15. The model's own projection plays
no part: its picks lost 4.2% at real prices.

No edge is claimed. The legs are chosen to be likely, not to be value.
"""
import logging
import math
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
import pandas as pd

from acca_report import LegContext, consensus_by_prop, name_key
from config import ACCA_WINDOWS, FUN_SLIPS, STAKE_GBP, STAT_LABELS
from participation import Role

logger = logging.getLogger(__name__)

UNITS = {
    "passing_yards": "pass yds", "completions": "completions", "carries": "carries", "receptions": "receptions",
    "receiving_yards": "rec yds", "def_tackles": "tackles", "rushing_yards": "rush yds",
}
SKIP_INJURY = {"Out", "Doubtful", "Questionable"}


def per_leg_target(target_odds: float = FUN_SLIPS["target_odds"], legs: int = FUN_SLIPS["legs"]) -> float:
    return (1 / target_odds) ** (1 / legs)


@dataclass
class ChanceModel:
    """actual / line for every graded prop, per stat and line size."""
    ratios: dict[tuple[str, bool], np.ndarray]
    medians: dict[str, float]

    @classmethod
    def from_graded(cls, graded: pd.DataFrame, stats=FUN_SLIPS["stats"],
                    min_rows: int = FUN_SLIPS["min_graded_props"]) -> "ChanceModel":
        graded = graded[graded["actual_value"].notna() & (graded["line"] > 0) & graded["stat_col"].isin(stats)]
        ratios, medians = {}, {}
        for stat, rows in graded.groupby("stat_col"):
            if len(rows) < min_rows:
                continue
            medians[stat] = float(rows["line"].median())
            r = rows["actual_value"] / rows["line"]
            for big in (False, True):
                ratios[(stat, big)] = np.sort(r[(rows["line"] >= medians[stat]) == big].to_numpy())
        return cls(ratios, medians)

    def covers(self, stat: str) -> bool:
        return stat in self.medians

    def chance(self, stat: str, line: float, over_prob: float, threshold: float) -> float:
        """Chance he gets to `threshold` or more, given the main line and the
        books' fair chance of the over at it. "5+" is "over 4.5", so the
        comparison is against threshold - 0.5: comparing against 5 itself
        understated count milestones by up to 10 points on held-out weeks."""
        ratios = self.ratios[(stat, line >= self.medians[stat])]
        anchor = float(np.quantile(ratios, 1 - over_prob))  # where the line sits if the books are right
        scale = 1 / anchor if anchor > 0 else 1.0
        scaled, cut = ratios * scale, (threshold - 0.5) / line
        # Whole-number stats tie on the cut; half of a tie counts each way,
        # or a main line priced at 50% would come out at 43%.
        return float(np.mean(scaled > cut) + 0.5 * np.mean(np.isclose(scaled, cut)))


def _step(stat: str) -> int:
    return FUN_SLIPS["yard_steps"].get(stat, 1)


def milestones(stat: str, line: float) -> list[int]:
    """Bettable 'X+' thresholds at or below the main line, lowest first."""
    step = _step(stat)
    top = math.ceil(line)  # over 4.5 == 5+
    return [m for m in range(step, top + 1, step)]


def _label(stat: str, threshold: int) -> str:
    return f"{threshold}+ {UNITS.get(stat, STAT_LABELS.get(stat, stat))}"


def _fraction(decimal_odds: float) -> str:
    frac = Fraction(decimal_odds - 1).limit_denominator(20)
    return "evens" if frac == 1 else f"{frac.numerator}/{frac.denominator}"


@dataclass
class Candidate:
    ctx: LegContext
    line: float
    over_prob: float
    snap_pct: float
    options: list[tuple[int, float]]  # (threshold, chance), lowest threshold first
    pick: int = 0  # index into options

    @property
    def threshold(self) -> int:
        return self.options[self.pick][0]

    @property
    def chance(self) -> float:
        return self.options[self.pick][1]

    def record(self) -> dict:
        ctx = self.ctx
        around = self.options[max(0, self.pick - 2): self.pick + 3]
        return {
            "player": ctx.player, "player_id": ctx.player_id, "team": ctx.team, "opponent": ctx.opponent,
            "game": ctx.game, "kickoff": ctx.kickoff, "stat": ctx.stat_col,
            "stat_label": STAT_LABELS.get(ctx.stat_col, ctx.stat_col),
            "threshold": self.threshold, "label": _label(ctx.stat_col, self.threshold),
            "over_line": self.threshold - 0.5, "chance": round(self.chance, 3),
            "fair_odds": round(1 / self.chance, 2), "fair_fraction": _fraction(1 / self.chance),
            "main_line": self.line, "main_over_chance": round(self.over_prob, 3),
            "snap_pct": round(self.snap_pct, 2),
            "alternatives": [{"threshold": m, "label": _label(ctx.stat_col, m), "chance": round(p, 3)} for m, p in around],
        }


@dataclass
class Exclusions:
    counts: dict[str, int] = field(default_factory=dict)

    def add(self, reason: str) -> None:
        self.counts[reason] = self.counts.get(reason, 0) + 1


def candidates_for(
    contexts: list[LegContext], consensus: dict, model: ChanceModel, role_of, excluded: Exclusions,
    target: float = None,
) -> list[Candidate]:
    """Every window prop that can be a leg, with its milestone nearest the
    per-leg target. role_of(ctx) -> Role | None."""
    target = target or per_leg_target()
    low, high = FUN_SLIPS["leg_chance_window"]
    # A quarterback's carries swing with scrambles and kneels (Bo Nix "4+
    # carries" made both week 4 and 5 replays); carries legs are for backs.
    quarterbacks = {ctx.player for ctx in contexts if ctx.stat_col in ("passing_yards", "completions")}
    found = []
    for ctx in contexts:
        if ctx.window not in ACCA_WINDOWS:
            continue
        if ctx.stat_col not in FUN_SLIPS["stats"] or not model.covers(ctx.stat_col):
            excluded.add("not a milestone market")
            continue
        if ctx.stat_col == "carries" and ctx.player in quarterbacks:
            excluded.add("quarterback carries")
            continue
        market = consensus.get((ctx.event_id, ctx.market, name_key(ctx.odds_player_name)))
        if (not market or pd.isna(market["line"]) or pd.isna(market["fair_prob"]) or market["n_books"] < 2
                or market["line"] <= 0):
            excluded.add("too few books")
            continue
        if ctx.injury_status in SKIP_INJURY:
            excluded.add("injury report")
            continue
        role: Role | None = role_of(ctx)
        floor = FUN_SLIPS["min_snap_pct_carries"] if ctx.stat_col == "carries" else FUN_SLIPS["min_snap_pct"]
        if role is None or role.last_pct < floor:
            excluded.add("part-time role")
            continue
        if role.swing > FUN_SLIPS["max_snap_swing"]:
            excluded.add("role just changed")
            continue
        line, over_prob = float(market["line"]), float(market["fair_prob"])
        options = [(m, model.chance(ctx.stat_col, line, over_prob, m)) for m in milestones(ctx.stat_col, line)]
        if not options:
            continue
        pick = min(range(len(options)), key=lambda i: abs(options[i][1] - target))
        if not low <= options[pick][1] <= high:
            excluded.add("no milestone near the target chance")
            continue
        found.append(Candidate(ctx, line, over_prob, role.last_pct, options, pick))
    # Closest to the target chance first (steadier role on a tie). Sorting
    # by role first filled the slips with quarterbacks (always 100% of snaps).
    found.sort(key=lambda c: (round(abs(c.chance - target), 2), -c.snap_pct, c.ctx.player))
    return found


def _choose(pool: list[Candidate], legs: int) -> list[Candidate]:
    chosen: list[Candidate] = []
    for max_per_game in (FUN_SLIPS["max_per_game"], 2):
        for cand in pool:
            if len(chosen) == legs:
                return chosen
            if any(c.ctx.player == cand.ctx.player for c in chosen):
                continue
            if sum(c.ctx.game == cand.ctx.game for c in chosen) >= max_per_game:
                continue
            if sum(c.ctx.stat_col == cand.ctx.stat_col for c in chosen) >= FUN_SLIPS["max_per_stat"]:
                continue
            chosen.append(cand)
    return chosen


def _tune(legs: list[Candidate], target_odds: float) -> None:
    """Moves single legs one milestone up or down while that brings the
    slip's chance closer to 1 in target_odds."""
    low, high = FUN_SLIPS["leg_chance_window"]
    goal = math.log(1 / target_odds)
    for _ in range(len(legs) * 2):
        current = sum(math.log(c.chance) for c in legs)
        best = None
        for c in legs:
            for move in (-1, 1):
                i = c.pick + move
                if not 0 <= i < len(c.options) or not low <= c.options[i][1] <= high:
                    continue
                new = current - math.log(c.chance) + math.log(c.options[i][1])
                if abs(new - goal) < abs(current - goal) and (best is None or abs(new - goal) < best[0]):
                    best = (abs(new - goal), c, i)
        if best is None:
            return
        best[1].pick = best[2]


def build_slips(
    contexts: list[LegContext], per_book_rows: list[dict], model: ChanceModel, role_of,
    window_kickoffs: dict[str, str] | None = None, log_rows=None,
) -> dict:
    """{"slips": [one per window], ...} for data.json. log_rows(rows), if
    given, receives every leg and spare for results_log.log_slip_legs."""
    target_odds, legs_per_slip = FUN_SLIPS["target_odds"], FUN_SLIPS["legs"]
    consensus = consensus_by_prop(per_book_rows)
    unique: dict[tuple, LegContext] = {}
    for ctx in contexts:
        unique.setdefault((ctx.event_id, ctx.market, ctx.player), ctx)
    excluded = Exclusions()
    pool = candidates_for(list(unique.values()), consensus, model, role_of, excluded)

    slips, log = [], []
    for window, spec in ACCA_WINDOWS.items():
        window_pool = [c for c in pool if c.ctx.window == window]
        if not window_pool:
            continue
        legs = _choose(window_pool, legs_per_slip)
        _tune(legs, target_odds)
        spares = [c for c in window_pool if all(c is not leg for leg in legs)][: FUN_SLIPS["spares"]]
        chance = math.prod(c.chance for c in legs) if legs else 0.0
        slips.append({
            "window": window, "label": spec["label"], "kickoff_uk": (window_kickoffs or {}).get(window, ""),
            "legs": [c.record() for c in legs], "spares": [c.record() for c in spares],
            "chance": round(chance, 4), "one_in": round(1 / chance) if chance else None,
            "fair_odds": round(1 / chance, 2) if chance else None,
            "fair_return": round(STAKE_GBP / chance, 2) if chance else None,
            "n_candidates": len(window_pool), "complete": len(legs) == legs_per_slip,
        })
        for role, group in (("leg", legs), ("spare", spares)):
            log += [{"window": window, "player_id": c.ctx.player_id, "player_name": c.ctx.player,
                     "stat_col": c.ctx.stat_col, "threshold": c.threshold, "main_line": c.line,
                     "over_prob": c.over_prob, "chance": c.chance, "role": role} for c in group]
    if log_rows is not None and log:
        log_rows(log)
    return {
        "target_odds": target_odds, "legs_per_slip": legs_per_slip, "stake": STAKE_GBP,
        "per_leg_target": round(per_leg_target(), 3), "slips": slips, "excluded": excluded.counts,
    }
