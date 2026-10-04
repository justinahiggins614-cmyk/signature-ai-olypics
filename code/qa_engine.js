#!/usr/bin/env node
/* AI Olympics engine QA: permanent determinism + record-hash test vectors.
 * - Archived vectors (n numeric): the v2 engine must reproduce the archived
 *   bout's winner/margin/seed, and the JS canonical-JSON implementation must
 *   reproduce the archived content_hash byte-for-byte (cross-checks the
 *   Python hashing used by code/migrate_v2.py and code/seed.py).
 * - Exhibition / user-AI vectors: the stated code path must reproduce the
 *   recorded winner/margin exactly.
 * Exit 0 = PASS, non-zero = FAIL. Runs inside the bout drip (seed.py) and CI.
 */
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const crypto = require('crypto');
const ROOT = path.join(__dirname, '..');
const E = require('./engine.js');
const roster = require(path.join(ROOT, 'data', 'contenders.json'));
const VECS = JSON.parse(fs.readFileSync(path.join(__dirname, 'test_vectors.json'), 'utf8'));

/* Canonical JSON — MUST match Python:
 * json.dumps(o, sort_keys=True, separators=(',',':'), ensure_ascii=False) */
function canonJSON(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(canonJSON).join(',') + ']';
  return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + canonJSON(v[k])).join(',') + '}';
}
function contentHash(rec) {
  const r = {};
  for (const k of Object.keys(rec)) if (k !== 'content_hash') r[k] = rec[k];
  return 'sha256:' + crypto.createHash('sha256').update(canonJSON(r), 'utf8').digest('hex');
}

function findArchived(id) {
  const dir = path.join(ROOT, 'data', 'chunks');
  for (const f of fs.readdirSync(dir).sort()) {
    if (!f.endsWith('.jsonl.gz')) continue;
    const lines = zlib.gunzipSync(fs.readFileSync(path.join(dir, f))).toString('utf8').split('\n');
    for (const line of lines) {
      if (!line.trim()) continue;
      const b = JSON.parse(line);
      if (b.id === id) return b;
    }
  }
  return null;
}

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; }
  else { fail++; console.error('FAIL: ' + name + (extra ? ' — ' + extra : '')); }
}

for (const v of VECS) {
  if (typeof v.n === 'number') {
    const f = E.bout(v.n, roster);
    check(v.id + ' winner', f.winner.id === v.winner, f.winner.id + ' vs ' + v.winner);
    check(v.id + ' margin', f.margin === v.margin, f.margin + ' vs ' + v.margin);
    check(v.id + ' seed', f.seed === v.seed, f.seed + ' vs ' + v.seed);
    const arch = findArchived(v.id);
    check(v.id + ' archived record present', !!arch);
    if (arch) {
      check(v.id + ' content_hash (JS canon == archived)', contentHash(arch) === v.content_hash,
        contentHash(arch) + ' vs ' + v.content_hash);
      check(v.id + ' stage_id', arch.stage_id === arch.stage.id);
      check(v.id + ' criteria_id', arch.criteria_id === arch.criteria.id);
      check(v.id + ' mission_id format', /^JAH-OLY-MIS-\d{2}$/.test(arch.mission_id));
      check(v.id + ' contender version', arch.contenders.every((c) => c.version === '1'));
    }
  } else if (v.n === 'exhibition-fixed-seed') {
    const b = E.bout(0, roster, { id: v.id, exhibition: true, seed: v.seed });
    check(v.id + ' exhibition winner', b.winner.id === v.winner);
    check(v.id + ' exhibition margin', b.margin === v.margin);
    check(v.id + ' exhibition status', b.status === 'EXHIBITION');
  } else if (v.n === 'user-ai-pair') {
    const userAI = { id: 'JAH-OLY-USER-0001', name: 'Test Forge', type: 'user', blurb: 'QA fixture', version: '1', source: 'user-entered',
      stats: { power: 77, speed: 66, wit: 88, precision: 70, creativity: 91, stamina: 60 } };
    const seed = E.fnv1a('JAH-OLY-USER-0001:JAH-AI-SYS-001') >>> 0;
    check(v.id + ' pair seed', seed === v.seed);
    const b = E.bout(0, roster, { id: v.id, exhibition: true, seed: seed, pair: [userAI, roster[0]] });
    check(v.id + ' pair winner', b.winner.id === v.winner);
    check(v.id + ' pair margin', b.margin === v.margin);
    check(v.id + ' pair custom stats used', b.contenders[0].stats.power === 77);
    const b2 = E.bout(0, roster, { id: v.id, exhibition: true, seed: seed, pair: [userAI, roster[0]] });
    check(v.id + ' pair deterministic', JSON.stringify(b) === JSON.stringify(b2));
  }
}

// structural invariants
check('rubric weights sum to 1.0',
  E.CRITERIA.every((c) => Math.abs(c.dims.reduce((s, d) => s + d[1], 0) - 1.0) < 1e-12));
check('12 stages versioned', E.STAGES.length === 12 && E.STAGES.every((s) => s.version === '1' && /^JAH-OLY-STAGE-\d{2}$/.test(s.id)));
check('6 criteria versioned', E.CRITERIA.length === 6 && E.CRITERIA.every((c) => c.version === '1' && /^JAH-OLY-CRIT-\d{2}$/.test(c.id)));
check('30 missions', E.MISSIONS.length === 30);
check('engine version', E.ENGINE_VERSION === '2.1');
check('8 events versioned', E.EVENTS.length === 8 && E.EVENTS.every((e) => e.version === '1' && /^JAH-OLY-EVENT-\d{2}$/.test(e.id)));
check('event arenas + rubrics resolve', E.EVENTS.every((e) =>
  E.STAGES.some((s) => s.key === e.arenaKey) && E.CRITERIA.some((c) => c.key === e.criteriaKey)));
/* v2.1 event-bout vectors: deterministic, carry the event, default path untouched */
(function () {
  const p = [roster[0], roster[1]];
  const e1 = E.bout(0, roster, { id: 'JAH-OLY-EVT-QA1', seed: 424242, event: 'wrestling', pair: p });
  const e2 = E.bout(0, roster, { id: 'JAH-OLY-EVT-QA1', seed: 424242, event: 'wrestling', pair: p });
  check('event bout deterministic', JSON.stringify(e1) === JSON.stringify(e2));
  check('event bout carries event', e1.event_id === 'JAH-OLY-EVENT-01' && e1.event.key === 'wrestling');
  check('event fixes rubric+arena', e1.criteria_id === 'JAH-OLY-CRIT-06' && e1.stage.key === 'pit');
  const d1 = E.bout(777, roster), d2 = E.bout(777, roster);
  check('default path unchanged by events', d1.event_id === null && JSON.stringify(d1) === JSON.stringify(d2));
  const ei = E.bout(0, roster, { id: 'JAH-OLY-EVT-QA2', seed: 424242, event: 2, pair: p });
  check('event index selects sprint', ei.event_id === 'JAH-OLY-EVENT-03' && ei.criteria.key === 'sprinter');
})();

console.log('qa_engine: ' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
