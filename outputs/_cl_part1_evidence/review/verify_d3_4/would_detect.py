"""Counterfactual (trajectories held fixed): for each co-marked OTHER victim in the 9 D3
cases, the first step t > marking step s at which any UAV was within UAV_OBSERVATION_RADIUS (8,
euclidean) of the victim's recorded cell. If t < 210 the candidate would have been CONFIRMED
(detection skips only dead/cancelled/rescued/unreachable), not relabelled never_detected.
Also: the sole carrier's state after s (alive? when back on grid, idle)."""
import json, os, math

OUT = r"E:\Projects\SAS\outputs"
FILES = [
    "_ffr_dimA_east_def_101.json",
    "_ffr_dimB_east_def_101.json",
    "_ffr_f2cDRY_east_def_101.json",
    "_ffr_dimfreshbase_east_half_606.json",
    "_ffr_dimfreshbase_east_half_1010.json",
    "_ffr_d4off_east_half_1323590814.json",
    "_ffr_f2b404s12_south_half_404.json",
    "_ffr_dfpCB_west_half_303.json",
    "_ffr_dfpB_west_half_505.json",
]
R = 8.0
tally = {"cand_detect_lt210": 0, "cand_no_detect": 0, "cand_detect_ge210": 0}
for f in FILES:
    d = json.load(open(os.path.join(OUT, f)))
    esc = d["unreachable_escape_log"]
    vs = d["victim_steps"]
    us = d["uav_steps"]
    H = len(vs)
    s = min(e["step"] for e in esc if e["cause"] == "geographically_isolated")
    marked = [e["victim_id"] for e in esc if e["step"] == s and e["cause"] == "geographically_isolated"]
    before = {r[0]: r[2] for r in vs[s - 2]}
    exiting_units = {r[0] for r in d["ff_steps"][s - 2] if r[4]}
    carried = {e["victim"] for e in d["exit_starts"] if e["step"] <= s and e["ff"] in exiting_units}
    print(f"{f}  s={s} horizon={H}")
    for v in marked:
        if v in carried:
            continue
        st = before.get(v)
        first = None
        for t in range(s + 1, H + 1):
            vrow = [r for r in vs[t - 1] if r[0] == v]
            if not vrow or vrow[0][1] is None:
                continue
            vx, vy = vrow[0][1]
            if vrow[0][2] == "dead":
                break
            for u in us[t - 1]:
                if u[1] is None:
                    continue
                if math.hypot(u[1][0] - vx, u[1][1] - vy) <= R:
                    first = t
                    break
            if first:
                break
        end = [r for r in vs[-1] if r[0] == v][0]
        print(f"    {v:9s} status@s-1={st:10s} first UAV within 8 after s: {first}   end={end[2]}")
        if st == "candidate":
            if first is None:
                tally["cand_no_detect"] += 1
            elif first < 210:
                tally["cand_detect_lt210"] += 1
            else:
                tally["cand_detect_ge210"] += 1
    # sole carrier after s
    carrier = sorted(exiting_units)
    for c in carrier:
        traj = []
        for t in range(s, min(H, s + 40) + 1):
            row = [r for r in d["ff_steps"][t - 1] if r[0] == c][0]
            traj.append((t, tuple(row[1]) if row[1] else None, row[2], row[4], row[5]))
        dead_at = next((t for t in range(s, H + 1) for r in d["ff_steps"][t - 1] if r[0] == c and r[5]), None)
        asg = [a for a in d["assigns"] if a.get("ff") == c and a.get("step", 0) > s]
        print(f"    carrier {c} dead_at={dead_at} later assigns={[(a.get('step'), a.get('vid'), a.get('reason')) for a in asg][:6]}")
print(tally)
