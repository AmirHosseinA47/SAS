"""sysdebug round (2026-09-28): invariant-only smoke probe. DIAGNOSIS ONLY.

Mirrors evaluate_scenarios._run_seed statement for statement - the params come from
evaluate_scenarios._scenario_params itself (so --scenario/--uavs/--victims/
--firefighters/--fire-trackers/--victim-searchers mean exactly what they mean on the
evaluate_scenarios CLI), then the same seeding order, apply_scenario_config,
model.debug_log = False, stdout redirected, and the per-step get_dashboard_state()
poll for the terminal step. Everything on top is a READ-ONLY observer: pure
attribute reads after model.step() returns, no RNG draw, no mutation.

--set KEY=VALUE adds an apply_scenario_config parameter, parsed exactly like
outputs/_ffr_harness.py _parse_value (bool/None/int/float/str).

Recorded per step (compact rows; the analyzer outputs/_sd_analyze.py derives every
Part 5 invariant from them, so thresholds can be changed without re-running):
  uav  : [uid, x, y, role, battery, rtb_active, rtb_docked, rtb_target_berth, exec_action]
  ff   : [ffid, x, y, status, assigned, exiting, dead, off_grid, bound_vid, target_pos,
          rescue_completed, exit_target]
  vic  : [vid, x, y, marker_status, managed_status, managed_ff_id, rescue_assigned,
          unreachable, cancelled, rescued_flag]
  dec  : mission / rescue / fail-safe selected option ids, rescue_action, fail-safe mode
         and reasons, per-UAV path-decision option ids
  trig : analyzer trigger counts by type for the step
Inline (every step, recorded only on violation):
  grid consistency (a scheduled non-Fire agent whose pos cell does not hold it; a
  non-Fire agent on the grid that is not in the schedule), depot cells burning /
  burnt / has_burned, UAV off-grid or out of bounds, victim-count drift.
Captured stdout: every bracketed diagnostic tag counted; the text is saved alongside.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import hashlib
import io as _io
import json
import os
import random
import re
import subprocess
import sys
import time
import traceback
import warnings


def _parse_value(raw: str):
    text = str(raw).strip()
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _sha(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return "missing"


TAG_RE = re.compile(r"^\s*\[([A-Za-z][A-Za-z0-9 _:/-]*)\]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=r"E:\Projects\SAS")
    ap.add_argument("--scenario", default="D", choices=["A", "B", "C", "D"])
    ap.add_argument("--wind", default="east", choices=["north", "south", "east", "west"])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--steps", type=int, default=360)
    ap.add_argument("--uavs", type=int, default=None)
    ap.add_argument("--victims", type=int, default=None)
    ap.add_argument("--firefighters", type=int, default=None)
    ap.add_argument("--fire-trackers", type=int, default=None, dest="fire_trackers")
    ap.add_argument("--victim-searchers", type=int, default=None, dest="victim_searchers")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")

    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import evaluate_scenarios as es  # noqa: E402
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
    from wildfire_model import WildFireModel  # noqa: E402
    from serve_dashboard import _build_evaluation  # noqa: E402

    for mod in (am, cfv, wf, es):
        path = os.path.abspath(getattr(mod, "__file__", ""))
        if not path.lower().startswith(repo.lower()):
            print("IMPORT MISMATCH: %s from %s" % (mod.__name__, path), file=sys.stderr)
            return 3

    ns = argparse.Namespace(
        scenario=args.scenario, wind=args.wind, uavs=args.uavs, victims=args.victims,
        firefighters=args.firefighters, fire_trackers=args.fire_trackers,
        victim_searchers=args.victim_searchers, batch_size=300, fire_spread=0.75,
        ff_absence_min=None, ff_absence_max=None,
    )
    params = es._scenario_params(ns)
    extra = {}
    for item in args.set:
        if "=" not in item:
            print("bad --set %r" % item, file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        extra[k.strip()] = _parse_value(v)
    params.update(extra)

    try:
        head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        head = "unknown"
    src_sha = {name: _sha(os.path.join(repo, name)) for name in (
        "agents.py", "wildfire_model.py", "common_fixed_variables.py", "serve_dashboard.py",
        "evaluate_scenarios.py",
        os.path.join("src_extension", "execution", "uav_executor.py"),
        os.path.join("src_extension", "adaptation", "local_adaptation_generator.py"),
        os.path.join("src_extension", "adaptation", "global_adaptation_generator.py"),
        os.path.join("src_extension", "planning", "utility_evaluation.py"),
        os.path.join("src_extension", "planning", "rescue_planner.py"),
        os.path.join("src_extension", "planning", "fail_safe_planner.py"),
    )}

    # ---- run: byte-for-byte the evaluate_scenarios._run_seed sequence ----------
    rng = random.Random(args.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    effective = {}
    for name in ("global_planner_mode", "base_station_mode", "ff_exit_leg_mode",
                 "base_station_depots", "base_station_return_mechanism"):
        fn = getattr(am, name, None)
        try:
            effective[name] = fn() if callable(fn) else "ABSENT"
        except Exception as exc:  # recorded, not swallowed
            effective[name] = "ERR %s" % type(exc).__name__

    H = int(getattr(cfv, "HEIGHT", 50))
    W = int(getattr(cfv, "WIDTH", 50))

    def xy(pos):
        if pos is None:
            return (None, None)
        return (int(pos[0]), int(pos[1]))

    def vid_of(model, agent):
        if agent is None:
            return None
        v = getattr(agent, "victim_id", None)
        if v is not None:
            return str(v)
        for k, m in (getattr(model, "victim_marker_agents", {}) or {}).items():
            if m is agent:
                return str(k)
        return "?"

    rows_uav, rows_ff, rows_vic, rows_dec, rows_trig = [], [], [], [], []
    viol = collections.defaultdict(list)   # inline invariant violations
    terminal_step = None
    step = 0
    crashed = None
    t0 = time.perf_counter()
    buf = _io.StringIO()
    caught_warnings = []
    evaluation = None
    model = None
    depot_cells = ()
    with warnings.catch_warnings(record=True) as wlist:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(buf):
            try:
                model = WildFireModel()
                model.debug_log = False
                station = getattr(model, "base_station", None)
                depot_cells = tuple(sorted(station.get("cells") or ())) if station else ()
                n_vict = len(getattr(model, "managed_victims", {}) or {})
                for _ in range(args.steps):
                    model.step()
                    step += 1
                    if terminal_step is None:
                        panel = model.get_dashboard_state()
                        mission = panel.get("mission_status", {}) or {}
                        if mission.get("all_victims_terminal"):
                            terminal_step = step
                    # ---------------- observers only below this line -------------
                    exec_r = getattr(model, "latest_execution_result", None) or {}
                    local = exec_r.get("local", {}) if isinstance(exec_r, dict) else {}
                    ures = (local.get("uav_results") or {}) if isinstance(local, dict) else {}
                    urow = []
                    sched_nonfire = {}
                    for a in model.schedule.agents:
                        tn = type(a).__name__
                        if tn == "Fire":
                            continue
                        sched_nonfire[id(a)] = a
                        if tn != "UAV":
                            continue
                        uid = str(a.unique_id)
                        x, y = xy(getattr(a, "pos", None))
                        if x is None or not (0 <= x < H and 0 <= y < W):
                            viol["uav_offgrid"].append([step, uid, x, y])
                        r = ures.get(uid) if isinstance(ures, dict) else None
                        act = str(r.get("action") or "") if isinstance(r, dict) else ""
                        tb = getattr(a, "rtb_target_berth", None)
                        urow.append([uid, x, y, str(getattr(a, "current_role", "") or ""),
                                     round(float(getattr(a, "battery_level", 0.0) or 0.0), 3),
                                     int(bool(getattr(a, "rtb_active", False))),
                                     int(bool(getattr(a, "rtb_docked", False))),
                                     (list(tb) if tb is not None else None), act])
                    rows_uav.append(urow)
                    frow = []
                    for ff_id, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                        x, y = xy(getattr(m, "pos", None))
                        if x is not None and not (0 <= x < H and 0 <= y < W):
                            viol["ff_out_of_bounds"].append([step, str(ff_id), x, y])
                        tp = getattr(m, "target_pos", None)
                        et = getattr(m, "exit_target", None)
                        frow.append([str(ff_id), x, y, str(getattr(m, "status", "") or ""),
                                     int(bool(getattr(m, "assigned", False))),
                                     int(bool(getattr(m, "exiting", False))),
                                     int(bool(getattr(m, "dead", False))),
                                     int(bool(getattr(m, "off_grid", False))),
                                     vid_of(model, getattr(m, "rescued_victim", None)),
                                     (list(xy(tp)) if tp is not None else None),
                                     int(bool(getattr(m, "rescue_completed", False))),
                                     (list(xy(et)) if et is not None else None)])
                    rows_ff.append(frow)
                    vrow = []
                    mv = getattr(model, "managed_victims", {}) or {}
                    if len(mv) != n_vict:
                        viol["victim_count_drift"].append([step, n_vict, len(mv)])
                    for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items():
                        x, y = xy(getattr(m, "pos", None))
                        st = mv.get(vid)
                        vrow.append([str(vid), x, y, str(getattr(m, "status", "") or ""),
                                     str(getattr(st, "status", "") or "") if st is not None else None,
                                     (str(getattr(st, "firefighter_id", "") or "") if st is not None else None),
                                     int(bool(getattr(st, "rescue_assigned", False))) if st is not None else None,
                                     int(bool(getattr(st, "unreachable", False))) if st is not None else None,
                                     int(bool(getattr(st, "cancelled", False))) if st is not None else None,
                                     int(bool(getattr(st, "rescued", False))) if st is not None else None])
                    rows_vic.append(vrow)
                    # grid consistency: every scheduled non-Fire agent with a pos is in
                    # that cell; every non-Fire agent on the grid is scheduled.
                    for a in sched_nonfire.values():
                        pos = getattr(a, "pos", None)
                        if pos is None:
                            continue
                        try:
                            here = model.grid.get_cell_list_contents([pos])
                        except Exception as exc:
                            viol["grid_lookup_error"].append([step, type(a).__name__, str(a.unique_id), repr(exc)[:80]])
                            continue
                        if not any(o is a for o in here):
                            viol["pos_not_in_cell"].append([step, type(a).__name__, str(a.unique_id), list(xy(pos))])
                    try:
                        gridcells = model.grid._grid  # mesa 1.2.1: list[x][y] of lists (read only)
                        for gx in range(len(gridcells)):
                            col = gridcells[gx]
                            for gy in range(len(col)):
                                for o in col[gy]:
                                    if type(o).__name__ == "Fire":
                                        continue
                                    if id(o) not in sched_nonfire:
                                        viol["ghost_on_grid"].append([step, type(o).__name__, str(getattr(o, "unique_id", "?")), gx, gy])
                    except Exception as exc:
                        viol["grid_scan_error"].append([step, repr(exc)[:80]])
                    # depot cells never burn
                    for cell in depot_cells:
                        for o in model.grid.get_cell_list_contents([cell]):
                            if type(o).__name__ != "Fire":
                                continue
                            if getattr(o, "burning", False) or getattr(o, "burnt", False) or getattr(o, "has_burned", False):
                                viol["depot_cell_burn"].append([step, list(cell), int(bool(o.burning)), int(bool(o.burnt))])
                    # decisions
                    pr = getattr(model, "latest_planning_result", None)
                    drow = {}
                    if isinstance(pr, dict):
                        md = pr.get("mission_decision")
                        rd = pr.get("rescue_decision")
                        fd = pr.get("fail_safe_decision")
                        drow["m"] = str(getattr(md, "selected_option_id", "") or "")
                        drow["r"] = str(getattr(rd, "selected_option_id", "") or "")
                        drow["ra"] = str(getattr(rd, "rescue_action", "") or "")
                        drow["rv"] = str(getattr(rd, "victim_id", "") or "")
                        drow["f"] = str(getattr(fd, "selected_option_id", "") or "")
                        drow["fa"] = str(getattr(fd, "fail_safe_action", "") or "")
                        drow["fs"] = int(bool(getattr(fd, "search_mode_active", False)))
                        pd = pr.get("path_decisions") or {}
                        drow["p"] = {str(k): str(getattr(v, "selected_option_id", "") or "") for k, v in pd.items()}
                    fs = getattr(model, "latest_failsafe_state", None)
                    if fs is not None:
                        drow["mode"] = str(getattr(getattr(fs, "mode", None), "value", getattr(fs, "mode", "")))
                        drow["why"] = sorted(str(getattr(r, "value", r)) for r in (getattr(fs, "active_reasons", ()) or ()))
                    rows_dec.append(drow)
                    snap = getattr(model, "latest_analysis_snapshot", None)
                    tc = collections.Counter()
                    for t in (getattr(snap, "all_triggers", ()) or ()):
                        tc[str(getattr(t, "trigger_type", "?"))] += 1
                    rows_trig.append(dict(tc))
                evaluation = _build_evaluation(model, terminal_step, step, params)
            except BaseException as exc:  # a crash is a finding: record it, never hide it
                crashed = {"step": step, "type": type(exc).__name__, "msg": str(exc)[:500],
                           "tb": traceback.format_exc()[-4000:]}
                if model is not None:
                    try:
                        evaluation = _build_evaluation(model, terminal_step, step, params)
                    except Exception:
                        evaluation = None
        caught_warnings = [("%s: %s" % (w.category.__name__, str(w.message)[:200])) for w in wlist]
    wall = time.perf_counter() - t0
    stdout_text = buf.getvalue()
    tags = collections.Counter()
    for line in stdout_text.splitlines():
        m = TAG_RE.match(line)
        if m:
            tags[m.group(1)] += 1

    depots_meta = None
    if model is not None and getattr(model, "base_station", None):
        st = model.base_station
        depots_meta = {"cells": [list(c) for c in depot_cells],
                       "uav_berths": [list(b) for b in st.get("uav_berths") or ()],
                       "ff_berths": [list(b) for b in st.get("firefighter_berths") or ()],
                       "fireproof_cleared": getattr(model, "base_station_fireproof_cleared", None)}
    out = {
        "probe": "sd_probe v1",
        "tag": args.tag, "repo": repo, "head": head, "src_sha": src_sha,
        "python": sys.version.split()[0],
        "mesa": getattr(sys.modules.get("mesa"), "__version__", "?"),
        "scenario": args.scenario, "wind": args.wind, "seed": args.seed, "steps": args.steps,
        "argv": sys.argv[1:], "params": params, "extra_params": extra, "effective": effective,
        "grid": [H, W], "depots": depots_meta,
        "eval": evaluation, "terminal_step": terminal_step, "steps_done": step,
        "crashed": crashed, "wall_s": round(wall, 1),
        "inline_violations": {k: v[:200] for k, v in viol.items()},
        "inline_violation_counts": {k: len(v) for k, v in viol.items()},
        "stdout_tags": dict(tags), "warnings": caught_warnings[:50],
        "warning_count": len(caught_warnings),
        "stdout_sha": hashlib.sha256(stdout_text.encode("utf-8", "replace")).hexdigest(),
        "rows_uav": rows_uav, "rows_ff": rows_ff, "rows_vic": rows_vic,
        "rows_dec": rows_dec, "rows_trig": rows_trig,
        "complete": crashed is None and step == args.steps,
    }
    stdout_path = args.out[:-5] + ".stdout.txt" if args.out.endswith(".json") else args.out + ".stdout.txt"
    with open(stdout_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(stdout_text)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(tmp, args.out)
    ev = evaluation or {}
    print("SD_DONE %s seed=%d steps=%d crashed=%s rescued=%s dead=%s unreach=%s cand=%s ffdead=%s viol=%s wall=%.0fs" % (
        args.tag, args.seed, step, (crashed or {}).get("type"), ev.get("rescued"), ev.get("dead"),
        ev.get("unreachable"), ev.get("candidate"), ev.get("firefighter_deaths"),
        dict(out["inline_violation_counts"]), wall))
    return 0 if crashed is None else 4


if __name__ == "__main__":
    raise SystemExit(main())
