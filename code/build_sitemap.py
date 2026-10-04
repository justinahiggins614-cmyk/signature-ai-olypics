#!/usr/bin/env python3
"""AI Olypics feed + sitemap builder (the 2h bout drip calls this after each run).

Outputs (idempotent, cheap):
  olypics-catalog.json  - one compact record per bout (id, contenders, winner,
                          stage, mission, url) - FIX-02 machine feed
  bouts.html            - pre-rendered static HTML tables (100 bouts/table) so
                          non-JS bots can ingest bout IDs, contenders, verdicts
                          - FIX-03 static fallback
  sitemap.xml           - sitemap INDEX pointing at sitemap-batch-*.xml
  sitemap-batch-N.xml   - modular sitemap batches (<=1000 bout URLs each) - FIX-02
robots.txt already points at sitemap.xml (left untouched).
"""
import json, os, gzip, html
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
BASE = 'https://justinahiggins614-cmyk.github.io/signature-ai-olypics'
today = date.today().isoformat()

# --- load index rows + roster names ---
rows = []
with gzip.open(os.path.join(DATA, 'index.json.gz'), 'rt') as f:
    for line in f:
        if line.strip():
            rows.append(json.loads(line))
names = {}
with open(os.path.join(DATA, 'contenders.json')) as f:
    for c in json.load(f):
        names[c['id']] = c.get('name', c['id'])
stage_names = {}
try:
    for f_ in sorted(os.listdir(os.path.join(DATA, 'chunks'))):
        if f_.endswith('.jsonl.gz'):
            with gzip.open(os.path.join(DATA, 'chunks', f_), 'rt') as g:
                for i, line in enumerate(g):
                    if i > 300:
                        break
                    if line.strip():
                        b = json.loads(line)
                        stage_names.setdefault(b['stage']['key'], b['stage']['name'])
            break
except Exception:
    pass

def esc(s):
    return html.escape(str(s or ''), quote=True)

# --- per-event compact bout lists for the bouts.html archive ---
# NETWORK ORDER (Manon, 2026-10-04): bouts.html carries the full bout catalog
# as A-Z collapsible <details> lists (one per Olypics event) that lazy-load
# their bouts on demand. Event assignment reuses build_medals.event_key_for
# (event_id, else deterministic seed%8) so the archive agrees with
# data/medals.json exactly.
from build_medals import event_key_for, EVENTS
from build_az import write_az, load_games
EV_DIR = os.path.join(DATA, 'events')
os.makedirs(EV_DIR, exist_ok=True)
ev_rows = {key: [] for key, name, emoji, eid in EVENTS}
az_rows = []  # [bout_id, mission, stage_name] -> data/index/az/ (bouts.html A-Z)
for f_ in sorted(os.listdir(os.path.join(DATA, 'chunks'))):
    if not f_.endswith('.jsonl.gz'):
        continue
    with gzip.open(os.path.join(DATA, 'chunks', f_), 'rt') as g:
        for line in g:
            if not line.strip():
                continue
            b = json.loads(line)
            ek = event_key_for(b)
            w = b['winner']['name']
            c0 = b['contenders'][0]['name']
            c1 = b['contenders'][1]['name']
            st = b.get('stage', {}) or {}
            st_name = st.get('name', st.get('key', ''))
            ev_rows[ek].append([b['id'], c0, c1, w, st_name,
                               b['mission'][:60]])
            az_rows.append([b['id'], b.get('mission', ''), st_name])
for key, name, emoji, eid in EVENTS:
    with open(os.path.join(EV_DIR, key + '.json'), 'w') as f:
        json.dump({'event': key, 'name': name, 'emoji': emoji,
                   'bouts': len(ev_rows[key]), 'rows': ev_rows[key]}, f,
                  ensure_ascii=False)
print('events: %d per-event lists -> data/events/ (%d bouts)' %
      (len(EVENTS), sum(len(v) for v in ev_rows.values())))

# --- A-Z archive: per-letter bout lists for the bouts.html "Every battle,
# A-Z by mission" section (+ Weekly Games mode). Built here, in the same
# chunk scan, so it can never go stale relative to the event lists above.
az_manifest = write_az(az_rows, load_games())

# medal leaders for the archive summaries / charts (rebuilt by seed.py's
# build_medals() call BEFORE this script runs in the drip, so never stale)
med = json.load(open(os.path.join(DATA, 'medals.json')))
med_by_ev = med.get('by_event', {})

# --- FIX-02: olypics-catalog.json ---
catalog = []
for r in rows:
    bid, wid, wname, c0, c1, stage_key, mission = r
    catalog.append({
        'id': bid,
        'url': BASE + '/?battle=' + bid,
        'contenders': [
            {'id': c0, 'name': names.get(c0, c0)},
            {'id': c1, 'name': names.get(c1, c1)},
        ],
        'winner': {'id': wid, 'name': wname},
        'stage': {'key': stage_key, 'name': stage_names.get(stage_key, stage_key)},
        'mission': mission,
    })
with open(os.path.join(ROOT, 'olypics-catalog.json'), 'w') as f:
    json.dump({'site': 'AI Olypics', 'updated': today, 'bouts': len(catalog),
               'records': catalog}, f, indent=1)
print('catalog: %d bouts -> olypics-catalog.json' % len(catalog))

# --- archive: A-Z event <details> + medal charts (lazy-loaded bout lists) ---
ev_az = sorted(EVENTS, key=lambda e: e[1].lower())
details_html = []
for key, name, emoji, eid in ev_az:
    n = len(ev_rows[key])
    leaders = med_by_ev.get(key, [])[:1]
    lead = (' · Top: %s (%d gold)' % (esc(leaders[0]['name']), leaders[0].get('gold', 0))
            if leaders else '')
    details_html.append(
        '<details class="ev" data-ev="%s" data-loaded="0"><summary>%s <b>%s</b> '
        '&mdash; %s bouts%s</summary><div class="evbody"></div></details>' % (
            key, emoji, esc(name), '{:,}'.format(n), lead))
med_rows = []
for i, e in enumerate(med.get('overall_ranking', [])[:5], 1):
    med_rows.append('<tr><td>%d</td><td>%s</td><td>%d</td><td>%d</td><td>%d</td></tr>' % (
        i, esc(e['name']), e.get('gold', 0), e.get('silver', 0), e.get('bronze', 0)))
ev_med_rows = []
for key, name, emoji, eid in ev_az:
    t = med_by_ev.get(key, [])
    if t:
        ev_med_rows.append('<tr><td>%s %s</td><td>%s</td><td>%d</td><td>%d</td><td>%d</td></tr>' % (
            emoji, esc(name), esc(t[0]['name']), t[0].get('gold', 0),
            t[0].get('silver', 0), t[0].get('bronze', 0)))

ARCH_JS = r"""
<script>
function olyEsc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function olyRow(r){var loser=r[3]===r[1]?r[2]:r[1];return '<li><a href="?battle='+r[0]+'">'+r[0]+'</a> &mdash; <b>'+olyEsc(r[3])+'</b> def. '+olyEsc(loser)+' &middot; '+olyEsc(r[4])+' &middot; <i>'+olyEsc(r[5])+'</i></li>';}
function olyLoadEv(det){var body=det.querySelector('.evbody');if(det.getAttribute('data-loaded')==='1')return;det.setAttribute('data-loaded','1');body.innerHTML='<p class="note">Loading bouts&hellip;</p>';fetch('data/events/'+det.getAttribute('data-ev')+'.json').then(function(r){return r.json();}).then(function(d){var h='<ul class="boutlist">';d.rows.forEach(function(r){h+=olyRow(r);});body.innerHTML=h+'</ul><p class="note">'+d.rows.length.toLocaleString()+' bouts in this event.</p>';}).catch(function(){body.innerHTML='<p class="note">Could not load this event\u2019s bouts. Check your connection and reopen.</p>';det.setAttribute('data-loaded','0');});}
document.querySelectorAll('details.ev').forEach(function(det){det.addEventListener('toggle',function(){if(det.open)olyLoadEv(det);});});
function olySearch(){var q=document.getElementById('olyq').value.trim().toLowerCase();var res=document.getElementById('olyres');if(q.length<2){res.innerHTML='<p class="note">Type at least 2 characters &mdash; a contender, winner, arena, mission, or JAH-OLY-&hellip;</p>';return;}res.innerHTML='<p class="note">Searching every battle&hellip;</p>';var keys=Array.prototype.map.call(document.querySelectorAll('details.ev'),function(d){return d.getAttribute('data-ev');});Promise.all(keys.map(function(k){return fetch('data/events/'+k+'.json').then(function(r){return r.json();});})).then(function(all){var hits=[];all.forEach(function(d){d.rows.forEach(function(r){if((r[0]+' '+r[1]+' '+r[2]+' '+r[3]+' '+r[4]+' '+r[5]).toLowerCase().indexOf(q)>=0)hits.push(r);});});if(!hits.length){res.innerHTML='<p class="note">No battles match.</p>';return;}var h='<ul class="boutlist">'+hits.slice(0,50).map(olyRow).join('')+'</ul>';if(hits.length>50)h+='<p class="note">Showing 50 of '+hits.length+' matches &mdash; narrow your search for more.</p>';res.innerHTML=h;}).catch(function(){res.innerHTML='<p class="note">Search failed &mdash; try again.</p>';});}
document.getElementById('olygo').addEventListener('click',olySearch);
document.getElementById('olyq').addEventListener('keydown',function(e){if(e.key==='Enter')olySearch();});
/* ---- Every battle, A-Z by mission ----
   Per-letter files at data/index/az/<LETTER>.json.gz (+ manifest.json,
   games.json) are built by code/build_az.py, called from build_sitemap.py
   in the same chunk scan as the event lists, so the archive can never go
   stale. A letter's file loads only on first open. Entries deep-link to
   ./?battle=<id> (the battle record); games deep-link to games.html?games=. */
var AZLETTERS="ABCDEFGHIJKLMNOPQRSTUVWXYZ#".split(""),AZ={counts:null,rows:{},shown:{},loading:{}},AZ_PAGE=250;
function azGunzip(url){return fetch(url).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.arrayBuffer();}).then(function(ab){if(typeof DecompressionStream==="undefined")throw new Error("gzip unsupported");var ds=new DecompressionStream("gzip");return new Response(new Blob([ab]).stream().pipeThrough(ds)).text();});}
function azItemHtml(r){return '<a class="azitem" href="./?battle='+r[0]+'"><span class="azid">'+r[0]+'</span><span class="aztitle">'+olyEsc(r[1])+'</span><span class="azcat">'+olyEsc(r[2]||"")+'</span></a>';}
function azRenderPage(L){var rows=AZ.rows[L]||[],shown=AZ.shown[L]||0;var body=document.querySelector('[data-azbody="'+L+'"]');if(!body)return;var h="",i;for(i=0;i<shown&&i<rows.length;i++)h+=azItemHtml(rows[i]);if(shown<rows.length){h+='<button type="button" class="azmore" data-azmore="'+L+'">SHOW MORE ('+(rows.length-shown).toLocaleString()+' REMAINING)</button>';}else{h+='<p class="note">End of letter '+olyEsc(L)+' \u2014 '+rows.length.toLocaleString()+' battles shown.</p>';}body.innerHTML=h;}
function azLoadLetter(L){if(AZ.rows[L]||AZ.loading[L])return;AZ.loading[L]=true;var body=document.querySelector('[data-azbody="'+L+'"]');azGunzip("data/index/az/"+L+".json.gz").then(function(text){var rows=[];text.split("\n").forEach(function(ln){ln=ln.trim();if(!ln)return;try{rows.push(JSON.parse(ln));}catch(x){}});AZ.rows[L]=rows;AZ.shown[L]=Math.min(AZ_PAGE,rows.length);delete AZ.loading[L];azRenderPage(L);}).catch(function(){delete AZ.loading[L];if(body)body.innerHTML='<p class="azerr">Could not load letter '+olyEsc(L)+' \u2014 check your connection and reopen.</p>';});}
function azHandleLetterParam(){var m=/[?&]letter=([A-Za-z#])/.exec(location.search);if(!m)return;var L=m[1].toUpperCase();var d=document.querySelector('#azletters details[data-letter="'+L+'"]');if(!d)return;d.open=true;azLoadLetter(L);}
function azRenderLetters(){var box=document.getElementById("azletters");if(!box||!AZ.counts)return;var h="";AZLETTERS.forEach(function(L){var n=AZ.counts[L]||0;h+='<details class="azsec" data-letter="'+L+'"><summary><span class="azletter">'+L+'</span><span class="azcount">'+n.toLocaleString()+' battles</span></summary><div class="azbody" data-azbody="'+L+'"><p class="azload">Open to load this letter&hellip;</p></div></details>';});box.innerHTML=h;azHandleLetterParam();}
function azRenderGames(list){var box=document.getElementById("azgames");if(!box||box.getAttribute("data-done"))return;box.setAttribute("data-done","1");var h="";if(!list.length)h='<p class="note">No weekly games archived yet.</p>';list.forEach(function(g){h+='<a class="azitem" href="games.html?games='+olyEsc(g.id)+'"><span class="azid">'+olyEsc(g.id)+'</span><span class="aztitle">Week '+g.week+' \u2014 week of '+olyEsc(g.week_start||"")+'</span><span class="azcat">'+Number(g.bout_count||0).toLocaleString()+' bouts</span></a>';});box.innerHTML=h;}
function azBuild(){var box=document.getElementById("azletters");if(!box)return;fetch("data/index/az/manifest.json").then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}).then(function(m){AZ.counts=m.counts||{};var el=document.getElementById("azTotal");if(el&&m.total)el.textContent=Number(m.total).toLocaleString();azRenderLetters();return fetch("data/index/az/games.json").then(function(r){return r.ok?r.json():[];}).catch(function(){return[];});}).then(function(g){azRenderGames(g||[]);}).catch(function(){box.innerHTML='<p class="note">The archive index could not be loaded \u2014 check your connection and reload. Search still works.</p>';});}
document.querySelectorAll(".azmode").forEach(function(b){b.addEventListener("click",function(){document.querySelectorAll(".azmode").forEach(function(x){x.classList.remove("active")});b.classList.add("active");var letters=document.getElementById("azletters"),games=document.getElementById("azgames");if(b.getAttribute("data-azmode")==="games"){letters.hidden=true;games.hidden=false;}else{letters.hidden=false;games.hidden=true;}});});
document.addEventListener("click",function(e){var m=e.target&&e.target.getAttribute?e.target.getAttribute("data-azmore"):null;if(m){AZ.shown[m]=(AZ.shown[m]||0)+AZ_PAGE;azRenderPage(m);}});
document.addEventListener("toggle",function(e){var d=e.target;if(d&&d.tagName==="DETAILS"&&d.classList.contains("azsec")&&d.open){azLoadLetter(d.getAttribute("data-letter"));}},true);
azBuild();
</script>
"""

ARCH_CSS = ('.archbox{border:2px solid #b36b00;background:#fff8ec;border-radius:10px;'
            'padding:12px 14px;margin:16px 0}'
            'details.ev{border:1px solid #999;border-radius:8px;margin:8px 0;background:#fff}'
            'details.ev summary{cursor:pointer;padding:14px 12px;font-size:16px;list-style:none}'
            'details.ev summary::-webkit-details-marker{display:none}'
            'details.ev summary:before{content:"\\25B6  ";color:#b36b00}'
            'details.ev[open] summary:before{content:"\\25BC  "}'
            '.evbody{padding:0 12px 12px}'
            'ul.boutlist{list-style:none;padding:0;margin:8px 0;max-height:420px;overflow:auto}'
            'ul.boutlist li{padding:7px 4px;border-top:1px solid #eee;font-size:13px}'
            '#olyq{width:68%%;max-width:420px;padding:11px;font-size:15px;border:1px solid #999;border-radius:6px}'
            'button.go{padding:11px 18px;font-size:15px;cursor:pointer;margin-left:6px}'
            'table.med{font-size:13px}table.med td,table.med th{padding:5px 8px}'
            '.note{color:#555;font-size:13px}'
            '.azmodes{display:flex;gap:10px;margin:10px 0;flex-wrap:wrap}'
            '.azmode{background:#fff8ec;border:1px solid #b36b00;color:#8a4b00;'
            'border-radius:8px;padding:9px 18px;font-size:14px;cursor:pointer}'
            '.azmode.active,.azmode:hover{background:#b36b00;color:#fff}'
            'details.azsec{border:1px solid #999;border-radius:8px;margin:8px 0;background:#fff}'
            'details.azsec summary{cursor:pointer;padding:12px;font-size:15px;'
            'list-style:none;display:flex;gap:12px;align-items:baseline}'
            'details.azsec summary::-webkit-details-marker{display:none}'
            'details.azsec summary:before{content:"\\25B6  ";color:#b36b00}'
            'details.azsec[open] summary:before{content:"\\25BC  "}'
            '.azletter{font-weight:bold;color:#8a4b00;min-width:30px;font-size:17px}'
            '.azcount{margin-left:auto;color:#666;font-size:13px}'
            '.azbody{padding:0 12px 12px}'
            'a.azitem{display:flex;gap:10px;align-items:baseline;padding:7px 4px;'
            'border-top:1px solid #eee;font-size:13px;text-decoration:none;color:inherit}'
            'a.azitem:hover{background:#fff8ec}'
            '.azid{color:#8a4b00;font-weight:bold;white-space:nowrap;font-size:12px}'
            '.aztitle{flex:1;min-width:0}'
            '.azcat{color:#666;font-size:12px;white-space:nowrap;overflow:hidden;'
            'text-overflow:ellipsis;max-width:32%}'
            '.azmore{display:block;margin:10px auto;padding:10px 22px;background:#fff8ec;'
            'border:1px solid #b36b00;color:#8a4b00;border-radius:8px;cursor:pointer;font-size:14px}'
            '.azload,.azerr{color:#666;font-size:13px;text-align:center;padding:12px}')
# --- TAB-WAVE (2026-10-04): calculator-style tab bar + Ask-the-AI box, baked into
# every regenerated bouts.html (drip-proof).
TABBAR_OLY = r"""<!-- JAH TAB BAR — Manon's 2026-10-04 order (calculator screenshot as spec).
     Paste right after </header> (or after the hero/title block) on index.html AND on the archive page.
     On index.html: "Front Door" carries class "on". On the archive page: "1 Million Archive" carries "on".
     Replace <a class="jtab" href="games.html">Games</a><a class="jtab" href="health.html">Health</a> with <a class="jtab" href="...">Label</a> items (may be empty). -->
<style>
.jtabbar{display:flex;gap:8px;overflow-x:auto;padding:10px 12px;-webkit-overflow-scrolling:touch;scrollbar-width:thin;border-bottom:1px solid rgba(128,128,128,.25)}
.jtabbar a.jtab{flex:0 0 auto;text-decoration:none;border:1px solid rgba(160,160,160,.45);border-radius:999px;padding:9px 16px;font-size:.92em;color:inherit;background:rgba(127,127,127,.08);white-space:nowrap;font-family:inherit}
.jtabbar a.jtab.on{background:#f5c518;border-color:#f5c518;color:#191919;font-weight:700}
</style>
<nav class="jtabbar" aria-label="Site sections">
<a class="jtab" href="index.html">🏠 Front Door</a>
<a class="jtab" href="add-ai.html">➕ Add Your Own AI</a>
<a class="jtab on" href="bouts.html">📚 1 Million Archive</a>
<a class="jtab" href="games.html">Games</a><a class="jtab" href="health.html">Health</a>
</nav>
"""
ASKAI_OLY = r"""<!-- ASK THE AI — Manon's 2026-10-04 order. Paste on the archive page, directly under the
     search/filter area (or at the top of the archive section if there is no search box).
     It FINDS records by scanning the page's own archive list, and ANSWERS with his real
     Signature Llama (same loader as the phone book). Never fake: if the Llama can't load,
     the found records are still shown honestly. Replace AI Olypics and the battle-bout archive. -->
<div class="jah-askai" id="jah-askai">
<style>
.jah-askai{border:1px solid rgba(160,160,160,.4);border-radius:12px;padding:14px;margin:14px 0;background:rgba(127,127,127,.06)}
.jah-askai h2{margin:0 0 4px;font-size:1.15em}
.jah-askai .jah-askai-sub{margin:0 0 10px;font-size:.9em;opacity:.85}
.jah-askai .jah-askai-row{display:flex;gap:8px}
.jah-askai input#jah-askai-q{flex:1;min-width:0;padding:10px 12px;border-radius:8px;border:1px solid rgba(160,160,160,.5);font-size:1em;background:#fff;color:#111}
.jah-askai button#jah-askai-go{padding:10px 18px;border-radius:8px;border:1px solid #f5c518;background:#f5c518;color:#191919;font-weight:700;font-size:1em;cursor:pointer}
.jah-askai #jah-askai-out{margin-top:10px;font-size:.95em}
.jah-askai #jah-askai-out ul{margin:6px 0;padding-left:20px}
.jah-askai .jah-askai-ans{border-left:3px solid #f5c518;padding-left:10px;margin-top:8px}
.jah-askai .jah-askai-thinking{opacity:.7;font-style:italic}
</style>
<h2>🤖 Ask the AI</h2>
<p class="jah-askai-sub">Ask about anything in this archive — the AI searches the records and answers.</p>
<div class="jah-askai-row">
<input id="jah-askai-q" type="text" autocomplete="off" placeholder="Ask about this archive…" aria-label="Ask about this archive">
<button id="jah-askai-go" type="button">Ask</button>
</div>
<div id="jah-askai-out" aria-live="polite"></div>
<script>
(function(){
var SITE="AI Olypics", DESC="the battle-bout archive";
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
/* Real Signature Llama loader — same pattern as the phone book. */
var LLAMA_BASE="https://justinahiggins614-cmyk.github.io/signature-backend/sigllama/";
var LLAMA_VOCAB="vocab2.json", LLAMA_BIN="sigllama-v2.bin";
var net={loading:null,ready:false};
function llamaEnsure(){
  if(net.ready) return Promise.resolve(true);
  if(net.loading) return net.loading;
  net.loading=new Promise(function(resolve){
    function fin(ok){net.ready=!!ok;resolve(net.ready);}
    function boot(){try{
      if(typeof SigLlama==="undefined"){fin(false);return;}
      SigLlama.load(LLAMA_BASE,LLAMA_VOCAB,LLAMA_BIN).then(function(){fin(true);},function(){fin(false);});
    }catch(e){fin(false);}}
    if(typeof SigLlama!=="undefined"){boot();return;}
    var s=document.createElement("script");s.src=LLAMA_BASE+"sigllama.js";s.async=true;
    s.onload=boot;s.onerror=function(){fin(false);};document.head.appendChild(s);
  });
  return net.loading;
}
/* FIND: keyword scan over the page's own archive list links. */
function findRecords(q){
  var words=String(q).toLowerCase().split(/[^a-z0-9]+/).filter(function(w){return w.length>2;});
  if(!words.length) return [];
  var scope=document.getElementById("jah-askai-scope")||document.querySelector("main")||document.body;
  var links=scope.getElementsByTagName("a"),out=[],seen={};
  for(var i=0;i<links.length;i++){
    var a=links[i];
    if(a.closest("nav")||a.closest("header")||a.closest("footer")||a.closest(".jah-askai")) continue;
    var t=(a.textContent||"").replace(/\s+/g," ").trim();
    if(t.length<3||t.length>160) continue;
    var tl=t.toLowerCase(),score=0;
    for(var j=0;j<words.length;j++) if(tl.indexOf(words[j])>=0) score++;
    if(score>0&&!seen[a.href]){seen[a.href]=1;out.push({t:t,h:a.href,s:score});}
    if(out.length>=60) break;
  }
  out.sort(function(x,y){return y.s-x.s;});
  return out.slice(0,5);
}
function ask(){
  var q=document.getElementById("jah-askai-q").value.trim();
  var out=document.getElementById("jah-askai-out");
  if(!q){out.innerHTML="<p>Please type a question first.</p>";return;}
  var found=findRecords(q),html="";
  if(found.length){
    html+="<p><b>📎 I found "+found.length+" record"+(found.length>1?"s":"")+" matching your words:</b></p><ul>"+
      found.map(function(f){return '<li><a href="'+esc(f.h)+'">'+esc(f.t)+"</a></li>";}).join("")+"</ul>";
  }else{
    html+="<p>No record titles matched those words — asking the AI anyway.</p>";
  }
  html+='<p class="jah-askai-thinking">🤖 thinking…</p>';
  out.innerHTML=html;
  var think=out.querySelector(".jah-askai-thinking");
  llamaEnsure().then(function(ok){
    if(!ok||typeof SigLlama==="undefined"||!SigLlama.loaded||!SigLlama.loaded()){
      think.textContent="The AI voice could not load right now — the records above are what matched your words.";return;}
    var ctx="You are the "+SITE+" archive helper. "+DESC+".\n"+
      (found.length?("Records matching the question: "+found.map(function(f){return f.t;}).join(" | ")+"\n"):"")+
      "User: "+q.slice(0,300)+"\nHelper (one to three sentences, plain words):";
    var done=false;
    function show(t){
      if(done) return; done=true;
      t=String(t||"").trim().replace(/^Helper\s*:\s*/i,"");
      if(t.length<8||/User\s*:/.test(t)) t="I searched the archive for you — the matching records are listed above.";
      think.outerHTML='<p class="jah-askai-ans">🤖 '+esc(t)+"</p>";
    }
    try{
      SigLlama.generate(ctx,{maxTokens:90,temperature:0.5,topK:40}).then(show,function(){show("");});
      setTimeout(function(){show("");},25000);
    }catch(e){show("");}
  });
}
document.getElementById("jah-askai-go").addEventListener("click",ask);
document.getElementById("jah-askai-q").addEventListener("keydown",function(e){if(e.key==="Enter")ask();});
})();
</script>
</div>
"""
# --- FIX-03: bouts.html static tables (100 bouts per table) ---
# CONSISTENCY PASS: every bout row carries the SIMULATION record-status badge.
# NETWORK ORDER (Manon, 2026-10-04): the page opens with the full Bout Archive
# (search + A-Z collapsible event lists + medal charts); the static record
# tables stay below as the bot-readable fallback. The count is stamped from
# len(catalog) — this script runs AFTER seed.py merges the new index rows in
# the drip, so the stamp is never one run behind.
parts = []
for i in range(0, len(catalog), 100):
    batch = catalog[i:i + 100]
    trs = ['<tr><th>Bout</th><th>Contender A</th><th>Contender B</th>'
           '<th>Winner</th><th>Stage</th><th>Mission</th><th>Record status</th></tr>']
    for b in batch:
        trs.append('<tr><td><a href="?battle=%s">%s</a></td><td>%s</td><td>%s</td>'
                   '<td><b>%s</b></td><td>%s</td><td>%s</td>'
                   '<td><span class="recbadge">SIMULATION</span></td></tr>' % (
            esc(b['id']), esc(b['id']),
            esc(b['contenders'][0]['name']), esc(b['contenders'][1]['name']),
            esc(b['winner']['name']), esc(b['stage']['name']), esc(b['mission'])))
    parts.append('<section><h2 id="batch-%d">Bouts %d&ndash;%d</h2>'
                 '<table>%s</table></section>' % (
        i // 100 + 1, i + 1, i + len(batch), ''.join(trs)))
nav = ' '.join('<a href="#batch-%d">%d&ndash;%d</a>' % (i // 100 + 1, i + 1, min(i + 100, len(catalog)))
               for i in range(0, len(catalog), 100))
page = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>AI Olypics — Bout Archive &amp; Record Tables</title>'
        '<meta name="description" content="The full AI Olypics bout archive: every battle by Olypics event (A-Z), medal charts, search, and static record tables with bout ID, contenders, winner, stage, mission.">'
        '<link rel="canonical" href="%s/bouts.html">' % BASE +
        '<script type="application/ld+json">' +
        json.dumps({"@context": "https://schema.org", "@type": "Dataset",
                    "name": "AI Olypics bout records",
                    "url": BASE + "/bouts.html",
                    "creator": {"@type": "Person", "name": "Justin Addam Higgins"},
                    "description": "The full AI Olypics bout archive and static HTML record tables for every bout."}) +
        '</script><style>body{font-family:Arial,sans-serif;max-width:1100px;margin:0 auto;padding:16px}'
        'table{border-collapse:collapse;width:100%%;margin:12px 0;font-size:13px}'
        'th,td{border:1px solid #999;padding:6px 8px;text-align:left;vertical-align:top}'
        'th{background:#eee}nav.toc{margin:12px 0;line-height:2}'
        '.sitekicker{font-size:11px;letter-spacing:.28em;color:#666}'
        '.recbadge{display:inline-block;border:2px solid #b36b00;background:#fff4e0;color:#8a4b00;border-radius:8px;padding:2px 10px;font-size:11px;font-weight:bold;letter-spacing:.06em}'
        + ARCH_CSS +
        '</style></head><body>'
        '<p class="sitekicker"><b>SITE 17 OF 27</b> &middot; THE JAH NETWORK</p>'
        '<h1>AI Olypics &mdash; Bout Archive</h1>'
        '<p><b id="boutCount">%s</b> battles recorded. Every bout is a deterministic <span class="recbadge">SIMULATION</span> &mdash; no real AIs fought. The battles are the product: open an event, search the archive, pick a fight to relive. <a href="./">Back to the battle dome</a>.</p>'
        '<div class="archbox"><h2>&#128269; Search every battle</h2>'
        '<input id="olyq" type="search" placeholder="Contender, winner, arena, mission, JAH-OLY-&hellip;" aria-label="Search battles">'
        '<button class="go" id="olygo" type="button">Search</button>'
        '<div id="olyres"><p class="note">Search runs across all eight events &mdash; results link straight to each battle.</p></div></div>'
        '<h2>&#127963;&#65039; The eight Olypics events &mdash; A&ndash;Z</h2>'
        '<p class="note">Open an event to load its battles &mdash; each event loads on demand, never all at once.</p>'
        '%s'
        '<h2>&#127993;&#65039; Every battle, A&ndash;Z by mission</h2>'
        '<p class="note">The whole bout catalog, A&ndash;Z by battle mission &mdash; <b id="azTotal">%s</b> battles, every one deep-linked to its battle record. Open a letter &mdash; its list loads on demand, so the page stays fast on phones. Or browse the Weekly Olypics games hall records.</p>'
        '<div class="azmodes" role="group" aria-label="Archive browse mode">'
        '<button type="button" class="azmode active" data-azmode="letters">A&ndash;Z by mission</button>'
        '<button type="button" class="azmode" data-azmode="games">Weekly games</button></div>'
        '<div id="azletters"><p class="note">Loading archive index&hellip;</p></div>'
        '<div id="azgames" hidden></div>'
        '<h2>&#127941; Medal charts</h2>'
        '<h3>Overall champions</h3>'
        '<table class="med"><tr><th></th><th>Champion</th><th>&#129351;</th><th>&#129352;</th><th>&#129353;</th></tr>%s</table>'
        '<h3>Event leaders</h3>'
        '<table class="med"><tr><th>Event</th><th>Leader</th><th>&#129351;</th><th>&#129352;</th><th>&#129353;</th></tr>%s</table>'
        '<h2 id="static">&#128203; Static record tables (bot-readable)</h2>'
        '<nav class="toc" aria-label="Bout batches">%s</nav>%s' % (
        '{:,}'.format(len(catalog)),
        ''.join(details_html),
        '{:,}'.format(len(az_rows)),
        ''.join(med_rows), ''.join(ev_med_rows),
        nav, ''.join(parts))
        + ARCH_JS + '</body></html>')
# TAB-WAVE: tab bar after the intro block, Ask-the-AI under the search box.
page = page.replace('<a href="./">Back to the battle dome</a>.</p>',
                    '<a href="./">Back to the battle dome</a>.</p>' + TABBAR_OLY, 1)
page = page.replace('results link straight to each battle.</p></div></div>',
                    'results link straight to each battle.</p></div></div>' + ASKAI_OLY, 1)
with open(os.path.join(ROOT, 'bouts.html'), 'w') as f:
    f.write(page)
print('bouts.html: %d static tables + %d event archive lists' % (len(parts), len(ev_az)))

# --- FIX-02: modular sitemaps - index + batches of 1000 bout URLs ---
urls = [BASE + '/', BASE + '/bouts.html', BASE + '/games.html', BASE + '/add-ai.html']
# weekly games deep links
games_dir = os.path.join(DATA, 'games')
if os.path.isdir(games_dir):
    for gf in sorted(os.listdir(games_dir)):
        if gf.startswith('weekly-') and gf.endswith('.json'):
            gid = 'JAH-OLY-GAMES-' + gf[len('weekly-'):-len('.json')]
            urls.append(BASE + '/games.html?games=' + gid)
urls += [BASE + '/?battle=' + r[0] for r in rows]
batches = [urls[i:i + 1000] for i in range(0, len(urls), 1000)]
batch_names = []
for n, batch in enumerate(batches, 1):
    name = 'sitemap-batch-%d.xml' % n
    sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + '\n'.join('<url><loc>%s</loc><lastmod>%s</lastmod></url>' % (u, today)
                      for u in batch)
          + '\n</urlset>\n')
    with open(os.path.join(ROOT, name), 'w') as f:
        f.write(sm)
    batch_names.append(name)
idx = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
       + '\n'.join('<sitemap><loc>%s/%s</loc><lastmod>%s</lastmod></sitemap>' % (BASE, n, today)
                   for n in batch_names)
       + '\n</sitemapindex>\n')
with open(os.path.join(ROOT, 'sitemap.xml'), 'w') as f:
    f.write(idx)
print('sitemap: %d URLs across %d batch files (index at sitemap.xml)' % (len(urls), len(batch_names)))
