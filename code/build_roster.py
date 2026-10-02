#!/usr/bin/env python3
"""Build data/contenders.json: Signature AIs (from the phone book catalog) +
3 industry-style replicas (clearly labeled) + deterministic hybrids (JAH-MIX-######,
shared ID scheme with the Mix Lab sister site)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
os.makedirs(DATA, exist_ok=True)

cat = json.load(open(os.path.expanduser('~/workspace/jah-ai-models/ai-catalog.json')))
roster = []
for r in cat['records']:
    roster.append({
        'id': r['ID'],
        'name': r['NAME'],
        'type': r['TYPE'],  # system | persona | domain
        'blurb': r['DESCRIPTION'][:220],
        'source': 'phone-book',
    })

# Industry-style replicas: ORIGINAL Signature creations evoking the archetype.
# Clearly labeled independent interpretations — never the real products.
replicas = [
    {'id': 'JAH-AI-REP-001', 'name': 'The Constellation',
     'type': 'replica',
     'blurb': 'Constellation-class conversationalist in the Gemini mold. Signature replica — independent interpretation, not affiliated with Google.',
     'source': 'replica'},
    {'id': 'JAH-AI-REP-002', 'name': 'The Chatwright',
     'type': 'replica',
     'blurb': 'Chat-style assistant in the ChatGPT mold. Signature replica — independent interpretation, not affiliated with OpenAI.',
     'source': 'replica'},
    {'id': 'JAH-AI-REP-003', 'name': 'The Appwright',
     'type': 'replica',
     'blurb': 'App-builder in the Base44 mold. Signature replica — independent interpretation, not affiliated with Base44.',
     'source': 'replica'},
]
roster.extend(replicas)

# Deterministic hybrids: seeded pairs of catalog AIs.
# JAH-MIX-###### IDs are SHARED with the Mix Lab sister site (same pair -> same ID).
import hashlib
sigs = [r for r in roster if r['source'] == 'phone-book']
hybrids = []
for i in range(120):
    h = hashlib.sha256(f'mixlab-pair-{i}'.encode()).hexdigest()
    a = sigs[int(h[:8], 16) % len(sigs)]
    b = sigs[int(h[8:16], 16) % len(sigs)]
    if b['id'] == a['id']:
        b = sigs[(sigs.index(b) + 7) % len(sigs)]
    hybrids.append({
        'id': f'JAH-MIX-{i+1:06d}',
        'name': f"{a['name']} x {b['name']}",
        'type': 'hybrid',
        'blurb': f"Mix-and-match hybrid of {a['name']} ({a['id']}) and {b['name']} ({b['id']}). Shared record with the AI Mix Lab.",
        'source': 'mixlab',
        'parents': [a['id'], b['id']],
    })
roster.extend(hybrids)

json.dump(roster, open(os.path.join(DATA, 'contenders.json'), 'w'), indent=1)
print(f"roster: {len(roster)} contenders "
      f"({sum(1 for r in roster if r['type']=='system')} systems, "
      f"{sum(1 for r in roster if r['type']=='persona')} personas, "
      f"{sum(1 for r in roster if r['type']=='domain')} domain, "
      f"{sum(1 for r in roster if r['type']=='replica')} replicas, "
      f"{sum(1 for r in roster if r['type']=='hybrid')} hybrids)")
