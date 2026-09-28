"""sysdebug round: Part 5 invariant analyzer over outputs/_sd_<name>.json (sd_probe v1).

usage: _sd_analyze.py <queue.jsonl> [--stuck 20] [--win 30] [--out report.txt]

Every check is derived from the probe's per-step rows (post-step state) plus the
probe's inline violations. Thresholds:
  STUCK  a unit that should be moving (FF assigned-approaching or carrying; UAV not
         docked) holds ONE cell for >= --stuck consecutive steps.
  LIVELOCK a WIN-step window (the unit active the whole window) whose positions,
         after collapsing consecutive repeats, visit <= 3 distinct cells with >= 8
         cell changes (dockfix-livelock-gate definition, widened window).
  NO-PROGRESS an FF on its approach whose Manhattan distance to target_pos is not
         below the window-start value after WIN steps while it moved >= 4 times, or a
         UAV on a return leg whose distance to its latched berth is likewise stuck.
A reported episode lists run, first step, last step, agent and cells.
"""
from __future__ import annotations

import collections
import json
import os
import sys

REPO = r"E:\Projects\SAS"
ACTIVE_VICTIM = ("candidate", "detected", "assigned", "confirmed", "en_route", "in_rescue")
TERMINAL = ("rescued", "dead", "unreachable")
ALARM_TAGS = ("RemovalFailure", "RescueInvariant", "KnowledgeMismatch", "Rescue Release Failed",
              "Rescue Hand-over Skipped", "RescueAuthority", "RescueDelayRefused", "Rescue Failed")


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def collapse(cells):
    out = []
    for c in cells:
        if not out or out[-1] != c:
            out.append(c)
    return out


def episodes(flags):
    """[(start_idx, end_idx)] of consecutive True runs."""
    res, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            res.append((start, i - 1))
            start = None
    if start is not None:
        res.append((start, len(flags) - 1))
    return res


def analyze(name, d, stuck_n, win):
    out = collections.defaultdict(list)
    info = {}
    steps = len(d["rows_uav"])
    info["steps"] = steps
    info["crashed"] = d.get("crashed")
    info["eval"] = d.get("eval") or {}
    info["tags"] = d.get("stdout_tags") or {}
    info["inline"] = d.get("inline_violation_counts") or {}
    for k, v in (d.get("inline_violations") or {}).items():
        for row in v[:20]:
            out["inline:" + k].append(row)
    nv = d["params"]["NUM_VICTIMS"]
    ev = info["eval"]
    # ---- I3 accounting
    if ev:
        tot = ev.get("rescued", 0) + ev.get("dead", 0) + ev.get("unreachable", 0) + ev.get("candidate", 0)
        if tot != nv or ev.get("total_victims") != nv:
            out["I3_count_mismatch"].append([tot, ev.get("total_victims"), nv])
    # ---- per-unit series
    ff_series = collections.defaultdict(list)
    for t, row in enumerate(d["rows_ff"], start=1):
        for r in row:
            ff_series[r[0]].append((t, r))
    uav_series = collections.defaultdict(list)
    for t, row in enumerate(d["rows_uav"], start=1):
        for r in row:
            uav_series[r[0]].append((t, r))
    vic_series = collections.defaultdict(list)
    for t, row in enumerate(d["rows_vic"], start=1):
        for r in row:
            vic_series[r[0]].append((t, r))

    # ---- I1 off-grid (FF / victim; UAV is inline)
    for ff, ser in ff_series.items():
        absent_run = 0
        for t, r in ser:
            _, x, y, status, assigned, exiting, dead, off_grid = r[:8]
            if x is None and not off_grid and not dead:
                out["I1_ff_offgrid_unexplained"].append([t, ff, status, assigned, exiting])
            if x is None and off_grid:
                absent_run += 1
                if absent_run == 7:  # absence is drawn in [3,5]; +2 slack
                    out["I1_ff_absence_overrun"].append([t, ff])
            else:
                absent_run = 0
            if dead and x is not None:
                out["I1_dead_ff_on_grid"].append([t, ff, x, y])
    for v, ser in vic_series.items():
        for t, r in ser:
            _, x, y, mstat, vstat = r[:5]
            if x is None and vstat not in ("rescued", "dead"):
                out["I1_victim_offgrid_unexplained"].append([t, v, mstat, vstat])
            if vstat == "rescued" and x is not None:
                out["I1_rescued_victim_still_on_grid"].append([t, v, x, y])

    # ---- I2 stuck / livelock / no-progress: firefighters
    for ff, ser in ff_series.items():
        def moving_role(r):
            _, x, y, status, assigned, exiting, dead, off_grid = r[:8]
            if x is None or dead:
                return None
            if exiting:
                return "carry"
            if assigned and r[9] is not None:
                return "approach"
            return None
        roles = [moving_role(r) for _, r in ser]
        cells = [((r[1], r[2]) if r[1] is not None else None) for _, r in ser]
        for kind in ("approach", "carry"):
            flags = [ro == kind for ro in roles]
            for a, b in episodes(flags):
                # stuck: same cell >= stuck_n consecutive
                run_start = a
                for i in range(a + 1, b + 2):
                    if i > b or cells[i] != cells[run_start]:
                        if i - run_start >= stuck_n:
                            out["I2_ff_stuck_%s" % kind].append([ser[run_start][0], ser[i - 1][0], ff, list(cells[run_start]),
                                                                 ser[run_start][1][3], ser[run_start][1][8]])
                        run_start = i
                # livelock: window with <=3 distinct cells and >=8 changes
                i = a
                while i + win - 1 <= b:
                    wc = cells[i:i + win]
                    col = collapse(wc)
                    if len(set(wc)) <= 3 and len(col) - 1 >= 8:
                        out["I2_ff_livelock_%s" % kind].append([ser[i][0], ser[i + win - 1][0], ff, sorted(set(map(tuple, wc)))])
                        i += win
                    else:
                        i += 1
                # no progress on approach
                if kind == "approach":
                    i = a
                    while i + win - 1 <= b:
                        tgt = ser[i][1][9]
                        tgt2 = ser[i + win - 1][1][9]
                        if tgt is None or tgt2 != tgt:
                            i += 1
                            continue
                        d0 = manhattan(cells[i], tgt)
                        d1 = manhattan(cells[i + win - 1], tgt)
                        moves = len(collapse(cells[i:i + win])) - 1
                        if d1 >= d0 and moves >= 4:
                            out["I2_ff_no_progress_approach"].append([ser[i][0], ser[i + win - 1][0], ff, list(cells[i]), list(tgt), d0, d1, ser[i][1][8]])
                            i += win
                        else:
                            i += 1
    # ---- I2 UAVs
    for uid, ser in uav_series.items():
        cells = [(r[1], r[2]) for _, r in ser]
        docked = [bool(r[6]) for _, r in ser]
        active = [not dk for dk in docked]
        for a, b in episodes(active):
            run_start = a
            for i in range(a + 1, b + 2):
                if i > b or cells[i] != cells[run_start]:
                    if i - run_start >= stuck_n:
                        acts = collections.Counter(ser[k][1][8] for k in range(run_start, i))
                        out["I2_uav_stuck"].append([ser[run_start][0], ser[i - 1][0], uid, list(cells[run_start]),
                                                    ser[run_start][1][3], int(ser[run_start][1][5]), acts.most_common(2)])
                    run_start = i
            i = a
            while i + win - 1 <= b:
                wc = cells[i:i + win]
                col = collapse(wc)
                if len(set(wc)) <= 3 and len(col) - 1 >= 8:
                    acts = collections.Counter(ser[k][1][8] for k in range(i, i + win))
                    out["I2_uav_livelock"].append([ser[i][0], ser[i + win - 1][0], uid, sorted(set(wc)), ser[i][1][3], acts.most_common(2)])
                    i += win
                else:
                    i += 1
        # ---- I6 battery + return legs
        for k, (t, r) in enumerate(ser):
            batt = r[4]
            if batt <= 0.0:
                moved = k > 0 and cells[k] != cells[k - 1]
                out["I6_uav_battery_zero"].append([t, uid, list(cells[k]), int(moved), int(r[5]), int(r[6])])
        rtb = [bool(r[5]) and not bool(r[6]) for _, r in ser]
        for a, b in episodes(rtb):
            berth = ser[a][1][7]
            if berth is None:
                continue
            best = manhattan(cells[a], berth)
            since = 0
            for i in range(a, b + 1):
                dcur = manhattan(cells[i], berth)
                if dcur < best:
                    best = dcur
                    since = 0
                else:
                    since += 1
                    if since == 20:
                        out["I6_rtb_no_progress"].append([ser[i - 19][0], ser[i][0], uid, list(cells[i]), list(berth), dcur])
            if b == len(ser) - 1:
                out["I6_rtb_leg_open_at_end"].append([ser[a][0], uid, list(cells[b]), list(berth), ser[b][1][4]])

    # ---- I4 contact / phantom rescue, I5 double binding
    pickups = collections.defaultdict(list)   # vid -> [(step, ff, ff_cell, victim_cell_prev, victim_cell_now)]
    prev_exit = {}
    prev_vcell = {}
    for t in range(steps):
        vcell = {r[0]: ((r[1], r[2]) if r[1] is not None else None) for r in d["rows_vic"][t]}
        for r in d["rows_ff"][t]:
            ff, x, y, status, assigned, exiting, dead, off_grid, vid = r[:9]
            if exiting and not prev_exit.get(ff, 0) and vid:
                pickups[vid].append([t + 1, ff, [x, y], prev_vcell.get(vid), vcell.get(vid), r[9]])
            prev_exit[ff] = exiting
        prev_vcell = vcell
        binders = collections.defaultdict(list)
        for r in d["rows_ff"][t]:
            ff, x, y, status, assigned, exiting, dead, off_grid, vid = r[:9]
            if vid and not dead and (assigned or exiting):
                binders[vid].append(ff)
        for vid, ffs in binders.items():
            if len(ffs) > 1:
                out["I5_double_binding_step"].append([t + 1, vid, ffs])
    # collapse I5 step rows into episodes
    if out.get("I5_double_binding_step"):
        eps = []
        for row in out["I5_double_binding_step"]:
            if eps and eps[-1][2] == row[1] and eps[-1][1] == row[0] - 1 and eps[-1][3] == row[2]:
                eps[-1][1] = row[0]
            else:
                eps.append([row[0], row[0], row[1], row[2]])
        out["I5_double_binding"] = eps
        del out["I5_double_binding_step"]
    first_rescued = {}
    for v, ser in vic_series.items():
        for t, r in ser:
            if r[4] == "rescued":
                first_rescued[v] = t
                break
    for v, t in first_rescued.items():
        pk = [p for p in pickups.get(v, []) if p[0] <= t]
        if not pk:
            out["I4_rescued_without_pickup"].append([t, v])
            continue
        for p in pk:
            s, ff, ffc, vprev, vnow, tgt = p
            if tuple(ffc) != tuple(vprev or (None, None)) and tuple(ffc) != tuple(vnow or (None, None)):
                out["I4_pickup_not_colocated"].append([s, v, ff, ffc, vprev, vnow, tgt])
    info["pickups"] = sum(len(v) for v in pickups.values())
    info["rescued_victims"] = len(first_rescued)
    # final: unresolved victim bound to two units
    last_ff = d["rows_ff"][-1] if d["rows_ff"] else []
    last_v = {r[0]: r for r in (d["rows_vic"][-1] if d["rows_vic"] else [])}
    fb = collections.defaultdict(list)
    for r in last_ff:
        if r[8] and not r[6] and (r[4] or r[5]):
            fb[r[8]].append(r[0])
    for vid, ffs in fb.items():
        vs = (last_v.get(vid) or [None] * 5)[4]
        if len(ffs) > 1 and vs not in ("rescued", "dead"):
            out["I5_end_unresolved_double"].append([vid, vs, ffs])
    # ---- I3 status vocabulary + monotonicity + consistency
    for v, ser in vic_series.items():
        seen_rescued = seen_dead = False
        for t, r in ser:
            vs = r[4]
            if vs not in ACTIVE_VICTIM + TERMINAL:
                out["I3_unknown_status"].append([t, v, vs])
            if seen_rescued and vs != "rescued":
                out["I3_rescued_reverted"].append([t, v, vs])
            if seen_dead and vs != "dead":
                out["I3_dead_reverted"].append([t, v, vs])
            seen_rescued = seen_rescued or vs == "rescued"
            seen_dead = seen_dead or vs == "dead"
            if bool(r[9]) != (vs == "rescued"):
                out["I3_rescued_flag_mismatch"].append([t, v, vs, r[9]])
        t, r = ser[-1]
        if r[3] != r[4]:
            out["I3_marker_vs_managed_end"].append([v, r[3], r[4]])
    # ---- I8 diagnostic tags
    for tag in ALARM_TAGS:
        if info["tags"].get(tag):
            out["I8_tag:" + tag].append([info["tags"][tag]])
    if int(info["tags"].get("Rescue Complete", 0)) != info["rescued_victims"]:
        out["I8_rescue_complete_vs_rescued"].append([info["tags"].get("Rescue Complete", 0), info["rescued_victims"]])
    # ---- decision variety (Part 2 support)
    dec = d["rows_dec"]
    var = {}
    for key in ("m", "r", "ra", "f", "fa", "mode"):
        var[key] = collections.Counter(str(x.get(key)) for x in dec)
    pfam = collections.Counter()
    for x in dec:
        for uid, oid in (x.get("p") or {}).items():
            fam = oid.rsplit("_", 2)[0] if oid.startswith("explore_unknown_region") else oid.split("_" + uid)[0]
            pfam[fam] += 1
    var["path_families"] = pfam
    roles = collections.Counter()
    switches = 0
    prev = None
    for row in d["rows_uav"]:
        cur = {r[0]: r[3] for r in row}
        if prev is not None:
            switches += sum(1 for k in cur if prev.get(k) != cur[k])
        prev = cur
    info["role_switches"] = switches
    info["variety"] = {k: dict(v.most_common(12)) for k, v in var.items()}
    return out, info


def main():
    args = sys.argv[1:]
    queue = args[0]
    stuck_n = int(args[args.index("--stuck") + 1]) if "--stuck" in args else 20
    win = int(args[args.index("--win") + 1]) if "--win" in args else 30
    outp = args[args.index("--out") + 1] if "--out" in args else None
    lines = []
    agg = collections.Counter()
    runs_with = collections.defaultdict(list)
    names = [json.loads(l)["name"] for l in open(queue, encoding="utf-8") if l.strip()]
    detail = {}
    for name in names:
        jp = os.path.join(REPO, "outputs", "_sd_%s.json" % name)
        if not os.path.exists(jp):
            lines.append("%-20s MISSING" % name)
            continue
        d = json.load(open(jp, encoding="utf-8"))
        out, info = analyze(name, d, stuck_n, win)
        ev = info["eval"]
        lines.append("%-20s %s wind=%-5s seed=%s %s GPM=%s steps=%d crashed=%s | resc=%s dead=%s unr=%s cand=%s ffd=%s burnt=%s term=%s | pickups=%d switches=%d | %s" % (
            name, d["scenario"], d["wind"], d["seed"], ev.get("scenario"), d["effective"].get("global_planner_mode"),
            info["steps"], (info["crashed"] or {}).get("type"), ev.get("rescued"), ev.get("dead"), ev.get("unreachable"),
            ev.get("candidate"), ev.get("firefighter_deaths"), ev.get("burnt_cells"), ev.get("terminal_step"),
            info["pickups"], info["role_switches"],
            " ".join("%s=%d" % (k, len(v)) for k, v in sorted(out.items())) or "no violations"))
        for k, v in out.items():
            agg[k] += len(v)
            runs_with[k].append(name)
        detail[name] = (out, info)
    lines.append("")
    lines.append("AGGREGATE (episodes / rows, runs):")
    for k in sorted(agg):
        lines.append("  %-40s %5d  in %d runs: %s" % (k, agg[k], len(runs_with[k]), ",".join(runs_with[k])))
    lines.append("")
    lines.append("DETAIL (first 12 rows per class per run):")
    for name, (out, info) in detail.items():
        if not out:
            continue
        lines.append("== %s  tags=%s" % (name, info["tags"]))
        for k in sorted(out):
            for row in out[k][:12]:
                lines.append("   %-36s %s" % (k, json.dumps(row)))
    lines.append("")
    lines.append("DECISION VARIETY (Part 2 support):")
    for name, (out, info) in detail.items():
        lines.append("== %s" % name)
        for k, v in info["variety"].items():
            lines.append("   %-14s %s" % (k, json.dumps(v)[:400]))
    text = "\n".join(lines)
    if outp:
        with open(outp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
