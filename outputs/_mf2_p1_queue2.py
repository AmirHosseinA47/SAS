"""fix2 Part 1: second diagnostic queue (tag mf2D). Same probe argv as the fix1 invariant runs
(outputs/_sd_mf1P_*.json.argv), so each hooked run can be checked value-identical to its twin.
  mf2D_hold_<cfg>  outputs/_mf2_p1_holds.py on A/S, C/N, D/E, D/W (item 2: hold origins)
  mf2D_sweep_B_W   outputs/_mf2_p1_sweep.py on B/W, 300 steps, windows 100-140 and 265-300
                   (item 3: the B/west edge loop)
"""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")


def probe_args(cfg, name, steps=None):
    with open(os.path.join(OUT, "_sd_mf1P_%s.json.argv" % cfg), encoding="utf-8") as fh:
        a = list(json.load(fh)["argv"][1:])
    out = os.path.join(OUT, "_sd_%s.json" % name)
    a[a.index("--out") + 1] = out
    a[a.index("--tag") + 1] = name
    if steps is not None:
        a[a.index("--steps") + 1] = str(steps)
    return a, out


def main():
    lines = []
    for cfg in ("A_S", "C_N", "D_E", "D_W"):
        name = "mf2D_hold_%s" % cfg
        a, out = probe_args(cfg, name)
        lines.append({"name": name, "argv": [os.path.join(OUT, "_mf2_p1_holds.py"), "--"] + a, "out": out})
    name = "mf2D_sweep_B_W"
    a, out = probe_args("B_W", name, steps=300)
    lines.append({"name": name, "argv": [os.path.join(OUT, "_mf2_p1_sweep.py"), "--win", "100-140",
                                         "--win", "265-300", "--"] + a, "out": out})
    path = os.path.join(OUT, "_mf2_q_p1b.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")
    print("wrote %d lines to %s" % (len(lines), path))


if __name__ == "__main__":
    sys.exit(main())
