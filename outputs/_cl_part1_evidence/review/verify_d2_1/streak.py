"""Reconstruct the carried victim's geo streak (end-of-step state) in recorded runs.

Read-only. Reads named _ffr_*.json files only.
geo_reachable(v, s): victim cell in BFS (4-conn, burning impassable) from the cells of
units that are not dead, status != dead, not exiting, pos not None - at end of step s.
served: assigned unit (assigned, status not dead/route_blocked, bound to v) is in living and
its manhattan distance to v fell since the previous step.
"""
import json
import sys
from collections import deque

W = H = 50


def burning_at(bi, s):
    out = set()
    for key, ivs in bi.items():
        for a, b in ivs:
            if a <= s and (b is None or s < b):
                x, y = key.split(",")
                out.add((int(x), int(y)))
                break
    return out


def bfs(starts, burning):
    r = set()
    q = deque()
    for c in starts:
        if c in burning or c in r:
            continue
        r.add(c)
        q.append(c)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in r or n in burning:
                continue
            if not (0 <= n[0] < W and 0 <= n[1] < H):
                continue
            r.add(n)
            q.append(n)
    return r


def run(path, vid, s0, s1, hold_from=None, hold_carrier=None):
    d = json.load(open(path))
    bi = d["burn_intervals"]
    ffs = d["ff_steps"]
    binds = d["ff_bind_steps"]
    vs = d["victim_steps"]
    streak = 0
    prev = {}
    rows = []
    for s in range(1, len(ffs) + 1):
        i = s - 1
        burning = burning_at(bi, s)
        living = []
        for (fid, pos, status, assigned, exiting, dead) in ffs[i]:
            if dead or status == "dead" or exiting or pos is None:
                continue
            living.append((fid, tuple(pos)))
        reach = bfs([c for _, c in living], burning)
        vrow = {r[0]: r for r in vs[i]}
        v = vrow.get(vid)
        vcell = tuple(v[1]) if v and v[1] is not None else None
        vstat = v[2] if v else ""
        bindmap = {b[0]: b[1] for b in binds[i]}
        assigned_ff = ""
        for (fid, pos, status, assigned, exiting, dead) in ffs[i]:
            if dead or not assigned or status in ("dead", "route_blocked"):
                continue
            if bindmap.get(fid) == vid:
                assigned_ff = fid
                break
        approaching = False
        newd = {}
        if vcell is not None:
            for fid, c in living:
                dist = abs(c[0] - vcell[0]) + abs(c[1] - vcell[1])
                newd[fid] = dist
                if fid != assigned_ff:
                    continue
                p = prev.get(fid)
                if p is not None and dist < p:
                    approaching = True
        prev = newd
        geo = vcell is not None and vcell in reach
        terminal = vstat in ("rescued", "dead", "unreachable", "cancelled")
        if terminal:
            streak = 0
        elif (not approaching) and (not geo):
            streak += 1
        else:
            streak = 0
        if s0 <= s <= s1:
            carrier = [(r[0], r[1], r[2], r[4]) for r in ffs[i]]
            rows.append((s, vcell, vstat, int(geo), int(approaching), streak,
                         len(living), carrier))
    return rows


if __name__ == "__main__":
    path, vid, s0, s1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    for r in run(path, vid, s0, s1):
        print(r)
