"""Checks that each league's dataset really is that league and is current.

Internal checks (always): team count, no team playing far more/fewer games
than the rest, no duplicate fixture, every upcoming fixture's clubs exist in
the results. Published-table check (where a table source exists): every
club's games played / goals for / goals against must match the published
table, which also proves the results file isn't missing recent matches."""
from __future__ import annotations

import logging
from collections import Counter
from statistics import median

from .names import best_match

log = logging.getLogger(__name__)


GP_OUTLIER = "games played out of line with the rest of the league"


def internal_checks(league, results, stats, fixtures) -> tuple[list[str], list[str]]:
    """Returns (problems, notes). A problem marks the league's rows with a data flag."""
    problems, notes = [], []
    n = len(stats)
    if n != league.teams:
        problems.append(f"{n} clubs in results, expected {league.teams}")
    else:
        notes.append(f"{n} clubs, as expected")
    gps = {t: s.all.gp for t, s in stats.items()}
    if gps:
        med = median(gps.values())
        odd = {t: g for t, g in gps.items() if abs(g - med) > 3}
        if odd:
            problems.append(GP_OUTLIER + ": "
                            + ", ".join(f"{t} {g} (league median {med:g})" for t, g in sorted(odd.items())))
        else:
            notes.append(f"games played {min(gps.values())}-{max(gps.values())} per club, consistent")
    same_day = [k for k, c in Counter((r["date"], r["home"], r["away"]) for r in results).items() if c > 1]
    if same_day:
        problems.append("duplicate result rows: " + ", ".join(f"{h} v {a} ({d})" for d, h, a in same_day))
    too_many = [k for k, c in Counter((r["home"], r["away"]) for r in results).items() if c > league.max_meetings]
    if too_many:
        problems.append(f"home-v-away pairing played more than {league.max_meetings}x (wrong league or merged seasons?): "
                        + ", ".join(f"{h} v {a}" for h, a in too_many[:5]))
    unknown = sorted({t for f in fixtures for t in (f["home"], f["away"]) if t not in stats})
    if unknown:
        problems.append("fixture clubs not found in this league's results: " + ", ".join(unknown))
    return problems, notes


def _differs(name, mine, theirs) -> str:
    return f"{name}: ours P{mine[0]} F{mine[1]} A{mine[2]} v table P{theirs[0]} F{theirs[1]} A{theirs[2]}"


def table_check(stats, table: dict[str, dict], source: str, playing=frozenset()) -> tuple[list[str], list[str]]:
    """Compare our per-club GP/GF/GA with a published table.

    `playing` = clubs with a match on the report day. Published tables update
    live, so during (or just after) that match a club can be exactly one game
    ahead of the results file; those clubs are matched on what we can check."""
    problems, notes = [], []
    if not table:
        return ["published table came back empty"], notes
    ours = set(stats)
    mapped = {}
    for pub_name in table:
        m = best_match(pub_name, ours)
        if m is None:
            problems.append(f"{source} table club '{pub_name}' not found in results")
        else:
            mapped[m] = pub_name
    if len(table) != len(ours):
        problems.append(f"{source} table has {len(table)} clubs, results have {len(ours)}")
    mismatches, live, ahead = [], 0, {}
    for ours_name, pub_name in sorted(mapped.items()):
        s, p = stats[ours_name].all, table[pub_name]
        if ours_name in playing and p["gp"] == s.gp + 1:
            live += 1  # today's game already counted in the live table
            continue
        mine = (s.gp, stats[ours_name].gf, stats[ours_name].ga)
        theirs = (p["gp"], p["gf"], p["ga"])
        if mine != theirs:
            if theirs[0] == mine[0] + 1:
                ahead[ours_name] = (theirs[1] - mine[1], theirs[2] - mine[2], mine, theirs)
            else:
                mismatches.append(_differs(ours_name, mine, theirs))
    # A game played since the results file was updated (e.g. Friday night) puts
    # both clubs exactly one game ahead, with mirrored goals (2-0 = +2/+0 and
    # +0/+2). Only clubs that pair up like that are let through.
    recent = []
    while ahead:
        a, (af, aa, *_) = next(iter(ahead.items()))
        b = next((n for n, (bf, ba, *_) in ahead.items() if n != a and bf == aa and ba == af), None)
        if b is None:
            _, _, mine, theirs = ahead.pop(a)
            mismatches.append(_differs(a, mine, theirs))
            continue
        ahead.pop(a), ahead.pop(b)
        recent.append(f"{a} {af}-{aa} {b}")
    if mismatches:
        problems.append(f"{len(mismatches)} club(s) differ from the {source} table: " + "; ".join(mismatches[:6])
                        + (" ..." if len(mismatches) > 6 else ""))
    elif mapped:
        extra = f" ({live} with today's game already in the table)" if live else ""
        notes.append(f"all {len(mapped)} clubs match the {source} table (played, scored, conceded){extra}")
    if recent and not mismatches:
        notes.append(f"{source} table already includes {len(recent)} game(s) the results file doesn't have yet "
                     f"({'; '.join(recent)}); those clubs' stats are one game behind")
    return problems, notes
