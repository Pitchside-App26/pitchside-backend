"""Converts American odds prices and the projection engine's edge_score
into probability terms, so a prop can be judged by whether it's actually a
good BET, not just how far the projection sits from the line -- the gap
flagged after grading real week 1 results: edge_pct only ever measured
distance from the number, never the price on that side, so a huge edge at
a terrible price and a small edge at a great price looked identical.

Two probabilities that are NOT the same thing:
  - market_implied_prob (no-vig): what the book's own two-sided price
    says, with the house's built-in edge normalized out.
  - model_prob: this engine's own estimate, derived from edge_score via a
    normal-distribution approximation. Real stat distributions aren't
    perfectly normal (especially low-count ones like sacks or INTs) --
    this is a starting point to grade against, like every other weight in
    this engine, not a validated model.
"""
import math


def _missing(v: float | None) -> bool:
    """True for None AND for NaN -- values here often arrive straight from
    a pandas Series (run_weekly.py's row.get("over_price")/"under_price"),
    where a value that was never set comes back as float NaN, not None.
    `v is None` alone lets NaN sail through every arithmetic step below
    and come out the other end as a JSON `NaN` literal, which is not valid
    JSON and breaks the site's fetch() with a parse error -- confirmed
    live: exactly this happened the first time a prop had only one side's
    price recorded.
    """
    return v is None or (isinstance(v, float) and math.isnan(v))


def implied_probability(american_price: float | None) -> float | None:
    """Straight conversion, vig included -- NOT a fair/no-vig probability.
    A two-way market's two implied probabilities sum to slightly over 100%
    because of the book's edge; removing that needs both sides' prices,
    see no_vig_probability below."""
    if _missing(american_price):
        return None
    if american_price > 0:
        return 100.0 / (american_price + 100.0)
    return -american_price / (-american_price + 100.0)


def no_vig_probability(picked_side_price: float | None, other_side_price: float | None) -> float | None:
    """Removes the vig by normalizing both sides' implied probabilities so
    they sum to exactly 100% -- the standard, simple de-vig method (not a
    more sophisticated model). None if either side's price is missing --
    never estimate one side from the other."""
    p_picked = implied_probability(picked_side_price)
    p_other = implied_probability(other_side_price)
    if p_picked is None or p_other is None:
        return None
    total = p_picked + p_other
    if not total:
        return None
    return p_picked / total


def model_probability(edge_score: float | None) -> float | None:
    """Approximates P(the picked side hits) from edge_score under a
    normal-distribution assumption -- edge_score is already
    (projection-line)/season_std, i.e. how many standard deviations the
    picked side clears the line by, so this is just its standard normal
    CDF. Unvalidated like every other weight in this engine."""
    if _missing(edge_score):
        return None
    z = abs(edge_score)
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def value_pct(model_prob: float | None, market_prob: float | None) -> float | None:
    """model_prob minus the market's no-vig probability, in percentage
    points -- positive means the model thinks the picked side is MORE
    likely to hit than the price implies. This is the number that actually
    answers "is this worth betting", which edge_pct alone never could."""
    if _missing(model_prob) or _missing(market_prob):
        return None
    return (model_prob - market_prob) * 100


def explain_value(price: float | None, market_prob: float | None, model_prob: float | None) -> str:
    """A plain-English sentence for the "why" text -- separate from
    explain.py's explain_projection() because price/value are market facts
    known only once build_ranked_prop() has a price to work with, not
    anything the projection engine itself computed."""
    if _missing(price) or _missing(market_prob) or _missing(model_prob):
        return ""
    gap = (model_prob - market_prob) * 100
    verdict = "looks like real value" if gap >= 3 else "looks about fairly priced" if gap >= -3 else "looks worse than the price suggests"
    return (
        f"At {price:+.0f}, the market's own no-vig price implies a {market_prob * 100:.0f}% "
        f"chance -- this projection implies about {model_prob * 100:.0f}%, which {verdict} "
        f"({gap:+.1f}pt gap)."
    )
