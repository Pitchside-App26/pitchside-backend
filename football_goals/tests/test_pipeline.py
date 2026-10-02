"""End-to-end run on fake data (no network): report, acca, history, grading."""
import random
from datetime import date

import pandas as pd
import pytest

from football_goals import grade_results, history, render, run_report
from football_goals.sources import api_football, espn, football_data

DAY = date(2026, 10, 3)


def _league_results(teams, rounds, seed):
    """Circle-method round robin, so no pairing repeats."""
    rnd = random.Random(seed)
    rows = []
    t = list(teams)
    for i in range(rounds):
        for j in range(len(t) // 2):
            h, a = (t[j], t[-1 - j]) if i % 2 == 0 else (t[-1 - j], t[j])
            ft = (rnd.randint(0, 3), rnd.randint(0, 2))
            ht = (rnd.randint(0, ft[0]), rnd.randint(0, ft[1]))
            rows.append({"date": f"2026-09-{i + 1:02d}", "home": h, "away": a,
                         "fthg": ft[0], "ftag": ft[1], "hthg": ht[0], "htag": ht[1]})
        t = [t[0]] + [t[-1]] + t[1:-1]
    return rows


@pytest.fixture
def fake(monkeypatch, tmp_path):
    from football_goals.leagues import LEAGUES
    data = {}
    for n, lg in enumerate(LEAGUES):
        teams = [f"{lg.key} Club {i}" for i in range(lg.teams)]
        data[lg.key] = (teams, _league_results(teams, 8, n))
    fd = {lg.fd_code: lg.key for lg in LEAGUES if lg.fd_code}

    def load_results(code, on):
        rows = [r for r in data[fd[code]][1] if r["date"] < on.isoformat()]
        return rows, {"source": "football-data.co.uk", "latest_result": max(r["date"] for r in rows), "last_modified": "x"}

    def load_fixtures(on):
        out = {}
        for code, key in fd.items():
            t = data[key][0]
            out[code] = [{"home": t[i], "away": t[i + 1], "kickoff": "15:00"} for i in range(0, len(t), 2)]
        return out, {}

    def scoreboard(slug, on):
        key = next(lg.key for lg in LEAGUES if lg.espn_slug == slug)
        t = data[key][0]
        evs = [{"id": "1", "home": t[0], "away": t[1], "status": "STATUS_POSTPONED", "kickoff": "15:00"}]
        return evs

    def standings(slug):
        return {}  # empty published table -> the league gets a data-check flag

    monkeypatch.setattr(football_data, "load_results", load_results)
    monkeypatch.setattr(football_data, "load_fixtures", load_fixtures)
    monkeypatch.setattr(espn, "scoreboard", scoreboard)
    monkeypatch.setattr(espn, "standings", standings)
    monkeypatch.setenv("API_FOOTBALL_KEY", "")
    monkeypatch.setattr(history, "HISTORY", tmp_path / "history.csv")
    return data


def test_full_run_and_grade(fake, monkeypatch, tmp_path):
    cfg = run_report.load_config()
    rep = run_report.run(DAY, cfg)
    names = {f["league"].name for f in rep["failed"]}
    assert names == {"National League North", "National League South"}
    assert all("API_FOOTBALL_KEY" in f["reason"] for f in rep["failed"])
    assert len(rep["postponed"]) == 7  # one per ESPN-covered league (ENG1-5, SCO1-2)
    # postponed fixtures are gone from the tables
    assert not any(r["home"].endswith("Club 0") and r["away"].endswith("Club 1") and r["league"] in
                   {"ENG1", "ENG2", "ENG3", "ENG4", "ENG5", "SCO1", "SCO2"} for r in rep["o15"])
    combs = [r["o15"]["combined_pct"] for r in rep["o15"]]
    assert combs == sorted(combs, reverse=True)
    html = render.html(rep)
    assert "Leagues not loaded" in html and "National League North" in html
    render.csv(rep, tmp_path / "r.csv")
    assert len(pd.read_csv(tmp_path / "r.csv")) == 2 * len(rep["o15"])
    assert (tmp_path / "history.csv").exists()
    h = history.load()
    assert len(h) == len(rep["o15"]) and set(h["status"]) == {"pending"}

    # Grade: pretend football-data now has the results for 3 Oct
    def load_results_after(code, on):
        rows = [{"date": DAY.isoformat(), "home": r["home"], "away": r["away"], "fthg": 1, "ftag": 1,
                 "hthg": 1, "htag": 0} for _, r in h.iterrows()]
        return rows, {}
    monkeypatch.setattr(football_data, "load_results", load_results_after)
    counts = grade_results.grade(today=date(2026, 10, 4))
    assert counts["graded"] == len(h)
    g = history.load()
    assert set(g["status"]) == {"graded"}
    assert g["o15_hit"].astype(str).str.lower().eq("true").all()
    assert g["gibh_hit"].astype(str).str.lower().eq("true").all()
    hr = history.hit_rates()
    assert hr["markets"]["Over 1.5"]["overall"]["hit_pct"] == 100
    assert "Track record" in render.results_page(g, hr)


def test_acca_sizes():
    cfg = run_report.load_config()

    def row(p):
        return {"o15": {"combined_pct": p, "venue_pct": p, "home_gp": 8, "away_gp": 8},
                "data_problem": False, "low_games": False}
    a = run_report.build_acca([row(0.9) for _ in range(25)], cfg, False)
    assert (len(a["legs"]), len(a["reserves"])) == (18, 4)
    a = run_report.build_acca([row(0.9) for _ in range(18)], cfg, False)
    assert (len(a["legs"]), len(a["reserves"])) == (16, 2)
    a = run_report.build_acca([row(0.9) for _ in range(5)] + [row(0.5)], cfg, False)
    assert a["legs"] == [] and len(a["reserves"]) == 5 and "Only 5 fixtures qualify" in a["message"]


def test_next_saturday():
    assert run_report.next_saturday(date(2026, 10, 2)) == date(2026, 10, 3)
    assert run_report.next_saturday(date(2026, 10, 3)) == date(2026, 10, 3)
    assert run_report.next_saturday(date(2026, 10, 4)) == date(2026, 10, 10)
