import sqlite3
from datetime import datetime, timezone

import pytest

import integrity
from integrity import find_problems, report
from results_log import _connect

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def _db(tmp_path, rows, analyst_rows=1):
    """rows: (week, player, stat, actual, void, snap_pct, logged_at)."""
    db = str(tmp_path / "log.sqlite3")
    conn = _connect(db)
    conn.executemany(
        "INSERT INTO weekly_output (logged_at, season, week, player_id, player_name, stat_col, line, actual_value, void, "
        "snap_pct) VALUES (?, 2026, ?, ?, ?, ?, 10.5, ?, ?, ?)",
        [(logged, wk, p, p, stat, actual, void, snap) for wk, p, stat, actual, void, snap, logged in rows],
    )
    conn.executemany("INSERT INTO analyst_picks (logged_at, season, week, player_id, stat_col, side, outlet, analyst) "
                     "VALUES ('t', 2026, 6, ?, 'receptions', 'over', 'o', 'a')", [(f"a{i}",) for i in range(analyst_rows)])
    conn.commit()
    conn.close()
    return db


def _healthy_week(n=40, zeros=1, voids=0, week=6):
    rows = [(week, f"p{i}", "receptions", 0.0 if i < zeros else 4.0, 0, 0.8, "2026-10-18") for i in range(n)]
    rows += [(week, f"v{i}", "receptions", None, 1, 0.0, "2026-10-18") for i in range(voids)]
    return rows


def test_a_healthy_week_passes(tmp_path):
    problems = find_problems(_db(tmp_path, _healthy_week()), NOW)
    assert problems == [] and report(problems) == 0


def test_too_many_full_time_players_on_zero_fails(tmp_path):
    problems = find_problems(_db(tmp_path, _healthy_week(zeros=8)), NOW)
    assert any("losing players" in p.message for p in problems)
    assert report(problems) == 1


def test_too_many_voids_fails(tmp_path):
    problems = find_problems(_db(tmp_path, _healthy_week(voids=5)), NOW)
    assert any("snap-count matching" in p.message for p in problems)


def test_props_left_ungraded_too_long_fail(tmp_path):
    rows = _healthy_week() + [(6, "late", "receptions", None, 0, None, "2026-10-01")]
    assert any("still ungraded" in p.message for p in find_problems(_db(tmp_path, rows), NOW))


def test_an_empty_analyst_feed_fails(tmp_path, monkeypatch):
    monkeypatch.setitem(integrity.ANALYST_PICKS, "enabled", True)
    problems = find_problems(_db(tmp_path, _healthy_week(), analyst_rows=0), NOW)
    assert [p.level for p in problems] == ["error"] and "analyst feed" in problems[0].message


def test_problems_go_to_the_github_job_summary(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    report([integrity.Problem("warning", "something odd")])
    assert "something odd" in summary.read_text()
