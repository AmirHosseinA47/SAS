import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from fs_env import Env
from fs_rules import move_toward, bfs_first_step, on_boundary
from fs_counterfactual import load, legs
from collections import Counter
def holds(env, leg, rule, horizon=300):
    pos, tgt, h = leg["p0"], leg["exit"], 0
    for k in range(leg["s0"] + 1, leg["s0"] + horizon):
        if pos == tgt or (rule == "F1F5" and on_boundary(pos)):
            return h
        nxt = None
        if rule != "base":
            nxt = bfs_first_step(env, pos, k)
        if nxt is None:
            nxt, _ = move_toward(env, pos, tgt, k)
        elif rule == "F5" and on_boundary(nxt):
            tgt = nxt
        if nxt is None:
            h += 1
            if env.burning(pos, k):
                return h
            nxt = pos
        pos = nxt
    return h
for lf in sys.argv[1:]:
    C = Counter()
    for name in [l.strip() for l in open(os.path.join(HERE, lf), encoding="utf-8") if l.strip()]:
        d = load(name)
        if d is None or "burn_intervals" not in d: continue
        env = Env(d, f_guess=8)
        for leg in legs(d):
            for r in ("base", "F1F5"):
                x = holds(env, leg, r); C[r + "_holds"] += x; C[r + "_legs_with_hold"] += x > 0
    print(lf, dict(C))
