"""fix2 Part 1: third diagnostic queue (tag mf2S) - outputs/_mf2_p1_strips.py on the fix1 invariant
configurations of all four scenarios under east and south wind (8 runs, argv of the
outputs/_sd_mf1P_*.json twins, so each is checked value-identical to its twin)."""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")


def main():
    lines = []
    for sc in "ABCD":
        for w in ("E", "S"):
            cfg = "%s_%s" % (sc, w)
            with open(os.path.join(OUT, "_sd_mf1P_%s.json.argv" % cfg), encoding="utf-8") as fh:
                a = list(json.load(fh)["argv"][1:])
            name = "mf2S_%s" % cfg
            out = os.path.join(OUT, "_sd_%s.json" % name)
            a[a.index("--out") + 1] = out
            a[a.index("--tag") + 1] = name
            lines.append({"name": name, "argv": [os.path.join(OUT, "_mf2_p1_strips.py"), "--"] + a, "out": out})
    path = os.path.join(OUT, "_mf2_q_p1c.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")
    print("wrote %d lines to %s" % (len(lines), path))


if __name__ == "__main__":
    sys.exit(main())
