from projection_engine import Projection
from rank_props import build_ranked_prop


def _proj():
    return Projection(
        player_id="p1", player_name="Test Player", stat_col="yards",
        projection=80.0, season_std=10.0, n_current_games=5, n_prior_games=0,
        method="veteran", confidence="normal",
    )


def test_injury_status_stored_and_mentioned_in_explanation():
    ranked = build_ranked_prop(_proj(), line=70.0, current_season_values=[], injury_status="Questionable")
    assert ranked.injury_status == "Questionable"
    assert "questionable" in ranked.explanation.lower()


def test_no_injury_status_means_no_mention():
    ranked = build_ranked_prop(_proj(), line=70.0, current_season_values=[])
    assert ranked.injury_status is None


def test_avg_targets_stored_and_mentioned_in_explanation():
    ranked = build_ranked_prop(_proj(), line=70.0, current_season_values=[], avg_targets=8.4)
    assert ranked.avg_targets == 8.4
    assert "8.4 targets" in ranked.explanation


def test_no_avg_targets_means_no_mention():
    ranked = build_ranked_prop(_proj(), line=70.0, current_season_values=[])
    assert ranked.avg_targets is None
    assert "targets" not in ranked.explanation
