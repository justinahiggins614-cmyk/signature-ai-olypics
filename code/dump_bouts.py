#!/usr/bin/env python3
"""Dump archived bouts by n for reproducibility checks."""
import gzip, json, sys
want = set(int(x) for x in sys.argv[1:])
import glob
for p in sorted(glob.glob('data/chunks/bouts-c*.jsonl.gz')):
    with gzip.open(p, 'rt') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            b = json.loads(line)
            if b['n'] in want:
                print(json.dumps(b))
                want.discard(b['n'])
    if not want:
        break
