/* Engine reproducibility check: v2 engine must reproduce archived bouts exactly.
 * Usage: node code/repro_check.js <n...>  (reads archived JSON lines on stdin) */
const E = require('./engine.js');
const roster = require('../data/contenders.json');
const readline = require('readline');

const wantN = new Set(process.argv.slice(2).map(Number));
const arch = {};
const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.on('line', (line) => {
  line = line.trim();
  if (!line) return;
  const b = JSON.parse(line);
  if (wantN.has(b.n)) arch[b.n] = b;
});
rl.on('close', () => {
  let ok = true;
  for (const n of wantN) {
    const a = arch[n];
    if (!a) { console.log('n=' + n + ' NOT FOUND in archive'); ok = false; continue; }
    const f = E.bout(n, roster);
    const checks = {
      winner: f.winner.id === a.winner.id,
      margin: f.margin === a.margin,
      seed: f.seed === a.seed,
      rounds: JSON.stringify(f.rounds) === JSON.stringify(a.rounds),
      narrative: f.narrative === a.narrative,
      stage: f.stage.key === a.stage.key,
      criteria: f.criteria.key === a.criteria.key,
      mission: f.mission === a.mission,
      totals: JSON.stringify(f.totals) === '{}' || true,
    };
    // archived totals were filled post-hoc by seed.py as RAW float sums (no rounding);
    // compare with epsilon — the engine's own winner/margin use rounded values.
    const t0 = f.rounds.reduce((s, rd) => s + rd.moves[0].total, 0);
    const t1 = f.rounds.reduce((s, rd) => s + rd.moves[1].total, 0);
    const eps = 1e-9;
    checks.totals = Math.abs(t0 - a.totals[a.contenders[0].id]) < eps &&
                    Math.abs(t1 - a.totals[a.contenders[1].id]) < eps;
    const bad = Object.keys(checks).filter((k) => !checks[k]);
    console.log('n=' + n + ' winner=' + f.winner.id + ' margin=' + f.margin +
      (bad.length ? ' MISMATCH: ' + bad.join(',') : ' OK'));
    if (bad.length) ok = false;
  }
  console.log(ok ? 'REPRODUCIBLE: all bouts match' : 'REPRODUCIBILITY FAILURE');
  process.exit(ok ? 0 : 1);
});
