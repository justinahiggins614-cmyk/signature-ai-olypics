#!/usr/bin/env python3
"""Amend pass: add top-level stage_id/stage_version/criteria_id/rubric_version
to migrated chunks so they match the engine v2 record shape exactly, then
recompute content_hash. Verifies battle data untouched."""
import gzip, json, glob, hashlib, os, tempfile

CHUNKS = 'data/chunks'

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')

def content_hash(rec):
    r = {k: v for k, v in rec.items() if k != 'content_hash'}
    return 'sha256:' + hashlib.sha256(canon(r)).hexdigest()

total = 0
for p in sorted(glob.glob(os.path.join(CHUNKS, 'bouts-c*.jsonl.gz'))):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        recs = [json.loads(l) for l in f if l.strip()]
    for b in recs:
        wid_before, margin_before = b['winner']['id'], b['margin']
        b['stage_id'] = b['stage']['id']
        b['stage_version'] = b['stage']['version']
        b['criteria_id'] = b['criteria']['id']
        b['rubric_version'] = b['criteria']['version']
        b['content_hash'] = content_hash(b)
        assert b['winner']['id'] == wid_before and b['margin'] == margin_before
        total += 1
    fd, tmp = tempfile.mkstemp(dir=CHUNKS, suffix='.tmp')
    os.close(fd)
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        for b in recs:
            f.write(json.dumps(b, ensure_ascii=False) + '\n')
    os.replace(tmp, p)
print('AMEND OK:', total, 'bouts')
