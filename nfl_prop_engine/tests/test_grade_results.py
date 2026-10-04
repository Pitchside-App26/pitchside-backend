import sqlite3

import pandas as pd
import pytest

from grade_results import _direction_hit, _match_actual, _ungraded_pairs, print_report
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


def test_match_actual_zero_when_game_final_but_no_stat_row():
    # Game's over (DEN is in completed_teams) but this player has no row at
    # all in either stats frame -- graded as 0, not left ungraded.
    result = _match_actual(
        "DEN", "receiving_yards", completed_teams={"DEN"}, offense_by_player={}, defense_by_player={}, player_id="p1",
    )
    assert result == 0.0


def test_match_actual_uses_real_value_when_present():
    offense_by_player = {"p1": {"receiving_yards": 42.0}}
    result = _match_actual(
        "DEN", "receiving_yards", completed_teams={"DEN"}, offense_by_player=offense_by_player,
        defense_by_player={}, player_id="p1",
    )
    assert result == 42.0


def test_match_actual_falls_back_to_defense_frame():
    defense_by_player = {"p1": {"def_tackles": 7.0}}
    result = _match_actual(
        "DEN", "def_tackles", completed_teams={"DEN"}, offense_by_player={},
        defense_by_player=defense_by_player, player_id="p1",
    )
    assert result == 7.0


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
