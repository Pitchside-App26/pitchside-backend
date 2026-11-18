"""Puts a confirmed bet slip on the live bet tracker (site/tracker.html).

A confirmed draft (bet_slips.normalize) becomes one tracker bet per slip in
site/bets.json, keyed by the issue it came from, so a corrected and
re-confirmed slip replaces its earlier version. The tracker reads ESPN's live
feed, so every leg needs its game as ESPN's "AWAY@HOME" abbreviations. That
comes from, in order: the game written on the slip, the team on the leg (a
moneyline's team), or the player's team on the season roster. A leg whose
game can't be found, or a market the tracker can't follow (spreads, first TD
scorer, ...), is kept and shown as "not tracked".

Football (soccer) legs are followed from ESPN, or for National League
North/South and Scottish League One/Two from the lower-league relay; the
tracker finds the match from the two clubs, the date and, if the slip names
it, the league.

Nothing that identifies the physical slip (reference, terminal, barcode, the
time it was placed) is ever written, and neither are Dan's stake or returns:
bets.json is public. The tracker keeps a stake Dan types in on his phone only.
"""
import json
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

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

# The competition as written on a slip -> the tracker's league (tracker-core.js
# GOALS_LEAGUES / RELAY_LEAGUES / SEARCH_LEAGUES). First match wins, so the
# narrower names come first. Anything else is left out and the tracker looks
# for the match across all the leagues it follows.
FOOTBALL_LEAGUES = [
    (r"national league north", "ls:north"),
    (r"national league south", "ls:south"),
    (r"national league", "eng.5"),
    (r"(scottish|spfl|scotland).*league (one|1)\b", "ls:sco3"),
    (r"(scottish|spfl|scotland).*league (two|2)\b", "ls:sco4"),
    (r"(scottish|spfl|scotland).*championship", "sco.2"),
    (r"(scottish|spfl|scotland).*premiership|^premiership$", "sco.1"),
    (r"champions league", "uefa.champions"),
    (r"conference league", "uefa.europa.conf"),
    (r"europa league", "uefa.europa"),
    (r"fa cup", "eng.fa"),
    (r"(efl|carabao|league) cup", "eng.league_cup"),
    (r"premier league", "eng.1"),
    (r"championship", "eng.2"),
    (r"league (one|1)\b", "eng.3"),
    (r"league (two|2)\b", "eng.4"),
]
MATCH_SPLIT = re.compile(r"\s+(?:v|vs\.?|-)\s+", re.IGNORECASE)


def football_league(competition: str | None) -> str | None:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(competition or "").lower())
    text = re.sub(r"\s+", " ", text).strip()
    for pattern, league in FOOTBALL_LEAGUES:
        if re.search(pattern, text):
            return league
    return None


def _same_club(a: str, b: str) -> float:
    a, b = a.lower().strip(), b.lower().strip()
    return 1.0 if a and (a in b or b in a) else SequenceMatcher(None, a, b).ratio()


def football_leg(leg: dict) -> tuple[dict, str | None]:
    """(tracker leg, YYYYMMDD) for one confirmed football leg."""
    match = (leg.get("game") or "").strip()
    teams = MATCH_SPLIT.split(match, maxsplit=1)
    day = (leg.get("date") or "").replace("-", "") or None
    label = " · ".join(x for x in (match, leg.get("market_text") or "") if x)
    if len(teams) != 2 or not all(t.strip() for t in teams):
        return {"type": "other", "label": label, "note": "match not clear on the slip"}, day
    home, away = (t.strip() for t in teams)
    base = {"sport": "soccer", "date": day or "", "home": home, "away": away}
    league = football_league(leg.get("competition"))
    if league:
        base["league"] = league
    market, side, line = leg.get("market"), leg.get("side"), leg.get("book_line")

    if market == "match_goals" and side in ("over", "under") and line is not None:
        return {**base, "type": "goals", "side": side, "line": line}, day
    if market == "btts" and side in ("yes", "no"):
        return {**base, "type": "btts", "side": side}, day
    if market == "goal_both_halves" and side == "yes":
        return {**base, "type": "gibh"}, day
    if market == "match_result" and leg.get("team"):
        team = leg["team"].strip()
        if team.lower() == "draw":
            return {**base, "type": "result", "pick": "draw"}, day
        h, a = _same_club(team, home), _same_club(team, away)
        if max(h, a) >= 0.6 and h != a:
            return {**base, "type": "result", "pick": "home" if h > a else "away"}, day
    return {"type": "other", "label": label, "note": "can't be followed live"}, day


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
        football = slip.get("sport") == "football"
        for leg in slip["legs"]:
            tracked, day = football_leg(leg) if football else tracker_leg(leg, schedule, team_of_player)
            legs.append(tracked)
            if day:
                days.add(day)
        bets.append({
            "id": f"issue-{issue}-slip-{n}",
            "book": slip.get("bookmaker") or "bet365",
            "kind": ("Football " if football else "") + KINDS.get(slip["bet_type"], "Bet"),
            "odds": slip.get("total_odds_text") or "",
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
