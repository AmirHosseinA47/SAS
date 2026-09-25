"""The current carrying-leg rule (agents.py _move_toward 2369-2464, exiting branch) and
candidate variants, over an fs_env.Env. Pure functions; nothing here touches the repo."""
from fs_env import nbrs, inb, ORDER


def md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def on_boundary(c):
    return any(not inb((c[0] + ox, c[1] + oy)) for ox, oy in ORDER)


def _score(env, pos, tgt, k):
    tx, ty = tgt
    cx, cy = pos
    dx, dy = tx - cx, ty - cy
    if abs(dx) >= abs(dy):
        pref = (cx + (1 if dx > 0 else -1 if dx < 0 else 0), cy)
    else:
        pref = (cx, cy + (1 if dy > 0 else -1 if dy < 0 else 0))
    db = md(pos, tgt)
    scored = []
    for c in nbrs(pos):
        if env.burning(c, k):
            continue
        da = md(c, tgt)
        a = env.adj(c, k)
        s = env.smoky(c, k)
        scored.append(dict(cell=c, da=da, imp=da < db, mnt=da == db, adj=a, smoke=s,
                           pref=c == pref, risk=100 * a + 10 * s))
    return scored, pref, db


def _pick(pool):
    return min(pool, key=lambda it: (it["da"], 0 if it["pref"] else 1))


def move_toward(env, pos, tgt, k, rule="base", last=None):
    """(chosen cell or None if nowhere to step, tier)."""
    scored, pref, db = _score(env, pos, tgt, k)
    if not scored:
        return None, 0
    if rule == "F4" and db == 1:
        imp = [it for it in scored if it["imp"]]
        if imp:
            return imp[0]["cell"], 5
    clean = [it for it in scored if not it["adj"] and not it["smoke"]]
    pools = [
        [it for it in clean if it["imp"]],
        [it for it in clean if it["mnt"]],
        list(clean),
    ]
    if rule == "F4b":
        # carrying: an improving non-burning cell (adjacent/smoky) beats a worsening clean one
        pools = [pools[0], pools[1], [it for it in scored if it["imp"]], pools[2]]
    if rule == "F4s":
        # carrying: an improving SMOKY-but-not-fire-adjacent cell beats a worsening clean one
        pools = [pools[0], pools[1], [it for it in scored if it["imp"] and not it["adj"]], pools[2]]
    for ti, pool in enumerate(pools, start=1):
        if rule == "F3" and last is not None:
            others = [it for it in pool if it["cell"] != last]
            pool = others
        if rule == "F3t" and last is not None and ti == len(pools):
            others = [it for it in pool if it["cell"] != last]
            if others:
                pool = others
        if rule == "F6" and ti == len(pools) and pool:
            cx, cy = pos
            rev = (2 * cx - pref[0], 2 * cy - pref[1])
            best = min(pool, key=lambda it: (it["da"], 1 if it["cell"] == rev else 0))
            return best["cell"], ti
        if pool:
            return _pick(pool)["cell"], min(ti, 3) if rule not in ("F4b", "F4s") else ti
    rest = scored
    if rule == "F3" and last is not None:
        rest = [it for it in scored if it["cell"] != last] or scored
    best = min(rest, key=lambda it: (it["risk"], it["da"], 0 if it["pref"] else 1))
    return best["cell"], 4


def bfs_first_step(env, pos, k, strict=True):
    """F5: first step of a shortest path to ANY boundary cell over non-burning cells
    that are (strict) not fire-adjacent and not smoky. Neighbour order = ORDER."""
    from collections import deque
    prev = {pos: None}
    q = deque([pos])
    while q:
        c = q.popleft()
        for n in nbrs(c):
            if n in prev or env.burning(n, k):
                continue
            if strict and (env.adj(n, k) or env.smoky(n, k)):
                continue
            prev[n] = c
            if on_boundary(n):
                while prev[n] != pos:
                    n = prev[n]
                return n
            q.append(n)
    return None
