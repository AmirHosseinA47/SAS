"""Verify D1-02: does rebinding fs_rules.bfs_first_step after importing fs_counterfactual
reach replay()? And do mutant kernels change the F5 census row (canary sensitivity)?
Reads recorded JSON only (explicit names from list_census.txt); no simulation."""
import os
import sys
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

mode = sys.argv[1]

calls = Counter()

if mode == "pre":
    import fs_rules
    orig = fs_rules.bfs_first_step

    def adapter(env, pos, k, strict=True):
        calls["adapter"] += 1
        return orig(env, pos, k, strict)
    fs_rules.bfs_first_step = adapter
    import fs_counterfactual as fc
else:
    import fs_counterfactual as fc
    import fs_rules
    orig = fs_rules.bfs_first_step

    def adapter(env, pos, k, strict=True):
        calls["adapter"] += 1
        return orig(env, pos, k, strict)
    fs_rules.bfs_first_step = adapter

from fs_env import Env, nbrs, inb, ORDER  # noqa: E402
from fs_rules import on_boundary  # noqa: E402


def mut_goal_first(env, pos, k, strict=True):
    """Mutant: goal test BEFORE the clean filter (a smoky/adjacent boundary is a goal)."""
    prev = {pos: None}
    q = deque([pos])
    while q:
        c = q.popleft()
        for n in nbrs(c):
            if n in prev or env.burning(n, k):
                continue
            if on_boundary(n):
                prev[n] = c
                while prev[n] != pos:
                    n = prev[n]
                return n
            if strict and (env.adj(n, k) or env.smoky(n, k)):
                continue
            prev[n] = c
            q.append(n)
    return None


def mut_reverse(env, pos, k, strict=True):
    """Mutant: reversed neighbour order."""
    prev = {pos: None}
    q = deque([pos])
    while q:
        c = q.popleft()
        ns = [(c[0] + ox, c[1] + oy) for ox, oy in reversed(ORDER)]
        for n in ns:
            if not inb(n):
                continue
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


def row(listfile, kern=None):
    if kern is not None:
        fc.bfs_first_step = kern
    C = Counter()
    per_leg = []
    for name in [l.strip() for l in open(os.path.join(HERE, listfile), encoding="utf-8") if l.strip()]:
        d = fc.load(name)
        if d is None or "burn_intervals" not in d:
            continue
        env = Env(d, f_guess=8)
        for leg in fc.legs(d):
            b = fc.replay(env, leg, "base")["n"]
            r = fc.replay(env, leg, "F5")
            n = r.get("n")
            C["legs"] += 1
            if n is None:
                C["dead" if "dead" in r else "timeout"] += 1
                per_leg.append(None)
                continue
            per_leg.append((n, r["end"]))
            C["steps"] += n
            C["stalled"] += n > leg["dist"] + 5
            C["adj"] += r["adj"]
            C["smoke"] += r["smoke"]
            C["shorter"] += (b is not None and n < b)
            C["longer"] += (b is not None and n > b)
    return dict(C), per_leg


if mode in ("pre", "post"):
    import fs_counterfactual
    print("mode", mode, "fc.bfs_first_step is adapter:", fs_counterfactual.bfs_first_step is adapter)
    C, _ = row(sys.argv[2])
    print("row", C)
    print("adapter calls", calls["adapter"])
elif mode == "mutants":
    fc_orig = fc.bfs_first_step
    base, bl = row(sys.argv[2], fc_orig)
    print("orig   ", base)
    for nm, kern in (("goal1st", mut_goal_first), ("reverse", mut_reverse)):
        C, pl = row(sys.argv[2], kern)
        diff = sum(1 for a, b in zip(bl, pl) if a != b)
        diffn = sum(1 for a, b in zip(bl, pl) if (a and a[0]) != (b and b[0]))
        print(nm, C, "legs with different (n,end):", diff, "different n:", diffn)
