"""The running record: every analysed fixture goes into data/history.csv when
the report runs (status 'pending'), and the Sunday grading run fills in the
score and whether each market landed."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

HISTORY = Path(__file__).parent / "data" / "history.csv"
KEY = ["report_date", "league", "home", "away"]
COLUMNS = KEY + ["league_name", "kickoff", "o15_combined", "o15_venue", "o15_league_rate",
                 "gibh_combined", "gibh_venue", "gibh_league_rate", "acca", "gibh_acca", "price", "flags",
                 "status", "fthg", "ftag", "hthg", "htag", "o15_hit", "gibh_hit", "graded_at", "result_source"]
BANDS = [(0, 75, "below 75"), (75, 80, "75-80"), (80, 85, "80-85"), (85, 90, "85-90"), (90, 101, "90+")]


def load() -> pd.DataFrame:
    if HISTORY.exists():
        df = pd.read_csv(HISTORY, dtype={"fthg": "Int64", "ftag": "Int64", "hthg": "Int64", "htag": "Int64"})
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = pd.NA
        df = df[COLUMNS]
    else:
        df = pd.DataFrame(columns=COLUMNS)
    # free-text / yes-no columns stay as plain objects so grading can write into them
    for c in ("o15_hit", "gibh_hit", "status", "graded_at", "result_source", "acca", "gibh_acca", "flags", "kickoff"):
        df[c] = df[c].astype(object)
    return df


def save(df: pd.DataFrame) -> None:
    HISTORY.parent.mkdir(exist_ok=True)
    df.sort_values(["report_date", "league", "kickoff", "home"]).to_csv(HISTORY, index=False)


def record_report(rows: list[dict], report_date: str) -> None:
    """Add this report's fixtures; a re-run for the same date replaces its still-pending rows."""
    df = load()
    keep = ~((df["report_date"] == report_date) & (df["status"] == "pending"))
    graded_keys = set(map(tuple, df.loc[df["report_date"] == report_date, KEY].astype(str).values))
    new = pd.DataFrame([r for r in rows if tuple(str(r[k]) for k in KEY) not in graded_keys], columns=COLUMNS)
    new["status"] = "pending"
    save(pd.concat([df[keep], new], ignore_index=True) if len(df) else new)


def band(pct: float) -> str:
    for lo, hi, label in BANDS:
        if lo <= pct < hi:
            return label
    return BANDS[-1][2]


def _summ(g: pd.DataFrame, hit: str, rate: str) -> dict:
    n = len(g)
    hits = int(g[hit].astype(bool).sum())
    return {"n": n, "hits": hits, "hit_pct": 100 * hits / n if n else None,
            "league_avg_pct": float(g[rate].mean()) if n else None}


def hit_rates(df: pd.DataFrame | None = None) -> dict:
    """Running hit rates from graded rows, each set against the league average
    (the season-to-date league rate at the time of each report)."""
    df = load() if df is None else df
    g = df[df["status"] == "graded"].copy()
    out = {"graded": len(g), "markets": {}}
    if g.empty:
        return out
    # "acca" holds the Over 1.5 accumulator tag (its original name); "gibh_acca" the GIBH one.
    for mk, label, tag in (("o15", "Over 1.5", "acca"), ("gibh", "Goal in both halves", "gibh_acca")):
        hit, rate, comb = f"{mk}_hit", f"{mk}_league_rate", f"{mk}_combined"
        sub = g.dropna(subset=[comb]).copy()
        sub[hit] = sub[hit].astype(str).str.lower().isin(["true", "1", "1.0"])
        sub["band"] = sub[comb].astype(float).map(band)
        acca = None
        legs = sub[sub[tag] == "leg"]
        if not legs.empty:
            per_week = legs.groupby("report_date")[hit].agg(["count", "sum"])
            acca = {"weeks": len(per_week), "won": int((per_week["count"] == per_week["sum"]).sum()),
                    "legs": int(per_week["count"].sum()), "legs_won": int(per_week["sum"].sum())}
        out["markets"][label] = {
            "overall": _summ(sub, hit, rate),
            "by_league": {lg: _summ(x, hit, rate) for lg, x in sub.groupby("league_name")},
            "by_band": {b: _summ(sub[sub["band"] == b], hit, rate) for _, _, b in BANDS if (sub["band"] == b).any()},
            "acca": acca,
        }
    return out
