"""Durable weekly logging, per the spec's explicit warning that this is a
heuristic blend, not a backtested model -- the ranking is only as good as
its track record, and that track record can't be checked later unless
every week's output is logged now. SQLite, stdlib only.
"""
import sqlite3
from datetime import datetime, timezone

from config import RESULTS_DB_PATH
from rank_props import RankedProp

SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_output (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    player_id TEXT,
    player_name TEXT,
    stat_col TEXT,
    line REAL,
    projection REAL,
    edge_score REAL,
    direction TEXT,
    hit_rate REAL,
    sample_size INTEGER,
    method TEXT,
    confidence TEXT,
    actual_value REAL,
    graded_at TEXT
);
"""


def _connect(db_path: str = RESULTS_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    return conn


def log_weekly_output(ranked: list[RankedProp], season: int, week: int, db_path: str = RESULTS_DB_PATH) -> int:
    logged_at = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            """INSERT INTO weekly_output
               (logged_at, season, week, player_id, player_name, stat_col, line, projection,
                edge_score, direction, hit_rate, sample_size, method, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    logged_at, season, week, p.player_id, p.player_name, p.stat_col, p.line,
                    p.projection, p.edge_score, p.direction, p.hit_rate, p.sample_size,
                    p.method, p.confidence,
                )
                for p in ranked
            ],
        )
    conn.close()
    return len(ranked)


def grade_week(season: int, week: int, actuals: dict[tuple[str, str], float], db_path: str = RESULTS_DB_PATH) -> int:
    """actuals: {(player_id, stat_col): actual_value}. Call this once real
    results are in, to close the loop on whether the ranking is worth
    trusting past week one."""
    conn = _connect(db_path)
    graded_at = datetime.now(timezone.utc).isoformat()
    count = 0
    with conn:
        cur = conn.execute(
            "SELECT id, player_id, stat_col FROM weekly_output WHERE season=? AND week=?",
            (season, week),
        )
        for row_id, player_id, stat_col in cur.fetchall():
            actual = actuals.get((player_id, stat_col))
            if actual is not None:
                conn.execute(
                    "UPDATE weekly_output SET actual_value=?, graded_at=? WHERE id=?",
                    (actual, graded_at, row_id),
                )
                count += 1
    conn.close()
    return count
