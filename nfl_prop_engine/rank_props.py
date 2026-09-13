"""Step 6: rank matched player props by standard-deviation-scaled edge."""
from dataclasses import dataclass

from projection_engine import Projection


@dataclass
class RankedProp:
    player_id: str
    player_name: str
    stat_col: str
    line: float
    projection: float
    edge_score: float
    direction: str  # "over" | "under"
    hit_rate: float | None
    sample_size: int
    method: str
    confidence: str


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


def build_ranked_prop(proj: Projection, line: float, current_season_values: list[float]) -> RankedProp:
    if proj.season_std and proj.season_std > 0:
        edge_score = (proj.projection - line) / proj.season_std
    else:
        edge_score = 0.0  # shouldn't happen given the league-wide std fallback, but never divide by zero

    direction = "over" if proj.projection >= line else "under"
    hit_rate, sample_size = compute_hit_rate(current_season_values, line, direction)

    return RankedProp(
        player_id=proj.player_id, player_name=proj.player_name, stat_col=proj.stat_col,
        line=line, projection=proj.projection, edge_score=edge_score, direction=direction,
        hit_rate=hit_rate, sample_size=sample_size,
        method=proj.method, confidence=proj.confidence,
    )


def rank(props: list[RankedProp]) -> list[RankedProp]:
    return sorted(props, key=lambda p: abs(p.edge_score), reverse=True)
