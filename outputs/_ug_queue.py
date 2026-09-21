"""Ungated round, Part 3: write the wave queues from the pre-registered arm table
(outputs/ungated_part1.txt 6.3) and the pre-registered seeds (outputs/_ug_seeds.py).

  _ug_queue.txt      stock harness arms + the FLIP route_blocked shards (ugGD)
  _ug_crn_queue.txt  the CRN arms (run with HARNESS=outputs/_fm2_probe_harness.py)
  _ug_rbC_queue.txt  the CONTROL route_blocked shards (ugGC; run with RBSCRIPT pointing
                     into the control worktree - the rb repo field is informational)

Order inside a queue only decides which comparison becomes possible first: the G1
identity arms on the canonical 13 lead, so a failed identity stops the round early.
Written with LF line endings (windows-bash-tool-gotchas: CR in a queue field breaks
argparse).

  .venv/Scripts/python.exe -B outputs/_ug_queue.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _ug_seeds  # noqa: E402

FLIP = "E:/Projects/SAS"
CTRL = "E:/Projects/SAS_wt/base11c3661"
STEPS = 240
UA = "--uav-actions"
EXPLICIT = ("--set FF_FIREFIGHT_EXTINGUISH=1 --set FF_FIREFIGHT_FIREBREAK=1 "
            "--set FF_FIREFIGHT_ENGAGED_RETREAT_RANGE=1 --set FF_FIREFIGHT_MISSION_GATE=0 "
            "--set FF_FIREFIGHT_DRY_RUN=0")
ANCHOR = EXPLICIT + " --set BASE_STATION_FIREPROOF=0 --set VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX=0"
DRY = "--set FF_FIREFIGHT_DRY_RUN=1"
CRN = "--set FM2P_CRN=1"

C13 = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("east", "default", s) for s in (101, 202, 303)])
F10 = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
       + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
RB4 = [("east", "half", s) for s in (111, 222, 333, 444)]
RB_SHARDS = [("a", "east", "101,202,303,404,505"), ("b", "east", "606,707,808,909"),
             ("c", "east", "111,222,333,444"), ("s", "south", "101,202,303,404,505")]


def u30():
    """The pre-registered U30 from the FROZEN record (outputs/_ug_seeds.txt), cross-checked
    against a fresh run of the selector, as _ug_analyze._u30() does. Added after the horizon
    follow-up's verification pass: this function still called the live selector, which is the
    self-reference defect class fixed in f737a3a (a mismatch now stops instead of writing a
    queue for a different set)."""
    frozen = _ug_seeds.frozen_u30()
    tuples, _rej, _src, _n = _ug_seeds.choose()
    if [(combo, seed) for combo, seed, _cell, _idx in tuples] != frozen:
        raise SystemExit("U30 MISMATCH: the selector no longer reproduces outputs/_ug_seeds.txt")
    out = [(combo.split("|")[0], combo.split("|")[1], seed) for combo, seed in frozen]
    assert len(out) == 30
    return out


def ff(tag, repo, tup, extra):
    w, r, s = tup
    return "ff|%s|%s|%s|%s|%d|%d|%s" % (tag, repo, w, r, s, STEPS, (UA + " " + extra).strip())


def write(path, lines):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("%-28s %d lines" % (os.path.basename(path), len(lines)))


def main():
    U30 = u30()
    stock = []
    # G1 first, canonical 13: flip default, explicit, anchor, control
    for tup in C13:
        stock += [ff("ugD", FLIP, tup, ""), ff("ugX", CTRL, tup, EXPLICIT),
                  ff("ugA", CTRL, tup, ANCHOR), ff("ugC", CTRL, tup, "")]
    for tup in F10:
        stock += [ff("ugD", FLIP, tup, ""), ff("ugX", CTRL, tup, EXPLICIT),
                  ff("ugA", CTRL, tup, ANCHOR), ff("ugC", CTRL, tup, "")]
    for tup in U30:
        stock += [ff("ugC", CTRL, tup, ""), ff("ugD", FLIP, tup, ""), ff("ugY", FLIP, tup, DRY)]
    for tup in RB4:
        stock += [ff("ugC", CTRL, tup, ""), ff("ugD", FLIP, tup, "")]
    for sfx, wind, seeds in RB_SHARDS:
        stock.append("rb|ugGD%s|%s|%s|half|%s|%d|" % (sfx, FLIP, wind, seeds, STEPS))
    write(os.path.join(HERE, "_ug_queue.txt"), stock)
    crn = []
    for tup in U30:
        crn += [ff("ugKC", CTRL, tup, CRN), ff("ugKD", FLIP, tup, CRN), ff("ugKY", FLIP, tup, CRN + " " + DRY)]
    write(os.path.join(HERE, "_ug_crn_queue.txt"), crn)
    rbc = ["rb|ugGC%s|%s|%s|half|%s|%d|" % (sfx, CTRL, wind, seeds, STEPS) for sfx, wind, seeds in RB_SHARDS]
    write(os.path.join(HERE, "_ug_rbC_queue.txt"), rbc)
    n_ff = sum(1 for l in stock + crn if l.startswith("ff|"))
    print("harness runs %d (stock %d + CRN %d), rb shards %d" % (
        n_ff, sum(1 for l in stock if l.startswith("ff|")), len(crn), 8))


if __name__ == "__main__":
    main()
