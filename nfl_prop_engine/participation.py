"""Who actually took the field each week, from nflverse's weekly snap counts.

Grading needs this to tell two different zeros apart:
- he played and recorded nothing -> a real 0: the under wins, the over loses;
- he took no snaps (inactive, injured, scratched) -> the bet is void, as a
  bookmaker would settle it, and the prop is left out of every hit rate.

Before this, both were graded 0, so every injured player's under counted as
a win (Puka Nacua, out in week 2, went down as 0 yards on an 85.5 line).

Any snap counts as playing, special teams included. Snap counts key on
pfr_player_id; the season roster carries both that and the gsis id the rest
of the engine uses. A player missing from the roster's pfr ids falls back
to his name, within his team or, failing that, if only one player that week
has the name.
"""
import re
from dataclasses import dataclass, field

import pandas as pd


def name_key(name) -> str:
    """'Marvin Harrison Jr.' and 'Marvin Harrison' both -> 'marvinharrison'."""
    no_suffix = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(name or "").lower())
    return re.sub(r"[^a-z]", "", no_suffix)


@dataclass(frozen=True)
class Snaps:
    played: bool
    pct: float  # share of his unit's snaps (offense or defense, whichever is higher)


@dataclass
class WeekParticipation:
    teams: set[str] = field(default_factory=set)  # teams whose snap sheet for the week is out
    by_pfr: dict[str, Snaps] = field(default_factory=dict)
    by_name_team: dict[tuple[str, str], Snaps] = field(default_factory=dict)
    by_unique_name: dict[str, Snaps] = field(default_factory=dict)

    def reported(self, team: str | None) -> bool:
        return team in self.teams

    def lookup(self, pfr_id: str | None, name: str | None, team: str | None) -> Snaps:
        """His snaps this week; not on the sheet at all means he didn't play."""
        if pfr_id and pfr_id in self.by_pfr:
            return self.by_pfr[pfr_id]
        key = name_key(name)
        found = self.by_name_team.get((key, team)) or self.by_unique_name.get(key)
        return found or Snaps(played=False, pct=0.0)


def _num(value) -> float:
    return 0.0 if pd.isna(value) else float(value)


def week_participation(snap_counts: pd.DataFrame, week: int) -> WeekParticipation:
    rows = snap_counts[snap_counts["week"] == week]
    result = WeekParticipation(teams=set(rows["team"].dropna()))
    names: dict[str, list[Snaps]] = {}
    for row in rows.itertuples():
        snaps = Snaps(
            played=_num(row.offense_snaps) + _num(row.defense_snaps) + _num(row.st_snaps) > 0,
            pct=max(_num(row.offense_pct), _num(row.defense_pct)),
        )
        if isinstance(row.pfr_player_id, str) and row.pfr_player_id:
            result.by_pfr[row.pfr_player_id] = snaps
        key = name_key(row.player)
        result.by_name_team[(key, row.team)] = snaps
        names.setdefault(key, []).append(snaps)
    result.by_unique_name = {key: found[0] for key, found in names.items() if len(found) == 1}
    return result


@dataclass(frozen=True)
class Role:
    """His share of his unit's snaps in his latest game, and his average
    over the (up to) three games before it (None with only one game). Three,
    not the whole season: a backup who became the starter weeks ago has a
    settled role by now, and his line has caught up."""
    last_pct: float
    avg_before: float | None
    games: int

    @property
    def swing(self) -> float:
        return 0.0 if self.avg_before is None else abs(self.last_pct - self.avg_before)


@dataclass
class RoleBook:
    by_pfr: dict[str, Role] = field(default_factory=dict)
    by_name_team: dict[tuple[str, str], Role] = field(default_factory=dict)
    by_unique_name: dict[str, Role] = field(default_factory=dict)

    def lookup(self, pfr_id: str | None, name: str | None, team: str | None) -> Role | None:
        if pfr_id and pfr_id in self.by_pfr:
            return self.by_pfr[pfr_id]
        key = name_key(name)
        return self.by_name_team.get((key, team)) or self.by_unique_name.get(key)


def season_roles(snap_counts: pd.DataFrame, before_week: int) -> RoleBook:
    """Every player's snap share this season, from the games before
    `before_week` he took a snap in."""
    rows = snap_counts[snap_counts["week"] < before_week].copy()
    rows["pct"] = rows[["offense_pct", "defense_pct"]].fillna(0).max(axis=1)
    rows = rows[rows["pct"] > 0].sort_values("week")
    book = RoleBook()
    names: dict[str, list[Role]] = {}
    for (pfr, player, team), games in rows.groupby(["pfr_player_id", "player", "team"], dropna=False):
        pcts = games["pct"].tolist()
        before = pcts[-4:-1]
        role = Role(pcts[-1], sum(before) / len(before) if before else None, len(pcts))
        if isinstance(pfr, str) and pfr:
            book.by_pfr[pfr] = role
        key = name_key(player)
        book.by_name_team[(key, team)] = role
        names.setdefault(key, []).append(role)
    book.by_unique_name = {key: found[0] for key, found in names.items() if len(found) == 1}
    return book
