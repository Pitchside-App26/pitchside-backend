"""Locked accumulator picks.

Once a Saturday's accumulators have been published close to the day (from the
day before), they are saved to data/picks/<date>.json and every later run for
that date shows the same legs and reserves in the same order. The stats on the
page still refresh, but the legs never change under someone who has already
bet them. A run with --repick (the workflow's "repick" box) replaces the lock.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

DIR = Path(__file__).parent / "data" / "picks"
PARTS = ("legs", "reserves", "below_line")


def _path(on: date) -> Path:
    return DIR / f"{on.isoformat()}.json"


def key(r) -> list[str]:
    return [r["league"], r["home"], r["away"]]


def load(on: date) -> dict | None:
    p = _path(on)
    return json.loads(p.read_text()) if p.exists() else None


def should_lock(on: date, today: date) -> bool:
    """Lock from the day before onwards: earlier runs (e.g. a Tuesday look-ahead)
    are previews built on data that will change before the weekend."""
    return (on - today).days <= 1


def save(on: date, accas: dict) -> dict:
    lock = {"locked_at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
    for mk, a in accas.items():
        if a["legs"]:
            lock[mk] = {part: [key(r) for r in a.get(part) or []] for part in PARTS}
    if not any(mk in lock for mk in accas):
        return {}
    DIR.mkdir(parents=True, exist_ok=True)
    _path(on).write_text(json.dumps(lock, indent=1) + "\n")
    return lock


def apply(rows, market: str, tag: str, lock_mk: dict, built: dict, locked_at: str) -> dict:
    """Rebuild `built` (a fresh build_acca result) from the locked picks.

    Locked fixtures that have dropped out (postponed, league failed to load)
    are reported, not replaced: the next reserve covers them on the slip."""
    by_key = {tuple(key(r)): r for r in rows}
    for r in rows:
        r.pop(tag, None)
    out, missing, flagged = {}, [], []
    for part in PARTS:
        out[part] = []
        for k in lock_mk.get(part, []):
            r = by_key.get(tuple(k))
            if r is None:
                missing.append(f"{k[1]} v {k[2]}")
                continue
            out[part].append(r)
            if part == "legs" and r.get("data_problem"):
                flagged.append(f"{r['home']} v {r['away']}")
    for r in out["legs"]:
        r[tag] = "leg"
    for r in out["reserves"]:
        r[tag] = "reserve"
    for r in out["below_line"]:
        r[tag] = "below_line"
    when = datetime.fromisoformat(locked_at).strftime("%a %H:%M UTC")
    k, n = len(out["legs"]), len(out["reserves"]) + len(out["below_line"])
    msg = f"{k}-fold with {n} reserve{'s' if n != 1 else ''}, locked as published {when}; later updates refresh the stats, not the picks."
    if missing:
        msg += f" No longer on the fixture list (postponed or not loaded): {', '.join(missing)} - swap in a reserve."
    if flagged:
        msg += f" Now flagged by a data check: {', '.join(flagged)}."
    return dict(built, legs=out["legs"], reserves=out["reserves"], below_line=out["below_line"],
                message=msg, locked=True)
