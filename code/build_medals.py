#!/usr/bin/env python3
"""Build data/medals.json — Olympic medal tables from the archived bouts.

Rules (published, deterministic):
- Every archived 1v1 bout awards GOLD to the winner, SILVER to the loser.
- BRONZE is awarded only in Weekly Games (third-place bouts; double-bronze
  for wrestling semifinal losers, per wrestling tradition).
- Bouts fought before Olympic events existed carry no event_id; they are
  assigned an event deterministically from their seed: EVENTS[seed % 8].
  Documented, reproducible, never re-rolled.
- Rankings sort by gold desc, then silver desc, then bronze desc, then name.
- Reigns ("for how long"): walking the archive in bout order, the #1 holder
  (by the same sort) is tracked; every change of the guard closes one reign
  and opens the next, with bout counts. Same per event.

Safe to run any time; called by code/seed.py and code/weekly_games.py.
"""
import json
import os
import gzip
import glob
import subprocess
import datetime
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')

# Must match code/engine.js EVENTS order (verified by verify_events() below).
EVENTS = [
    ('wrestling', 'Wrestling', '\U0001F93C', 'JAH-OLY-EVENT-01'),
    ('allaround', 'All-Around', '\U0001F3C5', 'JAH-OLY-EVENT-02'),
    ('sprint', 'Sprint', '\u26A1', 'JAH-OLY-EVENT-03'),
    ('marathon', 'Marathon', '\U0001F3C3', 'JAH-OLY-EVENT-04'),
    ('weightlifting', 'Weightlifting', '\U0001F3CB\uFE0F', 'JAH-OLY-EVENT-05'),
    ('gymnastics', 'Gymnastics', '\U0001F938', 'JAH-OLY-EVENT-06'),
    ('debate', 'Debate', '\U0001F399\uFE0F', 'JAH-OLY-EVENT-07'),
    ('puzzle', 'Puzzle Hunt', '\U0001F9E9', 'JAH-OLY-EVENT-08'),
]
EVENT_BY_ID = {e[3]: e[0] for e in EVENTS}
EVENT_BY_KEY = {e[0]: e for e in EVENTS}


def verify_events():
    """The Python event table must match engine.js exactly."""
    js = ("const E=require(%s);process.stdout.write(JSON.stringify("
          "E.EVENTS.map(e=>[e.id,e.key,e.name])));"
          % json.dumps(os.path.join(HERE, 'engine.js')))
    reg = json.loads(subprocess.run(['node', '-e', js], capture_output=True,
                                    text=True, check=True).stdout)
    mine = [[e[3], e[0], e[1]] for e in EVENTS]
    assert reg == mine, 'engine.js EVENTS drifted from build_medals.py: %r vs %r' % (reg, mine)


def iter_bouts():
    for p in sorted(glob.glob(os.path.join(DATA, 'chunks', 'bouts-c*.jsonl.gz'))):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def event_key_for(bout):
    eid = bout.get('event_id')
    if eid and eid in EVENT_BY_ID:
        return EVENT_BY_ID[eid]
    # legacy bouts (pre-Olympic): deterministic assignment from the seed
    return EVENTS[(bout.get('seed') or 0) % len(EVENTS)][0]


def build_medals():
    verify_events()
    roster = {c['id']: c for c in json.load(open(os.path.join(DATA, 'contenders.json')))}
    bouts = sorted(iter_bouts(), key=lambda b: b['id'])

    gold = Counter()
    silver = Counter()
    bronze = Counter()
    ev_gold = defaultdict(Counter)
    ev_silver = defaultdict(Counter)

    # reign tracking: (gold, silver, id) leader walk
    def leader(counters_g, counters_s, ids):
        best = None
        for cid in ids:
            key = (counters_g[cid], counters_s[cid])
            if best is None or key > best[0] or (key == best[0] and cid < best[1]):
                best = (key, cid)
        return best[1] if best else None

    reigns = []
    cur_leader = None
    reign_start = None
    reign_bouts = 0
    ev_reigns = {e[0]: [] for e in EVENTS}
    ev_leader = {e[0]: None for e in EVENTS}
    ev_reign_start = {e[0]: None for e in EVENTS}
    ev_reign_bouts = {e[0]: 0 for e in EVENTS}
    ev_prev = {e[0]: None for e in EVENTS}
    seen_ids = set()

    for b in bouts:
        w = b['winner']['id']
        l = b['loser']['id']
        ek = event_key_for(b)
        gold[w] += 1
        silver[l] += 1
        ev_gold[ek][w] += 1
        ev_silver[ek][l] += 1
        seen_ids.add(w)
        seen_ids.add(l)

        nl = leader(gold, silver, seen_ids)
        reign_bouts += 1
        if nl != cur_leader:
            if cur_leader is not None:
                reigns.append({'holder': cur_leader, 'from': reign_start,
                               'to': prev_id, 'bouts': reign_bouts - 1})
            cur_leader = nl
            reign_start = b['id']
            reign_bouts = 1
        prev_id = b['id']

        # per-event reign (only contenders seen in that event)
        nl_e = leader(ev_gold[ek], ev_silver[ek], [c for c in seen_ids if ev_gold[ek][c] or ev_silver[ek][c]])
        ev_reign_bouts[ek] += 1
        if nl_e != ev_leader[ek]:
            if ev_leader[ek] is not None:
                ev_reigns[ek].append({'holder': ev_leader[ek], 'from': ev_reign_start[ek],
                                      'to': ev_prev[ek], 'bouts': ev_reign_bouts[ek] - 1})
            ev_leader[ek] = nl_e
            ev_reign_start[ek] = b['id']
            ev_reign_bouts[ek] = 1
        ev_prev[ek] = b['id']

    # weekly-games bronze (and any games medals) live in the games records
    games = []
    games_dir = os.path.join(DATA, 'games')
    if os.path.isdir(games_dir):
        for p in sorted(glob.glob(os.path.join(games_dir, 'weekly-*.json'))):
            g = json.load(open(p))
            games.append(g)
            for row in g.get('medal_table', []):
                bronze[row['id']] += row.get('bronze', 0)

    def row(cid):
        c = roster.get(cid, {'name': cid, 'type': '?'})
        return {'id': cid, 'name': c.get('name', cid), 'type': c.get('type', '?'),
                'gold': gold[cid], 'silver': silver[cid], 'bronze': bronze[cid],
                'total': gold[cid] + silver[cid] + bronze[cid]}

    def rank_key(r):
        return (-r['gold'], -r['silver'], -r['bronze'], r['name'])

    overall = sorted((row(cid) for cid in seen_ids), key=rank_key)
    by_event = {}
    for ek, _, _, _ in EVENTS:
        ids = [c for c in seen_ids if ev_gold[ek][c] or ev_silver[ek][c]]
        by_event[ek] = sorted((dict(row(cid),
                               gold=ev_gold[ek][cid], silver=ev_silver[ek][cid],
                               bronze=0,
                               total=ev_gold[ek][cid] + ev_silver[ek][cid])
                              for cid in ids), key=rank_key)

    def champ(holder, start, bouts_held):
        c = roster.get(holder, {'name': holder})
        return {'id': holder, 'name': c.get('name', holder),
                'since': start, 'bouts_held': bouts_held}

    medals = {
        'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        'bouts_scanned': len(bouts),
        'contenders_ranked': len(overall),
        'events': [{'key': e[0], 'name': e[1], 'emoji': e[2], 'id': e[3]} for e in EVENTS],
        'overall_ranking': overall,
        'by_event': by_event,
        'reigns': {'overall': reigns,
                   'by_event': ev_reigns},
        'current_champions': {
            'overall': champ(cur_leader, reign_start, reign_bouts) if cur_leader else None,
            'by_event': {ek: (champ(ev_leader[ek], ev_reign_start[ek], ev_reign_bouts[ek])
                              if ev_leader[ek] else None)
                         for ek in ev_leader},
        },
        'games_history': [{'games_id': g['games_id'], 'week_start': g.get('week_start'),
                           'bouts': g.get('bout_count', 0)} for g in games],
        'rules': {
            'gold': 'bout winner (1v1)',
            'silver': 'bout loser (1v1)',
            'bronze': 'weekly games third-place bouts only; wrestling awards double bronze',
            'legacy_events': 'pre-Olympic bouts (no event_id) assigned EVENTS[seed % 8], deterministic',
            'ranking': 'gold desc, silver desc, bronze desc, name asc',
        },
    }
    with open(os.path.join(DATA, 'medals.json'), 'w') as f:
        json.dump(medals, f, indent=1)
    print('medals.json: %d bouts, %d contenders ranked, %d reigns, %d games'
          % (len(bouts), len(overall), len(reigns), len(games)))
    return medals


if __name__ == '__main__':
    build_medals()
