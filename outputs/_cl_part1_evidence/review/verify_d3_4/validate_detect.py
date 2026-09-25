"""Validate the radius-8 counterfactual: in the same 9 files, for every victim, predicted first
detection step (first t with a UAV within 8 of its recorded cell, before it is marked) vs the recorded
first step its status leaves 'candidate'. Tries lags 0 and 1 between uav_steps and victim_steps."""
import json, os, math

OUT = r"E:\Projects\SAS\outputs"
FILES = [
    "_ffr_dimA_east_def_101.json", "_ffr_dimB_east_def_101.json", "_ffr_f2cDRY_east_def_101.json",
    "_ffr_dimfreshbase_east_half_606.json", "_ffr_dimfreshbase_east_half_1010.json",
    "_ffr_d4off_east_half_1323590814.json", "_ffr_f2b404s12_south_half_404.json",
    "_ffr_dfpCB_west_half_303.json", "_ffr_dfpB_west_half_505.json",
]
agree = {0: 0, 1: 0, -1: 0}
n = 0
for f in FILES:
    d = json.load(open(os.path.join(OUT, f)))
    vs, us = d["victim_steps"], d["uav_steps"]
    H = len(vs)
    vids = [r[0] for r in vs[0]]
    for v in vids:
        rec = None
        for t in range(1, H + 1):
            row = [r for r in vs[t - 1] if r[0] == v][0]
            if row[2] != "candidate":
                rec = (t, row[2])
                break
        preds = {}
        for lag in (0, 1, -1):
            p = None
            for t in range(1, H + 1):
                tu = t + lag
                if tu < 1 or tu > H:
                    continue
                row = [r for r in vs[t - 1] if r[0] == v][0]
                if row[2] != "candidate" and (rec is None or t > rec[0]):
                    break
                if row[1] is None:
                    continue
                if any(u[1] is not None and math.hypot(u[1][0] - row[1][0], u[1][1] - row[1][1]) <= 8 for u in us[tu - 1]):
                    p = t
                    break
            preds[lag] = p
        n += 1
        ok = {lag: (rec is not None and preds[lag] == rec[0]) for lag in preds}
        for lag in ok:
            agree[lag] += ok[lag]
        print(f"{f[5:40]:36s} {v:9s} recorded leave-candidate={rec} pred lag0={preds[0]} lag1={preds[1]} lag-1={preds[-1]}")
print("agreement", agree, "of", n)
