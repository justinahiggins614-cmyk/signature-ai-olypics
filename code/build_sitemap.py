#!/usr/bin/env python3
"""Build sitemap.xml: home + one ?battle= URL per bout (from data/index.json.gz)."""
import json, gzip, os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = 'https://justinahiggins614-cmyk.github.io/signature-ai-olypics'
today = date.today().isoformat()

ids = []
with gzip.open(os.path.join(ROOT, 'data', 'index.json.gz'), 'rt') as f:
    for line in f:
        if line.strip():
            ids.append(json.loads(line)[0])

urls = [f'<url><loc>{BASE}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq></url>']
for bid in ids:
    urls.append(f'<url><loc>{BASE}/?battle={bid}</loc><lastmod>{today}</lastmod></url>')

sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
      + '\n'.join(urls) + '\n</urlset>\n')
open(os.path.join(ROOT, 'sitemap.xml'), 'w').write(sm)
print(f"sitemap: {len(urls)} URLs")
