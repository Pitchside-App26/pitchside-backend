import pytest

from projection_engine import Projection
from rank_props import build_ranked_prop, compute_hit_rate, rank


def _proj(projection, std=10.0, method="veteran", confidence="normal"):
    return Projection(
        player_id="p1", player_name="Test Player", stat_col="yards",
        projection=projection, season_std=std, n_current_games=5, n_prior_games=0,
        method=method, confidence=confidence,
    )


def test_edge_score_scales_by_std():
    ranked = build_ranked_prop(_proj(80.0, std=10.0), line=70.0, current_season_values=[60, 70, 80, 90, 100])
    assert ranked.edge_score == pytest.approx(1.0)
    assert ranked.direction == "over"


def test_hit_rate_excludes_pushes():
    hit_rate, n = compute_hit_rate([50, 50, 60, 40], line=50.0, direction="over")
    assert n == 2  # the two 50s are pushes, excluded
    assert hit_rate == pytest.approx(0.5)


def test_rank_orders_by_absolute_edge_descending():
    small = build_ranked_prop(_proj(51.0, std=10.0), line=50.0, current_season_values=[])
    large_negative = build_ranked_prop(_proj(20.0, std=10.0), line=50.0, current_season_values=[])
    ranked = rank([small, large_negative])
    assert ranked[0] is large_negative
    assert ranked[1] is small
