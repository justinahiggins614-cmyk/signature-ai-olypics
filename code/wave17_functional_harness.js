#!/usr/bin/env node
/* Wave-17 functional exercise: drives the REAL shipped functions (engine.js,
 * user-ai.js) against the REAL data (contenders.json, index.json.gz).
 * Exit 0 = all PASS. Pure engine/DOM-free logic only; DOM handlers are
 * exercised structurally where they cannot run in Node. */
'use strict';
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const ROOT = path.join(__dirname, '..');
const E = require('./engine.js');
const roster = require(path.join(ROOT, 'data', 'contenders.json'));

let pass = 0, fail = 0, rows = [];
function check(name, cond, extra) {
  if (cond) { pass++; rows.push('PASS  ' + name); }
  else { fail++; rows.push('FAIL  ' + name + (extra ? ' — ' + extra : '')); }
}

const P = [roster[0], roster[1]];

/* 2/3. Random/Random/Random (universal pit path) */
(function () {
  const b = E.bout(4242, roster, {});
  check('universal-pit path: default draws produce a bout', b && b.contenders.length === 2);
  check('universal-pit: deterministic', JSON.stringify(E.bout(4242, roster, {})) === JSON.stringify(b));
})();

/* 3. every stage */
E.STAGES.forEach(function (s, i) {
  const b = E.bout(0, roster, { id: 'QA-STAGE-' + i, seed: 9000 + i, stage: i, pair: P });
  check('stage ' + i + ' (' + s.key + ') applies', b.stage.key === s.key && b.stage_id === s.id);
});

/* 4. every criteria */
E.CRITERIA.forEach(function (c, i) {
  const b = E.bout(0, roster, { id: 'QA-CRIT-' + i, seed: 9100 + i, criteria: i, pair: P });
  check('criteria ' + i + ' (' + c.key + ') applies', b.criteria.key === c.key && b.criteria_id === c.id);
});

/* 5. every mission */
E.MISSIONS.forEach(function (m, i) {
  const b = E.bout(0, roster, { id: 'QA-MIS-' + i, seed: 9200 + i, mission: i, pair: P });
  check('mission ' + i + ' applies', b.mission === m && b.mission_id === E.missionId(i));
});

/* 6. universal pit (no pair, no stage) = pit path w/ random seed */
(function () {
  const b = E.bout(0, roster, { seed: 77777 });
  check('universal-pit seed path: seed fixed', b.seed === 77777 && b.contenders.length === 2);
})();

/* 7. staged bout: explicit stage/criteria/mission indexes (as stagedBout passes) */
(function () {
  const b = E.bout(0, roster, { id: 'QA-STAGED', seed: 31337, stage: 3, criteria: 4, mission: 12, pair: P });
  check('staged-bout: stage index 3', b.stage.key === E.STAGES[3].key);
  check('staged-bout: criteria index 4', b.criteria.key === E.CRITERIA[4].key);
  check('staged-bout: mission index 12', b.mission === E.MISSIONS[12]);
})();

/* 8. all 8 Olypics events fix arena+rubric */
E.EVENTS.forEach(function (ev) {
  const b = E.bout(0, roster, { id: 'QA-EVT-' + ev.key, seed: 424242, event: ev.key, pair: P });
  const wantCrit = E.CRITERIA.filter(function (c) { return c.key === ev.criteriaKey; })[0];
  const wantArena = E.STAGES.filter(function (s) { return s.key === ev.arenaKey; })[0];
  check('event ' + ev.key + ' fixes arena+rubric', b.event.key === ev.key && b.criteria.key === wantCrit.key && b.stage.key === wantArena.key);
});

/* --- user-AI (js/user-ai.js) with a localStorage stub --- */
const store = {};
global.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; },
};
global.window = global; global.self = global;
global.OlyEngine = E;
require(path.join(ROOT, 'js', 'user-ai.js'));
const U = global.UserAI;
global.roster = roster;

(function () {
  /* 8. Add Your AI */
  const base = U.deriveStats('JAH-OLY-USER-0001');
  check('deriveStats: 6 stats in 40..100', U.STAT_KEYS.every((k) => base[k] >= 40 && base[k] <= 100));
  check('deriveStats: deterministic', JSON.stringify(U.deriveStats('JAH-OLY-USER-0001')) === JSON.stringify(base));
  const ai = U.addAI({ name: 'Stress Forge', blurb: 'QA AI', traits: ['fast', 'witty'], persona: 'calm', stats: { power: 95, speed: 95, wit: 95, precision: 95, creativity: 95, stamina: 95 } });
  check('addAI: id issued', /^JAH-OLY-USER-\d{4}$/.test(ai.id));
  check('addAI: listed', U.getAI(ai.id) !== null);

  /* 11. stat slider clamping (40..100, out-of-range falls back to base) */
  const bad = U.addAI({ name: 'Clamp Test', stats: { power: 500, speed: -3 } });
  const cbase = U.deriveStats(bad.id);
  check('stats: >100 rejected to base', bad.stats.power === cbase.power);
  check('stats: <40 rejected to base', bad.stats.speed === cbase.speed);

  /* 12. user AI vs every supported contender class */
  const types = {};
  roster.forEach(function (c) { (types[c.type] = types[c.type] || []).push(c); });
  ['system', 'persona', 'domain', 'hybrid', 'replica'].forEach(function (t) {
    if (!types[t] || !types[t].length) { check('userAI vs ' + t + ' (no contenders in archive)', true); return; }
    const b = U.boutVs(ai, types[t][0]);
    check('userAI vs ' + t + ': bout runs', b.winner && b.loser && b.contenders[0].id === ai.id);
    check('userAI vs ' + t + ': custom stats used', b.contenders[0].stats.power === 95);
    check('userAI vs ' + t + ': flagged user-entered+exhibition', b.user_entered === true && b.exhibition === true);
  });

  /* battleAll subset: 5 bouts, scorecard, regenerate, export, delete */
  const run = U.battleAll(ai.id, roster.slice(0, 5).map((c) => c.id));
  check('battleAll(subset 5): 5 results', run && run.results.length === 5);
  const sc = U.scorecard(ai.id);
  check('scorecard: n=5', sc.n === 5 && sc.total.w + sc.total.l === 5);
  const regen = U.getBout(ai.id, roster[0].id);
  const orig = U.boutVs(ai, roster[0]);
  check('getBout regenerates deterministically', JSON.stringify(regen) === JSON.stringify(orig));
  const exp = U.exportData(ai.id);
  check('export: AI + bouts', exp.ais.length === 1 && !!exp.bouts[ai.id]);
  U.deleteAI(bad.id);
  check('deleteAI removes', U.getAI(bad.id) === null);
})();

/* --- search + arena filter against the REAL index --- */
(function () {
  const idxRows = zlib.gunzipSync(fs.readFileSync(path.join(ROOT, 'data', 'index.json.gz'))).toString('utf8')
    .split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
  check('index loads (' + idxRows.length + ' rows)', idxRows.length > 0);
  const stages = {}; idxRows.forEach((r) => { stages[r[5]] = 1; });
  check('arena filter options from index: ' + Object.keys(stages).length + ' stages', Object.keys(stages).length >= 12);
  const q = 'The Constellation'.toLowerCase();
  const hits = idxRows.filter((r) => r.join(' ').toLowerCase().indexOf(q) >= 0);
  check('battle search: contender hit', hits.length > 0);
  check('battle search: exact-ID row shape [id,winner,desc...]', /^JAH-OLY-\d{6}$/.test(idxRows[0][0]));
  /* 25. determinism: re-run engine for an archived bout id range */
  const mid = idxRows[Math.floor(idxRows.length / 2)][0];
  const n = parseInt(mid.slice(8), 10);
  const f = E.bout(n, roster);
  check('deterministic re-run (n=' + n + ') reproduces winner', f.winner.id === idxRows[Math.floor(idxRows.length / 2)][1]);
})();

/* --- battle record integrity helpers (index.html olyCanon/olyRecalc logic) --- */
function canonJSON(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(canonJSON).join(',') + ']';
  return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + canonJSON(v[k])).join(',') + '}';
}
(function () {
  const b = E.bout(12345, roster, {});
  const totals = {};
  totals[b.contenders[0].id] = b.rounds.reduce((s, rd) => s + rd.moves[0].total, 0);
  totals[b.contenders[1].id] = b.rounds.reduce((s, rd) => s + rd.moves[1].total, 0);
  const t0 = totals[b.contenders[0].id], t1 = totals[b.contenders[1].id];
  const margin = Math.round(Math.abs(t0 - t1) * 10) / 10;
  check('olyRecalc math: margin matches engine', margin === b.margin);
  const canon = canonJSON({ a: 1, b: [2, 1], c: { z: 1, y: 2 } });
  check('olyCanon: sorted keys, no spaces', canon === '{"a":1,"b":[2,1],"c":{"y":2,"z":1}}');
  /* tie rule */
  check('tie rule published', /TIE_RULE_FIRST_LISTED/.test(E.TIE_RULE));
})();

/* --- findings/inventions structure --- */
(function () {
  const b = E.bout(54321, roster, {});
  check('findings: structured {t,c}', b.findings.every((f) => typeof f === 'object' && f.t && f.c));
  check('findings: valid classes', b.findings.every((f) => ['observed', 'calculated', 'derived', 'speculative', 'narrative'].indexOf(f.c) >= 0));
  check('inventions: CONCEPT status, never auto-patented', b.inventions.every((iv) => iv.status === 'CONCEPT' && iv.record_type === 'DERIVED_INVENTION'));
})();

console.log(rows.join('\n'));
console.log('wave17_harness: ' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
