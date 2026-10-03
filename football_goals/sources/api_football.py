"""API-Football (api-sports.io): used for National League North and South,
which neither football-data.co.uk nor ESPN covers. Needs the
API_FOOTBALL_KEY secret. About 5 requests per weekly run."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..http_cache import fetch

log = logging.getLogger(__name__)
BASE = "https://v3.football.api-sports.io"
UK = ZoneInfo("Europe/London")
DONE = {"FT", "AET", "PEN"}
OFF = {"PST", "CANC", "ABD", "SUSP", "INT", "AWD", "WO"}
NAMES = {"north": "National League - North", "south": "National League - South"}


class ApiFootballError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not k:
        raise ApiFootballError("API_FOOTBALL_KEY secret is not set (see README: 'National League North/South')")
    return k


def _get(path: str, **params):
    r = fetch(f"{BASE}/{path}", params=params, headers={"x-apisports-key": _key()})
    j = r.json()
    errs = j.get("errors")
    if errs:
        raise ApiFootballError(f"API-Football refused /{path}: {errs}")
    return j["response"]


def season_year(on: date) -> int:
    return on.year if on.month >= 7 else on.year - 1


_league_ids: dict[str, int] = {}


def league_id(region: str, on: date) -> int:
    if region not in _league_ids:
        want = NAMES[region].lower()
        for item in _get("leagues", country="England", season=season_year(on)):
            nm = item["league"]["name"].lower()
            if nm == want or nm.replace(" -", "") == want.replace(" -", ""):
                _league_ids[region] = item["league"]["id"]
                break
        else:
            raise ApiFootballError(f"API-Football has no league called '{NAMES[region]}' this season")
    return _league_ids[region]


_fixture_cache: dict[tuple, list] = {}
_refreshed: set = set()


def _season_fixtures(region: str, on: date) -> list:
    k = (region, season_year(on))
    if k not in _fixture_cache:
        _fixture_cache[k] = _get("fixtures", league=league_id(region, on), season=season_year(on))
    return _fixture_cache[k]


def _row(f):
    ko = datetime.fromisoformat(f["fixture"]["date"]).astimezone(UK)
    return ko, f["teams"]["home"]["name"], f["teams"]["away"]["name"], f["fixture"]["status"]["short"]


def load_results(region: str, on: date):
    rows, no_ht = [], 0
    for f in _season_fixtures(region, on):
        ko, home, away, st = _row(f)
        if st not in DONE or ko.date() >= on:
            continue
        ht, ft = f["score"]["halftime"], f["score"]["fulltime"]
        if None in (ht.get("home"), ht.get("away"), ft.get("home"), ft.get("away")):
            no_ht += 1
            continue
        rows.append({"date": ko.date().isoformat(), "home": home, "away": away,
                     "fthg": ft["home"], "ftag": ft["away"], "hthg": ht["home"], "htag": ht["away"]})
    if no_ht:
        log.warning("%s: %d finished matches lack a half-time score and were skipped", region, no_ht)
    meta = {"source": "API-Football", "url": f"{BASE}/fixtures", "last_modified": None,
            "latest_result": max((x["date"] for x in rows), default=None), "rows_without_scores": no_ht}
    return rows, meta


def fixtures_on(region: str, on: date):
    """(fixtures, postponed) on a date."""
    fx, off = [], []
    for f in _season_fixtures(region, on):
        ko, home, away, st = _row(f)
        if ko.date() != on:
            continue
        item = {"home": home, "away": away, "kickoff": ko.strftime("%H:%M")}
        (off if st in OFF else fx).append(item)
    return fx, off


def result_on(region: str, on: date, home: str, away: str):
    """Graded result for a past fixture: dict, 'void', or None if not finished yet."""
    k = (region, season_year(on))
    if k not in _refreshed:  # fresh for grading, but once per run, not once per fixture
        _fixture_cache.pop(k, None)
        _refreshed.add(k)
    for f in _season_fixtures(region, on):
        ko, h, a, st = _row(f)
        if ko.date() == on and h == home and a == away:
            if st in OFF:
                return "void"
            if st in DONE and f["score"]["halftime"]["home"] is not None:
                return {"fthg": f["score"]["fulltime"]["home"], "ftag": f["score"]["fulltime"]["away"],
                        "hthg": f["score"]["halftime"]["home"], "htag": f["score"]["halftime"]["away"]}
            return None
    return None
