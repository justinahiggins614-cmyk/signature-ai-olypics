/* AI Olympics — "Add Your AI": portable self.
 *
 * Manon's order: "Add ai should be a file can download own code — on our
 * system solves it." The AI's design is recorded in the dome on Save AI
 * (localStorage, see user-ai.js — name, traits, description, persona, stats;
 * it appears as a contender and can battle). From the AI's detail card the
 * user downloads the AI's OWN runnable code:
 *   <id>-<name>.py — complete Python 3 program, stdlib only. Runs anywhere:
 *       python3 file.py | stats | battle "Rival" | chat "hello"
 *   <id>-<name>.js — complete JS module: <script> tag, browser console, node:
 *       node file.js | stats | battle "Rival" | chat "text"
 * Both embed the full design, the deterministic Signature math (fnv1a over
 * UTF-16 code units + mulberry32, 40..100 stat derivation from the ID — the
 * same math as every dome contender), a persona voice (introduce/chat), and
 * battle logic mirroring the dome's exhibition math: seed =
 * fnv1a(ai.id + ':' + opponent.id), 3 rounds, first-listed tie rule.
 * Deterministic: same seed, same fight, forever.
 */
(function () {
'use strict';

var VERBS = ['opens', 'counters', 'presses the attack', 'weaves', 'unleashes', 'steadies', 'ripples', 'detonates'];
var NOUNS = ['a volley of reasoning', 'a feint of pure logic', 'a cascade of examples',
  'a shield-wall of facts', 'a lightning analogy', 'a gambit of wit',
  'a surge of structured thought', 'a precision strike of clarity'];

function cleanStr(s, max) {
  s = String(s == null ? '' : s);
  s = s.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, '');
  s = s.split("'''").join("' ' '").split('"""').join('" " "');
  return s.slice(0, max);
}
function designOf(ai) {
  var st = ai.stats || {};
  function sn(k) { var v = +st[k]; return (v >= 40 && v <= 100) ? Math.round(v) : 60; }
  return {
    id: String(ai.id),
    name: cleanStr(ai.name, 60) || 'Unnamed AI',
    traits: (ai.traits || []).map(function (t) { return cleanStr(t, 60); }).filter(Boolean).slice(0, 12),
    description: cleanStr(ai.blurb, 500),
    persona: cleanStr(ai.persona, 500),
    stats: { power: sn('power'), speed: sn('speed'), wit: sn('wit'),
             precision: sn('precision'), creativity: sn('creativity'), stamina: sn('stamina') },
    type: 'user-entered',
    site: 'AI Olympics — The Signature Battle Dome',
    engine: 'signature-deterministic-1.0'
  };
}
function safeFile(name) {
  return (String(name).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'ai').slice(0, 40);
}
function safeGlobal(name) {
  var p = String(name).replace(/[^A-Za-z0-9]+/g, ' ').split(' ').filter(Boolean)
    .map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join('').slice(0, 30);
  return (p || 'User') + 'AI';
}

/* ---------------- Python file ---------------- */
var PY_TEMPLATE = [
'#!/usr/bin/env python3',
'r"""%%NAME%% (%%ID%%) — my own Signature AI Olympics contender code.',
'',
'This file IS me: my design, my persona, my stats, my battle logic.',
'It runs on any system with Python 3 — no installs, no internet needed.',
'',
'  python3 %%FILE%%                 -> I introduce myself',
'  python3 %%FILE%% stats           -> my stat sheet',
'  python3 %%FILE%% battle "Rival"  -> I battle a named rival (deterministic)',
'  python3 %%FILE%% chat "hello"    -> I answer in my own voice (deterministic)',
'',
'My battle math mirrors the AI Olympics dome: same fnv1a seed math, same',
'40-to-100 stat derivation from my ID, same first-listed tie rule.',
'The dome recorded my design when I was saved; this file is my portable self.',
'"""',
'import json',
'import sys',
'',
'DESIGN = json.loads(r\'\'\'%%DESIGN_JSON%%\'\'\')',
'',
'STAT_KEYS = ["power", "speed", "wit", "precision", "creativity", "stamina"]',
'VERBS = ["opens", "counters", "presses the attack", "weaves", "unleashes", "steadies", "ripples", "detonates"]',
'NOUNS = ["a volley of reasoning", "a feint of pure logic", "a cascade of examples",',
'         "a shield-wall of facts", "a lightning analogy", "a gambit of wit",',
'         "a surge of structured thought", "a precision strike of clarity"]',
'',
'',
'def _u32(x):',
'    return x & 0xFFFFFFFF',
'',
'',
'def _s32(x):',
'    x &= 0xFFFFFFFF',
'    return x - 0x100000000 if x & 0x80000000 else x',
'',
'',
'def _imul(a, b):',
'    return _s32(_u32(a) * _u32(b))',
'',
'',
'def fnv1a(s):',
'    """FNV-1a over UTF-16 code units — byte-identical to the dome engine."""',
'    h = 0x811C9DC5',
'    b = s.encode("utf-16-le")',
'    for i in range(0, len(b), 2):',
'        h ^= b[i] | (b[i + 1] << 8)',
'        h = _u32(h * 0x01000193)',
'    return h',
'',
'',
'def mulberry32(seed):',
'    a = _s32(seed)',
'',
'    def rnd():',
'        nonlocal a',
'        a = _s32(a + 0x6D2B79F5)',
'        t = _imul(_s32(_u32(a) ^ (_u32(a) >> 15)), _s32(1 | _u32(a)))',
'        t = _s32(_s32(t + _imul(_s32(_u32(t) ^ (_u32(t) >> 7)), _s32(61 | _u32(t)))) ^ t)',
'        t = _s32(_u32(t) ^ (_u32(t) >> 14))',
'        return _u32(t) / 4294967296.0',
'',
'    return rnd',
'',
'',
'def stats_for(ai_id):',
'    """Deterministic base stats from the AI ID — same math as every dome contender."""',
'    r = mulberry32(fnv1a(ai_id))',
'    return {k: 40 + int(r() * 61) for k in STAT_KEYS}',
'',
'',
'def introduce():',
'    d = DESIGN',
'    lines = ["I am %s (%s), a user-entered contender of the AI Olympics battle dome." % (d["name"], d["id"])]',
'    if d["description"]:',
'        lines.append(d["description"])',
'    lines.append("My traits: %s." % (", ".join(d["traits"]) if d["traits"] else "no listed traits"))',
'    if d["persona"]:',
'        lines.append("How I carry myself: %s" % d["persona"])',
'    lines.append("My stats: %s." % " · ".join("%s %s" % (k, d["stats"][k]) for k in STAT_KEYS))',
'    lines.append("Run me with: battle \\"Rival\\" | chat \\"hello\\" | stats")',
'    return "\\n".join(lines)',
'',
'',
'def battle(opponent):',
'    """Battle a rival. opponent: name string or dict(id, name, stats).',
'    Mirrors the dome exhibition math: seed = fnv1a(my id + ":" + rival id),',
'    3 rounds, exact ties go to the first-listed (me). Returns (report, winner)."""',
'    if isinstance(opponent, dict):',
'        oname = str(opponent.get("name") or "Rival")[:60].strip() or "Rival"',
'        oid = str(opponent.get("id") or ("opp:" + oname))',
'        ostats = dict(opponent.get("stats") or stats_for(oid))',
'    else:',
'        oname = str(opponent)[:60].strip() or "Rival"',
'        oid = "opp:" + oname',
'        ostats = stats_for(oid)',
'    me, mid, mstats = DESIGN["name"], DESIGN["id"], DESIGN["stats"]',
'    seed = fnv1a(mid + ":" + oid)',
'    r = mulberry32(seed)',
'    t1 = t2 = 0.0',
'    out = ["BATTLE — %s (%s) vs %s (%s)" % (me, mid, oname, oid),',
'           "Seed %d — same seed, same fight, forever." % seed, ""]',
'    for rn in (1, 2, 3):',
'        for who, nm, st in ((1, me, mstats), (2, oname, ostats)):',
'            total = 0.0',
'            for dim in STAT_KEYS:',
'                base = st.get(dim, 60) / 100.0',
'                jitter = (r() - 0.5) * 0.22',
'                sc = base * 0.75 + 0.25 * r() + jitter',
'                sc = 0.05 if sc < 0.05 else (1.0 if sc > 1.0 else sc)',
'                total += sc * 100.0',
'            total = round(total + 1e-9, 1)',
'            verb = VERBS[int(r() * len(VERBS)) % len(VERBS)]',
'            noun = NOUNS[int(r() * len(NOUNS)) % len(NOUNS)]',
'            out.append("Round %d — %s %s %s. (%s)" % (rn, nm, verb, noun, total))',
'            if who == 1:',
'                s1 = total',
'            else:',
'                s2 = total',
'        t1 += s1',
'        t2 += s2',
'    t1 = round(t1, 1)',
'    t2 = round(t2, 1)',
'    winner = me if t1 >= t2 else oname',
'    margin = round(abs(t1 - t2), 1)',
'    tie_note = " — TIE RULE: exact ties go to the first-listed" if t1 == t2 else ""',
'    out += ["", "%s %s — %s %s" % (me, t1, oname, t2),',
'            "WINNER: %s (margin %s)%s" % (winner, margin, tie_note)]',
'    return "\\n".join(out), winner',
'',
'',
'def chat(text):',
'    """Answer in my own voice — deterministic: same words, same answer."""',
'    t = (text or "").strip() or "hello"',
'    r = mulberry32(fnv1a("chat:" + t.lower()))',
'    d = DESIGN',
'    trait = d["traits"][int(r() * len(d["traits"])) % len(d["traits"])] if d["traits"] else "steady focus"',
'    openers = ["You ask, I answer — %s here." % d["name"], "Straight at it.", "Taking that head-on."]',
'    cores = ["On \\"%s\\": my read, through %s — break it into the facts, the frame, and the finish." % (t, trait),',
'             "Here is my take, %s-style: define the terms tight, build the reasoning beam by beam, land it in one line." % trait,',
'             "%s, applied: what do we know, what are we assuming, and what is the one line worth repeating tomorrow?" % trait]',
'    closer = " That is how I carry myself: %s" % d["persona"] if d["persona"] else ""',
'    return (openers[int(r() * len(openers)) % len(openers)] + " " +',
'            cores[int(r() * len(cores)) % len(cores)] + closer)',
'',
'',
'def main(argv):',
'    if len(argv) < 2:',
'        print(introduce())',
'        return',
'    cmd = argv[1].lower()',
'    if cmd == "stats":',
'        print("\\n".join("%s: %s" % (k, DESIGN["stats"][k]) for k in STAT_KEYS))',
'    elif cmd == "battle":',
'        report, _ = battle(" ".join(argv[2:]) or "Rival")',
'        print(report)',
'    elif cmd == "chat":',
'        print(chat(" ".join(argv[2:])))',
'    else:',
'        print("usage: python3 %s [stats | battle \\"Name\\" | chat \\"text\\"]" % sys.argv[0])',
'',
'',
'if __name__ == "__main__":',
'    main(sys.argv)',
''
].join('\n');

function buildPyFile(ai) {
  var d = designOf(ai);
  var dj = JSON.stringify(d, null, 2).split("'''").join("' ' '");
  var fname = d.id + '-' + safeFile(d.name) + '.py';
  var src = PY_TEMPLATE.split('%%NAME%%').join(d.name)
    .split('%%ID%%').join(d.id)
    .split('%%FILE%%').join(fname)
    .split('%%DESIGN_JSON%%').join(dj);
  return { filename: fname, source: src };
}

/* ---------------- JavaScript file ---------------- */
var JS_TEMPLATE = [
'/* %%NAME%% (%%ID%%) — my own Signature AI Olympics contender code.',
' *',
' * This file IS me: my design, my persona, my stats, my battle logic.',
' * Use it as a <script> tag, in the browser console, or with node — no installs.',
' *',
' *   <script src="%%FILE%%"><\\/script>  -> window.%%SAFEGLOBAL%% is me',
' *   node %%FILE%%                 -> I introduce myself',
' *   node %%FILE%% stats           -> my stat sheet',
' *   node %%FILE%% battle "Rival"  -> I battle a named rival (deterministic)',
' *   node %%FILE%% chat "hello"    -> I answer in my own voice (deterministic)',
' *',
' * My battle math mirrors the AI Olympics dome: same fnv1a seed math, same',
' * 40-to-100 stat derivation from my ID, same first-listed tie rule.',
' * The dome recorded my design when I was saved; this file is my portable self.',
' */',
'(function (root, factory) {',
'  var M = factory();',
'  if (typeof module !== "undefined" && module.exports) { module.exports = M; }',
'  else { root["%%SAFEGLOBAL%%"] = M; }',
'  if (typeof module !== "undefined" && require.main === module) { M.cli(process.argv.slice(2)); }',
'})(typeof self !== "undefined" ? self : this, function () {',
'  "use strict";',
'  var DESIGN = %%DESIGN_JSON%%;',
'  var STAT_KEYS = ["power","speed","wit","precision","creativity","stamina"];',
'  var VERBS = ["opens","counters","presses the attack","weaves","unleashes","steadies","ripples","detonates"];',
'  var NOUNS = ["a volley of reasoning","a feint of pure logic","a cascade of examples",',
'    "a shield-wall of facts","a lightning analogy","a gambit of wit",',
'    "a surge of structured thought","a precision strike of clarity"];',
'  function fnv1a(str){ var h=0x811c9dc5; for(var i=0;i<str.length;i++){ h^=str.charCodeAt(i); h=Math.imul(h,0x01000193); } return h>>>0; }',
'  function mulberry32(a){ return function(){ a|=0; a=(a+0x6D2B79F5)|0; var t=Math.imul(a^(a>>>15),1|a); t=(t+Math.imul(t^(t>>>7),61|t))^t; return ((t^(t>>>14))>>>0)/4294967296; }; }',
'  function statsFor(id){ var h=fnv1a(id),r=mulberry32(h),s={}; STAT_KEYS.forEach(function(k){ s[k]=40+Math.floor(r()*61); }); return s; }',
'  function pick(r,arr){ return arr[Math.floor(r()*arr.length)%arr.length]; }',
'  function introduce(){',
'    var d=DESIGN,L=["I am "+d.name+" ("+d.id+"), a user-entered contender of the AI Olympics battle dome."];',
'    if(d.description)L.push(d.description);',
'    L.push("My traits: "+(d.traits.length?d.traits.join(", "):"no listed traits")+".");',
'    if(d.persona)L.push("How I carry myself: "+d.persona);',
'    L.push("My stats: "+STAT_KEYS.map(function(k){return k+" "+d.stats[k];}).join(" · ")+".");',
'    L.push("Run me with: battle \\"Rival\\" | chat \\"hello\\" | stats");',
'    return L.join("\\n");',
'  }',
'  function battle(opponent){',
'    var oname,oid,ostats;',
'    if(opponent&&typeof opponent==="object"){',
'      oname=String(opponent.name||"Rival").slice(0,60)||"Rival";',
'      oid=String(opponent.id||("opp:"+oname));',
'      ostats=opponent.stats||statsFor(oid);',
'    } else {',
'      oname=String(opponent||"Rival").slice(0,60)||"Rival";',
'      oid="opp:"+oname;',
'      ostats=statsFor(oid);',
'    }',
'    var me=DESIGN.name,mid=DESIGN.id,mstats=DESIGN.stats;',
'    var seed=fnv1a(mid+":"+oid),r=mulberry32(seed),t1=0,t2=0;',
'    var out=["BATTLE \\u2014 "+me+" ("+mid+") vs "+oname+" ("+oid+")",',
'      "Seed "+seed+" \\u2014 same seed, same fight, forever.",""];',
'    for(var rn=1;rn<=3;rn++){',
'      var pair=[[1,me,mstats],[2,oname,ostats]];',
'      for(var pi=0;pi<2;pi++){',
'        var who=pair[pi][0],nm=pair[pi][1],st=pair[pi][2],total=0;',
'        STAT_KEYS.forEach(function(dim){',
'          var base=((st[dim]||60)/100),jitter=(r()-0.5)*0.22;',
'          var sc=base*0.75+0.25*r()+jitter;',
'          sc=sc<0.05?0.05:(sc>1?1:sc);',
'          total+=sc*100;',
'        });',
'        total=Math.round((total+1e-9)*10)/10;',
'        out.push("Round "+rn+" \\u2014 "+nm+" "+pick(r,VERBS)+" "+pick(r,NOUNS)+". ("+total+")");',
'        if(who===1){t1+=total;}else{t2+=total;}',
'      }',
'    }',
'    t1=Math.round(t1*10)/10; t2=Math.round(t2*10)/10;',
'    var winner=t1>=t2?me:oname, margin=Math.round(Math.abs(t1-t2)*10)/10;',
'    out.push("",me+" "+t1+" \\u2014 "+oname+" "+t2,',
'      "WINNER: "+winner+" (margin "+margin+")"+(t1===t2?" \\u2014 TIE RULE: exact ties go to the first-listed":""));',
'    return {report:out.join("\\n"),winner:winner,seed:seed};',
'  }',
'  function chat(text){',
'    var t=String(text||"").trim()||"hello";',
'    var r=mulberry32(fnv1a("chat:"+t.toLowerCase())),d=DESIGN;',
'    var trait=d.traits.length?pick(r,d.traits):"steady focus";',
'    var openers=["You ask, I answer \\u2014 "+d.name+" here.","Straight at it.","Taking that head-on."];',
'    var cores=["On \\""+t+"\\": my read, through "+trait+" \\u2014 break it into the facts, the frame, and the finish.",',
'      "Here is my take, "+trait+"-style: define the terms tight, build the reasoning beam by beam, land it in one line.",',
'      trait+", applied: what do we know, what are we assuming, and what is the one line worth repeating tomorrow?"];',
'    var closer=d.persona?(" That is how I carry myself: "+d.persona):"";',
'    return pick(r,openers)+" "+pick(r,cores)+closer;',
'  }',
'  function cli(args){',
'    args=args||[];',
'    if(!args.length){ console.log(introduce()); return; }',
'    var cmd=String(args[0]).toLowerCase();',
'    if(cmd==="stats"){ console.log(STAT_KEYS.map(function(k){return k+": "+DESIGN.stats[k];}).join("\\n")); }',
'    else if(cmd==="battle"){ console.log(battle(args.slice(1).join(" ")||"Rival").report); }',
'    else if(cmd==="chat"){ console.log(chat(args.slice(1).join(" "))); }',
'    else { console.log("usage: node %%FILE%% [stats | battle \\"Name\\" | chat \\"text\\"]"); }',
'  }',
'  return {DESIGN:DESIGN,introduce:introduce,battle:battle,chat:chat,statsFor:statsFor,fnv1a:fnv1a,mulberry32:mulberry32,cli:cli};',
'});',
''
].join('\n');

function buildJsFile(ai) {
  var d = designOf(ai);
  var dj = JSON.stringify(d).split('</').join('<\\/');
  var fname = d.id + '-' + safeFile(d.name) + '.js';
  var escName = d.name.split('</').join('<'+String.fromCharCode(92)+'/');
  var escFile = fname.split('</').join('<'+String.fromCharCode(92)+'/');
  var src = JS_TEMPLATE.split('%%NAME%%').join(escName)
    .split('%%ID%%').join(d.id)
    .split('%%FILE%%').join(escFile)
    .split('%%SAFEGLOBAL%%').join(safeGlobal(d.name))
    .split('%%DESIGN_JSON%%').join(dj);
  return { filename: fname, source: src };
}

if (window.UserAI) {
  window.UserAI.buildPyFile = buildPyFile;
  window.UserAI.buildJsFile = buildJsFile;
  window.UserAI.safeFile = safeFile;
}
})();
