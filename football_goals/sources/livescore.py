"""LiveScore's public app feed (no key): used for National League North and
South, the only free source found that serves their half-time scores to
GitHub's servers. It is unofficial, so every run also measures it against
football-data.co.uk on the National League, which both cover (see
`agreement_with`), and the leagues are checked against BBC's table.

One request per match day. Days more than SETTLE_DAYS old are saved under
data/livescore/ and never downloaded again."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ..http_cache import fetch

log = logging.getLogger(__name__)
URL = "https://prod-public-api.livescore.com/v1/api/app/date/soccer/{ymd}/0"  # /0 = times in UTC
STORE = Path(__file__).resolve().parent.parent / "data" / "livescore"
UK = ZoneInfo("Europe/London")
SETTLE_DAYS = 3
STAGES = {"north": "National League: North", "south": "National League: South", "national": "National League"}
DONE = {"FT", "AET", "AP"}


class LiveScoreError(RuntimeError):
    pass


def _is_off(status: str) -> bool:
    s = status.lower()
    return any(k in s for k in ("post", "canc", "aband", "susp", "award", "delay"))


def _parse(feed: dict) -> dict[str, list[dict]]:
    """Keep only the English stages we use, as plain match rows."""
    out = {k: [] for k in STAGES}
    wanted = {v: k for k, v in STAGES.items()}
    for st in feed.get("Stages", []):
        if st.get("Cnm") != "England" or st.get("Snm") not in wanted:
            continue
        for e in st.get("Events", []):
            ko = datetime.strptime(str(e["Esd"]), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(UK)
            num = lambda k: int(e[k]) if str(e.get(k, "")).strip().isdigit() else None  # noqa: E731
            out[wanted[st["Snm"]]].append({
                "home": e["T1"][0]["Nm"], "away": e["T2"][0]["Nm"], "status": str(e.get("Eps", "")),
                "date": ko.date().isoformat(), "kickoff": ko.strftime("%H:%M"),
                "fthg": num("Tr1"), "ftag": num("Tr2"), "hthg": num("Trh1"), "htag": num("Trh2"),
            })
    return out


_downloaded: dict[date, dict] = {}  # this run's downloads, so a day is fetched at most once per run


def day(d: date, today: date | None = None, refresh: bool = False) -> dict[str, list[dict]]:
    """One match day. A day more than SETTLE_DAYS before *today's real date* is
    saved and never downloaded again; anything newer is always fetched fresh
    (once per run). `today` is only for tests: it must never be a report date,
    or future days would be saved before they're played."""
    today = today or date.today()
    path = STORE / f"{d.isoformat()}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    if d in _downloaded:
        return _downloaded[d]
    r = fetch(URL.format(ymd=d.strftime("%Y%m%d")))
    try:
        rows = _parse(r.json())
    except (ValueError, KeyError) as e:
        raise LiveScoreError(f"LiveScore feed format changed ({type(e).__name__}: {e})") from e
    _downloaded[d] = rows
    if (today - d).days > SETTLE_DAYS:
        STORE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=0))
    time.sleep(0.3)  # be polite: this is someone else's free feed
    return rows


def season_start(on: date) -> date:
    return date(on.year if on.month >= 7 else on.year - 1, 7, 15)


def _season(stage: str, on: date) -> list[dict]:
    rows, d = [], season_start(on)
    while d < on:
        rows += day(d)[stage]  # settled-or-not is judged against the real date, never the report date
        d += timedelta(days=1)
    return rows


def _complete(r) -> bool:
    return r["status"] in DONE and None not in (r["fthg"], r["ftag"], r["hthg"], r["htag"])


def load_results(region: str, on: date):
    rows = _season(region, on)
    finished = [r for r in rows if r["status"] in DONE]
    good = [{k: r[k] for k in ("date", "home", "away", "fthg", "ftag", "hthg", "htag")} for r in finished if _complete(r)]
    missing_ht = len(finished) - len(good)
    if missing_ht:
        log.warning("%s: %d finished matches lack a half-time score and were skipped", region, missing_ht)
    if not good:
        raise LiveScoreError(f"LiveScore returned no finished {STAGES[region]} matches this season")
    meta = {"source": "LiveScore", "url": URL.split("{")[0], "last_modified": None,
            "latest_result": max(r["date"] for r in good), "rows_without_scores": missing_ht}
    return good, meta


def fixtures_on(region: str, on: date):
    rows = day(on, refresh=True)[region]
    fx = [{"home": r["home"], "away": r["away"], "kickoff": r["kickoff"]} for r in rows if not _is_off(r["status"])]
    off = [{"home": r["home"], "away": r["away"], "status": r["status"]} for r in rows if _is_off(r["status"])]
    return fx, off


def result_on(region: str, on: date, home: str, away: str):
    for r in day(on, refresh=True)[region]:
        if r["home"] == home and r["away"] == away:
            if _is_off(r["status"]):
                return "void"
            return {k: r[k] for k in ("fthg", "ftag", "hthg", "htag")} if _complete(r) else None
    return None


def agreement_with(reference: list[dict], on: date) -> tuple[int, int, list[str]]:
    """Compare LiveScore's National League results with another source's
    (football-data.co.uk): (matched, compared, first few disagreements)."""
    from ..names import best_match
    ls = [r for r in _season("national", on) if _complete(r)]
    ref_clubs = {t for r in reference for t in (r["home"], r["away"])}
    by_key = {(r["date"], r["home"], r["away"]): r for r in reference}
    agree, compared, diffs = 0, 0, []
    for r in ls:
        h, a = best_match(r["home"], ref_clubs), best_match(r["away"], ref_clubs)
        ref = by_key.get((r["date"], h, a))
        if ref is None:
            continue
        compared += 1
        mine = (r["fthg"], r["ftag"], r["hthg"], r["htag"])
        theirs = (ref["fthg"], ref["ftag"], ref["hthg"], ref["htag"])
        if mine == theirs:
            agree += 1
        elif len(diffs) < 5:
            diffs.append(f"{h} v {a} {r['date']}: LiveScore {mine[0]}-{mine[1]} (HT {mine[2]}-{mine[3]}), "
                         f"football-data {theirs[0]}-{theirs[1]} (HT {theirs[2]}-{theirs[3]})")
    return agree, compared, diffs
