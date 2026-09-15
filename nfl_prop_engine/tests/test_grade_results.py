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
