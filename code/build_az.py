#!/usr/bin/env python3
"""Per-letter A-Z archive builder for the AI Olypics bout catalog.

Feeds the "Every battle, A-Z by mission" section of bouts.html (plus the
Weekly Games mode). Row layout: [bout_id, mission, stage_name], sorted by
(mission, bout_id). One gz JSONL file per letter at data/index/az/<L>.json.gz
(+ manifest.json {total, built, counts} and games.json for the Weekly Games
mode) so phones lazy-load one letter at a time.

Called from code/build_sitemap.py (which already parses every bout, so the
rows are passed in and no second full scan is needed). Also runnable
standalone: python3 code/build_az.py
"""
import gzip
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
AZDIR = os.path.join(DATA, "index", "az")
LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)] + ["#"]


def az_letter(title):
    t = (title or "").strip().upper()
    for ch in t:
        if "A" <= ch <= "Z":
            return ch
        if ch.isalpha():
            return "#"
    return "#"


def write_az(az_rows, games):
    """Write per-letter gz files + manifest.json + games.json.

    az_rows: iterable of [bout_id, mission, stage_name].
    games: list of dicts {games_id, week, week_start, bout_count, contenders}.
    """
    os.makedirs(AZDIR, exist_ok=True)
    buckets = {}
    for r in az_rows:
        buckets.setdefault(az_letter(r[1]), []).append([r[0], r[1], r[2] or ""])
    counts = {}
    for letter, rows in buckets.items():
        rows.sort(key=lambda r: (r[1].lower(), r[0]))
        with gzip.open(os.path.join(AZDIR, letter + ".json.gz"), "wt",
                       encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False,
                                   separators=(",", ":")) + "\n")
        counts[letter] = len(rows)
    total = sum(counts.values())
    n_in = len(az_rows)
    if total != n_in:
        print("ERROR: A-Z archive row count mismatch (%d vs %d)"
              % (total, n_in), file=sys.stderr)
        sys.exit(1)
    manifest = {"total": total, "built": date.today().isoformat(),
                "counts": {k: counts[k] for k in sorted(counts)}}
    with open(os.path.join(AZDIR, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"))
    grows = [{"id": g.get("games_id"), "week": g.get("week"),
              "week_start": g.get("week_start"),
              "bout_count": g.get("bout_count"),
              "contenders": g.get("contenders")} for g in (games or [])]
    with open(os.path.join(AZDIR, "games.json"), "w",
              encoding="utf-8") as f:
        json.dump(grows, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = sum(os.path.getsize(os.path.join(AZDIR, l + ".json.gz"))
                  for l in counts) / 1e6
    print("WROTE data/index/az/: %d letter files, %d bouts, %.1fMB gz, %d games"
          % (len(counts), total, size_mb, len(grows)))
    return manifest


def iter_rows():
    rows = []
    chunkdir = os.path.join(DATA, "chunks")
    for f_ in sorted(os.listdir(chunkdir)):
        if not f_.endswith(".jsonl.gz"):
            continue
        with gzip.open(os.path.join(chunkdir, f_), "rt",
                       encoding="utf-8") as g:
            for line in g:
                line = line.strip()
                if not line:
                    continue
                b = json.loads(line)
                st = b.get("stage", {}) or {}
                rows.append([b["id"], b.get("mission", ""),
                             st.get("name", st.get("key", ""))])
    return rows


def load_games():
    p = os.path.join(DATA, "games", "index.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def main():
    rows = iter_rows()
    games = load_games()
    write_az(rows, games)


if __name__ == "__main__":
    main()
