#!/usr/bin/env python
"""Depot-cost round: is the --set passthrough added to the gate script INERT?

Part 2 added a --set flag to outputs/_rblatch_campaign2.py so the route_blocked
gate could run on an ARMED arm - the gate could not do that before, and the only
alternative was editing the shipped default, which this round is forbidden to do.

That addition has an obligation attached. The e703861 gate REFERENCE (tag `rbc`,
18 seeds, four shards) was produced by the script BEFORE the flag existed. If the
flag changed anything when it is not passed, the reference is not comparable and
every gate result in the round is unreadable. So one shard is re-run through the
MODIFIED script with NO --set and compared here FIELD FOR FIELD against the
reference shard it should reproduce.

_ffr_rbcompare.py cannot answer this: it compares a 4-tuple per seed plus pooled
counters, which is a summary, not an identity. This compares every recorded key.

Two keys are EXPECTED to differ and are excluded, with the reason:
  tag     the re-run is tagged differently on purpose, so the two shards can
          coexist on disk without one being globbed into the other's merge
  wall_s  wall-clock seconds per seed; it is a timing, not a result

usage:
  python outputs/_dc_rbinert.py --new dcinerta --old rbca --wind east
Read-only. Runs no simulation.
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXCLUDE_TOP = ("tag",)
EXCLUDE_EVAL = ("wall_s",)


def load(tag, wind):
    p = os.path.join(HERE, "_rblatch_camp2_%s_D_%s.json" % (tag, wind))
    if not os.path.exists(p):
        return None, p
    with open(p, encoding="utf-8") as f:
        return json.load(f), p


def scrub(d):
    out = {k: v for k, v in d.items() if k not in EXCLUDE_TOP}
    out["evals"] = [{k: v for k, v in e.items() if k not in EXCLUDE_EVAL}
                    for e in (d.get("evals") or [])]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", default="dcinerta")
    ap.add_argument("--old", default="rbca")
    ap.add_argument("--wind", default="east")
    a = ap.parse_args()

    new, pn = load(a.new, a.wind)
    old, po = load(a.old, a.wind)
    print("RBGATE --set INERTNESS  %s vs %s  (wind %s)" % (a.new, a.old, a.wind))
    if new is None or old is None:
        print("  MISSING: %s" % (pn if new is None else po))
        print("  VERDICT: CANNOT ANSWER - the gate reference is unvalidated.")
        raise SystemExit(1)

    n, o = scrub(new), scrub(old)
    keys = sorted(set(n) | set(o))
    diffs = [k for k in keys if n.get(k) != o.get(k)]
    print("  compared %d top-level keys (excluding %s; per-seed excluding %s)"
          % (len(keys), ", ".join(EXCLUDE_TOP), ", ".join(EXCLUDE_EVAL)))
    print("  seeds: %s" % (o.get("seeds"),))
    if not diffs:
        print("  IDENTICAL on every compared key.")
        print("  VERDICT: PASS - the --set addition is inert with no --set, so the")
        print("  e703861 reference shards remain valid for the gate comparison.")
        return
    print("  DIFFERING KEYS: %s" % ", ".join(diffs))
    for k in diffs:
        vo, vn = o.get(k), n.get(k)
        if k == "evals":
            for eo, en in zip(vo, vn):
                for kk in sorted(set(eo) | set(en)):
                    if eo.get(kk) != en.get(kk):
                        print("     seed %s  %-22s %r -> %r"
                              % (eo.get("seed"), kk, eo.get(kk), en.get(kk)))
        else:
            print("     %-22s %r -> %r" % (k, vo, vn))
    print("  VERDICT: FAIL - the addition is NOT inert. The reference cannot be")
    print("  used and the gate must be re-measured on both sides.")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
