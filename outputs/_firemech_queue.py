"""Fire mechanic round 1: write the pool queues for Part 3 (outputs/firemech_part1.txt 7.1).

Queue line format (outputs/_dcd4_pool.sh): tag|repo|wind|roles|seed|extra harness args.
Every run records --uav-actions (drone exposure E1/E2 needs it; dfD has it).

  ref        fmREF on the detached 6adeb4f worktree, canonical 13 + fresh 10
  canonical  fmOFF + the nine configuration arms, canonical 13
  fresh      fmOFF + the six non-identity arms, fresh 10

Written with LF line endings: a CR on the last field reaches argparse as a stray
argument (windows-bash-tool-gotchas).
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURE_REPO = "E:/Projects/SAS"
REF_REPO = ("C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/"
            "1913a319-891c-4481-bbf4-731ed8a75e27/scratchpad/base6adeb4f")

E = "--set FF_FIREFIGHT_EXTINGUISH=1"
F = "--set FF_FIREFIGHT_FIREBREAK=1"
S = "--set FF_FIREFIGHT_ENGAGED_RETREAT_RANGE=1"
DRY = "--set FF_FIREFIGHT_DRY_RUN=1"

# tag -> extra --set arguments (feature repo)
ARMS = {
    "fmOFF": [],
    "fmEFS": [E, F, S],
    "fmDRY": [E, F, S, DRY],
    "fmF": [F],
    "fmES": [E, S],
    "fmFS": [F, S],
    "fmE": [E],        # identity by construction -> fmOFF
    "fmEF": [E, F],    # identity by construction -> fmF
    "fmS": [S],        # identity by construction -> fmOFF
}
CANONICAL_ARMS = ["fmOFF", "fmEFS", "fmDRY", "fmF", "fmES", "fmFS", "fmE", "fmEF", "fmS"]
FRESH_ARMS = ["fmOFF", "fmEFS", "fmDRY", "fmF", "fmES", "fmFS"]

CANONICAL = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
             + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])


def line(tag, repo, wind, roles, seed, sets):
    extra = " ".join(["--uav-actions"] + list(sets))
    return "%s|%s|%s|%s|%d|%s" % (tag, repo, wind, roles, seed, extra)


def write(name, lines):
    path = os.path.join(HERE, "_firemech_queue_%s.txt" % name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for ln in lines:
            f.write(ln + "\n")
    print("%-10s %3d runs -> %s" % (name, len(lines), os.path.relpath(path, os.path.dirname(HERE))))


RB_SHARDS = (("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
             ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505"))
# route_blocked gate tags: no tag may be a prefix of another, because
# _ffr_rbcompare.py globs _rblatch_camp2_<tag>*_D_<wind>.json
RB_ARMS = {"fmgOFF": "fmOFF", "fmgEFS": "fmEFS", "fmgFB": "fmF"}


def rb_queue():
    """outputs/_dcd4rb_pool.sh format: kind|tag|repo|wind|roles|seeds|steps|extra.

    rb  = one gate shard, the same command line outputs/_ffr_rbgate.sh runs;
    ff  = the four rbgate-18 harness tuples not already in canonical/fresh
          (east/half 111-444), so the harness side of the gate covers all 18.
    """
    lines = []
    for gtag, arm in RB_ARMS.items():
        sets = " ".join(ARMS[arm])
        for sh, wind, seeds in RB_SHARDS:
            lines.append("rb|%s%s|%s|%s|half|%s|240|%s" % (gtag, sh, FEATURE_REPO, wind, seeds, sets))
    for arm in ("fmOFF", "fmEFS", "fmF"):
        for s in (111, 222, 333, 444):
            extra = " ".join(["--uav-actions"] + ARMS[arm])
            lines.append("ff|%s|%s|east|half|%d|240|%s" % (arm, FEATURE_REPO, s, extra))
    return lines


def main():
    write("rb", rb_queue())
    write("ref", [line("fmREF", REF_REPO, w, r, s, []) for (w, r, s) in CANONICAL + FRESH])
    # arm-major order: each arm's 13 finish together, so identity checks can start early
    write("canonical", [line(tag, FEATURE_REPO, w, r, s, ARMS[tag])
                        for tag in CANONICAL_ARMS for (w, r, s) in CANONICAL])
    write("fresh", [line(tag, FEATURE_REPO, w, r, s, ARMS[tag])
                    for tag in FRESH_ARMS for (w, r, s) in FRESH])


if __name__ == "__main__":
    main()
