"""Build dashboard.html from the paper ledger. Self-contained: no external scripts."""
import html
import json
from pathlib import Path

import ledger

OUT = Path(__file__).parent / "dashboard.html"


def max_drawdown(points):
    peak, worst = None, 0.0
    for p in points:
        peak = p if peak is None else max(peak, p)
        if peak:
            worst = min(worst, (p - peak) / peak)
    return worst


def build():
    state = ledger.load_state()
    decisions = ledger.read_jsonl(ledger.DECISIONS)
    equity = ledger.read_jsonl(ledger.EQUITY)
    series = [{"t": state.get("created", 0), "e": state["start_equity"]}] + \
             [{"t": r["ts"], "e": r["equity"]} for r in equity]
    eq_now = series[-1]["e"]
    dd = max_drawdown([p["e"] for p in series])
    refused = sum(1 for d in decisions if d["status"] == "refused")
    fills = sum(1 for d in decisions if d["status"] == "filled")

    def cell(v, fmt="{}"):
        return "" if v is None else html.escape(fmt.format(v))

    rows = "\n".join(
        f"<tr class='{d['status']}'><td>{cell(d['time'])}</td><td>{cell(d['action'])}</td>"
        f"<td><span class='tag {d['status']}'>{cell(d['status'])}</span></td><td>{cell(d['symbol'])}</td>"
        f"<td class='num'>{cell(d['price'], '{:,.2f}')}</td><td class='num'>{cell(d['size'], '{:.6f}')}</td>"
        f"<td class='num'>{cell(d['fee'], '{:.4f}')}</td>"
        f"<td>{cell(d['reason'])}{'<div class=refusal>Gate: ' + cell(d['refusal']) + '</div>' if d['refusal'] else ''}</td></tr>"
        for d in reversed(decisions)
    ) or "<tr><td colspan='8' class='empty'>No decisions yet.</td></tr>"

    page = TEMPLATE.format(
        equity=f"${eq_now:,.2f}", ret=f"{(eq_now / state['start_equity'] - 1):+.2%}",
        fees=f"${state['fees_paid']:,.4f}", dd=f"{dd:.2%}", refused=refused, fills=fills,
        n=len(decisions), rows=rows, series=json.dumps(series),
        position=html.escape(
            f"{state['position']['qty']:.6f} {state['position']['symbol']} @ ${state['position']['entry_price']:,.2f}"
            if state["position"] else "none"),
    )
    OUT.write_text(page)
    print(f"wrote {OUT}")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper Trading Ledger</title>
<style>
:root {{ --bg:#f5f5f3; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --line:#e3e2de; --series:#2a78d6;
  --critical:#d03b3b; --good:#0ca30c; --banner:#fff3cd; --banner-ink:#5c4400; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#121211; --surface:#1a1a19; --ink:#f0efec;
  --ink2:#c3c2b7; --line:#383835; --series:#3987e5; --critical:#e66767; --good:#0ca30c; --banner:#3a2f0b; --banner-ink:#f5d77a; }} }}
:root[data-theme="dark"] {{ --bg:#121211; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --line:#383835;
  --series:#3987e5; --critical:#e66767; --banner:#3a2f0b; --banner-ink:#f5d77a; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif }}
.banner {{ background:var(--banner); color:var(--banner-ink); font-weight:600; text-align:center; padding:10px 16px }}
main {{ max-width:1100px; margin:0 auto; padding:20px 16px 48px }}
h1 {{ font-size:20px; margin:0 0 16px }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:16px }}
.tile, .card {{ background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:12px 14px }}
.tile .k {{ color:var(--ink2); font-size:12px }} .tile .v {{ font-size:22px; font-weight:600; font-variant-numeric:tabular-nums }}
.card {{ margin-bottom:16px }} .card h2 {{ font-size:14px; margin:0 0 8px }}
#chart {{ position:relative }} svg {{ display:block; width:100%; height:260px }}
.axis text {{ fill:var(--ink2); font-size:11px }} .grid {{ stroke:var(--line) }}
#tip {{ position:absolute; pointer-events:none; background:var(--surface); border:1px solid var(--line); border-radius:6px;
  padding:4px 8px; font-size:12px; display:none; white-space:nowrap }}
.tablewrap {{ overflow-x:auto }}
table {{ width:100%; min-width:820px; border-collapse:collapse; font-size:13px }}
td:last-child {{ min-width:280px }}
th, td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top }}
th {{ color:var(--ink2); font-weight:500 }} .num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap }}
td:first-child {{ white-space:nowrap }}
.tag {{ font-size:11px; padding:1px 6px; border-radius:4px; border:1px solid var(--line) }}
.tag.refused {{ color:var(--critical); border-color:var(--critical) }}
.refusal {{ color:var(--critical); font-size:12px; margin-top:2px }} .empty {{ color:var(--ink2); text-align:center }}
.foot {{ color:var(--ink2); font-size:12px }}
</style></head><body>
<div class="banner">Paper money only. Not financial advice.</div>
<main>
<h1>Paper Trading Ledger</h1>
<div class="tiles">
  <div class="tile"><div class="k">Equity</div><div class="v">{equity}</div><div class="k">{ret} vs $100 start</div></div>
  <div class="tile"><div class="k">Fees paid</div><div class="v">{fees}</div></div>
  <div class="tile"><div class="k">Biggest drop (peak to trough)</div><div class="v">{dd}</div></div>
  <div class="tile"><div class="k">Orders refused by gate</div><div class="v">{refused}</div></div>
  <div class="tile"><div class="k">Fills</div><div class="v">{fills}</div><div class="k">of {n} decisions</div></div>
</div>
<div class="card"><h2>Equity over time (USD)</h2><div id="chart"><svg id="svg"></svg><div id="tip"></div></div></div>
<div class="card"><h2>Every decision</h2><p class="foot">Open position: {position}</p><div class="tablewrap"><table>
<thead><tr><th>Time (UTC)</th><th>Action</th><th>Status</th><th>Symbol</th><th class="num">Price</th><th class="num">Size</th><th class="num">Fee</th><th>Reason</th></tr></thead>
<tbody>{rows}</tbody></table></div></div>
<p class="foot">Data: Kraken public market data. Fills are simulated at the latest public trade price with a 0.4% fee. No real account is involved.</p>
</main>
<script>
const S = {series};
const svg = document.getElementById('svg'), tip = document.getElementById('tip'), NS = 'http://www.w3.org/2000/svg';
function el(n, a) {{ const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); return e; }}
function draw() {{
  svg.innerHTML = '';
  const W = svg.clientWidth, H = 260, m = {{l:52, r:12, t:10, b:26}};
  const t0 = S[0].t, t1 = Math.max(S[S.length-1].t, t0 + 1);
  let lo = Math.min(...S.map(p => p.e)), hi = Math.max(...S.map(p => p.e));
  const pad = Math.max((hi - lo) * 0.15, 1); lo -= pad; hi += pad;
  const x = t => m.l + (t - t0) / (t1 - t0) * (W - m.l - m.r), y = e => m.t + (hi - e) / (hi - lo) * (H - m.t - m.b);
  const g = el('g', {{class:'axis'}}); svg.appendChild(g);
  for (let i = 0; i <= 4; i++) {{ const v = lo + (hi - lo) * i / 4;
    g.appendChild(el('line', {{x1:m.l, x2:W-m.r, y1:y(v), y2:y(v), class:'grid'}}));
    const tx = el('text', {{x:m.l-6, y:y(v)+4, 'text-anchor':'end'}}); tx.textContent = '$' + v.toFixed(2); g.appendChild(tx); }}
  [t0, t1].forEach((t, i) => {{ const tx = el('text', {{x:x(t), y:H-6, 'text-anchor': i ? 'end' : 'start'}});
    tx.textContent = new Date(t*1000).toISOString().slice(0,16).replace('T',' '); g.appendChild(tx); }});
  svg.appendChild(el('path', {{d: S.map((p,i) => (i?'L':'M') + x(p.t) + ',' + y(p.e)).join(''), fill:'none',
    stroke:'var(--series)', 'stroke-width':2, 'stroke-linejoin':'round'}}));
  const last = S[S.length-1];
  svg.appendChild(el('circle', {{cx:x(last.t), cy:y(last.e), r:4, fill:'var(--series)', stroke:'var(--surface)', 'stroke-width':2}}));
  const cross = el('line', {{y1:m.t, y2:H-m.b, stroke:'var(--ink2)', 'stroke-dasharray':'3 3', visibility:'hidden'}}); svg.appendChild(cross);
  const hit = el('rect', {{x:m.l, y:0, width:W-m.l-m.r, height:H, fill:'transparent'}}); svg.appendChild(hit);
  hit.addEventListener('mousemove', ev => {{
    const r = svg.getBoundingClientRect(), mx = ev.clientX - r.left;
    let best = S[0]; for (const p of S) if (Math.abs(x(p.t) - mx) < Math.abs(x(best.t) - mx)) best = p;
    cross.setAttribute('x1', x(best.t)); cross.setAttribute('x2', x(best.t)); cross.setAttribute('visibility', 'visible');
    tip.style.display = 'block'; tip.textContent = new Date(best.t*1000).toISOString().slice(0,16).replace('T',' ') + '  $' + best.e.toFixed(2);
    tip.style.left = Math.min(x(best.t) + 8, W - tip.offsetWidth) + 'px'; tip.style.top = (y(best.e) - 30) + 'px'; }});
  hit.addEventListener('mouseleave', () => {{ tip.style.display = 'none'; cross.setAttribute('visibility', 'hidden'); }});
}}
draw(); addEventListener('resize', draw);
</script></body></html>
"""

if __name__ == "__main__":
    build()
