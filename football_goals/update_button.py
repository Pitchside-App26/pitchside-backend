"""The "Update now" panel on the report and results pages.

The pages are static and public, so they can't carry a GitHub key. Instead,
the owner pastes a fine-grained token (Actions: read & write on this repo
only) into the page once; it is kept in that phone's browser storage and sent
only to api.github.com. With it, one tap starts the workflow, the panel
follows the run, and the page reloads when the new version is published.
Without it, the panel links straight to the workflow's Run workflow screen."""
from __future__ import annotations

import json
import os
from html import escape

REPO = os.environ.get("GITHUB_REPOSITORY", "Pitchside-App26/pitchside-backend")
BRANCH = "main"
TOKEN_URL = "https://github.com/settings/personal-access-tokens/new"

CSS = """
.upd{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:10px 0}
.upd button{border:0;border-radius:10px;padding:10px 14px;font:600 .95rem/1 inherit;cursor:pointer;
 background:var(--accent);color:#fff}
.upd button.ghost{background:var(--chip);color:var(--ink)}
.upd input[type=date]{border:1px solid var(--line);border-radius:10px;padding:8px;background:var(--card);color:var(--ink);font:inherit}
.upd .st{flex-basis:100%;font-size:.85rem;color:var(--muted)}
.upd-setup{display:none}.upd-setup.open{display:block}
.upd-setup input[type=password]{width:100%;border:1px solid var(--line);border-radius:10px;padding:10px;
 background:var(--card);color:var(--ink);font:inherit;margin:6px 0}
.upd-setup ol{padding-left:1.2rem;margin:.4rem 0}.upd-setup li{margin:.25rem 0}
"""


def panel(workflow: str, label: str, with_date: bool) -> str:
    """HTML + script for one workflow's button. `workflow` is the file name."""
    runs_page = f"https://github.com/{REPO}/actions/workflows/{workflow}"
    date_input = "<input type=date id=upd-date aria-label='Match date (blank = next Saturday)'>" if with_date else ""
    cfg = json.dumps({"repo": REPO, "wf": workflow, "ref": BRANCH, "date": with_date})
    return f"""
<div class=card>
 <div class=upd>
  <button id=upd-go>↻ {escape(label)}</button>{date_input}
  <button class=ghost id=upd-setup-btn>⚙︎</button>
  <div class=st id=upd-st>Takes about a minute. The page reloads itself when it's done.</div>
 </div>
 <div class=upd-setup id=upd-setup>
  <p><b>One-time setup for one-tap updates</b> (on each phone or browser you use):</p>
  <ol>
   <li>Open <a href="{TOKEN_URL}" target=_blank rel=noopener>GitHub → new fine-grained token</a>.</li>
   <li>Name it <i>Goals report button</i>. Expiration: 1 year.</li>
   <li>Repository access: <b>Only select repositories</b> → <b>{escape(REPO.split('/')[1])}</b>.</li>
   <li>Repository permissions → <b>Actions</b> → <b>Read and write</b>. Leave everything else as it is.</li>
   <li>Tap <b>Generate token</b>, copy it, paste it below and tap Save.</li>
  </ol>
  <input type=password id=upd-token placeholder="Paste token (starts github_pat_)" autocomplete=off>
  <div class=upd><button id=upd-save>Save</button><button class=ghost id=upd-forget>Forget saved token</button></div>
  <p class=sub>The token stays in this browser only and is sent only to GitHub. It can start and check
  runs of this repo's workflows, nothing else. No setup? <a href="{runs_page}" target=_blank rel=noopener>Open the
  Run workflow screen on GitHub</a> instead.</p>
 </div>
</div>
<script>
(function(){{
  var C={cfg}, KEY='gh-actions-token', api='https://api.github.com/repos/'+C.repo+'/actions/workflows/'+C.wf;
  var $=function(id){{return document.getElementById(id)}}, st=$('upd-st'), setup=$('upd-setup');
  function tok(){{try{{return localStorage.getItem(KEY)}}catch(e){{return null}}}}
  function say(t){{st.textContent=t}}
  function hdr(){{return {{'Authorization':'Bearer '+tok(),'Accept':'application/vnd.github+json',
                         'X-GitHub-Api-Version':'2022-11-28'}}}}
  function why(r){{return r.status===401?'GitHub rejected the token (expired or mistyped). Tap ⚙︎ to paste a new one.'
    :(r.status===403||r.status===404)?'The token lacks permission. It needs Actions: Read and write on this repo. Tap ⚙︎.'
    :'GitHub said '+r.status+'. Try again in a minute.'}}
  $('upd-setup-btn').onclick=function(){{setup.classList.toggle('open')}};
  $('upd-save').onclick=function(){{var v=$('upd-token').value.trim(); if(!v)return;
    try{{localStorage.setItem(KEY,v)}}catch(e){{say('This browser blocks saving. Use the GitHub link instead.');return}}
    $('upd-token').value=''; setup.classList.remove('open'); say('Saved. Tap the button to update.')}};
  $('upd-forget').onclick=function(){{try{{localStorage.removeItem(KEY)}}catch(e){{}} say('Token removed from this browser.')}};
  // Find "our" run by id, not by clock: phone clocks can be off by more than the wait.
  function newest(){{
    return fetch(api+'/runs?event=workflow_dispatch&per_page=1',{{headers:hdr()}}).then(function(r){{
      if(!r.ok)throw r; return r.json()}}).then(function(j){{return (j.workflow_runs||[])[0]||null}});
  }}
  function follow(prev,t0,tries){{
    newest().then(function(run){{
      if(!run||run.id===prev){{run=null;say('Queued, waiting for GitHub to start it…')}}
      else if(run.status!=='completed'){{say('Running ('+run.status.replace('_',' ')+')… '+
        Math.round((Date.now()-t0)/1000)+'s')}}
      else if(run.conclusion==='success'){{say('Done. Reloading…');
        setTimeout(function(){{location.replace(location.pathname+'?t='+Date.now()+location.hash)}},4000);return}}
      else{{st.innerHTML='The run finished with “'+run.conclusion+'”. <a href="'+run.html_url+'" target=_blank>See what happened</a>.';
        $('upd-go').disabled=false;return}}
      if(tries>90){{say('Still going after 15 minutes. Check GitHub.');$('upd-go').disabled=false;return}}
      setTimeout(function(){{follow(prev,t0,tries+1)}},10000);
    }}).catch(function(r){{say(r&&r.status?why(r):'Lost connection. Pull to refresh in a minute.');$('upd-go').disabled=false}});
  }}
  $('upd-go').onclick=function(){{
    if(!tok()){{setup.classList.add('open');say('One-time setup needed first (below), or use the GitHub link.');return}}
    var body={{ref:C.ref}};
    if(C.date){{var d=$('upd-date').value; body.inputs={{date:d||''}}}}
    var btn=this, t0=Date.now(), prev=null; btn.disabled=true; say('Starting…');
    newest().then(function(run){{prev=run?run.id:null;
      return fetch(api+'/dispatches',{{method:'POST',headers:hdr(),body:JSON.stringify(body)}})}}).then(function(r){{
      if(r.status===204){{say('Started. Following the run…');setTimeout(function(){{follow(prev,t0,0)}},5000)}}
      else throw r;
    }}).catch(function(r){{btn.disabled=false;
      if(r&&r.status){{say(why(r));if(r.status!==422&&r.status<500)setup.classList.add('open')}}
      else say('No connection to GitHub.')}});
  }};
}})();
</script>"""
