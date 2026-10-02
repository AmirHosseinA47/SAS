"""untune Part 3: read-only. Per cell, the first step at which the two arms' UAV rows differ (any UAV; and searchers
only), against the shipped arm's last detection; and the G-O episodes pooled before / after the last detection."""
from __future__ import annotations

import collections
import sys

sys.argv = sys.argv[:1]
import _ut_analyze as U  # noqa: E402

A = U.A


def first_diff(a, b, searchers_only):
    for t, (ra, rb) in enumerate(zip(a["rows_uav"], b["rows_uav"])):
        if searchers_only:
            ra = [u for u in ra if u[3] == "victim_searcher"]
            rb = [u for u in rb if u[3] == "victim_searcher"]
        if [u[:3] for u in ra] != [u[:3] for u in rb]:
            return t + 1
    return None


def main():
    pooled = collections.Counter()
    for ref, arm, label in U.PAIRS:
        rr, ra = A.load(ref), A.load(arm)
        rel = collections.Counter()
        lines = []
        for k in sorted(set(rr) & set(ra)):
            fd = first_diff(rr[k], ra[k], True)
            last = U._last_detection(rr[k])
            dets = sorted(t for t in A.det_times(rr[k]).values() if t is not None)
            pend = sum(1 for t in dets if fd is not None and t > fd)
            where = ("never" if fd is None else "after last det" if last is not None and fd >= last
                     else "before last det")
            rel[where] += 1
            lines.append("%s first searcher divergence %s, last detection %s, detections after divergence %d -> %s" % (
                k, fd, last, pend, where))
        print("=" * 100)
        print(label, dict(rel))
        for ln in lines:
            print("   ", ln)
        for tag, runs in ((ref, rr), (arm, ra)):
            for k, d in runs.items():
                last = U._last_detection(d)
                for e in A.searcher_o(d)[0]:
                    when = "AFTER" if last is not None and e[1] >= last else "before"
                    pooled[(tag[:3], when)] += 1
    print("=" * 100)
    print("G-O broad episodes pooled over the four sets (ut0 = shipped, ut1 = untuned):", dict(sorted(pooled.items())))


if __name__ == "__main__":
    main()
