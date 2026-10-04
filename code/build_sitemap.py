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
EV_DIR = os.path.join(DATA, 'events')
os.makedirs(EV_DIR, exist_ok=True)
ev_rows = {key: [] for key, name, emoji, eid in EVENTS}
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
            ev_rows[ek].append([b['id'], c0, c1, w,
                               b['stage'].get('name', b['stage'].get('key', '')),
                               b['mission'][:60]])
for key, name, emoji, eid in EVENTS:
    with open(os.path.join(EV_DIR, key + '.json'), 'w') as f:
        json.dump({'event': key, 'name': name, 'emoji': emoji,
                   'bouts': len(ev_rows[key]), 'rows': ev_rows[key]}, f,
                  ensure_ascii=False)
print('events: %d per-event lists -> data/events/ (%d bouts)' %
      (len(EVENTS), sum(len(v) for v in ev_rows.values())))

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
            '.note{color:#555;font-size:13px}')
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
        '<h2>&#127941; Medal charts</h2>'
        '<h3>Overall champions</h3>'
        '<table class="med"><tr><th></th><th>Champion</th><th>&#129351;</th><th>&#129352;</th><th>&#129353;</th></tr>%s</table>'
        '<h3>Event leaders</h3>'
        '<table class="med"><tr><th>Event</th><th>Leader</th><th>&#129351;</th><th>&#129352;</th><th>&#129353;</th></tr>%s</table>'
        '<h2 id="static">&#128203; Static record tables (bot-readable)</h2>'
        '<nav class="toc" aria-label="Bout batches">%s</nav>%s' % (
        '{:,}'.format(len(catalog)),
        ''.join(details_html),
        ''.join(med_rows), ''.join(ev_med_rows),
        nav, ''.join(parts))
        + ARCH_JS + '</body></html>')
with open(os.path.join(ROOT, 'bouts.html'), 'w') as f:
    f.write(page)
print('bouts.html: %d static tables + %d event archive lists' % (len(parts), len(ev_az)))

# --- FIX-02: modular sitemaps - index + batches of 1000 bout URLs ---
urls = [BASE + '/', BASE + '/bouts.html', BASE + '/games.html']
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
