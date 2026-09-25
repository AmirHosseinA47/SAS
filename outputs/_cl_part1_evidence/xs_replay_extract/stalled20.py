"""Which legs stay 'stalled' (n > dist+5) under the replayed F5, and why."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fs_env import Env  # noqa: E402
from fs_rules import bfs_first_step, on_boundary, md  # noqa: E402
from fs_counterfactual import load, legs, replay as orig_replay  # noqa: E402
from drive import replay2  # noqa: E402

files = [l.strip() for l in open(os.path.join(HERE, "list_census.txt"), encoding="utf-8") if l.strip()]
rows = []
for name in files:
    d = load(name)
    if d is None or "burn_intervals" not in d:
        continue
    env = Env(d, f_guess=8)
    for leg in legs(d):
        f5 = replay2(env, leg, "F5")
        n = f5.get("n")
        if n is None or n <= leg["dist"] + 5:
            continue
        b = orig_replay(env, leg, "base")["n"]
        # distance from pickup to the boundary cell F5 actually completed on
        dend = md(leg["p0"], f5["end"])
        rows.append((name, leg["victim"], leg["s0"], leg["s1"] - leg["s0"], b, n, leg["dist"], dend, f5["fb"], f5["rev"], f5["adj"], f5["smoke"]))
print("F5-stalled legs:", len(rows))
print("name victim s0 rec base F5 dist_exit dist_to_F5_end fallback_steps reversals adj smoke")
for r in rows:
    print(" ", *r)
print("with any fallback step:", sum(1 for r in rows if r[8] > 0))
print("with any reversal:", sum(1 for r in rows if r[9] > 0))
print("stalled vs completion cell (n > dist_end+5):", sum(1 for r in rows if r[5] > r[7] + 5))
print("n - dist_exit:", sorted(r[5] - r[6] for r in rows))
