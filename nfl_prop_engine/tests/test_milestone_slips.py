import math

import numpy as np
import pandas as pd
import pytest

from acca_report import LegContext
from milestone_slips import ChanceModel, Exclusions, build_slips, candidates_for, milestones, per_leg_target
from participation import Role

STEADY = Role(0.9, 0.88, 5)


def _graded(stat="receptions", lines=(3.5, 4.5, 5.5, 6.5), n=60, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for line in lines:
        for _ in range(n):
            rows.append({"stat_col": stat, "line": line, "actual_value": max(0.0, round(rng.normal(line, line * 0.35)))})
    return pd.DataFrame(rows)


def _model():
    frames = [_graded(stat, lines) for stat, lines in [
        ("receptions", (3.5, 4.5, 5.5, 6.5)), ("receiving_yards", (35.5, 50.5, 65.5, 80.5)),
        ("passing_yards", (190.5, 220.5, 245.5, 270.5)), ("completions", (18.5, 20.5, 22.5, 24.5)),
        ("carries", (10.5, 13.5, 16.5, 19.5)), ("def_tackles", (4.5, 5.5, 6.5, 7.5))]]
    return ChanceModel.from_graded(pd.concat(frames))


def _ctx(player, stat, game="NE @ BUF", window="early", market=None, injury=None):
    away, home = game.split(" @ ")
    return LegContext(event_id=game, odds_player_name=player, market=market or f"m_{stat}", player=player,
                      stat_col=stat, team=home, opponent=away, home_team=home, away_team=away, kickoff="13:00",
                      projection=0, opp_factor=None, team_spread=None, total_line=None, injury_status=injury,
                      recent_values=[], player_id=player, window=window)


def _books(ctx, line, over_prob=0.5, n=2):
    american = lambda q: -100 * q / (1 - q) if q > 0.5 else 100 * (1 - q) / q
    return [{"event_id": ctx.event_id, "market": ctx.market, "player_name": ctx.odds_player_name, "point": line,
             "over_price": american(over_prob), "under_price": american(1 - over_prob), "bookmaker": f"b{i}"}
            for i in range(n)]


def test_the_main_line_sits_where_the_books_price_it():
    model = _model()
    assert model.chance("receptions", 4.5, 0.5, 5) == pytest.approx(0.5, abs=0.05)
    assert model.chance("receptions", 4.5, 0.6, 5) == pytest.approx(0.6, abs=0.05)
    # a lower milestone is more likely than a higher one
    assert model.chance("receptions", 4.5, 0.5, 3) > model.chance("receptions", 4.5, 0.5, 5)


def test_milestones_are_bettable_steps_at_or_below_the_line():
    assert milestones("receptions", 4.5) == [1, 2, 3, 4, 5]
    assert milestones("passing_yards", 45.5) == [10, 20, 30, 40]
    assert milestones("receiving_yards", 22.5) == [5, 10, 15, 20]


def test_a_six_fold_is_built_to_land_about_one_time_in_twenty():
    games = [f"T{i} @ H{i}" for i in range(8)]
    stats = [("receptions", 5.5), ("receiving_yards", 60.5), ("passing_yards", 230.5), ("completions", 21.5),
             ("carries", 15.5), ("def_tackles", 6.5)]
    contexts, rows = [], []
    for i, game in enumerate(games):
        for stat, line in stats:
            ctx = _ctx(f"P{i}{stat}", stat, game)
            contexts.append(ctx)
            rows += _books(ctx, line)
    logged = []
    out = build_slips(contexts, rows, _model(), lambda ctx: STEADY, {"early": "18:00"}, log_rows=logged.extend)
    slip = out["slips"][0]
    assert slip["complete"] and len(slip["legs"]) == 6
    assert 14 <= slip["one_in"] <= 28
    assert len({leg["game"] for leg in slip["legs"]}) == 6  # one leg a game while there are enough games
    assert max(sum(leg["stat"] == s for leg in slip["legs"]) for s, _ in stats) <= 2
    leg = slip["legs"][0]
    assert leg["label"].startswith(f"{leg['threshold']}+") and leg["over_line"] == leg["threshold"] - 0.5
    assert any(a["threshold"] == leg["threshold"] for a in leg["alternatives"])
    assert slip["chance"] == pytest.approx(math.prod(l["chance"] for l in slip["legs"]), rel=0.01)  # legs are rounded
    assert {r["role"] for r in logged} == {"leg", "spare"} and sum(r["role"] == "leg" for r in logged) == 6


@pytest.mark.parametrize("role, injury, books, reason", [
    (Role(0.4, 0.42, 4), None, 2, "part-time role"),        # a part-timer (Tory Horton at 17%)
    (Role(0.65, 0.42, 5), None, 2, "role just changed"),    # backup turned starter (Ollie Gordon)
    (STEADY, "Questionable", 2, "injury report"),
    (STEADY, None, 1, "too few books"),
])
def test_players_whose_line_lags_their_role_are_left_out(role, injury, books, reason):
    ctx = _ctx("P", "receptions", injury=injury)
    excluded = Exclusions()
    from acca_report import consensus_by_prop
    found = candidates_for([ctx], consensus_by_prop(_books(ctx, 5.5, n=books)), _model(), lambda c: role, excluded)
    assert found == [] and excluded.counts == {reason: 1}


def test_a_quarterbacks_carries_are_never_a_leg():
    from acca_report import consensus_by_prop
    qb_yards, qb_carries = _ctx("QB", "passing_yards"), _ctx("QB", "carries")
    rows = _books(qb_yards, 230.5) + _books(qb_carries, 6.5)
    excluded = Exclusions()
    found = candidates_for([qb_yards, qb_carries], consensus_by_prop(rows), _model(), lambda c: STEADY, excluded)
    assert [c.ctx.stat_col for c in found] == ["passing_yards"]
    assert excluded.counts == {"quarterback carries": 1}


def test_the_per_leg_target_for_one_in_twenty():
    assert per_leg_target(20, 6) == pytest.approx(0.607, abs=0.001)


def test_a_role_settles_after_a_few_games():
    from participation import season_roles

    weeks = [0.07, 0.19, 0.84, 0.56, 0.65]  # Ollie Gordon: backup, then the starter from week 3
    snaps = pd.DataFrame([{"week": w + 1, "player": "Ollie Gordon", "pfr_player_id": "GordOl00", "team": "MIA",
                           "offense_snaps": pct * 60, "offense_pct": pct, "defense_snaps": 0, "defense_pct": 0,
                           "st_snaps": 0} for w, pct in enumerate(weeks)])
    assert season_roles(snaps, 5).lookup("GordOl00", None, None).swing > 0.15  # week 5: just changed
    assert season_roles(snaps, 6).lookup("GordOl00", None, None).swing < 0.15  # week 6: settled
