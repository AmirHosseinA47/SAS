"""Emit the dimension round's run queue for outputs/_dim_pool.sh (stdout).

Order matters only for how early each comparison becomes possible: the
baseline, fix, control and instrumented arms first (the byte-identity gates),
then the fresh seeds (the load-bearing sample), then the pin-all check and the
three one-site-live ablation arms.

line: tag|repo|wind|roles|seed|extra harness args
"""
import os
import sys

BASE = ("C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/"
        "9f290476-6a7b-42cc-bad2-0d6d2ccb4449/scratchpad/base8520706")
FIX = "/e/Projects/SAS"

CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])

P, D, C = "_position_at_boundary", "_distance_from_boundary", "_execute_search_mode"

ARMS = [
    # tag, repo, sample, extra
    ("dimbase", BASE, CANON, ""),
    ("dimfix", FIX, CANON, ""),
    ("dimctrl", FIX, CANON, "--dim-hook deny"),
    ("diminst", FIX, CANON, "--dim-hook record --dim-observe"),
    ("dimfreshbase", BASE, FRESH, ""),
    ("dimfreshfix", FIX, FRESH, ""),
    ("dimpinall", FIX, CANON, "--dim-pin %s,%s,%s" % (P, D, C)),
    ("dimA", FIX, CANON, "--dim-pin %s,%s" % (D, C)),   # only P live
    ("dimB", FIX, CANON, "--dim-pin %s,%s" % (P, C)),   # only D live
    ("dimC", FIX, CANON, "--dim-pin %s,%s" % (P, D)),   # only the clamp live
]

if not os.path.isdir(BASE):
    print("baseline worktree missing: %s" % BASE, file=sys.stderr)
    sys.exit(2)

# LF only: a CRLF queue leaves a CR on the last field of every line, which the
# harness then receives as a stray argument.
sys.stdout.reconfigure(newline="\n")

n = 0
for tag, repo, sample, extra in ARMS:
    for wind, roles, seed in sample:
        print("|".join([tag, repo, wind, roles, str(seed), extra]))
        n += 1
print("# %d runs" % n, file=sys.stderr)
