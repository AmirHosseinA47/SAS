"""sysdebug round: seed-matched comparison of two counterfactual arms (_sd_*.json).

usage: _sd_cfcmp.py <pairs-spec> ...   where each spec is  base_name:arm_name
       _sd_cfcmp.py --pattern X_{w}_{s}_crn X_{w}_{s}_dd --winds S,E --seeds 9301-9306

Per pair: arm configs (from the JSON cf/cf2 records - refused if the two arms differ in
anything but the arm switch), eval deltas, first step at which any UAV / firefighter row
differs, count of steps with differing UAV rows, per-victim first detection step (from
[Victim Detection] stdout events), and outcome per victim. Totals over pairs at the end.
Read-only.
"""
import json
import os
import re
import sys

REPO = r"E:\Projects\SAS"
DET = re.compile(r"\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at")
KEYS = ("rescued", "dead", "unreachable", "never_detected", "geographically_isolated",
        "candidate", "firefighter_deaths", "burnt_cells", "terminal_step")


def load(name):
    p = os.path.join(REPO, "outputs", "_sd_%s.json" % name)
    if not os.path.exists(p):
        return None, None
    d = json.load(open(p, encoding="utf-8"))
    sp = p[:-5] + ".stdout.txt"
    text = open(sp, encoding="utf-8").read() if os.path.exists(sp) else ""
    det = {}
    for m in DET.finditer(text):
        det.setdefault(m.group(3), int(m.group(1)))
    return d, det


def final_status(d):
    return {r[0]: r[4] for r in d["rows_vic"][-1]} if d["rows_vic"] else {}


def compare(a_name, b_name, tot):
    a, adet = load(a_name)
    b, bdet = load(b_name)
    if a is None or b is None:
        print("%s vs %s: MISSING" % (a_name, b_name))
        return
    pa ={k: v for k, v in a["params"].items()}
    pb = {k: v for k, v in b["params"].items()}
    if pa != pb or a["seed"] != b["seed"] or a["scenario"] != b["scenario"] or a["wind"] != b["wind"]:
        print("%s vs %s: REFUSED - params/seed/scenario/wind differ" % (a_name, b_name))
        return
    if (a.get("cf") or {}).get("config", {}).get("crn") != (b.get("cf") or {}).get("config", {}).get("crn"):
        print("%s vs %s: REFUSED - CRN differs" % (a_name, b_name))
        return
    ea, eb = a["eval"] or {}, b["eval"] or {}
    deltas = {k: (ea.get(k), eb.get(k)) for k in KEYS if ea.get(k) != eb.get(k)}
    first_uav = next((t for t, (x, y) in enumerate(zip(a["rows_uav"], b["rows_uav"]), start=1)
                      if [r[:3] for r in x] != [r[:3] for r in y]), None)
    n_uav_diff = sum(1 for x, y in zip(a["rows_uav"], b["rows_uav"]) if [r[:3] for r in x] != [r[:3] for r in y])
    first_ff = next((t for t, (x, y) in enumerate(zip(a["rows_ff"], b["rows_ff"]), start=1)
                     if [r[:3] for r in x] != [r[:3] for r in y]), None)
    fa, fb = final_status(a), final_status(b)
    vic = []
    for v in sorted(set(fa) | set(fb)):
        if adet.get(v) != bdet.get(v) or fa.get(v) != fb.get(v):
            vic.append("%s det %s->%s %s->%s" % (v, adet.get(v), bdet.get(v), fa.get(v), fb.get(v)))
    print("%-16s vs %-16s | first UAV diff %-4s (%3d steps differ) first FF diff %-4s | %s | %s" % (
        a_name, b_name, first_uav, n_uav_diff, first_ff,
        ", ".join("%s %s->%s" % (k, x, y) for k, (x, y) in deltas.items()) or "eval identical",
        "; ".join(vic) or "victims identical"))
    tot["pairs"] += 1
    tot["pairs_diverged"] += int(first_uav is not None)
    tot["pairs_eval_differs"] += int(bool(deltas))
    for k in ("rescued", "dead", "unreachable", "never_detected", "firefighter_deaths"):
        tot["d_" + k] += int(eb.get(k) or 0) - int(ea.get(k) or 0)
    da = [adet.get(v) for v in sorted(set(adet) & set(bdet))]
    db = [bdet.get(v) for v in sorted(set(adet) & set(bdet))]
    tot["det_both"] += len(da)
    tot["det_sum_a"] += sum(da)
    tot["det_sum_b"] += sum(db)
    tot["det_only_a"] += len(set(adet) - set(bdet))
    tot["det_only_b"] += len(set(bdet) - set(adet))


def main():
    args = sys.argv[1:]
    pairs = []
    if args and args[0] == "--pattern":
        pa, pb = args[1], args[2]
        winds = args[args.index("--winds") + 1].split(",")
        lo, hi = args[args.index("--seeds") + 1].split("-")
        for w in winds:
            for s in range(int(lo), int(hi) + 1):
                pairs.append((pa.format(w=w, s=s), pb.format(w=w, s=s)))
    else:
        pairs = [tuple(x.split(":", 1)) for x in args]
    tot = {k: 0 for k in ("pairs", "pairs_diverged", "pairs_eval_differs", "d_rescued", "d_dead", "d_unreachable",
                          "d_never_detected", "d_firefighter_deaths", "det_both", "det_sum_a", "det_sum_b",
                          "det_only_a", "det_only_b")}
    for a, b in pairs:
        compare(a, b, tot)
    print("TOTALS (B minus A):", tot)
    if tot["det_both"]:
        print("mean first-detection step over victims detected in both arms: A %.1f  B %.1f" % (
            tot["det_sum_a"] / tot["det_both"], tot["det_sum_b"] / tot["det_both"]))


if __name__ == "__main__":
    main()
