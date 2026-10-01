"""Step 1: this week's NFL schedule.

Free, no API credits. Tells rank_props.py which teams are playing (needed
to scope step 3's opponent-adjustment pool) and gives spread_line/total_line
context for output.py.
"""
import logging
from datetime import date

import nfl_data_py as nfl
import pandas as pd

from config import ACCA_WINDOWS, SCHEDULES_FALLBACK_URL, get_current_nfl_season

logger = logging.getLogger(__name__)


def _load_full_schedule(season: int) -> pd.DataFrame:
    try:
        return nfl.import_schedules([season])
    except Exception as exc:
        logger.warning(
            "nfl_data_py.import_schedules() failed (%s); falling back to "
            "the verified nflverse-data release asset.", exc
        )
        df = pd.read_parquet(SCHEDULES_FALLBACK_URL)
        return df[df["season"] == season].reset_index(drop=True)


def load_schedule_seasons(seasons: list[int]) -> pd.DataFrame:
    """Multi-season schedule, used by opponent_stats.py to look up who a
    defensive player's team faced in a given week (needed because the
    defense stats file has no opponent_team column of its own)."""
    frames = [_load_full_schedule(s) for s in seasons]
    return pd.concat(frames, ignore_index=True)


def get_current_week(schedule: pd.DataFrame, today: date | None = None) -> int:
    """The next REG/POST week that hasn't finished yet (no scores logged)."""
    today = today or date.today()
    unplayed = schedule[schedule["home_score"].isna()]
    if unplayed.empty:
        return int(schedule["week"].max())
    return int(unplayed["week"].min())


def fetch_week_games(season: int | None = None, week: int | None = None) -> pd.DataFrame:
    """Returns this week's games with the columns rank_props.py needs:
    game_id, week, home_team, away_team, spread_line, total_line, roof.
    """
    season = season or get_current_nfl_season()
    schedule = _load_full_schedule(season)
    week = week or get_current_week(schedule)

    cols = ["game_id", "season", "week", "home_team", "away_team",
            "spread_line", "total_line", "roof", "gameday", "weekday", "gametime"]
    cols = [c for c in cols if c in schedule.columns]
    games = schedule[schedule["week"] == week][cols].reset_index(drop=True)
    logger.info("Season %s week %s: %d games", season, week, len(games))
    return games


def teams_playing(games: pd.DataFrame) -> set[str]:
    return set(games["home_team"]).union(set(games["away_team"]))


def opponent_map(games: pd.DataFrame) -> dict[str, str]:
    """team -> this week's opponent, both directions."""
    mapping = {}
    for _, row in games.iterrows():
        mapping[row["home_team"]] = row["away_team"]
        mapping[row["away_team"]] = row["home_team"]
    return mapping


def _format_kickoff(row) -> str:
    weekday = str(row.get("weekday", ""))[:3]
    gametime = row.get("gametime")
    if not weekday or gametime is None or pd.isna(gametime):
        return ""
    return f"{weekday} {gametime} ET"


def kickoff_map(games: pd.DataFrame) -> dict[str, str]:
    """team -> a display-ready kickoff string, e.g. "Sun 13:00 ET"."""
    mapping = {}
    for _, row in games.iterrows():
        label = _format_kickoff(row)
        mapping[row["home_team"]] = label
        mapping[row["away_team"]] = label
    return mapping


def game_window(weekday, gametime) -> str | None:
    """Which accumulator window a kickoff belongs to (config.ACCA_WINDOWS),
    from nflverse's Eastern-time weekday/gametime. None for everything else
    (London mornings, Thursday/Sunday/Monday nights, Saturdays)."""
    if weekday != "Sunday" or not isinstance(gametime, str):
        return None
    for key, spec in ACCA_WINDOWS.items():
        if spec["start_et"] <= gametime < spec["end_et"]:
            return key
    return None


def window_map(games: pd.DataFrame) -> dict[str, str | None]:
    """team -> accumulator window key (or None)."""
    mapping = {}
    for _, row in games.iterrows():
        window = game_window(row.get("weekday"), row.get("gametime"))
        mapping[row["home_team"]] = window
        mapping[row["away_team"]] = window
    return mapping


def window_uk_kickoffs(games: pd.DataFrame) -> dict[str, str]:
    """window key -> UK kickoff time(s), e.g. "21:05/21:25", converted from
    the real date rather than assumed: UK and US clocks change a week apart
    in late October/early November."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    times: dict[str, set[str]] = {}
    for _, row in games.iterrows():
        window = game_window(row.get("weekday"), row.get("gametime"))
        if window is None or not isinstance(row.get("gameday"), str):
            continue
        et = datetime.fromisoformat(f"{row['gameday']}T{row['gametime']}").replace(tzinfo=ZoneInfo("America/New_York"))
        times.setdefault(window, set()).add(et.astimezone(ZoneInfo("Europe/London")).strftime("%H:%M"))
    return {w: "/".join(sorted(t)) for w, t in times.items()}


def team_game_context(games: pd.DataFrame) -> dict[str, dict]:
    """team -> {'spread_line', 'total_line', 'is_home'} for this week's
    game, fed to game_context.py's environment/script adjustment. spread_line
    and total_line are already in `games` (fetch_week_games pulls them) --
    this just reshapes them per-team instead of per-game."""
    mapping = {}
    for _, row in games.iterrows():
        spread = row.get("spread_line")
        total = row.get("total_line")
        mapping[row["home_team"]] = {"spread_line": spread, "total_line": total, "is_home": True}
        mapping[row["away_team"]] = {"spread_line": spread, "total_line": total, "is_home": False}
    return mapping


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    games = fetch_week_games()
    print(games.to_string(index=False))
