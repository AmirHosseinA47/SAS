"""firemech round 2, Part 1: read the second probe wave (outputs/_fm2probe2_queue.txt). Read-only.

Per-run metrics come from outputs/_firemech_analyze.run_summary (round-1 definitions: intact =
2500 - ever_burned - cleared, E1/E2, deaths). Pairs each arm with its reference:
  f2cEFS, f2cDRY, f2cGW, f2cGF, f2cGES  vs f2cOFF (CRN control, wave 1)
  f2GES                               vs fmOFF  (stock control)
Also: f2cDRY fire == f2cOFF 240/240; gated arms rescued/dead == reference per run and gate opening
after terminal; f2cEFS vs f2cDRY (writes at matched behaviour under CRN).
A run is read only if its JSON exists with no .tmp/.fm2p.tmp and its .out log carries "seed=".

usage: _fm2_wave2_read.py [--sample canonical|fresh|both]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _firemech_analyze as FA  # noqa: E402

CANON = FA.CANONICAL
FRESH = FA.FRESH
PAIRS = [("f2cEFS", "f2cOFF"), ("f2cDRY", "f2cOFF"), ("f2cEFS", "f2cDRY"), ("f2cGW", "f2cOFF"),
         ("f2cGF", "f2cOFF"), ("f2cGES", "f2cOFF"), ("f2GES", "fmOFF"), ("f2GW", "fmOFF"), ("f2GF", "fmOFF"),
         ("f2cES", "f2cOFF"), ("f2cF", "f2cOFF")]
GATED = {"f2cGW", "f2cGF", "f2cGES", "f2GES", "f2GW", "f2GF"}


def rr(r):
    return "def" if r == "default" else r


def name(tag, t):
    return "%s_%s_%s_%d" % (tag, t[0], rr(t[1]), t[2])


def load(tag, t):
    n = name(tag, t)
    p = os.path.join(HERE, "_ffr_%s.json" % n)
    if not os.path.exists(p) or os.path.exists(p + ".tmp") or os.path.exists(p + ".fm2p.tmp"):
        return None
    if not tag.startswith("fm"):
        o = os.path.join(HERE, "_ffr_logs", n + ".out")
        if not os.path.exists(o) or "seed=" not in open(o, encoding="utf-8", errors="replace").read():
            return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def victims(d):
    return {v: st for v, _p, st in d["victim_steps"][-1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="both", choices=["canonical", "fresh", "both"])
    a = ap.parse_args()
    samples = {"canonical": [("canonical", CANON)], "fresh": [("fresh", FRESH)],
               "both": [("canonical", CANON), ("fresh", FRESH), ("both", CANON + FRESH)]}[a.sample]
    cache = {}

    def get(tag, t):
        k = (tag, t)
        if k not in cache:
            cache[k] = load(tag, t)
        return cache[k]

    for sname, tuples in samples:
        for dedup in (False, True):
            tt = [t for t in tuples if not (dedup and t[1] == "default")]
            print("=" * 100)
            print("SAMPLE %s %s (%d tuples)" % (sname, "DE-DUPLICATED (east/def excluded)" if dedup else "COUNTED", len(tt)))
            print("  %-7s vs %-7s %4s | %-13s %-13s | %-18s | %-9s | %-12s | %s" % (
                "arm", "ref", "n", "arm r/d/ffd", "ref r/d/ffd", "intact d (up/dn/=)", "flip runs",
                "E1 arm/ref", "checks"))
            for arm, ref in PAIRS:
                n = 0
                sa = {"rescued": 0, "dead": 0, "ffd": 0}
                sr = {"rescued": 0, "dead": 0, "ffd": 0}
                di = 0
                up = dn = eq = 0
                flips = 0
                e1 = [0, 0, 0, 0]
                checks = []
                viol = 0
                opened_before_term = 0
                for t in tt:
                    da, dr = get(arm, t), get(ref, t)
                    if da is None or dr is None:
                        continue
                    n += 1
                    off = get("fmOFF", t) if ref != "fmOFF" else dr
                    A = FA.run_summary(da, off)
                    R = FA.run_summary(dr, off)
                    for k in sa:
                        sa[k] += A[k]
                        sr[k] += R[k]
                    d = A["intact"] - R["intact"]
                    di += d
                    up += d > 0
                    dn += d < 0
                    eq += d == 0
                    flips += victims(da) != victims(dr)
                    e1[0] += A["e1n"]; e1[1] += A["e1d"]; e1[2] += R["e1n"]; e1[3] += R["e1d"]
                    if arm == "f2cDRY" and ref == "f2cOFF" and da["fire_digests"] != dr["fire_digests"]:
                        viol += 1
                    if arm in GATED and ref in ("f2cOFF", "fmOFF"):
                        if (A["rescued"], A["dead"]) != (R["rescued"], R["dead"]) or victims(da) != victims(dr):
                            viol += 1
                        rows = da.get("firefight_log") or []
                        term = dr.get("terminal_step")
                        if rows and (term is None or rows[0]["step"] <= term):
                            opened_before_term += 1
                if n == 0:
                    print("  %-7s vs %-7s    0  (no complete pairs yet)" % (arm, ref))
                    continue
                if arm == "f2cDRY" and ref == "f2cOFF":
                    checks.append("fire!=ref runs %d" % viol)
                if arm in GATED and ref in ("f2cOFF", "fmOFF"):
                    checks.append("outcome!=ref runs %d, opened<=terminal %d" % (viol, opened_before_term))
                print("  %-7s vs %-7s %4d | %4d/%3d/%3d  %4d/%3d/%3d  | %+6d (%2d/%2d/%2d) | %9d | %5.2f/%5.2f%% | %s" % (
                    arm, ref, n, sa["rescued"], sa["dead"], sa["ffd"], sr["rescued"], sr["dead"], sr["ffd"],
                    di, up, dn, eq, flips, 100.0 * e1[0] / max(1, e1[1]), 100.0 * e1[2] / max(1, e1[3]),
                    "; ".join(checks)))
    # bisection block
    print("=" * 100)
    print("south/half/404 WRITE_BEFORE bisection (vs fmDRY / fmEFS)")
    t = ("south", "half", 404)
    dry, efs = get("fmDRY", t), get("fmEFS", t)
    for s in (9, 12, 13, 14, 16):
        d = get("f2b404s%d" % s, t)
        if d is None:
            print("  s=%d pending" % s)
            continue
        e = d["eval"]
        fd = lambda x: next((i + 1 for i, (p, q) in enumerate(zip(d["fire_digests"], x["fire_digests"])) if p != q), None)
        print("  s=%-2d r/d/ffd %d/%d/%d fire first div vs DRY %s vs EFS %s victims %s" % (
            s, e["rescued"], e["dead"], e["firefighter_deaths"], fd(dry), fd(efs), victims(d)))


if __name__ == "__main__":
    main()
