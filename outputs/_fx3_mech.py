"""fix3a Part 1 - the depot-pocket MECHANISM, from outputs/_fx3_probe.py runs (read-only).

usage: _fx3_mech.py <tag> <cfg> <uid> <from_step> <to_step>
   or: _fx3_mech.py <tag> --episodes     (every searcher pocket episode, one summary line each,
                                          with the dominant event pattern)
Per step: position before the decision, edge-blocked flags [E,S(-y),W,N(+y)], the targets the
routing used (T wind target, R route, F forced progress + its method and pocket-blocked neighbours,
C choose_best_direction), the gate (in -> out), the executed direction/action, and wind-state keys.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _fx3_pockets as P  # noqa: E402

DIRS = "ESWN"   # selected_dir 0..3 = +x, -y, -x, +y


def load(tag, cfg):
    return json.load(open(os.path.join(HERE, "_sd_%s_%s.json" % (tag, cfg)), encoding="utf-8"))


def fmt_step(d, s, uid):
    ev = d["fx3"]["ev"].get(str(s), {}).get(uid, [])
    ws = d["fx3"]["ws"].get(str(s), {}).get(uid, {})
    parts = []
    pos = None
    for e in ev:
        k = e[0]
        if k == "x":
            pos = e[1]
            parts.append("opt=%s act=%s fs=%s ctx=%s" % (e[2], e[3], e[4], ",".join(x[:12] for x in e[5])))
        elif k == "E":
            parts.append("edge=%s" % "".join(DIRS[i] if f else "." for i, f in enumerate(e[1])))
        elif k == "T":
            parts.append("T=%s" % (e[1],))
        elif k == "R":
            parts.append("R(%s)->%s[%s]" % (e[1], e[3] if e[3] is None else DIRS[e[3][0]], e[4]))
        elif k == "F":
            bn = e[5]
            bns = "".join(DIRS[i] if f else "." for i, f in enumerate(bn)) if isinstance(bn, list) else bn
            parts.append("F(%s)->%s[%s] blk=%s" % (e[1], "-" if e[2] is None else DIRS[e[2]], e[3], bns))
        elif k == "C":
            parts.append("C(%s,%s)->%s" % (e[1], e[2][:3], DIRS[e[3]]))
        elif k == "G":
            parts.append("G %s:%s->%s:%s" % (DIRS[e[1]], e[2][-12:], DIRS[e[3]], e[4][-12:]))
        elif k == "X":
            parts.append("=> %s %s" % ("-" if e[1] is None else DIRS[int(e[1])], e[2]))
    wsk = "ps=%s esc=%s fce=%s fir=%s cur=%s ci=%s/%s ycom=%s" % (
        ws.get("pocket_streak"), ws.get("escape_target"), int(bool(ws.get("force_coverage_escape"))),
        int(bool(ws.get("force_interior_retarget"))), ws.get("current_target"), ws.get("corridor_index"),
        len(ws.get("corridor_targets") or []), ws.get("coverage_y_commit"))
    return pos, " | ".join(parts), wsk


def main():
    tag = sys.argv[1]
    if sys.argv[2] == "--episodes":
        files = sorted(glob.glob(os.path.join(HERE, "_sd_%s_*.json" % tag)))
        for f in files:
            d = json.load(open(f, encoding="utf-8"))
            if "fx3" not in d:
                continue
            for full in (False, True):
                eps, term = P.pockets(d, pre_terminal=not full)
                for e in eps:
                    if e["role"] != "victim_searcher":
                        continue
                    if full and term and e["start"] < term:
                        continue   # listed in the pre-terminal pass
                    pat = collections.Counter()
                    flags = collections.Counter()
                    mu = {r[0]: i for i, r in enumerate(d["mf2"]["uav"][0])} if d.get("mf2") else {}
                    for s in range(e["start"], e["end"] + 1):
                        kinds = []
                        fdir = rdir = xdir = edge = None
                        for ev in d["fx3"]["ev"].get(str(s), {}).get(e["uid"], []):
                            if ev[0] == "F":
                                kinds.append("F:" + ev[3])
                                fdir = ev[2]
                            elif ev[0] == "R":
                                kinds.append("R")
                                rdir = ev[3][0] if ev[3] is not None else None
                            elif ev[0] == "C":
                                kinds.append("C")
                            elif ev[0] == "G" and ev[1] != ev[3]:
                                kinds.append("Gchg")
                            elif ev[0] == "E":
                                edge = ev[1]
                            elif ev[0] == "X":
                                xdir = ev[1]
                        pat["+".join(kinds) or "none"] += 1
                        if fdir is not None and rdir is not None and fdir != rdir:
                            flags["route_replaced_by_retreat"] += 1
                        if edge is not None and sum(1 for f in edge if not f) == 1:
                            flags["one_legal_dir"] += 1
                        if edge is not None and all(edge):
                            flags["no_legal_dir"] += 1
                        if xdir is not None and edge is not None and edge[int(xdir)]:
                            flags["exec_edge_blocked_dir"] += 1
                        if mu:
                            row = d["mf2"]["uav"][s - 1]
                            m = [r for r in row if r[0] == e["uid"]]
                            if m and m[0][3] != "moved":
                                flags["not_moved:" + m[0][3]] += 1
                    print("%s %s/%s term=%s %s %s %d-%d len %d cells %s | %s | %s" % (
                        tag, d["scenario"], d["wind"][0].upper(), term, "FULL" if full else "PRE ",
                        e["uid"], e["start"], e["end"], e["len"], e["cells"], dict(pat.most_common(3)),
                        dict(flags)))
        return
    cfg, uid, a, b = sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    d = load(tag, cfg)
    rows = d["rows_uav"]
    for s in range(a, b + 1):
        pos, line, wsk = fmt_step(d, s, uid)
        after = [r for r in rows[s - 1] if r[0] == uid]
        after = (after[0][1], after[0][2]) if after else None
        print("%3d %s->%s %s\n      %s" % (s, pos, after, line, wsk))


if __name__ == "__main__":
    main()
