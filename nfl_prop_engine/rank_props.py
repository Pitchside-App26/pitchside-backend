"""Step 6: rank matched player props by standard-deviation-scaled edge."""
from dataclasses import dataclass

from explain import explain_projection
from pricing import explain_value, model_probability, no_vig_probability, value_pct
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

    return RankedProp(
        player_id=proj.player_id, player_name=proj.player_name,
        team=team, opponent=opponent, kickoff=kickoff,
        stat_col=proj.stat_col,
        line=line, projection=proj.projection, edge_score=edge_score, direction=direction,
        hit_rate=hit_rate, sample_size=sample_size,
        method=proj.method, confidence=proj.confidence,
        explanation=explanation,
        price=price, market_prob=market_prob, model_prob=model_prob, value_pct=val_pct,
    )


def rank(props: list[RankedProp]) -> list[RankedProp]:
    # value_pct (model probability vs. the market's own no-vig price) is
    # what actually answers "is this worth betting" -- prefer it over
    # edge_score (distance from the line alone) whenever price data is
    # available. Falls back to edge_score for props missing a price (e.g.
    # a backtest run over old data that never had one).
    return sorted(
        props,
        key=lambda p: abs(p.value_pct) if p.value_pct is not None else abs(p.edge_score),
        reverse=True,
    )
