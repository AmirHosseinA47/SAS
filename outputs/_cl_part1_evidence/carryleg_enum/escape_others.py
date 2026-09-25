"""Read-only: for each distinct isolation-escape-on-carrier case, the OTHER victims marked in
the same step: their prior status, and whether they were reachable (4-connected, burning
cells impassable, as _safe_path_reachable_cells) from the CARRIER's cell at that step,
using the recorded burn_intervals. Both interval-end conventions are tried."""
import json
import os
from collections import deque

OUT = r"E:\Projects\SAS\outputs"
FILES = [
    "_ffr_d4off_east_half_1323590814.json",
    "_ffr_dfpB_west_half_505.json",
    "_ffr_dfpCB_west_half_303.json",
    "_ffr_dimA_east_def_101.json",
    "_ffr_dimB_east_def_101.json",
    "_ffr_dimfreshbase_east_half_1010.json",
    "_ffr_dimfreshbase_east_half_606.json",
    "_ffr_f2b404s12_south_half_404.json",
    "_ffr_f2cDRY_east_def_101.json",
]


def burning_at(bi, t, inclusive_end):
    cells = set()
    for key, ivs in bi.items():
        x, y = (int(v) for v in key.split(","))
        for a, b in ivs:
            if a <= t and (t <= b if inclusive_end else t < b):
                cells.add((x, y))
                break
    return cells


def reach(start, burning, W=50, H=50):
    if start in burning:
        return set()
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if not (0 <= n[0] < H and 0 <= n[1] < W) or n in seen or n in burning:
                continue
            seen.add(n)
            q.append(n)
    return seen


for n in FILES:
    with open(os.path.join(OUT, n), encoding="utf-8") as fh:
        d = json.load(fh)
    ffs, vs, bi = d["ff_steps"], d["victim_steps"], d["burn_intervals"]
    esc = [u for u in d["unassigns"] if "isolat" in str(u["reason"])][0]
    s = int(esc["step"])
    ff = esc["ff"]
    carrier_cell = tuple({r[0]: r for r in ffs[s - 2]}[ff][1])
    marked = [e["victim_id"] for e in d["unreachable_escape_log"] if int(e["step"]) == s]
    prior = {v[0]: (v[1], v[2]) for v in vs[s - 2]}
    out = []
    for incl in (False, True):
        b = burning_at(bi, s, incl)
        r = reach(carrier_cell, b)
        out.append({vid: (tuple(prior[vid][0]) in r if prior[vid][0] else None) for vid in marked})
    print(n, "step", s, "carrier", ff, "at", carrier_cell)
    for vid in marked:
        print(f"   {vid}: prior {prior[vid]}  reachable from carrier cell: end-exclusive={out[0][vid]} end-inclusive={out[1][vid]}"
              f"  final={[v for v in vs[-1] if v[0] == vid][0][2]}")
