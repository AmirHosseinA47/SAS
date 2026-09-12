"""Dock-fix round: emit the run queue for outputs/_dim_pool.sh.

Arms are built from CONFIG CONSTANTS ONLY - there is no per-arm code branch
anywhere - so an arm-minus-arm difference attributes to exactly one change.

  dfzero    BASE_STATION_MODE=0 at the shipped defaults, WITH THE FIX ON. Must be
            byte-identical to this round's own dcoff. This is the statement that
            matters most: at mode 0 none of the new code is reachable, so the
            SHIPPED configuration is untouched even though the fix defaults on.
  dfkill    dcB's configuration + BASE_STATION_DOCK_FIX=0. THE STRONG CONTROL: it
            runs every changed code path with the switch off and must reproduce
            _ffr_dcB_* field for field. dfzero alone would not prove that, because
            at mode 0 the changed code never executes.
  dfA..dfD  the depot-cost round's four arms, unchanged except that the fix is on.
            Read against _ffr_dcA_* .. _ffr_dcD_*, seed for seed.
  dfm2ref   BASE_STATION_MODE=2 with the fix OFF. The SAME-INSTRUMENT REFERENCE
            for the mode-2 claim. The base-station round's own bsret artifacts
            predate the depot round's additions to `base_station` and `rtb_log`,
            so comparing dfm2fix against them directly would show instrument
            differences and read them as behaviour - which has happened twice in
            this project. This arm is what dfm2fix is actually compared to.
  dfm2fix   the same at BASE_STATION_MODE=2 with the fix on. THE STRONGEST SINGLE
            SIGNAL IN THE ROUND: 5 of these 13 runs deadlock permanently at HEAD.
  dfW0/dfW1 BASE_STATION_RETURN_MECHANISM=1 with two depots, waypoint fix off and
            on. The waypoint defect is a SEPARATE defect behind a SEPARATE switch
            and is measured apart from the docking fix, so an outcome attributes
            to one or the other. It is unreachable under mechanism 2 - the
            generator returns before it at local_adaptation_generator.py:1986 -
            so no mechanism-2 arm can see it and none of the arms above is
            confounded by it.

TAG COLLISION, checked rather than assumed. Several readers in outputs/ glob by
PREFIX, and the Windows filesystem is CASE-INSENSITIVE, so `_ffr_dfC*` would
match a `_ffr_dfctl_*` file. Every pair of tags below was checked for
case-insensitive prefixing: an earlier draft used `dfctl`, which `dfC` matches,
and `dfM2`, which `dfM2off` extends. Neither survives here.

INSTRUMENT DRIFT: NONE. This round adds no recorded field and does not touch
outputs/_ffr_harness.py, so the depot-cost artifacts already on disk are the
"before" side of every comparison and cost zero runs. The three new agent
attributes are invisible: the harness serialises an explicit field list and never
__dict__ or vars().

usage:
  python outputs/_df_queue.py > outputs/_df_queue.txt
  MAXPAR=10 MINFREE_KB=2500000 bash outputs/_dim_pool.sh outputs/_df_queue.txt
"""
from __future__ import annotations

import sys

REPO = "E:/Projects/SAS"

CANONICAL = (
    [("east", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
    + [("east", "default", s) for s in (101, 202, 303)]
)
FRESH = (
    [("east", "half", s) for s in (606, 707, 808, 909, 1010)]
    + [("south", "half", s) for s in (606, 707, 808, 909, 1010)]
)
# The waypoint arms only need to show the mechanism-1 difference, not to carry a
# mission-outcome claim, so they run the east/half canonical seeds only.
WAYPOINT = [("east", "half", s) for s in (101, 202, 303, 404, 505)]

ARMED = "--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=2"
DIST = "--set UAV_RETURN_TO_BASE_RESERVE=0 --set BASE_STATION_RETURN_MARGIN=39.23"
TWO_DEPOT = "--set BASE_STATION_DEPOTS=9 --set BASE_STATION_SPAWN_SPLIT=2"
MECH1 = ("--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=1 %s %s"
         % (DIST, TWO_DEPOT))

# (tag, extra harness args, sample)
# ORDERED BY WHAT THE ROUND CANNOT DO WITHOUT. The pool is restartable - it skips
# any run whose output already exists - and this wave has already died once to a
# Git-Bash fork failure, so the arms that decide the gate run FIRST and a death
# partway through costs the least important arms rather than the decisive ones.
ARMS = [
    ("dfzero", "--set BASE_STATION_MODE=0", "both"),
    ("dfkill", "%s %s --set BASE_STATION_DOCK_FIX=0" % (ARMED, DIST), "both"),
    ("dfm2ref", "--set BASE_STATION_MODE=2 --set BASE_STATION_RETURN_MECHANISM=2"
                " --set BASE_STATION_DOCK_FIX=0", "canonical"),
    ("dfm2fix", "--set BASE_STATION_MODE=2 --set BASE_STATION_RETURN_MECHANISM=2",
     "canonical"),
    ("dfB", "%s %s" % (ARMED, DIST), "both"),
    ("dfA", ARMED, "both"),
    ("dfC", "%s %s --set BASE_STATION_DEPOTS=16" % (ARMED, DIST), "both"),
    ("dfD", "%s %s %s" % (ARMED, DIST, TWO_DEPOT), "both"),
    ("dfW0", "%s --set BASE_STATION_WAYPOINT_FIX=0" % MECH1, "waypoint"),
    ("dfW1", "%s --set BASE_STATION_WAYPOINT_FIX=1" % MECH1, "waypoint"),
]

SAMPLES = {"canonical": CANONICAL, "fresh": FRESH,
           "both": CANONICAL + FRESH, "waypoint": WAYPOINT}

# Every arm carries the same harness flags - a flag on some arms and not others
# changes the recorded shape and makes the arms incomparable on the identity
# fields. --uav-actions is what carries the per-UAV `burning` flag that the
# drone-steps-in-fire measurement reads.
COMMON = "--uav-actions"


def check_tags():
    """Case-insensitive prefix check. A reader that globs `_ffr_<tag>*` on a
    case-insensitive filesystem would sweep one arm's files into another's."""
    tags = [t for t, _e, _s in ARMS]
    for a in tags:
        for b in tags:
            if a is not b and b.lower().startswith(a.lower()):
                raise SystemExit("tag %r is a prefix of %r - rename one" % (a, b))
    return tags


def main() -> int:
    # Queue files written on Windows can carry CR into the last field, which
    # argparse then sees as a stray argument. The pool strips it defensively;
    # emitting LF here means it never has to.
    sys.stdout.reconfigure(newline="\n")
    check_tags()
    total = 0
    for tag, extra, sample in ARMS:
        for wind, roles, seed in SAMPLES[sample]:
            args = (COMMON + " " + extra).strip()
            print("%s|%s|%s|%s|%d|%s" % (tag, REPO, wind, roles, seed, args))
            total += 1
    print("# %d runs total" % total, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
