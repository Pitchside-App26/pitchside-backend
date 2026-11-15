"""Puts a confirmed bet slip on the live bet tracker (site/tracker.html).

A confirmed draft (bet_slips.normalize) becomes one tracker bet per slip in
site/bets.json, keyed by the issue it came from, so a corrected and
re-confirmed slip replaces its earlier version. The tracker reads ESPN's live
feed, so every leg needs its game as ESPN's "AWAY@HOME" abbreviations. That
comes from, in order: the game written on the slip, the team on the leg (a
moneyline's team), or the player's team on the season roster. A leg whose
game can't be found, or a market the tracker can't follow (spreads, first TD
scorer, ...), is kept and shown as "not tracked".

Nothing that identifies the physical slip (reference, terminal, barcode, the
time it was placed) is ever written: bets.json is public.
"""
import json
import re
from datetime import date, datetime, timedelta

from config import ODDS_API_TEAM_NAME_TO_ABBR

BETS_PATH = "site/bets.json"
KEEP_DAYS = 10  # older bets drop off the tracker when a new one is added

# nflverse abbreviations -> ESPN's, where they differ.
TO_ESPN = {"LA": "LAR", "WAS": "WSH"}

# The engine's player-prop markets -> the tracker's stat names.
MARKET_STAT = {
    "player_pass_yds": "passingYards",
    "player_pass_tds": "passingTouchdowns",
    "player_pass_completions": "completions",
    "player_pass_interceptions": "interceptions",
    "player_rush_yds": "rushingYards",
    "player_rush_attempts": "carries",
    "player_reception_yds": "receivingYards",
    "player_receptions": "receptions",
    "player_tackles_assists": "tackles",
    "player_sacks": "sacks",
}

KINDS = {"single": "Single", "accumulator": "Accumulator", "bet_builder": "Bet Builder", "other": "Bet"}


def espn(abbr: str | None) -> str | None:
    return TO_ESPN.get(abbr, abbr) if abbr else None


def _team_patterns() -> list[tuple[re.Pattern, str]]:
    """Full names ("San Francisco 49ers") and nicknames ("49ers") -> nflverse
    abbreviation, longest first so "New York Jets" wins over "Jets"."""
    names = []
    for full, abbr in ODDS_API_TEAM_NAME_TO_ABBR.items():
        names += [(full, abbr), (full.split()[-1], abbr)]
    names.sort(key=lambda na: -len(na[0]))
    return [(re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE), abbr) for name, abbr in names]


TEAM_PATTERNS = _team_patterns()


def teams_in(text: str | None) -> list[str]:
    """nflverse abbreviations of the teams named in `text`, in order."""
    found, seen, rest = [], set(), str(text or "")
    for pattern, abbr in TEAM_PATTERNS:
        match = pattern.search(rest)
        if match and abbr not in seen:
            seen.add(abbr)
            found.append((match.start(), abbr))
            rest = rest[:match.start()] + " " * (match.end() - match.start()) + rest[match.end():]
    return [abbr for _, abbr in sorted(found)]


class Schedule:
    """The week's games: team -> (ESPN "AWAY@HOME", "YYYYMMDD")."""

    def __init__(self, games):
        self.by_team = {}
        for row in games.itertuples():
            key = f"{espn(row.away_team)}@{espn(row.home_team)}"
            day = str(getattr(row, "gameday", "") or "").replace("-", "")
            self.by_team[row.home_team] = self.by_team[row.away_team] = (key, day)

    def game_for(self, *teams: str | None) -> tuple[str, str] | None:
        for team in teams:
            if team in self.by_team:
                return self.by_team[team]
        return None


def tracker_leg(leg: dict, schedule: Schedule, team_of_player: dict[str, str]) -> tuple[dict, str | None]:
    """(tracker leg, game date) for one confirmed slip leg."""
    named = teams_in(leg.get("game"))
    backed = teams_in(leg.get("team"))
    player = (leg.get("player") or "").strip()
    found = schedule.game_for(*named, *backed, team_of_player.get(player))
    label = " ".join(x for x in (player or (leg.get("team") or ""), leg.get("market_text") or "") if x).strip()
    if found is None:
        return {"type": "other", "label": label, "note": "game not found"}, None
    game, day = found
    market, side, line = leg.get("market"), leg.get("side"), leg.get("book_line")

    if market in MARKET_STAT and side in ("over", "under") and line is not None:
        return {"type": "player", "game": game, "player": player, "stat": MARKET_STAT[market], "side": side,
                "line": line}, day
    if market == "player_anytime_td" and side == "yes" and player:
        return {"type": "anytime_td", "game": game, "player": player}, day
    if market == "game_total" and side in ("over", "under") and line is not None:
        return {"type": "total", "game": game, "side": side, "line": line}, day
    if market == "moneyline" and backed:
        return {"type": "moneyline", "game": game, "team": espn(backed[0])}, day
    return {"type": "other", "game": game, "label": label, "note": "can't be followed live"}, day


def tracker_bets(issue: int, draft: dict, schedule: Schedule, team_of_player: dict[str, str]) -> list[dict]:
    bets = []
    for n, slip in enumerate(draft["slips"], start=1):
        legs, days = [], set()
        for leg in slip["legs"]:
            tracked, day = tracker_leg(leg, schedule, team_of_player)
            legs.append(tracked)
            if day:
                days.add(day)
        bets.append({
            "id": f"issue-{issue}-slip-{n}",
            "book": slip.get("bookmaker") or "bet365",
            "kind": KINDS.get(slip["bet_type"], "Bet"),
            "odds": slip.get("total_odds_text") or "",
            "stake": slip.get("stake_gbp"),
            "returns": slip.get("potential_returns_gbp"),
            "dates": sorted(days),
            "legs": legs,
        })
    return bets


def _last_day(bet: dict) -> str:
    days = bet.get("dates") or [bet.get("date") or ""]
    return max(d for d in days if d) if any(days) else ""


def merge(existing: dict, issue: int, new_bets: list[dict], today: date) -> dict:
    """Replaces this issue's bets and drops any bet whose last game was more
    than KEEP_DAYS ago. Bets with no dates are kept."""
    cutoff = (today - timedelta(days=KEEP_DAYS)).strftime("%Y%m%d")
    prefix = f"issue-{issue}-"
    kept = [b for b in existing.get("bets", [])
            if not str(b.get("id", "")).startswith(prefix) and (not _last_day(b) or _last_day(b) >= cutoff)]
    return {**existing, "bets": new_bets + kept}


def publish(issue: int, draft: dict, schedule: Schedule, team_of_player: dict[str, str],
            path: str | None = None, today: date | None = None) -> int:
    """Writes this slip's bets into bets.json; returns how many legs the
    tracker can follow live."""
    path = path or BETS_PATH
    try:
        with open(path) as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = {"bets": []}
    bets = tracker_bets(issue, draft, schedule, team_of_player)
    merged = merge(existing, issue, bets, today or datetime.now().date())
    with open(path, "w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")
    return sum(leg["type"] != "other" for bet in bets for leg in bet["legs"])
