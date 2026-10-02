from datetime import date

from football_goals.sources import livescore


def ev(h, a, esd, eps, ft=None, ht=None):
    e = {"T1": [{"Nm": h}], "T2": [{"Nm": a}], "Esd": esd, "Eps": eps}
    if ft:
        e.update(Tr1=str(ft[0]), Tr2=str(ft[1]))
    if ht:
        e.update(Trh1=str(ht[0]), Trh2=str(ht[1]))
    return e


FEED = {"Stages": [
    {"Snm": "National League: North", "Cnm": "England", "Events": [
        ev("AFC Telford United", "King's Lynn Town", 20260926140000, "FT", (0, 5), (0, 1)),
        ev("Chester", "Spalding United", 20260926140000, "Postp."),
    ]},
    {"Snm": "National League: South", "Cnm": "England", "Events": [
        ev("Billericay", "Torquay United", 20260926140000, "FT", (3, 0), (2, 0))]},
    {"Snm": "National League", "Cnm": "England", "Events": [
        ev("Aldershot Town", "Tamworth", 20260926140000, "FT", (5, 1), (4, 0))]},
    {"Snm": "National League Championship", "Cnm": "New Zealand", "Events": [
        ev("Wellington Phoenix B", "Auckland United FC", 20260926023000, "FT", (1, 1), (1, 1))]},
]}


def test_parse_keeps_english_stages_and_converts_to_uk_time():
    rows = livescore._parse(FEED)
    north = rows["north"]
    assert len(north) == 2 and len(rows["south"]) == 1 and len(rows["national"]) == 1
    assert north[0] == {"home": "AFC Telford United", "away": "King's Lynn Town", "status": "FT",
                        "date": "2026-09-26", "kickoff": "15:00", "fthg": 0, "ftag": 5, "hthg": 0, "htag": 1}
    assert north[1]["fthg"] is None and livescore._is_off(north[1]["status"])


def test_results_fixtures_and_agreement(monkeypatch):
    parsed = livescore._parse(FEED)
    empty = {k: [] for k in livescore.STAGES}

    def fake_day(d, today=None, refresh=False):
        return parsed if d == date(2026, 9, 26) else empty
    monkeypatch.setattr(livescore, "day", fake_day)

    res, meta = livescore.load_results("north", date(2026, 10, 3))
    assert res == [{"date": "2026-09-26", "home": "AFC Telford United", "away": "King's Lynn Town",
                    "fthg": 0, "ftag": 5, "hthg": 0, "htag": 1}]
    assert meta["latest_result"] == "2026-09-26"

    fx, off = livescore.fixtures_on("north", date(2026, 9, 26))
    assert [f["home"] for f in fx] == ["AFC Telford United"]
    assert off[0]["home"] == "Chester"

    ref = [{"date": "2026-09-26", "home": "Aldershot", "away": "Tamworth", "fthg": 5, "ftag": 1, "hthg": 4, "htag": 0}]
    assert livescore.agreement_with(ref, date(2026, 10, 3))[:2] == (1, 1)
    ref[0]["hthg"] = 3
    agree, n, diffs = livescore.agreement_with(ref, date(2026, 10, 3))
    assert (agree, n) == (0, 1) and "HT 4-0" in diffs[0]
    assert livescore.result_on("north", date(2026, 9, 26), "Chester", "Spalding United") == "void"
    assert livescore.result_on("south", date(2026, 9, 26), "Billericay", "Torquay United") == \
        {"fthg": 3, "ftag": 0, "hthg": 2, "htag": 0}
