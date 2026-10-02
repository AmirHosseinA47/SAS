"""untune Part 3: read-only diagnosis of the searcher (O) episodes (G-O) - per episode: arm, cell, uid, steps, the
step labels inside it, the last detection, and the two searcher counts (privileged / known) and mission phase
recorded by the ut probe at its start and end. Pairs as in _ut_analyze.py. No simulation is run."""
from __future__ import annotations

import collections
import sys

sys.argv = sys.argv[:1]
import _ut_analyze as U  # noqa: E402

A = U.A


def labels(d, uid, s0, s1):
    c = collections.Counter()
    for t in range(s0, s1 + 1):
        for u in d["rows_uav"][t - 1]:
            if u[0] == uid:
                c[str(u[8] or "")] += 1
    return dict(c.most_common(4))


def main():
    for ref, arm, label in U.PAIRS:
        print("=" * 110)
        print(label)
        summary = collections.Counter()
        for tag in (ref, arm):
            for k, d in sorted(A.load(tag).items()):
                rows, last = U._ut_rows(d), U._last_detection(d)
                for e in A.searcher_o(d)[0]:
                    uid, s0, s1 = e[0], e[1], e[2]
                    r0, r1 = rows.get(s0) or [None] * 8, rows.get(s1) or [None] * 8
                    when = "AFTER" if last is not None and s0 >= last else "before"
                    case = U._case_at(rows, s0)
                    summary[(tag, when)] += 1
                    summary[(tag, when, case)] += 1
                    print("  %-6s %s uid %s %d-%d (%d) last_det %s %s case %s | counts priv/known start %s/%s end %s/%s"
                          " | labels %s" % (tag, k, uid, s0, s1, e[3], last, when, case, r0[1], r0[2], r1[1], r1[2],
                                            labels(d, uid, s0, s1)))
        print("  SUMMARY", dict(sorted(summary.items(), key=str)))


if __name__ == "__main__":
    main()
