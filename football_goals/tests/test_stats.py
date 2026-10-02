"""Hand-made datasets: every expected number below was worked out by hand."""
import pytest

from football_goals.stats import (fixture_markets, is_goal_in_both_halves, is_over_1_5,
                                  league_rates, team_stats)


def m(home, away, ft, ht):
    return {"home": home, "away": away, "fthg": ft[0], "ftag": ft[1], "hthg": ht[0], "htag": ht[1]}


NIL_NIL = m("A", "B", (0, 0), (0, 0))
ONE_ONE_SPLIT = m("A", "C", (1, 1), (1, 0))      # home scores 1st half, away 2nd half
TWO_NIL_SAME_HALF = m("B", "A", (2, 0), (2, 0))  # both goals before the break
TWO_NIL_SECOND_HALF = m("C", "B", (2, 0), (0, 0))


def test_nil_nil():
    assert not is_over_1_5(NIL_NIL)
    assert not is_goal_in_both_halves(NIL_NIL)


def test_one_one_goal_in_each_half():
    assert is_over_1_5(ONE_ONE_SPLIT)
    assert is_goal_in_both_halves(ONE_ONE_SPLIT)


def test_one_one_both_goals_first_half_is_not_gibh():
    assert not is_goal_in_both_halves(m("A", "B", (1, 1), (1, 1)))


def test_two_nil_same_half():
    assert is_over_1_5(TWO_NIL_SAME_HALF)
    assert not is_goal_in_both_halves(TWO_NIL_SAME_HALF)
    assert not is_goal_in_both_halves(TWO_NIL_SECOND_HALF)


def test_single_goal_is_under():
    assert not is_over_1_5(m("A", "B", (1, 0), (0, 0)))


def test_bad_half_time_score_is_rejected():
    with pytest.raises(ValueError):
        is_goal_in_both_halves(m("A", "B", (1, 0), (2, 0)))


RESULTS = [NIL_NIL, ONE_ONE_SPLIT, TWO_NIL_SAME_HALF, TWO_NIL_SECOND_HALF]


def test_team_counts_and_venue_splits():
    ts = team_stats(RESULTS)
    a = ts["A"]  # 0-0 (H), 1-1 split (H), 2-0 same half (A)
    assert (a.all.gp, a.all.o15, a.all.gibh) == (3, 2, 1)
    assert (a.home.gp, a.home.o15, a.home.gibh) == (2, 1, 1)
    assert (a.away.gp, a.away.o15, a.away.gibh) == (1, 1, 0)
    b = ts["B"]  # 0-0 (A), 2-0 same half (H), 2-0 second half (A)
    assert (b.all.gp, b.all.o15, b.all.gibh) == (3, 2, 0)
    assert (b.home.gp, b.away.gp) == (1, 2)
    assert a.all.pct("o15") == pytest.approx(2 / 3)


def test_league_rate():
    lr = league_rates(RESULTS)
    assert (lr.gp, lr.o15, lr.gibh) == (4, 3, 1)


def test_fixture_combined_and_venue_split():
    ts = team_stats(RESULTS)
    # A (home) v B (away)
    o = fixture_markets(ts["A"], ts["B"], "o15", min_games=6)
    assert o["combined_pct"] == pytest.approx((2 / 3 + 2 / 3) / 2)
    # A at home: 1/2 over; B away: 1/2 over (0-0, 2-0)
    assert o["venue_pct"] == pytest.approx(0.5)
    assert len(o["flags"]) == 2  # both teams under 6 games
    g = fixture_markets(ts["A"], ts["B"], "gibh", min_games=3)
    assert g["combined_pct"] == pytest.approx((1 / 3 + 0) / 2)
    assert g["flags"] == []


def test_fixture_with_unknown_team():
    ts = team_stats(RESULTS)
    o = fixture_markets(ts["A"], None, "o15", min_games=1)
    assert o["combined_pct"] is None
    assert o["flags"] == ["away team has no games"]


def test_goals_for_and_against():
    ts = team_stats(RESULTS)
    # A: 0-0 home, 1-1 home, lost 2-0 away -> scored 1, conceded 3
    assert (ts["A"].gf, ts["A"].ga) == (1, 3)
    # B: 0-0 away, won 2-0 home, lost 2-0 away -> scored 2, conceded 2
    assert (ts["B"].gf, ts["B"].ga) == (2, 2)
