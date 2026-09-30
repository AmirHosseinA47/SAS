"""fix3a Part 3 queues for outputs/_mf2_pool.py (outputs/fix3a_part3_prereg.txt, arms made concrete).

usage: _fx3_p3_queue.py <wave>   waves:
  w1   fx3Z (every new switch 0) + fx3S (shipped) on the 16 fx3v configurations, fx3S2 (shipped) +
       fx3SZ2 (every new switch 0) on the second set (seeds 9621-9636)          64 probe runs
  w2   fx3B0 / fx3B2 / fx3B3 / fx3B23 - scenario B, 4 winds x 4 seeds each           64 probe runs
  w3   fx3A1 (A1 only) + fx3A2 (A2 only), the 16 fx3v configurations               32 probe runs
  w4   harness fx3hZ / fx3hS (fix2's 16 canonical tuples) + route_blocked fx3gZ / fx3gS (4 shards each)
Every probe run: outputs/_fx3_probe.py --hazard (pass-through observers). Tags checked unused before
each wave (this script refuses to write a queue whose outputs already exist).
"""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")
PROBE = os.path.join(OUT, "_fx3_probe.py")
NEW = ["SEARCHER_ROUTE_FIRE_FIELD", "SEARCHER_SWEEP_IN_BOUNDS", "SEARCHER_CORNER_ESCAPE", "FREE_CELL_DOCKING",
       "SCENARIO_B_TEAM", "SCENARIO_B_STAGGERED_LAUNCH", "SCENARIO_B_RETURN_DELAY"]
A1 = ["SEARCHER_ROUTE_FIRE_FIELD", "SEARCHER_SWEEP_IN_BOUNDS", "SEARCHER_CORNER_ESCAPE"]
B = ["SCENARIO_B_TEAM", "SCENARIO_B_STAGGERED_LAUNCH", "SCENARIO_B_RETURN_DELAY"]
WIND = {"N": "north", "S": "south", "E": "east", "W": "west"}
WORDER = "NSEW"
# the fx3v (= mf2rS) seed map: A N 9601 S 9602 E 9603 W 9604, B 9605-9608, C 9609-9612, D 9613-9616
SET1 = {"%s_%s" % (sc, w): 9601 + 4 * i + j for i, sc in enumerate("ABCD") for j, w in enumerate(WORDER)}
SET2 = {k: v + 20 for k, v in SET1.items()}                     # 9621-9636, same order
BSEEDS = {w: [9605 + j, 9651 + j, 9661 + j, 9671 + j] for j, w in enumerate(WORDER)}


def sets(names_zero):
    out = []
    for n in names_zero:
        out += ["--set", "%s=0" % n]
    return out


def probe_line(arm, name_suffix, scenario, wind, seed, zero):
    name = "%s_%s" % (arm, name_suffix)
    out = os.path.join(OUT, "_sd_%s.json" % name)
    a = ["--scenario", scenario, "--wind", WIND[wind], "--seed", str(seed), "--set", "GLOBAL_PLANNER_MODE=0",
         "--steps", "360", "--set", "BATCH_SIZE=360", "--out", out, "--tag", name] + sets(zero)
    return {"name": name, "argv": [PROBE, "--hazard", "--"] + a, "out": out}


def cfg_arm(arm, seedmap, zero):
    q = []
    for sc in "ABCD":
        for w in WORDER:
            cfg = "%s_%s" % (sc, w)
            q.append(probe_line(arm, cfg, sc, w, seedmap[cfg], zero))
    return q


def main():
    wave = sys.argv[1]
    q = []
    if wave == "w1":
        q += cfg_arm("fx3Z", SET1, NEW)
        q += cfg_arm("fx3S", SET1, [])
        q += cfg_arm("fx3S2", SET2, [])
        q += cfg_arm("fx3SZ2", SET2, NEW)
    elif wave == "w2":
        for arm, zero in (("fx3B0", ["SCENARIO_B_STAGGERED_LAUNCH", "SCENARIO_B_RETURN_DELAY"]),
                          ("fx3B2", ["SCENARIO_B_RETURN_DELAY"]),
                          ("fx3B3", ["SCENARIO_B_STAGGERED_LAUNCH"]),
                          ("fx3B23", [])):
            for w in WORDER:
                for seed in BSEEDS[w]:
                    q.append(probe_line(arm, "B_%s_%d" % (w, seed), "B", w, seed, zero))
    elif wave == "w3":
        q += cfg_arm("fx3A1", SET1, ["FREE_CELL_DOCKING"] + B)
        q += cfg_arm("fx3A2", SET1, A1 + B)
    elif wave == "w4":
        tuples = ([("D", "east", "half", s) for s in (101, 202, 303, 404, 505)]
                  + [("D", "south", "half", s) for s in (101, 202, 303, 404, 505)]
                  + [("D", "east", "default", s) for s in (101, 202, 303)]
                  + [("A", "west", "default", 9501), ("B", "north", "default", 9502),
                     ("C", "south", "default", 9503)])
        for arm, zero in (("fx3hZ", NEW), ("fx3hS", [])):
            for sc, w, roles, seed in tuples:
                name = "%s_%s_%s_%s_%d" % (arm, sc, w, roles, seed)
                out = os.path.join(OUT, "_ffr_%s.json" % name)
                q.append({"name": name, "out": out,
                          "argv": [os.path.join(OUT, "_ffr_harness.py"), "--repo", REPO, "--scenario", sc,
                                   "--wind", w, "--roles", roles, "--seed", str(seed), "--steps", "360",
                                   "--out", out, "--tag", arm] + sets(zero)})
        for arm, zero in (("fx3gZ", NEW), ("fx3gS", [])):
            for sh, w, seeds in (("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
                                 ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505")):
                tag = "%s%s" % (arm, sh)
                out = os.path.join(OUT, "_rblatch_camp2_%s_D_%s.json" % (tag, w))
                q.append({"name": tag, "cwd": REPO, "out": out,
                          "argv": [os.path.join(OUT, "_rblatch_campaign2.py"), "--scenario", "D", "--wind", w,
                                   "--steps", "240", "--seeds", seeds, "--tag", tag] + sets(zero)})
    else:
        raise SystemExit("unknown wave %s" % wave)
    clash = [ln["out"] for ln in q if os.path.exists(ln["out"])]
    if clash:
        raise SystemExit("TAG COLLISION: %d outputs already exist, e.g. %s" % (len(clash), clash[0]))
    path = os.path.join(OUT, "_fx3_q_p3%s.jsonl" % wave)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in q:
            fh.write(json.dumps(ln) + "\n")
    print(path, len(q))


if __name__ == "__main__":
    main()
