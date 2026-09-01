"""Part 1 measurement over the arm-none dispatch-reachability sample.

Answers 2(a)-(d) of the brief, plus the provenance control (arm none must
reproduce c4d5a25's committed per-step traces) and the BFS cost figure.

    python outputs/_dr_p1.py [--arm none] [--prefix _dr]
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

CELLS13 = ["east_default_101", "east_default_202", "east_default_303",
           "east_half_101", "east_half_202", "east_half_303",
           "east_half_404", "east_half_505",
           "south_half_101", "south_half_202", "south_half_303",
           "south_half_404", "south_half_505"]
CELLSF = ["east_half_606", "east_half_707", "east_half_808",
          "east_half_909", "east_half_1010",
          "south_half_606", "south_half_707", "south_half_808",
          "south_half_909", "south_half_1010"]


EXTRA = []          # extension cells, set from --extra


def load(arm, prefix="_dr"):
    out = {}
    for cell in CELLS13 + CELLSF + EXTRA:
        p = os.path.join(HERE, "%s_%s_%s.json" % (prefix, arm, cell))
        if os.path.exists(p) and os.path.getsize(p) > 0:
            out[cell] = json.load(open(p))
    return out


def ev_of(d):
    e = d["evals"][0]
    return {"rescued": int(e.get("rescued", 0) or 0),
            "vdead": int(e.get("dead", 0) or 0),
            "ff": len(d["deaths"])}


# ------------------------------------------------------------------ outcomes
def dispatch_outcomes(cell, d):
    """Per dispatch: did the CHOSEN unit complete this rescue, and what
    happened to it if not.  The window for a dispatch runs from its step to
    the next dispatch of the same victim, or to the end of the run."""
    disp = d["dispatch"]
    vt = collections.defaultdict(dict)     # vid -> step -> status
    for r in d["vtrace"]:
        vt[r["v"]][r["step"]] = r["status"]
    ft = collections.defaultdict(dict)     # ff -> step -> row
    for r in d["fftrace"]:
        ft[r["ff"]][r["step"]] = r
    fol = collections.defaultdict(list)
    for r in d["follow_rows"]:
        fol[r["did"]].append(r)
    steps = d["steps"]

    by_victim = collections.defaultdict(list)
    for i, r in enumerate(disp):
        by_victim[r["victim"]].append(i)

    rows = []
    for i, r in enumerate(disp):
        sibs = by_victim[r["victim"]]
        nxt = steps + 1
        for j in sibs:
            if disp[j]["step"] > r["step"]:
                nxt = min(nxt, disp[j]["step"])
        end = min(nxt, steps + 1)
        chosen = r["arm_ff"] or r["stock_ff"]
        rescued = any(vt[r["victim"]].get(s, "") == "rescued"
                      for s in range(r["step"], end))
        fate = "completed" if rescued else "?"
        if not rescued:
            died = None
            for s in range(r["step"], end):
                row = ft[chosen].get(s)
                if row and row["dead"]:
                    died = s
                    break
            if died is not None:
                fate = "chosen_died"
            else:
                blocked = any((ft[chosen].get(s) or {}).get("status", "") == "route_blocked"
                              for s in range(r["step"], end))
                if blocked:
                    fate = "chosen_route_blocked"
                elif any(vt[r["victim"]].get(s, "") == "dead" for s in range(r["step"], end)):
                    fate = "victim_died"
                elif any(vt[r["victim"]].get(s, "") == "unreachable"
                         for s in range(r["step"], end)):
                    fate = "victim_unreachable"
                elif end > steps:
                    fate = "still_en_route_at_end"
                else:
                    fate = "reassigned"
        # passed-over candidates whose route stayed open across the window
        alt_open_all, alt_open_last = [], []
        frows = [x for x in fol[i] if r["step"] <= x["step"] < end]
        others = [c["ff"] for c in r["cands"] if c["ff"] != chosen]
        for o in others:
            vals = [x["r"].get(o) for x in frows]
            vals = [v for v in vals if v is not None]
            if vals and all(vals):
                alt_open_all.append(o)
            if vals and vals[-1]:
                alt_open_last.append(o)
        rows.append({"cell": cell, "i": i, "step": r["step"], "victim": r["victim"],
                     "chosen": chosen, "n_cand": r["n_cand"],
                     "margin": r["margin"], "fate": fate,
                     "chosen_reach": r["stock_reach"],
                     "n_follow": len(frows),
                     "alt_open_all": alt_open_all, "alt_open_last": alt_open_last,
                     "others": others})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="none")
    ap.add_argument("--prefix", default="_dr")
    ap.add_argument("--extra", default="",
                    help="comma-separated extension cells, e.g. east_half_111")
    ap.add_argument("--only-extra", action="store_true")
    a = ap.parse_args()
    if a.extra:
        EXTRA.extend([x.strip() for x in a.extra.split(",") if x.strip()])
    if a.only_extra:
        del CELLS13[:]
        del CELLSF[:]
    data = load(a.arm, a.prefix)
    have13 = [c for c in CELLS13 if c in data] + [c for c in EXTRA if c in data]
    havef = [c for c in CELLSF if c in data]
    print("SAMPLE: %d/13 seed-matched cells, %d/10 fresh cells, %d total"
          % (len(have13), len(havef), len(data)))
    missing = [c for c in CELLS13 + CELLSF + EXTRA if c not in data]
    if missing:
        print("MISSING: " + " ".join(missing))
    print()

    disp = []
    for cell in have13 + havef:
        for r in data[cell]["dispatch"]:
            r = dict(r)
            r["cell"] = cell
            disp.append(r)
    noff = []
    for cell in have13 + havef:
        for r in data[cell]["noff"]:
            r = dict(r)
            r["cell"] = cell
            noff.append(r)

    print("=" * 78)
    print("TOTALS")
    print("=" * 78)
    print("  dispatches (action=assign)           %4d" % len(disp))
    print("  no-firefighter-available calls       %4d   (%s)"
          % (len(noff), dict(collections.Counter(x["action"] for x in noff))))
    print("  dispatches per run                   %.1f" % (len(disp) / max(1, len(data))))
    drift = [r for r in disp if not r["stock_in_pool"]]
    print("  chosen unit NOT in replicated pool   %4d   (drift check, want 0)" % len(drift))
    print()

    # ------------------------------------------------------------- 2(a)
    print("=" * 78)
    print("2(a)  DISPATCHED WITH NO BFS ROUTE AT COMMITMENT")
    print("=" * 78)
    bad = [r for r in disp if r["stock_reach"] is False]
    print("  chosen unit had NO route          %4d / %d  (%.1f%%)"
          % (len(bad), len(disp), 100.0 * len(bad) / max(1, len(disp))))
    for r in bad:
        print("    %-20s step %3d  %s -> %s  man=%s  pool=%d"
              % (r["cell"], r["step"], r["stock_ff"], r["victim"],
                 r["stock_man"], r["n_cand"]))
    unk = [r for r in disp if r["stock_reach"] is None]
    if unk:
        print("  reachability unmeasurable         %4d" % len(unk))
    print()

    # ------------------------------------------------------------- 2(b)
    print("=" * 78)
    print("2(b)  DOES THE TIEBREAK DECIDE ANYTHING? - MARGIN DISTRIBUTION")
    print("=" * 78)
    poolsz = collections.Counter(r["n_cand"] for r in disp)
    print("  pool size distribution: " + "  ".join(
        "%d->%d" % (k, poolsz[k]) for k in sorted(poolsz)))
    multi = [r for r in disp if r["n_cand"] >= 2]
    print("  dispatches with a choice to make  %4d / %d  (%.1f%%)"
          % (len(multi), len(disp), 100.0 * len(multi) / max(1, len(disp))))
    if multi:
        mm = collections.Counter(r["margin"] for r in multi)
        print("  top-two Manhattan margin histogram:")
        for k in sorted(mm):
            print("      margin %3d : %3d" % (k, mm[k]))
        for thr in (0, 1, 2, 3, 5, 10):
            n = sum(1 for r in multi if r["margin"] <= thr)
            print("    margin <= %-2d : %3d / %d of multi-candidate  (%.1f%% of all dispatches)"
                  % (thr, n, len(multi), 100.0 * n / max(1, len(disp))))
    print()

    # ------------------------------------------------------------- 2(c)
    print("=" * 78)
    print("2(c)  OF THOSE, HOW OFTEN DO CLOSE CANDIDATES DIFFER IN REACHABILITY")
    print("=" * 78)
    print("  (the population a soft tiebreak would act on)")
    print("  %-12s %8s %10s %14s %12s" % ("margin<=", "n", "any-diff", "diff-in-top2", "would-flip"))
    for thr in (0, 1, 2, 3, 5, 10, 999):
        sel = [r for r in multi if r["margin"] <= thr]
        anydiff = [r for r in sel
                   if len({bool(c["reach"]) for c in r["cands"]}) > 1]
        top2 = [r for r in sel
                if bool(r["cands"][0]["reach"]) != bool(r["cands"][1]["reach"])]
        flip = []
        for r in sel:
            best = sorted(r["cands"],
                          key=lambda c: (c["man"], not bool(c["reach"]), c["ff"]))
            if best and best[0]["ff"] != r["stock_ff"]:
                flip.append(r)
        print("  %-12s %8d %10d %14d %12d"
              % (thr if thr != 999 else "any", len(sel), len(anydiff), len(top2), len(flip)))
    allflip = []
    for r in multi:
        best = sorted(r["cands"], key=lambda c: (c["man"], not bool(c["reach"]), c["ff"]))
        if best and best[0]["ff"] != r["stock_ff"]:
            allflip.append(r)
    print()
    print("  EVERY DISPATCH A SOFT TIEBREAK WOULD FLIP (untruncated):")
    if not allflip:
        print("    (none)")
    for r in allflip:
        print("    %-20s step %3d  victim %s  stock=%s -> soft=%s"
              % (r["cell"], r["step"], r["victim"], r["stock_ff"],
                 sorted(r["cands"], key=lambda c: (c["man"], not bool(c["reach"]), c["ff"]))[0]["ff"]))
        for c in r["cands"]:
            print("        %-12s pos=%-10s man=%3d reach=%s"
                  % (c["ff"], c["pos"], c["man"], c["reach"]))
    print()
    print("  EVERY DISPATCH A HARD FILTER WOULD CHANGE (untruncated):")
    hard = []
    for r in disp:
        keep = [c for c in r["cands"] if c["reach"]]
        if len(keep) == len(r["cands"]):
            continue
        win = sorted(keep, key=lambda c: (c["man"], c["ff"]))[0]["ff"] if keep else None
        if win != r["stock_ff"]:
            hard.append((r, win))
    if not hard:
        print("    (none)")
    for r, win in hard:
        print("    %-20s step %3d  victim %s  stock=%s -> hard=%s  pool=%d reachable=%d"
              % (r["cell"], r["step"], r["victim"], r["stock_ff"],
                 win or "EMPTY POOL", r["n_cand"],
                 sum(1 for c in r["cands"] if c["reach"])))
        for c in r["cands"]:
            print("        %-12s pos=%-10s man=%3d reach=%s"
                  % (c["ff"], c["pos"], c["man"], c["reach"]))
    print()

    # ------------------------------------------- 2(c-bis) detour / path length
    if any("bfs" in c for r in disp for c in r["cands"]):
        print("=" * 78)
        print("2(c-bis)  BFS PATH LENGTH - THE NEAR-CONTINUOUS VERSION OF THE TEST")
        print("=" * 78)
        cand = [c for r in disp for c in r["cands"] if "bfs" in c]
        det = [c for c in cand if c.get("detour") is not None]
        pos = [c for c in det if c["detour"] > 0]
        nopath = [c for c in cand if c.get("bfs") is None]
        print("  candidate evaluations with a path length   %4d" % len(det))
        print("  ... detour (bfs - manhattan) > 0           %4d" % len(pos))
        print("  ... no path at all                         %4d" % len(nopath))
        if pos:
            hist = collections.Counter(c["detour"] for c in pos)
            print("  detour histogram: " + "  ".join("%d->%d" % (k, hist[k]) for k in sorted(hist)))
        multi2 = [r for r in disp if r["n_cand"] >= 2 and "bfs" in r["cands"][0]]
        diff = [r for r in multi2
                if r["cands"][0].get("detour") != r["cands"][1].get("detour")]
        print("  multi-candidate dispatches whose two")
        print("    candidates DIFFER in detour              %4d / %d"
              % (len(diff), len(multi2)))
        # the question that actually matters: does ordering by BFS PATH LENGTH
        # - a strictly stronger test than the binary reach either arm uses -
        # ever pick a different unit than ordering by Manhattan?
        big = 10 ** 6
        flip = []
        for r in multi2:
            man_win = sorted(r["cands"], key=lambda c: (c["man"], c["ff"]))[0]["ff"]
            bfs_win = sorted(r["cands"],
                             key=lambda c: (big if c.get("bfs") is None else c["bfs"],
                                            c["ff"]))[0]["ff"]
            if man_win != bfs_win:
                flip.append(r)
        print("    a BFS-LENGTH-primary sort would pick a")
        print("    DIFFERENT unit                           %4d / %d"
              % (len(flip), len(multi2)))
        for r in diff:
            mark = "ORDERING FLIPS" if r in flip else "ordering unchanged"
            print("    %-20s step %3d victim %-9s %s"
                  % (r["cell"], r["step"], r["victim"], mark))
            for c in r["cands"]:
                print("        %-12s man=%3d bfs=%s detour=%s reach=%s"
                      % (c["ff"], c["man"], c.get("bfs"), c.get("detour"), c["reach"]))
        burn = [r for r in disp if r.get("vpos_burning")]
        print("  dispatches where the victim cell itself burns  %4d" % len(burn))
        print()

    # ------------------------------------------------------------- 2(d)
    print("=" * 78)
    print("2(d)  DOES THE CHOSEN UNIT COMPLETE THE RESCUE?")
    print("=" * 78)
    rows = []
    for cell in have13 + havef:
        rows.extend(dispatch_outcomes(cell, data[cell]))
    fates = collections.Counter(r["fate"] for r in rows)
    for k in sorted(fates, key=lambda k: -fates[k]):
        print("  %-24s %4d" % (k, fates[k]))
    failed = [r for r in rows if r["fate"] != "completed"]
    print()
    print("  chosen unit did NOT complete      %4d / %d  (%.1f%%)"
          % (len(failed), len(rows), 100.0 * len(failed) / max(1, len(rows))))
    withalt = [r for r in failed if r["others"]]
    print("  ... of which had ANY alternative  %4d" % len(withalt))
    stayed = [r for r in withalt if r["alt_open_all"]]
    lastop = [r for r in withalt if r["alt_open_last"]]
    print("  ... alt's route open EVERY step   %4d" % len(stayed))
    print("  ... alt's route open at last obs  %4d" % len(lastop))
    print()
    print("  FAILED DISPATCHES THAT HAD AN ALTERNATIVE (untruncated):")
    for r in withalt:
        print("    %-20s step %3d  victim %-9s chosen=%-11s fate=%-22s margin=%s"
              % (r["cell"], r["step"], r["victim"], r["chosen"], r["fate"], r["margin"]))
        print("        chosen_reach_at_dispatch=%s  alt=%s  alt_open_all=%s alt_open_last=%s follow_steps=%d"
              % (r["chosen_reach"], r["others"], r["alt_open_all"],
                 r["alt_open_last"], r["n_follow"]))
    print()

    # ------------------------------------------------------------- cost
    print("=" * 78)
    print("3.  BFS COST")
    print("=" * 78)
    tot_d = sum(data[c]["bfs"]["dispatch_calls"] for c in data)
    tot_ds = sum(data[c]["bfs"]["dispatch_secs"] for c in data)
    tot_all = sum(data[c]["bfs"]["calls"] for c in data)
    tot_alls = sum(data[c]["bfs"]["secs"] for c in data)
    wall = sum(sum(data[c]["wall"]) for c in data)
    print("  BFS calls at DISPATCH ONLY        %6d in %.4f s  (%.3f ms each)"
          % (tot_d, tot_ds, 1000.0 * tot_ds / max(1, tot_d)))
    print("  BFS calls incl. per-step follow   %6d in %.4f s  (%.3f ms each)"
          % (tot_all, tot_alls, 1000.0 * tot_alls / max(1, tot_all)))
    print("  simulation wall clock             %.1f s over %d runs (%.1f s/run)"
          % (wall, len(data), wall / max(1, len(data))))
    print("  dispatch BFS as a share of wall   %.5f %%" % (100.0 * tot_ds / max(1e-9, wall)))
    print("  BFS per candidate per dispatch    %.1f (mean pool size)"
          % (sum(r["n_cand"] for r in disp) / max(1, len(disp))))
    print()

    # ------------------------------------------------------------- outcomes
    print("=" * 78)
    print("PER-CELL OUTCOMES (arm %s)" % a.arm)
    print("=" * 78)
    for grp, cells in (("13-run seed-matched", have13), ("10 fresh", havef)):
        tr = td = tf = 0
        print("  %s" % grp)
        for c in cells:
            e = ev_of(data[c])
            tr += e["rescued"]; td += e["vdead"]; tf += e["ff"]
            print("    %-20s r%-3d d%-3d ff%-3d" % (c, e["rescued"], e["vdead"], e["ff"]))
        print("    %-20s r%-3d d%-3d ff%-3d" % ("TOTAL", tr, td, tf))
    print()


main()
