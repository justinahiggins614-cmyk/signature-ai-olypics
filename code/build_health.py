#!/usr/bin/env python3
"""Archive health: verify the Olypics archive end-to-end and publish
health.json + health.html. Run after every drip (cron)."""
import json, os, gzip, glob, hashlib, subprocess
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
BASE = 'https://justinahiggins614-cmyk.github.io/signature-ai-olypics/'

now = datetime.datetime.now(datetime.timezone.utc)
man = json.load(open(os.path.join(DATA, 'manifest.json')))
checks = []

def check(name, ok, detail=''):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    return ok

# 1. chunk files vs manifest
chunks = sorted(glob.glob(os.path.join(DATA, 'chunks', 'bouts-c*.jsonl.gz')))
check('chunk files present', len(chunks) == man['chunks'],
      '%d files, manifest says %d' % (len(chunks), man['chunks']))

# 2. scan chunks: count, IDs, dupes, hash spot-check
ids, dupes, n_recs = set(), 0, 0
hash_ok, hash_n = True, 0
first_id, last_id = None, None
for p in chunks:
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            b = json.loads(line)
            n_recs += 1
            if b['id'] in ids:
                dupes += 1
            ids.add(b['id'])
            if first_id is None:
                first_id = b['id']
            last_id = b['id']
            if n_recs % 997 == 0:  # spot-check ~12 records
                r = {k: v for k, v in b.items() if k != 'content_hash'}
                h = 'sha256:' + hashlib.sha256(
                    json.dumps(r, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=False).encode('utf-8')).hexdigest()
                if h != b['content_hash']:
                    hash_ok = False
                hash_n += 1
check('bout count matches manifest', n_recs == man['bouts'],
      '%d records, manifest %d' % (n_recs, man['bouts']))
check('no duplicate bout IDs', dupes == 0, '%d dupes' % dupes)
check('ID range contiguous', first_id == man['bout_id_range'][0] and
      last_id == man['bout_id_range'][1],
      '%s .. %s' % (first_id, last_id))
check('content_hash spot-check', hash_ok, '%d records re-hashed' % hash_n)

# 3. index rows vs manifest + index hash
idx_p = os.path.join(DATA, 'index.json.gz')
with gzip.open(idx_p, 'rt') as f:
    rows = [l for l in f if l.strip()]
check('index rows match manifest', len(rows) == man['bouts'],
      '%d rows' % len(rows))
with open(idx_p, 'rb') as f:
    ih = 'sha256:' + hashlib.sha256(f.read()).hexdigest()
check('index hash matches manifest', ih == man['index_hash'])

# 4. engine determinism sample (node)
js = ("const E=require(%s);const roster=require(%s);"
      "const out=[1,2059,4535,6000,12000].map(n=>{const b=E.bout(n,roster);"
      "return [b.id,b.winner.id,b.margin,b.seed];});"
      "process.stdout.write(JSON.stringify(out));"
      % (json.dumps(os.path.join(HERE, 'engine.js')),
         json.dumps(os.path.join(DATA, 'contenders.json'))))
p = subprocess.run(['node', '-e', js], capture_output=True, text=True)
det_ok = False
if p.returncode == 0:
    det_ok = True
    for bid, wid, margin, seed in json.loads(p.stdout):
        with gzip.open(os.path.join(DATA, 'chunks',
                                    'bouts-c%05d.jsonl.gz' % ((int(bid.split('-')[-1]) - 1) // 100 + 1)),
                       'rt', encoding='utf-8') as f:
            for line in f:
                b = json.loads(line)
                if b['id'] == bid:
                    if b['winner']['id'] != wid or b['margin'] != margin or b['seed'] != seed:
                        det_ok = False
                    break
check('engine determinism sample (5 bouts)', det_ok and p.returncode == 0)

# 5. roster
roster = json.load(open(os.path.join(DATA, 'contenders.json')))
check('roster complete', len(roster) == man['contenders']['total'] == 383,
      '%d contenders' % len(roster))
check('roster versioned', all(c.get('version') == '1' for c in roster))

# 6. data size guard
size = sum(os.path.getsize(p) for p in
           glob.glob(os.path.join(DATA, '**'), recursive=True)
           if os.path.isfile(p))
check('data dir under 800MB guard', size < 800 * 1024 * 1024,
      '%.1f MB' % (size / 1024 / 1024))

# 7. required site files
for rel in ['index.html', 'api.json', 'llms.txt', 'ai-manifest.json',
            'data/manifest.json', 'sitemap.xml', 'robots.txt',
            'schemas/battle.schema.json']:
    check('file present: ' + rel, os.path.exists(os.path.join(ROOT, rel)))

health = {
    'site': 'AI Olypics',
    'checked_at': now.isoformat(timespec='seconds'),
    'overall': 'HEALTHY' if all(c['ok'] for c in checks) else 'ATTENTION',
    'bouts': man['bouts'],
    'contenders': man['contenders']['total'],
    'checks': checks,
}
with open(os.path.join(ROOT, 'health.json'), 'w') as f:
    json.dump(health, f, indent=1)

rows_html = '\n'.join(
    '<tr><td>%s</td><td class="%s">%s</td><td>%s</td></tr>' % (
        c['name'], 'ok' if c['ok'] else 'bad', 'PASS' if c['ok'] else 'FAIL',
        c['detail']) for c in checks)
html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Olypics — Archive Health</title>
<style>body{{background:#0a0a12;color:#e8e8f0;font-family:system-ui,sans-serif;max-width:900px;margin:0 auto;padding:24px}}
h1{{color:#ffd700}}a{{color:#7fd4ff}}.ok{{color:#4ade80;font-weight:700}}.bad{{color:#f87171;font-weight:700}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}td,th{{border:1px solid #333;padding:8px;text-align:left}}
.banner{{padding:12px;border:2px solid #ffd700;border-radius:8px;margin:16px 0}}</style></head>
<body>
<h1>🏟️ AI Olypics — Archive Health</h1>
<div class="banner">Status: <strong class="{cls}">{overall}</strong> · checked {at} ·
{bouts:,} archived bouts · {cont} contenders · <a href="index.html">back to the dome</a></div>
<table><tr><th>Check</th><th>Result</th><th>Detail</th></tr>
{rows}
</table>
<p>Machine-readable: <a href="health.json">health.json</a> · counts source: <a href="data/manifest.json">data/manifest.json</a></p>
</body></html>""".format(cls='ok' if health['overall'] == 'HEALTHY' else 'bad',
                         overall=health['overall'], at=health['checked_at'],
                         bouts=man['bouts'], cont=man['contenders']['total'],
                         rows=rows_html)
with open(os.path.join(ROOT, 'health.html'), 'w') as f:
    f.write(html)
n_bad = sum(1 for c in checks if not c['ok'])
print('health: %s (%d/%d checks pass)' % (health['overall'], len(checks) - n_bad, len(checks)))
