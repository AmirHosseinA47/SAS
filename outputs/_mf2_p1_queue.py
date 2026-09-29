"""fix2 Part 1: queue for the alarm-attribution wave (tag mf2H) - the 16 fix1 invariant probe
configurations (outputs/_sd_mf1P_*.json: 4 scenarios x 4 winds, seeds 9601-9616, GPM 0,
360 steps, shipped defaults) re-run under outputs/_mf2_p1_hooks.py, argv otherwise identical."""
import json
import os
import sys

REPO = r"E:\Projects\SAS"
OUT = os.path.join(REPO, "outputs")


def main():
    lines = []
    for sc in "ABCD":
        for w in ("E", "N", "S", "W"):
            ref = os.path.join(OUT, "_sd_mf1P_%s_%s.json.argv" % (sc, w))
            with open(ref, encoding="utf-8") as fh:
                argv = json.load(fh)["argv"]
            probe_args = list(argv[1:])
            name = "mf2H_%s_%s" % (sc, w)
            out = os.path.join(OUT, "_sd_%s.json" % name)
            probe_args[probe_args.index("--out") + 1] = out
            probe_args[probe_args.index("--tag") + 1] = name
            lines.append({"name": name, "argv": [os.path.join(OUT, "_mf2_p1_hooks.py"), "--"] + probe_args,
                          "out": out})
    path = os.path.join(OUT, "_mf2_q_p1.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")
    print("wrote %d lines to %s" % (len(lines), path))


if __name__ == "__main__":
    sys.exit(main())
