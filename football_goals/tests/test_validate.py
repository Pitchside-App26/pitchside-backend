from football_goals.leagues import League
from football_goals.stats import team_stats
from football_goals.validate import internal_checks, table_check


def m(h, a, ft, ht=(0, 0), d="2026-09-01"):
    return {"date": d, "home": h, "away": a, "fthg": ft[0], "ftag": ft[1], "hthg": ht[0], "htag": ht[1]}


RES = [m("Alpha Town", "Beta", (1, 0)), m("Beta", "Gamma", (2, 2), (1, 1)), m("Gamma", "Alpha Town", (0, 3))]


def test_internal_checks_pass_and_fail():
    lg = League("X", "Test", 3)
    st = team_stats(RES)
    probs, notes = internal_checks(lg, RES, st, [{"home": "Alpha Town", "away": "Beta"}])
    assert probs == [] and notes
    probs, _ = internal_checks(League("X", "Test", 4), RES, st, [{"home": "Delta", "away": "Beta"}])
    assert any("expected 4" in p for p in probs)
    assert any("Delta" in p for p in probs)


def test_table_check_spots_missing_match():
    st = team_stats(RES)
    good = {"Alpha Town FC": {"gp": 2, "gf": 4, "ga": 0}, "Beta": {"gp": 2, "gf": 2, "ga": 3},
            "Gamma": {"gp": 2, "gf": 2, "ga": 5}}
    probs, notes = table_check(st, good, "Test")
    assert probs == [], probs
    stale = dict(good, Beta={"gp": 3, "gf": 3, "ga": 3})
    probs, _ = table_check(st, stale, "Test")
    assert probs and "Beta" in probs[0]


def test_repeat_pairings_allowed_in_scotland_only():
    res = [m("A", "B", (1, 0), d="2026-08-01"), m("A", "B", (2, 0), d="2026-11-01"), m("B", "A", (0, 0))]
    st = team_stats(res)
    eng, _ = internal_checks(League("ENG9", "Test", 2), res, st, [])
    sco, _ = internal_checks(League("SCO9", "Test", 2), res, st, [])
    assert any("more than 1x" in p for p in eng)
    assert not any("more than" in p for p in sco)


def test_gp_outlier_message_is_tagged():
    from football_goals.validate import GP_OUTLIER
    teams = ["A", "B", "C", "D"]
    res = [m(h, a, (1, 0), d=f"2026-0{8 + k}-{i + 10}") for k in range(2) for i, (h, a) in
           enumerate((h, a) for h in teams for a in teams if h != a)]   # 6 games each... x2 = 12
    res.append(m("A", "E", (1, 0), d="2026-10-01"))                     # E has played once
    probs, _ = internal_checks(League("SCO9", "Test", 5), res, team_stats(res), [])
    assert any(p.startswith(GP_OUTLIER) and "E 1" in p for p in probs), probs
