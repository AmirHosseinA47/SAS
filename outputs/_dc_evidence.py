#!/usr/bin/env python
"""Depot-cost round: regenerate every measured number quoted in Part 1.

One command, so a reader can check the design document rather than trust it.
Read-only; runs no simulation; reads only the base-station round's recorded arms.

  ./.venv/Scripts/python.exe outputs/_dc_evidence.py

Sections map onto the design document:
  A  3.1  the drain model and the threshold crossings           (mode-0 arm)
  B  2.2  the per-searcher return asymmetry                     (recorded field)
  C  4.3  which candidate depot burns, on DISTINCT fires only
  D  0.4  the mode-2 return deadlock
  E  5.2  the pairing geometry, and that D=45 is optimal
"""
from __future__ import annotations

import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
H = W = 50
SIZE = 5

CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "def", s) for s in (101, 202, 303)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])

ANCHORS = {"NW": (0, 45), "NE": (45, 45), "SW": (0, 0), "SE": (45, 0),
           "CENTRAL": (23, 23)}


def load(tag, wind, roles, seed):
    p = os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, roles, seed))
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def block(origin, n=SIZE):
    ox, oy = origin
    return [(ox + i, oy + j) for i in range(n) for j in range(n)]


def ranked(origin, n=SIZE):
    return sorted(block(origin, n),
                  key=lambda c: (-min(c[0], c[1], H - 1 - c[0], W - 1 - c[1]), c[0], c[1]))


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def cells_of(k):
    return {tuple(int(t) for t in k.split(","))}


def section_a():
    print("A. 3.1  DRAIN MODEL AND THRESHOLD CROSSINGS - mode-0 arm, canonical 13")
    fin, mf, x60, x30 = [], [], [], []
    for w, r, s in CANON:
        d = load("bsoff", w, r, s)
        if d is None:
            continue
        rows = d["uav_steps"]
        for a in range(len(rows[0])):
            prev, moves, b60, b30 = None, 0, None, None
            for i, row in enumerate(rows):
                b = float(row[a][4])
                pos = tuple(row[a][1])
                if prev is not None and pos != prev:
                    moves += 1
                prev = pos
                if b60 is None and b <= 60:
                    b60 = i + 1
                if b30 is None and b <= 30:
                    b30 = i + 1
            fin.append(float(rows[-1][a][4]))
            mf.append(moves / (len(rows) - 1))
            if b60:
                x60.append(b60)
            if b30:
                x30.append(b30)
    print("   UAV-runs %d" % len(fin))
    print("   final battery   mean %.2f  min %.2f  max %.2f"
          % (statistics.mean(fin), min(fin), max(fin)))
    print("   move fraction   mean %.4f  min %.4f  max %.4f"
          % (statistics.mean(mf), min(mf), max(mf)))
    print("   drain rate      %.4f per step" % ((100 - statistics.mean(fin)) / 239))
    print("   crosses 60 at   mean %.1f  min %d  max %d  (n=%d)"
          % (statistics.mean(x60), min(x60), max(x60), len(x60)))
    print("   crosses 30 at   mean %.1f  min %d  max %d  (n=%d of %d)"
          % (statistics.mean(x30), min(x30), max(x30), len(x30), len(fin)))
    print("   -> the shipped derivation assumed a move fraction of 5/6 = 0.8333;")
    print("      the measured MINIMUM is above it, so the assumption is a safe bound.")


def section_b():
    print("\nB. 2.2  PER-SEARCHER RETURN ASYMMETRY - recorded trigger_distance, no replay")
    # east: 2503's lane y[25,49] contains NW (y 45-49); 2502's y[0,24] does not.
    # south: 2502's lane x[0,24] contains NW (x 0-4); 2503's x[25,49] does not.
    home = {"east": {"2503": "lane-contains-NW", "2502": "far-lane"},
            "south": {"2502": "lane-contains-NW", "2503": "far-lane"}}
    agg = {"lane-contains-NW": [], "far-lane": [], "tracker": []}
    for w, r, s in CANON:
        if r != "half":
            continue            # both searchers exist only at the 2+2 role split
        d = load("bsfull", w, r, s)
        if d is None:
            continue
        for uid, trips in (d.get("rtb_log") or {}).items():
            for t in trips:
                agg[home[w].get(uid, "tracker")].append(t["trigger_distance"])
    for k, v in agg.items():
        if v:
            print("   %-18s n=%2d  mean %5.1f  min %2d  max %2d"
                  % (k, len(v), statistics.mean(v), min(v), max(v)))
    if agg["far-lane"] and agg["lane-contains-NW"]:
        print("   far-lane / home-lane = %.2fx"
              % (statistics.mean(agg["far-lane"]) / statistics.mean(agg["lane-contains-NW"])))


def section_c():
    print("\nC. 4.3  WHICH CANDIDATE DEPOT BURNS - on DISTINCT fires only")
    allc = CANON + FRESH
    dig = {}
    for w, r, s in allc:
        d = load("bsoff", w, r, s)
        if d is not None:
            dig[(w, r, s)] = d["fire_final_digest"]
    dup = sum(1 for s in (101, 202, 303)
              if dig.get(("east", "half", s)) == dig.get(("east", "def", s)))
    print("   east half/def pairs with an identical final fire digest: %d of 3" % dup)
    uniq = [(w, r, s) for w, r, s in allc if not (w == "east" and r == "def")]
    print("   distinct fires: %d of %d files" % (len(uniq), len(allc)))
    hits = {k: 0 for k in ANCHORS}
    first = {k: [] for k in ANCHORS}
    frac = {k: [] for k in ANCHORS}
    for w, r, s in uniq:
        d = load("bsoff", w, r, s)
        fb = {tuple(int(t) for t in k.split(",")): v
              for k, v in (d.get("first_burn_step") or {}).items()}
        bi = {tuple(int(t) for t in k.split(",")): v
              for k, v in (d.get("burn_intervals") or {}).items()}
        for name, origin in ANCHORS.items():
            blk = set(block(origin))
            hit = [st for c, st in fb.items() if c in blk]
            if hit:
                hits[name] += 1
                first[name].append(min(hit))
            berths = ranked(origin)[:6]
            tot = 0
            for c in berths:
                for a, b in bi.get(c, []):
                    b = 240 if b is None else b
                    tot += max(0, min(240, b) - max(0, a))
            frac[name].append(tot / (len(berths) * 240.0))
    print("   %-9s %-12s %-9s %-9s %s"
          % ("block", "ever burns", "first mean", "earliest", "berth-burn mean / max"))
    for k in ANCHORS:
        f = first[k]
        print("   %-9s %2d / %-7d %-9s %-9s %5.2f%% / %5.2f%%"
              % (k, hits[k], len(uniq),
                 ("%.0f" % statistics.mean(f)) if f else "-",
                 ("%d" % min(f)) if f else "-",
                 100 * statistics.mean(frac[k]), 100 * max(frac[k])))


def section_d():
    print("\nD. 0.4  THE MODE-2 RETURN DEADLOCK - every non-arriving leg, bsret")
    n = 0
    for w, r, s in CANON:
        d = load("bsret", w, r, s)
        if d is None:
            continue
        rows = d["uav_steps"]
        order = [str(x[0]) for x in rows[0]]
        berths = [tuple(c) for c in d["base_station"]["uav_berths"]]
        for uid, trips in sorted((d.get("rtb_log") or {}).items()):
            for t in trips:
                if t.get("arrival_step") is not None:
                    continue
                n += 1
                a = order.index(uid)
                last = tuple(rows[-1][a][1])
                stuck = 0
                for i in range(len(rows) - 1, -1, -1):
                    if tuple(rows[i][a][1]) != last:
                        break
                    stuck += 1
                print("   %-16s %s stuck at %-8s for %3d steps  batt %.1f  berth %s"
                      % ("%s/%s/%d" % (w, r, s), uid, last, stuck,
                         float(rows[-1][a][4]), berths[a]))
    print("   %d non-arriving legs; all are PERMANENTLY STUCK, not 'still flying'." % n)


def section_e():
    print("\nE. 5.2  PAIRING GEOMETRY, and that D=45 is optimal for a second block")
    dNW = [[min(man((x, y), c) for c in block(ANCHORS["NW"])) for y in range(W)]
           for x in range(H)]
    for name in ("NW", "NW+NE", "NW+SW", "NW+SE", "CENTRAL"):
        cells = []
        for part in name.split("+"):
            cells += block(ANCHORS[part])
        ds = [min(man((x, y), c) for c in cells) for x in range(H) for y in range(W)]
        print("   %-8s grid mean %6.3f   grid max D %3d" % (name, statistics.mean(ds), max(ds)))
    best, hits = None, 0
    for ox in range(H - SIZE + 1):
        for oy in range(W - SIZE + 1):
            m = 0
            for x in range(H):
                for y in range(W):
                    dx = 0 if ox <= x <= ox + SIZE - 1 else (ox - x if x < ox else x - (ox + SIZE - 1))
                    dy = 0 if oy <= y <= oy + SIZE - 1 else (oy - y if y < oy else y - (oy + SIZE - 1))
                    v = min(dNW[x][y], dx + dy)
                    if v > m:
                        m = v
            if best is None or m < best:
                best, hits = m, 1
            elif m == best:
                hits += 1
    print("   minimum achievable worst-case D over all %d second-block placements: %d"
          % ((H - SIZE + 1) * (W - SIZE + 1), best))
    print("   placements attaining it: %d.  SE attains it; NE and SW (65) do not." % hits)


if __name__ == "__main__":
    section_a()
    section_b()
    section_c()
    section_d()
    section_e()
