"""Per set: stall counted against the completion cell (not the fixed exit) and
step-back (reversal) totals, for base, F1, F5 (fs_counterfactual.replay) and F1F5."""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fs_env import Env  # noqa: E402
from fs_rules import md  # noqa: E402
from fs_counterfactual import load, legs, replay as orig_replay  # noqa: E402
from drive import replay2  # noqa: E402

for lf in sys.argv[1:]:
    files = [l.strip() for l in open(os.path.join(HERE, lf), encoding="utf-8") if l.strip()]
    C = {r: Counter() for r in ("base", "F1", "F5", "F1F5")}
    for name in files:
        d = load(name)
        if d is None or "burn_intervals" not in d:
            continue
        env = Env(d, f_guess=8)
        for leg in legs(d):
            res = {r: orig_replay(env, leg, r) for r in ("base", "F1", "F5")}
            res["F1F5"] = replay2(env, leg, "F1F5")
            for r, x in res.items():
                if x.get("n") is None:
                    C[r]["none"] += 1
                    continue
                dend = md(leg["p0"], x["end"])
                C[r]["stall_vs_exit"] += x["n"] > leg["dist"] + 5
                C[r]["stall_vs_completion_cell"] += x["n"] > dend + 5
                C[r]["reversals"] += x["rev"]
                C[r]["legs_with_2plus_reversals"] += x["rev"] >= 2
                C[r]["end_not_exit"] += x["end"] != leg["exit"]
    print("==", lf)
    for r, c in C.items():
        print("  %-5s %s" % (r, dict(c)))
