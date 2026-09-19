"""firemech round 2, Part 1: the DIAGNOSIS probe queue (outputs/_fm2_probe_harness.py).

Queue line format (outputs/_dcd4_pool.sh): tag|repo|wind|roles|seed|extra harness args.
Every run records --uav-actions. Canonical 13 lines come first, then fresh 10, so the
canonical screen of every arm completes before any fresh run starts.

Tags use the prefix f2 and are NEW: no file under outputs/ (top level, _ffr_logs, or
the quarantined outputs/_firemech_rewound_20260914/) carries any f2 tag, and no tag
below is a prefix of another (_ffr_rbcompare.py globs <tag>*).

  f2IDD   fmDRY configuration through the probe harness, no FM2P key -> must equal
          fmDRY value for value (the wrapper is a pass-through). canonical only.
  f2U0D   fmDRY + only ff_unit_0 may engage           positioning, unit 0 alone
  f2U1D   fmDRY + only ff_unit_1 may engage           positioning, unit 1 alone
  f2L3D   fmDRY + commitment limit 3 cells            positioning, bounded
  f2L8D   fmDRY + commitment limit 8 cells            positioning, bounded
  f2GD    fmDRY + engage only when no victim unresolved   positioning under the gate
  f2GW    fmEFS + the same gate                        fire effect kept under the gate
  f2GF    fmF   + the same gate                        firebreak-only under the gate
  f2cOFF  feature off, CRN fire                        the CRN control
  f2cES   E + S, CRN fire                              extinguish+S without draw shifts
  f2cF    F, CRN fire                                  firebreak without draw shifts

Written with LF line endings (windows-bash-tool-gotchas).
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "E:/Projects/SAS"

E = "--set FF_FIREFIGHT_EXTINGUISH=1"
F = "--set FF_FIREFIGHT_FIREBREAK=1"
S = "--set FF_FIREFIGHT_ENGAGED_RETREAT_RANGE=1"
DRY = "--set FF_FIREFIGHT_DRY_RUN=1"
CRN = "--set FM2P_CRN=1"
GATE = "--set FM2P_GATE=resolved"

ARMS = {
    "f2IDD": [E, F, S, DRY],
    "f2U0D": [E, F, S, DRY, "--set FM2P_ENGAGE_ONLY=ff_unit_0"],
    "f2U1D": [E, F, S, DRY, "--set FM2P_ENGAGE_ONLY=ff_unit_1"],
    "f2GW": [E, F, S, GATE],
    "f2GD": [E, F, S, DRY, GATE],
    "f2L3D": [E, F, S, DRY, "--set FM2P_LEASH=3"],
    "f2L8D": [E, F, S, DRY, "--set FM2P_LEASH=8"],
    "f2GF": [F, GATE],
    "f2cOFF": [CRN],
    "f2cES": [E, S, CRN],
    "f2cF": [F, CRN],
}
CANONICAL_ARMS = list(ARMS)
FRESH_ARMS = [a for a in ARMS if a != "f2IDD"]

CANONICAL = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])


def line(tag, wind, roles, seed):
    extra = " ".join(["--uav-actions"] + ARMS[tag])
    return "%s|%s|%s|%s|%d|%s" % (tag, REPO, wind, roles, seed, extra)


def main():
    tags = [t for t in ARMS]
    for a in tags:
        for b in tags:
            if a != b and b.startswith(a):
                raise SystemExit("tag %s is a prefix of %s" % (a, b))
    lines = []
    for tag in CANONICAL_ARMS:
        for w, r, s in CANONICAL:
            lines.append(line(tag, w, r, s))
    for tag in FRESH_ARMS:
        for w, r, s in FRESH:
            lines.append(line(tag, w, r, s))
    path = os.path.join(HERE, "_fm2probe_queue.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for ln in lines:
            f.write(ln + "\n")
    print("%d runs -> %s" % (len(lines), path))


if __name__ == "__main__":
    main()
