"""Wind at kickoff for outdoor games, from the free Open-Meteo forecast (no
key). Wind is the one weather effect with a clear published effect on NFL
passing: little below 10 mph, noticeable from about 15 mph, severe above
20 (deep passes and completion rates drop). The acca report uses it as a
Weather gate on passing and receiving legs: a wind at or above
WIND_FADE_MPH fails the over and backs the under.

Never raises: no forecast (indoors, an unknown venue, the service down)
just means the gate passes with a "no forecast" reason.
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Home stadium of each team, (latitude, longitude). Indoor stadiums are
# listed too; the schedule's roof column decides whether wind matters.
STADIUMS = {
    "ARI": (33.528, -112.263), "ATL": (33.755, -84.401), "BAL": (39.278, -76.623), "BUF": (42.774, -78.787),
    "CAR": (35.226, -80.853), "CHI": (41.862, -87.617), "CIN": (39.096, -84.516), "CLE": (41.506, -81.700),
    "DAL": (32.747, -97.095), "DEN": (39.744, -105.020), "DET": (42.340, -83.046), "GB": (44.501, -88.062),
    "HOU": (29.685, -95.411), "IND": (39.760, -86.164), "JAX": (30.324, -81.637), "KC": (39.049, -94.484),
    "LV": (36.091, -115.183), "LAC": (33.954, -118.339), "LA": (33.954, -118.339), "MIA": (25.958, -80.239),
    "MIN": (44.974, -93.258), "NE": (42.091, -71.264), "NO": (29.951, -90.081), "NYG": (40.814, -74.074),
    "NYJ": (40.814, -74.074), "PHI": (39.901, -75.168), "PIT": (40.447, -80.016), "SF": (37.403, -121.970),
    "SEA": (47.595, -122.332), "TB": (27.976, -82.503), "TEN": (36.166, -86.771), "WAS": (38.908, -76.865),
}
INDOOR_ROOFS = {"dome", "closed"}
GAME_HOURS = 3  # wind is taken as the strongest hour from kickoff to roughly the final whistle
# Open-Meteo timed out or answered 503 for every game on 11 Oct, so the
# Weather gate checked nothing. Each game now gets a few tries; after two
# games fail outright the service is taken as down and the rest are skipped
# rather than waited on (the run reports it either way).
ATTEMPTS = 3
RETRY_WAIT_SECONDS = 5
GIVE_UP_AFTER_FAILED_GAMES = 2


def kickoff_utc(gameday: str, gametime: str) -> datetime | None:
    try:
        local = datetime.strptime(f"{gameday} {gametime}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/New_York"))
    except (TypeError, ValueError):
        return None
    return local.astimezone(timezone.utc)


def max_wind_mph(forecast: dict, start: datetime, hours: int = GAME_HOURS) -> float | None:
    """Strongest hourly wind (mph) from kickoff for `hours` hours, from an
    Open-Meteo response requested with timezone=UTC and wind_speed_unit=mph."""
    hourly = (forecast or {}).get("hourly") or {}
    times, speeds = hourly.get("time") or [], hourly.get("wind_speed_10m") or []
    first = start.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    wanted = {(first + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(hours + 1)}
    values = [s for t, s in zip(times, speeds) if t in wanted and s is not None]
    return max(values) if values else None


def fetch_forecast(lat: float, lon: float, day: str, get=requests.get) -> dict:
    resp = get(FORECAST_URL, params={
        "latitude": lat, "longitude": lon, "hourly": "wind_speed_10m", "wind_speed_unit": "mph",
        "timezone": "UTC", "start_date": day, "end_date": (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"),
    }, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _fetch_with_retries(lat: float, lon: float, day: str, get, sleep) -> dict:
    for attempt in range(ATTEMPTS):
        try:
            return fetch_forecast(lat, lon, day, get=get)
        except Exception:
            if attempt == ATTEMPTS - 1:
                raise
            sleep(RETRY_WAIT_SECONDS * (attempt + 1))


def game_winds(games: pd.DataFrame, teams: set[str] | None = None, get=requests.get, sleep=time.sleep) -> dict[str, dict]:
    """team -> {"wind_mph": float | None, "indoors": bool} for each game
    (both teams), limited to games involving `teams` when given. An outdoor
    game with wind_mph None had no forecast (see failed_forecasts)."""
    result = {}
    failed_in_a_row = 0
    for row in games.itertuples():
        if teams is not None and row.home_team not in teams and row.away_team not in teams:
            continue
        roof = str(getattr(row, "roof", "") or "").lower()
        info = {"wind_mph": None, "indoors": roof in INDOOR_ROOFS}
        start = kickoff_utc(getattr(row, "gameday", None), getattr(row, "gametime", None))
        venue = STADIUMS.get(row.home_team)
        if not info["indoors"] and start is not None and venue is not None:
            if failed_in_a_row >= GIVE_UP_AFTER_FAILED_GAMES:
                logger.warning("No wind forecast for %s @ %s (the forecast service is down)", row.away_team, row.home_team)
            else:
                try:
                    forecast = _fetch_with_retries(*venue, start.strftime("%Y-%m-%d"), get, sleep)
                    info["wind_mph"] = max_wind_mph(forecast, start)
                    failed_in_a_row = 0
                except Exception as exc:  # the weather must never stop the run
                    failed_in_a_row += 1
                    logger.warning("No wind forecast for %s @ %s (%s)", row.away_team, row.home_team, exc)
        result[row.home_team] = result[row.away_team] = info
    return result


def failed_forecasts(winds: dict[str, dict]) -> tuple[int, int]:
    """(outdoor games with no forecast, outdoor games) from game_winds."""
    games = {id(info): info for info in winds.values()}.values()  # both teams share one entry per game
    outdoor = [info for info in games if not info["indoors"]]
    return sum(info["wind_mph"] is None for info in outdoor), len(outdoor)
