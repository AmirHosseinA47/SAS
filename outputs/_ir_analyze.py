"""Analyse _sb_probe.py output: classify firefighter deaths and quantify the
idle/standby retreat mechanism. Read-only."""
from __future__ import annotations
import argparse, collections, json, os, sys

MAXC = 49  # MultiGrid(50, 50, torus=False)

# Wind label -> the wall the fire front travels TOWARD.
# wind_vector_from_direction: north (0,+1) south (0,-1) east (+1,0) west (-1,0)
# on (pos[0], pos[1]) with pos[0] bounded by HEIGHT and pos[1] by WIDTH.
DOWNWIND = {
    "east":  ("axis0_max", lambda p: p[0] == MAXC),
    "west":  ("axis0_min", lambda p: p[0] == 0),
    "north": ("axis1_max", lambda p: p[1] == MAXC),
    "south": ("axis1_min", lambda p: p[1] == 0),
}


def on_boundary(p):
    return p is not None and (p[0] in (0, MAXC) or p[1] in (0, MAXC))


def wall_dist(p):
    return min(p[0], MAXC - p[0], p[1], MAXC - p[1])


def load(paths):
    runs = []
    for p in paths:
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            sys.stderr.write("MISSING/EMPTY: %s\n" % p)
            continue
        with open(p) as f:
            runs.append((p, json.load(f)))
    return runs


def classify(d):
    """Yield one record per death with window-based classification."""
    wind = d["wind"]
    dw_name, dw_test = DOWNWIND[wind]
    tr = collections.defaultdict(list)
    for r in d["fftrace"]:
        tr[(r["seed"], r["ff"])].append(r)
    for k in tr:
        tr[k].sort(key=lambda r: r["step"])

    life = collections.defaultdict(list)
    for e in d["lifecycle"]:
        life[(e["seed"], e["ff"])].append(e)

    surv = collections.defaultdict(list)
    for s in d["surv"]:
        surv[(s["seed"], s["ff"])].append(s)

    ign = d["ignition"]
    out = []
    for dth in d["deaths"]:
        key = (dth["seed"], dth["ff"])
        rows = [r for r in tr[key] if r["step"] < dth["step"]]
        rows.sort(key=lambda r: r["step"])
        prev = rows[-1] if rows else None

        def engaged(r):
            return bool(r.get("exiting")) or (r.get("target") is not None)

        # terminal idle run: consecutive non-engaged steps immediately before death
        idle_run = 0
        idle_start = None
        for r in reversed(rows):
            if engaged(r):
                break
            idle_run += 1
            idle_start = r["step"]

        # naive classification, exactly as the prior investigation measured it:
        # target_pos at the death-step snapshot
        naive_idle = (dth.get("target") is None) and not dth.get("exiting")

        # same-step lifecycle events (the artifact that corrupts the naive measure)
        same_step = [e for e in life[key] if e["step"] == dth["step"]]
        unassign_same_step = any(e["kind"] == "unassign" for e in same_step)

        # what was it doing just before it died?
        if prev is None:
            cls = "unknown"
        elif prev.get("exiting"):
            cls = "exiting"
        elif prev.get("target") is not None:
            cls = "in_transit"
        else:
            cls = "idle"

        # how did it become idle (last engagement-ending event)?
        cause = "never_engaged"
        cause_step = None
        if idle_start is not None:
            evs = [e for e in life[key] if e["step"] <= idle_start]
            evs.sort(key=lambda e: e["step"])
            for e in reversed(evs):
                if e["kind"] == "recycle":
                    cause, cause_step = "recycle_after_rescue", e["step"]
                    break
                if e["kind"] == "unassign" and e.get("ok"):
                    cause = "unassign:" + (e.get("reason") or "?")
                    cause_step = e["step"]
                    break
                if e["kind"] == "assign" and e.get("ok"):
                    cause, cause_step = "assigned_then_lost_target", e["step"]
                    break
            if not any(e["kind"] == "assign" and e.get("ok") for e in life[key]):
                cause = "never_assigned"

        pos = dth["pos"]
        ikey = "%d|%d,%d" % (dth["seed"], pos[0], pos[1]) if pos else None
        fire_arrival = ign.get(ikey) if ikey else None

        # survival-move forensics over the terminal idle run
        sruns = [s for s in surv[key]
                 if idle_start is not None and idle_start <= s["step"] <= dth["step"]]
        stalled_noop = [s for s in sruns if s.get("stalled_pre") and not s.get("moved")]
        wasted = [s for s in stalled_noop if (s.get("n_free") or 0) > 0]
        wasted_better = [s for s in stalled_noop if s.get("strictly_better_exists")]

        # how long was the stall latch set before death?
        stalled_steps = 0
        for r in reversed(rows):
            if not r.get("stalled"):
                break
            stalled_steps += 1

        # the last _survival_move call at or before the death step: was the unit
        # standing in fire, already latched, with an escape cell available?
        pre_calls = [s for s in surv[key] if s["step"] <= dth["step"]]
        pre_calls.sort(key=lambda s: s["step"])
        last_surv = pre_calls[-1] if pre_calls else None
        lethal = None
        if last_surv is not None:
            lethal = {
                "step": last_surv["step"],
                "idle": last_surv.get("idle"),
                "on_fire": last_surv.get("on_fire"),
                "stalled_pre": last_surv.get("stalled_pre"),
                "moved": last_surv.get("moved"),
                "n_inbounds": last_surv.get("n_inbounds"),
                "n_free": last_surv.get("n_free"),
                "n_safe": last_surv.get("n_safe"),
                "cur_dist": last_surv.get("cur_dist"),
                "best_free_dist": last_surv.get("best_free_dist"),
                "excl_fire": last_surv.get("excl_fire"),
                "excl_lastcell": last_surv.get("excl_lastcell"),
                "excl_leash": last_surv.get("excl_leash"),
                "n_candidates": last_surv.get("n_candidates"),
            }
            lethal["burned_with_escape_available"] = bool(
                (not last_surv.get("moved"))
                and (last_surv.get("n_free") or 0) > 0
            )
            lethal["burned_latched_with_escape"] = bool(
                last_surv.get("stalled_pre")
                and (not last_surv.get("moved"))
                and (last_surv.get("n_free") or 0) > 0
            )

        out.append({
            "wind": wind, "roles": d["roles"], "seed": dth["seed"],
            "ff": dth["ff"], "step": dth["step"], "pos": pos,
            "cls": cls, "naive_idle": naive_idle,
            "unassign_same_step": unassign_same_step,
            "misclassified_by_naive": bool(naive_idle and cls != "idle"),
            "idle_run": idle_run, "idle_start": idle_start,
            "idle_cause": cause, "idle_cause_step": cause_step,
            "on_boundary": on_boundary(pos),
            "wall_dist": wall_dist(pos) if pos else None,
            "on_downwind_wall": bool(dw_test(pos)) if pos else None,
            "downwind_wall": dw_name,
            "fire_arrival_step": fire_arrival,
            "idle_to_fire": (None if (fire_arrival is None or idle_start is None)
                             else fire_arrival - idle_start),
            "idle_to_death": (None if idle_start is None else dth["step"] - idle_start),
            "stalled_at_death": dth.get("stalled"),
            "stalled_steps_before_death": stalled_steps,
            "surv_calls_in_idle_run": len(sruns),
            "stalled_noop_calls": len(stalled_noop),
            "noop_with_free_neighbour": len(wasted),
            "noop_with_better_neighbour": len(wasted_better),
            "cat_at_death": dth.get("cat"),
            "lethal_moment": lethal,
        })
    return out


def surv_stats(d):
    """Aggregate _survival_move behaviour, idle units only."""
    c = collections.Counter()
    for s in d["surv"]:
        if not s.get("idle"):
            c["nonidle_calls"] += 1
            continue
        c["idle_calls"] += 1
        if s.get("stalled_pre"):
            c["idle_calls_already_latched"] += 1
            if not s.get("moved"):
                c["latched_noop"] += 1
                if (s.get("n_free") or 0) > 0:
                    c["latched_noop_but_free_cell_existed"] += 1
                if s.get("strictly_better_exists"):
                    c["latched_noop_but_better_cell_existed"] += 1
        else:
            if s.get("moved"):
                c["unlatched_moved"] += 1
            else:
                c["unlatched_noop"] += 1
                if (s.get("n_free") or 0) > 0:
                    c["unlatched_noop_but_free_cell_existed"] += 1
        if s.get("stalled_post") and not s.get("stalled_pre"):
            c["latch_set_this_call"] += 1
            if s.get("moved"):
                c["latch_set_while_still_moving"] += 1
            if (s.get("n_free") or 0) > 0:
                c["latch_set_while_free_cell_existed"] += 1
            if s.get("strictly_better_exists"):
                c["latch_set_while_better_cell_existed"] += 1
        if s.get("stalled_pre") and not s.get("stalled_post"):
            c["latch_cleared_this_call"] += 1
        # candidate-filter attribution when the real filter chain emptied
        if s.get("n_candidates") == 0:
            c["zero_candidates"] += 1
            if (s.get("n_free") or 0) > 0:
                c["zero_candidates_despite_free_cell"] += 1
                if s.get("excl_lastcell"):
                    c["zero_cand_blamed_lastcell"] += 1
                if s.get("excl_leash"):
                    c["zero_cand_blamed_leash"] += 1
        if (s.get("excl_leash") or 0) > 0:
            c["calls_with_leash_exclusion"] += 1
        if (s.get("excl_lastcell") or 0) > 0:
            c["calls_with_lastcell_exclusion"] += 1
        if (s.get("n_free") or 0) == 0:
            c["truly_enclosed_all_neighbours_burning"] += 1
        if (s.get("n_inbounds") or 0) < 4:
            c["at_grid_edge"] += 1
    return dict(c)


def idle_posture(d):
    """Where do idle firefighters actually sit, and does it hug the boundary?"""
    wind = d["wind"]
    dw_name, dw_test = DOWNWIND[wind]
    c = collections.Counter()
    walls = collections.Counter()
    for r in d["fftrace"]:
        if r.get("dead") or r.get("pos") is None:
            continue
        if r.get("exiting") or r.get("target") is not None:
            c["engaged_steps"] += 1
            continue
        c["idle_steps"] += 1
        p = r["pos"]
        if on_boundary(p):
            c["idle_steps_on_boundary"] += 1
            if dw_test(p):
                c["idle_steps_on_downwind_wall"] += 1
        walls[wall_dist(p)] += 1
        if r.get("stalled"):
            c["idle_steps_latched"] += 1
    return {"counts": dict(c), "wall_dist_hist": dict(sorted(walls.items())),
            "downwind_wall": dw_name}


def recycle_stats(d):
    wind = d["wind"]
    dw_name, dw_test = DOWNWIND[wind]
    rows = [e for e in d["lifecycle"] if e["kind"] == "recycle"]
    n = len(rows)
    onb = sum(1 for e in rows if on_boundary(e.get("pos_after")))
    dwn = sum(1 for e in rows if e.get("pos_after") and dw_test(e["pos_after"]))
    return {"n_recycles": n, "recycled_onto_boundary": onb,
            "recycled_onto_downwind_wall": dwn, "downwind_wall": dw_name,
            "positions": [e.get("pos_after") for e in rows]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json-out", default="")
    a = ap.parse_args()
    runs = load(a.files)
    all_deaths = []
    report = {}
    for path, d in runs:
        tag = os.path.basename(path)
        deaths = classify(d)
        all_deaths.extend(deaths)
        report[tag] = {
            "wind": d["wind"], "roles": d["roles"], "seeds": d["seeds"],
            "steps": d["steps"], "params": d["params"],
            "n_deaths": len(d["deaths"]),
            "deaths": deaths,
            "surv_stats": surv_stats(d),
            "idle_posture": idle_posture(d),
            "recycle": recycle_stats(d),
        }

    n = len(all_deaths)
    agg = {
        "total_deaths": n,
        "by_class": dict(collections.Counter(x["cls"] for x in all_deaths)),
        "naive_idle_count": sum(1 for x in all_deaths if x["naive_idle"]),
        "naive_misclassified": sum(1 for x in all_deaths if x["misclassified_by_naive"]),
        "unassign_same_step": sum(1 for x in all_deaths if x["unassign_same_step"]),
        "on_boundary": sum(1 for x in all_deaths if x["on_boundary"]),
        "on_downwind_wall": sum(1 for x in all_deaths if x["on_downwind_wall"]),
        "idle_deaths_on_boundary": sum(1 for x in all_deaths
                                       if x["cls"] == "idle" and x["on_boundary"]),
        "idle_causes": dict(collections.Counter(
            x["idle_cause"] for x in all_deaths if x["cls"] == "idle")),
        "stalled_at_death": sum(1 for x in all_deaths if x["stalled_at_death"]),
        "idle_deaths_stalled": sum(1 for x in all_deaths
                                   if x["cls"] == "idle" and x["stalled_at_death"]),
        "idle_run_lengths": sorted(x["idle_run"] for x in all_deaths if x["cls"] == "idle"),
        "idle_to_death": sorted(x["idle_to_death"] for x in all_deaths
                                if x["cls"] == "idle" and x["idle_to_death"] is not None),
        "noop_with_free_neighbour_total": sum(x["noop_with_free_neighbour"]
                                              for x in all_deaths),
        "burned_with_escape_available": sum(
            1 for x in all_deaths
            if (x.get("lethal_moment") or {}).get("burned_with_escape_available")),
        "burned_latched_with_escape": sum(
            1 for x in all_deaths
            if (x.get("lethal_moment") or {}).get("burned_latched_with_escape")),
        "no_surv_call_before_death": sum(
            1 for x in all_deaths if x.get("lethal_moment") is None),
        "idle_run_ge2": sum(1 for x in all_deaths
                            if x["cls"] == "idle" and x["idle_run"] >= 2),
        "idle_run_ge5": sum(1 for x in all_deaths
                            if x["cls"] == "idle" and x["idle_run"] >= 5),
        "idle_run_ge20": sum(1 for x in all_deaths
                             if x["cls"] == "idle" and x["idle_run"] >= 20),
    }
    report["_aggregate"] = agg
    txt = json.dumps(report, indent=1, default=str)
    if a.json_out:
        with open(a.json_out, "w") as f:
            f.write(txt)
    print(json.dumps(agg, indent=1, default=str))
    for tag in sorted(k for k in report if k != "_aggregate"):
        r = report[tag]
        print("\n===== %s (wind=%s roles=%s) deaths=%d =====" % (tag, r["wind"], r["roles"], r["n_deaths"]))
        print(" surv_stats:", json.dumps(r["surv_stats"], indent=1))
        print(" idle_posture:", json.dumps(r["idle_posture"], indent=1))
        print(" recycle:", json.dumps(r["recycle"], indent=1))
        for x in r["deaths"]:
            print("  DEATH", json.dumps(x, default=str))


main()
