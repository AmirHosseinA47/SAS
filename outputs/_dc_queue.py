"""Depot-cost round: emit the run queue for outputs/_dim_pool.sh.

Arms are built from CONFIG CONSTANTS ONLY - there is no per-arm code branch
anywhere - so an arm-minus-arm difference attributes to exactly one change.

  dcref   the e703861 worktree, measured by THIS round's harness. The
          same-instrument reference: arm A's own comparison target, and the thing
          dcoff has to be byte-identical to. Built BEFORE the wave, not after,
          because the harness gained fields this round (see below).
  dcoff   BASE_STATION_MODE=0. The kill switch. Must equal dcref on every
          recorded field.
  dcA     mode 3, flat-60 reserve, single NW depot. The previous round's bsfull
          re-measured at the current HEAD by the current instrument. THE
          REFERENCE THE OTHER THREE ARE READ AGAINST.
  dcB     dcA + distance-based reserve (flat floor 0, margin 39.23)
  dcC     dcB + a single CENTRAL depot
  dcD     dcB + two depots NW+SE, partition-nearest spawn split

INSTRUMENT DRIFT. This round adds `depots` / `uav_berths_by_depot` / `uav_home` /
`firefighter_home` inside the harness's existing `base_station` field, and
`target_depot` / `target_berth` / `home_depot` inside each `rtb_log` record.
Both are EMPTY at BASE_STATION_MODE 0 - base_station is None and rtb_log is
{uid: []} - so the kill-switch identity is untouched by the change. Nothing was
added to rtb_counters, uav_steps or any top-level field, because those are
populated at every mode and a new key there would drift the mode-0 baseline.
Arm A is re-measured regardless, because the source HEAD moved between f4e79d5
(where bsfull was measured) and e703861.

usage:
  python outputs/_dc_queue.py > outputs/_dc_queue.txt
  MAXPAR=10 MINFREE_KB=3000000 bash outputs/_dim_pool.sh outputs/_dc_queue.txt
"""
from __future__ import annotations

import sys

REPO = "E:/Projects/SAS"
BASE_REPO = (
    "C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/"
    "aabd7c4c-06e6-4ca4-b6be-e62841bf5ae7/scratchpad/dc_e703861"
)

CANONICAL = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)
FRESH = (
    [("east", "half", s) for s in (606, 707, 808, 909, 1010)]
    + [("south", "half", s) for s in (606, 707, 808, 909, 1010)]
)

ARMED = "--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=2"
# The distance regime: no flat floor, and the margin that carries the horizon
# constraint the flat floor used to carry. 39.23 is derived in
# outputs/depotcost_part1.txt section 3.5, not tuned.
DIST = "--set UAV_RETURN_TO_BASE_RESERVE=0 --set BASE_STATION_RETURN_MARGIN=39.23"

# (tag, repo, extra harness args, also runs the fresh sample)
ARMS = [
    ("dcref", BASE_REPO, "", False),
    ("dcoff", REPO, "--set BASE_STATION_MODE=0", True),
    ("dcA", REPO, ARMED, True),
    ("dcB", REPO, "%s %s" % (ARMED, DIST), True),
    ("dcC", REPO, "%s %s --set BASE_STATION_DEPOTS=16" % (ARMED, DIST), True),
    ("dcD", REPO, "%s %s --set BASE_STATION_DEPOTS=9 --set BASE_STATION_SPAWN_SPLIT=2"
     % (ARMED, DIST), True),
]

# Every arm carries the same harness flags, the reference arm included - a flag on
# some arms and not others changes the recorded shape and makes the arms
# incomparable on the identity fields.
COMMON = "--uav-actions"


def main() -> int:
    # Queue files written on Windows can carry CR into the last field, which
    # argparse then sees as a stray argument. The pool strips it defensively;
    # emitting LF here means it never has to.
    sys.stdout.reconfigure(newline="\n")
    total = 0
    for tag, repo, extra, do_fresh in ARMS:
        combos = list(CANONICAL) + (list(FRESH) if do_fresh else [])
        for wind, roles, seed in combos:
            args = (COMMON + " " + extra).strip()
            print("%s|%s|%s|%s|%d|%s" % (tag, repo, wind, roles, seed, args))
            total += 1
    print("# %d runs total" % total, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
