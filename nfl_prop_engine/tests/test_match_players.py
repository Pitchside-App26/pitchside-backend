from match_players import match_name


def test_exact_override_wins_over_fuzzy():
    overrides = {"Gabe Davis": "Gabriel Davis"}
    name, score, method = match_name("Gabe Davis", ["Gabriel Davis", "Gabriel Davison"], overrides)
    assert (name, method) == ("Gabriel Davis", "override")
    assert score == 100.0


def test_fuzzy_match_above_threshold():
    name, score, method = match_name("Patrick Mahomes II", ["Patrick Mahomes", "Someone Else"], overrides={})
    assert name == "Patrick Mahomes"
    assert method == "fuzzy"


def test_no_match_below_threshold_returns_none_not_a_guess():
    name, score, method = match_name("Zzzqx Totally Unrelated", ["Patrick Mahomes"], overrides={})
    assert name is None
    assert method == "below_threshold"


def test_no_candidates_returns_none():
    name, score, method = match_name("Anyone", [], overrides={})
    assert name is None
    assert method == "no_candidates"
