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


def test_build_ranked_prop_computes_price_fields_when_price_available():
    ranked = build_ranked_prop(
        _proj(80.0, std=10.0), line=70.0, current_season_values=[],
        over_price=-115, under_price=-105,
    )
    assert ranked.price == -115  # picked "over" (80 >= 70), so over's price
    assert ranked.market_prob is not None
    assert ranked.model_prob is not None
    assert ranked.value_pct is not None
    assert "market" in ranked.explanation.lower() or "-115" in ranked.explanation


def test_rank_prefers_value_pct_over_edge_score_when_available():
    # Small edge_score (0.1) but the market's own no-vig price says this
    # side is only a ~29% shot while the model says ~54% -- a real value
    # gap that plain distance-from-the-line would never surface. Should
    # outrank a bigger edge_score (4.0) with no price data at all.
    big_edge_no_price = build_ranked_prop(_proj(90.0, std=10.0), line=50.0, current_season_values=[])
    small_edge_big_value = build_ranked_prop(
        _proj(51.0, std=10.0), line=50.0, current_season_values=[],
        over_price=200, under_price=-400,
    )
    assert small_edge_big_value.value_pct is not None
    assert abs(small_edge_big_value.value_pct) > abs(big_edge_no_price.edge_score)
    ranked = rank([big_edge_no_price, small_edge_big_value])
    assert ranked[0] is small_edge_big_value
