"""fix3a Part 3: harness fx3hS (shipped) vs fx3hR (a5a496db) on fix2's 16 canonical tuples - reported, never
gated (a screen). Per tuple: rescued / dead / never_detected / candidate / terminal step / firefighter deaths.
usage: _fx3_hs_compare.py
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ("rescued", "dead", "never_detected", "candidate", "firefighter_deaths")


def main():
    tot = {"R": dict.fromkeys(KEYS, 0), "S": dict.fromkeys(KEYS, 0)}
    nt = {"R": 0, "S": 0}
    n = 0
    for fr in sorted(glob.glob(os.path.join(HERE, "_ffr_fx3hR_*.json"))):
        if ".json." in os.path.basename(fr):
            continue
        fs = fr.replace("_ffr_fx3hR_", "_ffr_fx3rhS_")
        if not os.path.exists(fs):
            print("missing", os.path.basename(fs))
            continue
        n += 1
        a, b = json.load(open(fr, encoding="utf-8")), json.load(open(fs, encoding="utf-8"))
        ea, eb = a["eval"], b["eval"]
        for side, e in (("R", ea), ("S", eb)):
            for k in KEYS:
                tot[side][k] += int(e.get(k) or 0)
            nt[side] += e.get("terminal_step") is None
        key = os.path.basename(fr)[len("_ffr_fx3hR_"):-5]
        print("%-26s R %s term %-4s | S %s term %-4s" % (
            key, "/".join(str(ea.get(k)) for k in KEYS), ea.get("terminal_step"),
            "/".join(str(eb.get(k)) for k in KEYS), eb.get("terminal_step")))
    print("tuples %d  (rescued/dead/never_detected/candidate/ff_deaths)" % n)
    for side in ("R", "S"):
        print("  %s  %s  no terminal %d" % (side, "/".join(str(tot[side][k]) for k in KEYS), nt[side]))


if __name__ == "__main__":
    main()
