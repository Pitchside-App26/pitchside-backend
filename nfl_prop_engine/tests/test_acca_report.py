import json

import pytest

from acca_report import LegContext, _safe_source, build_acca_report, consensus_by_prop, evaluate_leg
from output import write_json


def _book(book, point, over=-110, under=-110, event="e1", market="player_pass_yds", player="Drake Maye"):
    return {"event_id": event, "market": market, "player_name": player, "bookmaker": book,
            "point": point, "over_price": over, "under_price": under}


def _ctx(player="Drake Maye", market="player_pass_yds", stat="passing_yards", projection=240.0, event="e1",
         home="NYJ", away="NE", recent=(230, 250, 260, 210, 245, 255), opp=1.1, spread=3.0, total=46.5,
         injury=None, teammates_out=(), window="early"):
    return LegContext(
        event_id=event, odds_player_name=player, market=market, player=player, stat_col=stat,
        team=away, opponent=home, home_team=home, away_team=away, kickoff="Sun 1:00 ET", projection=projection,
        opp_factor=opp, team_spread=spread, total_line=total, injury_status=injury,
        recent_values=list(recent), teammates_out=list(teammates_out), window=window,
    )


@pytest.fixture
def gate_mode(monkeypatch):
    import acca_report

    monkeypatch.setitem(acca_report.ANALYST_SWEEP, "sources_gate", True)
    monkeypatch.setattr(acca_report, "FILL_WITH_NEAR_MISSES", False)


def _acca(report, window="early"):
    return next(a for a in report["accumulators"] if a["window"] == window)


TWO_BOOKS = [_book("draftkings", 214.5), _book("fanduel", 214.5, over=-120, under=100)]


def _gate(leg_or_record, name):
    gates = leg_or_record["gates"] if isinstance(leg_or_record, dict) else leg_or_record.gates
    for g in gates:
        if (g["gate"] if isinstance(g, dict) else g.gate) == name:
            return g
    return None


# --- consensus ---------------------------------------------------------------

def test_consensus_is_the_median_of_us_books():
    rows = [_book("draftkings", 214.5), _book("fanduel", 216.5), _book("betmgm", 215.5)]
    c = consensus_by_prop(rows)[("e1", "player_pass_yds", "Drake Maye")]
    assert c["line"] == 215.5
    assert c["n_books"] == 3
    assert c["fair_prob"] == pytest.approx(0.5)


def test_a_single_book_is_a_thin_market():
    c = consensus_by_prop([_book("draftkings", 214.5)])[("e1", "player_pass_yds", "Drake Maye")]
    assert c["line"] is None


# --- gates before the sweep --------------------------------------------------

def test_week3_maye_target_line_is_below_the_bet365_line_he_took():
    # Week 3: bet365 had Maye at 222.5 against a US consensus of 214.5.
    leg = evaluate_leg(_ctx(), consensus_by_prop(TWO_BOOKS)[("e1", "player_pass_yds", "Drake Maye")])
    assert leg.max_line == 216.5
    assert 222.5 > leg.max_line


def test_count_markets_get_no_line_tolerance():
    rows = [_book("draftkings", 4.5, market="player_receptions"), _book("fanduel", 4.5, market="player_receptions")]
    ctx = _ctx(market="player_receptions", stat="receptions", projection=5.5, recent=(5, 6, 4, 7, 5, 6))
    leg = evaluate_leg(ctx, consensus_by_prop(rows)[("e1", "player_receptions", "Drake Maye")])
    assert leg.max_line == 4.5


def test_a_good_leg_passes_every_gate_before_the_sweep():
    leg = evaluate_leg(_ctx(), consensus_by_prop(TWO_BOOKS)[("e1", "player_pass_yds", "Drake Maye")])
    assert leg.failed == []
    assert [g.gate for g in leg.gates] == ["market", "model", "form", "outlier", "matchup", "game_script", "injury"]


def test_gates_are_judged_at_the_worst_acceptable_line_not_the_consensus():
    # Projection 215.5 clears the 214.5 consensus but not the 216.5 max line.
    leg = evaluate_leg(_ctx(projection=215.5), consensus_by_prop(TWO_BOOKS)[("e1", "player_pass_yds", "Drake Maye")])
    assert [g.gate for g in leg.failed] == ["model"]


def test_thin_market_fails_and_skips_line_based_gates():
    leg = evaluate_leg(_ctx(), consensus_by_prop([_book("draftkings", 214.5)])[("e1", "player_pass_yds", "Drake Maye")])
    assert leg.failed[0].gate == "market"
    assert leg.max_line is None
    assert _gate(leg, "form") is None


def test_rookie_without_opponent_data_fails_matchup_with_a_reason():
    leg = evaluate_leg(_ctx(opp=None), consensus_by_prop(TWO_BOOKS)[("e1", "player_pass_yds", "Drake Maye")])
    assert _gate(leg, "matchup").passed is False
    assert "no opponent data" in _gate(leg, "matchup").reason


def test_teammate_out_is_a_flag_not_a_failure():
    leg = evaluate_leg(_ctx(teammates_out=["Stefon Diggs"]), consensus_by_prop(TWO_BOOKS)[("e1", "player_pass_yds", "Drake Maye")])
    assert leg.failed == []
    assert any("Stefon Diggs" in f for f in leg.flags)


# --- the whole report ------------------------------------------------------------

def _slate():
    """Three clean legs in two games, plus one leg that fails form."""
    rows, contexts = [], []
    specs = [
        ("e1", "NE", "NYJ", "Drake Maye", "player_pass_yds", "passing_yards", 214.5, 240.0, (230, 250, 260, 210, 245, 255)),
        ("e1", "NE", "NYJ", "Garrett Wilson", "player_reception_yds", "receiving_yards", 65.5, 80.0, (70, 90, 60, 85, 75, 80)),
        ("e2", "DAL", "PHI", "Tony Pollard", "player_rush_yds", "rushing_yards", 48.5, 60.0, (55, 62, 50, 70, 58, 65)),
        ("e2", "DAL", "PHI", "Cold Streak", "player_rush_yds", "rushing_yards", 48.5, 55.0, (10, 20, 15, 12, 90, 18)),
    ]
    for event, away, home, player, market, stat, line, projection, recent in specs:
        rows += [_book("draftkings", line, event=event, market=market, player=player),
                 _book("fanduel", line, event=event, market=market, player=player)]
        contexts.append(_ctx(player=player, market=market, stat=stat, projection=projection, event=event,
                             home=home, away=away, recent=recent))
    return contexts, rows


def _pick(player, market, line, side="Over", analyst="A", outlet="Covers"):
    return {"player": player, "market": market, "line": line, "side": side, "analyst": analyst,
            "outlet": outlet, "url": "https://example.com/pick"}


class FakeSweep:
    def __init__(self, picks_by_game):
        self.picks_by_game = picks_by_game
        self.calls = []

    def __call__(self, games, week, max_workers):
        self.calls.append(list(games))
        picks = {g: self.picks_by_game.get(g.rsplit(", NFL Week", 1)[0], []) for g in games}
        return picks, {"input_tokens": 1, "output_tokens": 1, "web_searches": 1, "estimated_cost_usd": 0.5}


def _two_analysts(player, market, line):
    return [_pick(player, market, line, analyst="A", outlet="Covers"), _pick(player, market, line, analyst="B", outlet="SI")]


def test_full_report_builds_an_accumulator_from_legs_backed_by_analysts(gate_mode):
    contexts, rows = _slate()
    sweep = FakeSweep({
        "New England Patriots at New York Jets": _two_analysts("Drake Maye", "Passing Yards", 214.5)
        + _two_analysts("Garrett Wilson", "Receiving Yards", 65.5),
        "Dallas Cowboys at Philadelphia Eagles": _two_analysts("Tony Pollard", "Rushing Yards", 48.5),
    })
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=sweep, api_key_present=True)

    assert _acca(report)["mode"] == "accumulator"
    assert {leg["player"] for leg in _acca(report)["legs"]} == {"Drake Maye", "Garrett Wilson", "Tony Pollard"}
    assert _acca(report)["combined_fair_odds"] == pytest.approx(8.0)  # three legs at 50% fair = 2.0 each
    assert all(leg["bet_builder"] == (leg["game"] == "NE @ NYJ") for leg in _acca(report)["legs"])
    # Cold Streak failed form before the sweep, so DAL @ PHI was swept only for Pollard.
    assert sorted(sweep.calls[0]) == ["Dallas Cowboys at Philadelphia Eagles, NFL Week 4 2026",
                                      "New England Patriots at New York Jets, NFL Week 4 2026"]
    assert report["excluded"][0]["player"] == "Cold Streak"
    assert [f["gate"] for f in report["excluded"][0]["failed"]] == ["form", "outlier"]
    assert report["analyst_sweep"]["usage"]["estimated_cost_usd"] == 0.5


def test_one_analyst_is_not_enough(gate_mode):
    contexts, rows = _slate()
    sweep = FakeSweep({"New England Patriots at New York Jets": [_pick("Drake Maye", "Passing Yards", 214.5)]})
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=sweep, api_key_present=True)
    assert _acca(report)["mode"] == "no_bet"
    maye = next(m for m in report["near_misses"] if m["player"] == "Drake Maye")
    assert "only 1 independent analyst" in _gate(maye, "sources")["reason"]


def test_an_analyst_on_the_under_marks_the_leg_contested(gate_mode):
    contexts, rows = _slate()
    picks = _two_analysts("Drake Maye", "Passing Yards", 214.5) + [_pick("Drake Maye", "Passing Yards", 214.5, side="Under", analyst="C")]
    sweep = FakeSweep({"New England Patriots at New York Jets": picks})
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=sweep, api_key_present=True)
    maye = next(m for m in _acca(report)["legs"] + report["near_misses"] if m["player"] == "Drake Maye")
    assert any(f.startswith("Contested") for f in maye["flags"])
    assert len(maye["sources"]["under"]) == 1


def test_without_an_api_key_the_sweep_is_skipped_and_says_why(gate_mode):
    contexts, rows = _slate()
    sweep = FakeSweep({})
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=sweep, api_key_present=False)
    assert sweep.calls == []
    assert _acca(report)["mode"] == "no_bet"
    assert "ANTHROPIC_API_KEY" in report["analyst_sweep"]["note"]
    assert "ANTHROPIC_API_KEY" in _gate(report["near_misses"][0], "sources")["reason"]


def test_the_sweep_is_capped_and_capped_games_say_so(gate_mode, monkeypatch):
    import acca_report

    monkeypatch.setitem(acca_report.ANALYST_SWEEP, "max_games", 1)
    contexts, rows = _slate()
    sweep = FakeSweep({})
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=sweep, api_key_present=True)
    assert len(sweep.calls[0]) == 1
    assert sweep.calls[0][0].startswith("New England Patriots at New York Jets")  # two surviving legs beats one
    pollard = next(m for m in report["near_misses"] if m["player"] == "Tony Pollard")
    assert "capped at 1 games" in _gate(pollard, "sources")["reason"]


def test_bet365_in_feed_is_detected():
    contexts, rows = _slate()
    rows.append(_book("bet365", 214.5))
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=FakeSweep({}), api_key_present=False)
    assert report["bet365_in_feed"] is True
    assert "bet365" in report["bookmakers_seen"]


def test_report_writes_valid_json(tmp_path):
    contexts, rows = _slate()
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=FakeSweep({}), api_key_present=True)
    _acca(report)["combined_probability"] = float("nan")  # must never reach the page as a bare NaN
    path = tmp_path / "data.json"
    write_json([], 2026, 4, str(path), accumulator=report)
    data = json.loads(path.read_text())
    assert data["accumulator"]["accumulators"][0]["combined_probability"] is None


@pytest.mark.parametrize("url, kept", [
    ("https://www.covers.com/x", "https://www.covers.com/x"),
    ("javascript:alert(1)", ""),
    ("data:text/html,hi", ""),
    (None, ""),
])
def test_only_web_links_reach_the_page(url, kept):
    assert _safe_source({"outlet": "Covers", "url": url})["url"] == kept


# --- analysts as a signal (the default since 1 Oct) ----------------------------

def test_signal_mode_suggests_legs_without_any_analyst_backing():
    contexts, rows = _slate()
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=FakeSweep({}), api_key_present=True)
    assert report["sources_mode"] == "signal"
    assert _acca(report)["mode"] == "accumulator"
    assert {leg["player"] for leg in _acca(report)["legs"]} == {"Drake Maye", "Garrett Wilson", "Tony Pollard"}
    for leg in _acca(report)["legs"]:
        assert _gate(leg, "sources") is None
        assert leg["sources_checked"] is True
        assert leg["sources_note"] == "0 independent analyst(s) backing the over"


def test_signal_mode_still_shows_backers_and_flags_contested():
    contexts, rows = _slate()
    picks = _two_analysts("Drake Maye", "Passing Yards", 214.5) + [_pick("Drake Maye", "Passing Yards", 214.5, side="Under", analyst="C")]
    report = build_acca_report(contexts, rows, week=4, season=2026,
                               sweep=FakeSweep({"New England Patriots at New York Jets": picks}), api_key_present=True)
    maye = next(leg for leg in _acca(report)["legs"] if leg["player"] == "Drake Maye")
    assert len(maye["sources"]["over"]) == 2 and len(maye["sources"]["under"]) == 1
    assert any(f.startswith("Contested") for f in maye["flags"])


def test_signal_mode_sweeps_the_suggested_legs_games_first(monkeypatch):
    import acca_report

    monkeypatch.setitem(acca_report.ANALYST_SWEEP, "max_games", 1)
    contexts, rows = _slate()
    sweep = FakeSweep({})
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=sweep, api_key_present=True)
    assert sweep.calls == [["New England Patriots at New York Jets, NFL Week 4 2026"]]  # two suggested legs beats one
    pollard = next(leg for leg in _acca(report)["legs"] if leg["player"] == "Tony Pollard")
    assert pollard["sources_checked"] is False
    assert "capped at 1 games" in pollard["sources_note"]


def test_signal_mode_without_an_api_key_still_suggests_legs():
    contexts, rows = _slate()
    report = build_acca_report(contexts, rows, week=4, season=2026, sweep=FakeSweep({}), api_key_present=False)
    assert _acca(report)["mode"] == "accumulator"
    assert all("ANTHROPIC_API_KEY" in leg["sources_note"] for leg in _acca(report)["legs"])


def test_every_evaluated_leg_is_logged_for_grading():
    contexts, rows = _slate()
    for i, ctx in enumerate(contexts):
        ctx.player_id = f"id{i}"
    logged = []
    build_acca_report(contexts, rows, week=4, season=2026, api_key_present=True, log_rows=logged.extend,
                      sweep=FakeSweep({"New England Patriots at New York Jets": _two_analysts("Drake Maye", "Passing Yards", 214.5)}))
    by_player = {r["player_name"]: r for r in logged}
    assert set(by_player) == {"Drake Maye", "Garrett Wilson", "Tony Pollard", "Cold Streak"}
    maye, cold = by_player["Drake Maye"], by_player["Cold Streak"]
    assert (maye["passed_gates"], maye["selected"], maye["sources_checked"], maye["n_over_sources"]) == (True, True, True, 2)
    assert maye["player_id"] == "id0" and maye["max_line"] == 216.5
    assert (cold["passed_gates"], cold["selected"], cold["failed_gates"]) == (False, False, "form,outlier")
    assert cold["sources_checked"] is False and cold["n_over_sources"] is None


# --- one accumulator per window, topped up to 6 --------------------------------

def _window_slate(specs):
    """specs: (player, event, away, home, window, opp_factor, projection)."""
    rows, contexts = [], []
    for player, event, away, home, window, opp, projection in specs:
        rows += [_book("draftkings", 50.5, event=event, market="player_rush_yds", player=player),
                 _book("fanduel", 50.5, event=event, market="player_rush_yds", player=player)]
        contexts.append(_ctx(player=player, market="player_rush_yds", stat="rushing_yards", projection=projection,
                             event=event, home=home, away=away, recent=(60, 62, 58, 70, 65, 61), opp=opp, window=window))
    return contexts, rows


def test_a_window_is_topped_up_to_six_with_one_gate_failures_best_first():
    specs = [
        ("Pass A", "e1", "NE", "BUF", "early", 1.1, 70), ("Pass B", "e2", "NYJ", "CHI", "early", 1.1, 70),
        # each fails only Matchup (opp 0.8); projection sets filler order
        ("Fill 80", "e3", "JAX", "CIN", "early", 0.8, 80), ("Fill 75", "e4", "DAL", "HOU", "early", 0.8, 75),
        ("Fill 74", "e5", "ARI", "NYG", "early", 0.8, 74), ("Fill 73", "e6", "LA", "PHI", "early", 0.8, 73),
        ("Fill 60", "e7", "GB", "TB", "early", 0.8, 60),
    ]
    contexts, rows = _window_slate(specs)
    report = build_acca_report(contexts, rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False,
                               window_kickoffs={"early": "18:00"})
    acca = _acca(report)
    assert acca["mode"] == "accumulator" and acca["kickoff_uk"] == "18:00"
    assert [leg["player"] for leg in acca["legs"]] == ["Pass A", "Pass B", "Fill 80", "Fill 75", "Fill 74", "Fill 73"]
    assert (acca["n_passed"], acca["n_fillers"]) == (2, 4)
    assert [leg["filler"] for leg in acca["legs"]] == [False, False, True, True, True, True]
    filler = acca["legs"][2]
    assert [g["gate"] for g in filler["gates"] if not g["passed"]] == ["matchup"]
    # Used fillers aren't repeated as near misses; the unused one is.
    assert [m["player"] for m in report["near_misses"]] == ["Fill 60"]


def test_fillers_respect_two_legs_per_game():
    specs = [("Pass A", "e1", "NE", "BUF", "early", 1.1, 70), ("Pass B", "e1", "NE", "BUF", "early", 1.1, 70),
             ("Fill same game", "e1", "NE", "BUF", "early", 0.8, 90), ("Fill other", "e2", "NYJ", "CHI", "early", 0.8, 80)]
    contexts, rows = _window_slate(specs)
    acca = _acca(build_acca_report(contexts, rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False))
    assert [leg["player"] for leg in acca["legs"]] == ["Pass A", "Pass B", "Fill other"]


def test_a_leg_with_no_target_line_is_never_a_filler():
    contexts, rows = _window_slate([("Pass A", "e1", "NE", "BUF", "early", 1.1, 70)])
    thin = _ctx(player="Thin Market", market="player_rush_yds", stat="rushing_yards", projection=90, event="e2",
                home="CHI", away="NYJ", recent=(60, 62, 58, 70, 65, 61), opp=1.1)
    rows.append(_book("draftkings", 50.5, event="e2", market="player_rush_yds", player="Thin Market"))  # one book only
    acca = _acca(build_acca_report(contexts + [thin], rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False))
    assert [leg["player"] for leg in acca["legs"]] == ["Pass A"]
    assert acca["mode"] == "singles"


def test_early_and_late_windows_get_separate_accumulators_and_other_games_are_left_out():
    specs = [("Early A", "e1", "NE", "BUF", "early", 1.1, 70), ("Late A", "e2", "KC", "LV", "late", 1.1, 70),
             ("Sunday Night", "e3", "DET", "CAR", None, 1.1, 99), ("SNF filler", "e3", "DET", "CAR", None, 0.8, 99)]
    contexts, rows = _window_slate(specs)
    logged = []
    report = build_acca_report(contexts, rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False, log_rows=logged.extend)
    assert [a["window"] for a in report["accumulators"]] == ["early", "late"]
    assert [leg["player"] for leg in _acca(report, "early")["legs"]] == ["Early A"]
    assert [leg["player"] for leg in _acca(report, "late")["legs"]] == ["Late A"]
    assert report["n_outside_windows"] == 2
    assert all(m["player"] != "SNF filler" for m in report["near_misses"])
    assert {r["player_name"]: r["window"] for r in logged}["Sunday Night"] is None  # still logged for grading


def test_turning_fill_off_restores_no_padding(monkeypatch):
    import acca_report

    monkeypatch.setattr(acca_report, "FILL_WITH_NEAR_MISSES", False)
    specs = [("Pass A", "e1", "NE", "BUF", "early", 1.1, 70), ("Fill", "e2", "NYJ", "CHI", "early", 0.8, 90)]
    contexts, rows = _window_slate(specs)
    acca = _acca(build_acca_report(contexts, rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False))
    assert [leg["player"] for leg in acca["legs"]] == ["Pass A"]


def test_fillers_are_logged_as_selected_fillers():
    specs = [("Pass A", "e1", "NE", "BUF", "early", 1.1, 70), ("Fill", "e2", "NYJ", "CHI", "early", 0.8, 90)]
    contexts, rows = _window_slate(specs)
    logged = []
    build_acca_report(contexts, rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False, log_rows=logged.extend)
    by_player = {r["player_name"]: r for r in logged}
    assert (by_player["Fill"]["selected"], by_player["Fill"]["filler"], by_player["Fill"]["window"]) == (True, True, "early")
    assert (by_player["Pass A"]["selected"], by_player["Pass A"]["filler"]) == (True, False)


def test_the_capped_sweep_is_shared_between_windows(monkeypatch):
    import acca_report

    monkeypatch.setitem(acca_report.ANALYST_SWEEP, "max_games", 2)
    specs = [("Early A", "e1", "NE", "BUF", "early", 1.1, 70), ("Early B", "e2", "NYJ", "CHI", "early", 1.1, 70),
             ("Early C", "e3", "JAX", "CIN", "early", 1.1, 70), ("Late A", "e4", "KC", "LV", "late", 1.1, 70)]
    contexts, rows = _window_slate(specs)
    sweep = FakeSweep({})
    build_acca_report(contexts, rows, 4, 2026, sweep=sweep, api_key_present=True)
    swept = [g.split(",")[0] for g in sweep.calls[0]]
    assert len(swept) == 2
    assert "Kansas City Chiefs at Las Vegas Raiders" in swept  # the late window gets a game


# --- spares: replacements offered when a leg fails the bet365 check ----------

def test_spares_list_unused_passing_legs_before_one_gate_failures():
    specs = [(f"Pass {i}", f"e{i}", f"A{i}", f"H{i}", "early", 1.1, 70 + i) for i in range(8)]
    specs += [("Near Big", "e20", "X1", "Y1", "early", 0.8, 99), ("Near Small", "e21", "X2", "Y2", "early", 0.8, 60)]
    contexts, rows = _window_slate(specs)
    acca = _acca(build_acca_report(contexts, rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False))
    assert [leg["player"] for leg in acca["legs"]] == ["Pass 7", "Pass 6", "Pass 5", "Pass 4", "Pass 3", "Pass 2"]
    assert [leg["player"] for leg in acca["spares"]] == ["Pass 1", "Pass 0", "Near Big", "Near Small"]
    assert [leg["filler"] for leg in acca["spares"]] == [False, False, True, True]
    spare = acca["spares"][0]
    assert spare["key"] == "Pass 1|rushing_yards"
    assert spare["recent"] == [60, 62, 58, 70, 65, 61]
    assert spare["max_line"] == 52.5


def test_spares_never_include_a_leg_without_a_target_line():
    contexts, rows = _window_slate([("Pass A", "e1", "NE", "BUF", "early", 1.1, 70)])
    thin = _ctx(player="Thin Market", market="player_rush_yds", stat="rushing_yards", projection=90, event="e2",
                home="CHI", away="NYJ", recent=(60, 62, 58, 70, 65, 61), opp=1.1)
    rows.append(_book("draftkings", 50.5, event="e2", market="player_rush_yds", player="Thin Market"))
    acca = _acca(build_acca_report(contexts + [thin], rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False))
    assert acca["spares"] == []


def test_with_fill_off_spares_are_only_legs_that_passed(monkeypatch):
    import acca_report

    monkeypatch.setattr(acca_report, "FILL_WITH_NEAR_MISSES", False)
    specs = [(f"Pass {i}", f"e{i}", f"A{i}", f"H{i}", "early", 1.1, 70 + i) for i in range(7)]
    specs += [("Near", "e20", "X1", "Y1", "early", 0.8, 99)]
    contexts, rows = _window_slate(specs)
    acca = _acca(build_acca_report(contexts, rows, 4, 2026, sweep=FakeSweep({}), api_key_present=False))
    assert [leg["player"] for leg in acca["spares"]] == ["Pass 0"]
