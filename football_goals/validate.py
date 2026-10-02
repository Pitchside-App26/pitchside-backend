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


def table_check(stats, table: dict[str, dict], source: str) -> tuple[list[str], list[str]]:
    """Compare our per-club GP/GF/GA with a published table."""
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
    mismatches = []
    for ours_name, pub_name in sorted(mapped.items()):
        s, p = stats[ours_name].all, table[pub_name]
        mine = (s.gp, stats[ours_name].gf, stats[ours_name].ga)
        theirs = (p["gp"], p["gf"], p["ga"])
        if mine != theirs:
            mismatches.append(f"{ours_name}: ours P{mine[0]} F{mine[1]} A{mine[2]} v table P{theirs[0]} F{theirs[1]} A{theirs[2]}")
    if mismatches:
        problems.append(f"{len(mismatches)} club(s) differ from the {source} table: " + "; ".join(mismatches[:6])
                        + (" ..." if len(mismatches) > 6 else ""))
    elif mapped:
        notes.append(f"all {len(mapped)} clubs match the {source} table (played, scored, conceded)")
    return problems, notes
