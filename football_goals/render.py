"""Turn a report dict into the phone page (an app-style layout: one section at a
time, bottom bar for Over 1.5 / GIBH / Results / Info), the CSV, and a short
markdown summary for the GitHub Actions run page.

The Results section sits between RESULTS_START / RESULTS_END markers so the
Sunday grading run can replace just that part of the published page."""
from __future__ import annotations

import csv as _csv
from html import escape
from zoneinfo import ZoneInfo

from . import scope, update_button

UK = ZoneInfo("Europe/London")
MARKETS = (("o15", "Over 1.5 goals", "over_1_5_highlight"), ("gibh", "Goal in both halves", "gibh_highlight"))
RESULTS_START, RESULTS_END = "<!--RESULTS-->", "<!--/RESULTS-->"
SHORT = {  # compact league labels for one-line rows
    "Premier League": "PL", "Championship": "Champ", "League One": "L1", "League Two": "L2",
    "National League": "NL", "National League North": "NL North", "National League South": "NL South",
    "Scottish Premiership": "SPL", "Scottish Championship": "Sco Champ", "Scottish League One": "Sco L1",
    "Scottish League Two": "Sco L2",
}


def pct(x, dp=0):
    return "–" if x is None else f"{100 * x:.{dp}f}%"


def _fixture(r):
    return f"{r['home']} v {r['away']}"


def _short(league_name: str) -> str:
    return SHORT.get(league_name, league_name)


CSS = """
:root{--bg:#f4f5f7;--card:#fff;--ink:#15181c;--muted:#626b75;--line:#e3e6ea;--hi:#e6f5ea;--hi-ink:#0f6a32;
--warn-bg:#fff3dc;--warn:#8a4b00;--bad-bg:#fdecec;--bad:#9b1c1c;--accent:#1f5fbf;--chip:#eceff3;--nav:#ffffffee}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e1115;--card:#171b21;--ink:#e9ecef;
--muted:#97a0aa;--line:#272d35;--hi:#11301c;--hi-ink:#7fdc9f;--warn-bg:#33270f;--warn:#ffc46b;--bad-bg:#3a1717;
--bad:#ff9b9b;--accent:#7fb0ff;--chip:#232931;--nav:#151a20ee}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
 padding-bottom:calc(72px + env(safe-area-inset-bottom))}
a{color:var(--accent)}
main{max-width:720px;margin:0 auto;padding:0 12px}
h2{font-size:1.05rem;margin:1.1rem 0 .4rem}h3{font-size:1rem;margin:.2rem 0 .4rem}
.sub{color:var(--muted);font-size:.85rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin:10px 0}
/* header */
.top{position:sticky;top:0;z-index:20;background:var(--bg);display:flex;align-items:center;gap:10px;
 padding:calc(10px + env(safe-area-inset-top)) 12px 8px;max-width:720px;margin:0 auto;border-bottom:1px solid var(--line)}
.top .t{flex:1;min-width:0}.top h1{font-size:1.15rem;margin:0;line-height:1.2}
.top p{margin:0;color:var(--muted);font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.icon{width:42px;height:42px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--ink);
 font-size:1.25rem;cursor:pointer;flex:none}
.icon[disabled]{opacity:.5}
.banner{display:block;margin:10px 0 0;padding:9px 12px;border-radius:12px;background:var(--warn-bg);color:var(--warn);
 text-decoration:none;font-size:.88rem}
.banner.bad{background:var(--bad-bg);color:var(--bad)}
/* bottom nav */
.bnav{position:fixed;left:0;right:0;bottom:0;z-index:25;display:flex;background:var(--nav);backdrop-filter:blur(10px);
 -webkit-backdrop-filter:blur(10px);border-top:1px solid var(--line);padding-bottom:env(safe-area-inset-bottom)}
.bnav a{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;padding:8px 0 9px;color:var(--muted);
 text-decoration:none;font-size:.72rem;font-weight:600}
.bnav a svg{width:22px;height:22px}
.bnav a[aria-current="page"]{color:var(--accent)}
.js .sec{display:none}.js .sec.on{display:block}
/* accumulator */
.acc-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.acc-head b{font-size:1.05rem}
.note{background:var(--warn-bg);color:var(--warn);border-radius:10px;padding:8px 11px;font-size:.85rem;margin:8px 0}
ol.legs{list-style:none;margin:6px 0 0;padding:0}
ol.legs li{display:flex;align-items:center;gap:10px;padding:9px 0;border-top:1px solid var(--line)}
ol.legs li:first-child{border-top:0}
.num{flex:none;width:24px;height:24px;border-radius:50%;background:var(--chip);color:var(--muted);font-size:.75rem;
 display:flex;align-items:center;justify-content:center;font-weight:700}
.fxn{flex:1;min-width:0;font-weight:600;line-height:1.25}
.fxn small{display:block;font-weight:400;color:var(--muted);font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pc{flex:none;font-variant-numeric:tabular-nums;font-weight:700;font-size:.92rem;padding:3px 8px;border-radius:8px;background:var(--chip)}
.pc.hi{background:var(--hi);color:var(--hi-ink)}
.tag{display:inline-block;background:var(--warn-bg);color:var(--warn);border-radius:6px;padding:0 6px;font-size:.72rem;margin-left:4px;font-weight:600}
.label{margin:12px 0 0;font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;font-weight:700}
/* fixture list */
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 8px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:7px 12px;
 font:600 .82rem/1 inherit;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
select.chip{appearance:none;-webkit-appearance:none;padding-right:28px;
 background-image:linear-gradient(45deg,transparent 50%,currentColor 50%),linear-gradient(135deg,currentColor 50%,transparent 50%);
 background-position:calc(100% - 15px) 52%,calc(100% - 10px) 52%;background-size:5px 5px;background-repeat:no-repeat}
.list{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
details.fx{border-top:1px solid var(--line)}details.fx:first-child{border-top:0}
details.fx>summary{list-style:none;display:flex;align-items:center;gap:10px;padding:10px 12px;cursor:pointer}
details.fx>summary::-webkit-details-marker{display:none}
details.fx[open]>summary{background:var(--chip)}
.fxd{display:grid;grid-template-columns:1fr 1fr;gap:8px 12px;padding:8px 12px 12px;font-size:.85rem}
.fxd div span{display:block;color:var(--muted);font-size:.72rem}
.fxd .fl{grid-column:1/-1}.fxd .fl .tag{margin:2px 4px 0 0}
.empty{padding:14px;color:var(--muted);margin:0}
.track{display:block;text-decoration:none;color:inherit;padding:10px 14px}
/* tables (Info / Results) */
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:.7rem;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
td.n,th.n{text-align:right;white-space:nowrap}
.scroll{overflow-x:auto}
details.card>summary{cursor:pointer;font-weight:600}
details.card ul{padding-left:1.1rem;margin:.5rem 0 0}
""" + update_button.CSS

ICONS = {
    "o15": "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'><circle cx='12' cy='12' r='9'/><path d='M12 3v4M12 17v4M3 12h4M17 12h4'/></svg>",
    "gibh": "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'><rect x='3' y='4' width='18' height='16' rx='2'/><path d='M12 4v16'/></svg>",
    "results": "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'><path d='M4 20V10M10 20V4M16 20v-7M22 20H2'/></svg>",
    "info": "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'><circle cx='12' cy='12' r='9'/><path d='M12 11v6M12 7.5v.5'/></svg>",
}
SECTIONS = (("o15", "Over 1.5"), ("gibh", "GIBH"), ("results", "Results"), ("info", "Info"))
MARKET_META = {"o15": ("Over 1.5 goals", "over_1_5_highlight", "Over 1.5", "Over 1.5 accumulator"),
               "gibh": ("Goal in both halves", "gibh_highlight", "Goal in both halves", "GIBH accumulator")}


def _key(report, r) -> str:
    """Stable id for a fixture, for per-phone features to come (e.g. a bet-slip checklist)."""
    return f"{report['date'].isoformat()}|{r['home']}|{r['away']}"


# ---------------------------------------------------------------- accumulator
def _acca(report, mk):
    a = report["accas"][mk]
    title = MARKET_META[mk][3]
    thr = report["config"]["thresholds"][MARKET_META[mk][1]] / 100
    odds = report["odds"]["enabled"] and mk == "o15"  # prices exist for Over 1.5 only

    def li(i, r, role, mark=""):
        m = r[mk]
        p = r.get("price")
        price = f" · {p['price']:.2f}" if odds and p else ""
        tag = f"<span class=tag>{escape(mark)}</span>" if mark else ""
        hi = m["combined_pct"] is not None and m["combined_pct"] >= thr
        return (f"<li data-key='{escape(_key(report, r))}' data-role={role}><span class=num>{i}</span>"
                f"<span class=fxn>{escape(_fixture(r))}{tag}<small>{escape(r['league_name'])} · "
                f"{escape(r['kickoff'] or '–')}{price}</small></span>"
                f"<b class='pc{' hi' if hi else ''}'>{pct(m['combined_pct'], 1)}</b></li>")
    size = f"{len(a['legs'])}-fold" if a["legs"] else "no fold"
    out = [f"<div class=card><div class=acc-head><b>{title}</b><span class=sub>{size}</span></div>"
           f"<p class=sub style='margin:.2rem 0 0'>{escape(a['message'])}</p>"]
    if a.get("note"):  # e.g. the bookmaker's boost rule: read before placing
        out.append(f"<div class=note>{escape(a['note'])}</div>")
    if a["legs"]:
        out.append(f"<ol class=legs data-role=legs>{''.join(li(i + 1, r, 'leg') for i, r in enumerate(a['legs']))}</ol>")
        if odds and all(r.get("price") for r in a["legs"]):
            tot = 1.0
            for r in a["legs"]:
                tot *= r["price"]["price"]
            out.append(f"<p class=sub>Combined price at best quoted prices: {tot:.2f}</p>")
    below = a.get("below_line") or []
    if a["reserves"] or below:
        label = "Reserves · use the top one first" if a["legs"] else "Qualifying fixtures"
        items = [li(i + 1, r, "reserve") for i, r in enumerate(a["reserves"])]
        items += [li(len(a["reserves"]) + i + 1, r, "below", f"below {a.get('min_pct', '')}%") for i, r in enumerate(below)]
        out.append(f"<p class=label>{label}</p><ol class=legs data-role=reserves>{''.join(items)}</ol>")
    out.append("</div>")
    return "".join(out)


# ---------------------------------------------------------------- fixture list
def _fixture_list(report, mk):
    cfg = report["config"]
    thr_key = MARKET_META[mk][1]
    thr = cfg["thresholds"][thr_key] / 100
    rows = report[mk]
    odds = report["odds"]["enabled"] and mk == "o15"
    leagues = sorted({r["league_name"] for r in rows})
    items = []
    for r in rows:
        m = r[mk]
        hi = m["combined_pct"] is not None and m["combined_pct"] >= thr
        flag = " · ⚑" if r["flags"] else ""
        p = r.get("price") if odds else None
        price = f"<div><span>Price</span>{p['price']:.2f} ({escape(p['book'])})</div>" if p else ""
        flags = ("<div class=fl><span>Flags</span>" + "".join(f"<span class=tag>{escape(f)}</span>" for f in r["flags"])
                 + "</div>") if r["flags"] else ""
        items.append(
            f"<details class=fx data-lg='{escape(r['league_name'])}' data-hi={int(hi)}>"
            f"<summary><span class=fxn>{escape(_fixture(r))}<small>{escape(_short(r['league_name']))} · "
            f"{escape(r['kickoff'] or '–')} · venue {pct(m['venue_pct'])}{flag}</small></span>"
            f"<b class='pc{' hi' if hi else ''}'>{pct(m['combined_pct'], 1)}</b></summary>"
            f"<div class=fxd><div><span>Home team</span>{pct(m['home_pct'])} · {m['home_gp']} games</div>"
            f"<div><span>Away team</span>{pct(m['away_pct'])} · {m['away_gp']} games</div>"
            f"<div><span>Venue-split</span>{pct(m['venue_pct'], 1)}</div>"
            f"<div><span>League</span>{escape(r['league_name'])}</div>{price}{flags}</div></details>")
    opts = "".join(f"<option value='{escape(lg)}'>{escape(_short(lg))}</option>" for lg in leagues)
    n_hi = sum(1 for r in rows if r[mk]["combined_pct"] is not None and r[mk]["combined_pct"] >= thr)
    return (f"<h2>All fixtures <span class=sub>· {len(rows)}</span></h2>"
            f"<p class=sub style='margin:0'>Covers {escape(scope.describe(cfg, mk))}. Tap a fixture for the detail.</p>"
            f"<div class=filters data-for={mk}><button class=chip aria-pressed=false data-f=hi>"
            f"{cfg['thresholds'][thr_key]}%+ only · {n_hi}</button>"
            f"<select class=chip data-f=lg aria-label='League'><option value=''>All leagues</option>{opts}</select></div>"
            f"<div class=list id=list-{mk}>{''.join(items) or '<p class=empty>No fixtures.</p>'}"
            f"<p class='empty nomatch' hidden>No fixtures match these filters.</p></div>")


# ---------------------------------------------------------------- track record
def _p0(x):
    return "–" if x is None else f"{x:.0f}%"


def _rates_table(stats_by, first_col):
    rows = []
    for name, s in stats_by.items():
        diff = None if s["hit_pct"] is None or s["league_avg_pct"] is None else s["hit_pct"] - s["league_avg_pct"]
        rows.append(f"<tr><td>{escape(name)}</td><td class=n>{s['hits']}/{s['n']}</td><td class=n>{_p0(s['hit_pct'])}</td>"
                    f"<td class=n>{_p0(s['league_avg_pct'])}</td><td class=n>{'–' if diff is None else f'{diff:+.0f}'}</td></tr>")
    return (f"<div class=scroll><table><thead><tr><th>{first_col}</th><th class=n>Landed</th><th class=n>Hit</th>"
            f"<th class=n>Lg avg</th><th class=n>+/-</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def _track(hit_rates, only: str | None = None):
    hr = hit_rates
    if not hr["graded"]:
        return ("<div class=card><p class=sub>No graded fixtures yet. After the weekend the results run records "
                "whether each market landed, and running hit rates appear here.</p></div>")
    out = []
    for label, d in hr["markets"].items():
        if only and label != only:
            continue
        o = d["overall"]
        out.append(f"<div class=card><h3>{label}</h3>")
        if d.get("acca"):
            a = d["acca"]
            out.append(f"<p>Accumulators landed in full: <b>{a['won']}/{a['weeks']}</b> · legs won {a['legs_won']}/{a['legs']}</p>")
        out.append(f"<p>Every fixture covered: <b>{o['hits']}/{o['n']}</b> ({_p0(o['hit_pct'])}) v league average "
                   f"{_p0(o['league_avg_pct'])}</p>")
        out.append("<p class=label>By combined-% band</p>" + _rates_table(d["by_band"], "Band"))
        out.append("<p class=label>By league</p>" + _rates_table(d["by_league"], "League") + "</div>")
    return "".join(out)


def _track_line(hit_rates, label):
    """One line under an accumulator pointing at the full record in Results."""
    d = hit_rates.get("markets", {}).get(label)
    if not d or not d["overall"]["n"]:
        return "<a class='card track' href='#results'><span class=sub>Track record: nothing graded yet · Results →</span></a>"
    o = d["overall"]
    return (f"<a class='card track' href='#results'><span class=sub>Track record: {o['hits']}/{o['n']} landed "
            f"({_p0(o['hit_pct'])}) v league average {_p0(o['league_avg_pct'])} · Results →</span></a>")


# ---------------------------------------------------------------- results
def results_section(df, hit_rates, cfg: dict | None = None) -> str:
    """Inner HTML of the Results section: last graded weekend + running record."""
    g = df[df["status"].isin(["graded", "void"])]
    title = "Results" if g.empty else f"Results · {escape(str(g['report_date'].max()))}"
    head = (f"<div class=row style='justify-content:space-between;margin-top:14px'><h2 style='margin:0'>{title}</h2>"
            + update_button.button(update_button.RESULTS_WF, "Check results now", cls="btn ghost") + "</div>")
    if g.empty:
        body = ("<div class=card><p class=sub>Nothing graded yet. The results run checks last weekend's games on "
                "Sunday at 7pm (and again Monday 1pm for late results), or tap <i>Check results now</i>.</p></div>")
    else:
        last = g["report_date"].max()
        wk = g[g["report_date"] == last].sort_values("o15_combined", ascending=False)

        def tick(mk, hit, r):  # "–" = that market didn't cover this fixture
            if cfg is not None and not scope.in_scope(cfg, mk, r.league_name, r.kickoff):
                return "–"
            return "✅" if str(hit).lower() in ("true", "1", "1.0") else "❌"
        rows = []
        for r in wk.itertuples():
            acca = []
            if isinstance(r.acca, str) and r.acca == "leg":
                acca.append("O1.5 leg")
            if isinstance(r.gibh_acca, str) and r.gibh_acca == "leg":
                acca.append("GIBH leg")
            sub = escape(_short(r.league_name)) + (" · " + ", ".join(acca) if acca else "")
            if r.status == "void":
                rows.append(f"<tr><td>{escape(r.home)} v {escape(r.away)}<div class=sub>{sub}</div></td>"
                            f"<td colspan=3 class=sub>postponed – void</td></tr>")
                continue
            rows.append(f"<tr><td>{escape(r.home)} v {escape(r.away)}<div class=sub>{sub}</div></td>"
                        f"<td class=n>{r.fthg}-{r.ftag}<div class=sub>HT {r.hthg}-{r.htag}</div></td>"
                        f"<td class=n>{tick('o15', r.o15_hit, r)}</td><td class=n>{tick('gibh', r.gibh_hit, r)}</td></tr>")
        body = ("<div class='card scroll'><table><thead><tr><th>Fixture</th><th class=n>Score</th><th class=n>O1.5</th>"
                f"<th class=n>GIBH</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>")
    return (head + body + "<h2>Track record</h2><p class=sub style='margin:0'>'Lg avg' is the season-to-date rate of "
            "the same leagues when each report ran: beating it means the selection adds something.</p>" + _track(hit_rates))


# ---------------------------------------------------------------- info
def _info(report):
    cfg = report["config"]
    gen = report["generated"].astimezone(UK).strftime("%a %d %b %Y, %H:%M UK")
    out = [f"<h2>This report</h2><div class=card><p style='margin-top:0'>For <b>{report['date'].strftime('%A %d %B %Y')}</b>, "
           f"generated {gen}.</p><p class=sub style='margin-bottom:0'>League matches only, this season. Every figure is "
           f"calculated from match results, not copied from stats sites. <a href='report.csv'>Download the CSV</a>.</p></div>"]
    if report["failed"]:
        out.append("<div class=card><h3>Leagues not loaded</h3><ul>" + "".join(
            f"<li><b>{escape(f['league'].name)}</b>: {escape(f['reason'])}</li>" for f in report["failed"]) + "</ul></div>")
    post = report["postponed"]
    if post:
        out.append(f"<details class=card><summary>Postponed / called off ({len(post)})</summary><ul>"
                   + "".join(f"<li>{escape(p['league'])}: {escape(p['home'])} v {escape(p['away'])} ({escape(p['status'])})</li>"
                             for p in post) + "</ul></details>")
    else:
        out.append("<div class=card><p class=sub style='margin:0'>No postponed games found on the fixture lists.</p></div>")
    odds = report["odds"]
    if odds["enabled"]:
        out.append(f"<div class=card><p class=sub>Prices (best UK price, Over 1.5) for: {escape(', '.join(odds['priced_leagues']) or 'none')}. "
                   f"None for: {escape(', '.join(odds['unpriced_leagues']) or 'none')}.</p></div>")
    out.append("<h2>Run for another date</h2><div class='card setup'><p class=sub style='margin-top:0'>The ↻ button at "
               "the top always runs next Saturday. Pick a date here for anything else.</p>"
               "<input type=date id=run-date aria-label='Match date'><div class=row>"
               + update_button.button(update_button.REPORT_WF, "Update report", date_from="run-date") + "</div></div>")
    out.append(update_button.setup_card())
    rows = []
    for res in report["loaded"]:
        lg, meta = res["league"], res["meta"]
        rows.append(f"<tr><td>{escape(_short(lg.name))}</td><td>{'⚠️' if res['problems'] else '✅'}</td>"
                    f"<td>{escape(meta['source'])}</td><td class=n>{res['results']}</td>"
                    f"<td class=n>{escape((meta.get('latest_result') or '–')[5:])}</td>"
                    f"<td class=n>{pct(res['rates']['o15'])}</td><td class=n>{pct(res['rates']['gibh'])}</td></tr>")
    for f in report["failed"]:
        rows.append(f"<tr><td>{escape(_short(f['league'].name))}</td><td>❌</td><td colspan=5 class=sub>not loaded</td></tr>")
    out.append("<h2>Data sources and checks</h2><div class='card scroll'><table><thead><tr><th>League</th><th></th>"
               "<th>Source</th><th class=n>Games</th><th class=n>Newest</th><th class=n>O1.5</th><th class=n>GIBH</th>"
               f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")
    for res in report["loaded"]:
        items = [f"<li>❗ {escape(p)}</li>" for p in res["problems"]] + [f"<li>{escape(n)}</li>" for n in res["notes"]]
        lm = res["meta"].get("last_modified")
        if lm:
            items.append(f"<li>source file last updated {escape(lm)}</li>")
        out.append(f"<details class=card><summary>{'⚠️ ' if res['problems'] else ''}{escape(res['league'].name)}</summary>"
                   f"<ul>{''.join(items)}</ul></details>")
    out.append(f"<h2>How the numbers work</h2><div class=card><p class=sub style='margin:0'>For each team: Over 1.5 % = "
               f"league games with 2+ goals ÷ games played. Goal-in-both-halves % = games with at least one goal in each "
               f"half ÷ games played (second-half goals = full-time total minus half-time total). Combined % = average of "
               f"the two teams. Venue-split = the home team's home games and the away team's away games. Teams with fewer "
               f"than {cfg['thresholds']['min_games']} games are flagged ⚑.</p></div>")
    return "".join(out)


# ---------------------------------------------------------------- page
APP_JS = """<script>
(function(){
  document.documentElement.classList.add('js');
  var secs=['o15','gibh','results','info'];
  function show(id,save){
    if(secs.indexOf(id)<0)id='o15';
    secs.forEach(function(s){document.getElementById(s).classList.toggle('on',s===id)});
    [].forEach.call(document.querySelectorAll('.bnav a'),function(a){
      a.setAttribute('aria-current',a.getAttribute('href')==='#'+id?'page':'false')});
    if(save){try{localStorage.setItem('goals-sec',id)}catch(e){}}
    window.scrollTo(0,0);
  }
  window.addEventListener('hashchange',function(){show(location.hash.slice(1),true)});
  var start=location.hash.slice(1);
  if(secs.indexOf(start)<0){try{start=localStorage.getItem('goals-sec')||'o15'}catch(e){start='o15'}
    history.replaceState(null,'','#'+start)}
  show(start,false);
  // fixture filters: "N%+ only" and league, remembered per market on this phone
  [].forEach.call(document.querySelectorAll('.filters'),function(f){
    var mk=f.getAttribute('data-for'), list=document.getElementById('list-'+mk),
        hi=f.querySelector('[data-f=hi]'), lg=f.querySelector('[data-f=lg]'), none=list.querySelector('.nomatch');
    function apply(save){
      var onlyHi=hi.getAttribute('aria-pressed')==='true', want=lg.value, shown=0;
      [].forEach.call(list.querySelectorAll('details.fx'),function(d){
        var ok=(!onlyHi||d.getAttribute('data-hi')==='1')&&(!want||d.getAttribute('data-lg')===want);
        d.hidden=!ok; if(ok)shown++});
      if(none)none.hidden=shown>0;
      if(save){try{localStorage.setItem('goals-f-'+mk,JSON.stringify({hi:onlyHi,lg:want}))}catch(e){}}
    }
    hi.addEventListener('click',function(){hi.setAttribute('aria-pressed',hi.getAttribute('aria-pressed')!=='true');apply(true)});
    lg.addEventListener('change',function(){apply(true)});
    try{var s=JSON.parse(localStorage.getItem('goals-f-'+mk)||'null');
      if(s){hi.setAttribute('aria-pressed',!!s.hi);if([].some.call(lg.options,function(o){return o.value===s.lg}))lg.value=s.lg}}catch(e){}
    apply(false);
  });
})();
</script>"""


def html(report) -> str:
    d = report["date"]
    hr = report["hit_rates"]
    loaded, failed = report["loaded"], report["failed"]
    n_fx = report.get("fixtures_total", len(report["o15"]))
    summary = (f"{n_fx} fixtures · {len(loaded)}/{len(loaded) + len(failed)} leagues"
               + (f" · {len(report['postponed'])} postponed" if report["postponed"] else ""))
    banners = []
    if failed:
        banners.append(f"<a class='banner bad' href='#info'>❌ Not loaded: {escape(', '.join(f['league'].name for f in failed))}"
                       f" · Info →</a>")
    flagged = [res for res in loaded if res["problems"]]
    if flagged:
        banners.append(f"<a class=banner href='#info'>⚠️ Data checks flagged {escape(', '.join(r['league'].name for r in flagged))}"
                       f" (kept out of both accumulators) · Info →</a>")
    top = (f"<header class=top><div class=t><h1>{d.strftime('%A %d %B')}</h1><p>{summary}</p></div>"
           + update_button.button(update_button.REPORT_WF, "↻", cls="icon", title="Update now (next Saturday)") + "</header>")
    secs = []
    for mk in ("o15", "gibh"):
        secs.append(f"<section class=sec id={mk}>{''.join(banners)}<h2>{MARKET_META[mk][0]}</h2>{_acca(report, mk)}"
                    f"{_track_line(hr, MARKET_META[mk][2])}{_fixture_list(report, mk)}</section>")
    secs.append(f"<section class=sec id=results>{RESULTS_START}{report['results_html']}{RESULTS_END}</section>")
    secs.append(f"<section class=sec id=info>{_info(report)}</section>")
    nav = "<nav class=bnav>" + "".join(
        f"<a href='#{k}' aria-current=false>{ICONS[k]}{label}</a>" for k, label in SECTIONS) + "</nav>"
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            f"<title>Goals {d.strftime('%d %b')}</title><style>{CSS}</style></head><body>{top}"
            f"<main>{''.join(secs)}</main>{nav}{update_button.script()}{APP_JS}</body></html>")


def replace_results(page: str, results_html: str) -> str:
    """Swap the Results section of an already-published page (used by the grading run)."""
    a, b = page.find(RESULTS_START), page.find(RESULTS_END)
    if a < 0 or b < 0:
        raise ValueError("page has no Results markers")
    return page[:a + len(RESULTS_START)] + results_html + page[b:]


# Old links to results.html land on the Results section instead.
REDIRECT = ("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content='0;url=index.html#results'>"
            "<title>Goals results</title><a href='index.html#results'>Results are now in the report: open them</a>")


# ---------------------------------------------------------------- CSV / summary
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
    lines.append(f"**Postponed:** {len(report['postponed'])}  ·  **Fixtures analysed:** "
                 f"{report.get('fixtures_total', len(report['o15']))}")
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
