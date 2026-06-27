"""
SQLite-backed logger for all recommended bets.

Schema
------
bets           — one row per bet, pending until result filled in
bankroll       — running balance ledger (deposits + bet settlements)

CLV (closing-line value) is recorded post-kick-off via update_closing_odds().
The only honest scoreboard is cumulative CLV over hundreds of bets —
short-term P/L is noise.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from .config import LOG_DB_PATH

log = logging.getLogger(__name__)

_CREATE_BETS = """
CREATE TABLE IF NOT EXISTS bets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date           TEXT NOT NULL,          -- ISO date of the weekly scan
    league              TEXT NOT NULL,
    fixture             TEXT NOT NULL,
    fixture_id          TEXT,                   -- API event ID (for CLV lookup)
    sport_key           TEXT,                   -- API sport key (for CLV lookup)
    market              TEXT NOT NULL,          -- h2h | totals | btts
    selection           TEXT NOT NULL,
    book                TEXT NOT NULL,
    odds_taken          REAL NOT NULL,
    true_p              REAL NOT NULL,          -- de-vigged Pinnacle probability
    fair_odds           REAL NOT NULL,          -- 1 / true_p
    edge_pct            REAL NOT NULL,          -- edge × 100
    stake               REAL NOT NULL,
    slip_type           TEXT NOT NULL,          -- single | double | treble
    result              TEXT NOT NULL DEFAULT 'pending', -- pending | win | loss | void
    pnl                 REAL,                   -- profit/loss when settled
    closing_pinnacle_odds REAL,                 -- filled in post-kick-off
    clv                 REAL,                   -- closing-line value (positive = good)
    running_bankroll    REAL                    -- balance after settlement
)
"""

_CREATE_BANKROLL = """
CREATE TABLE IF NOT EXISTS bankroll (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date    TEXT NOT NULL,
    type    TEXT NOT NULL,   -- deposit | bet | win | loss | void
    amount  REAL NOT NULL,   -- positive = in, negative = out
    balance REAL NOT NULL,
    note    TEXT
)
"""


@contextmanager
def _conn(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(db_path: str = LOG_DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _conn(db_path) as con:
        con.execute(_CREATE_BETS)
        con.execute(_CREATE_BANKROLL)
    log.info("DB initialised at %s", db_path)


def get_balance(db_path: str = LOG_DB_PATH) -> float:
    with _conn(db_path) as con:
        row = con.execute(
            "SELECT balance FROM bankroll ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return float(row["balance"]) if row else 0.0


def record_deposit(
    amount: float,
    note: str = "monthly top-up",
    db_path: str = LOG_DB_PATH,
) -> float:
    balance = get_balance(db_path) + amount
    with _conn(db_path) as con:
        con.execute(
            "INSERT INTO bankroll (date, type, amount, balance, note) VALUES (?,?,?,?,?)",
            (now_iso(), "deposit", amount, balance, note),
        )
    log.info("Deposit £%.2f recorded. New balance: £%.2f", amount, balance)
    return balance


def log_bet(
    *,
    scan_date: str,
    league: str,
    fixture: str,
    fixture_id: str,
    sport_key: str,
    market: str,
    selection: str,
    book: str,
    odds_taken: float,
    true_p: float,
    fair_odds: float,
    edge_pct: float,
    stake: float,
    slip_type: str,
    running_bankroll: float,
    db_path: str = LOG_DB_PATH,
) -> int:
    """Insert a new pending bet and deduct the stake from the bankroll ledger."""
    with _conn(db_path) as con:
        cur = con.execute(
            """INSERT INTO bets
               (scan_date, league, fixture, fixture_id, sport_key,
                market, selection, book, odds_taken, true_p, fair_odds,
                edge_pct, stake, slip_type, running_bankroll)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                scan_date, league, fixture, fixture_id, sport_key,
                market, selection, book, odds_taken, true_p, fair_odds,
                edge_pct, stake, slip_type, running_bankroll,
            ),
        )
        bet_id = cur.lastrowid

        new_balance = running_bankroll - stake
        con.execute(
            "INSERT INTO bankroll (date, type, amount, balance, note) VALUES (?,?,?,?,?)",
            (now_iso(), "bet", -stake, new_balance, f"bet #{bet_id}: {fixture} — {selection}"),
        )

    log.info("Logged bet #%d: %s | %s | %s @ %.2f (edge %.1f%%)",
             bet_id, fixture, selection, book, odds_taken, edge_pct)
    return bet_id


def settle_bet(
    bet_id: int,
    result: str,         # "win" | "loss" | "void"
    db_path: str = LOG_DB_PATH,
) -> float:
    """Record the result and update the bankroll. Returns updated balance."""
    with _conn(db_path) as con:
        row = con.execute(
            "SELECT odds_taken, stake FROM bets WHERE id = ?", (bet_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Bet #{bet_id} not found in DB.")

        odds = row["odds_taken"]
        stake = row["stake"]

        if result == "win":
            pnl = stake * (odds - 1.0)
        elif result == "void":
            pnl = 0.0
        else:
            pnl = -stake

        balance_before = get_balance(db_path)
        new_balance = balance_before + stake + (pnl if result == "win" else 0.0)
        if result == "void":
            new_balance = balance_before + stake

        con.execute(
            "UPDATE bets SET result=?, pnl=?, running_bankroll=? WHERE id=?",
            (result, pnl, new_balance, bet_id),
        )
        ledger_type = result  # "win" | "loss" | "void"
        ledger_amount = pnl if result == "win" else (stake if result == "void" else 0.0)
        con.execute(
            "INSERT INTO bankroll (date, type, amount, balance, note) VALUES (?,?,?,?,?)",
            (now_iso(), ledger_type, ledger_amount, new_balance, f"settle bet #{bet_id}"),
        )

    log.info("Settled bet #%d as %s (P/L: £%.2f). Balance: £%.2f",
             bet_id, result, pnl, new_balance)
    return new_balance


def update_closing_odds(
    bet_id: int,
    closing_pinnacle_odds: float,
    db_path: str = LOG_DB_PATH,
) -> float:
    """
    Record Pinnacle's closing price and compute CLV.

    CLV = (taken_odds / closing_odds) - 1
    Positive means we took a better price than the closing sharp line.
    """
    with _conn(db_path) as con:
        row = con.execute(
            "SELECT odds_taken FROM bets WHERE id = ?", (bet_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Bet #{bet_id} not found.")
        clv = (row["odds_taken"] / closing_pinnacle_odds) - 1.0
        con.execute(
            "UPDATE bets SET closing_pinnacle_odds=?, clv=? WHERE id=?",
            (closing_pinnacle_odds, clv, bet_id),
        )
    return clv


def clv_summary(db_path: str = LOG_DB_PATH) -> dict:
    """Aggregate CLV stats across all settled bets with closing odds recorded."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT clv, edge_pct, result FROM bets WHERE clv IS NOT NULL"
        ).fetchall()

    if not rows:
        return {"count": 0, "avg_clv": None, "avg_edge": None}

    clvs = [r["clv"] for r in rows]
    edges = [r["edge_pct"] for r in rows]
    return {
        "count": len(clvs),
        "avg_clv": sum(clvs) / len(clvs),
        "avg_edge_at_rec": sum(edges) / len(edges),
        "positive_clv_rate": sum(1 for c in clvs if c > 0) / len(clvs),
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
