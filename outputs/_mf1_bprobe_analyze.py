"""mf1 Part 1: summarise the scenario-B reduced-launch-battery probe (_mf1_bp_*.json)."""
import collections
import glob
import json
import os

for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_mf1_bp_*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    rows = d["rows_uav"]
    prev = {}
    trips = []
    for i, step in enumerate(rows):
        for r in step:
            act = r[5]
            if act and not prev.get(r[0]):
                trips.append((i + 1, r[0], round(r[4], 1)))
            prev[r[0]] = act
    minb = min(r[4] for s in rows for r in s)
    trig = collections.Counter()
    trig_steps = collections.defaultdict(list)
    for i, t in enumerate(d["rows_trig"]):
        for k, v in t.items():
            if "BATTERY" in k:
                trig[k] += v
                trig_steps[k].append(i + 1)
    modes = collections.Counter(r.get("mode") for r in d["rows_dec"])
    emerg = [i + 1 for i, r in enumerate(d["rows_dec"]) if r.get("mode") == "emergency"]
    reasons = collections.Counter()
    for r in d["rows_dec"]:
        for x in (r.get("reasons") or r.get("fr") or []):
            if "battery" in str(x):
                reasons[str(x)] += 1
    ev = d["eval"]
    docked = sum(r[6] for s in rows for r in s)
    print("%-20s rescued=%d unreach=%s causes=%s term=%s minbat=%.1f docked_uav_steps=%d" % (
        d["tag"], ev["rescued"], ev["unreachable"], ev["unreachable_causes"] or "-",
        d["terminal_step"], minb, docked))
    print("   rtb trips (step,uav,level): %s" % trips)
    for k in sorted(trig):
        s = trig_steps[k]
        print("   %s: %d trigger-instances on %d steps (first %s, last %s)" % (k, trig[k], len(set(s)), s[0], s[-1]))
    print("   modes: %s  emergency steps: %s  battery reasons: %s" % (dict(modes), (emerg[:12], len(emerg)), dict(reasons)))
