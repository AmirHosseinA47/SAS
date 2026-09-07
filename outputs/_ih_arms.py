"""Interior-hazard round: per-arm searcher exposure, mode mix and outcomes from
outputs/_ffr_<tag>_*.json, plus identity checks between arms.

usage:
  _ih_arms.py summary tag [tag ...]          exposure / mode / outcome per arm (canonical 13 unless
                                              the tag contains 'fresh')
  _ih_arms.py identity tagA tagB              eval + uav_steps + fire identity per run
  _ih_arms.py seeds tagA tagB                 per-seed r/d/ff/nd deltas
Missing runs are reported, not fatal.
"""
from __future__ import annotations

import collections
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
MOVE_X = [1, 0, -1, 0]
MOVE_Y = [0, -1, 0, 1]
H = W = 50
# params / extra_params record the --set overrides an arm was run with (the kill
# switch arms carry VICTIM_SEARCHER_HAZARD_RETREAT_RANGE there by construction);
# identity is about the recorded RESULTS, so they are compared separately and noted.
SKIP = {"tag", "repo", "wall_s", "dim", "uav_actions", "params", "extra_params"}


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def load(tag, combos):
    runs = {}
    for k in combos:
        p = _name(tag, *k)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            with open(p, encoding="utf-8") as f:
                runs[k] = json.load(f)
    missing = [k for k in combos if k not in runs]
    if missing:
        print("  [%s] MISSING %d/%d" % (tag, len(missing), len(combos)))
    return runs


def label(k):
    return "D/%s/%s %d" % (k[0], k[1], k[2])


def combos_for(tag):
    return FRESH if "fresh" in tag else CANON


def burning_by_step(run):
    by = collections.defaultdict(set)
    for key, ivs in run["burn_intervals"].items():
        x, y = key.split(",")
        for a, b in ivs:
            for s in range(a, b if b is not None else run["steps"] + 1):
                by[s].add((int(x), int(y)))
    return by


def fam(action):
    a = str(action or "")
    if a == "hold":
        return "hold"
    if "hazard_retreat" in a:
        return "hazard_retreat"
    if "escape_bfs" in a:
        return "escape_bfs"
    if "retarget_to_interior" in a:
        return "retarget_to_interior"
    if "sweep" in a:
        return "sweep"
    if "wind_aware_retarget" in a:
        return "wind_aware_retarget"
    if "wind_aware" in a:
        return "wind_aware"
    if "hold_escape" in a:
        return "hold_escape"
    if a.startswith("victim"):
        return "victim_other"
    return "other:" + a[:24]


def summary(tags):
    for tag in tags:
        combos = combos_for(tag)
        R = load(tag, combos)
        ev = collections.Counter()
        exp = collections.Counter()
        fams = collections.Counter()
        strict_test = 0
        strict_exec = 0
        n_act = 0
        per_seed = []
        by_mode = collections.Counter()
        for k in combos:
            r = R.get(k)
            if r is None:
                continue
            e = r["eval"]
            for m in ("rescued", "dead", "firefighter_deaths", "never_detected"):
                ev[m] += int(e.get(m, 0) or 0)
            by = burning_by_step(r)
            c = collections.Counter()
            for i, row in enumerate(r["uav_steps"]):
                s = i + 1
                b = by.get(s, set())
                for uid, pos, role, sd in row:
                    if role != "victim_searcher" or pos is None:
                        continue
                    cell = (pos[0], pos[1])
                    d = min((abs(cell[0] - fx) + abs(cell[1] - fy) for fx, fy in b), default=99)
                    c["steps"] += 1
                    c["on_fire"] += int(d == 0)
                    c["le2"] += int(d <= 2)
                    c["le3"] += int(d <= 3)
                    if d < 99:
                        c["dsum"] += min(d, 30)
                        c["dn"] += 1
                    c["edge5"] += int(min(cell[0], cell[1], H - 1 - cell[0], W - 1 - cell[1]) <= 5)
            exp.update(c)
            st = se = 0
            if r.get("uav_actions"):
                roles = {}
                for row in r["uav_steps"]:
                    for uid, pos, role, sd in row:
                        roles[uid] = role
                for row in r["uav_actions"]:
                    for uid, act, burning, vsm, asm, fd in row:
                        if roles.get(uid) != "victim_searcher":
                            continue
                        f = fam(act)
                        fams[f] += 1
                        n_act += 1
                        st += int(burning or vsm)
                        se += int(burning or vsm or asm)
                        by_mode[(f, "steps")] += 1
                        by_mode[(f, "burning")] += int(burning)
                        by_mode[(f, "strict")] += int(burning or vsm)
                        by_mode[(f, "le3")] += int(fd <= 3)
                        if fd < 99:
                            by_mode[(f, "dsum")] += min(fd, 30)
                            by_mode[(f, "dn")] += 1
                strict_test += st
                strict_exec += se
            per_seed.append((label(k), "%d/%d/%d/%d" % (e["rescued"], e["dead"], e["firefighter_deaths"], e.get("never_detected", 0)),
                             c["on_fire"], c["le3"], st))
        n = max(1, exp["steps"])
        print("=== %s (%d/%d runs) ===" % (tag, len(R), len(combos)))
        print("  outcomes r/d/ff/nd: %d/%d/%d/%d" % (ev["rescued"], ev["dead"], ev["firefighter_deaths"], ev["never_detected"]))
        print("  searcher steps %d: on burning cell %d (%.2f%%)  <=2 %d (%.1f%%)  <=3 %d (%.1f%%)  mean fire dist %.2f  edge<=5 %.1f%%" % (
            exp["steps"], exp["on_fire"], 100.0 * exp["on_fire"] / n, exp["le2"], 100.0 * exp["le2"] / n, exp["le3"], 100.0 * exp["le3"] / n,
            exp["dsum"] / max(1, exp["dn"]), 100.0 * exp["edge5"] / n))
        if n_act:
            print("  strict hazard steps (test definition: burning or visibility smoke): %d (%.2f%%);  executor level>0 (plus agent smoke): %d (%.2f%%)" % (
                strict_test, 100.0 * strict_test / n_act, strict_exec, 100.0 * strict_exec / n_act))
            print("  searcher mode mix: %s" % ", ".join("%s %.1f%%" % (f, 100.0 * v / n_act) for f, v in fams.most_common()))
            print("  exposure by mode (steps / on burning / strict / <=3 of fire / mean fire dist):")
            for f, v in fams.most_common():
                s = max(1, by_mode[(f, "steps")])
                print("    %-22s %5d  %4d (%.2f%%)  %4d (%.2f%%)  %4d (%.1f%%)  %.1f" % (
                    f, by_mode[(f, "steps")], by_mode[(f, "burning")], 100.0 * by_mode[(f, "burning")] / s,
                    by_mode[(f, "strict")], 100.0 * by_mode[(f, "strict")] / s, by_mode[(f, "le3")], 100.0 * by_mode[(f, "le3")] / s,
                    by_mode[(f, "dsum")] / max(1, by_mode[(f, "dn")])))
        print("  per seed (r/d/ff/nd, on_fire, <=3, strict): %s" % "; ".join("%s %s %d %d %d" % p for p in per_seed))


def identity(tag_a, tag_b):
    combos = combos_for(tag_a)
    A, B = load(tag_a, combos), load(tag_b, combos)
    n = same = 0
    print("=== IDENTITY %s vs %s ===" % (tag_a, tag_b))
    for k in combos:
        a, b = A.get(k), B.get(k)
        if a is None or b is None:
            continue
        n += 1
        d = [f for f in sorted(set(a) | set(b)) if f not in SKIP and a.get(f) != b.get(f)]
        ok = not d
        same += int(ok)
        ud = None
        if "uav_steps" in d:
            for i, (x, y) in enumerate(zip(a["uav_steps"], b["uav_steps"])):
                if x != y:
                    ud = i + 1
                    break
        pdiff = {kk: (a.get("params", {}).get(kk), b.get("params", {}).get(kk))
                 for kk in set(a.get("params", {})) | set(b.get("params", {}))
                 if a.get("params", {}).get(kk) != b.get("params", {}).get(kk)}
        print("  %-22s %s%s%s" % (label(k), "identical" if ok else "DIFFERS %s" % d,
                                  "" if ud is None else " (uav div @%d)" % ud,
                                  "" if not pdiff else "  [params differ: %s]" % pdiff))
    print("  identical: %d/%d (results; --set overrides in params compared separately)" % (same, n))


def seeds(tag_a, tag_b):
    combos = combos_for(tag_a)
    A, B = load(tag_a, combos), load(tag_b, combos)
    print("=== PER SEED %s -> %s ===" % (tag_a, tag_b))
    tot = collections.Counter()
    for k in combos:
        a, b = A.get(k), B.get(k)
        if a is None or b is None:
            continue
        ea, eb = a["eval"], b["eval"]
        flags = []
        for m, short in (("rescued", "resc"), ("dead", "dead"), ("firefighter_deaths", "ff"), ("never_detected", "nd")):
            x, y = int(ea.get(m, 0) or 0), int(eb.get(m, 0) or 0)
            tot[m + "_a"] += x
            tot[m + "_b"] += y
            if x != y:
                flags.append("%s %+d" % (short, y - x))
        print("  %-22s %d/%d/%d/%d -> %d/%d/%d/%d  %s" % (
            label(k), ea["rescued"], ea["dead"], ea["firefighter_deaths"], ea.get("never_detected", 0),
            eb["rescued"], eb["dead"], eb["firefighter_deaths"], eb.get("never_detected", 0),
            "; ".join(flags) or ("same" if ea == eb else "terminal only")))
    print("  TOTAL r/d/ff/nd %d/%d/%d/%d -> %d/%d/%d/%d" % (
        tot["rescued_a"], tot["dead_a"], tot["firefighter_deaths_a"], tot["never_detected_a"],
        tot["rescued_b"], tot["dead_b"], tot["firefighter_deaths_b"], tot["never_detected_b"]))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "summary":
        summary(argv[1:])
    elif argv[0] == "identity":
        identity(argv[1], argv[2])
    elif argv[0] == "seeds":
        seeds(argv[1], argv[2])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
