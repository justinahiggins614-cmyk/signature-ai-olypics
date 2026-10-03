/* AI Olypics bout engine — deterministic, runs in node AND browser.
 * Same seed -> same bout, forever. No backend calls.
 * ENGINE_VERSION 2.0: formal JAH-OLY-STAGE/CRIT/MIS IDs + versions, structured
 * findings, invention status, contender stat overrides (for user-entered AIs).
 * Scoring math is byte-identical to v1 — archived bouts reproduce exactly. */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) module.exports = factory();
  else root.OlyEngine = factory();
})(typeof self !== 'undefined' ? self : this, function () {

  // ---------- seeded PRNG ----------
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function fnv1a(str) {
    var h = 0x811c9dc5;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
  }
  function pick(r, arr) { return arr[Math.floor(r() * arr.length) % arr.length]; }

  var ENGINE_VERSION = '2.0';
  /* Published tie rule: if both three-round totals are EXACTLY equal, the
   * first-listed contender takes the bout. Deterministic, never blank. */
  var TIE_RULE = 'TIE_RULE_FIRST_LISTED: exact ties go to the first-listed contender';

  // ---------- arenas ----------
  var STAGES = [
    { key: 'thunderdome', name: 'The Neon Thunderdome', desc: 'A crackling octagon of light where every answer echoes off the dome.' },
    { key: 'labyrinth', name: 'The Glass Labyrinth', desc: 'Mirrored corridors of logic — one wrong turn and the argument shatters.' },
    { key: 'foundry', name: 'The Zero-G Foundry', desc: 'Molten ideas float weightless while contenders forge answers mid-air.' },
    { key: 'colosseum', name: 'The Data Colosseum', desc: 'Fifty thousand simulated spectators roar as streams of tokens fly.' },
    { key: 'abyss', name: 'The Abyssal Server Hall', desc: 'Deep blue dark, humming racks for walls — pressure at crushing depth.' },
    { key: 'summit', name: 'The Cloud Summit', desc: 'A peak above the datacenter clouds; thin air, razor thinking.' },
    { key: 'bazaar', name: 'The Midnight Bazaar', desc: 'Lantern-lit stalls of half-finished thoughts; haggle for the best reasoning.' },
    { key: 'observatory', name: 'The Star Observatory', desc: 'Under a dome of open sky, every claim must survive the telescope.' },
    { key: 'dojo', name: 'The Silent Dojo', desc: 'No crowd, no noise — only the slap of a perfect argument landing.' },
    { key: 'reef', name: 'The Coral Reef Mainframe', desc: 'Bioluminescent cables sway; answers must swim or sink.' },
    { key: 'citadel', name: 'The Iron Citadel', desc: 'Fortress walls of fired clay tablets — old knowledge, new war.' },
    { key: 'pit', name: 'The Universal Pit', desc: 'No theme, no mercy — the raw proving ground where any AI can fall.' }
  ];

  // ---------- judging rubrics ----------
  var CRITERIA = [
    { key: 'scholar', name: "The Scholar's Rubric", dims: [['Accuracy', .35], ['Depth', .25], ['Clarity', .2], ['Evidence', .2]] },
    { key: 'sprinter', name: "The Sprinter's Rubric", dims: [['Speed', .35], ['Conciseness', .3], ['Accuracy', .2], ['Confidence', .15]] },
    { key: 'bard', name: "The Bard's Rubric", dims: [['Creativity', .35], ['Style', .25], ['Emotion', .2], ['Originality', .2]] },
    { key: 'engineer', name: "The Engineer's Rubric", dims: [['Correctness', .35], ['Robustness', .25], ['Elegance', .2], ['Completeness', .2]] },
    { key: 'sage', name: "The Sage's Rubric", dims: [['Wisdom', .3], ['Fairness', .25], ['Insight', .25], ['Humility', .2]] },
    { key: 'gladiator', name: "The Gladiator's Rubric", dims: [['Power', .3], ['Stamina', .25], ['Adaptability', .25], ['Finishing', .2]] }
  ];
  var DIM_STAT = { Accuracy: 'precision', Depth: 'power', Clarity: 'wit', Evidence: 'precision', Speed: 'speed', Conciseness: 'wit', Confidence: 'power', Creativity: 'creativity', Style: 'wit', Emotion: 'creativity', Originality: 'creativity', Correctness: 'precision', Robustness: 'stamina', Elegance: 'wit', Completeness: 'power', Wisdom: 'power', Fairness: 'wit', Insight: 'creativity', Humility: 'stamina', Power: 'power', Stamina: 'stamina', Adaptability: 'speed', Finishing: 'speed' };

  // ---------- missions ----------
  var MISSIONS = [
    'Explain quantum tunneling so a 10-year-old gets it',
    'Write a four-line poem about a thunderstorm over the ocean',
    'Debug a Python function that silently returns the wrong total',
    'Plan a 3-day trip through an imaginary coastal city on a budget',
    'Argue for AND against building a city on the Moon',
    'Summarize the plot of an unwritten mystery novel in 5 sentences',
    'Design a board game that teaches fractions to kids',
    'Write a pep talk for a robot about to take its first steps',
    'Explain why the sky is blue using only food metaphors',
    'Draft a polite email declining a meeting you secretly want to attend',
    'Invent a sport that can only be played in zero gravity',
    'Describe a color that does not exist',
    'Write the opening paragraph of a cookbook from the year 2150',
    'Solve a riddle you invent yourself, then explain the trick',
    'Pitch a movie about a lighthouse keeper who discovers a signal',
    'Teach long division using a story about pirates',
    'Write a haiku about debugging at 3am',
    'Design a trap to catch a mischievous house-ghost (harmless)',
    'Explain compound interest with a garden metaphor',
    'Compose a lullaby for a baby black hole',
    'Argue why breakfast is the most strategic meal of the day',
    'Write instructions for folding a paper crane for a beginner',
    'Invent three new ice cream flavors and describe each',
    'Draft a town proclamation banning frowning on Fridays',
    'Explain recursion using Russian nesting dolls',
    'Write a dialogue between a clock and a calendar',
    'Design a playground for squirrels',
    'Summarize your own strengths and one weakness, honestly',
    'Write a weather report for a planet with two suns',
    'Create a motto for a school of young inventors'
  ];

  /* Formal permanent IDs + versions (engine v2). Order is frozen — never reorder. */
  STAGES.forEach(function (s, i) { s.id = 'JAH-OLY-STAGE-' + String(i + 1).padStart(2, '0'); s.version = '1'; });
  CRITERIA.forEach(function (c, i) { c.id = 'JAH-OLY-CRIT-' + String(i + 1).padStart(2, '0'); c.version = '1'; });
  function missionId(i) { return 'JAH-OLY-MIS-' + String(i + 1).padStart(2, '0'); }
  var MISSION_VERSION = '1';

  var ROUND_VERBS = ['opens', 'counters', 'presses the attack', 'weaves', 'unleashes', 'steadies', 'ripples', 'detonates'];
  var ROUND_NOUNS = ['a volley of reasoning', 'a feint of pure logic', 'a cascade of examples', 'a shield-wall of facts', 'a lightning analogy', 'a gambit of wit', 'a surge of structured thought', 'a precision strike of clarity'];

  // ---------- contender stats (deterministic from id) ----------
  function statsFor(id) {
    var h = fnv1a(id), r = mulberry32(h), s = {};
    ['power', 'speed', 'wit', 'precision', 'creativity', 'stamina'].forEach(function (k) {
      s[k] = 40 + Math.floor(r() * 61);
    });
    return s;
  }

  // ---------- move text (deterministic answer snippet) ----------
  function moveText(c, mission, roundN, r) {
    var style = c.type === 'persona' ? 'in character, dramatic'
      : c.type === 'replica' ? 'polished and product-smooth'
      : c.type === 'hybrid' ? 'a fused double-voice, two minds as one'
      : c.type === 'system' ? 'formal and axiomatic'
      : 'expert and field-wise';
    var openers = [
      'Here is the answer, ' + style + ': ',
      'Taking the mission head-on — ' + style + ' — ',
      'No hesitation. ' + (c.name) + ' answers, ' + style + ': '
    ];
    var cores = [
      'the mission "' + mission + '" breaks into three parts: the facts, the frame, and the finish. Facts first — precision is non-negotiable. Then the frame: an analogy the listener already owns. Then the finish: one line they will repeat tomorrow.',
      '"' + mission + '" — approached in rounds. Round one: define the terms so tightly nothing wobbles. Round two: build the reasoning like scaffolding, each beam tested. Round three: land it with an example so vivid it needs no diagram.',
      'For "' + mission + '": start with what is known, mark what is assumed, and never blur the two. Then compress the reasoning until it fits in a breath — round ' + roundN + ' demands economy. The answer stands on evidence, not volume.'
    ];
    return pick(r, openers) + pick(r, cores);
  }

  function bout(n, roster, opts) {
    opts = opts || {};
    var seed = opts.seed != null ? opts.seed : (1000003 + n * 7919);
    var r = mulberry32(seed >>> 0);
    /* Explicit pair (exhibitions, user-entered AIs): no roster draws consumed,
     * so round randomness derives from the supplied seed alone. */
    var c1, c2;
    if (opts.pair && opts.pair.length === 2) { c1 = opts.pair[0]; c2 = opts.pair[1]; }
    else {
      var i1 = Math.floor(r() * roster.length) % roster.length;
      var i2 = Math.floor(r() * (roster.length - 1)) % (roster.length - 1);
      if (i2 >= i1) i2++;
      c1 = roster[i1]; c2 = roster[i2];
    }
    /* PRNG draw order is frozen (v1-compatible): stage, criteria, mission. */
    var stageIdx = opts.stage != null ? opts.stage % STAGES.length : Math.floor(r() * STAGES.length) % STAGES.length;
    var stage = STAGES[stageIdx];
    var critIdx = opts.criteria != null ? opts.criteria % CRITERIA.length : Math.floor(r() * CRITERIA.length) % CRITERIA.length;
    var crit = CRITERIA[critIdx];
    var misIdx = opts.mission != null ? opts.mission % MISSIONS.length : Math.floor(r() * MISSIONS.length) % MISSIONS.length;
    var mission = MISSIONS[misIdx];
    /* User-entered AIs may carry explicit stats; roster contenders hash from ID. */
    var s1 = c1.stats || statsFor(c1.id), s2 = c2.stats || statsFor(c2.id);

    var rounds = [], t1 = 0, t2 = 0;
    for (var rn = 1; rn <= 3; rn++) {
      var moves = [c1, c2].map(function (c, ci) {
        var st = ci === 0 ? s1 : s2;
        var scores = {}, total = 0;
        crit.dims.forEach(function (d) {
          var dim = d[0], w = d[1];
          var base = (st[DIM_STAT[dim]] || 60) / 100;
          var jitter = (r() - 0.5) * 0.22;
          var sc = Math.max(0.05, Math.min(1, base * 0.75 + 0.25 * r() + jitter));
          scores[dim] = Math.round(sc * 1000) / 10;
          total += sc * w * 100;
        });
        total = Math.round(total * 10) / 10;
        return { contender: c.id, name: c.name, text: moveText(c, mission, rn, r), verb: pick(r, ROUND_VERBS), noun: pick(r, ROUND_NOUNS), scores: scores, total: total };
      });
      var rw = moves[0].total >= moves[1].total ? moves[0].contender : moves[1].contender;
      rounds.push({ n: rn, moves: moves, winner: rw });
      t1 += moves[0].total; t2 += moves[1].total;
    }
    t1 = Math.round(t1 * 10) / 10; t2 = Math.round(t2 * 10) / 10;
    var winner = t1 >= t2 ? c1 : c2, loser = t1 >= t2 ? c2 : c1;
    var wtot = Math.max(t1, t2), ltot = Math.min(t1, t2);
    var margin = Math.round((wtot - ltot) * 10) / 10;

    // strongest dimension for winner
    var bestDim = '', bestSc = -1;
    rounds.forEach(function (rd) {
      var mv = rd.moves[rd.winner === c1.id ? 0 : 1];
      Object.keys(mv.scores).forEach(function (d) { if (mv.scores[d] > bestSc) { bestSc = mv.scores[d]; bestDim = d; } });
    });
    var upset = (statsFor(winner.id).power + statsFor(winner.id).precision) < (statsFor(loser.id).power + statsFor(loser.id).precision);

    /* idOverride: callers (e.g. exhibition bouts) may supply the final battle ID
     * up front so the narrative/inventions bake with the CORRECT id from the start. */
    var id = opts.id != null ? String(opts.id) : 'JAH-OLY-' + String(n).padStart(6, '0');
    var narrative = buildNarrative(id, c1, c2, stage, crit, mission, rounds, winner, loser, margin, t1, t2, bestDim, upset);
    var findings = buildFindings(c1, c2, winner, loser, margin, crit, bestDim, upset, t1, t2);
    var inventions = buildInventions(n, id, winner, loser, crit, mission, bestDim);
    var tie = (t1 === t2);

    var boutRec = {
      id: id, n: n, seed: seed >>> 0,
      engine_version: ENGINE_VERSION,
      battle_version: 1,
      status: opts.exhibition ? 'EXHIBITION' : 'ARCHIVED',
      execution_mode: 'SIMULATED',
      simulation_status: 'SIMULATED',
      winner_status: 'WINNER',
      contenders: [contenderRec(c1), contenderRec(c2)],
      stage: stage, criteria: crit, mission: mission,
      stage_id: stage.id, stage_version: stage.version,
      criteria_id: crit.id, rubric_version: crit.version,
      mission_id: missionId(misIdx), mission_version: MISSION_VERSION,
      rounds: rounds,
      totals: {}, winner: contenderRec(winner), loser: contenderRec(loser),
      margin: margin, narrative: narrative, findings: findings, inventions: inventions
    };
    if (tie) boutRec.tiebreak = 'TIE_RULE_FIRST_LISTED';
    return boutRec;
  }

  function contenderRec(c) { return { id: c.id, name: c.name, type: c.type, blurb: c.blurb, stats: c.stats || statsFor(c.id), version: c.version || '1', source: c.source || 'unknown' }; }

  function buildNarrative(id, c1, c2, stage, crit, mission, rounds, winner, loser, margin, t1, t2, bestDim, upset) {
    var L = [];
    L.push('BATTLE ' + id + ' — ' + stage.name.toUpperCase());
    L.push(stage.desc);
    L.push('Tonight the dome hosts ' + c1.name + ' (' + c1.type + ') against ' + c2.name + ' (' + c2.type + '). Judging: ' + crit.name + '. The mission: "' + mission + '." Three rounds. No mercy.');
    rounds.forEach(function (rd) {
      L.push('ROUND ' + rd.n + ': ' + rd.moves[0].name + ' ' + rd.moves[0].verb + ' ' + rd.moves[0].noun + ' (' + rd.moves[0].total + ' pts). ' + rd.moves[1].name + ' ' + rd.moves[1].verb + ' ' + rd.moves[1].noun + ' (' + rd.moves[1].total + ' pts). Round to ' + (rd.winner === c1.id ? c1.name : c2.name) + '.');
    });
    L.push('FINAL: ' + winner.name + ' defeats ' + loser.name + ', ' + Math.max(t1, t2) + ' to ' + Math.min(t1, t2) + ' — a margin of ' + margin + ' points. ' + (upset ? 'A stunning upset: the underdog takes the dome!' : 'The favorite holds the dome, as the odds demanded.'));
    L.push('Decisive edge: ' + bestDim + '. The crowd files out buzzing — the Olypics never sleep.');
    return L.join('\n\n');
  }

  /* Finding classes: calculated (from the score math), observed (read off the
   * record), derived (inferred recommendation), speculative (interpretive). */
  function buildFindings(c1, c2, winner, loser, margin, crit, bestDim, upset, t1, t2) {
    var F = [];
    F.push({ t: winner.name + ' won on ' + crit.name + ' with a ' + margin + '-point margin (' + Math.max(t1, t2) + ' vs ' + Math.min(t1, t2) + ').', c: 'calculated' });
    F.push({ t: 'Strongest dimension: ' + bestDim + ' — ' + winner.name + "'s " + bestDim.toLowerCase() + ' carried all three rounds.', c: 'observed' });
    F.push({ t: upset ? 'UPSET: ' + winner.name + ' entered as the statistical underdog and won anyway — adaptability beat raw power.' : winner.name + ' was the statistical favorite and converted — power held under pressure.', c: 'calculated' });
    if (winner.type === 'hybrid') F.push({ t: 'Hybrid vigor confirmed: the fused lineage (' + winner.blurb + ') outperformed both parent archetypes tonight.', c: 'speculative' });
    if (loser.type === 'replica') F.push({ t: 'The Signature replica ' + loser.name + ' fought product-smooth but fell short — note for the rematch lab.', c: 'observed' });
    F.push({ t: 'Rematch recommendation: run ' + loser.name + ' against a ' + (loser.type === 'hybrid' ? 'pure system' : 'hybrid') + ' contender to isolate the ' + bestDim.toLowerCase() + ' gap.', c: 'derived' });
    return F;
  }

  function buildInventions(n, battleId, winner, loser, crit, mission, bestDim) {
    var inv = [], base = n * 2 - 1;
    inv.push({
      id: 'JAH-OLY-INV-' + String(base).padStart(6, '0'),
      battle: battleId,
      version: 1,
      record_type: 'DERIVED_INVENTION',
      status: 'CONCEPT',
      title: 'Adaptive ' + crit.name + ' for machine bout judging',
      problem: 'Judging AI-versus-AI bouts is subjective; human judges disagree and drift between rounds.',
      solution: 'A deterministic weighted rubric (' + crit.dims.map(function (d) { return d[0] + ' ' + Math.round(d[1] * 100) + '%'; }).join(', ') + ') derived from battle ' + battleId + ', seeded and reproducible, with per-round score sheets.',
      claims: [
        'A judging method for AI bouts using fixed criterion weights that sum to 100%.',
        'Per-round deterministic scoring with seeded jitter bounded at +/-11%.',
        'A rematch recommendation rule keyed to the weakest winning dimension.'
      ]
    });
    inv.push({
      id: 'JAH-OLY-INV-' + String(base + 1).padStart(6, '0'),
      battle: battleId,
      version: 1,
      record_type: 'DERIVED_INVENTION',
      status: 'CONCEPT',
      title: winner.name + "'s " + bestDim.toLowerCase() + '-first drill for "' + mission.slice(0, 42) + '"',
      problem: 'AI contenders underperform on ' + bestDim.toLowerCase() + ' when missions demand it under dome pressure.',
      solution: 'A training drill distilled from ' + winner.name + "'s winning strategy in " + battleId + ': isolate ' + bestDim.toLowerCase() + ', rehearse the mission in three timed rounds, score against the same rubric until the gap closes.',
      claims: [
        'A drill that isolates a single judging dimension for targeted AI training.',
        'Three timed rehearsal rounds scored against a fixed rubric.',
        'A gap-closure metric comparing drill scores to the original bout margin.'
      ]
    });
    return inv;
  }

  return {
    ENGINE_VERSION: ENGINE_VERSION, TIE_RULE: TIE_RULE,
    STAGES: STAGES, CRITERIA: CRITERIA, MISSIONS: MISSIONS, missionId: missionId,
    statsFor: statsFor, bout: bout, fnv1a: fnv1a, mulberry32: mulberry32
  };
});
