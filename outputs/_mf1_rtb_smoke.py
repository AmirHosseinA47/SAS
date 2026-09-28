"""mf1 Part 1: return-to-base trips and battery triggers in the 27 sysdebug smoke runs (read-only)."""
import glob
import json
import os

base = os.path.dirname(os.path.abspath(__file__))
files = sorted(glob.glob(os.path.join(base, "_sd_S_*.json"))) + sorted(glob.glob(os.path.join(base, "_sd_T*.json"))) \
    + sorted(glob.glob(os.path.join(base, "_sd_H*.json")))
print("run                    scenario     minbat trips  trigger steps / levels                     releases        battery triggers")
for f in files:
    d = json.load(open(f, encoding="utf-8"))
    rows = d["rows_uav"]  # [uid, x, y, role, battery, rtb_active, rtb_docked, target, action]
    prev, trig, rel = {}, [], []
    for i, step in enumerate(rows):
        for r in step:
            if r[5] and not prev.get(r[0]):
                trig.append("%d@%.0f" % (i + 1, r[4]))
            if prev.get(r[0]) and not r[5]:
                rel.append(str(i + 1))
            prev[r[0]] = r[5]
    bt = sorted({k for t in d["rows_trig"] for k in t if "BATTERY" in k})
    print("%-22s %-12s %5.1f %5d  %-42s %-15s %s" % (d["tag"], d["eval"]["scenario"], min(r[4] for s in rows for r in s),
          len(trig), ",".join(trig), ",".join(rel), bt or "none"))
