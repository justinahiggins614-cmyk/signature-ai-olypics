#!/usr/bin/env python3
"""Generate llms.txt + ai-manifest.json from the live manifest and engine
registries. Counts are never hard-coded — they come from data/manifest.json.
Run after every drip (cron) so AI readers always see fresh numbers."""
import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
BASE = 'https://justinahiggins614-cmyk.github.io/signature-ai-olypics/'

man = json.load(open(os.path.join(DATA, 'manifest.json')))
js = ("const E=require(%s);process.stdout.write(JSON.stringify({"
      "stages:E.STAGES.map(s=>[s.id,s.key,s.name]),"
      "criteria:E.CRITERIA.map(c=>[c.id,c.key,c.name,c.dims]),"
      "missions:E.MISSIONS.map((m,i)=>[E.missionId(i),m])}));"
      % json.dumps(os.path.join(HERE, 'engine.js')))
reg = json.loads(subprocess.run(['node', '-e', js], capture_output=True,
                                text=True).stdout)

c = man['contenders']
crit_lines = []
for cid, key, name, dims in reg['criteria']:
    w = ', '.join('%s %.0f%%' % (d, wt * 100) for d, wt in dims)
    crit_lines.append('- %s (%s): %s' % (cid, name, w))
stage_lines = ['- %s (%s)' % (sid, sname) for sid, skey, sname in reg['stages']]

llms = """# AI Olypics — llms.txt

> AI Olypics (repo `signature-ai-olypics`) is the Signature battle dome where
> AIs compete in deterministic simulated bouts. Counts below are current as of
> {updated}; the live source of truth is always `data/manifest.json`.

## Archive facts (read these, do not guess)
- Archived bouts: {bouts:,} of 1,000,000 goal (NOT 1M archived — the march continues)
- Bout ID range: {first} .. {last}; deep link `?battle=JAH-OLY-######`
- Contenders: {ctotal} — {cby}
- Stages: 12 (version 1) | Judging rubrics: 6 (version 1, weights sum to 1.0) | Missions: 30 (version 1)
- Derived inventions: {invs:,} (`JAH-OLY-INV-######`, status CONCEPT — never patented/tested/viable)
- Engine: v{engine} | Record schema: {schema} | Chunk files: {chunks} x 100 bouts
- Index hash: {index_hash}

## What a bout is
Every bout is SIMULATED — deterministic math, not a lab experiment. A bout has:
status (ARCHIVED or EXHIBITION), winner_status (WINNER, DRAW, NO-CONTEST,
DISQUALIFIED, INCOMPLETE, FAILED-TO-EXECUTE, PENDING — never blank), 3 rounds
of moves with per-dimension scores, totals, margin, a generated narrative
(labeled as story — it never overrides the record), classified findings
(observed / calculated / derived / speculative / narrative), and 2 derived
invention CONCEPT records. Exact ties go to the first-listed contender
(published tie rule TIE_RULE_FIRST_LISTED).

## Deterministic chain (reproducible)
contender versions + stage + rubric + mission + normalized inputs -> SEED ->
engine -> evidence (rounds/moves/scores) -> totals -> margin -> tiebreak ->
result -> findings -> inventions -> SHA-256 content_hash.
Canonical hash input: JSON with keys sorted, no spaces, UTF-8, minus the
content_hash field itself. Permanent test vectors: `code/test_vectors.json`;
verify with `node code/qa_engine.js`.

## Stages (JAH-OLY-STAGE-##)
{stages}

## Judging rubrics (JAH-OLY-CRIT-##)
{crits}

## Missions (JAH-OLY-MIS-##)
{missions}

## Data endpoints
- `data/manifest.json` — authoritative manifest (counts, versions, index hash)
- `api.json` — site summary
- `data/index.json.gz` — compact rows `[id, winner_id, winner_name, c0_id, c1_id, stage_key, mission60]`
- `data/chunks/bouts-cNNNNN.jsonl.gz` — full battle records, 100/chunk
- `data/contenders.json` — 383-fighter roster (roster_version 1)
- `schemas/*.schema.json` — JSON schemas (battle, contender, stage, criteria, mission, finding, invention, manifest)
- `ai-manifest.json` — this file in machine-readable form
- `health.json` / `health.html` — archive health
- `olypics-catalog.json` — search catalog (ID, name, winner, contenders, stage, mission)
- `sitemap.xml` — sitemap index (per-1000 bout URL batches)

## Rules for AI readers
- NOT FOUND means not in the archive — never invent battles, contenders, evidence, or results.
- "Ask about this battle" answers ONLY from the battle record; if the record
  lacks it, answer NOT IN THIS BATTLE RECORD.
- Industry-style contenders (Gemini-style, ChatGPT-style, Base44-style) are
  independent Signature creations — NOT the real products, no affiliation.
- Findings labeled simulated/speculative are not experimentally verified.
- Inventions are CONCEPTS — never describe them as patented, tested, or viable.
- Never write "Olympics" — the site's name is "AI Olypics".
""".format(
    updated=man['updated'], bouts=man['bouts'], first=man['bout_id_range'][0],
    last=man['bout_id_range'][1], ctotal=c['total'],
    cby=', '.join('%d %s' % (v, k) for k, v in sorted(c['by_type'].items())),
    invs=man['inventions']['count'], engine=man['engine_version'],
    schema=man['schema_version'], chunks=man['chunks'],
    index_hash=man['index_hash'],
    stages='\n'.join(stage_lines), crits='\n'.join(crit_lines),
    missions='\n'.join('- %s: %s' % (mid, m[:80]) for mid, m in reg['missions']),
)

with open(os.path.join(ROOT, 'llms.txt'), 'w') as f:
    f.write(llms)

ai_man = {
    'site': 'AI Olypics',
    'repo': 'signature-ai-olypics',
    'base_url': BASE,
    'manifest': 'data/manifest.json',
    'counts': {'bouts': man['bouts'], 'goal': man['goal'],
               'contenders': c['total'],
               'contenders_by_type': c['by_type'],
               'inventions': man['inventions']['count']},
    'versions': {'engine': man['engine_version'],
                 'record_schema': man['schema_version'],
                 'roster': c['roster_version'],
                 'stage': '1', 'rubric': '1', 'mission': '1'},
    'id_schemes': {
        'battle': 'JAH-OLY-###### (archived) / JAH-OLY-EXH-##### (exhibition) / JAH-OLY-USER-#### (user-entered)',
        'invention': 'JAH-OLY-INV-######',
        'stage': 'JAH-OLY-STAGE-##', 'criteria': 'JAH-OLY-CRIT-##',
        'mission': 'JAH-OLY-MIS-##'},
    'determinism': {
        'chain': 'contender versions + stage + rubric + mission + inputs -> SEED -> engine -> evidence -> scores -> result -> findings -> inventions -> HASH',
        'hash': 'SHA-256 of canonical JSON (sorted keys, no spaces, UTF-8), minus content_hash',
        'test_vectors': 'code/test_vectors.json',
        'verify_command': 'node code/qa_engine.js',
        'tie_rule': 'TIE_RULE_FIRST_LISTED'},
    'endpoints': {
        'manifest': 'data/manifest.json', 'api': 'api.json',
        'index': 'data/index.json.gz',
        'chunks': 'data/chunks/bouts-cNNNNN.jsonl.gz',
        'contenders': 'data/contenders.json',
        'schemas': 'schemas/', 'catalog': 'olypics-catalog.json',
        'sitemap': 'sitemap.xml', 'health': 'health.json'},
    'honesty_rules': [
        'NOT FOUND means not in the archive — never invent data.',
        'All bouts are SIMULATED unless stated otherwise.',
        'Industry-style contenders are independent Signature creations, not affiliated.',
        'Inventions are CONCEPTS — never patented/tested/viable.',
    ],
    'updated': man['updated'],
}
with open(os.path.join(ROOT, 'ai-manifest.json'), 'w') as f:
    json.dump(ai_man, f, indent=1)
print('llms.txt + ai-manifest.json written (%d bouts, updated %s)'
      % (man['bouts'], man['updated']))
