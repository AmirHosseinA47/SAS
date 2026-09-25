"""Is a set of cells reachable (burning-only BFS) from the OTHER unit's recorded cell?

Read-only. Usage: region.py file other_ff s0 s1 x0 x1 y0 y1
Prints per step: other unit cell, count of region cells reachable / non-burning.
"""
import json
import sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from streak import burning_at, bfs  # noqa: E402

path, other = sys.argv[1], sys.argv[2]
s0, s1, x0, x1, y0, y1 = map(int, sys.argv[3:9])
d = json.load(open(path))
bi = d["burn_intervals"]
for s in range(s0, s1 + 1):
    row = {r[0]: r for r in d["ff_steps"][s - 1]}
    o = row[other]
    burning = burning_at(bi, s)
    starts = []
    if not (o[5] or o[2] == "dead" or o[4] or o[1] is None):
        starts.append(tuple(o[1]))
    reach = bfs(starts, burning)
    cells = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    nb = [c for c in cells if c not in burning]
    rc = [c for c in nb if c in reach]
    print(s, o[1], o[2], "region nonburning", len(nb), "reachable", len(rc),
          sorted(rc)[:6])
