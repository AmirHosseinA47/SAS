"""Three-arm A/B: none vs keeplc vs hardlc, seed-matched on the canonical sample.

  none    stock HEAD (2acfb54)
  keeplc  `_reset_idle_retreat_state` preserves `_idle_retreat_last_cell`
          (agents.py:752 suppressed).  Predicted INERT.
  hardlc  the anti-oscillation memory survives BOTH clears - the reset AND the
          inline leash re-anchor at agents.py:786.  This is the only arm that
          actually blocks the step back.
"""
from __future__ import annotations
import collections, json, os, sys

OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, OUT)
from _irh2_analyse import (COMBOS, tight_reversals, attribute,
                           reset_sites_paired, key)


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
            return x, y
    return None


ARMS = [("none", "_irh2_"), ("keeplc", "_irh2_"), ("hardlc", "_irh2h_")]


def main():
    print("=" * 78)
    print("THREE-ARM SEED-MATCHED A/B, canonical sample (13 runs, D, 240 steps)")
    print("=" * 78)
    tot = {a: [0, 0, 0] for a, _ in ARMS}
    rev = {a: 0 for a, _ in ARMS}
    hol = {a: 0 for a, _ in ARMS}
    div = {a: 0 for a, _ in ARMS}
    missing = []
    print("\n  run          none        keeplc      hardlc      keeplc-trace  hardlc-trace")
    for tag, w, r_, seed in COMBOS:
        t = "%s_%s" % (tag, seed)
        ds = {}
        for arm, pre in ARMS:
            d = load("%s_%s" % (t, arm), pre)
            if d is None:
                missing.append("%s_%s" % (t, arm))
            ds[arm] = d
        if any(ds[a] is None for a, _ in ARMS):
            print("  %-12s INCOMPLETE" % t)
            continue
        e = {}
        for arm, _ in ARMS:
            reset_sites_paired(ds[arm])
            e[arm] = ev(ds[arm], seed)
            rr = attribute(ds[arm], tight_reversals(ds[arm]))
            rev[arm] += len(rr)
            hol[arm] += sum(1 for x in rr if x["class"].startswith("HOLE"))
            for i in range(3):
                tot[arm][i] += e[arm][i]
        dk = first_div(ds["none"], ds["keeplc"])
        dh = first_div(ds["none"], ds["hardlc"])
        div["keeplc"] += (dk is not None)
        div["hardlc"] += (dh is not None)
        print("  %-12s r%d/d%d/ff%d   r%d/d%d/ff%d   r%d/d%d/ff%d   %-13s %s"
              % (t, e["none"][0], e["none"][1], e["none"][2],
                 e["keeplc"][0], e["keeplc"][1], e["keeplc"][2],
                 e["hardlc"][0], e["hardlc"][1], e["hardlc"][2],
                 "same" if dk is None else "DIFFERS s%d" % dk[0][1],
                 "same" if dh is None else "DIFFERS s%d" % dh[0][1]))
    print("  %-12s r%d/d%d/ff%d   r%d/d%d/ff%d   r%d/d%d/ff%d"
          % ("TOTAL", *tot["none"], *tot["keeplc"], *tot["hardlc"]))
    if missing:
        print("\n  !! MISSING RUNS: %s" % missing)

    print("\n  runs whose trajectory differs from stock:")
    print("     keeplc  %d / 13      hardlc  %d / 13" % (div["keeplc"], div["hardlc"]))
    print("\n  tight reversals (all paths)   none %d   keeplc %d   hardlc %d"
          % (rev["none"], rev["keeplc"], rev["hardlc"]))
    print("  ...of which hole-attributed   none %d   keeplc %d   hardlc %d"
          % (hol["none"], hol["keeplc"], hol["hardlc"]))

    print("\n" + "=" * 78)
    print("PER-SEED DELTA, hardlc vs none  (the arm that actually blocks it)")
    print("=" * 78)
    worse = better = 0
    for tag, w, r_, seed in COMBOS:
        t = "%s_%s" % (tag, seed)
        a, b = load("%s_none" % t, "_irh2_"), load("%s_hardlc" % t, "_irh2h_")
        if a is None or b is None:
            continue
        ea, eb = ev(a, seed), ev(b, seed)
        if ea == eb:
            continue
        d = "rescued %d->%d  victims dead %d->%d  ff_deaths %d->%d" % (
            ea[0], eb[0], ea[1], eb[1], ea[2], eb[2])
        verdict = []
        if eb[0] < ea[0]:
            verdict.append("LOST A RESCUE")
            worse += 1
        if eb[0] > ea[0]:
            verdict.append("gained a rescue")
            better += 1
        if eb[2] > ea[2]:
            verdict.append("MORE FF DEATHS")
            worse += 1
        if eb[2] < ea[2]:
            verdict.append("fewer ff deaths")
            better += 1
        print("  %-12s %s   %s" % (t, d, " / ".join(verdict) or "neutral"))
    print("\n  seeds where blocking the reversal HELPED: %d   HURT: %d" % (better, worse))


main()
