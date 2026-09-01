"""route_blocked gate, THIS round's delta: lcfix (patched) vs irfix (b6527f7).

`_ir_rbmerge.py --prefix lcfix` answers the gate as originally defined, against
the 70e1b33 baseline.  This script answers the narrower question the round
actually needs: did the last_cell change move anything relative to the HEAD it
was branched from?

Read-only.
"""
from __future__ import annotations
import collections, glob, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))

# _ir_rbmerge.py runs its own main() at import time, so its two helpers are
# reproduced here rather than imported.  Same definitions.


def merge(paths):
    out = {"evals": [], "stats": collections.Counter(),
           "exact": collections.Counter(), "exact_fires": [],
           "exact_recoveries": [], "fires": [], "recoveries": [],
           "assigns": [], "latched": [], "deaths": [], "shards": []}
    for p in sorted(paths):
        with open(p) as f:
            d = json.load(f)
        out["shards"].append((os.path.basename(p), d["seeds"]))
        out["evals"].extend(d.get("evals") or [])
        out["stats"].update(d.get("stats") or {})
        out["exact"].update(d.get("exact") or {})
        for k in ("exact_fires", "exact_recoveries", "fires", "recoveries",
                  "assigns", "latched", "deaths"):
            out[k].extend(d.get(k) or [])
    return out


def by_seed(evals):
    return {int(e["seed"]): (int(e.get("rescued") or 0),
                             int(e.get("dead") or 0),
                             int(e.get("firefighter_deaths") or 0))
            for e in evals}


def shards(prefix, wind):
    return glob.glob(os.path.join(
        BASE, "_rblatch_camp2_%s*_D_%s.json" % (prefix, wind)))


grand = {"irfix": [0, 0, 0], "lcfix": [0, 0, 0]}
exact = {"irfix": collections.Counter(), "lcfix": collections.Counter()}
latched = {"irfix": [], "lcfix": []}
diffs = []

for wind in ("east", "south"):
    got = {}
    for pre in ("irfix", "lcfix"):
        sh = shards(pre, wind)
        if not sh:
            print("MISSING %s shards for %s" % (pre, wind))
            got[pre] = None
            continue
        got[pre] = merge(sh)
    if not all(got.values()):
        continue
    b, f = by_seed(got["irfix"]["evals"]), by_seed(got["lcfix"]["evals"])
    seeds = sorted(set(b) | set(f))
    print("=" * 78)
    print("D/%s   b6527f7 (idle-retreat HEAD)  ->  + last_cell fix" % wind)
    print("  irfix shards: %s" % "; ".join("%s[%s]" % s for s in got["irfix"]["shards"]))
    print("  lcfix shards: %s" % "; ".join("%s[%s]" % s for s in got["lcfix"]["shards"]))
    if sorted(b) != sorted(f):
        print("  !! SEED SET MISMATCH  irfix=%s lcfix=%s" % (sorted(b), sorted(f)))
    else:
        print("  seed sets match exactly (%d seeds, no dupes)" % len(seeds))
    print("=" * 78)
    same = 0
    for s in seeds:
        eb, ef = b.get(s), f.get(s)
        if eb is None or ef is None:
            print("  %-5s MISSING" % s)
            continue
        for i in range(3):
            grand["irfix"][i] += eb[i]
            grand["lcfix"][i] += ef[i]
        if eb == ef:
            same += 1
        else:
            diffs.append((wind, s, eb, ef))
        print("  seed %-5s r%d/d%d/ff%d -> r%d/d%d/ff%d %s"
              % (s, eb[0], eb[1], eb[2], ef[0], ef[1], ef[2],
                 "" if eb == ef else "  <-- changed"))
    print("  bit-identical on all three metrics: %d/%d" % (same, len(seeds)))
    for pre in ("irfix", "lcfix"):
        exact[pre].update(got[pre]["exact"])
        latched[pre].extend(got[pre]["latched"])
    print("  mechanics:")
    for k in ("fires", "recoveries", "reval_calls", "reval_calls_with_blocked_unit"):
        print("    %-32s %6s -> %6s"
              % (k, got["irfix"]["exact"].get(k, 0), got["lcfix"]["exact"].get(k, 0)))
    print("    %-32s %6d -> %6d" % ("end-of-run units still blocked",
                                    len(got["irfix"]["latched"]),
                                    len(got["lcfix"]["latched"])))
    print()

print("=" * 78)
print("ALL 18 RUNS   b6527f7 r%d/d%d/ff%d  ->  patched r%d/d%d/ff%d"
      % (tuple(grand["irfix"]) + tuple(grand["lcfix"])))
print("  deltas: rescued %+d, victims dead %+d, firefighter_deaths %+d"
      % (grand["lcfix"][0] - grand["irfix"][0],
         grand["lcfix"][1] - grand["irfix"][1],
         grand["lcfix"][2] - grand["irfix"][2]))
print("  seeds changed by this round: %s" % ([d[:2] for d in diffs] or "none"))
print("  units still route_blocked at end of run: %d -> %d"
      % (len(latched["irfix"]), len(latched["lcfix"])))
print("=" * 78)


def east333():
    """The case the route_blocked round was built around."""
    print()
    print("EAST / SEED 333 - the case 70e1b33 was built around")
    for pre in ("irfix", "lcfix"):
        sh = shards(pre, "east")
        if not sh:
            print("  %s: no data" % pre)
            continue
        m = merge(sh)
        ev = [e for e in m["evals"] if int(e["seed"]) == 333]
        fires = [x for x in m["exact_fires"] if int(x.get("seed", -1)) == 333]
        rec = [x for x in m["exact_recoveries"] if int(x.get("seed", -1)) == 333]
        if not ev:
            print("  %s: seed 333 not in this shard set" % pre)
            continue
        e = ev[0]
        print("  %-6s rescued=%s dead=%s ff_deaths=%s" % (
            pre, e.get("rescued"), e.get("dead"), e.get("firefighter_deaths")))
        print("         route_blocked firings: %s"
              % [(x.get("ff"), x.get("step"), x.get("pos")) for x in fires])
        print("         recoveries:            %s"
              % [(x.get("ff"), x.get("step"), x.get("pos"), x.get("to")) for x in rec])


east333()
