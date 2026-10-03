/* AI Olypics — "Add Your AI" (user-entered contenders).
 *
 * Fully client-side: the user defines their own contender (name, description,
 * traits/abilities, persona notes, stat sliders). It gets a local
 * JAH-OLY-USER-#### ID and can battle ALL 383 roster contenders (or a chosen
 * subset) to stress-test their model.
 *
 * Battles run the real deterministic engine as EXHIBITIONS via the explicit
 * contender-pair path: seed = fnv1a(userAI.id + ':' + opponent.id), so every
 * pairing reproduces forever. User-AI bouts are labeled USER-ENTERED, stored
 * only in this browser (localStorage), exportable — and NEVER merged into the
 * official archived battle records.
 */
(function () {
'use strict';

var LS_AIS = 'jah-oly-user-ais-v1';
var LS_BOUTS = 'jah-oly-user-bouts-v1';
var LS_SEQ = 'jah-oly-user-seq-v1';
var STAT_KEYS = ['power', 'speed', 'wit', 'precision', 'creativity', 'stamina'];

function lsGet(k, d) { try { var v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

function eng() { return window.OlyEngine; }
function getRoster() { return window.roster || []; }

/* ---------- roster of user AIs ---------- */
function listAIs() { return lsGet(LS_AIS, []); }
function getAI(id) {
  var list = listAIs();
  for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
  return null;
}
function nextId() {
  var n = (lsGet(LS_SEQ, 0) || 0) + 1;
  lsSet(LS_SEQ, n);
  return 'JAH-OLY-USER-' + String(n).padStart(4, '0');
}
function peekNextId() {
  var n = (lsGet(LS_SEQ, 0) || 0) + 1;
  return 'JAH-OLY-USER-' + String(n).padStart(4, '0');
}
/* Base stats are derived deterministically from the AI's ID with the same
 * fnv1a -> 40..100 math the dome uses for every contender, so they're
 * stable and reproducible. The user may then tune them with sliders. */
function deriveStats(id) { return eng().statsFor(id); }

function addAI(o) {
  o = o || {};
  var id = nextId();
  var ai = {
    id: id,
    name: String(o.name || 'Unnamed AI').slice(0, 60),
    blurb: String(o.blurb || '').slice(0, 500),
    traits: (o.traits || []).map(function (t) { return String(t).slice(0, 60); }).slice(0, 12),
    persona: String(o.persona || '').slice(0, 500),
    stats: {},
    type: 'user',
    version: '1',
    source: 'user-entered',
    created: new Date().toISOString()
  };
  var base = deriveStats(id);
  STAT_KEYS.forEach(function (k) {
    var v = o.stats && +o.stats[k];
    ai.stats[k] = (v >= 40 && v <= 100) ? Math.round(v) : base[k];
  });
  var list = listAIs();
  list.push(ai);
  lsSet(LS_AIS, list);
  return ai;
}
function deleteAI(id) {
  lsSet(LS_AIS, listAIs().filter(function (a) { return a.id !== id; }));
  var bouts = lsGet(LS_BOUTS, {});
  delete bouts[id];
  lsSet(LS_BOUTS, bouts);
}

/* ---------- battling ---------- */
function exhIdFor(seed) { return 'JAH-OLY-EXH-' + String(seed % 100000).padStart(5, '0'); }

/* One deterministic exhibition: user AI (first-listed) vs one opponent. */
function boutVs(ai, opp) {
  var E = eng();
  var seed = (E.fnv1a(ai.id + ':' + opp.id)) >>> 0;
  var b = E.bout(0, getRoster(), {
    id: exhIdFor(seed), exhibition: true, seed: seed, pair: [ai, opp]
  });
  b.exhibition = true;
  b.user_entered = true;
  b.user_ai_id = ai.id;
  b.totals = {};
  b.totals[b.contenders[0].id] = b.rounds.reduce(function (s, rd) { return s + rd.moves[0].total; }, 0);
  b.totals[b.contenders[1].id] = b.rounds.reduce(function (s, rd) { return s + rd.moves[1].total; }, 0);
  return b;
}

/* Regenerate a stored pairing on demand (nothing but the summary is kept). */
function getBout(aiId, oppId) {
  var ai = getAI(aiId);
  if (!ai) return null;
  var opp = null;
  getRoster().forEach(function (c) { if (c.id === oppId) opp = c; });
  if (!opp) return null;
  return boutVs(ai, opp);
}

/* Battle vs ALL roster contenders (or a subset of IDs). Stores summaries. */
function battleAll(aiId, subsetIds, onProgress) {
  var ai = getAI(aiId);
  if (!ai) return null;
  var opps = getRoster().filter(function (c) {
    return c.id !== ai.id && (!subsetIds || subsetIds.indexOf(c.id) >= 0);
  });
  var results = [];
  for (var i = 0; i < opps.length; i++) {
    var b = boutVs(ai, opps[i]);
    results.push({
      opp: opps[i].id, oppName: opps[i].name, oppType: opps[i].type,
      winner: b.winner.id, margin: b.margin, seed: b.seed, exh: b.id
    });
    if (onProgress && i % 25 === 0) onProgress(i + 1, opps.length);
  }
  if (onProgress) onProgress(opps.length, opps.length);
  var store = lsGet(LS_BOUTS, {});
  store[aiId] = { run_at: new Date().toISOString(), ai_name: ai.name, results: results };
  lsSet(LS_BOUTS, store);
  return store[aiId];
}
function getRun(aiId) { return lsGet(LS_BOUTS, {})[aiId] || null; }

/* Store a completed run (used by the chunked UI runner). */
function saveRun(aiId, results) {
  var ai = getAI(aiId);
  var store = lsGet(LS_BOUTS, {});
  store[aiId] = { run_at: new Date().toISOString(), ai_name: ai ? ai.name : aiId, results: results };
  lsSet(LS_BOUTS, store);
  return store[aiId];
}

/* ---------- scorecard: wins/draws/losses by contender category ---------- */
var TYPE_ORDER = ['system', 'persona', 'domain', 'hybrid', 'replica'];
function scorecard(aiId) {
  var run = getRun(aiId);
  var byType = {}, total = { w: 0, d: 0, l: 0 };
  TYPE_ORDER.forEach(function (t) { byType[t] = { w: 0, d: 0, l: 0, n: 0 }; });
  if (run) run.results.forEach(function (r) {
    var cell = byType[r.oppType] || (byType[r.oppType] = { w: 0, d: 0, l: 0, n: 0 });
    cell.n++;
    if (r.winner === aiId) { cell.w++; total.w++; }
    else { cell.l++; total.l++; } /* dome tie rule: exact ties go first-listed, so a winner always emerges */
  });
  return { byType: byType, total: total, run_at: run ? run.run_at : null, n: run ? run.results.length : 0 };
}

/* ---------- export ---------- */
function exportData(aiId) {
  var data = {
    exported_at: new Date().toISOString(),
    note: 'USER-ENTERED exhibitions only. Never part of the official AI Olypics archive.',
    ais: aiId ? [getAI(aiId)] : listAIs(),
    bouts: {}
  };
  var store = lsGet(LS_BOUTS, {});
  (aiId ? [aiId] : Object.keys(store)).forEach(function (id) {
    if (store[id]) data.bouts[id] = store[id];
  });
  return data;
}

window.UserAI = {
  listAIs: listAIs, getAI: getAI, addAI: addAI, deleteAI: deleteAI,
  deriveStats: deriveStats, peekNextId: peekNextId,
  boutVs: boutVs, getBout: getBout, battleAll: battleAll, getRun: getRun,
  saveRun: saveRun,
  scorecard: scorecard, exportData: exportData,
  TYPE_ORDER: TYPE_ORDER, STAT_KEYS: STAT_KEYS
};
})();
