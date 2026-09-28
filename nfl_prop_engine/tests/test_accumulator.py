from accumulator import Candidate, build_accumulator, filter_by_side
from leg_gates import GateResult


def _candidate(player, game, fair_prob=0.6, price=1.9, passed=True, market="player_pass_yds", side="over"):
    gates = [GateResult("line", passed, "test")]
    return Candidate(player=player, game=game, market=market, side=side, line=50.0, price_decimal=price, fair_prob=fair_prob, gates=gates)


def test_never_pads_below_max_legs():
    # 4 pass, 3 fail -- should build a 4-fold, never padding with a failed leg
    candidates = [
        _candidate("A", "G1", passed=True),
        _candidate("B", "G2", passed=True),
        _candidate("C", "G3", passed=True),
        _candidate("D", "G4", passed=True),
        _candidate("E", "G5", passed=False),
        _candidate("F", "G6", passed=False),
        _candidate("G", "G7", passed=False),
    ]
    result = build_accumulator(candidates)
    assert result.mode == "accumulator"
    assert len(result.legs) == 4
    assert all(c.player in ("A", "B", "C", "D") for c in result.legs)


def test_never_exceeds_max_legs_even_with_more_passing():
    candidates = [_candidate(f"P{i}", f"G{i}") for i in range(10)]
    result = build_accumulator(candidates, max_legs=6)
    assert len(result.legs) == 6


def test_fewer_than_three_passing_gives_singles():
    candidates = [_candidate("A", "G1"), _candidate("B", "G2")]
    result = build_accumulator(candidates)
    assert result.mode == "singles"
    assert len(result.legs) == 2
    assert result.combined_odds is None


def test_zero_passing_gives_no_bet():
    candidates = [_candidate("A", "G1", passed=False), _candidate("B", "G2", passed=False)]
    result = build_accumulator(candidates)
    assert result.mode == "no_bet"
    assert result.legs == []


def test_max_legs_per_game_cap():
    # 3 legs on the same game -- only 2 should make it in, best 2 by fair_prob
    candidates = [
        _candidate("A", "G1", fair_prob=0.7),
        _candidate("B", "G1", fair_prob=0.6),
        _candidate("C", "G1", fair_prob=0.5),
        _candidate("D", "G2", fair_prob=0.65),
    ]
    result = build_accumulator(candidates, max_legs=6, max_legs_per_game=2)
    g1_legs = [c for c in result.legs if c.game == "G1"]
    assert len(g1_legs) == 2
    assert {c.player for c in g1_legs} == {"A", "B"}  # C (lowest fair_prob) dropped


def test_bet_builder_group_tagged_for_same_game_pair():
    candidates = [
        _candidate("A", "G1", fair_prob=0.7),
        _candidate("B", "G1", fair_prob=0.6),
        _candidate("C", "G2", fair_prob=0.65),
        _candidate("D", "G3", fair_prob=0.55),
    ]
    result = build_accumulator(candidates)
    assert "G1" in result.bet_builder_groups
    assert len(result.bet_builder_groups["G1"]) == 2
    assert "G2" not in result.bet_builder_groups


def test_combined_odds_and_probability_are_products():
    candidates = [
        _candidate("A", "G1", fair_prob=0.6, price=1.9),
        _candidate("B", "G2", fair_prob=0.55, price=1.8),
        _candidate("C", "G3", fair_prob=0.65, price=2.0),
    ]
    result = build_accumulator(candidates)
    assert result.combined_odds is not None
    assert abs(result.combined_odds - (1.9 * 1.8 * 2.0)) < 1e-9
    assert abs(result.combined_probability - (0.6 * 0.55 * 0.65)) < 1e-9


def test_stake_never_escalates_and_is_flat_from_config():
    candidates = [_candidate(f"P{i}", f"G{i}") for i in range(3)]
    result = build_accumulator(candidates, stake_gbp=5.0)
    assert result.stake_gbp == 5.0


def test_filter_by_side_drops_unders_by_default():
    candidates = [_candidate("A", "G1", side="over"), _candidate("B", "G2", side="under")]
    assert [c.player for c in filter_by_side(candidates)] == ["A"]


def test_build_accumulator_never_includes_an_under_leg():
    # Requirement 1: overs only, even if an under leg would otherwise pass
    # every gate and have a great fair probability.
    candidates = [
        _candidate("OverA", "G1", side="over", fair_prob=0.5),
        _candidate("UnderB", "G2", side="under", fair_prob=0.9),  # best fair_prob, but wrong side
        _candidate("OverC", "G3", side="over", fair_prob=0.55),
        _candidate("OverD", "G4", side="over", fair_prob=0.52),
    ]
    result = build_accumulator(candidates)
    assert all(c.side == "over" for c in result.legs)
    assert "UnderB" not in {c.player for c in result.legs}
