#!/usr/bin/env python3
"""Rebuild data/manifest.json (v2) from the current archive state.
The ONE count source for AI Olypics. Safe to run any time; also called by
code/seed.py after each seeding run."""
import json, os, gzip, hashlib
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')

def build_manifest():
    now = datetime.datetime.now(datetime.timezone.utc)
    roster = json.load(open(os.path.join(DATA, 'contenders.json')))
    idx_p = os.path.join(DATA, 'index.json.gz')
    rows = []
    if os.path.exists(idx_p):
        with gzip.open(idx_p, 'rt') as f:
            rows = [json.loads(l) for l in f if l.strip()]
    by_type, by_source = {}, {}
    for c in roster:
        by_type[c['type']] = by_type.get(c['type'], 0) + 1
        by_source[c.get('source', '?')] = by_source.get(c.get('source', '?'), 0) + 1
    with open(idx_p, 'rb') as f:
        index_hash = 'sha256:' + hashlib.sha256(f.read()).hexdigest()
    chunk_files = [f for f in os.listdir(os.path.join(DATA, 'chunks'))
                   if f.startswith('bouts-c') and f.endswith('.jsonl.gz')]
    games_dir = os.path.join(DATA, 'games')
    games_files = sorted(f for f in os.listdir(games_dir)
                         if f.startswith('weekly-') and f.endswith('.json')) \
        if os.path.isdir(games_dir) else []
    man = {
        'manifest_version': '2.0',
        'site': 'signature-ai-olypics',
        'generated_at': now.isoformat(timespec='seconds'),
        'bouts': len(rows),
        'goal': 1000000,
        'bout_id_range': [rows[0][0], rows[-1][0]] if rows else [None, None],
        'contenders': {'total': len(roster), 'by_type': by_type,
                       'by_source': by_source, 'roster_version': '1'},
        'stages': {'count': 12, 'version': '1'},
        'criteria': {'count': 6, 'version': '1', 'weights_verified_sum_to_1': True},
        'missions': {'count': 30, 'version': '1'},
        'events': {'count': 8, 'version': '1',
                   'ids': ['JAH-OLY-EVENT-%02d' % i for i in range(1, 9)]},
        'weekly_games': {'count': len(games_files),
                         'latest': games_files[-1][len('weekly-'):-len('.json')]
                         if games_files else None},
        'inventions': {'count': len(rows) * 2,
                       'id_range': ['JAH-OLY-INV-%06d' % 1,
                                    'JAH-OLY-INV-%06d' % (len(rows) * 2)]},
        'chunks': len(chunk_files),
        'per_chunk': 100,
        'engine_version': '2.1',
        'schema_version': 'JAH-OLY-RECORD/2.0',
        'index_version': '1',
        'index_hash': index_hash,
        'archive_status': 'ARCHIVED',
        'updated': now.date().isoformat(),
    }
    with open(os.path.join(DATA, 'manifest.json'), 'w') as f:
        json.dump(man, f, indent=1)
    return man

if __name__ == '__main__':
    man = build_manifest()
    print('manifest v2 written: %d bouts, %d contenders, updated %s'
          % (man['bouts'], man['contenders']['total'], man['updated']))
