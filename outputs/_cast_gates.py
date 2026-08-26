"""Compute CAST gate items 1-4 from a lane_matrix JSON directory.

Convention re-derived from and validated against the Q2.2 table of
cast_part1.txt (outputs/lane_matrix -> 0.8399 / 0.7250 / 0.7824):
  per-searcher value = mean over the 5 seeds
  combo mean         = mean of the two per-searcher values
  ALL                = mean of the two column means
Gate 4 counts lane-seed observations with lane_final[uav].obs_frac > 0.90
out of 8 combos x 5 seeds x 2 lanes = 80.

    usage: _cast_gates.py <dir> [<baseline_dir>]
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

ORDER = [("C", w) for w in ("east", "west", "north", "south")] + \
        [("D", w) for w in ("east", "west", "north", "south")]


def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def load(base):
    files = {}
    for p in glob.glob(os.path.join(base, "*.json")):
        tag = os.path.splitext(os.path.basename(p))[0]
        with open(p, encoding="utf-8") as fh:
            files[tag] = json.load(fh)
    return files


def combo_stats(rows):
    uids = sorted(rows[0]["lane_final"].keys())
    per_uav = [mean([r["lane_compliance"][u] for r in rows]) for u in uids]
    return uids, per_uav, mean(per_uav)


def summarize(base):
    files = load(base)
    per_combo, col0, col1, cov_hits, cov_tot, missing = {}, [], [], 0, 0, []
    for sc, w in ORDER:
        tag = "%s_%s" % (sc, w)
        rows = files.get(tag)
        if not rows:
            missing.append(tag)
            continue
        uids, per_uav, cmean = combo_stats(rows)
        per_combo[tag] = (uids, per_uav, cmean, len(rows))
        col0.append(per_uav[0])
        col1.append(per_uav[1])
        for r in rows:
            for u in uids:
                cov_tot += 1
                if r["lane_final"][u]["obs_frac"] > 0.90:
                    cov_hits += 1
    overall = mean([mean(col0), mean(col1)]) if col0 else float("nan")
    return per_combo, mean(col0) if col0 else float("nan"), \
        mean(col1) if col1 else float("nan"), overall, cov_hits, cov_tot, missing


base = sys.argv[1]
cur = summarize(base)
ref = summarize(sys.argv[2]) if len(sys.argv) > 2 else None

print("MATRIX: %s" % base)
if ref:
    print("BASELINE: %s" % sys.argv[2])
print("")
if ref:
    print("  combo      lane0    lane1    combo-mean   | baseline    delta")
else:
    print("  combo      lane0    lane1    combo-mean   seeds")
print("  " + "-" * 68)
for sc, w in ORDER:
    tag = "%s_%s" % (sc, w)
    if tag not in cur[0]:
        print("  %-10s <MISSING>" % tag)
        continue
    uids, per_uav, cmean, nseeds = cur[0][tag]
    if ref and tag in ref[0]:
        bmean = ref[0][tag][2]
        d = cmean - bmean
        print("  %-10s %s=%.4f %s=%.4f  %.4f      | %.4f     %+.4f%s"
              % (tag, uids[0], per_uav[0], uids[1], per_uav[1], cmean, bmean, d,
                 "  REGRESSION" if d < -0.0001 else ""))
    else:
        print("  %-10s %s=%.4f %s=%.4f  %.4f      %d"
              % (tag, uids[0], per_uav[0], uids[1], per_uav[1], cmean, nseeds))
print("  " + "-" * 68)
if ref:
    print("  %-10s %-8.4f %-8.4f %.4f      | %.4f     %+.4f"
          % ("ALL", cur[1], cur[2], cur[3], ref[3], cur[3] - ref[3]))
else:
    print("  %-10s %-8.4f %-8.4f %.4f" % ("ALL", cur[1], cur[2], cur[3]))
print("")
print("  per-lane coverage obs_frac > 0.90: %d/%d%s"
      % (cur[4], cur[5], ("   (baseline %d/%d)" % (ref[4], ref[5])) if ref else ""))
if cur[6]:
    print("  MISSING COMBOS: %s" % ", ".join(cur[6]))
