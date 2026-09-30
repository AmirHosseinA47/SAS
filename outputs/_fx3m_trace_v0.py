"""fix3a merge - timeline of the late victim in each route_blocked trace (read-only).
Prints every change of the victim's marker status / managed status / firefighter / rescue_assigned / unreachable /
cancelled, the victim's position at those steps, and the assigned firefighter's position, status and target.

usage (repo root): .venv/Scripts/python.exe outputs/_fx3m_trace_v0.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _fx3r_analyze as R  # noqa: E402

TRACES = (("fx3mTe606", "victim_0"), ("fx3mTs505", "victim_0"))


def main():
    for tag, vid in TRACES:
        d = R.load_one(os.path.join(HERE, "_sd_%s.json" % tag))
        print("=" * 100)
        print("%s %s detected %s (first [Victim Detection] event)" % (tag, vid, d["_det"].get(vid)))
        prev = None
        for t, row in enumerate(d["rows_vic"]):
            v = next((x for x in row if x[0] == vid), None)
            if v is None:
                continue
            key = tuple(v[3:])
            if key != prev:
                ffid = v[5]
                ff = None
                if ffid:
                    ff = next((f for f in d["rows_ff"][t] if f[0] == ffid), None)
                print("  step %3d  pos (%s,%s) marker %-10s managed %-10s ff %-6s assigned %s unreach %s cancel %s"
                      " rescued %s | ff %s" % (
                          t + 1, v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9],
                          (ff and "pos (%s,%s) status %s target %s exiting %s" % (ff[1], ff[2], ff[3], ff[9], ff[5]))))
                prev = key
        # firefighters over the window: status changes of every firefighter
        print("  firefighter status changes:")
        prevf = {}
        for t, row in enumerate(d["rows_ff"]):
            for f in row:
                k = (f[3], f[4], f[5], f[8], tuple(f[9]) if f[9] else None)
                if prevf.get(f[0]) != k:
                    print("    step %3d %s pos (%s,%s) status %-12s assigned %s exiting %s victim %s target %s" % (
                        t + 1, f[0], f[1], f[2], f[3], f[4], f[5], f[8], f[9]))
                    prevf[f[0]] = k


if __name__ == "__main__":
    main()
