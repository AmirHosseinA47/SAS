"""Read-only: for each hold-conversion candidate, print the other unit's state
over the carry, escape log, unassigns and the would-be isolation streak.

A carried victim's geo streak runs on a step iff no living (not dead, not
exiting, on-grid) unit can reach the victim's cell over non-burning cells
(wildfire_model.py:4997-5015, 5073; rescue_planner.py:499-502). We rebuild
that per step from ff_steps + burn_intervals + victim_steps.
"""
import json, sys, os
from collections import deque

BASE = "E:/Projects/SAS/outputs"
CASES = [
    ("_ffr_f2cEFS_east_half_404.json", "victim_0", "ff_unit_1", 104, 133),
    ("_ffr_fmDRY_east_half_101.json", "victim_0", "ff_unit_0", 100, 135),
    ("_ffr_uhD_east_half_1291443119.json", "victim_0", "ff_unit_1", 84, 148),
    ("_ffr_uhY_east_half_1291443119.json", "victim_0", "ff_unit_1", 84, 148),
]
N = 50


def burning_at(bi, k):
    out = set()
    for key, ivs in bi.items():
        x, y = map(int, key.split(","))
        for a, b in ivs:
            if a <= k and (b is None or k < b):
                out.add((x, y))
                break
    return out


def reach(starts, burning):
    r = set()
    q = deque()
    for s in starts:
        if s in burning:
            continue
        r.add(s); q.append(s)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in r or n in burning:
                continue
            if not (0 <= n[0] < N and 0 <= n[1] < N):
                continue
            r.add(n); q.append(n)
    return r


for fn, vid, ffid, s0, s1 in CASES:
    assert "_firemech_rewound" not in fn and "/" not in fn
    p = os.path.join(BASE, fn)
    d = json.load(open(p))
    print("=" * 70)
    print(fn, "steps", d.get("steps"), "extra", d.get("extra_params"))
    ffs = d["ff_steps"]
    vs = d["victim_steps"]
    bi = d["burn_intervals"]
    streak = 0
    for k in range(s0 - 2, min(s1 + 6, len(ffs) + 1)):
        # row index i = state after step i+1  => step k state is ffs[k-1]
        i = k - 1
        if i < 0 or i >= len(ffs):
            continue
        rows = ffs[i]
        vrow = {r[0]: r for r in vs[i]}
        v = vrow.get(vid)
        vcell = tuple(v[1]) if v and v[1] else None
        burning = burning_at(bi, k)
        starts = []
        desc = []
        for r in rows:
            uid, pos, st, asg, ex, dead = r
            desc.append("%s:%s/%s/a%d/e%d/d%d" % (uid[-1], tuple(pos) if pos else None, st, asg, ex, dead))
            if dead or st == "dead" or ex or pos is None:
                continue
            starts.append(tuple(pos))
        rc = reach(starts, burning)
        georeach = vcell is not None and vcell in rc
        # 'served' needs the assigned unit in living; a carrier is never in living
        if not georeach:
            streak += 1
        else:
            streak = 0
        print(" k=%3d v=%s %s  geo=%d streak~%d  %s" % (k, vcell, v[2] if v else None, georeach, streak, "  ".join(desc)))
    print(" escape log:", [e for e in d.get("unreachable_escape_log", []) if s0 - 5 <= e["step"] <= s1 + 40])
    print(" unassigns:", [u for u in d.get("unassigns", []) if s0 - 5 <= u["step"] <= s1 + 40])
    print(" exit_starts:", [e for e in d.get("exit_starts", []) if s0 - 5 <= e["step"] <= s1 + 5])
