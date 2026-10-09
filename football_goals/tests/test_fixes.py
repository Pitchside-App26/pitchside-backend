"""Regression tests for the deep-review fixes (one per bug)."""
from datetime import date

import pandas as pd
import pytest

from football_goals import grade_results, history, render, run_report
from football_goals.sources import espn, football_data, livescore


@pytest.fixture
def tmp_history(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "HISTORY", tmp_path / "history.csv")
    return tmp_path


def _row(lg, h, a, rd="2026-10-03", **kw):
    r = {"report_date": rd, "league": lg, "home": h, "away": a, "league_name": lg, "kickoff": "15:00",
         "o15_combined": 85.0, "o15_venue": 85.0, "o15_league_rate": 75.0, "gibh_combined": 66.0,
         "gibh_venue": 66.0, "gibh_league_rate": 60.0, "acca": "", "gibh_acca": "", "price": None, "flags": ""}
    r.update(kw)
    return r


# 1. A second run for the same date must not wipe that week.
def test_rerun_same_date_keeps_the_week(tmp_history):
    rows = [_row("ENG4", "A", "B"), _row("ENG4", "C", "D"), _row("SCO4", "E", "F")]
    for _ in range(3):
        history.record_report(rows, "2026-10-03")
        assert len(history.load()) == 3


# 8. A league that fails to load on a re-run keeps its recorded fixtures.
def test_rerun_keeps_leagues_that_did_not_load(tmp_history):
    history.record_report([_row("ENG4", "A", "B"), _row("SCO4", "E", "F")], "2026-10-03")
    history.record_report([_row("ENG4", "A", "B")], "2026-10-03", leagues={"ENG4"})  # SCO4 failed this time
    assert sorted(history.load()["league"]) == ["ENG4", "SCO4"]


def test_rerun_never_duplicates_a_graded_fixture(tmp_history):
    history.record_report([_row("ENG4", "A", "B")], "2026-10-03")
    df = history.load()
    df.loc[0, "status"] = "graded"
    history.save(df)
    history.record_report([_row("ENG4", "A", "B"), _row("ENG4", "C", "D")], "2026-10-03")
    h = history.load()
    assert len(h) == 2 and sorted(h["status"]) == ["graded", "pending"]


# 9. An accumulator week only counts once every leg has a result.
def test_acca_week_with_a_pending_leg_is_not_a_win():
    legs = [dict(_row("ENG4", f"T{i}", "X", acca="leg"), status="graded", o15_hit=True, gibh_hit=False) for i in range(15)]
    legs.append(dict(_row("SCO3", "P", "Q", acca="leg"), status="pending", o15_hit=None, gibh_hit=None))
    a = history.hit_rates(pd.DataFrame(legs))["markets"]["Over 1.5"]["acca"]
    assert (a["weeks"], a["won"], a["open_weeks"]) == (0, 0, 1)
    legs[-1].update(status="graded", o15_hit=False)
    a = history.hit_rates(pd.DataFrame(legs))["markets"]["Over 1.5"]["acca"]
    assert (a["weeks"], a["won"], a["legs"], a["legs_won"]) == (1, 0, 16, 15)
    legs[-1].update(status="void")           # a postponed leg drops out, as the bookmaker settles it
    a = history.hit_rates(pd.DataFrame(legs))["markets"]["Over 1.5"]["acca"]
    assert (a["weeks"], a["won"], a["legs"]) == (1, 1, 15)


# 11. GIBH picks spread across their own bands.
def test_gibh_has_its_own_bands():
    rows = [dict(_row("ENG4", f"T{i}", "X", gibh_combined=p), status="graded", o15_hit=True, gibh_hit=True)
            for i, p in enumerate([52.0, 58.0, 63.0, 67.5, 72.0, 81.0])]
    bands = history.hit_rates(pd.DataFrame(rows))["markets"]["Goal in both halves"]["by_band"]
    assert list(bands) == ["below 55", "55-60", "60-65", "65-70", "70-75", "75+"]


# 3. A report for a future date must not save days that haven't been played.
def test_future_report_date_never_saves_unplayed_days(monkeypatch, tmp_path):
    monkeypatch.setattr(livescore, "STORE", tmp_path)
    monkeypatch.setattr(livescore, "_downloaded", {})
    monkeypatch.setattr(livescore.time, "sleep", lambda s: None)

    class R:
        def json(self):
            return {"Stages": []}
    calls = []
    monkeypatch.setattr(livescore, "fetch", lambda url: calls.append(url) or R())

    class FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 4)          # a Sunday...
    monkeypatch.setattr(livescore, "date", FakeDate)
    livescore._season("north", date(2026, 10, 10))   # ...running next Saturday's report
    saved = sorted(p.name for p in tmp_path.iterdir())
    assert saved[-1] == "2026-09-30.json"            # 4+ days old only; 1-9 Oct stay unsaved
    # 5. each day is downloaded at most once per run, even across leagues
    n = len(calls)
    livescore._season("south", date(2026, 10, 10))
    livescore._season("national", date(2026, 10, 10))
    assert len(calls) == n


# 4. One bad ESPN summary or impossible score must not lose everyone else's results.
def test_grading_survives_bad_fixtures(tmp_history, monkeypatch):
    history.record_report([_row("ENG3", "A", "B"), _row("ENG3", "C", "D"), _row("ENG4", "E", "F")], "2026-10-03")

    def csv(code, on):
        if code == "E3":
            return [{"date": "2026-10-03", "home": "E", "away": "F", "fthg": 2, "ftag": 1, "hthg": 1, "htag": 0}], {}
        return [{"date": "2026-10-03", "home": "C", "away": "D", "fthg": 1, "ftag": 0, "hthg": 1, "htag": 1}], {}
    monkeypatch.setattr(football_data, "load_results", csv)
    monkeypatch.setattr(espn, "scoreboard", lambda slug, d: [
        {"id": "9", "home": "A", "away": "B", "status": "STATUS_FULL_TIME", "home_score": "1", "away_score": "1"}])

    def boom(slug, eid):
        raise RuntimeError("HTTP 502")
    monkeypatch.setattr(espn, "halftime", boom)
    counts = grade_results.grade(today=date(2026, 10, 4))
    h = history.load().set_index("home")
    assert h.loc["E", "status"] == "graded"          # League Two still graded
    assert h.loc["C", "status"] == "unresolved"      # HT 1-1 but FT 1-0: impossible, recorded not raised
    assert h.loc["A", "status"] == "pending"         # ESPN failed: retried next run
    assert counts["graded"] == 1 and counts["unresolved"] == 1


# 10. The grading run refreshes each section's track-record line too.
def test_grading_refreshes_track_lines():
    old_hr = {"graded": 0, "markets": {}}
    page = ("<p>" + render.track_line(old_hr, "o15") + render.track_line(old_hr, "gibh") + "</p>"
            + render.RESULTS_START + "old" + render.RESULTS_END)
    new_hr = {"graded": 4, "markets": {
        "Over 1.5": {"overall": {"n": 4, "hits": 3, "hit_pct": 75.0, "league_avg_pct": 70.0}},
        "Goal in both halves": {"overall": {"n": 4, "hits": 2, "hit_pct": 50.0, "league_avg_pct": 60.0}}}}
    out = render.replace_results(page, "new", new_hr)
    assert "3/4 landed" in out and "2/4 landed" in out and "nothing graded yet" not in out and "new" in out


# 12. Below-the-line reserves follow the same price rule as the legs.
def test_below_line_reserves_respect_min_price():
    cfg = run_report.load_config()
    cfg["odds"]["min_price"] = 1.20

    def row(p, price):
        return {"o15": {"combined_pct": p, "venue_pct": p, "home_gp": 8, "away_gp": 8},
                "data_problem": False, "low_games": False, "price": {"price": price} if price else None}
    rows = [row(0.9, 1.3) for _ in range(16)] + [row(0.79, 1.05), row(0.78, None), row(0.77, 1.25)]
    a = run_report.build_acca(rows, cfg, "o15", odds_on=True)
    assert [r["o15"]["combined_pct"] for r in a["below_line"]] == [0.77]


# Live tables: a club mid-match is one game ahead of the results file - not a data error.
def test_table_check_tolerates_todays_games():
    from football_goals.stats import team_stats
    from football_goals.validate import table_check
    res = [_m("A", "B", 2, 1), _m("B", "C", 0, 0), _m("C", "A", 1, 1)]
    st = team_stats(res)
    live = {"A": {"gp": 3, "gf": 5, "ga": 2}, "B": {"gp": 2, "gf": 1, "ga": 2}, "C": {"gp": 2, "gf": 1, "ga": 1}}
    probs, _ = table_check(st, live, "ESPN")
    assert probs                                      # without knowing A plays today, it's a mismatch
    probs, notes = table_check(st, live, "ESPN", playing=frozenset({"A", "D"}))
    assert probs == [] and "today's game already in the table" in notes[0]
    live["A"]["gp"] = 4                               # two games ahead is still a real problem
    assert table_check(st, live, "ESPN", playing=frozenset({"A"}))[0]


def _m(h, a, fh, fa):
    return {"date": "2026-09-01", "home": h, "away": a, "fthg": fh, "ftag": fa, "hthg": 0, "htag": 0}


# After kick-off on the report day, a re-run must not rewrite that day's record.
def test_history_frozen_once_games_start(monkeypatch):
    from datetime import datetime, timezone
    def at(y, mo, d, hh, mm):  # a UK time (BST in October)
        return datetime(y, mo, d, hh - 1, mm, tzinfo=timezone.utc)
    monkeypatch.setattr(run_report, "uk_now", lambda: at(2026, 10, 3, 14, 59).astimezone(run_report.ZoneInfo("Europe/London")))
    assert not run_report.games_started(date(2026, 10, 3), ["15:00", "17:30"])
    assert run_report.games_started(date(2026, 10, 3), ["12:30", "15:00"])
    assert run_report.games_started(date(2026, 10, 2), [])
    assert not run_report.games_started(date(2026, 10, 10), ["15:00"])
    monkeypatch.setattr(run_report, "uk_now", lambda: at(2026, 10, 3, 15, 7).astimezone(run_report.ZoneInfo("Europe/London")))
    assert run_report.games_started(date(2026, 10, 3), ["15:00"])


# Scottish League One/Two get a second results source for grading.
def test_livescore_scottish_results_match_our_names(monkeypatch):
    feed = {"Stages": [{"Snm": "League One", "Cnm": "Scotland", "Events": [
        {"T1": [{"Nm": "Queen of the South"}], "T2": [{"Nm": "Cove Rangers"}], "Esd": 20261003140000, "Eps": "FT",
         "Tr1": "2", "Tr2": "1", "Trh1": "1", "Trh2": "0"},
        {"T1": [{"Nm": "Airdrieonians"}], "T2": [{"Nm": "Montrose"}], "Esd": 20261003140000, "Eps": "Postp."}]},
        {"Snm": "League One", "Cnm": "England", "Events": []}]}
    parsed = livescore._parse(feed)
    monkeypatch.setattr(livescore, "day", lambda d, today=None, refresh=False: parsed)
    out = livescore.results_by_name("sco3", date(2026, 10, 3), {"Queen of Sth", "Cove Rangers", "Airdrie Utd", "Montrose"})
    assert out[("Queen of Sth", "Cove Rangers")] == {"fthg": 2, "ftag": 1, "hthg": 1, "htag": 0}
    assert out[("Airdrie Utd", "Montrose")] == "void"
