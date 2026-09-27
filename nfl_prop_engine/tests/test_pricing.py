import pytest

from pricing import (
    american_to_decimal,
    decimal_implied_probability,
    explain_value,
    fair_probability_avg,
    implied_probability,
    model_probability,
    no_vig_probability,
    no_vig_probability_decimal,
    us_consensus_line,
    value_pct,
)


def test_implied_probability_negative_price():
    # -110 is the classic "standard vig" price -> 110/210
    assert implied_probability(-110) == pytest.approx(110 / 210)


def test_implied_probability_positive_price():
    assert implied_probability(120) == pytest.approx(100 / 220)


def test_implied_probability_none_without_price():
    assert implied_probability(None) is None


def test_implied_probability_none_with_nan_price():
    # Real failure mode, not hypothetical: a pandas row.get() on a missing
    # column value returns float('nan'), not None -- `is None` alone would
    # let this through and eventually reach json.dump() as an invalid
    # `NaN` token, breaking the live site's fetch().json() entirely.
    assert implied_probability(float("nan")) is None


def test_no_vig_probability_normalizes_to_one():
    # Both sides at -110 (a symmetric, standard-vig market) -> no-vig prob
    # should land back at exactly 0.5, the vig cancels out.
    assert no_vig_probability(-110, -110) == pytest.approx(0.5)


def test_no_vig_probability_none_if_either_side_missing():
    assert no_vig_probability(-110, None) is None
    assert no_vig_probability(None, -110) is None


def test_no_vig_probability_none_if_either_side_nan():
    assert no_vig_probability(-110, float("nan")) is None
    assert no_vig_probability(float("nan"), -110) is None


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


# --- Decimal-odds helpers (Week 4 accumulator engine) -----------------------

def test_american_to_decimal_positive_and_negative():
    assert american_to_decimal(150) == pytest.approx(2.5)
    assert american_to_decimal(-110) == pytest.approx(1.9090909, rel=1e-4)


def test_american_to_decimal_none_with_missing_or_nan():
    assert american_to_decimal(None) is None
    assert american_to_decimal(float("nan")) is None


def test_decimal_implied_probability():
    assert decimal_implied_probability(2.0) == pytest.approx(0.5)
    assert decimal_implied_probability(1.5) == pytest.approx(2 / 3)


def test_no_vig_probability_decimal_symmetric_market():
    # Both sides at the same decimal price -> vig cancels, lands at 0.5
    assert no_vig_probability_decimal(1.9, 1.9) == pytest.approx(0.5)


def test_us_consensus_line_needs_at_least_two_books():
    assert us_consensus_line([214.5]) is None
    assert us_consensus_line([214.5, 210.5]) == pytest.approx(212.5)
    assert us_consensus_line([214.5, 210.5, 216.5]) == pytest.approx(214.5)


def test_us_consensus_line_ignores_missing_books():
    assert us_consensus_line([214.5, None, 210.5]) == pytest.approx(212.5)


def test_fair_probability_avg_averages_devigged_probabilities():
    # Two books, both symmetric (1.9/1.9) -> average is still 0.5
    avg = fair_probability_avg([(1.9, 1.9), (1.87, 1.95)])
    assert avg is not None
    assert 0.45 < avg < 0.55


def test_fair_probability_avg_none_without_any_complete_pair():
    assert fair_probability_avg([(1.9, None), (None, 1.9)]) is None
