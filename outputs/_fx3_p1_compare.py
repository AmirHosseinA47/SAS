"""fix3a - arm comparison for the depot-area items (read-only). Part 1 prototypes; pre-registered for Part 3.

usage: _fx3_p1_compare.py <tag> [<tag> ...] [--cfgs A_E,...]
Per arm over its probe runs (_sd_<tag>_<cfg>.json; B prototype names _sd_<tag>_B_<W>_<seed>.json too):
  pockets   depot-pocket UAV-steps (outputs/_fx3_pockets.py definition) PRE / FULL, searcher and tracker;
            searcher episodes split into OSCILLATION (the searcher changes cell on >= 1/3 of the
            episode's steps) and WAIT (it holds one cell on > 2/3 of the steps - the prototype's
            deliberate fire wait); the longest of each
  fire_wait searcher steps labelled ..._fire_wait (the prototype's wait) PRE / FULL, longest run
  finish    runs with a terminal step; the three runs a5a496db never finished (A_N, B_E, C_S)
  outcomes  rescued / dead / never_detected
  exposure  UAV-steps on a burning cell (mf2 uav rows), searcher-only and all-UAV, and on smoke
  docking   return legs, standoffs (fix2 P3-7: excess >= 10 or an outside-depot wait >= 5; open legs
            counted), the longest stationary wait one cell outside a depot on a return leg
  invariants docked UAV-steps outside every depot footprint; steps with two UAVs on one cell
"""
from __future__ import annotations

import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _fx3_pockets as P  # noqa: E402
import _mf2_p3_analyze as A  # noqa: E402


def load(tag, cfgs=None):
    out = {}
    for f in glob.glob(os.path.join(HERE, "_sd_%s_*.json" % tag)):
        m = re.match(r"_sd_%s_(.+)\.json$" % re.escape(tag), os.path.basename(f))
        if not m:
            continue
        c = m.group(1)
        if cfgs and c not in cfgs:
            continue
        out[c] = json.load(open(f, encoding="utf-8"))
    return out


def outside_wait(d):
    depot = {tuple(c) for c in d["depots"]["cells"]}
    best = 0
    run = {}
    prev = {}
    for row in d["rows_uav"]:
        for u in row:
            uid, x, y, rtb, dock = u[0], u[1], u[2], u[5], u[6]
            c = (x, y)
            near = c not in depot and any(abs(x - a) + abs(y - b) == 1 for a, b in depot)
            if rtb and not dock and near and prev.get(uid) == c:
                run[uid] = run.get(uid, 0) + 1
            else:
                run[uid] = 0
            best = max(best, run[uid])
            prev[uid] = c
    return best


def arm_stats(runs):
    S = collections.Counter()
    longest = collections.Counter()
    finish = {}
    for c, d in sorted(runs.items()):
        depot = {tuple(x) for x in d["depots"]["cells"]}
        term = d.get("terminal_step")
        finish[c] = term
        for full in (False, True):
            eps, _ = P.pockets(d, pre_terminal=not full)
            k = "FULL" if full else "PRE"
            for e in eps:
                role = "s" if e["role"] == "victim_searcher" else "t"
                S["pocket_%s_%s" % (role, k)] += e["len"]
                if role == "s":
                    rows = d["rows_uav"]
                    cells = [[u for u in rows[s - 1] if u[0] == e["uid"]][0][1:3] for s in range(e["start"], e["end"] + 1)]
                    ch = sum(1 for i in range(1, len(cells)) if cells[i] != cells[i - 1])
                    kind = "osc" if ch * 3 >= len(cells) else "wait"
                    S["ep_%s_%s" % (kind, k)] += 1
                    S["steps_%s_%s" % (kind, k)] += e["len"]
                    longest["%s_%s" % (kind, k)] = max(longest["%s_%s" % (kind, k)], e["len"])
        T = len(d["rows_uav"])
        pre_end = (term - 1) if term else T
        run = {}
        for t, row in enumerate(d["rows_uav"]):
            seen = collections.Counter()
            for u in row:
                uid, x, y, role, bat, rtb, dock, berth, act = u
                seen[(x, y)] += 1
                if dock and (x, y) not in depot:
                    S["docked_outside"] += 1
                if str(act).endswith("_fire_wait"):
                    S["fire_wait_FULL"] += 1
                    if t + 1 <= pre_end:
                        S["fire_wait_PRE"] += 1
                    run[uid] = run.get(uid, 0) + 1
                    longest["fire_wait_run"] = max(longest["fire_wait_run"], run[uid])
                else:
                    run[uid] = 0
            S["shared_cell_steps"] += sum(1 for v in seen.values() if v > 1)
        mu = (d.get("mf2") or {}).get("uav") or []
        for t, row in enumerate(mu):
            for u in row:
                if len(u) < 6 or not isinstance(u[4], int):
                    continue
                S["uav_steps"] += 1
                S["fire_all"] += u[4]
                S["smoke_all"] += u[5]
                if u[1] == "victim_searcher":
                    S["s_steps"] += 1
                    S["fire_s"] += u[4]
                    S["smoke_s"] += u[5]
        e = d.get("eval") or {}
        S["rescued"] += e.get("rescued") or 0
        S["dead"] += e.get("dead") or 0
        S["nd"] += e.get("never_detected") or 0
        n, w = A.standoffs(d)
        S["legs"] += n
        S["standoffs"] += len(w)
        longest["outside_wait"] = max(longest["outside_wait"], outside_wait(d))
    return S, longest, finish


def pct(a, b):
    return "%.2f%%" % (100.0 * a / b) if b else "n/a"


def main():
    args = sys.argv[1:]
    cfgs = None
    if "--cfgs" in args:
        i = args.index("--cfgs")
        cfgs = set(args[i + 1].split(","))
        args = args[:i] + args[i + 2:]
    for tag in args:
        runs = load(tag, cfgs)
        S, L, fin = arm_stats(runs)
        nt = sum(1 for v in fin.values() if v is None)
        print("== %s (%d runs)" % (tag, len(runs)))
        print("   pockets PRE searcher %d tracker %d | FULL searcher %d tracker %d" % (
            S["pocket_s_PRE"], S["pocket_t_PRE"], S["pocket_s_FULL"], S["pocket_t_FULL"]))
        print("   searcher episodes PRE: oscillation %d (%d steps, longest %d), wait %d (%d steps, longest %d)"
              " | FULL: oscillation %d (%d), wait %d (%d)" % (
                  S["ep_osc_PRE"], S["steps_osc_PRE"], L["osc_PRE"], S["ep_wait_PRE"], S["steps_wait_PRE"],
                  L["wait_PRE"], S["ep_osc_FULL"], S["steps_osc_FULL"], S["ep_wait_FULL"], S["steps_wait_FULL"]))
        print("   fire_wait UAV-steps PRE %d FULL %d, longest run %d" % (
            S["fire_wait_PRE"], S["fire_wait_FULL"], L["fire_wait_run"]))
        print("   runs with no terminal step %d %s | A_N %s B_E %s C_S %s" % (
            nt, sorted(k for k, v in fin.items() if v is None), fin.get("A_N"), fin.get("B_E"), fin.get("C_S")))
        print("   rescued %d dead %d never_detected %d" % (S["rescued"], S["dead"], S["nd"]))
        print("   in fire: searcher %s all-UAV %s | smoke: searcher %s all-UAV %s" % (
            pct(S["fire_s"], S["s_steps"]), pct(S["fire_all"], S["uav_steps"]), pct(S["smoke_s"], S["s_steps"]),
            pct(S["smoke_all"], S["uav_steps"])))
        print("   docking: %d legs, %d standoffs, longest outside-depot wait %d | docked outside a footprint %d"
              " | UAV-steps sharing a cell %d" % (S["legs"], S["standoffs"], L["outside_wait"], S["docked_outside"],
                                                  S["shared_cell_steps"]))


if __name__ == "__main__":
    main()
