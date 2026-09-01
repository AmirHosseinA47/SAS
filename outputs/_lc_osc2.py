"""Per-cell oscillation attribution, and direct last_cell-violation counting.

The 62b4fbe standard: a "direct last_cell violation" is a survival move that
lands on the cell `_idle_retreat_last_cell` held at entry to that call.  Under
a fix arm the SANCTIONED re-admissions are exactly such moves and are counted
separately; anything left over would be a defect.

Read-only.
"""
from __future__ import annotations
import os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _lc_p1 import BASE13, load, tup  # noqa: E402

ARMS = ["none", "a", "b", "c"]


def cell_osc(d):
    mv = defaultdict(list)
    for x in d["surv"]:
        if x["moved"] and x["pos"] and x["post"]:
            mv[(int(x["seed"]), str(x["ff"]))].append(
                (int(x["step"]), tup(x["pos"]), tup(x["post"])))
    t = defaultdict(int)
    for seq in mv.values():
        seq.sort()
        t["moves"] += len(seq)
        for i in range(len(seq)):
            for j in range(i + 1, len(seq)):
                if seq[j][1] == seq[i][2] and seq[j][2] == seq[i][1]:
                    t["rev_any"] += 1
                    if seq[j][0] - seq[i][0] == 1:
                        t["rev_tight"] += 1
    return t


def violations(d):
    """Survival moves that land on the last_cell the call started with."""
    sanctioned = set()
    for c in d["cand"]:
        if c.get("readmitted"):
            sanctioned.add((int(c["seed"]), str(c["ff"]), int(c["step"])))
        # arm 'a' does not set readmitted; its sanctioned scans are the
        # cur_dist==0 ones where the filter was dropped
        if d["arm"] == "a" and int(c["cur_dist"]) == 0 and c["lc_admissible"]:
            sanctioned.add((int(c["seed"]), str(c["ff"]), int(c["step"])))
    n_v = n_s = 0
    rows = []
    for x in d["surv"]:
        if not x["moved"] or not x["post"] or not x["last_cell_pre"]:
            continue
        if tup(x["post"]) == tup(x["last_cell_pre"]):
            k = (int(x["seed"]), str(x["ff"]), int(x["step"]))
            if k in sanctioned:
                n_s += 1
            else:
                n_v += 1
                rows.append((int(x["step"]), str(x["ff"]), tup(x["pos"]),
                             tup(x["post"])))
    return n_v, n_s, rows


print("%-20s %s" % ("cell", "  ".join("%-22s" % ("arm " + a) for a in ARMS)))
print("%-20s %s" % ("", "  ".join("%-22s" % "moves/revAny/revTight" for a in ARMS)))
tot = {a: defaultdict(int) for a in ARMS}
for c in BASE13:
    line = "%-20s" % ("%s_%s_%d" % c)
    vals = {}
    for a in ARMS:
        d = load(a, *c)
        t = cell_osc(d)
        vals[a] = (t["moves"], t["rev_any"], t["rev_tight"])
        for k in ("moves", "rev_any", "rev_tight"):
            tot[a][k] += t[k]
        nv, ns, rows = violations(d)
        tot[a]["viol"] += nv
        tot[a]["sanctioned"] += ns
        if nv:
            tot[a].setdefault("rows", [])
        line += "  %-22s" % ("%d/%d/%d" % vals[a])
    base = vals["none"]
    flag = "  <--" if any(vals[a] != base for a in ARMS[1:]) else ""
    print(line + flag)
print("-" * 110)
print("%-20s %s" % ("TOTAL", "  ".join(
    "%-22s" % ("%d/%d/%d" % (tot[a]["moves"], tot[a]["rev_any"], tot[a]["rev_tight"]))
    for a in ARMS)))
print()
print("DIRECT last_cell VIOLATIONS (move lands on the last_cell the call started with)")
for a in ARMS:
    print("  arm %-5s unsanctioned %d   sanctioned by the arm itself %d"
          % (a, tot[a]["viol"], tot[a]["sanctioned"]))
print()
print("UNSANCTIONED VIOLATION DETAIL")
for a in ARMS:
    for c in BASE13:
        d = load(a, *c)
        nv, ns, rows = violations(d)
        for r in rows:
            print("  arm %-5s %-20s s%-4d %-10s %s -> %s"
                  % (a, "%s_%s_%d" % c, r[0], r[1], r[2], r[3]))
