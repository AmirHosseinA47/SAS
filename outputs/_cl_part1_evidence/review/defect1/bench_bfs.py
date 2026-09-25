"""Micro-benchmark of a 50x50 clean-cell BFS using mesa 1.2.1 MultiGrid reads (no SAS model)."""
import time, sys
from collections import deque
import mesa
print(sys.version.split()[0], mesa.__version__)
class M(mesa.Model):
    pass
class Sm:
    def __init__(s, on): s.on = on
    def is_smoke_active(s): return s.on
class F(mesa.Agent):
    def __init__(s, uid, m, b):
        super().__init__(uid, m); s.burning = b; s.smoke = Sm(False)
    def is_burning(s): return s.burning
m = M(); g = mesa.space.MultiGrid(50, 50, False)
uid = 0
for x in range(50):
    for y in range(50):
        # worst case: a burning ring 2 cells in from the edge -> no clean goal, BFS floods the interior
        b = (x in (2, 47) and 2 <= y <= 47) or (y in (2, 47) and 2 <= x <= 47)
        g.place_agent(F(uid, m, b), (x, y)); uid += 1
OFF = ((1, 0), (-1, 0), (0, 1), (0, -1))
def burning(c):
    if g.out_of_bounds(c): return False
    for a in g.get_cell_list_contents([c]):
        if type(a) is F and a.is_burning(): return True
    return False
def smoky(c):
    if g.out_of_bounds(c): return False
    for a in g.get_cell_list_contents([c]):
        if type(a) is F and a.smoke.is_smoke_active(): return True
    return False
def bfs(start):
    memo = {}
    def fb(c):
        v = memo.get(c)
        if v is None: v = memo[c] = burning(c)
        return v
    def passable(c):
        if fb(c): return False
        if any(fb((c[0]+ox, c[1]+oy)) for ox, oy in OFF): return False
        return not smoky(c)
    def isb(c): return any(g.out_of_bounds((c[0]+ox, c[1]+oy)) for ox, oy in OFF)
    prev = {start: None}; q = deque([start]); n_tested = 0
    while q:
        c = q.popleft()
        for ox, oy in OFF:
            n = (c[0]+ox, c[1]+oy)
            if g.out_of_bounds(n) or n in prev: continue
            n_tested += 1
            if not passable(n): continue
            prev[n] = c
            if isb(n):
                while prev[n] != start: n = prev[n]
                return n, n_tested
            q.append(n)
    return None, n_tested
for trial in range(3):
    t = time.perf_counter(); r = bfs((25, 25)); dt = time.perf_counter() - t
    print("enclosed-interior BFS", r, "%.1f ms" % (dt * 1000))
