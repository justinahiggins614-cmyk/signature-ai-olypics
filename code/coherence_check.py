#!/usr/bin/env python3
"""AI Olympics canon-coherence check (build-time, fails loudly).

Verifies everything the battle dome presents about an AI matches the
phone-book canon (jah-ai-models/ai-catalog.json) exactly:
  1. data/contenders.json — 383 fighters expected (260 phone-book +
     120 mixlab hybrids + 3 industry-style replicas).
     * phone-book contenders: id, name, type, blurb (first-120-chars rule,
       same as JAHtalk.canonIssues) match the canon record.
     * mixlab hybrids: parents[] ids exist in the canon; parent names in
       the blurb match canon names.
     * replicas: blurb must keep the "independent interpretation, not
       affiliated" framing and never claim to be the real product.
  2. data/chunks/*.jsonl.gz — every bout's contender records resolve to
     the checked roster (no drift between roster and battle records).
  3. Narrative scan: no battle narrative looks like a machine stat dump
     (KEY=VALUE runs) — the dome scribe runs every reply through
     JAHtalk.guard, but the source records should be clean too.

Exit 0 = COHERENT. Any issue -> print and exit 1 (fails loudly).
Run after every drip that touches data/ (seed.py), before the push.
"""
import gzip, glob, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.environ.get("CANON_PATH",
    os.path.expanduser("~/workspace/jah-ai-models/ai-catalog.json"))

EXPECTED_REPLICAS = {
    "JAH-AI-REP-001": ("The Constellation", "Google"),
    "JAH-AI-REP-002": ("The Chatwright", "OpenAI"),
    "JAH-AI-REP-003": ("The Appwright", "Base44"),
}

issues = []

def fail(msg):
    issues.append(msg)

def norm(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()

def looks_like_dump(x):
    x = str(x or "")
    kv = re.findall(r"\b[A-Z][A-Z0-9_]{2,}=[^\s|]+", x)
    if len(kv) >= 2:
        return True
    if x.count("|") >= 3 and "=" in x:
        return True
    if re.search(r"UPTIME=|STORAGE=|TOLERANCE=|CPC=|DIM_[A-Z]+=", x):
        return True
    return False

def main():
    if not os.path.exists(CANON):
        print("COHERENCE CHECK ABORTED: canon not found at", CANON)
        return 1
    canon = json.load(open(CANON))["records"]
    by_id = {r["ID"]: r for r in canon}

    roster = json.load(open(os.path.join(REPO, "data", "contenders.json")))
    print("contenders.json: %d fighters" % len(roster))

    by_rost = {}
    counts = {"phone-book": 0, "mixlab": 0, "replica": 0}
    for c in roster:
        cid, cname, src = c.get("id"), c.get("name"), c.get("source")
        if cid in by_rost:
            fail("duplicate contender id %s" % cid)
        by_rost[cid] = c
        counts[src] = counts.get(src, 0) + 1
        if src == "phone-book":
            r = by_id.get(cid)
            if r is None:
                fail("contender %s not in phone-book canon" % cid)
                continue
            if cname != r["NAME"]:
                fail("name drift %s: dome %r, canon %r" % (cid, cname, r["NAME"]))
            if str(c.get("type", "")).lower() != str(r["TYPE"]).lower():
                fail("type drift %s: dome %r, canon %r" % (cid, c.get("type"), r["TYPE"]))
            if norm(c.get("blurb"))[:120] != norm(r["DESCRIPTION"])[:120]:
                fail("description drift %s (first 120 chars differ)" % cid)
        elif src == "mixlab":
            if not re.fullmatch(r"JAH-MIX-\d{6}", cid or ""):
                fail("bad hybrid id %r" % cid)
            for pid in (c.get("parents") or []):
                r = by_id.get(pid)
                if r is None:
                    fail("hybrid %s parent %s not in canon" % (cid, pid))
                elif r["NAME"] not in norm(c.get("blurb")):
                    fail("hybrid %s blurb drops canon parent name %r" % (cid, r["NAME"]))
            if "Shared record with the AI Mix Lab." not in str(c.get("blurb")):
                fail("hybrid %s blurb lost Mix Lab cross-link" % cid)
        elif src == "replica":
            exp = EXPECTED_REPLICAS.get(cid)
            if exp is None:
                fail("unknown replica id %s" % cid)
                continue
            ename, ecompany = exp
            if cname != ename:
                fail("replica name drift %s: %r vs expected %r" % (cid, cname, ename))
            blurb = norm(c.get("blurb"))
            if "independent interpretation, not affiliated" not in blurb:
                fail("replica %s lost its not-affiliated framing" % cid)
            if ecompany.lower() not in blurb.lower():
                fail("replica %s lost its %s disclaimer" % (cid, ecompany))
        else:
            fail("contender %s has unexpected source %r" % (cid, src))

    if len(roster) != 383:
        fail("roster count %d != 383 (260 + 120 + 3)" % len(roster))
    for k, want in (("phone-book", 260), ("mixlab", 120), ("replica", 3)):
        if counts.get(k, 0) != want:
            fail("roster source %s: %d != %d" % (k, counts.get(k, 0), want))
    print("  roster mix: %s" % counts)

    # index.html contenders section must present the same replicas + framing
    page = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
    for cid, (ename, ecompany) in EXPECTED_REPLICAS.items():
        if ename not in page:
            fail("index.html lost replica %r" % ename)
    if "independent interpretation, not affiliated" not in page:
        fail("index.html lost replica not-affiliated framing")

    # ---- bouts chunks: contender records resolve to the checked roster ----
    chunks = sorted(glob.glob(os.path.join(REPO, "data", "chunks", "*.jsonl.gz")))
    nb = ndump = 0
    for ch in chunks:
        with gzip.open(ch, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                b = json.loads(line)
                nb += 1
                for c in b.get("contenders", []) + [b.get("winner"), b.get("loser")]:
                    if not c:
                        continue
                    rc = by_rost.get(c.get("id"))
                    if rc is None:
                        fail("bout %s contender %s not in roster" % (b.get("id"), c.get("id")))
                    elif c.get("name") != rc.get("name"):
                        fail("bout %s contender name drift %r" % (b.get("id"), c.get("name")))
                if looks_like_dump(b.get("narrative")):
                    ndump += 1
                    if ndump == 1:
                        fail("bout %s narrative looks like a stat dump" % b.get("id"))
    print("battle chunks: %d bouts in %d files (dump-like narratives: %d)" % (nb, len(chunks), ndump))

    if issues:
        print("\nCANON DRIFT DETECTED (%d issues):" % len(issues))
        for i in issues[:40]:
            print("  -", i)
        if len(issues) > 40:
            print("  ... and %d more" % (len(issues) - 40))
        return 1
    print("\nCOHERENCE OK: %d contenders + %d bouts — all canon-coherent, replicas framed." %
          (len(roster), nb))
    return 0

if __name__ == "__main__":
    sys.exit(main())
