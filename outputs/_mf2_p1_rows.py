"""fix2 Part 1: re-verify items 1, 2, 4, 5 at c08456b from recorded probe rows. Read-only.

Input: outputs/_sd_<tag>_*.json written by outputs/_sd_probe.py (default tag mf1P: the 16 fix1
invariant runs, shipped defaults, 4 scenarios x 4 winds, source == c08456b modulo line endings -
outputs/_mf2_p1_provenance.py). Every definition below is stated in the output.

usage: _mf2_p1_rows.py [tag ...]  (default mf1P)
"""
from __future__ import annotations

import collections
import glob
import json
import os
import re
import statistics
import sys

OUT = r"E:\Projects\SAS\outputs"
DET_RE = re.compile(r"^\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at")
SEARCHER = {"victim_searcher", "victim_search"}
TERMINAL = {"rescued", "dead", "unreachable"}


def load(tag):
    runs = []
    for f in sorted(glob.glob(os.path.join(OUT, "_sd_%s_*.json" % tag))):
        if f.endswith(".argv") or ".json." in os.path.basename(f):
            continue
        d = json.load(open(f, encoding="utf-8"))
        st = f[:-5] + ".stdout.txt"
        det = {}
        if os.path.exists(st):
            for line in open(st, encoding="utf-8", errors="replace"):
                m = DET_RE.match(line.strip())
                if m and m.group(3) not in det:
                    det[m.group(3)] = int(m.group(1))
        d["_det"] = det
        d["_name"] = os.path.basename(f)[4:-5]
        runs.append(d)
    return runs


def item1(runs, P):
    modes = collections.Counter()
    why = collections.Counter()
    trig_steps = collections.Counter()
    first_nonnormal = []
    n = 0
    for d in runs:
        fnn = None
        for i, r in enumerate(d["rows_dec"]):
            n += 1
            m = r.get("mode", "?")
            modes[m] += 1
            why[(m, tuple(r.get("why") or ()))] += 1
            if m != "normal" and fnn is None:
                fnn = i + 1
        first_nonnormal.append(fnn)
        for t in d["rows_trig"]:
            for k in t:
                trig_steps[k] += 1
    P("ITEM 1 - FAIL-SAFE MODE AND ALARMS (%d runs, %d steps)" % (len(runs), n))
    P("  first step not 'normal', per run: %s" % first_nonnormal)
    for m, c in modes.most_common():
        P("  mode %-22s %6d steps  %5.1f%%" % (m, c, 100.0 * c / n))
    P("  mode + active reasons (top 14):")
    for (m, w), c in why.most_common(14):
        P("    %5.1f%%  %-20s %s" % (100.0 * c / n, m, ",".join(w)))
    art = {"collision_risk", "extreme_drift", "critical_communication"}
    sf = [(m, w) for (m, w), c in why.items() for _ in range(c) if m == "safety_first"]
    only_art = sum(1 for m, w in sf if set(w) <= art | {"search_mode_required"} and set(w) & art)
    P("  safety_first steps whose reasons are only the three artifact reasons (+/- search): %d of %d" % (only_art, len(sf)))
    ir = [(m, w) for (m, w), c in why.items() for _ in range(c) if m == "information_recovery"]
    P("  information_recovery steps carrying search_mode_required: %d of %d" % (
        sum(1 for m, w in ir if "search_mode_required" in w), len(ir)))
    P("  trigger types: share of steps with >= 1 instance")
    for k, c in sorted(trig_steps.items(), key=lambda kv: -kv[1]):
        P("    %-28s %5.1f%%" % (k, 100.0 * c / n))
    return trig_steps


def item2(runs, P):
    c = collections.Counter()
    for d in runs:
        rows = d["rows_uav"]
        for t in range(1, len(rows)):
            prev = {u[0]: u for u in rows[t - 1]}
            for u in rows[t]:
                uid, x, y, role, bat, rtb, dock, berth, act = u
                p = prev.get(uid)
                if p is None:
                    continue
                if rtb or dock:
                    continue
                moved = (x, y) != (p[1], p[2])
                if act in ("hold", "fire_flank_hold") or act.startswith("hold_escape"):
                    c[(act if not act.startswith("hold_escape") else "hold_escape", moved)] += 1
    P("ITEM 2 - HOLD STEPS THAT MOVE (executor label of the step vs position change; rtb legs excluded)")
    for lab in ("hold", "fire_flank_hold", "hold_escape"):
        mv, st = c[(lab, True)], c[(lab, False)]
        tot = mv + st
        P("  %-16s %5d steps, moved %5d (%.1f%%)" % (lab, tot, mv, 100.0 * mv / tot if tot else 0.0))


def blocks(flags):
    out, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        if not f and start is not None:
            out.append((start + 1, i))
            start = None
    if start is not None:
        out.append((start + 1, len(flags)))
    return out


def item4(runs, P):
    P("ITEM 4 - THE NO-SEARCHER GAP")
    P("  searcher FLYING = role victim_searcher, not rtb_active, not docked. gap step = no searcher flying.")
    P("  outstanding victim = managed status not rescued/dead/unreachable; alive undetected = outstanding and")
    P("  no [Victim Detection] event for it yet (stdout). first-return trigger = first step rtb_active goes 1.")
    tot_gap = tot_gap_und = 0
    runs_block_outstanding = runs_block_undetected = 0
    spreads, trig_all = [], []
    for d in runs:
        rows_u, rows_v, det = d["rows_uav"], d["rows_vic"], d["_det"]
        gap = []
        for t, row in enumerate(rows_u):
            s = [u for u in row if u[3] in SEARCHER]
            gap.append(bool(s) and not any((not u[5]) and (not u[6]) for u in s))
        first_trig = {}
        for t, row in enumerate(rows_u):
            for u in row:
                if u[5] and u[0] not in first_trig:
                    first_trig[u[0]] = t + 1
        ft = sorted(first_trig.values())
        if ft:
            spreads.append(ft[-1] - ft[0])
            trig_all += ft
        bl = blocks(gap)
        g = sum(gap)
        und_steps = 0
        outst_any = False
        und_any = False
        for (a, b) in bl:
            for t in range(a, b + 1):
                vrow = rows_v[t - 1]
                outst = [v for v in vrow if (v[4] or v[3]) not in TERMINAL]
                und = [v for v in outst if det.get(v[0], 10 ** 9) > t]
                if t == a and outst:
                    outst_any = True
                if und:
                    und_steps += 1
                    und_any = True
        tot_gap += g
        tot_gap_und += und_steps
        runs_block_outstanding += int(outst_any)
        runs_block_undetected += int(und_any)
        P("  %-10s gap blocks %-34s gap steps %3d  with alive-undetected victim %3d  first-return triggers %s" % (
            d["_name"], bl[:4], g, und_steps, ft))
    P("  TOTAL gap steps %d; gap steps with an alive undetected victim %d; runs whose gap opens with victims"
      " outstanding %d/%d; runs with an alive undetected victim during a gap %d/%d" % (
          tot_gap, tot_gap_und, runs_block_outstanding, len(runs), runs_block_undetected, len(runs)))
    if spreads:
        P("  first-return spread (last - first UAV) per run: median %s, range %s-%s; trigger steps %s-%s" % (
            statistics.median(spreads), min(spreads), max(spreads), min(trig_all), max(trig_all)))


def item5(runs, P):
    P("ITEM 5 - RETURN LEGS: excess steps (duration - Manhattan distance from trigger cell to berth) and")
    P("  the longest wait one cell outside a depot cell (stationary, rtb_active, not docked)")
    hist = collections.Counter()
    worst = []
    for d in runs:
        rows = d["rows_uav"]
        depot = {tuple(c) for c in ((d.get("depots") or {}).get("cells") or [])}
        legs = {}
        for t, row in enumerate(rows):
            for u in row:
                uid, x, y, role, bat, rtb, dock, berth, act = u
                L = legs.setdefault(uid, [])
                if rtb and not dock:
                    if not L or L[-1].get("done"):
                        L.append({"start": t + 1, "cell": (x, y), "berth": berth, "path": [(x, y)]})
                    else:
                        L[-1]["path"].append((x, y))
                elif dock and L and not L[-1].get("done"):
                    L[-1]["done"] = t + 1
        for uid, L in legs.items():
            for leg in L:
                if not leg.get("done") or leg["berth"] is None:
                    continue
                dist = abs(leg["cell"][0] - leg["berth"][0]) + abs(leg["cell"][1] - leg["berth"][1])
                dur = leg["done"] - leg["start"]
                ex = dur - dist
                hist[ex if ex <= 2 else (5 if ex <= 5 else (10 if ex <= 10 else (20 if ex <= 20 else 99)))] += 1
                run, best, prev = 0, 0, None
                for c in leg["path"]:
                    near = any(abs(c[0] - q[0]) + abs(c[1] - q[1]) == 1 for q in depot) and c not in depot
                    run = run + 1 if (c == prev and near) else 0
                    best = max(best, run)
                    prev = c
                if ex >= 5 or best >= 5:
                    worst.append((d["_name"], uid, leg["start"], dur, dist, ex, best))
    P("  excess histogram (buckets 0,1,2,<=5,<=10,<=20,>20): %s" % sorted(hist.items()))
    for w in sorted(worst, key=lambda r: -r[5]):
        P("    %s uav %s leg from step %d: %d steps for distance %d (excess %d), longest outside-depot wait %d" % w)


def main():
    tags = sys.argv[1:] or ["mf1P"]
    lines = []
    P = lines.append
    for tag in tags:
        runs = load(tag)
        P("=" * 100)
        P("TAG %s: %d runs %s" % (tag, len(runs), [d["_name"] for d in runs]))
        item1(runs, P)
        item2(runs, P)
        item4(runs, P)
        item5(runs, P)
    text = "\n".join(lines)
    print(text)


if __name__ == "__main__":
    main()
