from datetime import datetime, timezone

import pandas as pd

from weather import game_winds, kickoff_utc, max_wind_mph


def test_kickoff_converts_eastern_to_utc_across_the_clock_change():
    assert kickoff_utc("2026-10-11", "13:00") == datetime(2026, 10, 11, 17, 0, tzinfo=timezone.utc)
    assert kickoff_utc("2026-11-08", "13:00") == datetime(2026, 11, 8, 18, 0, tzinfo=timezone.utc)
    assert kickoff_utc(None, "13:00") is None


def _forecast(start_hour, speeds):
    return {"hourly": {"time": [f"2026-10-11T{h:02d}:00" for h in range(start_hour, start_hour + len(speeds))],
                       "wind_speed_10m": speeds}}


def test_wind_is_the_strongest_hour_from_kickoff_to_the_final_whistle():
    start = datetime(2026, 10, 11, 17, 0, tzinfo=timezone.utc)
    # 15:00-22:00 UTC; the game hours are 17:00-20:00.
    assert max_wind_mph(_forecast(15, [30, 30, 8, 12, 17, 9, 40, 40]), start) == 17
    assert max_wind_mph({}, start) is None


class _Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_game_winds_skips_domes_and_never_raises():
    games = pd.DataFrame([
        {"home_team": "BUF", "away_team": "NE", "roof": "outdoors", "gameday": "2026-10-11", "gametime": "13:00"},
        {"home_team": "DET", "away_team": "CHI", "roof": "dome", "gameday": "2026-10-11", "gametime": "13:00"},
        {"home_team": "KC", "away_team": "LV", "roof": "outdoors", "gameday": "2026-10-11", "gametime": "16:25"},
        {"home_team": "SEA", "away_team": "SF", "roof": "outdoors", "gameday": "2026-10-12", "gametime": "20:15"},
    ])
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["latitude"])
        if params["latitude"] == 39.049:  # Arrowhead: the service is down
            raise ConnectionError("down")
        return _Resp(_forecast(17, [21, 22, 19, 18]))

    winds = game_winds(games, {"BUF", "NE", "DET", "CHI", "KC", "LV"}, get=fake_get)
    assert winds["NE"] == {"wind_mph": 22, "indoors": False}
    assert winds["DET"] == {"wind_mph": None, "indoors": True}
    assert winds["KC"] == {"wind_mph": None, "indoors": False}
    assert "SEA" not in winds  # outside the teams asked for
    assert len(calls) == 2  # no request for the dome
