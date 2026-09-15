import pytest

from pricing import explain_value, implied_probability, model_probability, no_vig_probability, value_pct


def test_implied_probability_negative_price():
    # -110 is the classic "standard vig" price -> 110/210
    assert implied_probability(-110) == pytest.approx(110 / 210)


def test_implied_probability_positive_price():
    assert implied_probability(120) == pytest.approx(100 / 220)


def test_implied_probability_none_without_price():
    assert implied_probability(None) is None


def test_no_vig_probability_normalizes_to_one():
    # Both sides at -110 (a symmetric, standard-vig market) -> no-vig prob
    # should land back at exactly 0.5, the vig cancels out.
    assert no_vig_probability(-110, -110) == pytest.approx(0.5)


def test_no_vig_probability_none_if_either_side_missing():
    assert no_vig_probability(-110, None) is None
    assert no_vig_probability(None, -110) is None


def test_model_probability_zero_edge_is_fifty_percent():
    assert model_probability(0.0) == pytest.approx(0.5)


def test_model_probability_increases_with_edge_magnitude():
    assert model_probability(1.0) > model_probability(0.5) > model_probability(0.0)


def test_model_probability_symmetric_for_negative_edge():
    # edge_score's sign just reflects direction (over vs under) -- the
    # model's confidence in whichever side it picked only depends on
    # magnitude.
    assert model_probability(-1.0) == model_probability(1.0)


def test_model_probability_none_without_edge():
    assert model_probability(None) is None


def test_value_pct_positive_when_model_more_confident_than_market():
    assert value_pct(model_prob=0.60, market_prob=0.50) == pytest.approx(10.0)


def test_value_pct_none_with_missing_input():
    assert value_pct(None, 0.5) is None
    assert value_pct(0.5, None) is None


def test_explain_value_empty_without_full_price_data():
    assert explain_value(None, 0.5, 0.6) == ""
    assert explain_value(-110, None, 0.6) == ""


def test_explain_value_mentions_price_and_both_probabilities():
    text = explain_value(-110, market_prob=0.50, model_prob=0.60)
    assert "-110" in text
    assert "50%" in text
    assert "60%" in text
