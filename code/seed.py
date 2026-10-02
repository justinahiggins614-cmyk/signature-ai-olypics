#!/usr/bin/env python3
"""Seed bouts: node code/engine.js -> JSONL, packed 100/chunk into
data/chunks/bouts-cNNNNN.jsonl.gz. Rebuilds data/index.json.gz (compact rows)
and data/state.json. Usage: seed.py --n 2000 [--start 1]"""
import json, os, sys, gzip, subprocess, argparse

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

roster = json.load(open(os.path.join(DATA, 'contenders.json')))
state_p = os.path.join(DATA, 'state.json')
state = json.load(open(state_p)) if os.path.exists(state_p) else {'next_index': 1, 'next_inv': 1}
start = args.start or state['next_index']
n = args.n

js = f"""
const E = require({json.dumps(os.path.join(HERE, 'engine.js'))});
const roster = require({json.dumps(os.path.join(DATA, 'contenders.json'))});
let out = [];
for (let i = 0; i < {n}; i++) {{
  const b = E.bout({start} + i, roster);
  b.totals[b.contenders[0].id] = b.rounds.reduce((s,rd)=>s+rd.moves[0].total,0);
  b.totals[b.contenders[1].id] = b.rounds.reduce((s,rd)=>s+rd.moves[1].total,0);
  out.push(JSON.stringify(b));
}}
process.stdout.write(out.join('\\n'));
"""
p = subprocess.run(['node', '-e', js], capture_output=True, text=True)
if p.returncode != 0:
    print("NODE ERROR:", p.stderr[:2000]); sys.exit(1)
lines = [l for l in p.stdout.split('\n') if l.strip()]
assert len(lines) == n, f"expected {n} bouts, got {len(lines)}"

# pack into chunks of per_chunk
idx_rows = []
chunk_no = (start - 1) // args.per_chunk + 1
buf = []
def flush():
    global chunk_no
    if not buf: return
    cp = os.path.join(CHUNKS, f'bouts-c{chunk_no:05d}.jsonl.gz')
    with gzip.open(cp, 'wt') as f:
        f.write('\n'.join(buf) + '\n')
    chunk_no += 1
    buf.clear()

for i, line in enumerate(lines):
    b = json.loads(line)
    idx_rows.append([b['id'], b['winner']['id'], b['winner']['name'],
                     b['contenders'][0]['id'], b['contenders'][1]['id'],
                     b['stage']['key'], b['mission'][:60]])
    buf.append(line)
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
man = {'bouts': len(all_rows), 'goal': 1000000, 'chunks': chunk_no - 1,
       'per_chunk': args.per_chunk, 'updated': '2026-10-02'}
json.dump(man, open(os.path.join(DATA, 'manifest.json'), 'w'), indent=1)
print(f"seeded {n} bouts ({start}..{start+n-1}); total {len(all_rows)}; chunks {chunk_no-1}")
