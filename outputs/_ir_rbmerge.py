"""Merge the sharded route_blocked gate runs and compare, seed-matched,
against the 70e1b33 baseline (outputs/_rblatch_camp2_exact_D_{wind}.json).

The campaign harness accumulates per-seed `evals` plus flat global counters,
so sharding across processes merges additively. Sharding is verified here:
the union of shard seeds must equal the baseline seed set exactly, with no
duplicates.

usage: _ir_rbmerge.py --prefix irfix
"""
import argparse, collections, glob, json, os

BASE = os.path.dirname(os.path.abspath(__file__))


def load(p):
    with open(p) as f:
        return json.load(f)


def merge(paths):
    out = {"evals": [], "stats": collections.Counter(),
           "exact": collections.Counter(), "exact_fires": [],
           "exact_recoveries": [], "fires": [], "recoveries": [],
           "assigns": [], "latched": [], "deaths": [], "shards": []}
    for p in sorted(paths):
        d = load(p)
        out["shards"].append((os.path.basename(p), d["seeds"]))
        out["evals"].extend(d.get("evals") or [])
        out["stats"].update(d.get("stats") or {})
        out["exact"].update(d.get("exact") or {})
        for k in ("exact_fires", "exact_recoveries", "fires", "recoveries",
                  "assigns", "latched", "deaths"):
            out[k].extend(d.get(k) or [])
    return out


def by_seed(evals):
    m = {}
    for e in evals:
        m[int(e["seed"])] = (int(e.get("rescued") or 0),
                             int(e.get("dead") or 0),
                             int(e.get("firefighter_deaths") or 0))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="irfix")
    a = ap.parse_args()

    grand_b = [0, 0, 0]
    grand_f = [0, 0, 0]
    regressions, ff_up, ff_down = [], [], []
    tot_exact_b = collections.Counter()
    tot_exact_f = collections.Counter()
    all_latched_f, all_recov_f = [], []

    for wind in ("east", "south"):
        base = load(os.path.join(BASE, "_rblatch_camp2_exact_D_%s.json" % wind))
        shards = glob.glob(os.path.join(
            BASE, "_rblatch_camp2_%s*_D_%s.json" % (a.prefix, wind)))
        if not shards:
            print("MISSING shards for %s" % wind)
            continue
        fix = merge(shards)

        b, f = by_seed(base["evals"]), by_seed(fix["evals"])
        base_seeds = [int(s) for s in base["seeds"].split(",")]

        print("=" * 78)
        print("D/%s   70e1b33 baseline  ->  + idle-retreat fix" % wind)
        print("  shards: %s" % "; ".join("%s[%s]" % s for s in fix["shards"]))
        if sorted(f) != sorted(base_seeds):
            print("  !! SEED SET MISMATCH: shards=%s baseline=%s"
                  % (sorted(f), sorted(base_seeds)))
        else:
            print("  seed set matches baseline exactly (%d seeds, no dupes)"
                  % len(base_seeds))
        print("=" * 78)
        print("  seed |   rescued      | victims dead   |  ff_deaths")
        print("  -----+----------------+----------------+---------------")
        sb, sf = [0, 0, 0], [0, 0, 0]
        for seed in base_seeds:
            eb, ef = b.get(seed), f.get(seed)
            if eb is None or ef is None:
                print("  %-5s MISSING" % seed)
                continue
            for i in range(3):
                sb[i] += eb[i]
                sf[i] += ef[i]
            if ef[0] < eb[0]:
                regressions.append((wind, seed, eb[0], ef[0]))
            if ef[2] > eb[2]:
                ff_up.append((wind, seed, eb[2], ef[2]))
            if ef[2] < eb[2]:
                ff_down.append((wind, seed, eb[2], ef[2]))

            def cell(x, y):
                d = y - x
                return "%2d -> %2d%-7s" % (x, y, (" (%+d)" % d) if d else "")
            mark = "  <-- changed" if eb != ef else ""
            print("  %-5s %s| %s| %s%s" % (
                seed, cell(eb[0], ef[0]), cell(eb[1], ef[1]),
                cell(eb[2], ef[2]), mark))
        print("  TOTAL %s| %s| %s" % (
            "%2d -> %2d%-7s" % (sb[0], sf[0], " (%+d)" % (sf[0] - sb[0])),
            "%2d -> %2d%-7s" % (sb[1], sf[1], " (%+d)" % (sf[1] - sb[1])),
            "%2d -> %2d%-7s" % (sb[2], sf[2], " (%+d)" % (sf[2] - sb[2]))))
        identical = sum(1 for s in base_seeds
                        if b.get(s) is not None and b.get(s) == f.get(s))
        print("  seeds bit-identical on all three metrics: %d/%d"
              % (identical, len(base_seeds)))
        for i in range(3):
            grand_b[i] += sb[i]
            grand_f[i] += sf[i]

        eb_ex = collections.Counter(base.get("exact") or {})
        ef_ex = collections.Counter(fix["exact"])
        tot_exact_b.update(eb_ex)
        tot_exact_f.update(ef_ex)
        print()
        print("  route_blocked mechanics (exact hooks):")
        for k in ("fires", "recoveries", "reval_calls",
                  "reval_calls_with_blocked_unit"):
            print("    %-32s %6s -> %6s" % (k, eb_ex.get(k, 0), ef_ex.get(k, 0)))
        print("    %-32s %6s -> %6s" % (
            "end-of-run units still blocked",
            len(base.get("latched") or []), len(fix["latched"])))
        all_latched_f.extend(fix["latched"])
        all_recov_f.extend(fix["exact_recoveries"])
        if fix["exact_recoveries"]:
            print("    recoveries in detail:")
            for r in fix["exact_recoveries"]:
                print("      seed %-5s %-10s step %-4s at %s -> %s"
                      % (r.get("seed"), r.get("ff"), r.get("step"),
                         r.get("pos"), r.get("to")))
        print()

    print("=" * 78)
    print("ALL 18 RUNS   rescued %d -> %d (%+d)   victims dead %d -> %d (%+d)"
          "   ff_deaths %d -> %d (%+d)" % (
              grand_b[0], grand_f[0], grand_f[0] - grand_b[0],
              grand_b[1], grand_f[1], grand_f[1] - grand_b[1],
              grand_b[2], grand_f[2], grand_f[2] - grand_b[2]))
    print("=" * 78)
    print()
    print("ROUTE_BLOCKED GATE ITEMS (from outputs/rblatch_report.txt section 2)")
    print("  [%s] rescued does not decrease on any seed"
          % ("PASS" if not regressions else "FAIL"))
    for r in regressions:
        print("        regression: D/%s seed %s  rescued %d -> %d" % r)
    print("  [%s] recovery pass still recovers units"
          % ("PASS" if tot_exact_f.get("recoveries", 0) > 0 else "CHECK"))
    print("        recoveries %d -> %d, route_blocked firings %d -> %d"
          % (tot_exact_b.get("recoveries", 0), tot_exact_f.get("recoveries", 0),
             tot_exact_b.get("fires", 0), tot_exact_f.get("fires", 0)))
    print("  [%s] no unit left latched as route_blocked at end of run"
          % ("PASS" if not all_latched_f else "FAIL"))
    for l in all_latched_f:
        print("        still blocked: %s" % l)
    print("  ff_deaths seeds up: %s" % (ff_up or "none"))
    print("  ff_deaths seeds down: %s" % (ff_down or "none"))


main()
