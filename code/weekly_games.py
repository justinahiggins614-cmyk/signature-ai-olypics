#!/usr/bin/env python3
"""Run a full Weekly Olympics: ALL roster contenders, 8 Olympic events,
single-elimination brackets. Deterministic from the week number.

Usage: weekly_games.py [--week N]

- Week N defaults to (existing games) + 1; games_id JAH-OLY-GAMES-####.
- Bracket seeding: contenders ordered by the current overall medal table
  (gold, silver, bronze, name); top seeds earn byes to fill a 512 bracket.
- Every bracket bout is a real archived JAH-OLY-###### bout (IDs continue the
  global sequence from data/state.json; invention IDs continue too), tagged
  with games_id, engine v2.1, JAH-OLY-RECORD/2.0 envelopes + content hashes.
- Per event: single elimination -> GOLD (champion), SILVER (runner-up),
  BRONZE (third-place bout winners; wrestling awards DOUBLE bronze to both
  semifinal losers, per wrestling tradition — no third-place bout).
- Bracket pairing is deterministic: round 1 pairs best-remaining vs
  worst-remaining; later rounds pair the rank-sorted pool first-vs-last, so
  top seeds can only meet deep in the bracket.
- Bout seeds: fnv1a('{games_id}:{event}:R{round}:{c1}-vs-{c2}') — unique and
  reproducible; the whole games replays exactly from the week number.
- Writes data/games/weekly-####.json (permanent games record), repacks
  chunks, rebuilds index/manifest/medals/api/sitemap/llms/health.

Bout math: 383 contenders -> 512 bracket (129 byes) -> 382 bouts per event;
8 events = 3056 + 7 bronze bouts = 3063 bouts per games.
"""
import json
import os
import sys
import gzip
import glob
import argparse
import subprocess
import datetime
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
sys.path.insert(0, HERE)
from record_util import content_hash
from build_medals import build_medals, EVENTS

EVENT_KEYS = [e[0] for e in EVENTS]


def fnv1a(s):
    h = 0x811c9dc5
    for ch in s:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def load_roster():
    return json.load(open(os.path.join(DATA, 'contenders.json')))


def medal_rank_order():
    """Contender ids, best first, from the current overall medal table."""
    m = json.load(open(os.path.join(DATA, 'medals.json')))
    return [r['id'] for r in m['overall_ranking']]


def run_node_bouts(specs):
    """specs: [{n,id,seed,c1,c2,event}] -> list of bout dicts (no envelope)."""
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as tf:
        json.dump(specs, tf)
        spec_path = tf.name
    js = ("const fs=require('fs');"
          "const E=require(%s);" % json.dumps(os.path.join(HERE, 'engine.js')))
    js += ("const roster=require(%s);" % json.dumps(os.path.join(DATA, 'contenders.json')))
    js += (
        "const byId={};roster.forEach(c=>{byId[c.id]=c;});"
        "const specs=JSON.parse(fs.readFileSync(%s,'utf8'));" % json.dumps(spec_path)
        + "let out=[];"
        + "for(const s of specs){"
        + "const c1=byId[s.c1],c2=byId[s.c2];"
        + "if(!c1||!c2)throw new Error('unknown contender '+s.c1+'/'+s.c2);"
        + "const b=E.bout(s.n,roster,{pair:[c1,c2],event:s.event,seed:s.seed,id:s.id});"
        + "b.totals={};"
        + "b.totals[c1.id]=b.rounds.reduce((x,rd)=>x+rd.moves[0].total,0);"
        + "b.totals[c2.id]=b.rounds.reduce((x,rd)=>x+rd.moves[1].total,0);"
        + "out.push(JSON.stringify(b));}"
        + "process.stdout.write(out.join('\\n'));"
    )
    p = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    os.unlink(spec_path)
    if p.returncode != 0:
        print('NODE ERROR:', p.stderr[:2000])
        sys.exit(1)
    lines = [l for l in p.stdout.split('\n') if l.strip()]
    assert len(lines) == len(specs), 'node returned %d bouts, expected %d' % (len(lines), len(specs))
    return [json.loads(l) for l in lines]


def play_round(specs_meta, next_n, games_id, event_key, round_no, created):
    """specs_meta: [(c1id, c2id)] -> (bouts, winners, losers)."""
    specs = []
    for i, (c1, c2) in enumerate(specs_meta):
        n = next_n + i
        seed = fnv1a('%s:%s:R%d:%s-vs-%s' % (games_id, event_key, round_no, c1, c2))
        specs.append({'n': n, 'id': 'JAH-OLY-%06d' % n, 'seed': seed,
                      'c1': c1, 'c2': c2, 'event': event_key})
    bouts = run_node_bouts(specs)
    for b in bouts:
        b['games_id'] = games_id
        b['created'] = created
        b['content_hash'] = content_hash(b)
        assert b['engine_version'] == '2.1' and b['status'] == 'ARCHIVED'
        assert b['event_id'] == [e[3] for e in EVENTS if e[0] == event_key][0], b['event_id']
    winners = [b['winner']['id'] for b in bouts]
    losers = [b['loser']['id'] for b in bouts]
    return bouts, winners, losers


def run_event_bracket(event_key, ranked_ids, next_n, games_id, created):
    """Single-elim bracket. Returns (bouts, gold, silver, bronzes)."""
    n = len(ranked_ids)
    size = 1
    while size < n:
        size *= 2
    byes = size - n
    bye_ids = ranked_ids[:byes]
    fighters = ranked_ids[byes:]

    all_bouts = []
    # round 1: best-remaining vs worst-remaining
    pairs = [(fighters[i], fighters[-(i + 1)]) for i in range(len(fighters) // 2)]
    bouts, winners, _ = play_round(pairs, next_n, games_id, event_key, 1, created)
    all_bouts.extend(bouts)
    next_n += len(bouts)

    # later rounds: rank-sorted pool, first-vs-last
    rank_pos = {cid: i for i, cid in enumerate(ranked_ids)}
    pool = sorted(bye_ids + winners, key=lambda c: rank_pos[c])
    round_no = 2
    semi_losers = []
    while len(pool) > 2:
        pairs = [(pool[i], pool[-(i + 1)]) for i in range(len(pool) // 2)]
        bouts, winners, _ = play_round(pairs, next_n, games_id, event_key, round_no, created)
        all_bouts.extend(bouts)
        next_n += len(bouts)
        pool = sorted(winners, key=lambda c: rank_pos[c])
        round_no += 1
    # final (pool == 2)
    bouts, winners, losers = play_round([(pool[0], pool[1])], next_n, games_id, event_key, round_no, created)
    all_bouts.extend(bouts)
    next_n += len(bouts)
    gold, silver = winners[0], losers[0]
    # semifinal losers: from the previous round's losers — recompute: the two
    # losers of the round before the final
    bronzes = []
    if event_key == 'wrestling':
        bronzes = semi_losers_of(all_bouts, pool, ranked_ids)
    else:
        sl = semi_losers_of(all_bouts, pool, ranked_ids)
        if len(sl) == 2:
            bouts, winners, _ = play_round([(sl[0], sl[1])], next_n, games_id, event_key,
                                           round_no + 1, created)
            all_bouts.extend(bouts)
            next_n += len(bouts)
            bronzes = [winners[0]]
    return all_bouts, gold, silver, bronzes, next_n


def semi_losers_of(all_bouts, finalists, ranked_ids):
    """Find the two semifinal losers: losers of the bouts whose winners are
    the two finalists, in the latest round before the final."""
    # the final is the last bout; semifinals are the two bouts before it
    # whose winners are the finalists
    final = all_bouts[-1]
    semis = [b for b in all_bouts[:-1]
             if b['winner']['id'] in (final['contenders'][0]['id'], final['contenders'][1]['id'])]
    # take the two most recent such bouts
    semis = semis[-2:]
    return [b['loser']['id'] for b in semis]


def pack_chunks(bouts, start_n, per_chunk=100):
    """Append bouts to data/chunks continuing the global chunk numbering."""
    chunks_dir = os.path.join(DATA, 'chunks')
    chunk_no = (start_n - 1) // per_chunk + 1
    buf = []
    index_rows = []

    def flush():
        nonlocal chunk_no
        if not buf:
            return
        cp = os.path.join(chunks_dir, 'bouts-c%05d.jsonl.gz' % chunk_no)
        assert not os.path.exists(cp), 'chunk collision: ' + cp
        with gzip.open(cp, 'wt', encoding='utf-8') as f:
            f.write('\n'.join(buf) + '\n')
        buf.clear()
        chunk_no += 1

    for b in bouts:
        index_rows.append([b['id'], b['winner']['id'], b['winner']['name'],
                           b['contenders'][0]['id'], b['contenders'][1]['id'],
                           b['stage']['key'], b['mission'][:60]])
        buf.append(json.dumps(b, ensure_ascii=False))
        if len(buf) >= per_chunk:
            flush()
    flush()

    # merge into master index (dedupe by id — re-runs are idempotent)
    idx_p = os.path.join(DATA, 'index.json.gz')
    existing = []
    if os.path.exists(idx_p):
        with gzip.open(idx_p, 'rt') as f:
            existing = [json.loads(l) for l in f if l.strip()]
    seen = {r[0]: r for r in existing}
    for r in index_rows:
        seen[r[0]] = r
    all_rows = [seen[k] for k in sorted(seen)]
    with gzip.open(idx_p, 'wt') as f:
        for r in all_rows:
            f.write(json.dumps(r) + '\n')
    return len(all_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', type=int, default=None)
    args = ap.parse_args()

    games_dir = os.path.join(DATA, 'games')
    os.makedirs(games_dir, exist_ok=True)
    existing = sorted(glob.glob(os.path.join(games_dir, 'weekly-*.json')))
    week = args.week or (len(existing) + 1)
    games_id = 'JAH-OLY-GAMES-%04d' % week
    if os.path.exists(os.path.join(games_dir, 'weekly-%04d.json' % week)) and args.week:
        print('games %s already exists — refusing to overwrite' % games_id)
        sys.exit(1)

    # medal-seeded brackets need a fresh medal table
    build_medals()
    roster = load_roster()
    ranked = medal_rank_order()
    assert len(ranked) == len(roster), 'roster/medal mismatch'

    state_p = os.path.join(DATA, 'state.json')
    state = json.load(open(state_p))
    next_n = state['next_index']

    now = datetime.datetime.now(datetime.timezone.utc)
    created = now.isoformat(timespec='seconds')
    week_start = now.date().isoformat()
    week_end = (now.date() + datetime.timedelta(days=7)).isoformat()

    all_bouts = []
    events_out = []
    medal_rows = {}
    for ek in EVENT_KEYS:
        bouts, gold, silver, bronzes, next_n = run_event_bracket(ek, ranked, next_n, games_id, created)
        all_bouts.extend(bouts)
        ev_id = [e[3] for e in EVENTS if e[0] == ek][0]
        ev_name = [e[1] for e in EVENTS if e[0] == ek][0]
        events_out.append({
            'event_id': ev_id, 'event_key': ek, 'event_name': ev_name,
            'bouts': len(bouts),
            'bout_ids': [b['id'] for b in bouts],
            'gold': gold, 'silver': silver, 'bronze': bronzes,
        })
        for cid, medal in [(gold, 'gold'), (silver, 'silver')] + [(c, 'bronze') for c in bronzes]:
            medal_rows.setdefault(cid, {'gold': 0, 'silver': 0, 'bronze': 0})
            medal_rows[cid][medal] += 1
        print('event %-13s: %4d bouts  gold=%s' % (ek, len(bouts), gold))

    total = pack_chunks(all_bouts, state['next_index'])
    state['next_index'] = state['next_index'] + len(all_bouts)
    json.dump(state, open(state_p, 'w'), indent=1)

    names = {c['id']: c for c in roster}
    medal_table = sorted(
        ({'id': cid, 'name': names[cid]['name'], 'type': names[cid]['type'], **m}
         for cid, m in medal_rows.items()),
        key=lambda r: (-r['gold'], -r['silver'], -r['bronze'], r['name']))

    def cname(cid):
        return names[cid]['name'] if cid in names else cid

    ceremony_lines = [
        '\U0001F3DF\uFE0F WEEKLY OLYMPICS #%d — %s' % (week, week_start),
        '%d contenders entered all 8 Olympic events. %d bouts fought. The torch is lit.' % (len(roster), len(all_bouts)),
    ]
    for ev in events_out:
        ek, nm = ev['event_key'], ev['event_name']
        emoji = [e[2] for e in EVENTS if e[0] == ek][0]
        bl = ', '.join(cname(c) for c in ev['bronze']) if ev['bronze'] else 'none contested'
        ceremony_lines.append('%s %s — GOLD: %s · SILVER: %s · BRONZE: %s'
                              % (emoji, nm, cname(ev['gold']), cname(ev['silver']), bl))
    ceremony_lines.append('The medal table is final. See you at the next games — the torch never goes out. \U0001F525')

    games_rec = {
        'games_id': games_id,
        'week': week,
        'week_start': week_start,
        'week_end': week_end,
        'contenders': len(roster),
        'contender_ids': ranked,
        'events': events_out,
        'medal_table': medal_table,
        'bout_count': len(all_bouts),
        'bout_id_range': [all_bouts[0]['id'], all_bouts[-1]['id']],
        'engine_version': '2.1',
        'schema_version': 'JAH-OLY-RECORD/2.0',
        'determinism': 'bracket seeds from data/medals.json overall ranking; '
                       'bout seeds fnv1a(games_id:event:round:c1-vs-c2); '
                       'replay with --week %d' % week,
        'ceremony': '\n\n'.join(ceremony_lines),
    }
    gp = os.path.join(games_dir, 'weekly-%04d.json' % week)
    json.dump(games_rec, open(gp, 'w'), indent=1)

    # games index (for the Games Hall archive list)
    idx = []
    for p in sorted(glob.glob(os.path.join(games_dir, 'weekly-*.json'))):
        g = json.load(open(p))
        idx.append({'games_id': g['games_id'], 'week': g['week'],
                    'week_start': g['week_start'], 'bout_count': g['bout_count'],
                    'contenders': g['contenders']})
    json.dump(idx, open(os.path.join(games_dir, 'index.json'), 'w'), indent=1)

    # rebuild derived artifacts
    from build_manifest import build_manifest
    man = build_manifest()
    build_medals()
    api_p = os.path.join(ROOT, 'api.json')
    api = json.load(open(api_p)) if os.path.exists(api_p) else {}
    api.update({
        'bouts': total,
        'engine_version': '2.1',
        'weekly_games': {'count': week, 'latest': games_id, 'latest_week': week_start},
        'updated': man['updated'],
    })
    json.dump(api, open(api_p, 'w'), indent=1)

    for mod, fn in [('build_sitemap', None), ('build_llms', None), ('build_health', None)]:
        try:
            subprocess.run([sys.executable, os.path.join(HERE, mod + '.py')], check=True)
        except subprocess.CalledProcessError as e:
            print('WARNING: %s failed: %s' % (mod, e))

    print('games %s complete: %d bouts (%s..%s), total archive %d'
          % (games_id, len(all_bouts), all_bouts[0]['id'], all_bouts[-1]['id'], total))


if __name__ == '__main__':
    main()
