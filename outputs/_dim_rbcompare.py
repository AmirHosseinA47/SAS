"""Seed-matched comparison of two route_blocked gate runs (merged shards), e.g.
the phantom round's final gate on this exact source (phfix3 == 8520706 behaviour)
against this round's gate (dimfix) - this round's OWN delta, as lastcell_report
section 5.2 did. The gate verdict itself stays with _ir_rbmerge.py (70e1b33 base).

usage: _dim_rbcompare.py --a phfix3 --b dimfix
"""
import argparse, collections, glob, json, os

BASE = os.path.dirname(os.path.abspath(__file__))


def merge(prefix, wind):
    paths = sorted(glob.glob(os.path.join(BASE, "_rblatch_camp2_%s*_D_%s.json" % (prefix, wind))))
    out = {"evals": [], "exact": collections.Counter(), "latched": [], "recoveries": [], "fires": [], "shards": []}
    for p in paths:
        d = json.load(open(p))
        out["shards"].append(os.path.basename(p))
        out["evals"].extend(d.get("evals") or [])
        out["exact"].update(d.get("exact") or {})
        for k in ("latched", "exact_recoveries", "exact_fires"):
            out[{"exact_recoveries": "recoveries", "exact_fires": "fires"}.get(k, k)].extend(d.get(k) or [])
    return out


def by_seed(evals):
    return {int(e["seed"]): (int(e.get("rescued") or 0), int(e.get("dead") or 0), int(e.get("firefighter_deaths") or 0)) for e in evals}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="phfix3")
    ap.add_argument("--b", default="dimfix")
    args = ap.parse_args()
    G = [0, 0, 0]; H = [0, 0, 0]; ident = n = 0; regress = []; ff_up = []; ff_down = []
    for wind in ("east", "south"):
        A, B = merge(args.a, wind), merge(args.b, wind)
        a, b = by_seed(A["evals"]), by_seed(B["evals"])
        seeds = sorted(set(a) | set(b))
        print("=" * 78)
        print("D/%s   %s -> %s   (shards a=%s b=%s)" % (wind, args.a, args.b, A["shards"], B["shards"]))
        print("  seed |   rescued      | victims dead   |  ff_deaths")
        for s in seeds:
            ea, eb = a.get(s), b.get(s)
            if ea is None or eb is None:
                print("  %-5s MISSING (%s)" % (s, "a" if ea is None else "b")); continue
            n += 1
            ident += int(ea == eb)
            for i in range(3):
                G[i] += ea[i]; H[i] += eb[i]
            if eb[0] < ea[0]: regress.append((wind, s, ea[0], eb[0]))
            if eb[2] > ea[2]: ff_up.append((wind, s, ea[2], eb[2]))
            if eb[2] < ea[2]: ff_down.append((wind, s, ea[2], eb[2]))
            cell = lambda x, y: "%2d -> %2d%-7s" % (x, y, (" (%+d)" % (y - x)) if y != x else "")
            print("  %-5s %s| %s| %s%s" % (s, cell(ea[0], eb[0]), cell(ea[1], eb[1]), cell(ea[2], eb[2]), "  <-- changed" if ea != eb else ""))
        print("  route_blocked mechanics: " + ", ".join("%s %s -> %s" % (k, A["exact"].get(k, 0), B["exact"].get(k, 0))
                                                        for k in ("fires", "recoveries", "reval_calls", "reval_calls_with_blocked_unit")))
        print("  end-of-run units still blocked: %d -> %d" % (len(A["latched"]), len(B["latched"])))
        if B["recoveries"]:
            print("  recoveries in %s: %s" % (args.b, [(r.get("seed"), r.get("ff"), r.get("step"), r.get("pos")) for r in B["recoveries"]]))
    print("=" * 78)
    print("ALL RUNS (%d)  rescued %d -> %d (%+d)  victims dead %d -> %d (%+d)  ff_deaths %d -> %d (%+d)   seeds identical on all three: %d/%d" % (
        n, G[0], H[0], H[0] - G[0], G[1], H[1], H[1] - G[1], G[2], H[2], H[2] - G[2], ident, n))
    print("rescued decreased on: %s" % (regress or "none"))
    print("ff_deaths up on: %s   down on: %s" % (ff_up or "none", ff_down or "none"))


main()
