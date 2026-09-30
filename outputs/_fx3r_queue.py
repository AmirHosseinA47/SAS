"""fix3a ROUND 2 queue for outputs/_mf2_pool.py - the arms of outputs/fix3a_r2_prereg.txt section 2.

usage: _fx3r_queue.py all     -> outputs/_fx3_q_r2all.jsonl (route_blocked shards first, the longest)
Every probe run: outputs/_fx3_probe.py (v3) --hazard. Refuses to write a queue whose outputs already exist
(tag collision), like outputs/_fx3_p3_queue.py.
"""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")
PROBE = os.path.join(OUT, "_fx3_probe.py")
P2 = ["SEARCHER_ROUTE_FIRE_FIELD", "SEARCHER_SWEEP_IN_BOUNDS", "SEARCHER_CORNER_ESCAPE", "FREE_CELL_DOCKING",
      "SCENARIO_B_TEAM", "SCENARIO_B_STAGGERED_LAUNCH", "SCENARIO_B_RETURN_DELAY"]
R2 = ["SEARCHER_FIRE_ROUTE_OWNER", "SEARCHER_ROUTE_BOUNDED_WAIT"]
ALL = P2 + R2
A1 = ["SEARCHER_ROUTE_FIRE_FIELD", "SEARCHER_SWEEP_IN_BOUNDS", "SEARCHER_CORNER_ESCAPE"]
B = ["SCENARIO_B_TEAM", "SCENARIO_B_STAGGERED_LAUNCH", "SCENARIO_B_RETURN_DELAY"]
WIND = {"N": "north", "S": "south", "E": "east", "W": "west"}
WORDER = "NSEW"
SET1 = {"%s_%s" % (sc, w): 9601 + 4 * i + j for i, sc in enumerate("ABCD") for j, w in enumerate(WORDER)}
SET2 = {k: v + 20 for k, v in SET1.items()}
BSEEDS = {w: [9605 + j, 9651 + j, 9661 + j, 9671 + j] for j, w in enumerate(WORDER)}
W39 = ["--set", "SEARCHER_ROUTE_WAIT_LIMIT=39"]


def zero(names):
    out = []
    for n in names:
        out += ["--set", "%s=0" % n]
    return out


def probe_line(arm, suffix, scenario, wind, seed, extra):
    name = "%s_%s" % (arm, suffix)
    out = os.path.join(OUT, "_sd_%s.json" % name)
    a = ["--scenario", scenario, "--wind", WIND[wind], "--seed", str(seed), "--set", "GLOBAL_PLANNER_MODE=0",
         "--steps", "360", "--set", "BATCH_SIZE=360", "--out", out, "--tag", name] + extra
    return {"name": name, "argv": [PROBE, "--hazard", "--"] + a, "out": out}


def cfg_arm(arm, seedmap, extra):
    return [probe_line(arm, "%s_%s" % (sc, w), sc, w, seedmap["%s_%s" % (sc, w)], extra)
            for sc in "ABCD" for w in WORDER]


def main():
    if sys.argv[1:] != ["all"]:
        raise SystemExit("usage: _fx3r_queue.py all")
    rb, probes, harness = [], [], []
    for arm, extra in (("fx3rgZ", zero(ALL)), ("fx3rgS", []), ("fx3rgW", W39)):
        for sh, w, seeds in (("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
                             ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505")):
            tag = "%s%s" % (arm, sh)
            out = os.path.join(OUT, "_rblatch_camp2_%s_D_%s.json" % (tag, w))
            rb.append({"name": tag, "cwd": REPO, "out": out,
                       "argv": [os.path.join(OUT, "_rblatch_campaign2.py"), "--scenario", "D", "--wind", w,
                                "--steps", "240", "--seeds", seeds, "--tag", tag] + extra})
    probes += cfg_arm("fx3rZ", SET1, zero(ALL))
    probes += cfg_arm("fx3rX", SET1, zero(R2))
    probes += cfg_arm("fx3rS", SET1, [])
    probes += cfg_arm("fx3rS2", SET2, [])
    probes += cfg_arm("fx3rSZ2", SET2, zero(ALL))
    probes += cfg_arm("fx3rA1", SET1, zero(["FREE_CELL_DOCKING"] + B))
    probes += cfg_arm("fx3rA2", SET1, zero(A1 + R2 + B))
    for arm, zs in (("fx3rB0", ["SCENARIO_B_STAGGERED_LAUNCH", "SCENARIO_B_RETURN_DELAY"]),
                    ("fx3rB2", ["SCENARIO_B_RETURN_DELAY"]), ("fx3rB3", ["SCENARIO_B_STAGGERED_LAUNCH"]),
                    ("fx3rB23", [])):
        for w in WORDER:
            for seed in BSEEDS[w]:
                probes.append(probe_line(arm, "B_%s_%d" % (w, seed), "B", w, seed, zero(zs)))
    probes += cfg_arm("fx3rW", SET1, W39)
    probes += cfg_arm("fx3rW2", SET2, W39)
    tuples = ([("D", "east", "half", s) for s in (101, 202, 303, 404, 505)]
              + [("D", "south", "half", s) for s in (101, 202, 303, 404, 505)]
              + [("D", "east", "default", s) for s in (101, 202, 303)]
              + [("A", "west", "default", 9501), ("B", "north", "default", 9502), ("C", "south", "default", 9503)])
    for arm, extra in (("fx3rhZ", zero(ALL)), ("fx3rhS", [])):
        for sc, w, roles, seed in tuples:
            name = "%s_%s_%s_%s_%d" % (arm, sc, w, roles, seed)
            out = os.path.join(OUT, "_ffr_%s.json" % name)
            harness.append({"name": name, "out": out,
                            "argv": [os.path.join(OUT, "_ffr_harness.py"), "--repo", REPO, "--scenario", sc,
                                     "--wind", w, "--roles", roles, "--seed", str(seed), "--steps", "360",
                                     "--out", out, "--tag", arm] + extra})
    q = rb + probes + harness
    names = [ln["name"] for ln in q]
    assert len(names) == len(set(names))
    clash = [ln["out"] for ln in q if os.path.exists(ln["out"])]
    if clash:
        raise SystemExit("TAG COLLISION: %d outputs already exist, e.g. %s" % (len(clash), clash[0]))
    path = os.path.join(OUT, "_fx3_q_r2all.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in q:
            fh.write(json.dumps(ln) + "\n")
    print(path, "route_blocked %d, probe %d, harness %d, total %d" % (len(rb), len(probes), len(harness), len(q)))


if __name__ == "__main__":
    main()
