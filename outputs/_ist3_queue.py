"""isTrue round Part 3: the identity-run queue (outputs/_mf2_pool.py JSONL) and its FROZEN configuration list.

usage: _ist3_queue.py            writes outputs/_ist3_configs.json (frozen) and outputs/_ist3_q.jsonl
       _ist3_queue.py --check    re-derives both and STOPS (exit 3) on any difference from the files on disk

Every line runs the measurement round's own chain (outputs/fix3b_part1.txt 19 / 19.10 / 19.11; the bayesprep queue
convention, outputs/_bp_queue.py) through the record-only reach wrapper outputs/_ist3_reach.py (same arguments, adds
<out>.reach.json): outputs/_ut_probe.py --crn --hazard --instrument -- --repo <checkout> --scenario S
--wind W --seed N --set GLOBAL_PLANNER_MODE=g --set VICTIM_SPAWN_MODE=p [arm and point --set ...] --steps H
--set BATCH_SIZE=H --out ... --tag ...

ARMS (outputs/isTrue_part1.txt section 10; Part 3 plan):
  B    E:/Projects/SAS_wt/basef686 (detached f686e932 = main before this round), the configuration's --set list
  F1   E:/Projects/SAS_wt/istrue, + --set NUMPY_SCALAR_FLAGS=0                              (F-1 alone)
  F12  E:/Projects/SAS_wt/istrue, the configuration's --set list                            (shipped)
  K    E:/Projects/SAS_wt/istrue, + MR1_TRUTHINESS_FIX=0 + NUMPY_SCALAR_FLAGS=0, one configuration per strategy arm
       (scenario A / B / C only: the literal count is 0 throughout scenario D)
CONFIGURATIONS: MAIN = 12 strategy arms x 2 placements x 4 winds (scenario = (wind + arm + placement) mod 4, so every
  (arm, placement) sees every wind and every scenario); SENSITIVITY = the 12 runnable 19.7 parameter points x 2
  placements, + the 480-step point as BF and CUR x 2 placements; point 2 (2x2-cell belief) has no implementation.
SEEDS: 52001 + configuration index, FROZEN in outputs/_ist3_configs.json (committed before launch; the generator refuses
  to run once it exists). Checked unused once, before freezing: no frozen seed as a token in any *.argv, *.jsonl, *.py,
  *.sh or *.txt of outputs/ in istrue, the main checkout and the dispatch worktree (non-recursive); all outside the
  measurement round's 29000-32000 (fix3b 10.3).
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = r"E:\Projects\SAS_wt\istrue"
BASE = r"E:\Projects\SAS_wt\basef686"
PROBE = os.path.join(WT, "outputs", "_ist3_reach.py")    # record-only reach wrapper around outputs/_ut_probe.py
SEED0 = 52001
WINDS = ("north", "south", "east", "west")
SCEN = ("A", "B", "C", "D")
PLACES = (("r", 0), ("u", 1))
# 19.3 + 19.10 (a): name, GLOBAL_PLANNER_MODE, extra --set
STRATEGY = (
    ("CUR", 0, ()),
    ("LO", 0, ("SEARCHER_TARGETING=1",)),
    ("BD", 0, ("SEARCHER_TARGETING=2",)),
    ("BF", 0, ("SEARCHER_TARGETING=3",)),
    ("FP", 0, ("SEARCHER_TARGETING=5",)),
    ("RW", 0, ("SEARCHER_TARGETING=4",)),
    ("GP", 1, ("SEARCHER_TARGETING=3",)),
    ("BFcoord", 0, ("SEARCHER_TARGETING=3", "SEARCHER_TARGETING_COORDINATION=0")),
    ("BFbatt", 0, ("SEARCHER_TARGETING=3", "SEARCHER_TARGETING_BATTERY=0")),
    ("BFmotion", 0, ("SEARCHER_TARGETING=3", "SEARCHER_BELIEF_MOTION=0")),
    ("BFreach", 0, ("SEARCHER_TARGETING=3", "SEARCHER_TARGETING_REACHABILITY=0")),
    ("BFfix0", 0, ("SEARCHER_TARGETING=3", "SEARCHER_TARGETING_FIX=0")),
)
ARM_SETS = {name: (gpm, sets) for name, gpm, sets in STRATEGY}
# 19.7 sensitivity points runnable as a --set (point 2 has no implementation; point 11 = 480 steps, below)
SENS = (
    ("s01stride1", "BF", ("SEARCHER_BELIEF_STRIDE=1",)),
    ("s03q005", "BD", ("SEARCHER_BELIEF_DIFFUSION_Q=0.05",)),
    ("s04q03", "BD", ("SEARCHER_BELIEF_DIFFUSION_Q=0.3",)),
    ("s05d50_3", "BF", ("SEARCHER_BELIEF_FLEE_D50=3",)),
    ("s06d50_8", "BF", ("SEARCHER_BELIEF_FLEE_D50=8",)),
    ("s07bo0", "BF", ("SEARCHER_BELIEF_BURNOVER=0",)),
    ("s08bo02", "BF", ("SEARCHER_BELIEF_BURNOVER=0.2",)),
    ("s09bo05", "BF", ("SEARCHER_BELIEF_BURNOVER=0.5",)),
    ("s10pds05", "BF", ("SEARCHER_BELIEF_PD_SMOKE=0.5",)),
    ("s12u10_10", "FP", ("SEARCHER_FP_U10_KMH=10",)),
    ("s13u10_40", "FP", ("SEARCHER_FP_U10_KMH=40",)),
    ("s14kappa3", "FP", ("SEARCHER_FP_KAPPA=3",)),
)
ARMS = {
    "B": (BASE, ()),
    "F1": (WT, ("NUMPY_SCALAR_FLAGS=0",)),
    "F12": (WT, ()),
    "K": (WT, ("MR1_TRUTHINESS_FIX=0", "NUMPY_SCALAR_FLAGS=0")),
}


def configs() -> list[dict]:
    out = []
    for a, (name, gpm, sets) in enumerate(STRATEGY):
        for p, (pl, spawn) in enumerate(PLACES):
            for w, wind in enumerate(WINDS):
                out.append({"kind": "main", "strategy": name, "point": "", "place": pl, "spawn": spawn,
                            "wind": wind, "scenario": SCEN[(w + a + p) % 4], "gpm": gpm, "sets": list(sets),
                            "steps": 360})
    j = 0
    for pt, arm, psets in SENS:
        gpm, sets = ARM_SETS[arm]
        for pl, spawn in PLACES:
            c = (5 * j + 3) % 16
            j += 1
            out.append({"kind": "sens", "strategy": arm, "point": pt, "place": pl, "spawn": spawn,
                        "wind": WINDS[c % 4], "scenario": SCEN[c // 4], "gpm": gpm, "sets": list(sets) + list(psets),
                        "steps": 360})
    for arm in ("BF", "CUR"):
        gpm, sets = ARM_SETS[arm]
        for pl, spawn in PLACES:
            c = (5 * j + 3) % 16
            j += 1
            out.append({"kind": "sens", "strategy": arm, "point": "s11h480", "place": pl, "spawn": spawn,
                        "wind": WINDS[c % 4], "scenario": SCEN[c // 4], "gpm": gpm, "sets": list(sets), "steps": 480})
    for i, c in enumerate(out):
        c["index"] = i
        c["seed"] = SEED0 + i
        c["cid"] = "%03d_%s%s_%s_%s%s" % (i, c["strategy"], ("_" + c["point"]) if c["point"] else "", c["place"],
                                          c["scenario"], c["wind"][0].upper())
    # K: one configuration per strategy arm (main), placement varying with the arm, scenario A / B / C only - the
    # literal (`is True`) count is 0 on every step of scenario D, so a D configuration would make G-K / G1-b trivial
    for a, (name, _g, _s) in enumerate(STRATEGY):
        pick = next(c for c in out if c["kind"] == "main" and c["strategy"] == name
                    and c["spawn"] == a % 2 and c["scenario"] == SCEN[a % 3])
        pick["k_arm"] = True
    return out


def line(c: dict, arm: str) -> dict:
    repo, arm_sets = ARMS[arm]
    name = "ist3_%s_%s" % (arm, c["cid"])
    out = os.path.join(WT, "outputs", "_sd_%s.json" % name)
    argv = [PROBE, "--crn", "--hazard", "--instrument", "--", "--repo", repo, "--scenario", c["scenario"],
            "--wind", c["wind"], "--seed", str(c["seed"]),
            "--set", "GLOBAL_PLANNER_MODE=%d" % c["gpm"], "--set", "VICTIM_SPAWN_MODE=%d" % c["spawn"]]
    for s in list(c["sets"]) + list(arm_sets):
        argv += ["--set", s]
    argv += ["--steps", str(c["steps"]), "--set", "BATCH_SIZE=%d" % c["steps"], "--out", out, "--tag", name]
    return {"name": name, "argv": argv, "out": out, "cwd": repo}


def queue(cfgs: list[dict]) -> list[dict]:
    lines = []
    for c in cfgs:                          # the configuration's arms adjacent: comparisons complete early
        for arm in ("B", "F1", "F12") + (("K",) if c.get("k_arm") else ()):
            lines.append(line(c, arm))
    return lines


SEED_DIRS = (HERE, r"E:\Projects\SAS\outputs", r"E:\Projects\SAS_wt\dispatch\outputs")


def seeds_unused(cfgs: list[dict]) -> list[str]:
    pat = re.compile(r"(?<!\d)(%s)(?!\d)" % "|".join(str(c["seed"]) for c in cfgs))
    bad = []
    files = set()
    for d in SEED_DIRS:                     # non-recursive globs only (the quarantine rule)
        for ext in ("*.argv", "*.jsonl", "*.py", "*.sh", "*.txt"):
            files.update(glob.glob(os.path.join(d, ext)))
    for f in sorted(files):
        base = os.path.basename(f)
        if base.startswith(("_ist3_", "_sd_ist3_")):
            continue                        # this round's own files
        raw = open(f, "rb").read()
        utf16 = raw[:2] in (bytes([0xFF, 0xFE]), bytes([0xFE, 0xFF]))     # PowerShell-redirected outputs/*.txt
        t = raw.decode("utf-16", errors="replace") if utf16 else raw.decode("utf-8", errors="replace")
        if pat.search(t):
            bad.append(f)
    return bad


def main() -> int:
    sys.stdout.reconfigure(newline="\n")
    cfgs = configs()
    q = queue(cfgs)
    assert all(not (29000 <= c["seed"] <= 32000) for c in cfgs)
    cfg_path = os.path.join(HERE, "_ist3_configs.json")
    q_path = os.path.join(HERE, "_ist3_q.jsonl")
    cfg_txt = json.dumps({"seed0": SEED0, "configs": cfgs}, indent=1) + "\n"
    q_txt = "".join(json.dumps(x) + "\n" for x in q)
    if "--check" in sys.argv[1:]:
        ok = (open(cfg_path, encoding="utf-8").read() == cfg_txt and open(q_path, encoding="utf-8").read() == q_txt)
        print("FROZEN CHECK", "OK" if ok else "MISMATCH")
        return 0 if ok else 3
    if os.path.exists(cfg_path) or os.path.exists(q_path):
        print("REFUSED: %s / %s exist - the list is frozen; use --check" % (cfg_path, q_path))
        return 3
    bad = seeds_unused(cfgs)
    if bad:
        print("REFUSED: a frozen seed already appears in", bad[:10])
        return 3
    existing = [x["out"] for x in q if os.path.exists(x["out"])]
    if existing:
        print("REFUSED: outputs already exist, e.g.", existing[:3])
        return 3
    with open(cfg_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(cfg_txt)
    with open(q_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(q_txt)
    kinds = {}
    for c in cfgs:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print("configurations %d %s | runs %d (B/F1/F12 x %d + K %d) | seeds %d-%d"
          % (len(cfgs), kinds, len(q), len(cfgs), sum(1 for c in cfgs if c.get("k_arm")),
             cfgs[0]["seed"], cfgs[-1]["seed"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
