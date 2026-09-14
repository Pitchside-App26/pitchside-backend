from explain import explain_projection
from projection_engine import Projection


def _veteran_proj(**overrides):
    base = dict(
        player_id="p1", player_name="Test Player", stat_col="passing_yards",
        projection=268.0, season_std=50.0, n_current_games=0, n_prior_games=17,
        method="veteran", confidence="normal",
        current_season_avg=0.0, prior_season_avg=267.8, last5_avg=268.0,
        blended_season_avg=268.0, baseline=268.0, opp_factor=1.0,
        opponent_team="NYG", team_changed=False, prior_weight=1.0,
    )
    base.update(overrides)
    return Projection(**base)


def test_explain_zero_current_games_mentions_prior_season():
    text = explain_projection(_veteran_proj())
    assert "No games played yet this season" in text
    assert "267.8" in text


def test_explain_mentions_matchup_adjustment_when_significant():
    proj = _veteran_proj(n_current_games=5, current_season_avg=250.0, opp_factor=1.2)
    text = explain_projection(proj)
    assert "NYG" in text
    assert "favorable" in text or "tougher" in text


def test_explain_flags_thin_sample():
    proj = _veteran_proj(method="thin_sample", confidence="low")
    text = explain_projection(proj)
    assert "low confidence" in text


def test_explain_rookie_mentions_analog_pool():
    proj = Projection(
        player_id="r1", player_name="Rookie Player", stat_col="receiving_yards",
        projection=61.7, season_std=20.0, n_current_games=0, n_prior_games=0,
        method="rookie_prior", confidence="low",
        n_analog_players=9, analog_position="WR", analog_pick=9,
    )
    text = explain_projection(proj)
    assert "No NFL games played yet" in text
    assert "9" in text
    assert "WR" in text
    assert "pick #9" in text
