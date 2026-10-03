#!/usr/bin/env python3
"""Shared bout-record utilities for the Olypics pipeline.

canon()/content_hash() MUST match code/qa_engine.js canonJSON/contentHash
(sorted keys, no spaces, UTF-8, minus the content_hash field itself) and the
browser-side olyCanon() in index.html. Change in all four places or not at all.
"""
import json
import hashlib


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def content_hash(rec):
    r = {k: v for k, v in rec.items() if k != 'content_hash'}
    return 'sha256:' + hashlib.sha256(canon(r)).hexdigest()
