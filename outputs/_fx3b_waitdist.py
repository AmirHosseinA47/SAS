"""fix3a follow-up (fx3b) - evidence for the bounded-wait pre-registration, from Part 3 runs ALREADY ON DISK
(no new run). For every latched no-path episode (consecutive steps labelled ..._fire_wait or ..._fire_retreat
by one searcher) in the A1-containing Part 3 arms: its length, and how it ENDED -
  OPENED   the next step is a route call toward the SAME target (the fire moved; waiting paid off)
  RETARGET the next step routes to a different target or does not route (the planner moved on by itself)
  HORIZON  the run ended during the episode
and, for the pre-latch prototypes (fx3pA1, fx3pV - labels only, no latch state), the length distribution.
usage: _fx3b_waitdist.py
"""
from __future__ import annotations

import collections
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WAIT = "victim_search_wind_aware_retarget_to_interior_fire_wait"
RETREAT = "victim_search_wind_aware_retarget_to_interior_fire_retreat"
NOPATH = (WAIT, RETREAT)
ARMS = ("fx3S", "fx3S2", "fx3A1", "fx3B0", "fx3B2", "fx3B3", "fx3B23")
PROTO = ("fx3pA1", "fx3pV")


def runs(tag):
    for f in sorted(glob.glob(os.path.join(HERE, "_sd_%s_*.json" % tag))):
        b = os.path.basename(f)
        if ".json." in b:
            continue
        yield b[len("_sd_%s_" % tag):-5], json.load(open(f, encoding="utf-8"))


def episodes(d):
    rows = d["rows_uav"]
    per = collections.defaultdict(list)          # uid -> [(step, label)]
    for t, row in enumerate(rows):
        for u in row:
            if u[3] == "victim_searcher":
                per[u[0]].append((t + 1, str(u[8] or "")))
    out = []
    for uid, seq in per.items():
        i = 0
        while i < len(seq):
            if seq[i][1] not in NOPATH:
                i += 1
                continue
            j = i
            while j + 1 < len(seq) and seq[j + 1][1] in NOPATH and seq[j + 1][0] == seq[j][0] + 1:
                j += 1
            out.append((uid, seq[i][0], seq[j][0], seq[j + 1] if j + 1 < len(seq) else None,
                        sum(1 for k in range(i, j + 1) if seq[k][1] == WAIT)))
            i = j + 1
    return out


def latched(d, step, uid):
    """The target of the searcher's LAST route call at `step` (the probe's 'R' event: target, label,
    [dir, result label], method), rounded like the latch; None without a route call. (The probe's
    wind-state whitelist does not record fire_route_target itself.)"""
    ev = (d.get("fx3") or {}).get("ev") or {}
    t = None
    for e in (ev.get(str(step)) or {}).get(uid) or []:
        if e[0] == "R" and e[1]:
            t = (int(round(float(e[1][0]))), int(round(float(e[1][1]))))
    return t


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def main():
    ends = collections.Counter()
    lens = collections.defaultdict(list)
    all_lens = []
    for tag in ARMS:
        for key, d in runs(tag):
            for uid, s0, s1, nxt, nwait in episodes(d):
                n = s1 - s0 + 1
                all_lens.append(n)
                t0 = latched(d, s0, uid)
                if nxt is None:
                    kind = "HORIZON"
                else:
                    t1 = latched(d, nxt[0], uid)
                    kind = "OPENED" if (t0 is not None and t1 == t0) else "RETARGET"
                ends[kind] += 1
                lens[kind].append(n)
    print("LATCHED no-path episodes (fire_wait / fire_retreat runs), A1-containing Part 3 arms %s" % (ARMS,))
    print("  episodes %d | length median %d, p75 %d, p90 %d, p95 %d, max %d" % (
        len(all_lens), pct(all_lens, .5), pct(all_lens, .75), pct(all_lens, .9), pct(all_lens, .95),
        max(all_lens or [0])))
    for kind in ("OPENED", "RETARGET", "HORIZON"):
        xs = lens[kind]
        print("  ended %-8s %4d | length median %d, p90 %d, max %d" % (
            kind, len(xs), pct(xs, .5), pct(xs, .9), max(xs or [0])))
    for w in (10, 15, 20, 25, 30, 39, 50):
        cut = [n for n in all_lens if n > w]
        opened_cut = [n for n in lens["OPENED"] if n > w]
        print("  bound W=%2d: episodes cut %3d (%.0f%%), of them would have OPENED %3d; steps saved <= %d" % (
            w, len(cut), 100.0 * len(cut) / max(1, len(all_lens)), len(opened_cut), sum(n - w for n in cut)))
    print()
    print("PRE-LATCH PROTOTYPES (labels only):")
    for tag in PROTO:
        xs = [s1 - s0 + 1 for _k, d in runs(tag) for (_u, s0, s1, _n, _w) in episodes(d)]
        print("  %-7s episodes %d | median %d, p90 %d, max %d" % (tag, len(xs), pct(xs, .5), pct(xs, .9),
                                                                 max(xs or [0])))


if __name__ == "__main__":
    main()
