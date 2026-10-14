import sqlite3

import pandas as pd
import pytest

from grade_results import _direction_hit, _match_actual, _ungraded_pairs, print_report
from participation import week_participation
from results_log import SCHEMA


def test_direction_hit_over():
    assert _direction_hit("over", 50.5, 60.0) == "hit"
    assert _direction_hit("over", 50.5, 40.0) == "miss"


def test_direction_hit_under():
    assert _direction_hit("under", 50.5, 40.0) == "hit"
    assert _direction_hit("under", 50.5, 60.0) == "miss"


def test_direction_hit_push_on_exact_line():
    assert _direction_hit("over", 50.0, 50.0) == "push"


def test_match_actual_none_when_team_game_not_final():
    result = _match_actual("DEN", "rushing_yards", completed_teams=set(), offense_by_player={}, defense_by_player={}, player_id="p1")
    assert result is None


def _sheet(*rows, week=1):
    """A snap-count sheet: (player, pfr_id, team, offense, defense, special teams)."""
    return week_participation(pd.DataFrame([
        {"week": week, "player": p, "pfr_player_id": pfr, "team": t, "offense_snaps": o, "offense_pct": o / 60,
         "defense_snaps": d, "defense_pct": d / 60, "st_snaps": st}
        for p, pfr, t, o, d, st in rows
    ]), week)


SHEET = _sheet(("Puka Nacua", "NacuPu00", "LA", 0, 0, 0),  # listed with no snaps: did not play
               ("Davis Allen", "AlleDa00", "LA", 30, 0, 5),
               ("Gunner Guy", "GuyGu00", "LA", 0, 0, 12))


def _grade(player_id, stats=None, participation=SHEET, pfr_id=None, name=None, team="LA"):
    return _match_actual(team, "receiving_yards", {"LA"}, stats or {}, {}, player_id, participation,
                         pfr_id=pfr_id, name=name)


def test_a_player_who_took_no_snaps_is_void_not_zero():
    assert _grade("p1", pfr_id="NacuPu00").void
    assert _grade("p2", pfr_id="NobodyX00", name="Not On The Sheet").void


def test_a_player_who_played_and_recorded_nothing_is_a_real_zero():
    outcome = _grade("p1", pfr_id="AlleDa00")
    assert (outcome.value, outcome.snap_pct) == (0.0, 0.5)


def test_special_teams_snaps_count_as_playing():
    assert _grade("p1", pfr_id="GuyGu00").value == 0.0


def test_a_player_without_a_pfr_id_is_found_by_name():
    assert _grade("p1", name="Davis Allen Jr.").value == 0.0


def test_no_stats_waits_for_the_snap_sheet_rather_than_guessing():
    assert _grade("p1", pfr_id="AlleDa00", participation=None) is None
    assert _grade("p1", pfr_id="AlleDa00", participation=_sheet(("X", "X00", "KC", 50, 0, 0))) is None


def test_match_actual_uses_real_value_when_present():
    offense_by_player = {"p1": {"receiving_yards": 42.0}}
    result = _match_actual(
        "DEN", "receiving_yards", completed_teams={"DEN"}, offense_by_player=offense_by_player,
        defense_by_player={}, player_id="p1",
    )
    assert result.value == 42.0


def test_a_stats_row_means_he_played_even_without_the_stat():
    result = _match_actual("DEN", "receiving_yards", {"DEN"}, {"p1": {"rushing_yards": 30.0}}, {}, "p1")
    assert result.value == 0.0


def test_match_actual_falls_back_to_defense_frame():
    defense_by_player = {"p1": {"def_tackles": 7.0}}
    result = _match_actual(
        "DEN", "def_tackles", completed_teams={"DEN"}, offense_by_player={},
        defense_by_player=defense_by_player, player_id="p1",
    )
    assert result.value == 7.0


def _seed_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    conn.executemany(
        """INSERT INTO weekly_output
           (logged_at, season, week, player_id, player_name, stat_col, line, projection,
            edge_score, direction, hit_rate, sample_size, method, confidence, actual_value, graded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()


def test_ungraded_pairs_only_returns_rows_missing_actual_value(tmp_path):
    db_path = str(tmp_path / "test.sqlite3")
    _seed_db(db_path, [
        ("t", 2026, 1, "p1", "Player One", "receiving_yards", 40.0, 50.0, 0.5, "over", None, 0, "veteran", "normal", None, None),
        ("t", 2026, 1, "p2", "Player Two", "carries", 10.0, 12.0, 0.3, "over", None, 0, "veteran", "normal", 15.0, "t"),
    ])
    pairs = _ungraded_pairs(2026, 1, db_path)
    assert pairs == {("p1", "receiving_yards")}


def test_print_report_hit_rate_math(tmp_path, capsys):
    db_path = str(tmp_path / "test.sqlite3")
    _seed_db(db_path, [
        # over, line 40, actual 50 -> hit
        ("t", 2026, 1, "p1", "Player One", "receiving_yards", 40.0, 55.0, 0.9, "over", None, 0, "veteran", "normal", 50.0, "g"),
        # over, line 40, actual 30 -> miss
        ("t", 2026, 1, "p2", "Player Two", "receiving_yards", 40.0, 55.0, 0.9, "over", None, 0, "veteran", "normal", 30.0, "g"),
        # under, line 10, actual 10 -> push, excluded from hit-rate denominator
        ("t", 2026, 1, "p3", "Player Three", "carries", 10.0, 8.0, 0.2, "under", None, 0, "veteran", "normal", 10.0, "g"),
    ])
    print_report(db_path)
    out = capsys.readouterr().out
    assert "n=3" in out  # overall row count includes the push
    assert "hit=1" in out
    assert "miss=1" in out
    assert "hit-rate=50.0%" in out  # 1 hit / (1 hit + 1 miss), push excluded


# --- accumulator-report legs ----------------------------------------------------

from grade_results import acca_groups
from results_log import grade_acca_week, log_acca_legs


def _acca_row(player_id, passed=True, selected=False, checked=True, n_over=0, n_under=0, max_line=50.5, stat="rushing_yards",
              filler=False):
    return {
        "player_id": player_id, "player_name": player_id, "stat_col": stat, "market": "player_rush_yds",
        "game": "NE @ BUF", "consensus_line": max_line - 2, "max_line": max_line, "projection": 60.0,
        "fair_prob": 0.5, "passed_gates": passed, "failed_gates": None if passed else "form",
        "selected": selected, "filler": filler, "window": "early", "sources_checked": checked,
        "n_over_sources": n_over if checked else None, "n_under_sources": n_under if checked else None,
    }


def test_acca_legs_are_logged_graded_and_grouped(tmp_path):
    db = str(tmp_path / "log.sqlite3")
    log_acca_legs([
        _acca_row("backed", n_over=2, selected=True),
        _acca_row("lonely", n_over=0),
        _acca_row("unchecked", checked=False),
        _acca_row("failed", passed=False, checked=False, selected=True, filler=True),
    ], 2026, 4, db_path=db)

    # Weeks/pairs needing grades now include acca legs.
    assert ("backed", "rushing_yards") in _ungraded_pairs(2026, 4, db_path=db)

    n = grade_acca_week(2026, 4, {("backed", "rushing_yards"): 70.0, ("lonely", "rushing_yards"): 40.0,
                                  ("unchecked", "rushing_yards"): 51.0, ("failed", "rushing_yards"): 20.0}, db_path=db)
    assert n == 4

    conn = sqlite3.connect(db)
    df = pd.read_sql_query("SELECT * FROM acca_legs", conn)
    conn.close()
    groups = {label: rows for label, rows in acca_groups(df)}
    assert list(groups["passed every gate"]["outcome"]) == ["hit", "miss", "hit"]
    assert list(groups["failed a gate"]["outcome"]) == ["miss"]
    assert list(groups["passed, 2+ analysts"]["player_id"]) == ["backed"]
    assert list(groups["passed, 0 analysts"]["player_id"]) == ["lonely"]
    assert list(groups["passed, not checked"]["player_id"]) == ["unchecked"]
    assert list(groups["selected, passed every gate"]["player_id"]) == ["backed"]
    assert list(groups["selected as a filler"]["player_id"]) == ["failed"]


def test_acca_groups_count_a_leg_once_per_week_from_its_latest_run(tmp_path):
    db = str(tmp_path / "log.sqlite3")
    log_acca_legs([_acca_row("p", n_over=0)], 2026, 4, db_path=db)   # Thursday test run
    log_acca_legs([_acca_row("p", n_over=2)], 2026, 4, db_path=db)   # Sunday run
    grade_acca_week(2026, 4, {("p", "rushing_yards"): 70.0}, db_path=db)
    conn = sqlite3.connect(db)
    df = pd.read_sql_query("SELECT * FROM acca_legs", conn)
    conn.close()
    groups = {label: rows for label, rows in acca_groups(df)}
    assert len(groups["passed every gate"]) == 1
    assert list(groups["passed, 2+ analysts"]["player_id"]) == ["p"]


def test_grading_never_overwrites_an_already_graded_acca_leg(tmp_path):
    db = str(tmp_path / "log.sqlite3")
    log_acca_legs([_acca_row("p")], 2026, 4, db_path=db)
    grade_acca_week(2026, 4, {("p", "rushing_yards"): 70.0}, db_path=db)
    assert grade_acca_week(2026, 4, {("p", "rushing_yards"): 10.0}, db_path=db) == 0


def test_bet_profit_at_american_prices():
    from grade_results import bet_profit

    assert bet_profit("over", 50.5, 60, -110) == pytest.approx(100 / 110)
    assert bet_profit("under", 50.5, 60, -110) == -1.0
    assert bet_profit("over", 50.0, 50, 120) == 0.0  # push returns the stake
    assert bet_profit("under", 0.5, 0, -300) == pytest.approx(1 / 3)
    assert bet_profit("over", 50.5, 60, None) is None


def test_prices_are_logged_and_judged_on_profit(tmp_path):
    import sqlite3

    import pandas as pd

    from grade_results import profit_groups
    from projection_engine import Projection
    from rank_props import build_ranked_prop
    from results_log import grade_week, log_weekly_output

    db = str(tmp_path / "log.sqlite3")
    proj = Projection(player_id="p1", player_name="P", stat_col="rushing_yards", projection=70.0, season_std=10.0,
                      n_current_games=4, n_prior_games=0, method="veteran", confidence="normal")
    prop = build_ranked_prop(proj, 60.5, [], over_price=-120, under_price=100, bookmaker="draftkings")
    assert (prop.over_price, prop.under_price, prop.bookmaker) == (-120, 100, "draftkings")
    log_weekly_output([prop], 2026, 5, db)
    grade_week(2026, 5, {("p1", "rushing_yards"): 80.0}, db)
    df = pd.read_sql_query("SELECT * FROM weekly_output", sqlite3.connect(db))
    assert df.loc[0, "market_over_prob"] == pytest.approx((120 / 220) / (120 / 220 + 0.5))
    groups = dict(profit_groups(df))
    assert groups["every over"] == [pytest.approx(100 / 120)]
    assert groups["every under"] == [-1.0]
    assert groups["the engine's picks"] == [pytest.approx(100 / 120)]  # engine picked the over


def test_an_old_database_gets_the_price_columns(tmp_path):
    import sqlite3

    from results_log import _connect

    db = str(tmp_path / "old.sqlite3")
    old = sqlite3.connect(db)
    old.execute("CREATE TABLE weekly_output (id INTEGER PRIMARY KEY, logged_at TEXT, season INTEGER, week INTEGER, "
                "player_id TEXT, player_name TEXT, stat_col TEXT, line REAL, projection REAL, edge_score REAL, "
                "direction TEXT, hit_rate REAL, sample_size INTEGER, method TEXT, confidence TEXT, "
                "actual_value REAL, graded_at TEXT)")
    old.commit(); old.close()
    cols = {r[1] for r in _connect(db).execute("PRAGMA table_info(weekly_output)")}
    assert {"over_price", "under_price", "bookmaker", "market_over_prob"} <= cols


# --- voids and one row per prop ------------------------------------------------

def test_a_void_prop_is_settled_and_left_out_of_the_hit_rate(tmp_path, capsys):
    from results_log import VOID, grade_week

    db = str(tmp_path / "log.sqlite3")
    _seed_db(db, [
        ("t", 2026, 2, "nacua", "Puka Nacua", "receiving_yards", 85.5, 80.0, -0.2, "under", None, 0, "veteran", "normal", None, None),
        ("t", 2026, 2, "p2", "Player Two", "receiving_yards", 40.0, 50.0, 0.5, "over", None, 0, "veteran", "normal", None, None),
    ])
    assert grade_week(2026, 2, {("nacua", "receiving_yards"): VOID, ("p2", "receiving_yards"): 50.0}, db) == 2
    assert _ungraded_pairs(2026, 2, db) == set()  # a void is settled, not retried every week
    print_report(db)
    out = capsys.readouterr().out
    assert "1 graded props" in out and "1 more were void" in out
    assert "hit=1" in out and "miss=0" in out  # the injured player's under is not a win


def test_a_regrade_replaces_an_old_zero_with_a_void(tmp_path):
    from results_log import VOID, grade_week

    db = str(tmp_path / "log.sqlite3")
    _seed_db(db, [("t", 2026, 2, "nacua", "Puka Nacua", "receiving_yards", 85.5, 80.0, -0.2, "under", None, 0,
                   "veteran", "normal", 0.0, "old")])
    assert grade_week(2026, 2, {("nacua", "receiving_yards"): VOID}, db) == 0  # graded rows are left alone...
    assert grade_week(2026, 2, {("nacua", "receiving_yards"): VOID}, db, overwrite=True) == 1  # ...unless regrading
    row = sqlite3.connect(db).execute("SELECT actual_value, void FROM weekly_output").fetchone()
    assert row == (None, 1)
    assert _ungraded_pairs(2026, 2, db, regrade=True) == {("nacua", "receiving_yards")}


def test_a_rerun_replaces_the_weeks_rows_instead_of_adding_more(tmp_path):
    db = str(tmp_path / "log.sqlite3")
    for n_over in (0, 1, 2):
        log_acca_legs([_acca_row("p", n_over=n_over)], 2026, 4, db_path=db)
    rows = sqlite3.connect(db).execute("SELECT n_over_sources FROM acca_legs").fetchall()
    assert rows == [(2,)]  # one row, from the latest run


def test_an_old_database_with_duplicates_keeps_the_latest_row_per_prop(tmp_path):
    from results_log import _connect

    db = str(tmp_path / "log.sqlite3")
    _seed_db(db, [
        ("run1", 2026, 1, "p1", "P", "receptions", 4.5, 5.0, 0.1, "over", None, 0, "veteran", "normal", 6.0, "g"),
        ("run2", 2026, 1, "p1", "P", "receptions", 4.5, 5.2, 0.1, "over", None, 0, "veteran", "normal", 6.0, "g"),
        ("run2", 2026, 1, "p1", "P", "receiving_yards", 40.5, 45.0, 0.1, "over", None, 0, "veteran", "normal", 50.0, "g"),
        ("run2", 2026, 2, "p1", "P", "receptions", 4.5, 5.0, 0.1, "over", None, 0, "veteran", "normal", 3.0, "g"),
    ])
    rows = _connect(db).execute("SELECT logged_at, week, stat_col FROM weekly_output ORDER BY id").fetchall()
    assert rows == [("run2", 1, "receptions"), ("run2", 1, "receiving_yards"), ("run2", 2, "receptions")]
