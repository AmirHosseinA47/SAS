"""fix3a Part 1 queues for outputs/_mf2_pool.py (the fix1/fix2 memory-aware pool, unchanged).

  fx3v  the 16 mf2rS configurations (A-D x N/S/E/W, seeds 9601-9616, 360 steps, GPM 0) at the
        SHIPPED DEFAULTS of this checkout (a5a496db): the mf2rS argv with every fix2 --set pair
        removed, run through outputs/_fx3_probe.py (pass-through searcher-routing observers).
        Re-verifies the session-2 depot-pocket evidence at a5a496db and records the mechanism.

usage: _fx3_p1_queue.py fx3v  -> writes outputs/_fx3_q_fx3v.jsonl
"""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")
FIX2 = {"GLOBAL_ANALYZER_FIRE_SOURCE_FIX", "FAILSAFE_REAL_ALARMS", "UAV_HOLD_STATIONARY",
        "SEARCHER_WIND_COVERAGE_FIX", "SEARCHER_GATE_NEAR_FIELD", "STAGGERED_LAUNCH_BATTERY",
        "STAGGER_COMPACT", "STATIONARY_YIELD_FIX", "YIELD_ONLY_WHEN_CONTENDING"}


def strip_fix2(a):
    out, i = [], 0
    while i < len(a):
        if a[i] == "--set" and a[i + 1].split("=", 1)[0] in FIX2:
            i += 2
            continue
        out.append(a[i])
        i += 1
    return out


def line(arm, cfg, extra_sets=()):
    with open(os.path.join(OUT, "_sd_mf2rS_%s.json.argv" % cfg), encoding="utf-8") as fh:
        a = list(json.load(fh)["argv"])
    a = a[a.index("--") + 1:]
    a = strip_fix2(a)
    name = "%s_%s" % (arm, cfg)
    out = os.path.join(OUT, "_sd_%s.json" % name)
    a[a.index("--out") + 1] = out
    a[a.index("--tag") + 1] = name
    for kv in extra_sets:
        a += ["--set", kv]
    return {"name": name, "argv": [os.path.join(OUT, "_fx3_probe.py"), "--"] + a, "out": out}


B_SEEDS = {"N": [9605, 9651], "S": [9606, 9652], "E": [9607, 9653], "W": [9608, 9654]}
WIND = {"N": "north", "S": "south", "E": "east", "W": "west"}
BARMS = {"fx3pb0": ("0", "none"), "fx3pb2": ("1", "none"), "fx3pbL": ("1", "low"),
         "fx3pbC": ("1", "crit"), "fx3pb3": ("0", "low")}


def bline(arm, w, seed):
    b2, b3 = BARMS[arm]
    name = "%s_B_%s_%d" % (arm, w, seed)
    out = os.path.join(OUT, "_sd_%s.json" % name)
    a = ["--scenario", "B", "--wind", WIND[w], "--seed", str(seed), "--uavs", "4", "--victims", "4",
         "--firefighters", "3", "--set", "GLOBAL_PLANNER_MODE=0", "--steps", "360", "--set", "BATCH_SIZE=360",
         "--out", out, "--tag", name]
    return {"name": name, "argv": [os.path.join(OUT, "_fx3_bproto.py"), "--b2", b2, "--b3", b3, "--"] + a,
            "out": out}


def main():
    arm = sys.argv[1]
    cfg16 = ["%s_%s" % (s, w) for s in "ABCD" for w in "ENSW"]
    if arm == "fx3v":
        q = [line("fx3v", c) for c in cfg16]
    elif arm == "p1b":
        # the hazard replay of the pocket configurations (value-identical to fx3v by construction)
        # and the scenario-B prototypes (B1 team; B2 / B3 by monkeypatch, _fx3_bproto.py)
        q = []
        for c in ("A_N", "B_E", "C_S", "D_N", "B_W"):
            ln = line("fx3h", c)
            ln["argv"] = [ln["argv"][0], "--hazard"] + ln["argv"][1:]
            q.append(ln)
        for arm_b in ("fx3pb0", "fx3pb2", "fx3pbL", "fx3pbC", "fx3pb3"):
            for w in "NSEW":
                for seed in B_SEEDS[w]:
                    q.append(bline(arm_b, w, seed))
    elif arm == "p1ref":
        # the a5a496db REFERENCES for Part 3's identity and route_blocked checks, run on this unchanged
        # tree (no worktree needed): fix2's 16 canonical harness tuples and fix1's four rbgate shards,
        # shipped defaults (no --set)
        q = []
        tuples = ([("D", "east", "half", s) for s in (101, 202, 303, 404, 505)]
                  + [("D", "south", "half", s) for s in (101, 202, 303, 404, 505)]
                  + [("D", "east", "default", s) for s in (101, 202, 303)]
                  + [("A", "west", "default", 9501), ("B", "north", "default", 9502),
                     ("C", "south", "default", 9503)])
        for sc, w, roles, seed in tuples:
            name = "fx3hR_%s_%s_%s_%d" % (sc, w, roles, seed)
            out = os.path.join(OUT, "_ffr_%s.json" % name)
            q.append({"name": name, "out": out,
                      "argv": [os.path.join(OUT, "_ffr_harness.py"), "--repo", REPO, "--scenario", sc,
                               "--wind", w, "--roles", roles, "--seed", str(seed), "--steps", "360",
                               "--out", out, "--tag", "fx3hR"]})
        for sh, w, seeds in (("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
                             ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505")):
            tag = "fx3gR%s" % sh
            out = os.path.join(OUT, "_rblatch_camp2_%s_D_%s.json" % (tag, w))
            q.append({"name": tag, "cwd": REPO, "out": out,
                      "argv": [os.path.join(OUT, "_rblatch_campaign2.py"), "--scenario", "D", "--wind", w,
                               "--steps", "240", "--seeds", seeds, "--tag", tag]})
    else:
        raise SystemExit("unknown arm %s" % arm)
    path = os.path.join(OUT, "_fx3_q_%s.jsonl" % arm)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in q:
            fh.write(json.dumps(ln) + "\n")
    print(path, len(q))


if __name__ == "__main__":
    main()
