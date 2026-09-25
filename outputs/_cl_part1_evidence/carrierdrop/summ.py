import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "scan.json"), encoding="utf-8") as f:
    S = json.load(f)
drops = S["drops"]
print("drops by reason:", collections.Counter(d["reason"] for d in drops))
print("drops by reason, probe files excluded:", collections.Counter(d["reason"] for d in drops if not d["file"].startswith("_ffr_xs")))
# distinct drops: (tuple, cls, ff, vid, step, cell, reason)
dist = {}
for d in drops:
    if d["file"].startswith("_ffr_xs"):
        continue
    key = (tuple(d["tup"]), d["cls"], d["ff"], d["vid"], d["step"], tuple(d["cell"]) if d["cell"] else None, d["reason"])
    dist.setdefault(key, []).append(d)
print("distinct drops (non-probe):", len(dist), collections.Counter(k[-1] for k in dist))
for reason in sorted(set(k[-1] for k in dist)):
    ks = [k for k in dist if k[-1] == reason]
    nrep = sum(len(dist[k][0]["reps"]) for k in ks)
    nrep_occ = sum(len(x["reps"]) for k in ks for x in dist[k])
    contact = sum(1 for k in ks for r in dist[k][0]["reps"] if r["contact"] is not None)
    resc = sum(1 for k in ks for r in dist[k][0]["reps"] if r["rescued"])
    anyresc = sum(1 for k in ks if dist[k][0]["rescued_by_any"])
    ffdead = sum(1 for k in ks if dist[k][0]["ff_dead_at_drop"])
    vfinal = collections.Counter(dist[k][0]["vfinal"] for k in ks)
    print("\nREASON %s: %d distinct drops (%d file-occurrences); carrier dead at drop step %d; victim final %s" % (
        reason, len(ks), sum(len(dist[k]) for k in ks), ffdead, dict(vfinal)))
    print("   replacement assigns after the drop: %d distinct (%d file-occurrences); reached victim cell %d; rescued %d; victim rescued by anyone later %d" % (
        nrep, nrep_occ, contact, resc, anyresc))
    dd = [r["d0"] for k in ks for r in dist[k][0]["reps"]]
    print("   replacement distance at assign:", sorted(x for x in dd if x is not None))
    best = [r["best"] for k in ks for r in dist[k][0]["reps"]]
    print("   closest approach:", sorted(x for x in best if x is not None), "none:", sum(1 for x in best if x is None))
    lag = [(dist[k][0]["vdeath"] - dist[k][0]["step"]) if dist[k][0]["vdeath"] else None for k in ks]
    print("   victim death minus drop step:", collections.Counter(lag))
    for k in sorted(ks, key=lambda k: (k[0], k[4])):
        x = dist[k][0]
        tags = sorted(set(y["tag"] for y in dist[k]))
        print("     %s/%s/%s %s %s %s drop@%d cell %s ffdead=%s vdeath=%s vfinal=%s reps=%s tags(%d)=%s" % (
            k[0][0], k[0][1], k[0][2], k[1], x["ff"], x["vid"], x["step"], x["cell"], x["ff_dead_at_drop"], x["vdeath"], x["vfinal"],
            [(r["step"], r["ff"], r["reason"], r["d0"], r["best"], r["contact"], r["rescued"]) for r in x["reps"]],
            len(dist[k]), ",".join(tags)[:160]))
