"""Team and league goal statistics, computed from match-level results only.

A result is a dict-like row with: home, away, fthg, ftag, hthg, htag.
Second-half goals are derived as full-time minus half-time for each side.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def total_goals(m) -> int:
    return int(m["fthg"]) + int(m["ftag"])


def is_over_1_5(m) -> bool:
    return total_goals(m) >= 2


def is_goal_in_both_halves(m) -> bool:
    first = int(m["hthg"]) + int(m["htag"])
    second = total_goals(m) - first
    if second < 0:
        raise ValueError(f"half-time total exceeds full-time total: {dict(m)}")
    return first >= 1 and second >= 1


@dataclass
class Split:
    gp: int = 0
    o15: int = 0
    gibh: int = 0

    def add(self, m) -> None:
        self.gp += 1
        self.o15 += is_over_1_5(m)
        self.gibh += is_goal_in_both_halves(m)

    def pct(self, market: str) -> float | None:
        if not self.gp:
            return None
        return getattr(self, market) / self.gp


@dataclass
class TeamStats:
    team: str
    all: Split = field(default_factory=Split)
    home: Split = field(default_factory=Split)
    away: Split = field(default_factory=Split)
    gf: int = 0  # goals scored, for checking against published tables
    ga: int = 0


def team_stats(results) -> dict[str, TeamStats]:
    out: dict[str, TeamStats] = {}
    for m in results:
        for side, venue in ((m["home"], "home"), (m["away"], "away")):
            ts = out.setdefault(side, TeamStats(side))
            ts.all.add(m)
            getattr(ts, venue).add(m)
            scored, conceded = (m["fthg"], m["ftag"]) if venue == "home" else (m["ftag"], m["fthg"])
            ts.gf += int(scored)
            ts.ga += int(conceded)
    return out


def league_rates(results) -> Split:
    s = Split()
    for m in results:
        s.add(m)
    return s


def _avg(a, b):
    if a is None or b is None:
        return None
    return (a + b) / 2


def fixture_markets(home: TeamStats | None, away: TeamStats | None, market: str, min_games: int):
    """Combined % (all games) and venue-split % (home team at home, away team away)."""
    h_pct = home.all.pct(market) if home else None
    a_pct = away.all.pct(market) if away else None
    flags = []
    for label, ts in (("home", home), ("away", away)):
        if ts is None:
            flags.append(f"{label} team has no games")
        elif ts.all.gp < min_games:
            flags.append(f"{ts.team}: only {ts.all.gp} games")
    venue = _avg(home.home.pct(market) if home else None, away.away.pct(market) if away else None)
    return {
        "home_pct": h_pct,
        "away_pct": a_pct,
        "combined_pct": _avg(h_pct, a_pct),
        "venue_pct": venue,
        "home_gp": home.all.gp if home else 0,
        "away_gp": away.all.gp if away else 0,
        "flags": flags,
    }
