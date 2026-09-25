"""Read-only. f2cEFS east/half/404: is the east pocket (where the held carrier
would walk from (46,8) to the boundary) reachable over non-burning cells from
the only other living unit (ff_unit_0) on steps 120-170?  If not, a held
carrier's victim accrues the geo streak every step (the carrier itself is not a
start: wildfire_model.py:5005) and the isolation escape fires at streak 30."""
import json, os
from collections import deque
BASE = "E:/Projects/SAS/outputs"
fn = "_ffr_f2cEFS_east_half_404.json"
d = json.load(open(os.path.join(BASE, fn)))
bi = d["burn_intervals"]; ffs = d["ff_steps"]; N = 50


def burning_at(k):
    out = set()
    for key, ivs in bi.items():
        x, y = map(int, key.split(","))
        for a, b in ivs:
            if a <= k and (b is None or k < b):
                out.add((x, y)); break
    return out


def reach(starts, burning):
    r = set(); q = deque()
    for s in starts:
        if s not in burning:
            r.add(s); q.append(s)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in r or n in burning or not (0 <= n[0] < N and 0 <= n[1] < N):
                continue
            r.add(n); q.append(n)
    return r

pocket = [(x, y) for x in range(44, 50) for y in range(0, 14)]
for k in range(120, 171):
    i = k - 1
    if i >= len(ffs):
        break
    other = [r for r in ffs[i] if r[0] == "ff_unit_0"][0]
    if other[1] is None or other[5]:
        print(k, "ff_unit_0 not a start", other); continue
    b = burning_at(k)
    rc = reach([tuple(other[1])], b)
    hit = [c for c in pocket if c in rc]
    nb = [c for c in pocket if c not in b]
    print("k=%d ff0=%s status=%s  pocket non-burning %d, reachable from ff0 %d" % (
        k, tuple(other[1]), other[2], len(nb), len(hit)))
