"""firemech round 2, Part 1: the SECOND diagnosis probe queue (outputs/_fm2_probe_harness.py).

Written after wave 1 (outputs/_fm2probe_queue.txt) showed, on the canonical screen:
  - CRN removes extinguish's coin flip (f2cES 11 up / 0 down) and weakens firebreak;
  - the resolved-victims gate is rescue-neutral by construction but keeps less fire effect.
This wave asks the questions those raise. Canonical 13 lines first, then fresh 10.

  f2cEFS  full configuration, CRN fire           does the mechanic cost rescues without draw shifts?
  f2cDRY  full configuration DRY, CRN fire       its positioning-only control (fire == f2cOFF)
  f2cGW   full configuration + gate, CRN fire    physical fire effect kept under the gate
  f2cGF   firebreak only + gate, CRN fire        the same for firebreak only
  f2cGES  extinguish + S + gate, CRN fire        the same for extinguish + S
  f2GES   extinguish + S + gate, stock fire      stock counterpart of f2cGES (f2GW / f2GF ran in wave 1)
  f2b404sN  fmEFS on south/half/404 with FM2P_WRITE_BEFORE=N, N in 9, 12, 13, 14, 16
            (outputs/_fm2_diag_south404.txt section 6: 9 -> fmDRY's fire, 16 -> fmEFS's fire,
             12 and 13 give identical fires, 14 a new realisation after step ~102)

Tags are new (prefix f2), none is a prefix of another, none exists anywhere under outputs/.
Written with LF line endings.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _fm2_queue as Q1  # noqa: E402

E, F, S, DRY, CRN, GATE = Q1.E, Q1.F, Q1.S, Q1.DRY, Q1.CRN, Q1.GATE

ARMS = {
    "f2cEFS": [E, F, S, CRN],
    "f2cDRY": [E, F, S, DRY, CRN],
    "f2cGW": [E, F, S, GATE, CRN],
    "f2cGF": [F, GATE, CRN],
    "f2cGES": [E, S, GATE, CRN],
    "f2GES": [E, S, GATE],
}
BISECT = {"f2b404s%d" % s: [E, F, S, "--set FM2P_WRITE_BEFORE=%d" % s] for s in (9, 12, 13, 14, 16)}


def line(tag, sets, wind, roles, seed):
    return "%s|%s|%s|%s|%d|%s" % (tag, Q1.REPO, wind, roles, seed, " ".join(["--uav-actions"] + sets))


def main():
    all_tags = list(ARMS) + list(BISECT) + list(Q1.ARMS)
    for a in all_tags:
        for b in all_tags:
            if a != b and b.startswith(a):
                raise SystemExit("tag %s is a prefix of %s" % (a, b))
    lines = []
    for tag, sets in BISECT.items():
        lines.append(line(tag, sets, "south", "half", 404))
    for tag, sets in ARMS.items():
        for w, r, s in Q1.CANONICAL:
            lines.append(line(tag, sets, w, r, s))
    for tag, sets in ARMS.items():
        for w, r, s in Q1.FRESH:
            lines.append(line(tag, sets, w, r, s))
    path = os.path.join(HERE, "_fm2probe2_queue.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for ln in lines:
            f.write(ln + "\n")
    print("%d runs -> %s" % (len(lines), path))


if __name__ == "__main__":
    main()
