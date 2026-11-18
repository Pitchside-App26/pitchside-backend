"""The bet slip on each accumulator card (all in the browser, nothing sent anywhere):

- tap a leg's circle to tick it once it's on the bookmaker's slip;
- ✕ "can't get this" crosses a leg out and brings in the next reserve;
- + adds any reserve as an extra leg (e.g. playing an 8-fold from a 6-fold);
- Log bet saves bookmaker, stake and the return shown on the slip, with the
  exact legs, under "My bets" in Results;
- Info has Back up / Restore, since everything lives in this phone's browser.

The repo and the site are public, so logged bets are deliberately kept on
the phone only (localStorage): stakes and returns never reach GitHub.
Settling bets (won/lost, profit) comes later, from published results.
"""
from __future__ import annotations

import json

CSS = """
.acca .tk{flex:none;width:26px;height:26px;border-radius:50%;border:2px solid var(--muted);background:none;color:transparent;
 font:700 .8rem/1 inherit;cursor:pointer;padding:0;display:none}
.js-slip .acca .tk{display:inline-flex;align-items:center;justify-content:center}
.js-slip .acca li .num{display:none}
.acca li.on .tk{background:var(--hi-ink);border-color:var(--hi-ink);color:var(--card)}
.acca .act{flex:none;width:30px;height:30px;border-radius:8px;border:1px solid var(--line);background:var(--card);
 color:var(--muted);font:700 1rem/1 inherit;cursor:pointer;padding:0;display:none}
.js-slip .acca .act{display:inline-flex;align-items:center;justify-content:center}
.acca li.out{opacity:.45}.acca li.out .fxn{text-decoration:line-through}
.acca li.out .tk{visibility:hidden}
.acca li[data-role=reserve] .tk,.acca li[data-role=below] .tk{visibility:hidden}
.acca li.in .tk{visibility:visible}
.acca li.in{background:var(--hi);margin:0 -14px;padding-left:14px;padding-right:14px}
.acca li.in .act{color:var(--bad)}
.slip-bar{display:none;margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}
.js-slip .slip-bar{display:block}
.slip-bar .count{font-weight:700}
.logf{display:none;margin-top:8px}.logf.open{display:block}
.logf label{display:block;font-size:.78rem;color:var(--muted);margin-top:8px}
.logf input,.logf select{width:100%;border:1px solid var(--line);border-radius:10px;padding:10px;background:var(--card);
 color:var(--ink);font:inherit;margin-top:3px}
.logf .two{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.prow{display:flex;gap:8px;align-items:center;margin-top:6px}.prow span{flex:1;font-size:.85rem}
.prow input,.logf .prow input{width:86px;flex:none;border:1px solid var(--line);border-radius:10px;padding:8px;
 background:var(--card);color:var(--ink);font:inherit}.prow input.bad{border-color:#d33}
.pcheck td,.pcheck th{padding:4px 6px;font-size:.85rem}
.bet .legs-list{margin:.4rem 0 0;padding-left:1.1rem;font-size:.85rem}
.bet .meta{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
"""

MY_BETS = ("<div id=my-bets><h2 style='margin-top:14px'>My bets</h2>"
           "<p class=sub style='margin:0 0 8px'><a href='../tracker.html'>Follow them live on My bets →</a></p>"
           "<div id=my-bets-list>"
           "<div class=card><p class=sub style='margin:0'>Bets you log from an accumulator card appear here. "
           "They're kept on this phone only.</p></div></div><div id=price-check></div></div>")

BACKUP_CARD = """
<h2>My bets backup</h2>
<div class='card setup'>
 <p class=sub style='margin-top:0'>Logged bets are kept in this browser only (the site is public, so they're
 never uploaded). On an iPhone the home-screen icon, Safari and in-app browsers each have their own copy, so
 always open the page the same way. Clearing browser data deletes them, so back up now and then. A backup file also moves them to
 another phone or browser.</p>
 <div class=row><button class=btn id=bets-backup>Back up</button><button class='btn ghost' id=bets-restore-btn>Restore</button>
 <input type=file id=bets-restore accept='application/json,.json' hidden></div>
 <p class=sub id=bets-backup-msg style='margin-bottom:0'></p>
</div>"""

SCRIPT_TEMPLATE = """<script>
(function(){
  var CFG=__CFG__, BETS='goals-bets-v1';
  function load(k,d){try{var v=localStorage.getItem(k);return v?JSON.parse(v):d}catch(e){return d}}
  function save(k,v){try{localStorage.setItem(k,JSON.stringify(v));return true}catch(e){return false}}
  function el(tag,cls,text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
  function money(x){return '£'+Number(x).toFixed(2)}
  function bets(){return load(BETS,[])}
  // A price as typed (1/7, 2/13, evens, 1.14) -> decimal odds; null = left blank; NaN = can't read it.
  function dec(t){t=String(t||'').replace(/\s/g,'');if(!t)return null;
    var m=t.match(/^(\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?)$/);
    if(m)return +m[2]>0?Math.round((1+m[1]/m[2])*1000)/1000:NaN;
    if(/^evens?$/i.test(t))return 2;
    return /^\d+(\.\d+)?$/.test(t)&&+t>1&&+t<1000?Math.round(+t*1000)/1000:NaN}
  // One price box per leg; returns a reader giving [{odds,price}|null] per leg, or false if one can't be read.
  function priceRows(legs,box){
    var ins=legs.map(function(l){var r=el('div','prow');r.appendChild(el('span',null,l.fx));
      var i=el('input');i.placeholder='e.g. 1/7';i.value=l.odds||'';i.autocapitalize='off';i.setAttribute('autocomplete','off');
      i.dataset.k=l.key;r.appendChild(i);box.appendChild(r);return i});
    return function(){var out=[],ok=true;ins.forEach(function(i){var v=i.value.trim(),p=dec(v),bad=p!==null&&isNaN(p);
      i.classList.toggle('bad',bad);if(bad)ok=false;out.push(p===null||bad?null:{odds:v,price:p})});return ok?out:false}}
  if(!save('goals-slip-probe',1)){return}            // storage blocked: leave the plain list as it is
  try{if(navigator.storage&&navigator.storage.persist)navigator.storage.persist()}catch(e){}  // ask not to be evicted
  document.documentElement.classList.add('js-slip');

  [].forEach.call(document.querySelectorAll('.acca[data-mk]'),function(card){
    var mk=card.dataset.mk, date=card.dataset.date, sk='goals-slip-'+date+'-'+mk;
    var st=load(sk,{ticked:[],out:[],added:[]});
    var legs=[].slice.call(card.querySelectorAll('li[data-role=leg]'));
    var res=[].slice.call(card.querySelectorAll('li[data-role=reserve],li[data-role=below]'));
    if(!legs.length&&!res.length)return;
    function has(a,k){return a.indexOf(k)>=0}
    function drop(a,k){var i=a.indexOf(k);if(i>=0)a.splice(i,1)}
    function keep(){save(sk,st);paint()}
    function slip(){return legs.filter(function(li){return !has(st.out,li.dataset.key)})
      .concat(res.filter(function(li){return has(st.added,li.dataset.key)}))}
    legs.concat(res).forEach(function(li){
      var isLeg=li.dataset.role==='leg', k=li.dataset.key;
      var tk=el('button','tk','✓');tk.setAttribute('aria-label','Added to my slip');li.insertBefore(tk,li.firstChild);
      tk.onclick=function(){if(has(st.ticked,k))drop(st.ticked,k);else st.ticked.push(k);keep()};
      var act=el('button','act');li.appendChild(act);
      act.onclick=function(){
        if(isLeg){
          if(has(st.out,k)){drop(st.out,k)}            // put it back
          else{st.out.push(k);drop(st.ticked,k);         // can't get it: bring in the next reserve
            var next=res.filter(function(r){return !has(st.added,r.dataset.key)})[0];
            if(next)st.added.push(next.dataset.key)}
        }else{if(has(st.added,k)){drop(st.added,k);drop(st.ticked,k)}else st.added.push(k)}
        keep()};
    });
    var bar=el('div','slip-bar'), line=el('div','row'), count=el('span','count'), sub=el('span','sub');
    var logb=el('button','btn','Log bet'), reset=el('button','btn ghost','Reset');
    line.appendChild(count);line.appendChild(sub);bar.appendChild(line);
    var btns=el('div','row');btns.appendChild(logb);btns.appendChild(reset);bar.appendChild(btns);
    var form=el('div','logf');bar.appendChild(form);card.appendChild(bar);
    reset.onclick=function(){if(confirm('Clear the ticks and swaps on this slip?')){st={ticked:[],out:[],added:[]};keep()}};
    logb.onclick=function(){form.classList.toggle('open');if(form.classList.contains('open'))buildForm()};
    function paint(){
      legs.forEach(function(li){var k=li.dataset.key, o=has(st.out,k);li.classList.toggle('out',o);
        li.classList.toggle('on',!o&&has(st.ticked,k));var a=li.querySelector('.act');
        a.textContent=o?'↺':'✕';a.setAttribute('aria-label',o?'Put this leg back':"Can't get this leg: swap in the next reserve")});
      res.forEach(function(li){var k=li.dataset.key, i=has(st.added,k);li.classList.toggle('in',i);
        li.classList.toggle('on',i&&has(st.ticked,k));var a=li.querySelector('.act');
        a.textContent=i?'−':'+';a.setAttribute('aria-label',i?'Take this leg off my slip':'Add to my slip')});
      var s=slip(), t=s.filter(function(li){return has(st.ticked,li.dataset.key)}).length;
      var extra=st.added.length-st.out.length, swaps=Math.min(st.out.length,st.added.length);
      count.textContent=s.length+'-fold · '+t+' of '+s.length+' ticked';
      sub.textContent=(swaps?swaps+' swapped':'')+(swaps&&extra>0?' · ':'')+(extra>0?'+'+extra+' extra':'')+(extra<0?(swaps?' · ':'')+(-extra)+' fewer':'');
      var logged=bets().filter(function(b){return b.date===date&&b.mk===mk});
      logb.textContent=logged.length?'Log another bet':'Log bet';
    }
    function buildForm(){
      form.textContent='';
      var s=slip(); if(!s.length){form.appendChild(el('p','sub','No legs on the slip.'));return}
      var last=load('goals-last-bookie-'+mk,null)||CFG.defaults[mk]||CFG.bookies[0];
      var lb=el('label',null,'Bookmaker'), sel=el('select');
      CFG.bookies.concat(['Other']).forEach(function(b){var o=el('option',null,b);o.value=b;if(b===last)o.selected=true;sel.appendChild(o)});
      var other=el('input');other.placeholder='Bookmaker name';other.style.display='none';
      if(CFG.bookies.indexOf(last)<0&&last!=='Other'){sel.value='Other';other.value=last;other.style.display=''}
      sel.onchange=function(){other.style.display=sel.value==='Other'?'':'none'};
      lb.appendChild(sel);lb.appendChild(other);form.appendChild(lb);
      var two=el('div','two'), ls=el('label',null,'Stake (£)'), lr=el('label',null,'Return on the slip (£)');
      var stake=el('input'), ret=el('input');[stake,ret].forEach(function(i){i.type='number';i.step='0.01';i.min='0';i.inputMode='decimal'});
      ret.placeholder='incl. any boost';ls.appendChild(stake);lr.appendChild(ret);two.appendChild(ls);two.appendChild(lr);form.appendChild(two);
      // Legs: this card's slip, plus any fixture from this tab's full list (your own picks).
      var ex=[], on={}, typed={}, read=null;
      s.forEach(function(li){on[li.dataset.key]=1});
      function cur(){return s.map(function(li){return {key:li.dataset.key,fx:li.dataset.fx,lg:li.dataset.lg,pct:li.dataset.pct,
        role:li.dataset.role}}).concat(ex)}
      var pool=[].slice.call((card.closest('section')||document).querySelectorAll('details.fx[data-key]'));
      var addSel=el('select');
      function fillAdd(){addSel.textContent='';var o0=el('option',null,'+ Add a fixture not on this card');o0.value='';
        addSel.appendChild(o0);pool.forEach(function(d){if(on[d.dataset.key])return;
          var o=el('option',null,d.dataset.fx+' · '+d.dataset.pct);o.value=d.dataset.key;addSel.appendChild(o)})}
      addSel.onchange=function(){var d=pool.filter(function(x){return x.dataset.key===addSel.value})[0];if(!d)return;
        ex.push({key:d.dataset.key,fx:d.dataset.fx,lg:d.dataset.lg,pct:d.dataset.pct,role:'extra'});on[d.dataset.key]=1;
        fillAdd();draw()};
      var pl=el('label',null,'Price of each leg (optional: 1/7, 2/13 or 1.14). It shows over time whether short prices land more often than our ratings.');
      var pbox=el('div'), note=el('p','sub');
      form.appendChild(pl);form.appendChild(pbox);if(pool.length){fillAdd();form.appendChild(addSel)}form.appendChild(note);
      function draw(){[].forEach.call(pbox.querySelectorAll('input'),function(i){typed[i.dataset.k]=i.value});
        pbox.textContent='';var L=cur();read=priceRows(L.map(function(l){return {key:l.key,fx:l.fx,odds:typed[l.key]||''}}),pbox);
        note.textContent='Saves this '+L.length+'-fold with its exact legs, on this phone only.'}
      draw();
      var go=el('button','btn','Save bet');form.appendChild(go);
      go.onclick=function(){
        var bk=sel.value==='Other'?other.value.trim():sel.value, sv=parseFloat(stake.value), rv=parseFloat(ret.value);
        if(!bk){alert('Enter the bookmaker');return}
        if(!(sv>0)||!(rv>0)){alert('Enter the stake and the return shown on the bet slip');return}
        if(rv<sv){alert('The return should include your stake (it is the total paid out if it wins)');return}
        var pr=read();if(!pr){alert("A price couldn't be read: type it like 1/7, 2/13 or 1.14, or leave it blank");return}
        var L=cur();
        var b={id:Date.now().toString(36)+Math.random().toString(36).slice(2,6),date:date,mk:mk,title:card.dataset.title,
          bookie:bk,stake:Math.round(sv*100)/100,ret:Math.round(rv*100)/100,logged:new Date().toISOString(),
          legs:L.map(function(l,n){var o={key:l.key,fx:l.fx,lg:l.lg,pct:l.pct,role:l.role};
            if(pr[n]){o.odds=pr[n].odds;o.price=pr[n].price}return o})};
        var all=bets();all.push(b);
        if(!save(BETS,all)){alert('This browser blocked saving.');return}
        save('goals-last-bookie-'+mk,bk);form.classList.remove('open');form.textContent='';
        paint();showBets();
        var t=document.getElementById('toast');if(t){t.hidden=false;t.textContent='Logged: '+bk+' '+money(b.stake)+' to return '+money(b.ret)+'. See Results → My bets.';
          setTimeout(function(){t.hidden=true},5000)}
      };
    }
    paint();
  });

  function showBets(){
    var box=document.getElementById('my-bets-list'); if(!box)return;
    var all=bets().slice().sort(function(a,b){return a.date<b.date?1:a.date>b.date?-1:(a.logged<b.logged?1:-1)});
    box.textContent='';
    if(!all.length){box.appendChild(el('div','card')).appendChild(el('p','sub',
      'Bets you log from an accumulator card appear here. They are kept on this phone only.'));return}
    var staked=all.reduce(function(s,b){return s+b.stake},0);
    box.appendChild(el('p','sub',all.length+' bet'+(all.length===1?'':'s')+' logged · '+money(staked)+' staked. '+
      'Won/lost and profit will appear here once settling is added.'));
    all.forEach(function(b){
      var c=el('div','card bet'), m=el('div','meta');
      m.appendChild(el('b',null,b.bookie+' · '+b.legs.length+'-fold '+(b.mk==='o15'?'Over 1.5':'GIBH')));
      m.appendChild(el('span','sub',b.date));c.appendChild(m);
      c.appendChild(el('div',null,money(b.stake)+' to return '+money(b.ret)));
      var d=el('details'), sm=el('summary','sub','Legs');d.appendChild(sm);
      var ol=el('ol','legs-list');b.legs.forEach(function(l){ol.appendChild(el('li',null,l.fx+' · '+l.pct+
        (l.odds?' · '+l.odds:'')+(l.role==='extra'?' (own pick)':l.role!=='leg'?' (reserve)':'')))});
      d.appendChild(ol);c.appendChild(d);
      var np=b.legs.filter(function(l){return l.price}).length;
      var pe=el('button','btn ghost',np?'Prices ('+np+' of '+b.legs.length+')':'Add prices');pe.style.marginTop='8px';pe.style.marginRight='8px';
      var pf=el('div','logf');
      pe.onclick=function(){if(pf.classList.toggle('open')){pf.textContent='';var rd=priceRows(b.legs,pf);
        var sv=el('button','btn','Save prices');sv.style.marginTop='8px';pf.appendChild(sv);
        sv.onclick=function(){var pr=rd();if(!pr){alert("A price couldn't be read: type it like 1/7, 2/13 or 1.14");return}
          var all=bets();all.forEach(function(x){if(x.id!==b.id)return;x.legs.forEach(function(l,n){
            if(pr[n]){l.odds=pr[n].odds;l.price=pr[n].price}else{delete l.odds;delete l.price}})});
          save(BETS,all);showBets()}}};
      c.appendChild(pe);
      var del=el('button','btn ghost','Delete');del.style.marginTop='8px';
      del.onclick=function(){if(!confirm('Delete this logged bet?'))return;
        save(BETS,bets().filter(function(x){return x.id!==b.id}));showBets()};
      c.appendChild(del);c.appendChild(pf);box.appendChild(c);
    });
    priceCheck();
  }

  // Prices v ratings: every priced Over 1.5 leg you've logged, against its graded result.
  function priceCheck(){
    var box=document.getElementById('price-check');if(!box)return;box.textContent='';
    var R={};try{R=JSON.parse(document.getElementById('o15-results').textContent)}catch(e){}
    var legs=[],seen={},waiting=0;
    bets().forEach(function(b){if(b.mk!=='o15')return;b.legs.forEach(function(l){
      if(!l.price||seen[l.key])return;seen[l.key]=1;var r=R[l.key];
      if(r===1||r===0)legs.push({p:l.price,pct:parseFloat(l.pct),won:r===1});else if(r!=='v')waiting++})});
    if(!legs.length&&!waiting)return;
    var c=el('div','card');c.appendChild(el('h3',null,'Prices v ratings'));
    if(!legs.length){c.appendChild(el('p','sub',waiting+' priced leg'+(waiting===1?'':'s')+' waiting for results.'));box.appendChild(c);return}
    function table(title,bands,val,extra){
      var t=el('table','pcheck'),h=el('tr');[title,'Landed','Bookmaker','Our rating'].forEach(function(x){h.appendChild(el('th',null,x))});t.appendChild(h);
      bands.forEach(function(bd){var g=legs.filter(function(l){var v=val(l);return v>=bd[0]&&v<bd[1]});if(!g.length)return;
        var w=g.filter(function(l){return l.won}).length,tr=el('tr');
        var imp=g.reduce(function(a,l){return a+100/l.p},0)/g.length,rt=g.reduce(function(a,l){return a+(l.pct||0)},0)/g.length;
        [bd[2],w+' of '+g.length+' ('+Math.round(100*w/g.length)+'%)',Math.round(imp)+'%',Math.round(rt)+'%'].forEach(function(x){tr.appendChild(el('td',null,x))});
        t.appendChild(tr)});
      c.appendChild(t)}
    table('Price',[[0,1.13,'1/8 or shorter'],[1.13,1.17,'2/15 to 1/6'],[1.17,1.2,'2/11'],[1.2,99,'1/5 or longer']],function(l){return l.p});
    table('Our rating',[[82,101,'82%+'],[79,82,'79-82%'],[0,79,'under 79%']],function(l){return l.pct});
    c.appendChild(el('p','sub',legs.length+' priced leg'+(legs.length===1?'':'s')+' graded'+(waiting?', '+waiting+' waiting':'')+
      '. "Bookmaker" is the chance its price implies (it includes their margin). If short prices land more often than '+
      'high ratings do, the price is the better guide. Give it 100+ legs before reading much into it.'));
    box.appendChild(c);
  }
  showBets();

  var bk=document.getElementById('bets-backup'), rb=document.getElementById('bets-restore-btn'),
      ri=document.getElementById('bets-restore'), msg=document.getElementById('bets-backup-msg');
  if(bk)bk.onclick=function(){
    var data=JSON.stringify({kind:'goals-bets',version:1,exported:new Date().toISOString(),bets:bets()},null,1);
    var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([data],{type:'application/json'}));
    a.download='goals-bets-'+new Date().toISOString().slice(0,10)+'.json';document.body.appendChild(a);a.click();
    setTimeout(function(){URL.revokeObjectURL(a.href);a.remove()},1000);
    msg.textContent='Backup of '+bets().length+' bet(s) downloaded.'};
  if(rb)rb.onclick=function(){ri.click()};
  if(ri)ri.onchange=function(){
    var f=ri.files[0];if(!f)return;var r=new FileReader();
    r.onload=function(){try{var j=JSON.parse(r.result);if(j.kind!=='goals-bets'||!Array.isArray(j.bets))throw 0;
        var all=bets(), ids={};all.forEach(function(b){ids[b.id]=1});
        var added=[],merged=0;
        j.bets.forEach(function(b){if(!b||!b.id||ids[b.id]||!b.legs||!(b.stake>0))return;
          var same=all.filter(function(x){return x.date===b.date&&x.mk===b.mk&&x.ret===b.ret})[0];
          if(!same){added.push(b);return}
          var byKey={};b.legs.forEach(function(l){byKey[l.key]=l});    // already logged here: just fill in prices
          same.legs.forEach(function(l){var o=byKey[l.key];if(o&&o.price&&!l.price){l.odds=o.odds;l.price=o.price}});merged++});
        save(BETS,all.concat(added));msg.textContent='Restored '+added.length+' bet(s)'+(merged?', added prices to '+merged:'')+
          ' ('+(j.bets.length-added.length-merged)+' already here).';
        showBets()}catch(e){msg.textContent="That file isn't a bets backup."}
      ri.value=''};
    r.readAsText(f)};
})();
</script>"""


def script(cfg: dict) -> str:
    b = cfg.get("betting") or {}
    bookies = [str(x) for x in (b.get("bookmakers") or ["SpreadEx", "Sky Bet", "Bet365", "BetFred", "BoyleSports"])]
    d = b.get("default_bookmaker") or {}
    data = {"bookies": bookies, "defaults": {"o15": d.get("over_1_5", bookies[0]), "gibh": d.get("gibh", bookies[0])}}
    return SCRIPT_TEMPLATE.replace("__CFG__", json.dumps(data).replace("</", "<\\/"))
