"""Detail on each sole-exit / emptied-by-last_cell event: would re-admission
actually be TAKEN by the tier chain, what did the unit do instead, and did it die?

Read-only. Companion to _lc_p1.py.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _lc_p1 import BASE13, arm_rows, fresh_cells, tup  # noqa: E402


def analyse(cells, label):
    print("=" * 78)
    print(label)
    print("=" * 78)
    n_ev = n_stalledpath = n_normalpath = 0
    n_would_move = n_bypassed = n_diedafter = 0
    for w, r, s, d in arm_rows("none", cells):
        tag = "%s_%s_%d" % (w, r, s)
        # per (seed, ff) step -> end-of-step pos / dead
        pos = {}
        dead_at = {}
        for row in d["fftrace"]:
            k = (int(row["seed"]), str(row["ff"]))
            pos[(k[0], k[1], int(row["step"]))] = tup(row["pos"])
            if row["dead"] and k not in dead_at:
                dead_at[k] = int(row["step"])
        surv = {(int(x["seed"]), str(x["ff"]), int(x["step"])): x for x in d["surv"]}
        mt = {(int(x["seed"]), str(x["ff"]), int(x["step"])): x for x in d["movetoward"]}
        rb = set((int(x["seed"]), str(x["ff"]), int(x["step"])) for x in d["route_blocked"])
        for c in d["cand"]:
            if not (c["sole_exit"] or c["emptied_by_lc"]):
                continue
            n_ev += 1
            key = (int(c["seed"]), str(c["ff"]), int(c["step"]))
            sv = surv.get(key)
            mv = mt.get(key)
            stalled = bool(c["stalled"])
            n_stalledpath += stalled
            n_normalpath += (not stalled)
            lc_dist = c["lc_dist"]
            cur = int(c["cur_dist"])
            # Would the tier chain actually take last_cell if re-admitted?
            #   stalled idle path -> _pick_improving_retreat only (needs ideal
            #     or strictly improving, or lower risk at >= dist)
            #   normal path -> tier-3 fallback takes the sole candidate anyway
            improving = (lc_dist is not None and lc_dist > cur)
            would = (not stalled) or improving
            n_would_move += bool(would)
            moved = bool(sv and sv["moved"])
            bypass = bool(mv and mv["moved"])
            n_bypassed += bypass
            dk = (int(c["seed"]), str(c["ff"]))
            dstep = dead_at.get(dk)
            gap = (dstep - int(c["step"])) if dstep else None
            if gap is not None and 0 <= gap <= 30:
                n_diedafter += 1
            print("  %-18s s%-4d %-10s cell=%-9s lc=%-9s cur_d=%d lc_d=%s "
                  "idle=%-5s stall=%-5s sole=%-5s | survmoved=%-5s mt_moved=%-5s "
                  "rb=%-5s | improving=%-5s WOULD_MOVE=%-5s | death=%s (+%s)"
                  % (tag, c["step"], c["ff"], tuple(c["cell"]),
                     tuple(c["last_cell"]) if c["last_cell"] else None,
                     cur, lc_dist, c["idle"], stalled, c["sole_exit"],
                     moved, bypass, key in rb, improving, would, dstep, gap))
    print("  ----")
    print("  events                              %d" % n_ev)
    print("    on the stalled-revalidation path  %d" % n_stalledpath)
    print("    on the normal scan path           %d" % n_normalpath)
    print("  re-admission would be TAKEN         %d" % n_would_move)
    print("  unit moved anyway via _move_toward  %d" % n_bypassed)
    print("  unit dead within 30 steps after     %d" % n_diedafter)
    print()


if __name__ == "__main__":
    analyse(BASE13, "BASELINE 13-RUN SAMPLE - every sole-exit / emptied-by-lc event")
    analyse(fresh_cells(), "FRESH SEEDS - every sole-exit / emptied-by-lc event")
