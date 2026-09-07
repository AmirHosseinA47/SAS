"""Emit the interior-hazard round's Part 3 queue for outputs/_dim_pool.sh (stdout).

Order: the two identity proofs first (patched tree at 0 == e76c806, at 99 == the
gate+retreat replay), then the range-6 arm, then the fresh seeds of all three,
then 8520706 on the fresh seeds with labels (the recorded dimfreshbase runs are
the outcome baseline; this arm only adds the per-step labels).
line: tag|repo|wind|roles|seed|extra harness args
"""
import sys

BASE = ("C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/"
        "9bc02eb9-696e-4ce4-aec7-6f7cd580e2ca/scratchpad/base8520706")
SRC = "/e/Projects/SAS"

CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])

OFF = "--uav-actions --set VICTIM_SEARCHER_HAZARD_RETREAT_RANGE=0"
R99 = "--uav-actions"
R6 = "--uav-actions --set VICTIM_SEARCHER_HAZARD_RETREAT_RANGE=6"

ARMS = [
    ("ihoff", SRC, CANON, OFF),
    ("ihrest99", SRC, CANON, R99),
    ("ihrest6", SRC, CANON, R6),
    ("ihrest99fresh", SRC, FRESH, R99),
    ("ihrest6fresh", SRC, FRESH, R6),
    ("ihofffresh", SRC, FRESH, OFF),
    ("ihbasefresh", BASE, FRESH, "--uav-actions"),
]

sys.stdout.reconfigure(newline="\n")
n = 0
for tag, repo, sample, extra in ARMS:
    for wind, roles, seed in sample:
        print("|".join([tag, repo, wind, roles, str(seed), extra]))
        n += 1
print("# %d runs" % n, file=sys.stderr)
