"""fix3a round 2 - read-only: every (O) searcher oscillation episode of an arm classified by the steering that made
its steps (outputs/fix3a_r2_prereg.txt; the report's diagnosis).
  BAND   a FIRE_RETREAT move INTO the edge band (penetration 0 -> >0) followed by one OUT of it - the near-field
         retreat and the no-path band exit taking turns
  FIRE   other FIRE_RETREAT / FIRE_WAIT steps (the route's no-path outcomes)
  ROUTE  route steps (escape_bfs / retarget_to_interior / *_fire_route moves)
  YIELD  hold / hold_escape / yield_step_aside
  PLAN   anything else (the ordinary planner's own step)
usage: _fx3r_osc_mech.py <tag> [<tag> ...]
"""
from __future__ import annotations

import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv, ARGS = sys.argv[:1], sys.argv[1:]
import _fx3r_analyze as A  # noqa: E402


def pen(c, n=50):
    return max(0, 4 - min(c[0], n - 1 - c[0])) + max(0, 4 - min(c[1], n - 1 - c[1]))


def kind(label):
    label = str(label or "")
    if label in A.FIRE_LABELS:
        return "FIRE"
    if label.startswith("hold") or "yield" in label:
        return "YIELD"
    if label.endswith("_fire_route") or "retarget_to_interior" in label or label == "victim_search_escape_bfs":
        return "ROUTE"
    return "PLAN"


def main():
    for tag in ARGS:
        runs = A.load(tag)
        tot = collections.Counter()
        per_ep = []
        for key, d in sorted(runs.items()):
            rows = d["rows_uav"]
            pos, lab = {}, {}
            for t, row in enumerate(rows):
                for u in row:
                    pos[(t + 1, u[0])] = (int(u[1]), int(u[2]))
                    lab[(t + 1, u[0])] = str(u[8] or "")
            for e in A.searcher_osc_episodes(d):
                uid, s0, s1 = e[0], e[1], e[2]
                c = collections.Counter()
                band_in = band_out = 0
                for s in range(s0, s1 + 1):
                    k = kind(lab.get((s, uid)))
                    c[k] += 1
                    a, b = pos.get((s - 1, uid)), pos.get((s, uid))
                    if a and b and a != b and lab.get((s, uid)) == A.RETREAT:
                        if pen(a) == 0 and pen(b) > 0:
                            band_in += 1
                        elif pen(a) > 0 and pen(b) < pen(a):
                            band_out += 1
                top = "BAND" if band_in and band_out and band_in + band_out >= (s1 - s0 + 1) // 2 else \
                    max(c, key=c.get)
                tot[top] += 1
                per_ep.append((key, uid, s0, s1, s1 - s0 + 1, top, dict(c)))
        print("%-8s episodes %d by mechanism %s" % (tag, len(per_ep), dict(tot)))
        for ep in per_ep:
            print("   ", ep)


if __name__ == "__main__":
    main()
