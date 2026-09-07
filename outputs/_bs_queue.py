"""Base-station round: emit the run queue for outputs/_dim_pool.sh.

Arms are built from CONFIG CONSTANTS ONLY - there is no per-arm code branch
anywhere - so a level-N minus level-(N-1) difference attributes exactly one
increment. BASE_STATION_MODE is an ordinal ladder and each level is a strict
superset of the one below.

  bsbase    the 16b2da8 checkout, measured by THIS harness so every recorded
            field is comparable. The identity reference.
  bsoff     feature source, BASE_STATION_MODE=0. Must be byte-identical to
            bsbase; that is the kill-switch gate.
  bsspawn   +spawn at the depot (UAVs and firefighters)
  bsspawnu  +spawn, UAVs only - attributes the firefighter half of the spawn
            move, which is where the rescue rate lives
  bsret     +return-to-base, hardcoded agent route
  bsretp    +return-to-base, planner route
  bsfull    +recharge, hardcoded route
  bsfullp   +recharge, planner route

usage:
  python outputs/_bs_queue.py > outputs/_bs_queue.txt
  MAXPAR=10 MINFREE_KB=3000000 bash outputs/_dim_pool.sh outputs/_bs_queue.txt
"""
from __future__ import annotations

import sys

REPO = "E:/Projects/SAS"
BASE_REPO = (
    "C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/"
    "cf6ada8d-34c4-4705-9076-db5f32fc96be/scratchpad/base16b2da8"
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

# (tag, repo, extra harness args, runs on the fresh sample too)
ARMS = [
    ("bsbase",   BASE_REPO, "",                                                        True),
    ("bsoff",    REPO,      "--set BASE_STATION_MODE=0",                               True),
    ("bsspawn",  REPO,      "--set BASE_STATION_MODE=1",                               False),
    ("bsspawnu", REPO,      "--set BASE_STATION_MODE=1 --set BASE_STATION_SPAWN_FIREFIGHTERS=0", False),
    ("bsret",    REPO,      "--set BASE_STATION_MODE=2 --set BASE_STATION_RETURN_MECHANISM=2", False),
    ("bsretp",   REPO,      "--set BASE_STATION_MODE=2 --set BASE_STATION_RETURN_MECHANISM=1", False),
    ("bsfull",   REPO,      "--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=2", True),
    ("bsfullp",  REPO,      "--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=1", True),
]

# Every arm carries the same harness flags, the baseline checkout arm included -
# a flag on some arms and not others changes the recorded shape and makes the
# arms incomparable on the identity fields.
COMMON = "--uav-actions"


def main() -> int:
    # Queue files written on Windows can carry CR into the last field, which
    # argparse then sees as a stray argument. The pool strips it defensively;
    # emitting LF here means it never has to.
    sys.stdout.reconfigure(newline="\n")
    total = 0
    for tag, repo, extra, do_fresh in ARMS:
        combos = list(CANONICAL) + (list(FRESH) if do_fresh else [])
        # NOTE: the fresh sample uses the SAME tag, not a "fresh" suffix -
        # outputs/_ih_arms.py picks its combo list by testing for the substring
        # "fresh" in the tag, so a tag must never contain it by accident.
        for wind, roles, seed in combos:
            args = (COMMON + " " + extra).strip()
            print("%s|%s|%s|%s|%d|%s" % (tag, repo, wind, roles, seed, args))
            total += 1
    print("# %d runs total" % total, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
