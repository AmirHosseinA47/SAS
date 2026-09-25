"""Verifier for finding D3-1. Read-only. For the 6 geo markings in the shipped-config
(ug*/uh*) runs, list over the streak window [s-29, s] every step where any live unit was
exiting, and whether the marked victim was ever in custody. Also compute, per run, the
longest custody streak (consecutive carrying steps of one victim during which NO live,
on-grid, non-exiting unit's burning-only BFS covers the carrier cell) - i.e. how close the
shipped config comes to D3. Named top-level files only (non-recursive glob)."""
import glob, json, os, re, sys
from collections import deque

OUT = r"E:\Projects\SAS\outputs"
W = H = 50
pat = re.compile(r"^_ffr_([A-Za-z0-9]+)_(east|south|west|north)_(half|def)_(\d+)\.json$")


def burning_sets(d, nsteps):
    per = [set() for _ in range(nsteps + 2)]
    for key, ivs in (d.get("burn_intervals") or {}).items():
        x, y = key.split(",")
        c = (int(x), int(y))
        for s, e in ivs:
            hi = nsteps + 1 if e is None else min(e, nsteps + 1)
            for t in range(max(0, s), hi):
                per[t].add(c)
    return per


def bfs(starts, burning):
    seen = set()
    q = deque()
    for s in starts:
        s = tuple(s)
        if s in burning or s in seen or not (0 <= s[0] < W and 0 <= s[1] < H):
            continue
        seen.add(s); q.append(s)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < W and 0 <= n[1] < H and n not in seen and n not in burning:
                seen.add(n); q.append(n)
    return seen


TAGS = sys.argv[2].split(",")
files = sorted(sum((glob.glob(os.path.join(OUT, "_ffr_%s_*.json" % t)) for t in TAGS), []))
mode = sys.argv[1] if len(sys.argv) > 1 else "window"
tot = 0
maxrows = []
for f in files:
    bn = os.path.basename(f)
    m = pat.match(bn)
    if not m or bn.endswith(".xstrace.json"):
        continue
    tot += 1
    d = json.load(open(f, encoding="utf-8"))
    ffs = d["ff_steps"]
    binds = d.get("ff_bind_steps")
    n = len(ffs)
    geo = [e for e in d.get("unreachable_escape_log", []) if e.get("cause") == "geographically_isolated"]
    if mode == "window":
        for e in geo:
            s = int(e["step"])
            print("==", bn, e["victim_id"], "@", s, "steps", n)
            for t in range(max(1, s - 29), s + 1):
                row = ffs[t - 1]
                b = {r[0]: r[1] for r in (binds[t - 1] if binds else [])}
                ex = [(r[0], r[1], b.get(r[0])) for r in row if r[4] and not r[5]]
                alive = [(r[0], r[1], r[2]) for r in row if not r[5]]
                if ex or t in (s - 29, s):
                    print("   t=%d alive=%s exiting=%s" % (t, alive, ex))
    else:
        if not binds:
            continue
        burn = burning_sets(d, n)
        best = (0, None)
        cur = {}
        for t in range(1, n + 1):
            row = ffs[t - 1]
            b = {r[0]: r[1] for r in binds[t - 1]}
            living = [tuple(r[1]) for r in row if not r[5] and str(r[2]).lower() != "dead" and not r[4] and r[1] is not None]
            carriers = [(r[0], tuple(r[1]), b.get(r[0])) for r in row if not r[5] and r[4] and r[1] is not None and b.get(r[0])]
            region = bfs(living, burn[t]) if carriers else set()
            newcur = {}
            for uid, cell, v in carriers:
                if cell in region:
                    continue
                k = (uid, v)
                newcur[k] = cur.get(k, 0) + 1
                if newcur[k] > best[0]:
                    best = (newcur[k], (uid, v, t, len(living)))
            cur = newcur
        maxrows.append((best[0], bn, n, best[1]))
if mode != "window":
    maxrows.sort(reverse=True)
    print("runs", len(maxrows), "of", tot)
    for r in maxrows[:25]:
        print(r)
    import collections
    hist = collections.Counter(min(r[0] // 5 * 5, 30) for r in maxrows)
    print("hist (bucket of 5):", sorted(hist.items()))
    print("360-step runs:", sum(1 for r in maxrows if r[2] >= 360), "max streak among them:",
          max((r[0] for r in maxrows if r[2] >= 360), default=None))
