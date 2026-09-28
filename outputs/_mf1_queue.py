"""fix1 (mf1) Part 3: build the pre-registered run queues (outputs/fix1_part1.txt section 11).

usage: _mf1_queue.py   -> writes outputs/_mf1_q_harness.jsonl, _mf1_q_probe.jsonl,
                          _mf1_q_rbgate.jsonl, _mf1_q_invariants.jsonl (the P3-7 names in
                          the _sd_analyze.py queue format)
Arms (every harness arm runs THIS checkout's outputs/_ffr_harness.py, --repo selects the
code): mf1R = 51c5165 worktree; mf1Z = fix1, all four switches 0; mf1Bt / mf1Rl / mf1Ct =
fix1 with only item 2 / 3 / 6 on; mf1Zc = mf1Z instrumented like mf1Ct. Probe arms (the
sysdebug probe, which takes --victims): mf1Un (item 4 only) and mf1Zp (all off); mf1P
(shipped). rbgate: mf1gR (worktree), mf1gZ (all off), mf1gS (shipped), shards a/b/c/s.
Every harness run: 360 steps, no --set BATCH_SIZE (item 1's default must cover it).
"""
from __future__ import annotations

import json
import os

REPO = r"E:\Projects\SAS"
WT = r"E:\Projects\SAS_wt\mf1_51c5165"
OUT = os.path.join(REPO, "outputs")
SW = ("REDUCED_LAUNCH_BATTERY", "ROLE_SPLIT_HALF_RULE", "UNDETECTED_WRITEOFF_FIX", "SEARCHER_COUNTERS_PER_STEP")


def sets(on=()):
    out = []
    for k in SW:
        out += ["--set", "%s=%d" % (k, 1 if k in on else 0)]
    return out


ARMS = {
    "mf1R": (WT, sets()),               # same --set as mf1Z: unused names at 51c5165
    "mf1Z": (REPO, sets()),
    "mf1Bt": (REPO, sets(("REDUCED_LAUNCH_BATTERY",))),
    "mf1Rl": (REPO, sets(("ROLE_SPLIT_HALF_RULE",))),
    "mf1Ct": (REPO, sets(("SEARCHER_COUNTERS_PER_STEP",))),
    "mf1Zc": (REPO, sets()),
}
INSTRUMENTED = ("mf1Ct", "mf1Zc")

C13 = ([("D", "east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("D", "south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("D", "east", "default", s) for s in (101, 202, 303)])
P31 = C13 + [("A", "west", "default", 9501), ("B", "north", "default", 9502), ("C", "south", "default", 9503)]
P32 = ([("B", w, "default", s) for w in ("north", "south", "east", "west") for s in (9511, 9512)]
       + [("A", "east", "default", 9513), ("C", "east", "default", 9514), ("D", "east", "default", 9515)])
P33 = ([("A", "east", "default", 9521), ("B", "east", "default", 9522)]
       + [("C", w, "default", s) for w in ("east", "south") for s in (9523, 9524)]
       + [("D", "east", "default", s) for s in (101, 202, 303)]
       + [("A", "east", "half", 9521), ("C", "east", "half", 9523)])
P35 = [("D", w, "half", s) for w in ("south", "east") for s in (9531, 9532, 9533)]

PLAN = [("mf1R", P31), ("mf1Z", P31),
        ("mf1Bt", P32), ("mf1Z", P32),
        ("mf1Rl", P33), ("mf1Z", [t for t in P33 if t[0] != "D" and t[2] == "default"]),
        ("mf1Ct", P35), ("mf1Zc", P35), ("mf1Z", P35)]


def harness_line(arm, tup):
    repo, extra = ARMS[arm]
    sc, wind, roles, seed = tup
    name = "%s_%s_%s_%s_%d" % (arm, sc, wind, roles, seed)
    out = os.path.join(OUT, "_ffr_%s.json" % name)
    script = "_mf1_counters.py" if arm in INSTRUMENTED else "_ffr_harness.py"
    argv = [os.path.join(OUT, script), "--repo", repo, "--scenario", sc, "--wind", wind,
            "--roles", roles, "--seed", str(seed), "--steps", "360", "--out", out, "--tag", arm] + extra
    return {"name": name, "argv": argv, "out": out}


def probe_line(name, args):
    out = os.path.join(OUT, "_sd_%s.json" % name)
    return {"name": name, "argv": [os.path.join(OUT, "_sd_probe.py")] + args + ["--out", out, "--tag", name],
            "out": out}


# P3-4: the three sysdebug write-off configurations + three more D/east/10-victim seeds, at
# the sysdebug settings (legacy roles unless given, GPM as recorded); item 4 alone vs all off.
P34 = [("AE9103", ["--scenario", "A", "--wind", "east", "--seed", "9103", "--set", "GLOBAL_PLANNER_MODE=0"]),
       ("DEv10_9122", ["--scenario", "D", "--wind", "east", "--seed", "9122", "--set", "GLOBAL_PLANNER_MODE=0", "--victims", "10"]),
       ("DhN9127", ["--scenario", "D", "--wind", "north", "--seed", "9127", "--set", "GLOBAL_PLANNER_MODE=1",
                    "--fire-trackers", "2", "--victim-searchers", "2"])]
P34 += [("DEv10_%d" % s, ["--scenario", "D", "--wind", "east", "--seed", str(s), "--set", "GLOBAL_PLANNER_MODE=0",
                          "--victims", "10"]) for s in (9123, 9124, 9125)]
# P3-7: shipped defaults, 4 scenarios x 4 winds, GPM 0
P37 = []
seed = 9601
for sc in "ABCD":
    for wind in ("north", "south", "east", "west"):
        P37.append(("%s_%s" % (sc, wind[0].upper()), ["--scenario", sc, "--wind", wind, "--seed", str(seed),
                                                        "--set", "GLOBAL_PLANNER_MODE=0"]))
        seed += 1

RB_SHARDS = {"a": ("east", "101,202,303,404,505"), "b": ("east", "606,707,808,909"),
             "c": ("east", "111,222,333,444"), "s": ("south", "101,202,303,404,505")}


def main() -> int:
    seen = set()
    harness = []
    for arm, tuples in PLAN:
        for tup in tuples:
            ln = harness_line(arm, tup)
            if ln["name"] in seen:
                continue
            seen.add(ln["name"])
            harness.append(ln)
    probe = []
    for name, args in P34:
        base = args + ["--steps", "360", "--set", "BATCH_SIZE=360"]  # the probe pins batch 300 itself
        probe.append(probe_line("mf1Un_" + name, base + sets(("UNDETECTED_WRITEOFF_FIX",))))
        probe.append(probe_line("mf1Zp_" + name, base + sets()))
    inv = []
    for name, args in P37:
        ln = probe_line("mf1P_" + name, args + ["--steps", "360", "--set", "BATCH_SIZE=360"])
        probe.append(ln)
        inv.append({"name": ln["name"]})
    rb = []
    for arm, (root, extra) in {"mf1gR": (WT, []), "mf1gZ": (REPO, sets()), "mf1gS": (REPO, [])}.items():
        for shard, (wind, seeds) in RB_SHARDS.items():
            tag = arm + shard
            rb.append({"name": tag, "cwd": root,
                       "argv": [os.path.join(root, "outputs", "_rblatch_campaign2.py"), "--scenario", "D",
                                "--wind", wind, "--steps", "240", "--seeds", seeds, "--tag", tag] + extra,
                       "out": os.path.join(root, "outputs", "_rblatch_camp2_%s_D_%s.json" % (tag, wind))})
    # Stage 2 (after the harness queue): probes, rbgate, the 360-step evaluate run (P3-6a),
    # and mf1Zv - three mf1Z tuples that ran BEFORE the review fix (3340d42) re-run after
    # it, to show the fix is inert with every switch at 0 (compared field for field).
    zv = []
    for tup in (("D", "south", "half", 202), ("A", "west", "default", 9501), ("B", "north", "default", 9502)):
        ln = harness_line("mf1Z", tup)
        name = ln["name"].replace("mf1Z_", "mf1Zv_", 1)
        out = ln["out"].replace("_ffr_mf1Z_", "_ffr_mf1Zv_")
        argv = [x if x != ln["out"] else out for x in ln["argv"]]
        argv[argv.index("--tag") + 1] = "mf1Zv"
        zv.append({"name": name, "argv": argv, "out": out})
    ev = [{"name": "mf1_eval360", "argv": [os.path.join(OUT, "_mf1_eval360.py"), os.path.join(OUT, "_mf1_eval360.json")],
           "out": os.path.join(OUT, "_mf1_eval360.json")}]
    stage2 = rb + zv + ev + probe
    for fname, lines in (("_mf1_q_harness.jsonl", harness), ("_mf1_q_probe.jsonl", probe),
                         ("_mf1_q_rbgate.jsonl", rb), ("_mf1_q_invariants.jsonl", inv),
                         ("_mf1_q_stage2.jsonl", stage2)):
        with open(os.path.join(OUT, fname), "w", encoding="utf-8", newline="\n") as fh:
            for ln in lines:
                fh.write(json.dumps(ln) + "\n")
        print("%s: %d lines" % (fname, len(lines)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
