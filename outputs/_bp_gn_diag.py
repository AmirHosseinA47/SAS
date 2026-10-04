"""bayesprep screen: why a run never finishes (G-N) - DETECTION or RESCUE - and the same victim in the reference run.

usage: _bp_gn_diag.py <tag>_<cell> [<ref_tag>_<cell>] ...   e.g. bpdr_D_N bpcr_D_N
       _bp_gn_diag.py --all          every screen run without terminal_step (outputs/_sd_bp*_*.json), each against
                                     bpc at the same placement and cell

For every victim of the run: spawn cell, first '[Victim Detection]' step (stdout), end status (marker / managed,
firefighter, rescued), the step it died if it died; for every victim ALIVE AND NOT RESCUED at the end: detected or not,
its final cell, and the closest approach (Euclidean) of any UAV and of any victim searcher over the run. The run is
classed DETECTION (an alive victim never detected) or RESCUE (every alive unrescued victim was detected).
Read-only on outputs/; no model import.
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DET_RE = re.compile(r"^\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at")


def load(name):
    p = os.path.join(HERE, "_sd_%s.json" % name)
    d = json.load(open(p, encoding="utf-8"))
    det = {}
    so = p[:-5] + ".stdout.txt"
    if os.path.exists(so):
        for line in open(so, encoding="utf-8"):
            m = DET_RE.match(line.strip())
            if m and m.group(3) not in det:
                det[m.group(3)] = int(m.group(1))
    d["_det"] = det
    return d


def victims(d):
    rows = d["rows_vic"]
    out = {}
    for v in rows[0]:
        out[v[0]] = {"spawn": (v[1], v[2]), "det": d["_det"].get(v[0]), "died": None, "path": []}
    for i, step_rows in enumerate(rows):
        for v in step_rows:
            o = out[v[0]]
            if v[1] is not None:
                o["path"].append((i + 1, (v[1], v[2])))
            if o["died"] is None and v[3] == "dead":
                o["died"] = i + 1
    for v in rows[-1]:
        o = out[v[0]]
        o["end"] = {"marker": v[3], "managed": v[4], "ff": v[5], "assigned": v[6], "unreachable": v[7],
                    "cancelled": v[8], "rescued": v[9]}
    return out


def closest(d, path, searchers_only=False):
    best = (math.inf, None, None)
    pos = dict(path)
    for i, step_rows in enumerate(d["rows_uav"]):
        t = i + 1
        if t not in pos:
            continue
        vx, vy = pos[t]
        for u in step_rows:
            if u[1] is None or (searchers_only and u[3] != "victim_searcher"):
                continue
            dist = math.hypot(u[1] - vx, u[2] - vy)
            if dist < best[0]:
                best = (dist, t, u[0])
    return best


def report(name):
    d = load(name)
    vs = victims(d)
    print("%s  scenario %s wind %s seed %s  terminal_step %s  rescued %s dead %s" % (
        name, d["scenario"], d["wind"], d["seed"], d.get("terminal_step"), d["eval"].get("rescued"),
        d["eval"].get("dead")))
    open_ = []
    for vid, o in sorted(vs.items()):
        e = o["end"]
        alive_unres = e["marker"] not in ("dead", "rescued") and not e["rescued"]
        line = "  %-9s spawn %-9s det %-5s died %-5s end %s/%s ff %s rescued %s" % (
            vid, o["spawn"], o["det"], o["died"], e["marker"], e["managed"], e["ff"], e["rescued"])
        if alive_unres:
            c_all, c_s = closest(d, o["path"]), closest(d, o["path"], True)
            last = o["path"][-1][1] if o["path"] else None
            line += "  <== ALIVE, NOT RESCUED: final cell %s, closest UAV %.2f (step %s, %s), closest searcher %.2f" % (
                last, c_all[0], c_all[1], c_all[2], c_s[0])
            open_.append(o["det"] is None)
        print(line)
    if d.get("terminal_step") is None:
        cls = "DETECTION" if any(open_) else ("RESCUE" if open_ else "UNCLEAR (no alive unrescued victim)")
        print("  => never finishes: %s" % cls)
    return d


def main():
    args = sys.argv[1:]
    if args == ["--all"]:
        for p in sorted(glob.glob(os.path.join(HERE, "_sd_bp*_*.json"))):
            name = os.path.basename(p)[4:-5]
            m = re.match(r"^(bp[a-z]+?)(r|u2|u)_([A-D]_[ENSW])$", name)
            if not m or m.group(1) in ("bpv1", "bpn"):
                continue
            d = json.load(open(p, encoding="utf-8"))
            if d.get("terminal_step") is not None:
                continue
            report(name)
            ref = "bpc%s_%s" % (m.group(2), m.group(3))
            if m.group(1) != "bpc" and os.path.exists(os.path.join(HERE, "_sd_%s.json" % ref)):
                print("  reference:")
                report(ref)
            print()
        return 0
    for name in args:
        report(name)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
