#!/usr/bin/env python3
"""Seed bouts: node code/engine.js -> JSONL, packed 100/chunk into
data/chunks/bouts-cNNNNN.jsonl.gz. Rebuilds data/index.json.gz (compact rows)
and data/state.json. New bouts carry the full JAH-OLY-RECORD/2.0 envelope
(engine_version "2", created timestamp, SHA-256 content_hash).

Pre-flight: runs node code/qa_engine.js — aborts if the engine fails its
permanent determinism/hash test vectors.

Usage: seed.py --n 2000 [--start 1]
"""
import json, os, sys, gzip, subprocess, argparse, hashlib
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
CHUNKS = os.path.join(DATA, 'chunks')
os.makedirs(CHUNKS, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument('--n', type=int, default=2000)
ap.add_argument('--start', type=int, default=None)
ap.add_argument('--per-chunk', type=int, default=100)
args = ap.parse_args()

# --- pre-flight: engine determinism + hash vectors must pass ---
qa = subprocess.run(['node', os.path.join(HERE, 'qa_engine.js')],
                    capture_output=True, text=True)
print(qa.stdout.strip().split('\n')[-1] if qa.stdout.strip() else '(qa silent)')
if qa.returncode != 0:
    print("QA ENGINE FAILED — aborting seed:\n" + qa.stderr[:2000])
    sys.exit(1)

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')

def content_hash(rec):
    r = {k: v for k, v in rec.items() if k != 'content_hash'}
    return 'sha256:' + hashlib.sha256(canon(r)).hexdigest()

roster = json.load(open(os.path.join(DATA, 'contenders.json')))
state_p = os.path.join(DATA, 'state.json')
state = json.load(open(state_p)) if os.path.exists(state_p) else {'next_index': 1, 'next_inv': 1}
start = args.start or state['next_index']
n = args.n
now = datetime.datetime.now(datetime.timezone.utc)
created = now.isoformat(timespec='seconds')

js = f"""
const E = require({json.dumps(os.path.join(HERE, 'engine.js'))});
const roster = require({json.dumps(os.path.join(DATA, 'contenders.json'))});
let out = [];
for (let i = 0; i < {n}; i++) {{
  const b = E.bout({start} + i, roster);
  b.totals[b.contenders[0].id] = b.rounds.reduce((s,rd)=>s+rd.moves[0].total,0);
  b.totals[b.contenders[1].id] = b.rounds.reduce((s,rd)=>s+rd.moves[1].total,0);
  b.created = {json.dumps(created)};
  out.push(JSON.stringify(b));
}}
process.stdout.write(out.join('\\n'));
"""
p = subprocess.run(['node', '-e', js], capture_output=True, text=True)
if p.returncode != 0:
    print("NODE ERROR:", p.stderr[:2000]); sys.exit(1)
lines = [l for l in p.stdout.split('\n') if l.strip()]
assert len(lines) == n, f"expected {n} bouts, got {len(lines)}"

# envelope completion: content_hash over the final record
idx_rows = []
chunk_no = (start - 1) // args.per_chunk + 1
buf = []
def flush():
    global chunk_no
    if not buf: return
    cp = os.path.join(CHUNKS, f'bouts-c{chunk_no:05d}.jsonl.gz')
    with gzip.open(cp, 'wt', encoding='utf-8') as f:
        f.write('\n'.join(buf) + '\n')
    chunk_no += 1
    buf.clear()

for i, line in enumerate(lines):
    b = json.loads(line)
    assert b['engine_version'] == '2.0' and b['status'] == 'ARCHIVED', b['id']
    b['content_hash'] = content_hash(b)
    idx_rows.append([b['id'], b['winner']['id'], b['winner']['name'],
                     b['contenders'][0]['id'], b['contenders'][1]['id'],
                     b['stage']['key'], b['mission'][:60]])
    buf.append(json.dumps(b, ensure_ascii=False))
    if len(buf) >= args.per_chunk:
        flush()
flush()

# merge into master index
idx_p = os.path.join(DATA, 'index.json.gz')
existing = []
if os.path.exists(idx_p):
    with gzip.open(idx_p, 'rt') as f:
        existing = [json.loads(l) for l in f if l.strip()]
all_rows = existing + idx_rows
# dedupe by id (re-runs are idempotent)
seen = {}
for row in all_rows:
    seen[row[0]] = row
all_rows = [seen[k] for k in sorted(seen)]
with gzip.open(idx_p, 'wt') as f:
    for row in all_rows:
        f.write(json.dumps(row) + '\n')

state['next_index'] = start + n
json.dump(state, open(state_p, 'w'), indent=1)

# --- authoritative manifest v2 (ONE count source) ---
from build_manifest import build_manifest
man = build_manifest()
today = man['updated']
by_type = man['contenders']['by_type']

# --- api.json: keep keys, refresh counts/versions/date ---
api_p = os.path.join(ROOT, 'api.json')
api = json.load(open(api_p)) if os.path.exists(api_p) else {}
api.update({
    'bouts': len(all_rows),
    'contenders': len(roster),
    'contender_breakdown': by_type,
    'engine_version': '2.0',
    'schema_version': 'JAH-OLY-RECORD/2.0',
    'manifest': 'data/manifest.json',
    'updated': today,
})
json.dump(api, open(api_p, 'w'), indent=1)
print(f"seeded {n} bouts ({start}..{start+n-1}); total {len(all_rows)}; chunks {chunk_no-1}")
