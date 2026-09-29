"""fix2 Part 2 CHECKPOINT P2-5 (tag mf2K): the 16 fix1 invariant configurations (outputs/_sd_mf1P_*:
A-D x N/S/E/W, seeds 9601-9616, GPM 0, 360 steps) with STAGGERED_LAUNCH_BATTERY = 1 and every other
fix2 switch 0 - item 4 alone - to decide whether DEPOT_STANDOFF_FIX is built (outputs/fix2_part1.txt
section 5, ruling D-10). Plain outputs/_sd_probe.py; argv otherwise the mf1P twin's."""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")
FIX2_OFF = ["GLOBAL_ANALYZER_FIRE_SOURCE_FIX=0", "FAILSAFE_REAL_ALARMS=0", "UAV_HOLD_STATIONARY=0",
            "SEARCHER_WIND_COVERAGE_FIX=0", "SEARCHER_GATE_NEAR_FIELD=0", "DEPOT_STANDOFF_FIX=0"]


def main():
    lines = []
    for sc in "ABCD":
        for w in ("E", "N", "S", "W"):
            with open(os.path.join(OUT, "_sd_mf1P_%s_%s.json.argv" % (sc, w)), encoding="utf-8") as fh:
                a = list(json.load(fh)["argv"][1:])
            name = "mf2K_%s_%s" % (sc, w)
            out = os.path.join(OUT, "_sd_%s.json" % name)
            a[a.index("--out") + 1] = out
            a[a.index("--tag") + 1] = name
            for s in FIX2_OFF + ["STAGGERED_LAUNCH_BATTERY=1"]:
                a += ["--set", s]
            lines.append({"name": name, "argv": [os.path.join(OUT, "_sd_probe.py")] + a, "out": out})
    path = os.path.join(OUT, "_mf2_q_p2k.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")
    print("wrote %d lines to %s" % (len(lines), path))


if __name__ == "__main__":
    sys.exit(main())
