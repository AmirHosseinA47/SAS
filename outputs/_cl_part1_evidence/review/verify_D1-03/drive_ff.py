"""Verifier driver for finding D1-03: does a fire-free (burning-only) path exist when the
clean BFS falls back, and what would 'clean first, else fire-free' do?  Read-only on the
repo: opens explicit outputs/_ffr_*.json names via fs_counterfactual.load."""
import os
import sys
import heapq
from collections import Counter, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fs_env import Env, nbrs  # noqa: E402
from fs_rules import move_toward, bfs_first_step, on_boundary, md  # noqa: E402
from fs_counterfactual import load, legs  # noqa: E402


def least_exposure_first_step(env, pos, k):
    """Dijkstra over non-burning cells, cost = (hazard cells entered, length); goal = any
    boundary cell (goal itself may be adjacent/smoky; it is non-burning)."""
    start = pos
    best = {start: (0, 0)}
    prev = {start: None}
    heap = [(0, 0, 0, start)]
    cnt = 0
    while heap:
        h, L, _, c = heapq.heappop(heap)
        if best.get(c) != (h, L):
            continue
        if c != start and on_boundary(c):
            n = c
            while prev[n] != start:
                n = prev[n]
            return n
        for n in nbrs(c):
            if env.burning(n, k):
                continue
            hz = 1 if (env.adj(n, k) or env.smoky(n, k)) else 0
            key = (h + hz, L + 1)
            if n not in best or key < best[n]:
                best[n] = key
                prev[n] = c
                cnt += 1
                heapq.heappush(heap, (key[0], key[1], cnt, n))
    return None


def replay(env, leg, rule, horizon=300, stats=None):
    pos, tgt = leg["p0"], leg["exit"]
    hist = [pos]
    adj_steps = smoke_steps = rev = fb = 0
    for k in range(leg["s0"] + 1, leg["s0"] + horizon):
        if rule != "base" and on_boundary(pos):
            return dict(n=k - leg["s0"], adj=adj_steps, smoke=smoke_steps, rev=rev, end=pos, fb=fb)
        if pos == tgt:
            return dict(n=k - leg["s0"], adj=adj_steps, smoke=smoke_steps, rev=rev, end=pos, fb=fb)
        if rule == "base":
            nxt, _t = move_toward(env, pos, tgt, k)
        elif rule == "F5":
            nxt = bfs_first_step(env, pos, k)
            if nxt is None:
                fb += 1
                if stats is not None:
                    stats["fb_adv"] += 1
                    stats["fb_adv_ff_path"] += bfs_first_step(env, pos, k, strict=False) is not None
                nxt, _t = move_toward(env, pos, tgt, k)
        elif rule == "F5ns":  # literal 'fire-free' reading: burning-only BFS
            nxt = bfs_first_step(env, pos, k, strict=False)
            if nxt is None:
                fb += 1
                nxt, _t = move_toward(env, pos, tgt, k)
        elif rule == "F5L":  # clean first, else burning-only BFS
            nxt = bfs_first_step(env, pos, k)
            if nxt is None:
                nxt = bfs_first_step(env, pos, k, strict=False)
                if nxt is None:
                    fb += 1
                    nxt, _t = move_toward(env, pos, tgt, k)
        elif rule == "F5E":  # clean first, else least-exposure non-burning path
            nxt = bfs_first_step(env, pos, k)
            if nxt is None:
                nxt = least_exposure_first_step(env, pos, k)
                if nxt is None:
                    fb += 1
                    nxt, _t = move_toward(env, pos, tgt, k)
        if nxt is None:
            if env.burning(pos, k):
                return dict(n=None, dead=k)
            nxt = pos
        if len(hist) >= 2 and nxt == hist[-2] and nxt != pos:
            rev += 1
        pos = nxt
        hist.append(pos)
        adj_steps += env.adj(pos, k)
        smoke_steps += env.smoky(pos, k)
    return dict(n=None, timeout=True)


RULES = ["base", "F5", "F5ns", "F5L", "F5E"]

if __name__ == "__main__":
    fg = int(os.environ.get("F_GUESS", "8"))
    files = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    C = {r: Counter() for r in RULES}
    stats = Counter()
    detail = []
    for name in files:
        d = load(name)
        if d is None or "burn_intervals" not in d:
            continue
        env = Env(d, f_guess=fg)
        for leg in legs(d):
            res = {r: replay(env, leg, r, stats=(stats if r == "F5" else None)) for r in RULES}
            b = res["base"]["n"]
            for r in RULES:
                x = res[r]
                c = C[r]
                c["legs"] += 1
                if x.get("n") is None:
                    c["dead" if "dead" in x else "timeout"] += 1
                    continue
                c["steps"] += x["n"]
                c["stalled_fixed"] += x["n"] > leg["dist"] + 5
                c["stalled_reached"] += x["n"] > md(leg["p0"], x["end"]) + 5
                c["adj"] += x["adj"]
                c["smoke"] += x["smoke"]
                c["rev"] += x["rev"]
                c["fb_adv"] += x.get("fb", 0)
                c["fb_legs"] += x.get("fb", 0) > 0
                if b is not None:
                    c["shorter"] += x["n"] < b
                    c["longer"] += x["n"] > b
            if any((res[r].get("fb", 0) or 0) > 0 for r in RULES if r != "base") or \
               len({res[r].get("n") for r in ("F5", "F5ns", "F5L", "F5E")}) > 1:
                detail.append((name, leg["victim"], leg["s0"], leg["dist"],
                               {r: (res[r].get("n"), res[r].get("fb"), res[r].get("rev"), res[r].get("adj"),
                                    res[r].get("smoke"), res[r].get("dead")) for r in RULES}))
    print("F_GUESS", fg, "list", sys.argv[1])
    print("F5 fallback advances:", stats["fb_adv"], " of which a burning-only path existed:", stats["fb_adv_ff_path"])
    for r in RULES:
        print(r, dict(C[r]))
    if "-v" in sys.argv:
        for row in detail:
            print(" ", row)
