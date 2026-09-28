"""Week 3 replay -- the Week 4 upgrade spec's own acceptance criterion.

Fixture data built from the real Week 3 numbers named in the spec, no
live API calls. Must show Maye Over 222.5, Garrett Wilson Over 76.5 and
Pollard Over 61.5 all failing the line gate (the actual bad legs from the
two accumulators that lost), and no unders anywhere in the output (two
of the real Week 3 legs -- Mayfield, Javonte Williams -- were exactly the
"under leg that depended on game script" failure mode named in the
spec's own postmortem).
"""
from accumulator import Candidate, build_accumulator
from leg_gates import line_gate, price_gate


def _passed(*results):
    return list(results)


def test_week3_bad_legs_all_fail_the_line_gate():
    maye_line = line_gate(bet365_line=222.5, consensus_line=214.5, stat_col="passing_yards")
    wilson_line = line_gate(bet365_line=76.5, consensus_line=65.5, stat_col="receiving_yards")
    pollard_line = line_gate(bet365_line=61.5, consensus_line=48.5, stat_col="rushing_yards")

    assert maye_line.passed is False
    assert wilson_line.passed is False
    assert pollard_line.passed is False
    assert maye_line.gate == wilson_line.gate == pollard_line.gate == "line"


def test_week3_replay_end_to_end_excludes_bad_legs_and_unders():
    candidates = [
        # The three real bad legs -- bet365's line had already drifted
        # well past the US consensus. Price gate would pass; line gate
        # fails, and that's the one that matters here.
        Candidate(
            player="Drake Maye", game="NE @ NYJ", market="player_pass_yds", side="over",
            line=222.5, price_decimal=1.91, fair_prob=0.58,
            gates=_passed(
                line_gate(222.5, 214.5, "passing_yards"),
                price_gate(1.91),
            ),
        ),
        Candidate(
            player="Garrett Wilson", game="NYJ @ NE", market="player_reception_yds", side="over",
            line=76.5, price_decimal=1.87, fair_prob=0.55,
            gates=_passed(
                line_gate(76.5, 65.5, "receiving_yards"),
                price_gate(1.87),
            ),
        ),
        Candidate(
            player="Tony Pollard", game="TEN @ HOU", market="player_rush_yds", side="over",
            line=61.5, price_decimal=1.95, fair_prob=0.56,
            gates=_passed(
                line_gate(61.5, 48.5, "rushing_yards"),
                price_gate(1.95),
            ),
        ),
        # Real Week 3 failure mode #1 from the postmortem: under legs that
        # depended on game script. Even with clean gates on their own
        # terms, these must never reach the accumulator -- overs only.
        Candidate(
            player="Baker Mayfield", game="TB @ ATL", market="player_pass_yds", side="under",
            line=245.5, price_decimal=1.90, fair_prob=0.65,
            gates=_passed(line_gate(240.5, 245.5, "passing_yards"), price_gate(1.90)),
        ),
        Candidate(
            player="Javonte Williams", game="DAL @ CHI", market="player_rush_yds", side="under",
            line=55.5, price_decimal=1.88, fair_prob=0.60,
            gates=_passed(line_gate(50.5, 55.5, "rushing_yards"), price_gate(1.88)),
        ),
        # Clean legs that should actually survive -- bet365 in line with
        # the US market, decent price. These are what the accumulator
        # should be built from instead.
        Candidate(
            player="Clean Leg A", game="KC @ DEN", market="player_reception_yds", side="over",
            line=45.5, price_decimal=1.91, fair_prob=0.55,
            gates=_passed(line_gate(45.5, 45.0, "receiving_yards"), price_gate(1.91)),
        ),
        Candidate(
            player="Clean Leg B", game="SF @ SEA", market="player_pass_yds", side="over",
            line=230.5, price_decimal=1.87, fair_prob=0.54,
            gates=_passed(line_gate(230.5, 229.5, "passing_yards"), price_gate(1.87)),
        ),
        Candidate(
            player="Clean Leg C", game="PHI @ NYG", market="player_rush_yds", side="over",
            line=50.5, price_decimal=1.95, fair_prob=0.57,
            gates=_passed(line_gate(50.5, 49.5, "rushing_yards"), price_gate(1.95)),
        ),
    ]

    result = build_accumulator(candidates)

    included_players = {c.player for c in result.legs}
    assert "Drake Maye" not in included_players
    assert "Garrett Wilson" not in included_players
    assert "Tony Pollard" not in included_players
    assert "Baker Mayfield" not in included_players
    assert "Javonte Williams" not in included_players
    assert included_players == {"Clean Leg A", "Clean Leg B", "Clean Leg C"}

    assert all(c.side == "over" for c in result.legs)
    assert result.mode == "accumulator"  # 3 clean legs clears the singles/accumulator line
