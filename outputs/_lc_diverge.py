"""First divergence between two arms on one cell, and the scan that caused it.

usage: _lc_diverge.py <armA> <armB> <wind> <roles> <seed>
Read-only.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _lc_p1 import load, tup  # noqa: E402


def trace(d):
    out = {}
    for r in d["fftrace"]:
        out[(str(r["ff"]), int(r["step"]))] = (tup(r["pos"]), bool(r["dead"]),
                                               str(r["status"]), str(r["cat"]))
    return out


def main():
    a, b, w, r, s = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
    da, db = load(a, w, r, s), load(b, w, r, s)
    if da is None or db is None:
        print("missing data"); return
    ta, tb = trace(da), trace(db)
    ffs = sorted(set(k[0] for k in ta))
    first = None
    for step in range(1, int(da["steps"]) + 1):
        for ff in ffs:
            if ta.get((ff, step)) != tb.get((ff, step)):
                first = (step, ff); break
        if first: break
    print("cell %s/%s/%d   arms %s vs %s" % (w, r, s, a, b))
    print("evals %s : %s" % (
        {k: da["evals"][0][k] for k in ("rescued", "dead", "firefighter_deaths")},
        {k: db["evals"][0][k] for k in ("rescued", "dead", "firefighter_deaths")}))
    print("deaths %s : %s" % (
        [(x["step"], x["ff"], x["pos"]) for x in da["deaths"]],
        [(x["step"], x["ff"], x["pos"]) for x in db["deaths"]]))
    if not first:
        print("NO DIVERGENCE in fftrace")
        return
    step, ff = first
    print("first divergence: step %d %s   %s -> %s" % (step, ff, ta.get((ff, step)),
                                                       tb.get((ff, step))))
    print()
    print("candidate scans for %s in steps %d..%d" % (ff, step - 3, step + 2))
    for tag, d in ((a, da), (b, db)):
        print("  arm %s:" % tag)
        for c in d["cand"]:
            if str(c["ff"]) == ff and step - 3 <= int(c["step"]) <= step + 2:
                print("    s%-4d cell=%-9s lc=%-9s cur_d=%d nfree=%d free=%s "
                      "n_stock=%d n_ret=%d readm=%s stall=%s idle=%s lc_d=%s"
                      % (c["step"], tuple(c["cell"]),
                         tuple(c["last_cell"]) if c["last_cell"] else None,
                         c["cur_dist"], c["n_free"], [tuple(x) for x in c["free"]],
                         c["n_stock"], c["n_returned"], c.get("readmitted"),
                         c["stalled"], c["idle"], c["lc_dist"]))
    print()
    print("positions %s steps %d..%d" % (ff, step - 3, step + 8))
    for st in range(max(1, step - 3), min(int(da["steps"]), step + 8) + 1):
        print("    s%-4d  %-40s | %s" % (st, ta.get((ff, st)), tb.get((ff, st))))


main()
