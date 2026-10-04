"""bayesprep screen: the item-1 mechanism - Bayes-flee with the fix (bpf) vs without it (bpx), same seeds (CRN).

usage: _bp_item1_mech.py   -> prints, per placement (r, u) and arm: targets issued, mean issued leg length L,
       steps per issued target, drop reasons, searcher-steps steered by the strategy (exec_steps) / in fallback, the
       mean number of distinct cells inside any searcher's detection disc by step 30 / 60 / 120 / 240 (coverage
       speed), split band (edge distance < 4) / non-band. Read-only on outputs/; no model import.
"""
from __future__ import annotations

import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ["%s_%s" % (s, w) for s in "ABCD" for w in "ENSW"]
R = 8
OFF = [(dx, dy) for dx in range(-R, R + 1) for dy in range(-R, R + 1) if dx * dx + dy * dy <= R * R]
CHECK = (30, 60, 120, 240)


def band(x, y):
    return min(x, y, 49 - x, 49 - y) < 4


def coverage(d):
    seen = set()
    out = {}
    for i, rows in enumerate(d["rows_uav"]):
        t = i + 1
        for u in rows:
            if u[3] != "victim_searcher" or u[1] is None:
                continue
            for dx, dy in OFF:
                x, y = u[1] + dx, u[2] + dy
                if 0 <= x < 50 and 0 <= y < 50:
                    seen.add((x, y))
        if t in CHECK:
            out[t] = (sum(1 for c in seen if band(*c)), sum(1 for c in seen if not band(*c)))
    return out


def main():
    for place in ("r", "u"):
        print("-- placement %s" % place)
        for arm in ("bpf", "bpx"):
            tag = "%s%s" % (arm, place)
            issued = legs = 0
            stats = {}
            cov = {t: ([], []) for t in CHECK}
            runs = 0
            for k in KEYS:
                p = os.path.join(HERE, "_sd_%s_%s.json" % (tag, k))
                if not os.path.exists(p):
                    continue
                d = json.load(open(p, encoding="utf-8"))
                runs += 1
                fb = d["fb3"]
                issued += len(fb["issued"])
                legs += sum(int(e[3]) for e in fb["issued"])
                for per in fb["stats"].values():
                    for key, v in per.items():
                        stats[key] = stats.get(key, 0) + int(v)
                for t, (b, nb) in coverage(d).items():
                    cov[t][0].append(b)
                    cov[t][1].append(nb)
            steered = stats.get("exec_steps", 0)
            print("  %s runs %d | issued %d, mean L at issue %.1f | exec_steps (strategy-steered) %d = %.1f per target |"
                  " fallback_steps %d" % (tag, runs, issued, legs / max(issued, 1), steered, steered / max(issued, 1),
                                          stats.get("fallback_steps", 0)))
            print("      drops %s" % {k: v for k, v in sorted(stats.items()) if k.startswith(("drop_", "giveup"))})
            print("      mean cells covered by searchers (band of 736 / non-band of 1764) at step " + "  ".join(
                "%d: %.0f / %.0f" % (t, statistics.mean(cov[t][0]), statistics.mean(cov[t][1])) for t in CHECK if cov[t][0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
