"""Offline: distribution of |pos - origin| at survival_move calls, and how
much of the leash exclusion is explained by a PROVABLY stale origin (d>6).

Invariant being tested: _survival_move alone can never leave the unit more
than IDLE_RETREAT_MAX_CELLS from its own origin (origin is set to `cell`, and
every move it makes passed `from_origin <= 6`). So d>6 proves some OTHER
mechanism moved the unit, i.e. the origin is stale by construction.
"""
import json, sys, collections

MAX = 6

def md(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

tot = collections.Counter()
dhist = collections.Counter()
dhist_idle = collections.Counter()
zero_rows = []
latched_rows = []

for path in sys.argv[1:]:
    d = json.load(open(path))
    tag = path.split('_sb_')[-1].replace('.json','')
    for s in d["surv"]:
        pos = s.get("pos"); org = s.get("origin")
        if pos is None:
            continue
        pos = tuple(pos)
        tot["calls"] += 1
        if org is None:
            dhist["origin_None"] += 1
            if s.get("idle"): dhist_idle["origin_None"] += 1
            continue
        dd = md(pos, tuple(org))
        dhist[dd] += 1
        if s.get("idle"): dhist_idle[dd] += 1
        if dd > MAX:
            tot["calls_with_provably_stale_origin"] += 1
            if s.get("idle"): tot["idle_calls_with_provably_stale_origin"] += 1
        row = dict(s); row["d_origin"] = dd; row["tag"] = tag
        if s.get("n_candidates") == 0:
            zero_rows.append(row)
        if s.get("idle") and s.get("stalled_pre"):
            latched_rows.append(row)

print("=" * 74)
print("A. |pos - origin| distribution over ALL _survival_move calls")
print("=" * 74)
print("total calls with pos:", tot["calls"])
print("  d histogram (all)  :", dict(sorted(dhist.items(), key=lambda kv: str(kv[0]))))
print("  d histogram (idle) :", dict(sorted(dhist_idle.items(), key=lambda kv: str(kv[0]))))
print("  calls where d > %d (PROVABLY stale origin): %d  (idle: %d)"
      % (MAX, tot["calls_with_provably_stale_origin"],
         tot["idle_calls_with_provably_stale_origin"]))

print()
print("=" * 74)
print("B. zero-candidate events: is the leash exclusion explained by d>6?")
print("=" * 74)
print("zero-candidate events total:", len(zero_rows))
c = collections.Counter()
for r in zero_rows:
    free = r.get("n_free") or 0
    c["free>0" if free else "free==0 (genuine enclosure)"] += 1
    if free:
        if (r.get("excl_leash") or 0) > 0:
            c["  leash excluded >=1"] += 1
            c["    and d>6 (stale)" if r["d_origin"] > MAX
              else "    and d<=6 (leash working as designed)"] += 1
        if (r.get("excl_lastcell") or 0) > 0:
            c["  lastcell excluded >=1"] += 1
for k in sorted(c):
    print("  %-45s %d" % (k, c[k]))

print()
print("  detail of zero-candidate events with a free cell available:")
print("  %-16s %5s %4s %-9s %-9s %3s %3s %5s %5s %5s %5s" % (
    "tag/seed/ff", "step", "d", "pos", "origin",
    "free", "cand", "xfire", "xlast", "xlsh", "idle"))
for r in sorted(zero_rows, key=lambda r: (r["tag"], r["seed"], r["step"])):
    if (r.get("n_free") or 0) == 0:
        continue
    print("  %-16s %5d %4d %-9s %-9s %3d %4d %5d %5d %5d %5s" % (
        "%s/%s/%s" % (r["tag"][:6], r["seed"], r["ff"][-6:]),
        r["step"], r["d_origin"], str(tuple(r["pos"])), str(tuple(r["origin"])),
        r.get("n_free") or 0, r.get("n_candidates") or 0,
        r.get("excl_fire") or 0, r.get("excl_lastcell") or 0,
        r.get("excl_leash") or 0, r.get("idle")))

print()
print("=" * 74)
print("C. ALREADY-LATCHED idle calls: what would revalidation see?")
print("=" * 74)
print("latched idle calls:", len(latched_rows))
c2 = collections.Counter()
for r in latched_rows:
    free = r.get("n_free") or 0
    xl = r.get("excl_lastcell") or 0
    c2["latched"] += 1
    if free == 0:
        c2["  no free neighbour at all (genuinely enclosed)"] += 1
        continue
    c2["  free neighbour existed"] += 1
    if r.get("strictly_better_exists"):
        c2["    strictly better free cell existed"] += 1
        # after re-anchor the leash cannot exclude (all neighbours d=1)
        if free - xl > 0:
            c2["      survives last_cell exclusion -> WOULD MOVE"] += 1
        else:
            c2["      only free cell was last_cell -> would stay latched"] += 1
    else:
        c2["    no strictly better cell -> would stay latched (by design)"] += 1
    if r["d_origin"] > MAX:
        c2["    (of which origin provably stale d>6)"] += 1
for k in sorted(c2):
    print("  %-58s %d" % (k, c2[k]))
