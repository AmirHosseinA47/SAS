"""Planner round Part 1, section 11A (a): the recharge coverage gap, from the C13 observe
recorder data already written by Part 1 (v1 files; no model is built or run).

Per run: the steps on which every victim searcher is returning or docked (as blocks of
consecutive planner steps), the steps on which every UAV is, how many of the searcher-gap
steps had at least one victim not yet confirmed, and the battery at step 1.
Paths are relative to this file, so it runs on any checkout that has the _pl_v_observe files.
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for p in sorted(glob.glob(os.path.join(HERE, "_pl_v_observe_*.json"))):
    d = json.load(open(p))
    tag = "%s/%s" % (d["label"][2:], d["seed"])
    gap, fleet, undetected = [], 0, 0
    n_search = None
    for s in d["shadow"]:
        searchers = [u for u in s["uav"] if u["role"] == "victim_searcher"]
        n_search = len(searchers)
        if all(u["rtb"] or u["dock"] for u in s["uav"]):
            fleet += 1
        if not any(not u["rtb"] and not u["dock"] for u in searchers):
            gap.append(s["step"])
            if any(not v[1] for v in (s.get("mv") or {}).values()):
                undetected += 1
    blocks = []
    for x in gap:
        if blocks and x == blocks[-1][1] + 1:
            blocks[-1][1] = x
        else:
            blocks.append([x, x])
    batt1 = sorted({round(u["batt"], 2) for u in d["shadow"][0]["uav"]})
    rows.append((tag, n_search, len(gap), blocks, fleet, undetected, batt1))
    print("%-17s searchers=%d  no-searcher steps=%2d blocks=%s  whole-fleet-out steps=%2d  "
          "of the no-searcher steps with a victim unconfirmed=%2d  battery at step 1=%s"
          % (tag, n_search, len(gap), blocks, fleet, undetected, batt1))
print("SUMMARY: no-searcher steps %d-%d; single block in %d of %d runs, ending at %d-%d; "
      "whole fleet out in %d of %d runs (%d-%d steps); runs with an unconfirmed victim in the gap: %d"
      % (min(r[2] for r in rows), max(r[2] for r in rows),
         sum(1 for r in rows if len(r[3]) == 1), len(rows),
         min(r[3][-1][1] for r in rows), max(r[3][-1][1] for r in rows),
         sum(1 for r in rows if r[4]), len(rows), min(r[4] for r in rows), max(r[4] for r in rows),
         sum(1 for r in rows if r[5])))
