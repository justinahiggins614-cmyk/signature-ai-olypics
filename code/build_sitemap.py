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

# --- FIX-03: bouts.html static tables (100 bouts per table) ---
# CONSISTENCY PASS: every bout row carries the SIMULATION record-status badge.
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
        '<title>AI Olypics — Bout Record Tables</title>'
        '<meta name="description" content="Static record tables for every AI Olypics bout: bout ID, contenders, winner, stage, mission.">'
        '<link rel="canonical" href="%s/bouts.html">' % BASE +
        '<script type="application/ld+json">' +
        json.dumps({"@context": "https://schema.org", "@type": "Dataset",
                    "name": "AI Olypics bout records",
                    "url": BASE + "/bouts.html",
                    "creator": {"@type": "Person", "name": "Justin Addam Higgins"},
                    "description": "Static HTML record tables for every AI Olypics bout."}) +
        '</script><style>body{font-family:Arial,sans-serif;max-width:1100px;margin:0 auto;padding:16px}'
        'table{border-collapse:collapse;width:100%%;margin:12px 0;font-size:13px}'
        'th,td{border:1px solid #999;padding:6px 8px;text-align:left;vertical-align:top}'
        'th{background:#eee}nav.toc{margin:12px 0;line-height:2}'
        '.sitekicker{font-size:11px;letter-spacing:.28em;color:#666}'
        '.recbadge{display:inline-block;border:2px solid #b36b00;background:#fff4e0;color:#8a4b00;border-radius:8px;padding:2px 10px;font-size:11px;font-weight:bold;letter-spacing:.06em}'
        '</style></head><body>'
        '<p class="sitekicker"><b>SITE 17 OF 27</b> &middot; THE JAH NETWORK</p>'
        '<h1>AI Olypics — Bout Record Tables</h1>'
        '<p>%d bouts recorded (static, bot-readable). Every bout is a deterministic <span class="recbadge">SIMULATION</span> — no real AIs fought. <a href="./">Back to the battle dome</a>.</p>'
        '<nav class="toc" aria-label="Bout batches">%s</nav>%s</body></html>' % (
        len(catalog), nav, ''.join(parts)))
with open(os.path.join(ROOT, 'bouts.html'), 'w') as f:
    f.write(page)
print('bouts.html: %d static tables' % len(parts))

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
