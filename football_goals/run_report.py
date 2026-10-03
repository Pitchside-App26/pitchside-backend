"""Weekly football goals report.

    python -m football_goals.run_report                 # next Saturday
    python -m football_goals.run_report --date 2026-10-03

Writes site/index.html (the phone report), site/report.csv, adds the
fixtures to data/history.csv, and prints a summary for the Actions page."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import history, render, scope
from .http_cache import FetchError
from .leagues import LEAGUES
from .names import best_match
from .sources import api_football, bbc, espn, football_data, livescore
from .stats import fixture_markets, league_rates, team_stats
from .validate import GP_OUTLIER, internal_checks, table_check

HERE = Path(__file__).parent
log = logging.getLogger("football_goals")


def next_saturday(today: date) -> date:
    return today + timedelta(days=(5 - today.weekday()) % 7)


def load_config() -> dict:
    return yaml.safe_load((HERE / "config.yaml").read_text())


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")


def _espn_crosscheck(league, on, fixtures, clubs, notes, problems):
    """Use ESPN's fixture list to drop postponed games and catch any the
    fixtures file is missing. Returns (fixtures, postponed)."""
    events = espn.scoreboard(league.espn_slug, on)
    postponed, seen = [], set()
    by_pair = {(f["home"], f["away"]): f for f in fixtures}
    for ev in events:
        h, a = best_match(ev["home"], clubs), best_match(ev["away"], clubs)
        if not h or not a:
            problems.append(f"ESPN fixture '{ev['home']} v {ev['away']}' could not be matched to this league's clubs")
            continue
        seen.add((h, a))
        if ev["status"] in espn.OFF_STATUSES:
            postponed.append({"home": h, "away": a, "status": ev["status"].replace("STATUS_", "").title()})
            by_pair.pop((h, a), None)
        elif (h, a) in by_pair:
            by_pair[(h, a)]["kickoff"] = ev["kickoff"]  # ESPN gives an exact UK kick-off time
        else:
            by_pair[(h, a)] = {"home": h, "away": a, "kickoff": ev["kickoff"], "note": "listed by ESPN only"}
    for pair, f in by_pair.items():
        if pair not in seen and events:
            f["note"] = "not on ESPN's list - check it's still on"
    notes.append(f"fixtures cross-checked with ESPN ({len(events)} listed, {len(postponed)} postponed)")
    return list(by_pair.values()), postponed


LIVESCORE_MIN_AGREEMENT = 0.97
_ls_check: dict = {}


def livescore_accuracy(on):
    """LiveScore v football-data.co.uk on the National League (both cover it),
    worked out once per run. Returns (problems, notes) for the regional leagues."""
    if on not in _ls_check:
        try:
            ref, _ = football_data.load_results("EC", on)
            agree, n, diffs = livescore.agreement_with(ref, on)
        except Exception as e:  # noqa: BLE001
            _ls_check[on] = ([f"could not measure LiveScore's accuracy against football-data.co.uk: {e}"], [])
        else:
            rate = agree / n if n else 0
            msg = (f"LiveScore accuracy check: {agree}/{n} National League results identical to football-data.co.uk "
                   f"(full-time and half-time)")
            if n < 20 or rate < LIVESCORE_MIN_AGREEMENT:
                _ls_check[on] = ([msg + (" - too few to trust" if n < 20 else " - below 97%") +
                                  (": " + "; ".join(diffs) if diffs else "")], [])
            else:
                _ls_check[on] = ([], [msg + (" - differences: " + "; ".join(diffs) if diffs else "")])
            log.info(msg)
    return _ls_check[on]


def load_regional(league, on, notes, problems):
    """National League North/South: LiveScore first, API-Football if LiveScore fails."""
    try:
        results, meta = livescore.load_results(league.regional, on)
        fixtures, postponed = livescore.fixtures_on(league.regional, on)
        p, n = livescore_accuracy(on)
        problems += p
        notes += n + ["results, fixtures and postponements from LiveScore (unofficial feed)"]
        return results, meta, fixtures, postponed
    except Exception as ls_err:  # noqa: BLE001
        log.warning("%s: LiveScore failed (%s); trying API-Football", league.name, ls_err)
        try:
            results, meta = api_football.load_results(league.regional, on)
            fixtures, postponed = api_football.fixtures_on(league.regional, on)
        except Exception as af_err:  # noqa: BLE001
            raise RuntimeError(f"LiveScore failed ({ls_err}); API-Football backup failed ({af_err})") from af_err
        notes.append("LiveScore unavailable, so results, fixtures and postponements came from API-Football")
        return results, meta, fixtures, postponed


def analyse_league(league, on, fd_fixtures, cfg):
    """Everything for one league. Raises if the league can't be loaded."""
    t = cfg["thresholds"]
    notes, problems, postponed = [], [], []
    if league.fd_code:
        results, meta = football_data.load_results(league.fd_code, on)
        fixtures = [dict(f) for f in fd_fixtures.get(league.fd_code, [])]
    else:
        results, meta, fixtures, postponed = load_regional(league, on, notes, problems)
    if not results:
        raise ValueError("no completed results found for this season")
    stats = team_stats(results)

    if league.espn_slug:
        try:
            fixtures, postponed = _espn_crosscheck(league, on, fixtures, set(stats), notes, problems)
        except FetchError as e:
            problems.append(f"could not cross-check fixtures with ESPN ({e}); postponements may be missed")
    elif league.fd_code:
        notes.append("no second fixture source for this league; postponements rely on football-data.co.uk's list")

    p, n = internal_checks(league, results, stats, fixtures)
    problems += p
    notes += n
    table_ok = False
    try:
        table, source = None, None
        # An independent publisher's table, never the results source's own.
        if league.espn_slug:
            table, source = espn.standings(league.espn_slug), "ESPN"
        elif league.bbc_slug:
            table, source = bbc.table(league.bbc_slug), "BBC Sport"
        if table is None:
            notes.append("no published table available for an independent check")
        else:
            p, n = table_check(stats, table, source)
            problems += p
            notes += n
            table_ok = not p
            if table_ok:
                # The published table shows the same odd games-played count, so it's
                # real (postponements, a late-admitted club), not a data error.
                for q in [q for q in problems if q.startswith(GP_OUTLIER)]:
                    problems.remove(q)
                    notes.append(q + f" - confirmed by the {source} table, so genuine, not a data error")
    except Exception as e:  # noqa: BLE001 -- a failed check is reported, not fatal
        problems.append(f"published-table check could not run: {e}")

    latest = meta.get("latest_result")
    if latest:
        age = (on - date.fromisoformat(latest)).days
        if age > cfg["data"]["max_results_age_days"]:
            msg = f"newest result is {age} days old ({latest})"
            if table_ok:
                notes.append(msg + " - fine: the published table agrees nothing has been missed (e.g. international break)")
            else:
                problems.append(msg + " and no published table could confirm it is up to date")

    lr = league_rates(results)
    rows = []
    for f in fixtures:
        h, a = stats.get(f["home"]), stats.get(f["away"])
        o = fixture_markets(h, a, "o15", t["min_games"])
        g = fixture_markets(h, a, "gibh", t["min_games"])
        flags = list(o["flags"])
        if f.get("note"):
            flags.append(f["note"])
        if problems:
            flags.append("data check failed - see top")
        rows.append({"league": league.key, "league_name": league.name, "home": f["home"], "away": f["away"],
                     "kickoff": f.get("kickoff") or "", "o15": o, "gibh": g, "flags": flags,
                     "low_games": bool(o["flags"]), "data_problem": bool(problems)})
    return {
        "league": league, "results": len(results), "teams": len(stats), "rows": rows, "postponed": postponed,
        "rates": {"o15": lr.pct("o15"), "gibh": lr.pct("gibh"), "gp": lr.gp},
        "meta": meta, "notes": notes, "problems": problems,
    }


ACCA = {  # market -> (config section, row/history tag, label)
    "o15": ("accumulator", "acca", "Over 1.5"),
    "gibh": ("gibh_accumulator", "gibh_acca", "goal in both halves"),
}


def build_acca(rows, cfg, market: str, odds_on: bool):
    section, tag, label = ACCA[market]
    a = cfg[section]
    min_pct = a["min_combined_pct"] / 100
    pool = [r for r in rows
            if r[market]["combined_pct"] is not None and r[market]["combined_pct"] >= min_pct
            and not r["data_problem"] and not (a["require_min_games"] and r["low_games"])]
    if market == "o15" and odds_on and cfg["odds"]["min_price"] > 1.0:  # prices exist for Over 1.5 only
        pool = [r for r in pool if r.get("price") and r["price"]["price"] > cfg["odds"]["min_price"]]
    pool.sort(key=lambda r: (r[market]["combined_pct"], r[market]["venue_pct"] or 0,
                             min(r[market]["home_gp"], r[market]["away_gp"])), reverse=True)
    n, lo, hi, nres = len(pool), a["min_legs"], a["max_legs"], a["reserves"]
    if n >= lo + nres:
        k = min(hi, n - nres)
    elif n >= lo:
        k = lo
    else:
        k = 0
    legs, reserves = pool[:k], pool[k:k + nres]
    below = []
    if k and len(reserves) < nres and a.get("fill_reserves_below_line", False):
        # Short of reserves: offer the best fixtures just under the bar, clearly marked,
        # so a leg the bookmaker won't take (e.g. priced too short for a boost) can still be swapped.
        under = [r for r in rows
                 if r[market]["combined_pct"] is not None and r[market]["combined_pct"] < min_pct
                 and not r["data_problem"] and not (a["require_min_games"] and r["low_games"])]
        if market == "o15" and odds_on and cfg["odds"]["min_price"] > 1.0:  # same price rule as the legs
            under = [r for r in under if r.get("price") and r["price"]["price"] > cfg["odds"]["min_price"]]
        under.sort(key=lambda r: (r[market]["combined_pct"], r[market]["venue_pct"] or 0,
                                  min(r[market]["home_gp"], r[market]["away_gp"])), reverse=True)
        below = under[:nres - len(reserves)]
    pct = a["min_combined_pct"]
    if k == 0:
        msg = (f"Only {n} fixture{'s' if n != 1 else ''} qualif{'y' if n != 1 else 'ies'} "
               f"({label} combined {pct}%+, every team {cfg['thresholds']['min_games']}+ games, "
               f"data checks passed) - not enough for a {lo}-{hi} fold. They are listed below as candidates.")
        legs, reserves = [], pool
    elif below:
        msg = (f"{k}-fold. {len(reserves)} reserve{'s' if len(reserves) != 1 else ''} at {pct}%+, "
               f"plus {len(below)} below the line (under {pct}%).")
    elif len(reserves) < nres:
        msg = f"{k}-fold. Only {len(reserves)} reserve{'s' if len(reserves) != 1 else ''} available (wanted {nres})."
    else:
        msg = f"{k}-fold with {len(reserves)} reserves."
    for r in legs:
        r[tag] = "leg"
    for r in reserves:
        r[tag] = "reserve" if k else "candidate"
    for r in below:
        r[tag] = "below_line"
    return {"legs": legs, "reserves": reserves, "below_line": below, "message": msg, "pool": n,
            "note": (a.get("note") or "").strip(), "min_pct": pct}


def run(on: date, cfg: dict) -> dict:
    log.info("Report for %s", on.isoformat())
    loaded, failed = [], []
    try:
        fd_fixtures, fx_meta = football_data.load_fixtures(on)
        log.info("fixtures.csv: %s", {k: len(v) for k, v in fd_fixtures.items()})
    except Exception as e:  # noqa: BLE001
        log.error("fixtures.csv failed: %s", e)
        fd_fixtures, fx_meta = {}, {"error": str(e)}

    for lg in LEAGUES:
        try:
            if lg.fd_code and "error" in fx_meta:
                raise RuntimeError(f"fixture list unavailable: {fx_meta['error']}")
            res = analyse_league(lg, on, fd_fixtures, cfg)
            loaded.append(res)
            log.info("%-22s %3d results, %2d clubs, %2d fixtures, %d postponed, %d problem(s)",
                     lg.name, res["results"], res["teams"], len(res["rows"]), len(res["postponed"]), len(res["problems"]))
            for p in res["problems"]:
                log.warning("%s: %s", lg.name, p)
        except Exception as e:  # noqa: BLE001 -- one league failing must not sink the report
            log.error("%s FAILED: %s", lg.name, e, exc_info=not isinstance(e, (FetchError, RuntimeError)))
            failed.append({"league": lg, "reason": str(e)})

    rows = [r for res in loaded for r in res["rows"]]
    odds_info = {"enabled": bool(cfg["odds"]["enabled"]), "priced_leagues": [], "unpriced_leagues": []}
    if odds_info["enabled"]:
        from .odds import over15_prices
        for res in loaded:
            lg = res["league"]
            if not res["rows"]:
                continue
            try:
                prices = over15_prices(lg, res["rows"], on, cfg["odds"]["bookmaker_region"]) if lg.odds_key else {}
            except Exception as e:  # noqa: BLE001
                log.warning("odds for %s failed: %s", lg.name, e)
                prices = {}
            for r in res["rows"]:
                r["price"] = prices.get((r["home"], r["away"]))
            (odds_info["priced_leagues"] if prices else odds_info["unpriced_leagues"]).append(lg.name)

    def market_rows(mk):
        keep = [r for r in rows if scope.in_scope(cfg, mk, r["league_name"], r["kickoff"])]
        log.info("%s: %d of %d fixtures in scope (%s)", mk, len(keep), len(rows), scope.describe(cfg, mk))
        return sorted(keep, key=lambda r: (r[mk]["combined_pct"] is not None, r[mk]["combined_pct"] or 0), reverse=True)
    o15, gibh = market_rows("o15"), market_rows("gibh")
    accas = {"o15": build_acca(o15, cfg, "o15", odds_info["enabled"]),
             "gibh": build_acca(gibh, cfg, "gibh", odds_info["enabled"])}

    hist_rows = []
    for res in loaded:
        for r in res["rows"]:
            pct = lambda m, k: None if r[m][k] is None else round(100 * r[m][k], 1)  # noqa: E731
            hist_rows.append({
                "report_date": on.isoformat(), "league": r["league"], "home": r["home"], "away": r["away"],
                "league_name": r["league_name"], "kickoff": r["kickoff"],
                "o15_combined": pct("o15", "combined_pct"), "o15_venue": pct("o15", "venue_pct"),
                "o15_league_rate": round(100 * res["rates"]["o15"], 1),
                "gibh_combined": pct("gibh", "combined_pct"), "gibh_venue": pct("gibh", "venue_pct"),
                "gibh_league_rate": round(100 * res["rates"]["gibh"], 1),
                "acca": r.get("acca", ""), "gibh_acca": r.get("gibh_acca", ""), "price": (r.get("price") or {}).get("price"),
                "flags": "; ".join(r["flags"]),
            })
    history.record_report(hist_rows, on.isoformat(), leagues={res["league"].key for res in loaded})

    hit_rates = history.hit_rates(cfg=cfg)
    return {
        "date": on, "generated": datetime.now(timezone.utc), "loaded": loaded, "failed": failed,
        "o15": o15, "gibh": gibh, "accas": accas, "odds": odds_info, "fixtures_meta": fx_meta,
        "postponed": [dict(p, league=res["league"].name) for res in loaded for p in res["postponed"]],
        "hit_rates": hit_rates, "config": cfg, "fixtures_total": len(rows),
        "results_html": render.results_section(history.load(), hit_rates, cfg),
    }


def main(argv=None) -> int:
    setup_logging()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD (default: next Saturday, or today if it's Saturday)")
    args = ap.parse_args(argv)
    on = date.fromisoformat(args.date.strip()) if args.date and args.date.strip() else next_saturday(date.today())
    report = run(on, load_config())
    site = HERE / "site"
    site.mkdir(exist_ok=True)
    (site / "index.html").write_text(render.html(report), encoding="utf-8")
    render.csv(report, site / "report.csv")
    (site / "results.html").write_text(render.REDIRECT, encoding="utf-8")  # old bookmarks
    md = render.markdown_summary(report)
    print("\n" + md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(md)
    log.info("Wrote %s and report.csv", site / "index.html")
    return 0 if report["loaded"] else 1


if __name__ == "__main__":
    sys.exit(main())
