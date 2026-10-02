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
# GIBH rates run 55-75%, so its picks need their own, lower bands to tell anything apart.
GIBH_BANDS = [(0, 55, "below 55"), (55, 60, "55-60"), (60, 65, "60-65"), (65, 70, "65-70"), (70, 75, "70-75"),
              (75, 101, "75+")]
MARKET_BANDS = {"o15": BANDS, "gibh": GIBH_BANDS}


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


def record_report(rows: list[dict], report_date: str, leagues=None) -> None:
    """Add this report's fixtures. A re-run for the same date replaces the
    still-pending rows of the leagues it loaded (`leagues`; default: the
    leagues in `rows`), keeps every other row, and never re-adds a fixture
    that has already been graded."""
    df = load()
    leagues = {r["league"] for r in rows} if leagues is None else set(leagues)
    same_day = df["report_date"] == report_date
    replace = same_day & (df["status"] == "pending") & df["league"].isin(leagues)
    done = df.loc[same_day & (df["status"] != "pending"), KEY].astype(str)
    done_keys = set(map(tuple, done.values))
    new = pd.DataFrame([r for r in rows if tuple(str(r[k]) for k in KEY) not in done_keys], columns=COLUMNS)
    new["status"] = "pending"
    save(pd.concat([df[~replace], new], ignore_index=True) if len(df) else new)


def band(pct: float, bands=BANDS) -> str:
    for lo, hi, label in bands:
        if lo <= pct < hi:
            return label
    return bands[-1][2]


def _summ(g: pd.DataFrame, hit: str, rate: str) -> dict:
    n = len(g)
    hits = int(g[hit].astype(bool).sum())
    return {"n": n, "hits": hits, "hit_pct": 100 * hits / n if n else None,
            "league_avg_pct": float(g[rate].mean()) if n else None}


def hit_rates(df: pd.DataFrame | None = None, cfg: dict | None = None) -> dict:
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
        if cfg is not None:  # only the fixtures this market's tab would have shown
            from .scope import in_scope
            sub = sub[[in_scope(cfg, mk, lg, ko) for lg, ko in zip(sub["league_name"], sub["kickoff"])]]
        sub[hit] = sub[hit].astype(str).str.lower().isin(["true", "1", "1.0"])
        bands = MARKET_BANDS[mk]
        sub["band"] = sub[comb].astype(float).map(lambda p: band(p, bands))
        out["markets"][label] = {"acca": _acca_record(df, mk, tag)}
        out["markets"][label].update({
            "overall": _summ(sub, hit, rate),
            "by_league": {lg: _summ(x, hit, rate) for lg, x in sub.groupby("league_name")},
            "by_band": {b: _summ(sub[sub["band"] == b], hit, rate) for _, _, b in bands if (sub["band"] == b).any()},
        })
    return out


def _acca_record(df: pd.DataFrame, mk: str, tag: str):
    """Accumulator weeks, counting only weeks where every leg has a result.
    A postponed (void) leg drops out, as bookmakers settle it; a week with a
    leg still pending or never resolved isn't counted, so it can't show as
    won on the strength of the legs that happened to be graded."""
    legs = df[(df[tag] == "leg") & (df["status"] != "void")].copy()
    if legs.empty:
        return None
    hit = f"{mk}_hit"
    legs[hit] = legs[hit].astype(str).str.lower().isin(["true", "1", "1.0"])
    weeks = won = n_legs = legs_won = open_weeks = 0
    for _, wk in legs.groupby("report_date"):
        if (wk["status"] != "graded").any():
            open_weeks += 1
            continue
        weeks += 1
        won += bool(wk[hit].all())
        n_legs += len(wk)
        legs_won += int(wk[hit].sum())
    if not weeks and not open_weeks:
        return None
    return {"weeks": weeks, "won": won, "legs": n_legs, "legs_won": legs_won, "open_weeks": open_weeks}
