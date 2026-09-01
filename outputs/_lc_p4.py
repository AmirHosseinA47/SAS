"""Part 4 validation: patched source vs stock b6527f7, seed-matched.

Arms on disk:
    _lc_none_*   stock b6527f7, probe attached           (PRE)
    _lc_b_*      stock b6527f7 + the option-(b) monkeypatch  (what Part 2 validated)
    _lc_post_*   the PATCHED SOURCE, probe attached      (POST)

Three things are checked:
  1. EQUIVALENCE - POST must reproduce the arm-b monkeypatch exactly, or the
     shipped code is not what the design was validated on.
  2. OUTCOMES    - seed-matched, reported for the 13-run sample AND the
     10 fresh seeds SEPARATELY as well as pooled.
  3. OSCILLATION - reversal counts and direct last_cell violations, to the
     62b4fbe standard.

Read-only.
"""
from __future__ import annotations
import os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _lc_p1 import BASE13, fresh_cells, load, tup  # noqa: E402


def trace(d):
    return [(int(r["step"]), str(r["ff"]),
             tup(r["pos"]), bool(r["dead"]), str(r["status"])) for r in d["fftrace"]]


def ev3(d):
    e = d["evals"][0]
    return (e["rescued"], e["dead"], e["firefighter_deaths"])


def deaths(d):
    return sorted((int(x["step"]), str(x["ff"]),
                   tuple(x["pos"]) if x["pos"] else None) for x in d["deaths"])


def osc(d):
    mv = defaultdict(list)
    for x in d["surv"]:
        if x["moved"] and x["pos"] and x["post"]:
            mv[(int(x["seed"]), str(x["ff"]))].append(
                (int(x["step"]), tup(x["pos"]), tup(x["post"])))
    t = defaultdict(int)
    for seq in mv.values():
        seq.sort()
        t["moves"] += len(seq)
        for i in range(len(seq)):
            for j in range(i + 1, len(seq)):
                if seq[j][1] == seq[i][2] and seq[j][2] == seq[i][1]:
                    t["rev_any"] += 1
                    if seq[j][0] - seq[i][0] == 1:
                        t["rev_tight"] += 1
    return t


def violations(d):
    """Survival moves landing on the last_cell the call began with.

    On the patched source the sanctioned ones are the scans where the chain
    came back empty at cur_dist == 0 - detectable because the probe wraps
    `_retreat_candidates`, and the recursive fallback makes a SECOND call at
    the same (seed, ff, step) with last_cell None.
    """
    per_step = defaultdict(list)
    for c in d["cand"]:
        per_step[(int(c["seed"]), str(c["ff"]), int(c["step"]))].append(c)
    sanctioned = set()
    for k, cs in per_step.items():
        if len(cs) > 1 and any(c["last_cell"] is None for c in cs) \
                and any(int(c["cur_dist"]) == 0 for c in cs):
            sanctioned.add(k)
        if any(c.get("readmitted") for c in cs):
            sanctioned.add(k)
    n_v = n_s = 0
    rows = []
    for x in d["surv"]:
        if not x["moved"] or not x["post"] or not x["last_cell_pre"]:
            continue
        if tup(x["post"]) == tup(x["last_cell_pre"]):
            k = (int(x["seed"]), str(x["ff"]), int(x["step"]))
            if k in sanctioned:
                n_s += 1
            else:
                n_v += 1
                rows.append((int(x["step"]), str(x["ff"]),
                             tup(x["pos"]), tup(x["post"])))
    return n_v, n_s, rows


def section(cells, label):
    print("=" * 78)
    print(label)
    print("=" * 78)
    have = [c for c in cells if load("post", *c) is not None]
    missing = [c for c in cells if load("post", *c) is None]
    if missing:
        print("  NOT YET RUN: %s" % ["%s_%s_%d" % c for c in missing])
    eq_ok = eq_bad = 0
    tp = [0, 0, 0]
    tq = [0, 0, 0]
    op = defaultdict(int)
    oq = defaultdict(int)
    viol = sanc = 0
    changed = []
    print("  %-20s %-13s %-13s %-9s %s"
          % ("cell", "stock(pre)", "patched(post)", "trace", "post==arm b"))
    for c in have:
        pre, post = load("none", *c), load("post", *c)
        armb = load("b", *c)
        a, b = ev3(pre), ev3(post)
        for i in range(3):
            tp[i] += a[i]
            tq[i] += b[i]
        for k, v in osc(pre).items():
            op[k] += v
        for k, v in osc(post).items():
            oq[k] += v
        nv, ns, rows = violations(post)
        viol += nv
        sanc += ns
        same_trace = trace(pre) == trace(post)
        if armb is None:
            eq = "no arm-b run"
        else:
            ok = (trace(armb) == trace(post)) and (deaths(armb) == deaths(post))
            eq = "IDENTICAL" if ok else "*** MISMATCH ***"
            eq_ok += ok
            eq_bad += (not ok)
        if a != b:
            changed.append(("%s_%s_%d" % c, a, b))
        print("  %-20s %-13s %-13s %-9s %s"
              % ("%s_%s_%d" % c, "r%d/d%d/ff%d" % a, "r%d/d%d/ff%d" % b,
                 "same" if same_trace else "DIFFERS", eq))
    print("  " + "-" * 74)
    print("  %-20s %-13s %-13s" % ("TOTAL", "r%d/d%d/ff%d" % tuple(tp),
                                   "r%d/d%d/ff%d" % tuple(tq)))
    print("  deltas: rescued %+d, victims dead %+d, firefighter_deaths %+d"
          % (tq[0] - tp[0], tq[1] - tp[1], tq[2] - tp[2]))
    print("  equivalence vs the arm-b monkeypatch: %d identical, %d mismatched"
          % (eq_ok, eq_bad))
    print("  oscillation  moves %d -> %d | reversals(any) %d -> %d | tight %d -> %d"
          % (op["moves"], oq["moves"], op["rev_any"], oq["rev_any"],
             op["rev_tight"], oq["rev_tight"]))
    print("  direct last_cell violations, post-fix: %d UNSANCTIONED, %d sanctioned"
          % (viol, sanc))
    if changed:
        print("  cells whose outcome changed:")
        for nm, a, b in changed:
            print("    %-20s r%d/d%d/ff%d -> r%d/d%d/ff%d" % ((nm,) + a + b))
    return tp, tq, eq_bad, viol


if __name__ == "__main__":
    p1, q1, e1, v1 = section(BASE13, "13-RUN SEED-MATCHED SAMPLE (the gate's sample)")
    print()
    p2, q2, e2, v2 = section(fresh_cells(), "10 FRESH SEEDS (never used by a prior round)")
    print()
    print("=" * 78)
    print("POOLED, 23 RUNS")
    print("=" * 78)
    print("  stock    r%d/d%d/ff%d" % (p1[0] + p2[0], p1[1] + p2[1], p1[2] + p2[2]))
    print("  patched  r%d/d%d/ff%d" % (q1[0] + q2[0], q1[1] + q2[1], q1[2] + q2[2]))
    print("  deltas   rescued %+d, victims dead %+d, firefighter_deaths %+d"
          % (q1[0] + q2[0] - p1[0] - p2[0], q1[1] + q2[1] - p1[1] - p2[1],
             q1[2] + q2[2] - p1[2] - p2[2]))
    print()
    print("  BOTH SAMPLES ARE REPORTED SEPARATELY ABOVE ON PURPOSE.  The 13-run")
    print("  sample alone is -1 firefighter death AND -1 rescue; the pooled")
    print("  figure is more favourable.  Neither number should be quoted alone.")
    print()
    print("  equivalence mismatches (must be 0): %d" % (e1 + e2))
    print("  unsanctioned last_cell violations (must be 0): %d" % (v1 + v2))
