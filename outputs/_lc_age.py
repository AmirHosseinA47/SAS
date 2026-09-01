"""How long does _idle_retreat_last_cell persist, and what does the guard prevent?

(1) AGE: for every _retreat_candidates call, how many steps have passed since the
    unit last actually changed cell.  last_cell is written only immediately
    before a survival-move move, so age is an upper bound on how long the same
    cell has been refused.
(2) PREVENTION: how often the last_cell filter removes a cell while candidates
    remain (guard merely redirects) vs empties the set (guard blocks).
(3) Under arm c, how many ungated re-admissions turn into a tight reversal.

Read-only.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _lc_p1 import BASE13, arm_rows, fresh_cells, tup  # noqa: E402


def last_move_step(d):
    """(seed, ff, step) -> step of the most recent position change before `step`."""
    tr = defaultdict(list)
    for r in d["fftrace"]:
        tr[(int(r["seed"]), str(r["ff"]))].append((int(r["step"]), tup(r["pos"])))
    out = {}
    for k, rows in tr.items():
        rows.sort()
        last_change, cur = None, None
        for st, p in rows:
            if cur is not None and p != cur:
                last_change = st
            cur = p
            out[(k[0], k[1], st)] = last_change
    return out


def run(cells, label, arm="none"):
    print("=" * 78)
    print("%s  (arm %s)" % (label, arm))
    print("=" * 78)
    ages = defaultdict(int)
    tot = defaultdict(int)
    for w, r, s, d in arm_rows(arm, cells):
        lms = last_move_step(d)
        for c in d["cand"]:
            if c["last_cell"] is None:
                tot["lc_none"] += 1
                continue
            tot["lc_set"] += 1
            prev = lms.get((int(c["seed"]), str(c["ff"]), int(c["step"]) - 1))
            age = None if prev is None else int(c["step"]) - prev
            if age is not None:
                ages[min(age, 10)] += 1
                tot["age_sum"] += age
                tot["age_n"] += 1
                if age > 1:
                    tot["age_gt1"] += 1
            if c["lc_removed"]:
                tot["removed"] += 1
                if c["n_stock"] > 0:
                    tot["removed_redirect"] += 1
                else:
                    tot["removed_blocked"] += 1
    print("  scans with last_cell set / unset      %d / %d"
          % (tot["lc_set"], tot["lc_none"]))
    print("  last_cell filter actually removed     %d" % tot["removed"])
    print("    candidates remained (redirect)      %d" % tot["removed_redirect"])
    print("    set left EMPTY (blocked)            %d" % tot["removed_blocked"])
    if tot["age_n"]:
        print("  age of last_cell in steps: mean %.2f, >1 step in %d of %d scans"
              % (tot["age_sum"] / tot["age_n"], tot["age_gt1"], tot["age_n"]))
        print("    histogram (10+ bucketed): %s"
              % ", ".join("%s:%d" % ("10+" if k == 10 else k, ages[k])
                          for k in sorted(ages)))
    print()


def readmit_to_reversal(cells, arm):
    """Under arm b/c: does a re-admission become a tight reversal next step?"""
    n_readmit = n_rev = 0
    detail = []
    for w, r, s, d in arm_rows(arm, cells):
        moves = defaultdict(dict)
        for x in d["surv"]:
            if x["moved"]:
                moves[(int(x["seed"]), str(x["ff"]))][int(x["step"])] = (
                    tup(x["pos"]), tup(x["post"]))
        for c in d["cand"]:
            if not c.get("readmitted"):
                continue
            n_readmit += 1
            k = (int(c["seed"]), str(c["ff"]))
            st = int(c["step"])
            here = moves[k].get(st)
            nxt = moves[k].get(st + 1)
            rev = bool(here and nxt and nxt[1] == here[0])
            n_rev += rev
            detail.append(("%s_%s_%d" % (w, r, s), st, c["ff"], int(c["cur_dist"]),
                           here, nxt, rev))
    print("  arm %s: re-admissions %d, of which reversed on the very next step %d"
          % (arm, n_readmit, n_rev))
    for row in detail:
        print("    %-18s s%-4d %-10s cur_d=%d move=%s next=%s reversed=%s" % row)
    print()


if __name__ == "__main__":
    run(BASE13, "BASELINE 13-RUN SAMPLE - last_cell persistence and prevention")
    run(fresh_cells(), "FRESH SEEDS - last_cell persistence and prevention")
    print("=" * 78)
    print("RE-ADMISSION -> IMMEDIATE REVERSAL (what the guard is for)")
    print("=" * 78)
    for arm in ("b", "c"):
        readmit_to_reversal(BASE13, arm)
