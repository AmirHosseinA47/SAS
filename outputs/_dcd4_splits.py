"""dcd4 round: outcome accounting, per-scenario splits and paired sign tests.

Read-only. A second, independent path to the outcome numbers: it reads `eval`
straight from the harness JSON / rbgate shard (not through _dcd4_analyze's
summaries), so its totals cross-check that script's.

  A  victim accounting per arm on the fourth set (every victim is exactly one of
     rescued / dead / never_detected / other-unreachable / still-alive candidate
     at step 240 / horizon-unresolved)
  B  per-scenario split (east/half, south/half, east/default) - fourth set and
     the 27 DISTINCT prior tuples (canonical 13 + fresh 10 + rbgate east 111-444)
  C  paired comparisons per metric: tuples better / worse / tied, the exact
     two-sided sign-test p on the untied tuples, and a deterministic paired
     bootstrap 90% interval on the per-run mean difference. Descriptive only:
     the decision rule is the prereg gate, not these.

A run is counted only if _dcd4_validate says VALID (d4* arms) - a missing or
invalid run drops its whole tuple from every paired comparison.

usage: .venv/Scripts/python.exe outputs/_dcd4_splits.py
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _dcd4_analyze as AN  # noqa: E402  (tuples, prior lists, validator hook only)

METRICS = ("rescued", "dead", "never_detected", "firefighter_deaths")
LOWER_BETTER = {"rescued": False, "dead": True, "never_detected": True, "firefighter_deaths": True}
SHORT = {"rescued": "rescued", "dead": "dead", "never_detected": "nd", "firefighter_deaths": "ffd"}


def ev_of(tag, t):
    p = AN.ffr_path(tag, *t)
    if not os.path.exists(p):
        return None
    if AN._why_invalid(tag, t, p) is not None:
        return None
    with open(p, "rb") as f:
        d = json.loads(f.read().decode("utf-8-sig"))
    ev = d.get("eval")
    del d
    return ev if isinstance(ev, dict) else None


def shard_evals(tag, shard, wind):
    p = os.path.join(HERE, "_rblatch_camp2_%s%s_D_%s.json" % (tag, shard, wind))
    with open(p, "rb") as f:
        d = json.loads(f.read().decode("utf-8-sig"))
    return {(wind, "half", int(e["seed"])): e for e in d["evals"]}


def load_fourth():
    tuples = AN.fourth()[0]
    return {arm: {t: ev_of(arm, t) for t in tuples} for arm in ("d4off", "d4D", "d4A")}, tuples


def load_prior27():
    tuples = list(AN.CANON) + list(AN.FRESH)
    arms = {}
    for role, tag, rb in (("base", "dcoff", "rbc"), ("D", "dcD", "dcrbD"), ("A", "dcA", "dcrbA")):
        m = {t: ev_of(tag, t) for t in tuples}
        m.update(shard_evals(rb, "c", "east"))
        arms[role] = m
    extra = sorted(k for k in arms["base"] if k not in tuples)
    return arms, tuples + extra


def sign_p(better, worse):
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def boot_ci(diffs, reps=10000, seed=20260913):
    if not diffs:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return (means[int(0.05 * reps)], means[int(0.95 * reps) - 1])


def compare(label, X, Y, tuples, xname, yname):
    pairs = [t for t in tuples if X.get(t) is not None and Y.get(t) is not None]
    print("  %-22s %s - %s   pairs %d" % (label, xname, yname, len(pairs)))
    for m in METRICS:
        diffs = [int(X[t].get(m) or 0) - int(Y[t].get(m) or 0) for t in pairs]
        if LOWER_BETTER[m]:
            better = sum(1 for v in diffs if v < 0)
            worse = sum(1 for v in diffs if v > 0)
        else:
            better = sum(1 for v in diffs if v > 0)
            worse = sum(1 for v in diffs if v < 0)
        lo, hi = boot_ci(diffs)
        print("    %-8s total %+4d  per-run %+.3f  90%% boot [%+.3f, %+.3f]   %s better %2d / worse %2d / tied %2d   sign-test p=%.3f"
              % (SHORT[m], sum(diffs), (sum(diffs) / len(pairs)) if pairs else 0.0, lo, hi,
                 xname, better, worse, len(pairs) - better - worse, sign_p(better, worse)))
    return pairs


def group_of(t):
    return "%s/%s" % (t[0], t[1])


def main():
    sys.stdout.reconfigure(newline="\n")
    F, ftuples = load_fourth()
    P, ptuples = load_prior27()

    print("A  VICTIM ACCOUNTING, fourth set (every victim in exactly one bucket)")
    print("  %-6s runs victims rescued dead nd other_unreachable alive_at_240 unresolved | ff_deaths | check" % "arm")
    for arm in ("d4off", "d4D", "d4A"):
        evs = [e for e in F[arm].values() if e is not None]
        tot = sum(int(e.get("total_victims") or 0) for e in evs)
        r = sum(int(e.get("rescued") or 0) for e in evs)
        dd = sum(int(e.get("dead") or 0) for e in evs)
        nd = sum(int(e.get("never_detected") or 0) for e in evs)
        un = sum(int(e.get("unreachable") or 0) for e in evs)
        hz = sum(int(e.get("horizon_unresolved") or 0) for e in evs)
        ca = sum(int(e.get("candidate") or 0) for e in evs)
        ff = sum(int(e.get("firefighter_deaths") or 0) for e in evs)
        other = un - nd
        resid = tot - r - dd - un - ca - hz
        print("  %-6s %4d %7d %7d %4d %2d %17d %12d %10d | %9d | residual %d"
              % (arm, len(evs), tot, r, dd, nd, other, ca, hz, ff, resid))

    print()
    print("B  PER-SCENARIO SPLIT   cells rescued/dead/nd/ffd (runs)")
    for title, arms, tuples, names in (
            ("fourth set", F, ftuples, (("off", "d4off"), ("D", "d4D"), ("A", "d4A"))),
            ("prior 27 distinct", P, ptuples, (("off", "base"), ("D", "D"), ("A", "A")))):
        print("  %s" % title)
        groups = sorted({group_of(t) for t in tuples})
        for g in groups + ["ALL"]:
            gt = [t for t in tuples if g == "ALL" or group_of(t) == g]
            cells = []
            for short, key in names:
                evs = [arms[key].get(t) for t in gt]
                evs = [e for e in evs if e is not None]
                cells.append("%-4s %3d/%3d/%2d/%2d (%2d)" % (
                    short, sum(int(e.get("rescued") or 0) for e in evs), sum(int(e.get("dead") or 0) for e in evs),
                    sum(int(e.get("never_detected") or 0) for e in evs),
                    sum(int(e.get("firefighter_deaths") or 0) for e in evs), len(evs)))
            print("    %-12s %s" % (g, "   ".join(cells)))

    print()
    print("C  PAIRED COMPARISONS (descriptive; the decision rule is the prereg gate)")
    pooled = {}
    for key_f, key_p, nm in (("d4D", "D", "D"), ("d4A", "A", "A"), ("d4off", "base", "off")):
        m = {("fourth",) + t: F[key_f].get(t) for t in ftuples}
        m.update({("prior",) + t: P[key_p].get(t) for t in ptuples})
        pooled[nm] = m
    ptup = [("fourth",) + t for t in ftuples] + [("prior",) + t for t in ptuples]
    for x, y in (("D", "off"), ("A", "off"), ("D", "A")):
        print(" %s vs %s" % (x, y))
        fx = {"D": F["d4D"], "A": F["d4A"], "off": F["d4off"]}
        px = {"D": P["D"], "A": P["A"], "off": P["base"]}
        compare("fourth set (30)", fx[x], fx[y], ftuples, x, y)
        compare("prior 27 distinct", px[x], px[y], ptuples, x, y)
        compare("pooled 57 distinct", pooled[x], pooled[y], ptup, x, y)
        for g in sorted({group_of(t) for t in ftuples}):
            gt = [t for t in ftuples if group_of(t) == g]
            compare("fourth %s" % g, fx[x], fx[y], gt, x, y)
            gp = [t for t in ptuples if group_of(t) == g]
            compare("prior27 %s" % g, px[x], px[y], gp, x, y)
            gq = [("fourth",) + t for t in gt] + [("prior",) + t for t in gp]
            compare("pooled57 %s" % g, pooled[x], pooled[y], gq, x, y)
    print("SPLITS_COMPLETE")


if __name__ == "__main__":
    main()
