"""isTrue round Part 3, PART 1 SECTION 5'S OWN IDENTITY RUNS (G1-c / G2 of outputs/isTrue_part1.txt 5.1 / 5.2 / 7):
the 8 census configurations of Part 1 3.0 (a) through the harness outputs/_ffr_harness.py (which mirrors
evaluate_scenarios), in four arms, so the ruling's "as in section 5" is met on the harness as well as on the
measurement chain (outputs/_ist3_queue.py).

usage: _ist3h_queue.py            writes outputs/_ist3h_q.jsonl (refuses to overwrite)
       _ist3h_queue.py --check    re-derives it and STOPS (exit 3) on any difference from the file on disk

CONFIGURATIONS (Part 1 3.0 (a), the same seeds; --steps 360, --roles half as there):
  S_east_101, S_west_103, S_south_102     shipped defaults, scenario D
  B5_east_101                             --set SEARCHER_TARGETING=5
  G1_east_101                             --set GLOBAL_PLANNER_MODE=1
  A_east_104, Bsc_east_104, C_east_104    --scenario A / B / C
ARMS: B (E:/Projects/SAS_wt/basef686 = f686e932), F12 (istrue, shipped), F1 (+ NUMPY_SCALAR_FLAGS=0),
  K (+ MR1_TRUTHINESS_FIX=0 + NUMPY_SCALAR_FLAGS=0). 32 runs. The harness file is istrue's for every arm (unchanged
  since f686e932); --repo picks the checkout the simulation is imported from.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = r"E:\Projects\SAS_wt\istrue"
BASE = r"E:\Projects\SAS_wt\basef686"
HARNESS = os.path.join(WT, "outputs", "_ffr_harness.py")
CONFIGS = (
    ("S_east_101", "east", 101, "D", ()),
    ("S_west_103", "west", 103, "D", ()),
    ("S_south_102", "south", 102, "D", ()),
    ("B5_east_101", "east", 101, "D", ("SEARCHER_TARGETING=5",)),
    ("G1_east_101", "east", 101, "D", ("GLOBAL_PLANNER_MODE=1",)),
    ("A_east_104", "east", 104, "A", ()),
    ("Bsc_east_104", "east", 104, "B", ()),
    ("C_east_104", "east", 104, "C", ()),
)
ARMS = (
    ("B", BASE, ()),
    ("F12", WT, ()),
    ("F1", WT, ("NUMPY_SCALAR_FLAGS=0",)),
    ("K", WT, ("MR1_TRUTHINESS_FIX=0", "NUMPY_SCALAR_FLAGS=0")),
)
QUEUE = os.path.join(HERE, "_ist3h_q.jsonl")


def lines() -> list[dict]:
    out = []
    for cid, wind, seed, scen, sets in CONFIGS:
        for arm, repo, arm_sets in ARMS:
            name = "ist3h_%s_%s" % (arm, cid)
            jout = os.path.join(WT, "outputs", "_%s.json" % name)
            argv = [HARNESS, "--repo", repo, "--wind", wind, "--seed", str(seed), "--steps", "360", "--scenario", scen,
                    "--out", jout, "--tag", "ist3h%s" % arm]
            for s in sets + arm_sets:
                argv += ["--set", s]
            out.append({"name": name, "argv": argv, "out": jout, "cwd": repo})
    return out


def text() -> str:
    return "".join(json.dumps(ln, sort_keys=True) + "\n" for ln in lines())


def main() -> int:
    if sys.argv[1:] == ["--check"]:
        with open(QUEUE, encoding="utf-8") as f:
            same = f.read() == text()
        print("H QUEUE", "OK" if same else "DIFFERS")
        return 0 if same else 3
    if os.path.exists(QUEUE):
        print("refusing to overwrite", QUEUE)
        return 2
    with open(QUEUE, "w", encoding="utf-8", newline="\n") as f:
        f.write(text())
    print("wrote", QUEUE, len(lines()), "lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
