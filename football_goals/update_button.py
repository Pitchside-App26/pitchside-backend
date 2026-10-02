"""Buttons that start a GitHub Actions run from the page (↻ Update now,
Check results now), plus the one-time token setup that powers them.

The page is static and public, so it can't carry a GitHub key. Instead, the
owner pastes a fine-grained token (Actions: read & write on this repo only)
into the Info section once; it is kept in that browser's storage and sent
only to api.github.com. A tap then starts the workflow, a toast follows the
run, and the page reloads when the new version is published. Without a
token, the setup card links straight to the workflow's Run workflow screen.
"""
from __future__ import annotations

import json
import os
from html import escape

REPO = os.environ.get("GITHUB_REPOSITORY", "Pitchside-App26/pitchside-backend")
BRANCH = "main"
TOKEN_URL = "https://github.com/settings/personal-access-tokens/new"
REPORT_WF = "football-goals-report.yml"
RESULTS_WF = "football-goals-results.yml"

CSS = """
.toast{position:fixed;left:12px;right:12px;bottom:calc(76px + env(safe-area-inset-bottom));z-index:30;
 background:var(--ink);color:var(--bg);border-radius:12px;padding:10px 14px;font-size:.9rem;box-shadow:0 6px 24px #0004}
.toast[hidden]{display:none}.toast a{color:inherit}
.setup input[type=password],.setup input[type=date]{width:100%;border:1px solid var(--line);border-radius:10px;padding:10px;
 background:var(--card);color:var(--ink);font:inherit;margin:6px 0}
.setup ol{padding-left:1.2rem;margin:.4rem 0}.setup li{margin:.25rem 0}
.btn{border:0;border-radius:10px;padding:10px 14px;font:600 .95rem/1 inherit;cursor:pointer;background:var(--accent);color:#fff}
.btn.ghost{background:var(--chip);color:var(--ink)}.btn[disabled]{opacity:.5}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
"""


def button(workflow: str, label: str, cls: str = "btn", date_from: str = "", title: str = "") -> str:
    """A button that starts `workflow`. `date_from` = id of a date input to send as the date."""
    extra = f" data-date-from={date_from}" if date_from else ""
    return (f"<button class='{cls}' data-wf='{escape(workflow)}'{extra} title='{escape(title or label)}' "
            f"aria-label='{escape(title or label)}'>{label}</button>")


def setup_card() -> str:
    runs_page = f"https://github.com/{REPO}/actions/workflows/{REPORT_WF}"
    return f"""
<div class='card setup' id=setup>
 <h3>One-tap updates <span class=sub id=setup-state></span></h3>
 <p class=sub>The ↻ button and <i>Check results now</i> need a GitHub token, saved once on each phone or browser.</p>
 <ol>
  <li>Open <a href="{TOKEN_URL}" target=_blank rel=noopener>GitHub → new fine-grained token</a>.</li>
  <li>Name it <i>Goals report button</i>. Expiration: 1 year.</li>
  <li>Repository access: <b>Only select repositories</b> → <b>{escape(REPO.split('/')[1])}</b>.</li>
  <li>Repository permissions → <b>Actions</b> → <b>Read and write</b>. Leave everything else as it is.</li>
  <li>Tap <b>Generate token</b>, copy it, paste it below and tap Save.</li>
 </ol>
 <input type=password id=tok-in placeholder="Paste token (starts github_pat_)" autocomplete=off>
 <div class=row><button class=btn id=tok-save>Save</button><button class='btn ghost' id=tok-forget>Forget saved token</button></div>
 <p class=sub>The token stays in this browser only and is sent only to GitHub. It can only manage this repo's
 workflow runs (start, check, cancel): it can't change code or read your secrets. No token? Use the
 <a href="{runs_page}" target=_blank rel=noopener>Run workflow screen on GitHub</a> instead.</p>
</div>"""


SCRIPT_TEMPLATE = """<script>
(function(){
  var C=__CFG__, KEY='gh-actions-token', toast=document.getElementById('toast');
  function $(id){return document.getElementById(id)}
  function tok(){try{return localStorage.getItem(KEY)}catch(e){return null}}
  function say(t,html){if(!toast)return;toast.hidden=false;if(html)toast.innerHTML=t;else toast.textContent=t;}
  function done(ms){setTimeout(function(){toast.hidden=true},ms||6000)}
  function state(){var s=$('setup-state');if(s)s.textContent=tok()?'· set up on this device ✓':'· not set up on this device'}
  function hdr(){return {'Authorization':'Bearer '+tok(),'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}}
  function api(wf){return 'https://api.github.com/repos/'+C.repo+'/actions/workflows/'+wf}
  function why(r){return r.status===401?'GitHub rejected the token (expired or mistyped). Paste a new one in Info.'
    :(r.status===403||r.status===404)?'The token lacks permission: it needs Actions: Read and write on this repo.'
    :'GitHub said '+r.status+'. Try again in a minute.'}
  function toSetup(){location.hash='#info';setTimeout(function(){var s=$('setup');if(s)s.scrollIntoView()},50)}
  state();
  if($('tok-save'))$('tok-save').onclick=function(){var v=$('tok-in').value.trim();if(!v)return;
    try{localStorage.setItem(KEY,v)}catch(e){say('This browser blocks saving; use the GitHub link instead.');done();return}
    $('tok-in').value='';state();say('Saved. Tap ↻ to update.');done(3000)};
  if($('tok-forget'))$('tok-forget').onclick=function(){try{localStorage.removeItem(KEY)}catch(e){}state();say('Token removed from this browser.');done(3000)};
  // "Our" run is found by id, not clock: phone clocks can be off by more than the wait.
  function newest(wf){return fetch(api(wf)+'/runs?event=workflow_dispatch&per_page=1',{headers:hdr()})
    .then(function(r){if(!r.ok)throw r;return r.json()}).then(function(j){return (j.workflow_runs||[])[0]||null})}
  function follow(wf,prev,t0,n,btn){
    newest(wf).then(function(run){
      if(!run||run.id===prev)say('Queued, waiting for GitHub to start it…');
      else if(run.status!=='completed')say('Running… '+Math.round((Date.now()-t0)/1000)+'s (about a minute)');
      else if(run.conclusion==='success'){say('Done. Reloading…');
        setTimeout(function(){location.replace(location.pathname+'?t='+Date.now()+location.hash)},3000);return}
      else{say('The run finished with “'+run.conclusion+'”. <a href="'+run.html_url+'" target=_blank>See what happened</a>.',true);btn.disabled=false;return}
      if(n>90){say('Still going after 15 minutes. Check GitHub.');btn.disabled=false;return}
      setTimeout(function(){follow(wf,prev,t0,n+1,btn)},10000);
    }).catch(function(r){say(r&&r.status?why(r):'Lost connection. Refresh in a minute.');btn.disabled=false});
  }
  [].forEach.call(document.querySelectorAll('[data-wf]'),function(btn){
    btn.addEventListener('click',function(){
      var wf=btn.getAttribute('data-wf');
      if(!tok()){say('One-time setup needed first: see “One-tap updates” in Info.');done();toSetup();return}
      var body={ref:C.ref}, df=btn.getAttribute('data-date-from');
      if(wf===C.report){var d=df&&$(df)?$(df).value:'';body.inputs={date:d||''}}
      var t0=Date.now(), prev=null; btn.disabled=true; say('Starting…');
      newest(wf).then(function(run){prev=run?run.id:null;
        return fetch(api(wf)+'/dispatches',{method:'POST',headers:hdr(),body:JSON.stringify(body)})})
      .then(function(r){if(r.status===204){say('Started. Following the run…');setTimeout(function(){follow(wf,prev,t0,0,btn)},5000)}else throw r})
      .catch(function(r){btn.disabled=false;
        if(r&&r.status){say(why(r));done(9000);if(r.status!==422&&r.status<500)toSetup()}else{say('No connection to GitHub.');done()}});
    });
  });
})();
</script>"""


def script() -> str:
    cfg = json.dumps({"repo": REPO, "ref": BRANCH, "report": REPORT_WF})
    return "<div class=toast id=toast role=status hidden></div>" + SCRIPT_TEMPLATE.replace("__CFG__", cfg)
