"""Step 6: rank matched player props by standard-deviation-scaled edge."""
from dataclasses import dataclass

from explain import explain_projection
from pricing import _missing, explain_value, model_probability, no_vig_probability, value_pct
from projection_engine import Projection


@dataclass
class RankedProp:
    player_id: str
    player_name: str
    team: str
    opponent: str
    kickoff: str  # display string, e.g. "Sun 1:00 ET"
    stat_col: str
    line: float
    projection: float
    edge_score: float
    direction: str  # "over" | "under"
    hit_rate: float | None
    sample_size: int
    method: str
    confidence: str
    explanation: str = ""

    # Price -- see pricing.py. price is the picked side's American odds;
    # market_prob is the no-vig implied probability from BOTH sides'
    # prices; model_prob is this engine's own estimate from edge_score;
    # value_pct is the gap between them, in percentage points.
    price: float | None = None
    market_prob: float | None = None
    model_prob: float | None = None
    value_pct: float | None = None

    # "Questionable" | "Doubtful" | None -- see fetch_injuries.py. "Out"
    # players never reach here at all: run_weekly.py excludes them before
    # calling build_ranked_prop, since a prop for someone who isn't going
    # to play isn't a real recommendation.
    injury_status: str | None = None

    # Average targets/game this season so far (receiving props only) --
    # informational context from NGS data, not a projection input. See
    # fetch_stats.fetch_receiving_usage.
    avg_targets: float | None = None

    # Both sides' American prices at `line` and the book they came from, so
    # graded results can be judged on profit at the price, not just hit rate.
    over_price: float | None = None
    under_price: float | None = None
    bookmaker: str | None = None


def compute_hit_rate(current_values: list[float], line: float, direction: str) -> tuple[float | None, int]:
    """Fraction of this player's own games this season that would have
    cleared the given side of the line. Ties (value == line) count as
    neither a hit nor a miss, matching how a real push works."""
    if not current_values:
        return None, 0
    decisive = [v for v in current_values if v != line]
    if not decisive:
        return None, 0
    if direction == "over":
        hits = sum(1 for v in decisive if v > line)
    else:
        hits = sum(1 for v in decisive if v < line)
    return hits / len(decisive), len(decisive)


def build_ranked_prop(
    proj: Projection, line: float, current_season_values: list[float],
    team: str = "", opponent: str = "", kickoff: str = "",
    over_price: float | None = None, under_price: float | None = None,
    injury_status: str | None = None, avg_targets: float | None = None, bookmaker: str | None = None,
) -> RankedProp:
    if proj.season_std and proj.season_std > 0:
        edge_score = (proj.projection - line) / proj.season_std
    else:
        edge_score = 0.0  # shouldn't happen given the league-wide std fallback, but never divide by zero

    direction = "over" if proj.projection >= line else "under"
    hit_rate, sample_size = compute_hit_rate(current_season_values, line, direction)

    price = over_price if direction == "over" else under_price
    other_price = under_price if direction == "over" else over_price
    market_prob = no_vig_probability(price, other_price)
    model_prob = model_probability(edge_score)
    val_pct = value_pct(model_prob, market_prob)

    explanation = explain_projection(proj)
    value_sentence = explain_value(price, market_prob, model_prob)
    if value_sentence:
        explanation = f"{explanation} {value_sentence}"
    if injury_status:
        explanation = (
            f"{explanation} Listed {injury_status} on this week's injury report -- "
            f"treat this number with extra caution."
        )
    if avg_targets is not None:
        explanation = f"{explanation} Averaging {avg_targets:.1f} targets/game this season."

    return RankedProp(
        player_id=proj.player_id, player_name=proj.player_name,
        team=team, opponent=opponent, kickoff=kickoff,
        stat_col=proj.stat_col,
        line=line, projection=proj.projection, edge_score=edge_score, direction=direction,
        hit_rate=hit_rate, sample_size=sample_size,
        method=proj.method, confidence=proj.confidence,
        explanation=explanation,
        price=price, market_prob=market_prob, model_prob=model_prob, value_pct=val_pct,
        injury_status=injury_status, avg_targets=avg_targets,
        over_price=None if _missing(over_price) else float(over_price),
        under_price=None if _missing(under_price) else float(under_price),
        bookmaker=bookmaker or None,
    )


def rank(props: list[RankedProp]) -> list[RankedProp]:
    # value_pct (model probability vs. the market's own no-vig price) is
    # what actually answers "is this worth betting". Best value first,
    # signed: ranking by its size alone put the worst-priced bets (big
    # negative value) next to the best. Props with no price follow, by
    # standardised edge (e.g. a backtest over data that never had prices).
    priced = sorted((p for p in props if p.value_pct is not None), key=lambda p: p.value_pct, reverse=True)
    unpriced = sorted((p for p in props if p.value_pct is None), key=lambda p: abs(p.edge_score), reverse=True)
    return priced + unpriced
