import pandas as pd

from football_goals import history
from football_goals.scope import describe, in_scope

CFG = {"markets": {"over_1_5": {"kickoffs": ["15:00"], "exclude_leagues": []},
                   "gibh": {"kickoffs": ["15:00"], "exclude_leagues": ["National League North", "National League South"]}}}


def test_three_pm_only_for_both_markets():
    for mk in ("o15", "gibh"):
        assert in_scope(CFG, mk, "League Two", "15:00")
        assert not in_scope(CFG, mk, "League Two", "12:30")
        assert not in_scope(CFG, mk, "League Two", "17:30")
        assert not in_scope(CFG, mk, "League Two", "")          # unknown kick-off is left out
        assert not in_scope(CFG, mk, "League Two", float("nan"))


def test_regional_leagues_out_of_gibh_only():
    assert in_scope(CFG, "o15", "National League North", "15:00")
    assert not in_scope(CFG, "gibh", "National League North", "15:00")
    assert not in_scope(CFG, "gibh", "National League South", "15:00")
    assert in_scope(CFG, "gibh", "National League", "15:00")


def test_empty_rules_mean_everything():
    assert in_scope({}, "o15", "Anything", "19:45")
    assert describe({}, "gibh") == "all fixtures"
    assert describe(CFG, "gibh") == "15:00 kick-offs only; excludes National League North, National League South"


def test_track_record_counts_only_in_scope_fixtures():
    base = {"report_date": "2026-10-03", "status": "graded", "o15_combined": 85.0, "o15_league_rate": 75.0,
            "gibh_combined": 70.0, "gibh_league_rate": 60.0, "acca": "", "gibh_acca": ""}
    df = pd.DataFrame([
        dict(base, league_name="League Two", kickoff="15:00", o15_hit=True, gibh_hit=True),
        dict(base, league_name="League Two", kickoff="12:30", o15_hit=False, gibh_hit=False),
        dict(base, league_name="National League North", kickoff="15:00", o15_hit=False, gibh_hit=False),
    ])
    hr = history.hit_rates(df, cfg=CFG)
    assert hr["markets"]["Over 1.5"]["overall"]["n"] == 2            # 15:00 League Two + 15:00 North
    assert hr["markets"]["Goal in both halves"]["overall"]["n"] == 1  # North excluded
    assert hr["markets"]["Goal in both halves"]["overall"]["hit_pct"] == 100
    assert history.hit_rates(df)["markets"]["Over 1.5"]["overall"]["n"] == 3   # no config = everything
