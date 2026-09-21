"""Ungated round, Part 3 G5: the route_blocked gate. Read-only -> outputs/_ug_rbgate.txt

  1. _ffr_rbcompare.py --new ugGC --old ihrest   the control must reproduce the known four
  2. _ffr_rbcompare.py --new ugGD --old ihrest   the gate as the brief reads it
  3. _ffr_rbcompare.py --new ugGD --old ugGC     the feature's own delta
  4. THE RE-ROLL METHOD (depotfireproof round, decision 6.5; pre-registered in
     ungated_part1.txt 6.5 G5) for any regressing seed outside the known four:
       - re-roll status from the ugC/ugD HARNESS runs of the same tuple (every rb18 tuple
         has one: 14 are canonical/fresh, 4 are rb4): RE-ROLLED if the fire digest first
         differs before the control's terminal_step;
       - a NOT re-rolled new regression is a NEW FAILURE outright;
       - re-rolled seeds are judged on the POOLED rescued of all re-rolled seeds
         (ugGD vs ugGC); where the verdict hinges on one seed, its CRN pair decides
         (a loss under CRN is NEW, none is re-roll) - flagged here as REQUIRED.
  5. provenance cross-checks: ugGC == sfRBG (629a321, same source as 11c3661) and each
     shard's eval == its harness run's eval (ugGD vs ugD, ugGC vs ugC) on rescued / dead /
     firefighter_deaths / terminal_step.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = sys.executable
KNOWN = {("east", 707), ("south", 101), ("south", 202), ("south", 404)}
OUT = []


def say(s=""):
    OUT.append(str(s))
    print(s)


def shards(tag):
    evals = {}
    for p in sorted(glob.glob(os.path.join(HERE, "_rblatch_camp2_%s?_D_*.json" % tag))):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        wind = "south" if p.endswith("_south.json") else "east"
        for ev in d.get("evals") or []:
            evals[(wind, int(ev["seed"]))] = ev
    return evals


def compare(new, old):
    r = subprocess.run([PY, os.path.join(HERE, "_ffr_rbcompare.py"), "--new", new, "--old", old],
                       capture_output=True, text=True, cwd=os.path.dirname(HERE))
    text = (r.stdout or "") + (r.stderr or "")
    regr = set()
    for line in text.splitlines():
        m = re.search(r"regression: D/(\w+) seed (\d+)\s+rescued (\d+) -> (\d+)", line)
        if m:
            regr.add((m.group(1), int(m.group(2))))
    return text, regr


def main():
    sys.stdout.reconfigure(newline="\n")
    say("ROUTE_BLOCKED GATE (G5) - ungated round. Known four at the shipped default: %s" % sorted(KNOWN))
    gd, gc = shards("ugGD"), shards("ugGC")
    say("ugGD %d seed records, ugGC %d" % (len(gd), len(gc)))
    if len(gd) < 18 or len(gc) < 18:
        say("PENDING")
        return 1
    results = {}
    for new, old in (("ugGC", "ihrest"), ("ugGD", "ihrest"), ("ugGD", "ugGC")):
        text, regr = compare(new, old)
        results[(new, old)] = regr
        say("")
        say("=" * 78)
        say("_ffr_rbcompare.py --new %s --old %s   regressions: %s" % (new, old, sorted(regr) or "none"))
        say("=" * 78)
        for line in text.splitlines():
            if line.strip():
                say("  " + line.rstrip())
    ctrl_set = results[("ugGC", "ihrest")]
    new_set = results[("ugGD", "ihrest")]
    say("")
    say("SUMMARY")
    say("  control ugGC vs ihrest: %s  (%s)" % (sorted(ctrl_set), "== the known four" if ctrl_set == KNOWN else "DIFFERS from the known four"))
    say("  ugGD vs ihrest:         %s" % sorted(new_set))
    extra = sorted(new_set - KNOWN)
    say("  regressions outside the known four: %s" % (extra or "NONE"))

    import _ug_analyze as U  # harness runs, for re-roll status
    tmap = {("east", s): ("east", "half", s) for s in (101, 202, 303, 404, 505, 606, 707, 808, 909, 111, 222, 333, 444)}
    tmap.update({("south", s): ("south", "half", s) for s in (101, 202, 303, 404, 505)})
    rer = {}
    for k, t in tmap.items():
        a, b = U.S_("ugC", t), U.S_("ugD", t)
        if a is None or b is None:
            rer[k] = None
            continue
        term = a["terminal"] if a["terminal"] is not None else 240
        rer[k] = b["fire_div"] is not None and b["fire_div"] < term
    rerolled = sorted(k for k, v in rer.items() if v)
    say("  re-rolled seeds (harness digests, before the control's terminal_step): %d of 18: %s" % (len(rerolled), rerolled))
    verdict = "PASS"
    for k in extra:
        if rer.get(k) is False:
            say("  NEW FAILURE %s/%d: NOT re-rolled - the same fire, a worse outcome" % k)
            verdict = "FAIL"
        elif rer.get(k) is None:
            say("  %s/%d: no harness pair - cannot classify" % k)
            verdict = "FAIL"
        else:
            say("  %s/%d: RE-ROLLED - judged on the pooled re-rolled set" % k)
    pool_gd = sum(gd[k]["rescued"] for k in rerolled if k in gd)
    pool_gc = sum(gc[k]["rescued"] for k in rerolled if k in gc)
    say("  pooled rescued over the %d re-rolled seeds: ugGC %d -> ugGD %d (%+d)" % (len(rerolled), pool_gc, pool_gd, pool_gd - pool_gc))
    hinge = [k for k in extra if rer.get(k)]
    if hinge and pool_gd < pool_gc:
        say("  CRN PAIR REQUIRED for %s: the pooled re-rolled set loses rescues, so the verdict hinges on these seeds" % hinge)
        verdict = "PENDING-CRN"
    elif hinge:
        say("  re-rolled regressions %s are offset in the pooled re-rolled set: no new failure by the re-roll method" % hinge)
    say("")
    say("PROVENANCE CROSS-CHECKS")
    sf = shards("sfRBG")
    same = sum(1 for k in gc if k in sf and all(gc[k].get(f) == sf[k].get(f) for f in ("rescued", "dead", "firefighter_deaths", "terminal_step")))
    say("  ugGC == sfRBG (629a321, same source) on rescued/dead/ff_deaths/terminal: %d/%d" % (same, len(gc)))
    for tagS, tagH, ev in (("ugGD", "ugD", gd), ("ugGC", "ugC", gc)):
        agree = n = 0
        rows = []
        for k, t in tmap.items():
            S = U.S_(tagH, t)
            if S is None or k not in ev:
                continue
            n += 1
            e = ev[k]
            pair = ((e["rescued"], e["dead"], e["firefighter_deaths"], e.get("terminal_step")),
                    (S["rescued"], S["dead"], S["ffd"], S["terminal"]))
            if pair[0] == pair[1]:
                agree += 1
            else:
                rows.append("    %s/%d shard %s harness %s" % (k[0], k[1], pair[0], pair[1]))
        say("  shard %s eval == harness %s eval: %d/%d" % (tagS, tagH, agree, n))
        for r in rows:
            say(r)
    say("")
    say("G5 VERDICT: %s" % verdict)
    with open(os.path.join(HERE, "_ug_rbgate.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
