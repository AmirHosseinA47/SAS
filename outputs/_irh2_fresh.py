"""Fresh-seed check: none vs hardlc on seeds never used to tune anything here.

The canonical 13 are the sample the hole was measured on, so they are also the
sample a fix would be over-fitted to.  east/half and south/half, seeds
1111..5555, 240 steps, same params.
"""
from __future__ import annotations
import json, os, sys

OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, OUT)
from _irh2_analyse import tight_reversals, attribute, reset_sites_paired, key

CELLS = ([("fh", s) for s in (1111, 2222, 3333, 4444, 5555)]
         + [("fs", s) for s in (1111, 2222, 3333, 4444, 5555)])


def load(tag, pre):
    p = os.path.join(OUT, "%s%s.json" % (pre, tag))
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p) as f:
        return json.load(f)


def ev(d, seed):
    e = [x for x in d["evals"] if x["seed"] == seed][0]
    return (e["rescued"], e["dead"], e["firefighter_deaths"])


def trace(d):
    return [(r["seed"], r["step"], r["ff"], key(r["pos"]), r["dead"])
            for r in d["fftrace"]]


def first_div(a, b):
    for x, y in zip(trace(a), trace(b)):
        if x != y:
            return x
    return None


def main():
    tn = [0, 0, 0]
    th = [0, 0, 0]
    revn = revh = holn = holh = 0
    ndiv = 0
    n = 0
    missing = []
    print("=" * 78)
    print("FRESH SEEDS (never used to tune this round): none vs hardlc")
    print("=" * 78)
    print("\n  run          none        hardlc      trace         tight rev   hole")
    for tag, seed in CELLS:
        a = load("%s_%s_none" % (tag, seed), "_irh2_")
        b = load("%s_%s_hardlc" % (tag, seed), "_irh2h_")
        if a is None or b is None:
            missing.append("%s_%s" % (tag, seed))
            print("  %-12s INCOMPLETE" % ("%s_%s" % (tag, seed)))
            continue
        reset_sites_paired(a)
        reset_sites_paired(b)
        ra = attribute(a, tight_reversals(a))
        rb = attribute(b, tight_reversals(b))
        ha = sum(1 for x in ra if x["class"].startswith("HOLE"))
        hb = sum(1 for x in rb if x["class"].startswith("HOLE"))
        ea, eb = ev(a, seed), ev(b, seed)
        d = first_div(a, b)
        ndiv += (d is not None)
        n += 1
        for i in range(3):
            tn[i] += ea[i]
            th[i] += eb[i]
        revn += len(ra); revh += len(rb); holn += ha; holh += hb
        print("  %-12s r%d/d%d/ff%d   r%d/d%d/ff%d   %-13s %3d->%-3d   %d->%d"
              % ("%s_%s" % (tag, seed), ea[0], ea[1], ea[2], eb[0], eb[1], eb[2],
                 "same" if d is None else "DIFFERS s%d" % d[1],
                 len(ra), len(rb), ha, hb))
    print("  %-12s r%d/d%d/ff%d   r%d/d%d/ff%d   %-13s %3d->%-3d   %d->%d"
          % ("TOTAL", tn[0], tn[1], tn[2], th[0], th[1], th[2],
             "%d/%d differ" % (ndiv, n), revn, revh, holn, holh))
    if missing:
        print("\n  !! MISSING: %s" % missing)

    print("\n  per-seed outcome deltas (hardlc - none):")
    worse = better = 0
    for tag, seed in CELLS:
        a = load("%s_%s_none" % (tag, seed), "_irh2_")
        b = load("%s_%s_hardlc" % (tag, seed), "_irh2h_")
        if a is None or b is None:
            continue
        ea, eb = ev(a, seed), ev(b, seed)
        if ea == eb:
            continue
        v = []
        if eb[0] > ea[0]: v.append("gained a rescue"); better += 1
        if eb[0] < ea[0]: v.append("LOST A RESCUE"); worse += 1
        if eb[2] < ea[2]: v.append("fewer ff deaths"); better += 1
        if eb[2] > ea[2]: v.append("MORE FF DEATHS"); worse += 1
        print("    %-12s rescued %d->%d  victims dead %d->%d  ff %d->%d   %s"
              % ("%s_%s" % (tag, seed), ea[0], eb[0], ea[1], eb[1], ea[2], eb[2],
                 " / ".join(v) or "neutral"))
    print("\n  fresh seeds where blocking the reversal HELPED: %d   HURT: %d"
          % (better, worse))


main()
