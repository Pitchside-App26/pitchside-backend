"""Turn a report dict into the phone-friendly HTML page, the CSV, and a short
markdown summary for the GitHub Actions run page."""
from __future__ import annotations

import csv as _csv
from html import escape
from zoneinfo import ZoneInfo

from . import scope, update_button

UK = ZoneInfo("Europe/London")
MARKETS = (("o15", "Over 1.5 goals", "over_1_5_highlight"), ("gibh", "Goal in both halves", "gibh_highlight"))


def pct(x, dp=0):
    return "–" if x is None else f"{100 * x:.{dp}f}%"


def _fixture(r):
    return f"{r['home']} v {r['away']}"


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16191d;--muted:#5d6670;--line:#e2e5e9;--hi:#e7f6ec;--hi-ink:#11622f;
--warn-bg:#fff4e0;--warn:#8a4b00;--bad-bg:#fdecec;--bad:#9b1c1c;--accent:#1f5fbf;--chip:#eef1f5}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1216;--card:#171b21;--ink:#e8ebef;
--muted:#9aa3ad;--line:#2a3038;--hi:#12301d;--hi-ink:#7fdc9f;--warn-bg:#33270f;--warn:#ffc46b;--bad-bg:#3a1717;
--bad:#ff9b9b;--accent:#7fb0ff;--chip:#222831}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}
h1{font-size:1.45rem;margin:.2rem 0}h2{font-size:1.15rem;margin:1.6rem 0 .5rem}
.sub{color:var(--muted);font-size:.88rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:10px 0}
.alert{border-radius:12px;padding:10px 14px;margin:10px 0}
.alert.bad{background:var(--bad-bg);color:var(--bad)}.alert.warn{background:var(--warn-bg);color:var(--warn)}
.alert ul{margin:.3rem 0 0;padding-left:1.1rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.kpi b{display:block;font-size:1.35rem}.kpi span{color:var(--muted);font-size:.8rem}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:.9rem}
th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);background:var(--chip)}
td.n,th.n{text-align:right;white-space:nowrap}
tr.hi td{background:var(--hi)}tr.hi td.comb{color:var(--hi-ink);font-weight:700}
.flag{display:inline-block;background:var(--warn-bg);color:var(--warn);border-radius:6px;padding:0 6px;margin:1px 2px 1px 0;font-size:.75rem}
.gp{color:var(--muted);font-size:.75rem}
.lg{color:var(--muted);font-size:.78rem}
details summary{cursor:pointer;font-weight:600}
.mob{display:none}
.tabs{position:sticky;top:0;z-index:5;display:flex;gap:4px;background:var(--bg);padding:10px 0 8px;margin-top:1.2rem}
.tab{flex:1;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:10px 6px;
 font:600 .95rem/1.2 inherit;cursor:pointer;text-align:center}
.tab span{display:block;font-weight:400;font-size:.75rem;color:var(--muted);margin-top:2px}
.tab[aria-selected="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.tab[aria-selected="true"] span{color:#fff;opacity:.85}
.js .panel[hidden]{display:none}""" + update_button.CSS + """
ol.acca{padding-left:1.4rem;margin:.3rem 0}ol.acca li{margin:.25rem 0}
.pill{display:inline-block;background:var(--chip);border-radius:999px;padding:1px 8px;font-size:.78rem;margin-left:4px}
@media (max-width:640px){
 table.rt thead{display:none}
 table.rt,table.rt tbody,table.rt tr,table.rt td{display:block;width:100%}
 table.rt{border:none;background:none}
 table.rt tr{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:8px 0;padding:6px 10px}
 table.rt tr.hi{background:var(--hi)}table.rt tr.hi td{background:none}
 table.rt td{border:none;padding:2px 0;display:flex;justify-content:space-between;gap:12px;text-align:right}
 table.rt td::before{content:attr(data-l);color:var(--muted);font-size:.8rem;text-align:left}
 table.rt td.fx{display:block;text-align:left;font-weight:600;font-size:1rem}table.rt td.fx::before{content:none}
 table.rt td.fl{display:block;text-align:left}table.rt td.fl::before{content:none}
 table.rt td.lgcol{display:none}.mob{display:block}
}
"""


def _market_table(report, mk, title, thr_key):
    cfg = report["config"]
    thr = cfg["thresholds"][thr_key] / 100
    odds = report["odds"]["enabled"]
    rows = report[mk]
    head = ("<tr><th>League</th><th>Fixture</th><th>KO</th><th class=n>Home %</th><th class=n>Away %</th>"
            "<th class=n>Combined</th><th class=n>Venue-split</th>" + ("<th class=n>Price</th>" if odds else "")
            + "<th>Flags</th></tr>")
    body = []
    for r in rows:
        m = r[mk]
        hi = m["combined_pct"] is not None and m["combined_pct"] >= thr
        price = ""
        if odds:
            p = r.get("price") if mk == "o15" else None
            price = f"<td class=n data-l='Price'>{p['price']:.2f}<div class=gp>{escape(p['book'])}</div></td>" if p else "<td class=n data-l='Price'>–</td>"
        flags = "".join(f"<span class=flag>{escape(f)}</span>" for f in r["flags"])
        body.append(
            f"<tr class='{'hi' if hi else ''}'><td data-l='League' class='lg lgcol'>{escape(r['league_name'])}</td>"
            f"<td class=fx>{escape(_fixture(r))}<div class='lg mob' style='font-weight:400'>{escape(r['league_name'])}</div></td>"
            f"<td data-l='Kick-off'>{escape(r['kickoff'] or '–')}</td>"
            f"<td class=n data-l='Home %'><span>{pct(m['home_pct'])} <span class=gp>{m['home_gp']}g</span></span></td>"
            f"<td class=n data-l='Away %'><span>{pct(m['away_pct'])} <span class=gp>{m['away_gp']}g</span></span></td>"
            f"<td class='n comb' data-l='Combined %'>{pct(m['combined_pct'], 1)}</td>"
            f"<td class=n data-l='Venue-split %'>{pct(m['venue_pct'], 1)}</td>{price}"
            f"<td class=fl data-l='Flags'>{flags}</td></tr>")
    n_hi = sum(1 for r in rows if r[mk]["combined_pct"] is not None and r[mk]["combined_pct"] >= thr)
    return (f"<h2>{title} <span class=pill>{n_hi} at {cfg['thresholds'][thr_key]}%+</span></h2>"
            f"<p class=sub><b>Covers: {escape(scope.describe(cfg, mk))}.</b> "
            f"Sorted by combined %. Highlighted rows are at or above {cfg['thresholds'][thr_key]}%. "
            f"Venue-split = home team's home games and away team's away games.</p>"
            f"<table class=rt><thead>{head}</thead><tbody>{''.join(body) or '<tr><td>No fixtures.</td></tr>'}</tbody></table>")


ACCA_TITLE = {"o15": "Suggested Over 1.5 accumulator", "gibh": "Suggested goal-in-both-halves accumulator"}


def _acca(report, mk):
    a = report["accas"][mk]
    odds = report["odds"]["enabled"] and mk == "o15"  # no bookmaker prices for GIBH

    def li(r, mark=""):
        p = r.get("price")
        price = f" <span class=pill>{p['price']:.2f}</span>" if odds and p else ""
        tag = f" <span class=flag>{escape(mark)}</span>" if mark else ""
        return (f"<li><b>{escape(_fixture(r))}</b> <span class=lg>{escape(r['league_name'])}, {escape(r['kickoff'] or '')}</span>"
                f" <span class=pill>{pct(r[mk]['combined_pct'], 1)}</span>{price}{tag}</li>")
    out = [f"<h2>{ACCA_TITLE[mk]}</h2><div class=card><p>{escape(a['message'])}</p>"]
    if a.get("note"):  # e.g. the bookmaker's boost rule: read before placing, so it sits at the top
        out.append(f"<div class='alert warn' style='margin:.2rem 0 .6rem'>{escape(a['note'])}</div>")
    if a["legs"]:
        out.append(f"<ol class=acca>{''.join(li(r) for r in a['legs'])}</ol>")
        if odds and all(r.get("price") for r in a["legs"]):
            tot = 1.0
            for r in a["legs"]:
                tot *= r["price"]["price"]
            out.append(f"<p class=sub>Combined price at best quoted prices: {tot:.2f}</p>")
    below = a.get("below_line") or []
    if a["reserves"] or below:
        label = "Reserves" if a["legs"] else "Qualifying fixtures"
        items = "".join(li(r) for r in a["reserves"])
        items += "".join(li(r, f"below {a.get('min_pct', '')}%") for r in below)
        out.append(f"<p><b>{label}</b> <span class=sub>in order: use the top one first</span></p><ol class=acca>{items}</ol>")

    if mk == "gibh" and report["odds"]["enabled"]:
        out.append("<p class=sub>Prices are only fetched for Over 1.5, so this tab has none.</p>")
    out.append("</div>")
    return "".join(out)


def _p0(x):
    return "–" if x is None else f"{x:.0f}%"


def _rates_table(stats_by, first_col):
    rows = []
    for name, s in stats_by.items():
        diff = None if s["hit_pct"] is None or s["league_avg_pct"] is None else s["hit_pct"] - s["league_avg_pct"]
        rows.append(f"<tr><td>{escape(name)}</td><td class=n>{s['hits']}/{s['n']}</td><td class=n>{_p0(s['hit_pct'])}</td>"
                    f"<td class=n>{_p0(s['league_avg_pct'])}</td><td class=n>{'–' if diff is None else f'{diff:+.0f}'}</td></tr>")
    return (f"<table><thead><tr><th>{first_col}</th><th class=n>Landed</th><th class=n>Hit %</th>"
            f"<th class=n>League avg</th><th class=n>+/-</th></tr></thead><tbody>{''.join(rows)}</tbody></table>")


def _track(hit_rates, only: str | None = None):
    hr = hit_rates
    if not hr["graded"]:
        return ("<h2>Track record</h2><div class=card><p class=sub>No graded fixtures yet. After this weekend the Sunday "
                "results run will record whether each market landed, and running hit rates will appear here.</p></div>")
    out = [f"<h2>Track record</h2><p class=sub>{hr['graded']} graded fixtures so far. 'League avg' is the season-to-date "
           "rate of the same leagues at the time of each report: beating it means the selection adds something.</p>"]
    for label, d in hr["markets"].items():
        if only and label != only:
            continue
        if d.get("acca"):
            a = d["acca"]
            out.append(f"<div class=card>{label} accumulators: <b>{a['won']}/{a['weeks']}</b> landed in full; "
                       f"legs {a['legs_won']}/{a['legs']} won.</div>")
        out.append(f"<details class=card open><summary>{label}, every fixture: {d['overall']['hits']}/{d['overall']['n']}"
                   f" ({d['overall']['hit_pct']:.0f}% v league avg {d['overall']['league_avg_pct']:.0f}%)</summary>")
        out.append("<p class=sub>By combined-% band</p>" + _rates_table(d["by_band"], "Band"))
        out.append("<p class=sub>By league</p>" + _rates_table(d["by_league"], "League") + "</details>")
    return "".join(out)


def _data_section(report):
    out = ["<h2>Data sources and checks</h2>"]
    rows = []
    for res in report["loaded"]:
        lg, meta = res["league"], res["meta"]
        status = "⚠️ check" if res["problems"] else "✅"
        rows.append(f"<tr><td>{escape(lg.name)}</td><td>{status}</td><td>{escape(meta['source'])}</td>"
                    f"<td class=n>{res['results']}</td><td class=n>{escape(meta.get('latest_result') or '–')}</td>"
                    f"<td class=n>{pct(res['rates']['o15'])}</td><td class=n>{pct(res['rates']['gibh'])}</td></tr>")
    for f in report["failed"]:
        rows.append(f"<tr><td>{escape(f['league'].name)}</td><td>❌ not loaded</td><td colspan=5>{escape(f['reason'])}</td></tr>")
    out.append("<table><thead><tr><th>League</th><th>Status</th><th>Source</th><th class=n>Results</th>"
               "<th class=n>Newest result</th><th class=n>League O1.5</th><th class=n>League GIBH</th></tr></thead>"
               f"<tbody>{''.join(rows)}</tbody></table>")
    for res in report["loaded"]:
        items = [f"<li>❗ {escape(p)}</li>" for p in res["problems"]] + [f"<li>{escape(n)}</li>" for n in res["notes"]]
        lm = res["meta"].get("last_modified")
        if lm:
            items.append(f"<li>source file last updated {escape(lm)}</li>")
        out.append(f"<details class=card><summary>{escape(res['league'].name)}</summary><ul>{''.join(items)}</ul></details>")
    return "".join(out)


TABS = (("o15", "Over 1.5", "Over 1.5 goals", "over_1_5_highlight", "Over 1.5"),
        ("gibh", "Goal in both halves", "Goal in both halves", "gibh_highlight", "Goal in both halves"))

# Shows one market at a time. Without JavaScript both panels simply show one after the other.
# The chosen tab is kept in the address (#gibh) so it can be bookmarked, and remembered on this phone.
TAB_JS = """<script>
(function(){
  document.documentElement.classList.add('js');
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  function show(id,save){
    tabs.forEach(function(t){var on=t.dataset.tab===id;t.setAttribute('aria-selected',on);
      document.getElementById('panel-'+t.dataset.tab).hidden=!on;});
    if(save){try{localStorage.setItem('goals-tab',id)}catch(e){}
      history.replaceState(null,'','#'+id);}
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){show(t.dataset.tab,true)})});
  var start=(location.hash||'').slice(1);
  if(!document.getElementById('panel-'+start)){try{start=localStorage.getItem('goals-tab')}catch(e){start=null}}
  show(document.getElementById('panel-'+start)?start:'o15',false);
})();
</script>"""


def _tabs(report):
    cfg = report["config"]
    buttons, panels = [], []
    for mk, short, title, thr_key, track_label in TABS:
        a = report["accas"][mk]
        size = f"{len(a['legs'])}-fold" if a["legs"] else f"{len(a['reserves'])} qualify"
        thr = cfg["thresholds"][thr_key] / 100
        n_hi = sum(1 for r in report[mk] if r[mk]["combined_pct"] is not None and r[mk]["combined_pct"] >= thr)
        buttons.append(f"<button class=tab role=tab data-tab={mk} aria-selected=false aria-controls=panel-{mk}>"
                       f"{short}<span>{size} · {n_hi} at {cfg['thresholds'][thr_key]}%+</span></button>")
        panels.append(f"<section class=panel id=panel-{mk} role=tabpanel>{_acca(report, mk)}"
                      f"{_market_table(report, mk, title, thr_key)}{_track(report['hit_rates'], track_label)}</section>")
    return f"<nav class=tabs role=tablist>{''.join(buttons)}</nav>{''.join(panels)}"


def html(report) -> str:
    d = report["date"]
    gen = report["generated"].astimezone(UK).strftime("%a %d %b %Y, %H:%M UK")
    cfg = report["config"]
    alerts = []
    if report["failed"]:
        alerts.append("<div class='alert bad'><b>Leagues not loaded</b> – everything else below is complete:<ul>"
                      + "".join(f"<li><b>{escape(f['league'].name)}</b>: {escape(f['reason'])}</li>" for f in report["failed"])
                      + "</ul></div>")
    flagged = [res for res in report["loaded"] if res["problems"]]
    if flagged:
        alerts.append("<div class='alert warn'><b>Data checks need a look</b> – these leagues' fixtures are flagged and "
                      "kept out of both accumulators:<ul>" + "".join(
                          f"<li><b>{escape(res['league'].name)}</b>: {escape('; '.join(res['problems']))}</li>" for res in flagged)
                      + "</ul></div>")
    newest = max((res["meta"].get("latest_result") or "" for res in report["loaded"]), default="")
    post = report["postponed"]
    post_html = ("<details class=card><summary>Postponed / called off (" + str(len(post)) + ")</summary><ul>"
                 + "".join(f"<li>{escape(p['league'])}: {escape(p['home'])} v {escape(p['away'])} ({escape(p['status'])})</li>" for p in post)
                 + "</ul></details>") if post else "<p class=sub>No postponed games found on the fixture lists.</p>"
    odds = report["odds"]
    odds_html = ""
    if odds["enabled"]:
        odds_html = (f"<p class=sub>Prices (best UK price, Over 1.5) available for: {escape(', '.join(odds['priced_leagues']) or 'none')}. "
                     f"No prices for: {escape(', '.join(odds['unpriced_leagues']) or 'none')}.</p>")
    n_fx = report.get("fixtures_total", len(report["o15"]))
    kpis = (f"<div class=kpis><div class=kpi><b>{n_fx}</b><span>fixtures analysed</span></div>"
            f"<div class=kpi><b>{len(report['loaded'])}/{len(report['loaded']) + len(report['failed'])}</b><span>leagues loaded</span></div>"
            f"<div class=kpi><b>{len(post)}</b><span>postponed</span></div>"
            f"<div class=kpi><b>{escape(newest or '–')}</b><span>newest result in data</span></div></div>")
    body = (f"<main><h1>Goals report – {d.strftime('%A %d %B %Y')}</h1>"
            f"<p class=sub>Generated {gen}. League matches only, this season. Figures are calculated from match results, "
            f"not copied from stats sites.</p>"
            f"{update_button.panel('football-goals-report.yml', 'Update now', with_date=True)}"
            f"{''.join(alerts)}{kpis}{post_html}{odds_html}"
            f"{_tabs(report)}{_data_section(report)}"
            f"<h2>How the numbers work</h2><div class=card><p class=sub>For each team: Over 1.5 % = league games with 2+ "
            f"goals ÷ games played. Goal-in-both-halves % = games with at least one goal in each half ÷ games played "
            f"(second-half goals = full-time total minus half-time total). Combined % = average of the two teams. "
            f"Teams with fewer than {cfg['thresholds']['min_games']} games are flagged. "
            f"<a href='report.csv'>Download the CSV</a> · <a href='results.html'>Last weekend's results</a>.</p></div></main>")
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Goals Report {d.isoformat()}</title><style>{CSS}</style></head><body>{body}{TAB_JS}</body></html>")


def csv(report, path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = _csv.writer(fh)
        w.writerow(["market", "league", "fixture", "kickoff", "home_pct", "away_pct", "combined_pct", "venue_split_pct",
                    "home_games", "away_games", "flags", "accumulator", "over_1_5_price"])
        for mk, label, _ in MARKETS:
            for r in report[mk]:
                m = r[mk]
                f = lambda x: "" if x is None else round(100 * x, 1)  # noqa: E731
                w.writerow([label, r["league_name"], _fixture(r), r["kickoff"], f(m["home_pct"]), f(m["away_pct"]),
                            f(m["combined_pct"]), f(m["venue_pct"]), m["home_gp"], m["away_gp"], "; ".join(r["flags"]),
                            r.get("acca" if mk == "o15" else "gibh_acca", ""),
                            (r.get("price") or {}).get("price", "") if mk == "o15" else ""])


def markdown_summary(report) -> str:
    cfg = report["config"]
    lines = [f"## Goals report – {report['date'].strftime('%a %d %b %Y')}", ""]
    if report["failed"]:
        lines.append("**Not loaded:** " + "; ".join(f"{f['league'].name} ({f['reason']})" for f in report["failed"]))
    lines.append("**Loaded:** " + ", ".join(
        f"{r['league'].name}{' ⚠️' if r['problems'] else ''}" for r in report["loaded"]))
    lines.append(f"**Postponed:** {len(report['postponed'])}  ·  **Fixtures analysed:** {len(report['o15'])}")
    lines += ["", f"**Over 1.5 accumulator:** {report['accas']['o15']['message']}",
              f"**Goal-in-both-halves accumulator:** {report['accas']['gibh']['message']}", ""]
    for mk, title, key in MARKETS:
        thr = cfg["thresholds"][key]
        lines += [f"### {title} (highlight {thr}%+)", "", "| League | Fixture | KO | Home % | Away % | Combined | Venue-split | Flags |",
                  "|---|---|---|--:|--:|--:|--:|---|"]
        for r in report[mk]:
            m = r[mk]
            star = " ✅" if m["combined_pct"] is not None and m["combined_pct"] >= thr / 100 else ""
            lines.append(f"| {r['league_name']} | {_fixture(r)} | {r['kickoff']} | {pct(m['home_pct'])} | {pct(m['away_pct'])} | "
                         f"**{pct(m['combined_pct'], 1)}**{star} | {pct(m['venue_pct'], 1)} | {'; '.join(r['flags'])} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def results_page(df, hit_rates, cfg: dict | None = None) -> str:
    """Last graded weekend fixture by fixture, plus the running record."""
    g = df[df["status"].isin(["graded", "void"])]
    if g.empty:
        body = "<p class=sub>Nothing graded yet.</p>"
        last = None
    else:
        last = g["report_date"].max()
        wk = g[g["report_date"] == last].sort_values("o15_combined", ascending=False)
        rows = []
        for r in wk.itertuples():
            if r.status == "void":
                rows.append(f"<tr><td>{escape(r.home)} v {escape(r.away)}<div class=lg>{escape(r.league_name)}</div></td>"
                            f"<td colspan=4>postponed – void</td></tr>")
                continue
            def tick(mk, hit, r=r):  # "–" = that market didn't cover this fixture
                if cfg is not None and not scope.in_scope(cfg, mk, r.league_name, r.kickoff):
                    return "–"
                return "✅" if str(hit).lower() in ("true", "1", "1.0") else "❌"
            rows.append(f"<tr><td>{escape(r.home)} v {escape(r.away)}<div class=lg>{escape(r.league_name)}"
                        f"{' · O1.5 acca ' + escape(str(r.acca)) if isinstance(r.acca, str) and r.acca else ''}"
                        f"{' · GIBH acca ' + escape(str(r.gibh_acca)) if isinstance(r.gibh_acca, str) and r.gibh_acca else ''}</div></td>"
                        f"<td class=n>{r.fthg}-{r.ftag} <span class=gp>HT {r.hthg}-{r.htag}</span></td>"
                        f"<td class=n>{r.o15_combined:.0f}% {tick('o15', r.o15_hit)}</td><td class=n>{r.gibh_combined:.0f}% {tick('gibh', r.gibh_hit)}</td></tr>")
        body = ("<table><thead><tr><th>Fixture</th><th class=n>Score</th><th class=n>O1.5</th><th class=n>GIBH</th></tr></thead>"
                f"<tbody>{''.join(rows)}</tbody></table>")
    title = f"Results – {last}" if last else "Results"
    main_ = (f"<main><h1>{title}</h1><p class=sub><a href='index.html'>← Back to the latest report</a></p>"
             f"{update_button.panel('football-goals-results.yml', 'Check results now', with_date=False)}{body}"
             f"{_track(hit_rates)}</main>")
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Goals Results</title><style>{CSS}</style></head><body>{main_}</body></html>")
