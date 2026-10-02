"""football-data.co.uk: season results (with half-time scores) and the
upcoming fixtures list. Free CSVs, no key."""
from __future__ import annotations

import io
import logging
from datetime import date, datetime

import pandas as pd

from ..http_cache import fetch

log = logging.getLogger(__name__)
BASE = "https://www.football-data.co.uk"


def season_code(d: date) -> str:
    """2026-10-03 -> '2627' (seasons roll over in July)."""
    start = d.year if d.month >= 7 else d.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def _read_csv(content: bytes) -> pd.DataFrame:
    text = content.decode("latin-1").lstrip("﻿").lstrip("ï»¿")
    df = pd.read_csv(io.StringIO(text))
    return df.dropna(how="all")


def _parse_dates(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce").fillna(
        pd.to_datetime(s, format="%d/%m/%y", errors="coerce"))


def load_results(fd_code: str, on: date):
    """Completed league results this season. Returns (rows, meta)."""
    url = f"{BASE}/mmz4281/{season_code(on)}/{fd_code}.csv"
    r = fetch(url)
    df = _read_csv(r.content)
    need = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "HTHG", "HTAG"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"{fd_code}: CSV lacks columns {missing}")
    df["date"] = _parse_dates(df["Date"])
    complete = df.dropna(subset=need)
    dropped = len(df) - len(complete)
    if dropped:
        log.warning("%s: %d rows lack a full-time or half-time score and were skipped", fd_code, dropped)
    complete = complete[complete["date"].dt.date < on]
    rows = [{
        "date": d.date().isoformat(), "home": h.strip(), "away": a.strip(),
        "fthg": int(fh), "ftag": int(fa), "hthg": int(hh), "htag": int(ha),
    } for d, h, a, fh, fa, hh, ha in complete[["date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "HTHG", "HTAG"]].itertuples(index=False)]
    meta = {
        "source": "football-data.co.uk",
        "url": url,
        "last_modified": r.headers.get("Last-Modified"),
        "latest_result": max((x["date"] for x in rows), default=None),
        "rows_without_scores": dropped,
    }
    return rows, meta


def load_fixtures(on: date):
    """All fixtures on a date from fixtures.csv, keyed by football-data division."""
    url = f"{BASE}/fixtures.csv"
    r = fetch(url)
    df = _read_csv(r.content)
    df["date"] = _parse_dates(df["Date"])
    df = df[df["date"].dt.date == on]
    out = {}
    for row in df.itertuples(index=False):
        out.setdefault(row.Div, []).append({
            "home": str(row.HomeTeam).strip(), "away": str(row.AwayTeam).strip(),
            "kickoff": str(row.Time) if isinstance(row.Time, str) else "",
        })
    meta = {"url": url, "last_modified": r.headers.get("Last-Modified"),
            "fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"}
    return out, meta
