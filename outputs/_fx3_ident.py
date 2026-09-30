"""fix3a - value identity of two probe arms (read-only).

usage: _fx3_ident.py <tagA> <tagB> [--cfgs A_E,A_N,...] [--no-mf2]
Compares, per configuration present in both arms, every behavioural _sd_probe field (rows_uav,
rows_ff, rows_vic, rows_dec, rows_trig, eval, terminal_step, steps_done, crashed, stdout_sha,
stdout_tags, inline_violations, warning_count) and, unless --no-mf2, the mf2 observer sections.
params / argv / tag / head / src_sha / wall_s / fx3 are provenance, not behaviour, and are
reported separately (head and the switch-bearing params).
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDS = ("rows_uav", "rows_ff", "rows_vic", "rows_dec", "rows_trig", "eval", "terminal_step",
          "steps_done", "crashed", "stdout_sha", "stdout_tags", "inline_violations", "warning_count")


def arm(tag):
    out = {}
    for f in glob.glob(os.path.join(HERE, "_sd_%s_*.json" % tag)):
        cfg = os.path.basename(f)[len("_sd_%s_" % tag):-len(".json")]
        out[cfg] = f
    return out


def main():
    a, b = sys.argv[1], sys.argv[2]
    cfgs = None
    if "--cfgs" in sys.argv:
        cfgs = set(sys.argv[sys.argv.index("--cfgs") + 1].split(","))
    use_mf2 = "--no-mf2" not in sys.argv
    A, B = arm(a), arm(b)
    common = sorted(set(A) & set(B))
    if cfgs:
        common = [c for c in common if c in cfgs]
    n_same = 0
    for c in common:
        da = json.load(open(A[c], encoding="utf-8"))
        db = json.load(open(B[c], encoding="utf-8"))
        diff = [k for k in FIELDS if da.get(k) != db.get(k)]
        if use_mf2:
            for k in sorted(set((da.get("mf2") or {})) | set((db.get("mf2") or {}))):
                if k == "probe":
                    continue
                if (da.get("mf2") or {}).get(k) != (db.get("mf2") or {}).get(k):
                    diff.append("mf2." + k)
        first = None
        if "rows_uav" in diff:
            for t, (ra, rb) in enumerate(zip(da["rows_uav"], db["rows_uav"])):
                if ra != rb:
                    first = t + 1
                    break
        same = not diff
        n_same += same
        print("%-5s %s  head %s / %s  %s%s" % (
            c, "IDENTICAL" if same else "DIFFER", str(da.get("head"))[:8], str(db.get("head"))[:8],
            "" if same else "fields " + ",".join(diff),
            "" if first is None else "  first rows_uav diff at step %d" % first))
    print("%s vs %s: %d/%d identical on every behavioural field%s" % (
        a, b, n_same, len(common), " (+ mf2 sections)" if use_mf2 else ""))


if __name__ == "__main__":
    main()
