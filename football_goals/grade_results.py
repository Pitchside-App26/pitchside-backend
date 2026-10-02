"""Sunday-evening results run: for every pending fixture in data/history.csv
whose date has passed, find the half-time and full-time score and record
whether Over 1.5 and goal-in-both-halves landed.

    python -m football_goals.grade_results

Order of sources per league: football-data.co.uk (same source as the
analysis), then ESPN (often quicker on a Sunday), then API-Football for
National League North/South. A fixture that has no result yet stays
'pending' and is retried on the next run; one postponed is marked 'void'."""
from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta, timezone

from pathlib import Path

from . import history, render
from .leagues import BY_KEY
from .names import best_match
from .run_report import setup_logging
from .sources import api_football, espn, football_data, livescore
from .stats import is_goal_in_both_halves, is_over_1_5

log = logging.getLogger("football_goals.grade")
GIVE_UP_DAYS = 14


def _from_csv(league, day: date):
    try:
        rows, _ = football_data.load_results(league.fd_code, day + timedelta(days=1))
    except Exception as e:  # noqa: BLE001
        log.warning("%s: football-data CSV unavailable (%s)", league.name, e)
        return {}
    return {(r["home"], r["away"]): r for r in rows if r["date"] == day.isoformat()}


def _from_espn(league, day: date, clubs):
    out = {}
    try:
        events = espn.scoreboard(league.espn_slug, day)
    except Exception as e:  # noqa: BLE001
        log.warning("%s: ESPN unavailable (%s)", league.name, e)
        return out
    for ev in events:
        h, a = best_match(ev["home"], clubs), best_match(ev["away"], clubs)
        if not h or not a:
            continue
        if ev["status"] in espn.OFF_STATUSES:
            out[(h, a)] = "void"
        elif ev["status"] in espn.DONE_STATUSES:
            try:
                ht = espn.halftime(league.espn_slug, ev["id"])
            except Exception as e:  # noqa: BLE001 -- one bad match summary mustn't stop the rest
                log.warning("%s %s v %s: ESPN half-time unavailable (%s)", league.name, h, a, e)
                continue
            if ht:
                out[(h, a)] = {"fthg": int(ev["home_score"]), "ftag": int(ev["away_score"]), "hthg": ht[0], "htag": ht[1]}
    return out


def grade(today: date | None = None) -> dict:
    today = today or date.today()
    df = history.load()
    todo = df[(df["status"] == "pending") & (df["report_date"] < today.isoformat())]
    log.info("%d pending fixture(s) to grade", len(todo))
    counts = {"graded": 0, "void": 0, "still_pending": 0, "unresolved": 0}
    for (rd, lg_key), grp in todo.groupby(["report_date", "league"]):
        try:
            _grade_league(df, grp, BY_KEY[lg_key], date.fromisoformat(rd), today, counts)
        except Exception as e:  # noqa: BLE001 -- one league failing mustn't lose the others' results
            log.error("%s %s: grading failed (%s); its fixtures stay pending for the next run", lg_key, rd, e,
                      exc_info=True)
    history.save(df)
    log.info("Grading done: %s", counts)
    return counts


def _grade_league(df, grp, league, day: date, today: date, counts: dict) -> None:
    """Grade one league's fixtures for one report date, writing into `df`."""
    clubs = set(grp["home"]) | set(grp["away"])
    found, source = {}, {}
    if league.fd_code:
        for k, v in _from_csv(league, day).items():
            found[k], source[k] = v, "football-data.co.uk"
    missing = [(h, a) for h, a in zip(grp["home"], grp["away"]) if (h, a) not in found]
    if missing and league.espn_slug:
        for k, v in _from_espn(league, day, clubs).items():
            if k not in found:
                found[k], source[k] = v, "ESPN"
    if missing and league.regional:
        down = set()  # a source that failed once isn't retried for every remaining fixture
        for h, a in missing:
            for name, src in (("LiveScore", livescore), ("API-Football", api_football)):
                if name in down:
                    continue
                try:
                    v = src.result_on(league.regional, day, h, a)
                except Exception as e:  # noqa: BLE001
                    log.warning("%s: %s unavailable (%s)", league.name, name, e)
                    down.add(name)
                    continue
                if v is not None:
                    found[(h, a)], source[(h, a)] = v, name
                    break
    for idx, row in grp.iterrows():
        k = (row["home"], row["away"])
        res = found.get(k)
        if res == "void":
            df.loc[idx, ["status", "graded_at", "result_source"]] = ["void", _now(), source.get(k, "ESPN")]
            counts["void"] += 1
        elif res:
            try:
                o15, gibh = bool(is_over_1_5(res)), bool(is_goal_in_both_halves(res))
            except ValueError as e:  # e.g. half-time total above full-time: the source is wrong
                df.loc[idx, ["status", "graded_at", "result_source"]] = ["unresolved", _now(), f"{source[k]}: {e}"]
                counts["unresolved"] += 1
                log.warning("%s %s v %s: impossible score from %s (%s), marked unresolved", league.name, *k, source[k], e)
                continue
            df.loc[idx, ["fthg", "ftag", "hthg", "htag"]] = [res["fthg"], res["ftag"], res["hthg"], res["htag"]]
            df.loc[idx, "o15_hit"] = o15
            df.loc[idx, "gibh_hit"] = gibh
            df.loc[idx, ["status", "graded_at", "result_source"]] = ["graded", _now(), source[k]]
            counts["graded"] += 1
            log.info("%s %s v %s %d-%d (HT %d-%d): O1.5 %s, GIBH %s", league.name, k[0], k[1], res["fthg"],
                     res["ftag"], res["hthg"], res["htag"], o15, gibh)
        elif (today - day).days > GIVE_UP_DAYS:
            df.loc[idx, "status"] = "unresolved"
            counts["unresolved"] += 1
            log.warning("%s %s v %s: no result after %d days, marked unresolved", league.name, *k, GIVE_UP_DAYS)
        else:
            counts["still_pending"] += 1
            log.info("%s %s v %s: no result yet, will retry next run", league.name, *k)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    setup_logging()
    counts = grade()
    from .run_report import load_config
    cfg = load_config()
    hr = history.hit_rates(cfg=cfg)
    site = Path(__file__).parent / "site"
    site.mkdir(exist_ok=True)
    # Refresh just the Results section of the published report page.
    page = site / "index.html"
    if page.exists():
        try:
            page.write_text(render.replace_results(page.read_text(encoding="utf-8"),
                                                   render.results_section(history.load(), hr, cfg), hr),
                            encoding="utf-8")
        except ValueError as e:
            log.warning("could not update the report page's Results section: %s", e)
    (site / "results.html").write_text(render.REDIRECT, encoding="utf-8")
    for label, d in hr["markets"].items():
        o = d["overall"]
        log.info("%s running: %d/%d (%.0f%%) v league avg %.0f%%", label, o["hits"], o["n"], o["hit_pct"], o["league_avg_pct"])
    return 0 if counts is not None else 1


if __name__ == "__main__":
    sys.exit(main())
