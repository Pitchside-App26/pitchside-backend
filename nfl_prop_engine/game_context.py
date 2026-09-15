"""Game-level context derived from the schedule's own spread/total lines --
signal about THIS SPECIFIC GAME's expected environment (how much scoring)
and script (which team is more likely to be running out a lead vs. throwing
to catch up), as opposed to a player's own history or the opponent's
season-long tendency, neither of which project_veteran/project_rookie knew
anything about before this module existed.

Sign convention for spread_line CONFIRMED against real 2026 week 1 results
(all 16 games, not a cherry-picked example): positive spread_line means the
HOME team is favored by that many points -- correlation between spread_line
and the actual home-team scoring margin across the week was +0.34. This is
nflverse's own convention, which is the OPPOSITE of the common bettor-facing
convention ("-3" means favored by 3) -- verified directly against real
results rather than assumed, since getting the sign backwards here would
silently flip every adjustment this module makes.
"""
from config import GAME_SCRIPT_SCALE, PASS_VOLUME_STATS, RUSH_VOLUME_STATS


def team_spread(spread_line: float | None, is_home: bool) -> float | None:
    """This team's own expected margin, from their own perspective --
    positive means favored, negative means underdog. spread_line as
    published is always from the home team's perspective, so an away team's
    own spread is the negation of it."""
    if spread_line is None:
        return None
    return spread_line if is_home else -spread_line


def team_implied_total(total_line: float | None, spread_line: float | None, is_home: bool) -> float | None:
    """This team's own share of the game's expected total points: half the
    total, shifted by half of the team's own spread (a favorite is implied
    for more than half the total, an underdog for less)."""
    if total_line is None or spread_line is None:
        return None
    return total_line / 2 + team_spread(spread_line, is_home) / 2


def environment_factor(implied_total: float | None, league_avg_team_total: float | None) -> float | None:
    """>1 means a higher-scoring environment for this team's offense than a
    typical team this week; <1 means lower. None (no adjustment) if either
    input is missing -- never fabricate a factor from a partial line."""
    if implied_total is None or not league_avg_team_total:
        return None
    return implied_total / league_avg_team_total


def script_tilt(spread: float | None, scale: float = GAME_SCRIPT_SCALE) -> float:
    """-1..+1: how much game script favors this team running (positive --
    this team is the bigger favorite, more likely to be protecting a lead)
    vs. throwing to catch up (negative, the bigger underdog). Clipped at
    `scale` points of spread -- beyond that there's no real basis for
    assuming the relationship keeps scaling linearly. Returns 0.0 (neutral)
    rather than None with no spread data, since this is used as a tilt
    rather than a multiplier and 0 is already the correct neutral value.
    """
    if spread is None:
        return 0.0
    return max(-1.0, min(1.0, spread / scale))


def apply_game_context(
    baseline: float,
    stat_col: str,
    env_factor: float | None,
    tilt: float,
    env_weight: float,
    script_weight: float,
) -> float:
    """Applies the environment (scoring-context) and script (run/pass mix)
    adjustments to a baseline projection. Rushing and passing/receiving
    volume move in OPPOSITE directions off the same script tilt -- a team
    protecting a lead runs more and throws less, an underdog does the
    reverse. Any stat not in either set (currently: all defensive stats)
    passes through unchanged -- see config.py's comment on why.
    """
    if stat_col in RUSH_VOLUME_STATS:
        value = baseline
        if env_factor is not None:
            value *= 1 + env_weight * (env_factor - 1)
        return value * (1 + script_weight * tilt)
    if stat_col in PASS_VOLUME_STATS:
        value = baseline
        if env_factor is not None:
            value *= 1 + env_weight * (env_factor - 1)
        return value * (1 - script_weight * tilt)
    return baseline
