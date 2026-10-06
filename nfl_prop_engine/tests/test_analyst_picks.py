import sqlite3

import pandas as pd
import pytest

import analyst_sweep
from analyst_picks import GameRef, PlayerRef, build_feed, fetch_slate_picks, log_rows, picks_by_game, resolve_picks
from tests.test_analyst_sweep import _install, _response

PLAYERS = [
    PlayerRef("p1", "Kyren Williams", "LA"),
    PlayerRef("p2", "A.J. Brown", "PHI"),
    PlayerRef("p3", "Byron Young", "LA"),
    PlayerRef("p4", "Byron Young", "PHI"),
    PlayerRef("p5", "Patrick Mahomes", "KC"),
]
GAME = GameRef("LA @ PHI", "Los Angeles Rams at Philadelphia Eagles", "early")
TEAM_GAMES = {"LA": GAME, "PHI": GAME}  # KC isn't in a window this week


def _raw(**kw):
    pick = {"outlet": "Covers", "analyst": "Jane Doe", "player": "Kyren Williams", "team": "LA",
            "market": "Rushing Yards", "side": "Over", "line": 61.5, "price": "-115",
            "publish_date": "2026-10-02", "url": "https://www.covers.com/nfl/props"}
    return {**pick, **kw}


def test_picks_are_matched_to_a_player_game_and_engine_market():
    resolved, dropped = resolve_picks([_raw()], PLAYERS, TEAM_GAMES)
    assert dropped == 0
    p = resolved[0]
    assert (p["player_id"], p["market"], p["stat_col"], p["side"], p["line"]) == (
        "p1", "player_rush_yds", "rushing_yards", "over", 61.5)
    assert (p["game"], p["window"], p["stat_label"]) == ("LA @ PHI", "early", "Rush Yds")


@pytest.mark.parametrize("raw", [
    _raw(market="Anytime TD Scorer"),          # not an over/under market the engine covers
    _raw(market="Rush + Rec Yards"),           # combo market
    _raw(side="Pass"),                         # no side
    _raw(line=None),                           # no line
    _raw(player="Somebody Unknown"),           # no such player
    _raw(player="Patrick Mahomes", team="KC"), # game outside the windows
    "not a dict",
])
def test_unusable_picks_are_dropped_and_counted(raw):
    resolved, dropped = resolve_picks([raw], PLAYERS, TEAM_GAMES)
    assert (resolved, dropped) == ([], 1)


def test_a_shared_name_resolves_to_the_team_the_article_named():
    resolved, _ = resolve_picks([_raw(player="Byron Young", team="PHI", market="Sacks", line=0.5)], PLAYERS, TEAM_GAMES)
    assert resolved[0]["player_id"] == "p4"


def test_the_same_analysts_pick_is_kept_once_and_unsafe_links_are_dropped():
    raws = [_raw(), _raw(url="javascript:alert(1)"), _raw(analyst="Someone Else", url="ftp://x")]
    resolved, _ = resolve_picks(raws, PLAYERS, TEAM_GAMES)
    assert len(resolved) == 2
    assert resolved[1]["url"] == ""


def test_every_window_game_gets_an_entry_for_the_slips():
    resolved, _ = resolve_picks([_raw()], PLAYERS, TEAM_GAMES)
    grouped = picks_by_game(resolved, [GAME.description, "Miami Dolphins at Minnesota Vikings"])
    assert len(grouped[GAME.description]) == 1
    assert grouped["Miami Dolphins at Minnesota Vikings"] == []


def test_feed_says_how_each_pick_sits_against_the_slips_and_the_engine():
    raws = [
        _raw(),                                                          # in the slip, over
        _raw(analyst="B", side="Under"),                                 # in the slip, under
        _raw(player="A.J. Brown", team="PHI", market="Receptions", line=5.5),  # engine says under
        _raw(player="A.J. Brown", team="PHI", market="Receiving Yards", line=70.5),  # engine didn't rate
    ]
    resolved, _ = resolve_picks(raws, PLAYERS, TEAM_GAMES)
    accumulator = {"accumulators": [{"legs": [{"player": "Kyren Williams", "stat": "rushing_yards", "max_line": 63.5}]}]}
    ranked = {("p2", "receptions"): {"projection": 4.84, "line": 5.5, "direction": "under"}}
    feed = build_feed(resolved, accumulator, ranked, {"ran": True, "note": "x"})
    by = {(p["player"], p["stat_col"], p["side"]): p["engine"] for p in feed["picks"]}
    assert by[("Kyren Williams", "rushing_yards", "over")]["status"] == "slip_agree"
    assert by[("Kyren Williams", "rushing_yards", "over")]["slip_line"] == 63.5
    assert by[("Kyren Williams", "rushing_yards", "under")]["status"] == "slip_against"
    assert by[("A.J. Brown", "receptions", "over")] == {
        "status": "engine_disagree", "label": "Engine disagrees", "projection": 4.8, "engine_line": 5.5, "slip_line": None,
        "slip_side": None}
    assert by[("A.J. Brown", "receiving_yards", "over")]["status"] == "unrated"
    assert feed["ran"] is True and "game_description" not in feed["picks"][0]


def test_an_analyst_under_agrees_with_an_under_in_the_slip():
    resolved, _ = resolve_picks([_raw(side="Under")], PLAYERS, TEAM_GAMES)
    accumulator = {"accumulators": [{"legs": [{"player": "Kyren Williams", "stat": "rushing_yards", "side": "under",
                                               "target_line": 59.5}]}]}
    engine = build_feed(resolved, accumulator, {}, {})["picks"][0]["engine"]
    assert (engine["status"], engine["slip_side"], engine["slip_line"]) == ("slip_agree", "under", 59.5)


def test_feed_survives_a_failed_accumulator():
    resolved, _ = resolve_picks([_raw()], PLAYERS, TEAM_GAMES)
    feed = build_feed(resolved, {"error": "boom"}, {}, {"ran": True})
    assert feed["picks"][0]["engine"]["status"] == "unrated"


def test_one_search_covers_the_slate_and_reports_its_cost(monkeypatch):
    client = _install(monkeypatch, [_response("end_turn", text='[{"player": "Kyren Williams"}]', searches=8,
                                              in_tok=200_000, out_tok=8_000)])
    picks, usage = fetch_slate_picks(["Los Angeles Rams at Philadelphia Eagles (early games)"], 4, 2026)
    assert picks == [{"player": "Kyren Williams"}]
    assert len(client.calls) == 1
    assert client.calls[0]["tools"][0]["max_uses"] == 8
    assert "Los Angeles Rams at Philadelphia Eagles" in client.calls[0]["system"]
    assert usage["estimated_cost_usd"] == pytest.approx(0.56)  # 200k x $2/M + 8k x $10/M + 8 x $0.01


def test_picks_are_logged_and_graded_at_the_analysts_own_line(tmp_path):
    from grade_results import analyst_groups
    from results_log import grade_analyst_week, log_analyst_picks

    db = str(tmp_path / "log.sqlite3")
    raws = [_raw(), _raw(analyst="B", side="Under")]
    resolved, _ = resolve_picks(raws, PLAYERS, TEAM_GAMES)
    feed = build_feed(resolved, None, {}, {})
    assert log_analyst_picks(log_rows(feed), 2026, 4, db) == 2
    assert grade_analyst_week(2026, 4, {("p1", "rushing_yards"): 80.0}, db) == 2
    df = pd.read_sql_query("SELECT * FROM analyst_picks", sqlite3.connect(db))
    groups = dict(analyst_groups(df))
    assert list(groups["overs"]["outcome"]) == ["hit"]
    assert list(groups["unders"]["outcome"]) == ["miss"]


def test_slate_picks_fill_in_every_window_legs_analyst_backing():
    from tests.test_acca_report import FakeSweep, _acca, _window_slate
    from acca_report import build_acca_report

    contexts, rows = _window_slate([("Pass A", "e1", "NE", "BUF", "early", 1.1, 70),
                                    ("Fails Matchup", "e2", "NYJ", "CHI", "early", 0.8, 70)])
    slate = {
        "New England Patriots at Buffalo Bills": [
            {"player": "Pass A", "market": "player_rush_yds", "side": "over", "line": 51.5, "outlet": "Covers",
             "analyst": "X", "url": ""},
            {"player": "Pass A", "market": "player_rush_yds", "side": "over", "line": 50.5, "outlet": "SI",
             "analyst": "Y", "url": ""},
        ],
        "New York Jets at Chicago Bears": [],
    }
    sweep = FakeSweep({})
    report = build_acca_report(contexts, rows, 4, 2026, sweep=sweep, api_key_present=True, slate_picks=slate)
    assert sweep.calls == []  # the per-game sweep never runs
    legs = {leg["player"]: leg for leg in _acca(report)["legs"]}
    assert legs["Pass A"]["sources_note"] == "2 independent analyst(s) backing the over"
    assert legs["Fails Matchup"]["sources_checked"] is True  # a filler, still checked
    assert report["analyst_sweep"]["ran"] is True


def test_a_thin_market_leg_is_checked_without_crashing():
    from tests.test_acca_report import FakeSweep, _acca, _book, _ctx, _window_slate
    from acca_report import build_acca_report

    contexts, rows = _window_slate([("Pass A", "e1", "NE", "BUF", "early", 1.1, 70)])
    contexts.append(_ctx(player="Thin", market="player_rush_yds", stat="rushing_yards", projection=90, event="e1",
                         home="BUF", away="NE", recent=(60, 62, 58, 70, 65, 61)))
    rows.append(_book("draftkings", 50.5, event="e1", market="player_rush_yds", player="Thin"))  # one book only
    slate = {"New England Patriots at Buffalo Bills": [
        {"player": "Thin", "market": "player_rush_yds", "side": "over", "line": 50.5, "outlet": "Covers", "analyst": "X", "url": ""}]}
    report = build_acca_report(contexts, rows, 4, 2026, sweep=FakeSweep({}), api_key_present=True, slate_picks=slate)
    assert "error" not in report
    assert [leg["player"] for leg in _acca(report)["legs"]] == ["Pass A"]
