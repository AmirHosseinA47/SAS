"""Depot-cost round: the ARMED refactor-inertness control, dcAref.

WHY THIS ARM EXISTS. The kill-switch gate proves mode 0 is byte-identical to
e703861 - but mode 0 executes NONE of the new code: _apply_return_to_base returns
at `mode < 2`, no depot is built, no berth is assigned. Arm dcA is the reference
that arms B, C and D are read against, and it runs at MODE 3, where every new code
path IS live: the generalised _build_base_station, the per-depot berth tables,
_rtb_select_berth, the latch, and the depot-scoped _rtb_inside_depot.

If the refactor moved single-depot mode-3 behaviour at all, then dcA is not "the
shipped feature re-measured" and every comparison in the round is against a
baseline that quietly moved. Nothing else in the round tests that.

dcAref is e703861's SOURCE at MODE 3 with the shipped single-depot defaults,
measured by THIS round's harness - identical instrument, identical config, the
only difference being the 790 lines of Part 2. dcA == dcAref is the claim.

ONE EXPECTED DIFFERENCE, and it is the instrument recording the source rather
than the source behaving differently: each rtb_log record is built by the SOURCE's
own agents.py, and e703861's agents.py does not know about `target_depot`,
`target_berth` or `home_depot`. Those three keys are therefore absent on the
dcAref side by construction. The comparison excludes exactly those three keys and
nothing else; outputs/_dc_arms.py --mode identity --rtb-new-keys does that.

usage:
  python outputs/_dc_refactor_queue.py > outputs/_dc_refactor_queue.txt
  MAXPAR=8 MINFREE_KB=2500000 bash outputs/_dim_pool.sh outputs/_dc_refactor_queue.txt
"""
from __future__ import annotations

import sys

BASE_REPO = (
    "C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/"
    "aabd7c4c-06e6-4ca4-b6be-e62841bf5ae7/scratchpad/dc_e703861"
)

CANONICAL = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)

# Exactly dcA's configuration, run against the pre-refactor source. Every other
# BASE_STATION_* constant is left at its shipped default on both sides, which is
# what makes this a one-variable comparison.
ARMED = "--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=2"
COMMON = "--uav-actions"


def main() -> int:
    # LF only: a CR reaches argparse as a stray argument on the last field.
    sys.stdout.reconfigure(newline="\n")
    n = 0
    for wind, roles, seed in CANONICAL:
        print("dcAref|%s|%s|%s|%d|%s"
              % (BASE_REPO, wind, roles, seed, (COMMON + " " + ARMED).strip()))
        n += 1
    print("# %d runs" % n, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
