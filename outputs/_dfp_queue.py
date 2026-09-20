"""Non-burnable-depot round: emit the wave queues for outputs/_dfp_pool.sh.

queue line: kind|tag|repo|wind|roles|seeds|steps|extra   (outputs/_dcd4rb_pool.sh format)
  kind ff  one harness run  (outputs/_ffr_harness.py), --repo selects the CHECKOUT
  kind rb  one route_blocked gate shard (outputs/_rblatch_campaign2.py). NOTE the
           rb job carries NO --repo: the campaign inserts its own parent directory
           on sys.path, so a shard measures the checkout the SCRIPT lives in - the
           dfp worktree for every shard below. That is why the rb control is the
           kill-switch arm rather than a second checkout.

TWO CHECKOUTS, both git worktrees of E:/Projects/SAS created for this round, so the
shared checkout (which another session is reading) is never touched:
  E:/Projects/SAS_wt/dfp            branch depotfireproof - the feature source
  E:/Projects/SAS_wt/base6281542    detached 6281542      - the control source

ARMS
  dfpB    OLD checkout, NO --set        the CONTROL: 6281542 at its shipped default
  dfpOFF  NEW checkout, switch 0        kill switch; must equal dfpB value for value
  dfpDRY  NEW checkout, switch 1 dry 1  cells identified, nothing written; every
                                        recorded FIRE value must equal dfpOFF's,
                                        digests included (DRY changes no fuel)
  dfpON   NEW checkout, switch 1        the real arm

Every arm states BASE_STATION_FIREPROOF explicitly rather than leaning on the
shipped default, so this queue cannot change meaning if the default is flipped
after the gate (flip_runner_register.txt's rule).

SAMPLES
  canonical 13  all four arms                     52 runs
  fresh 10      dfpB + dfpON                      20
  rb18 extras   east/half 111,222,333,444         8   - so E1/E2 can be read on the
                dfpB + dfpON                          same 18 seeds as the control
  west/north    5 seeds x 2 winds, dfpB + dfpON   20  - decision 6.4: the NW depot
                                                      is the primary one and both
                                                      of these winds drive fire at
                                                      it (Wind.is_on_wind_direction:
                                                      west spreads toward smaller x,
                                                      north toward larger y; NW is
                                                      x 0-4, y 45-49)
  rb gate       4 shards x {ON, control}          8 shards = 36 seed-runs

TAGS. Prefix dfp. No file under outputs/ matches _ffr_dfp* or _rblatch_camp2_dfp*
before this round, and no tag below is a prefix of another in either direction
(_ffr_rbcompare.py and the shard readers glob "<tag>*").

usage: python outputs/_dfp_queue.py pilot > /dev/null   # 4 runs, one seed, all arms
       python outputs/_dfp_queue.py wave  > /dev/null   # the 100 ff runs
       python outputs/_dfp_queue.py rb    > /dev/null   # the 8 gate shards
Written with LF line endings (windows-bash-tool-gotchas).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEW = "E:/Projects/SAS_wt/dfp"
OLD = "E:/Projects/SAS_wt/base6281542"

# The dcD configuration, PINNED. Character for character the depot round's dcrbD
# gate line and the dcd4rb round's arm D (outputs/_dcd4rb_queue.py:44-48), so a
# run here is comparable with dfD / d4D / drhD at the file level. Pinning is not
# decoration: outputs/flip_runner_register.txt records that 49 shell runners and
# 560 queue lines silently changed meaning at the 2026-09-14 default flip because
# they leaned on the default instead of stating it. Every value below IS the
# shipped default at 6281542, so this is the same configuration, said out loud.
DCD = ("--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=2"
       " --set UAV_RETURN_TO_BASE_RESERVE=0 --set BASE_STATION_RETURN_MARGIN=39.23"
       " --set BASE_STATION_DEPOTS=9 --set BASE_STATION_SPAWN_SPLIT=2")

OFF = "--set BASE_STATION_FIREPROOF=0"
ON = "--set BASE_STATION_FIREPROOF=1"
DRY = "--set BASE_STATION_FIREPROOF=1 --set BASE_STATION_FIREPROOF_DRY_RUN=1"

# dfpB runs the 6281542 checkout, which has no BASE_STATION_FIREPROOF at all.
# apply_scenario_config setattr-CREATES the attribute, so passing the switch there
# would create a constant that checkout's code never reads - harmless but a lie in
# extra_params. It is deliberately the one arm that does not carry it.
ARMS = {
    "dfpB": (OLD, DCD),
    "dfpOFF": (NEW, "%s %s" % (DCD, OFF)),
    "dfpDRY": (NEW, "%s %s" % (DCD, DRY)),
    "dfpON": (NEW, "%s %s" % (DCD, ON)),
}

CANONICAL = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
RB_EXTRA = [("east", "half", s) for s in (111, 222, 333, 444)]
WESTNORTH = ([("west", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("north", "half", s) for s in (101, 202, 303, 404, 505)])

# ---------------------------------------------------------------- CRN arms ---
# Decision 6.5 says per-seed outcome signs on a re-rolled seed are noise, and 16 of
# the 23 gate seeds re-roll. That rule is right, and it also leaves the round unable
# to say anything per seed. COMMON RANDOM NUMBERS remove the reason for the rule:
# with FM2P_CRN=1 (outputs/_fm2_probe_harness.py) Fire.step's single draw becomes
# crn_uniform(seed, cell unique_id, that cell's steps_counter) instead of the next
# number of the shared stream, so clearing 50 cells' fuel CANNOT shift the draw of
# any other cell. Every remaining difference is PHYSICAL.
# CRN arms compare only with CRN arms - the fire is a different, equally distributed
# realisation from stock - so both arms below are CRN and neither is comparable with
# dfpB / dfpON.
CRN = "--set FM2P_CRN=1"
CRN_ARMS = {"dfpCB": (OLD, "%s %s" % (DCD, CRN)),
            "dfpCON": (NEW, "%s %s %s" % (DCD, CRN, ON))}

RB_SHARDS = (("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
             ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505"))
RB_ARMS = {"dfpRBG": "%s %s" % (DCD, ON), "dfpRBC": "%s %s" % (DCD, OFF)}


def ff(tag, w, r, s):
    repo, sets = dict(ARMS, **CRN_ARMS)[tag]
    return ("ff|%s|%s|%s|%s|%d|240|--uav-actions %s" % (tag, repo, w, r, s, sets)).rstrip()


def rb(tag, w, seeds, sets):
    return ("rb|%s|%s|%s|half|%s|240|%s" % (tag, NEW, w, seeds, sets)).rstrip()


def check_tags(tags):
    """Intra-round prefix safety AND a filesystem check against every tag already
    on disk - in BOTH directions, case-insensitively, because the readers glob
    "<tag>*" and Windows folds case. Asserting this in a docstring, as the first
    version of this file did, is not the same as enforcing it."""
    import glob as _glob
    import re as _re
    for a in tags:
        for b in tags:
            if a != b and b.startswith(a):
                raise SystemExit("tag %s is a prefix of %s" % (a, b))
    existing = set()
    for pat, rx in ((("_ffr_*.json"), r"_ffr_(.+?)_(east|south|west|north)_"),
                    (("_rblatch_camp2_*.json"), r"_rblatch_camp2_(.+?)_D_")):
        for p in _glob.glob(os.path.join(HERE, pat)):
            m = _re.search(rx, os.path.basename(p))
            if m:
                existing.add(m.group(1))
    mine = {t for t in tags}
    clash = []
    for e in sorted(existing):
        if e in mine:
            continue
        for t in mine:
            if t.lower().startswith(e.lower()) or e.lower().startswith(t.lower()):
                clash.append("%s <-> %s" % (t, e))
    if clash:
        raise SystemExit("tag collides with an existing tag on disk: %s" % clash)
    print("tag check: %d this round, %d already on disk, 0 prefix collisions either way"
          % (len(mine), len(existing)))


def write(name, lines):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for ln in lines:
            f.write(ln + "\n")
    print("%d lines -> %s" % (len(lines), path))
    return path


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "wave"
    check_tags(list(ARMS) + list(CRN_ARMS)
               + ["%s%s" % (t, sh) for t in RB_ARMS for sh, _w, _s in RB_SHARDS])
    if what == "pilot":
        return write("_dfp_pilot_queue.txt",
                     [ff(t, "east", "half", 101) for t in ("dfpB", "dfpOFF", "dfpDRY", "dfpON")])
    if what == "crn":
        lines = []
        for tag in ("dfpCB", "dfpCON"):
            for w, r, s in CANONICAL + FRESH + WESTNORTH:
                lines.append(ff(tag, w, r, s))
        return write("_dfp_crn_queue.txt", lines)
    if what == "rb":
        return write("_dfp_rb_queue.txt",
                     [rb("%s%s" % (tag, sh), w, seeds, sets)
                      for tag, sets in RB_ARMS.items() for sh, w, seeds in RB_SHARDS])
    lines = []
    # canonical first, arm by arm, so the whole canonical screen of the round
    # lands before any fresh run starts (every prior round's ordering)
    for tag in ("dfpB", "dfpOFF", "dfpDRY", "dfpON"):
        for w, r, s in CANONICAL:
            lines.append(ff(tag, w, r, s))
    for tag in ("dfpB", "dfpON"):
        for w, r, s in FRESH:
            lines.append(ff(tag, w, r, s))
    for tag in ("dfpB", "dfpON"):
        for w, r, s in RB_EXTRA:
            lines.append(ff(tag, w, r, s))
    for tag in ("dfpB", "dfpON"):
        for w, r, s in WESTNORTH:
            lines.append(ff(tag, w, r, s))
    # NOTE, corrected after the fact: an earlier comment here claimed the pilot's
    # four runs would be adopted as VALID by this queue. They could not have been -
    # the pilot lines carry no dcD pins, so their extra_params can never equal a
    # wave line's, and _dcd4_validate.py compares extra_params exactly. They were
    # moved to outputs/_dfp_pilot_superseded/ by hand instead (they also predate
    # the display commit), and the wave started at valid=0 / missing=100.
    return write("_dfp_queue.txt", lines)


if __name__ == "__main__":
    main()
