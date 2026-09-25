"""Fire + smoke field reconstructed from a recorded _ffr_*.json (read-only).

burning(c, k): recorded post-step burning at step k (burn_intervals, half-open).
smoky(c, k):   exact replay of agents.py Fire.step (89-115) + Smoke.smoke_step (199-220)
               per cell, driven by the recorded burning history; fire ticks at k % 3 == 0
               (FIRE_SPREAD_SPEED 3). Initial fuel F is exact for cells burnt by fuel
               exhaustion (F = number of burning ticks); otherwise F = F_GUESS (clamped to
               > burning ticks). Extinguish / scorched-clear writes from firefight_log set
               fuel 0 at their step.
"""
from collections import defaultdict

N = 50
ORDER = ((1, 0), (-1, 0), (0, 1), (0, -1))


def inb(c):
    return 0 <= c[0] < N and 0 <= c[1] < N


def nbrs(c):
    for ox, oy in ORDER:
        n = (c[0] + ox, c[1] + oy)
        if inb(n):
            yield n


class Env:
    def __init__(self, d, horizon=None, f_guess=8):
        self.horizon = horizon or int(d.get("steps") or 360)
        self.iv = defaultdict(list)
        for key, lst in (d.get("burn_intervals") or {}).items():
            x, y = (int(v) for v in key.split(","))
            for a, b in lst:
                self.iv[(x, y)].append((a, b if b is not None else 10 ** 9))
        writes = {}
        for r in d.get("firefight_log") or []:
            if not r.get("wrote"):
                continue
            act = r.get("action")
            if act == "extinguish" or (act == "clear" and r.get("scorched")):
                if r.get("target"):
                    writes.setdefault(tuple(r["target"]), int(r["step"]))
        ground = d.get("fire_ground_final") or {}
        self.smoke = {}
        self.exact_f = {}
        for cell, iv in self.iv.items():
            key = "%d,%d" % cell
            g = ground.get(key) or [1, 0, 0]
            e = writes.get(cell)
            ticks = sum((min(b, self.horizon) - a) // 3 for a, b in iv)
            if g[1] and e is None:
                F, ex = ticks, True
            else:
                F, ex = max(f_guess, ticks + 1), False
            self.exact_f[cell] = ex
            self.smoke[cell] = self._sim(iv, F, e)

    def _sim(self, iv, F, e):
        def burning_post(k):
            for a, b in iv:
                if a <= k < b:
                    return True
            return False
        lb, counter, smoke = 2, F, False
        fuel, has_burned, burnt = F, False, False
        on = set()

        def smoke_step(b):
            nonlocal lb, counter, smoke
            if not smoke and counter == F:
                if (b and lb == 2) or (0 < lb < 2):
                    lb -= 1
                elif lb == 0:
                    smoke = True
            elif smoke:
                if 0 < counter <= F:
                    counter -= 1
                elif counter == 0:
                    smoke = False
        for k in range(1, self.horizon + 1):
            if burnt:
                smoke_step(False)
            elif k % 3 == 0:
                cur = burning_post(k - 1)
                if cur:
                    has_burned = True
                    if fuel > 0:
                        fuel -= 1
                if has_burned and fuel <= 0:
                    burnt = True
                    cur = False
                smoke_step(cur)
            # FF writes land in the advance phase of step e (after Fire.step of e)
            if e is not None and k == e:
                fuel = 0
                has_burned = True
            if smoke:
                on.add(k)
        return on

    def burning(self, c, k):
        for a, b in self.iv.get(c, ()):
            if a <= k < b:
                return True
        return False

    def smoky(self, c, k):
        return (not self.burning(c, k)) and k in self.smoke.get(c, ())

    def adj(self, c, k):
        return any(self.burning(n, k) for n in nbrs(c))
