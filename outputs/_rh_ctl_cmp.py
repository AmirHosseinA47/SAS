"""Compare two _rh_control tag sets, digest by digest and element by element.

Deliberately does NOT stop at hashes:
  * agent_positions is compared as a LIST, element for element
  * the evaluation metric dict is compared key by key
  * modetraj is compared step by step, and the first divergent step reported
  * the raw stdout files are compared as BYTES

usage: _rh_ctl_cmp.py <tag_a> <tag_b>
"""
from __future__ import annotations
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
LABELS = [
    "east_half_101", "east_half_202", "east_half_303", "east_half_404",
    "east_half_505", "south_half_101", "south_half_202", "south_half_303",
    "south_half_404", "south_half_505", "east_def_101", "east_def_202",
    "east_def_303",
]
SCALARS = [
    "stdout_sha256", "stdout_lines", "stdout_len", "agent_positions_sha256",
    "firemap_sha256", "scorchmap_sha256", "cellcolor_sha256",
    "rngstate_sha256", "modetraj_sha256", "leftover_pending", "terminal_step",
]
DICTS = ["eval", "residue", "ground_counts", "cellcolor_hist", "mode_hist"]


def load(tag, label):
    p = os.path.join(BASE, "_rh_ctl_%s_%s.json" % (tag, label))
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)["run"]


def main(a, b):
    total_diffs = 0
    checked = 0
    print("=" * 78)
    print("CONTROL COMPARISON   %s  vs  %s" % (a, b))
    print("=" * 78)
    for label in LABELS:
        ra, rb = load(a, label), load(b, label)
        diffs = []
        for k in SCALARS:
            checked += 1
            if ra.get(k) != rb.get(k):
                diffs.append("  %-24s %s  !=  %s" % (k, ra.get(k), rb.get(k)))
        for k in DICTS:
            da, db = ra.get(k) or {}, rb.get(k) or {}
            keys = sorted(set(da) | set(db))
            for kk in keys:
                checked += 1
                if da.get(kk) != db.get(kk):
                    diffs.append("  %s[%s]  %s  !=  %s" % (k, kk, da.get(kk), db.get(kk)))
        # positions element for element
        pa, pb = ra.get("agent_positions") or [], rb.get("agent_positions") or []
        checked += 1
        if len(pa) != len(pb):
            diffs.append("  agent_positions LENGTH %d != %d" % (len(pa), len(pb)))
        else:
            for i, (x, y) in enumerate(zip(pa, pb)):
                checked += 1
                if x != y:
                    diffs.append("  agent_positions[%d]  %s  !=  %s" % (i, x, y))
        # mode trajectory step by step
        ma, mb = ra.get("modetraj") or [], rb.get("modetraj") or []
        checked += 1
        if len(ma) != len(mb):
            diffs.append("  modetraj LENGTH %d != %d" % (len(ma), len(mb)))
        else:
            for i, (x, y) in enumerate(zip(ma, mb)):
                checked += 1
                if x != y:
                    diffs.append("  modetraj[step %d]  %s  !=  %s" % (i + 1, x, y))
                    break
        # raw stdout bytes
        fa = os.path.join(BASE, "_rh_ctl_%s_%s.stdout.txt" % (a, label))
        fb = os.path.join(BASE, "_rh_ctl_%s_%s.stdout.txt" % (b, label))
        ba = open(fa, "rb").read()
        bb = open(fb, "rb").read()
        checked += 1
        byte_ok = ba == bb
        if not byte_ok:
            diffs.append("  RAW STDOUT BYTES DIFFER  %d vs %d bytes" % (len(ba), len(bb)))

        status = "IDENTICAL" if not diffs else "*** %d DIFFS ***" % len(diffs)
        print("%-16s  npos=%-3d nmode=%-4d stdout=%d/%d bytes  %s"
              % (label, len(pa), len(ma), len(ba), len(bb), status))
        for d in diffs:
            print(d)
        total_diffs += len(diffs)

    print("-" * 78)
    print("leaf values compared : %d" % checked)
    print("differences          : %d" % total_diffs)
    print("VERDICT              : %s"
          % ("BYTE-IDENTICAL" if total_diffs == 0 else "DIVERGENT"))
    return 0 if total_diffs == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
