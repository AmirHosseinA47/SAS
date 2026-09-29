"""fix2 Part 3 instrument: outputs/_sd_probe.py (unchanged) plus PASS-THROUGH observers.

Every hook calls the original with the original arguments, returns its result unchanged, draws from
no RNG and writes no simulation state. P3-1(a) proves it: an all-switches-0 run must be
value-identical to its recorded c08456b twin (outputs/_sd_mf1P_*) on every _sd_probe field.

usage: _mf2_probe.py -- <_sd_probe.py args ...>

Adds d["mf2"] to the probe JSON:
  uav    per step, per UAV: [uid, role, stay, moved_class, burning, smoke, fire_dist, drift_level,
         risk_status, yielded, selected_dir]  (selected_dir: the direction this step used; added for
         the item-2 follow-up - earlier runs have 10 fields)
         moved_class = moved / stay / docked_hold / nodir_hold / refused_occupied / refused_oob;
         burning = a burning Fire agent on its cell; smoke = the cell is visibility smoke-obscured or
         holds an active smoke (the harness --uav-actions definitions); fire_dist = Manhattan to the
         nearest burning cell (99 if none); yielded = the dispatcher's fail-safe yield this step.
  fleet  per step: [visible_fire_cells, belief_high_cells, fleet_fire_lost, alarms, fs_noop, named]
         named = {COLLISION_RISK|scope / DRIFT_TOO_HIGH|scope: sorted affected entity ids;
                  SEARCH_MODE_REQUIRED|scope: 'FLEET_FIRE_LOST' / 'other' per trigger, by explanation};
         alarms = {TYPE|scope: count} for COLLISION_RISK, DRIFT_TOO_HIGH, CRITICAL_LINK_UNRELIABLE,
         SEARCH_MODE_REQUIRED; fs_noop = the fail-safe decision carries no action and no search flag.
  search per step, per searcher: [uid, coverage_y_commit, north_strip_done, south_strip_done,
         west_strip_done, east_strip_done, last_wind_direction, y]
  gate   {calls, replaced, replaced_far} - the searcher hazard gate; far = the searcher's nearest
         strict fire/smoke cell more than 6 away (SEARCHER_GATE_NEAR_RANGE).
  route  {calls, replaced} - _attempt_pathfinding_toward_target returns that differ from the greedy /
         BFS step (only the 3b near-field rule changes them).
  strips {xpull|wind|dir|moved=..: n} - the coverage x-strip pull, separated from the interior
         clamp (outputs/_mf2_p1_strips.py logic).
"""
from __future__ import annotations

import collections
import copy
import json
import os
import runpy
import sys


def main() -> int:
    argv = sys.argv[1:]
    probe_args = argv[argv.index("--") + 1:]
    out_path = probe_args[probe_args.index("--out") + 1]
    repo = r"E:\Projects\SAS"
    for i, a in enumerate(probe_args):
        if a == "--repo":
            repo = probe_args[i + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402
    import src_extension.execution.uav_executor as ux  # noqa: E402

    cur = {"step": 0}
    UAV_ROWS, FLEET_ROWS, SEARCH_ROWS = [], [], []
    GATE = collections.Counter()
    ROUTE = collections.Counter()
    STRIPS = collections.Counter()
    last_move = {}

    # ---- UAV.move outcome ---------------------------------------------------------------
    omove = am.UAV.move

    def move(self):
        docked = bool(getattr(self, "rtb_docked", False))
        try:
            pipeline = bool(getattr(self.model, "_is_extension_pipeline_active", lambda: False)())
        except Exception:
            pipeline = False
        applied = bool(getattr(self, "execution_direction_applied", False))
        stay = bool(getattr(self, "execution_stay", False))
        d = int(self.selected_dir)
        mx, my = [1, 0, -1, 0], [0, -1, 0, 1]
        oob = bool(self.model.grid.out_of_bounds((self.pos[0] + mx[d], self.pos[1] + my[d])))
        moved = omove(self)
        if docked:
            cls = "docked_hold"
        elif pipeline and not applied:
            cls = "nodir_hold"
        elif moved:
            cls = "moved"
        elif stay:
            cls = "stay"
        elif oob:
            cls = "refused_oob"
        else:
            cls = "refused_occupied"
        last_move[str(self.unique_id)] = cls
        return moved

    am.UAV.move = move

    # ---- the searcher hazard gate and the pathfinding route ----------------------------------
    ogate = ux.UAVExecutor._apply_victim_searcher_hazard_gate

    def gate(self, agent, chosen_dir, action):
        r = ogate(self, agent, chosen_dir, action)
        GATE["calls"] += 1
        if r[0] != chosen_dir:
            GATE["replaced"] += 1
            pos = getattr(agent, "pos", None)
            if pos is not None and self._min_strict_hazard_distance((int(pos[0]), int(pos[1]))) > 6:
                GATE["replaced_far"] += 1
        return r

    ux.UAVExecutor._apply_victim_searcher_hazard_gate = gate

    oforced = ux.UAVExecutor._forced_progress_direction
    oroute = ux.UAVExecutor._attempt_pathfinding_toward_target
    route_ctx = {"forced": None}

    def forced(self, agent, target):
        r = oforced(self, agent, target)
        route_ctx["forced"] = r
        return r

    def route(self, agent, target, **kw):
        route_ctx["forced"] = None
        r = oroute(self, agent, target, **kw)
        if r is not None:
            ROUTE["calls"] += 1
            if route_ctx["forced"] is not None and r[0] != route_ctx["forced"]:
                ROUTE["replaced"] += 1
        return r

    ux.UAVExecutor._forced_progress_direction = forced
    ux.UAVExecutor._attempt_pathfinding_toward_target = route

    # ---- the coverage x-strip pull (outputs/_mf2_p1_strips.py) ----------------------------
    ofin = lag._finalize_coverage_target

    def fin(target, wind_state, *, x_min=None, y_min, y_max, x_max=None, ax=None, ay=None,
            fire_cells=None, smoke_cells=None, step_index=None):
        pull = None
        try:
            if target is not None and lag._coverage_mode_active(wind_state):
                ws = copy.deepcopy(wind_state)
                sxmin = lag._coverage_safe_x_min(x_min) if x_min is not None else lag.COVERAGE_INTERIOR_X_MIN
                sxmax = lag._coverage_safe_x_max(x_max) if x_max is not None else lag.COVERAGE_INTERIOR_X_MAX
                tx = max(sxmin, min(sxmax, float(target[0])))
                wind = str(ws.get("last_wind_direction") or "").strip().lower()
                if lag._active_lane_axis(ws) != "x":
                    lag._mark_x_strip_progress(ws, sxmin, sxmax)
                    east_ok = lag._allow_east_force(ws) if wind == "west" else True
                    if lag._west_sweep_pending(ws, sxmin) and ax is not None and float(ax) > sxmin + 4:
                        pull = ("west", min(tx, float(sxmin + lag.COVERAGE_SWEEP_BAND_MARGIN)) != tx)
                    elif (lag._east_sweep_pending(ws, sxmax) and east_ok and ax is not None
                          and float(ax) < sxmax - 4):
                        pull = ("east", max(tx, float(sxmax - lag.COVERAGE_SWEEP_BAND_MARGIN)) != tx)
        except Exception as exc:  # observer only
            STRIPS["HOOK_ERR %r" % (exc,)] += 1
        r = ofin(target, wind_state, x_min=x_min, y_min=y_min, y_max=y_max, x_max=x_max, ax=ax, ay=ay,
                 fire_cells=fire_cells, smoke_cells=smoke_cells, step_index=step_index)
        if pull is not None:
            wind = str(wind_state.get("last_wind_direction") or "").strip().lower() or "?"
            STRIPS["xpull|%s|%s|moved=%s" % (wind, pull[0], pull[1])] += 1
        return r

    lag._finalize_coverage_target = fin

    # ---- per-step reads after the model's step ------------------------------------------
    ostep = wf.WildFireModel.step
    ALARMS = ("COLLISION_RISK", "DRIFT_TOO_HIGH", "CRITICAL_LINK_UNRELIABLE", "SEARCH_MODE_REQUIRED")

    def step(self):
        cur["step"] += 1
        r = ostep(self)
        try:
            burning = set()
            smoke = set()
            for a in self.schedule.agents:
                if type(a).__name__ != "Fire" or a.pos is None:
                    continue
                cell = (int(a.pos[0]), int(a.pos[1]))
                if getattr(a, "burning", False):
                    burning.add(cell)
                sm = getattr(a, "smoke", None)
                act = getattr(sm, "is_smoke_active", None) if sm is not None else None
                if (callable(act) and act()) or bool(getattr(sm, "smoke", False)):
                    smoke.add(cell)
            vis = getattr(self, "visibility_model", None)
            vsm = getattr(vis, "smoke_obscured_cells", None) if vis is not None else None
            if isinstance(vsm, (set, list, tuple)):
                smoke |= {tuple(int(v) for v in c[:2]) for c in vsm}
            disp = getattr(self, "decision_dispatcher", None)
            streaks = getattr(disp, "_yield_streaks", {}) or {}
            urm = getattr(self, "uav_resource_model", None)
            row = []
            for a in sorted((x for x in self.schedule.agents if type(x) is am.UAV), key=lambda x: x.unique_id):
                uid = str(a.unique_id)
                cell = (int(a.pos[0]), int(a.pos[1])) if a.pos is not None else None
                fd = 99
                if cell is not None and burning:
                    fd = min(abs(cell[0] - bx) + abs(cell[1] - by) for bx, by in burning)
                st = (getattr(urm, "by_uav_id", {}) or {}).get(uid) if urm is not None else None
                ys = streaks.get(uid)
                row.append([uid, str(getattr(a, "current_role", "") or ""),
                            int(bool(getattr(a, "execution_stay", False))), last_move.get(uid),
                            int(cell in burning) if cell else 0, int(cell in smoke) if cell else 0, int(fd),
                            (round(float(st.drift_level), 3) if st is not None and st.drift_level is not None else None),
                            (str(st.local_risk_status) if st is not None else None),
                            int(bool(ys is not None and ys[0] == int(self.evaluation_timesteps_counter) and ys[2])),
                            int(getattr(a, "selected_dir", 0) or 0)])
            UAV_ROWS.append(row)
            visible = sum(len(getattr(lom, "visible_fire_cells", ()) or ())
                          for lom in (getattr(self, "local_observation_models", {}) or {}).values())
            belief = getattr(getattr(self, "fire_runtime_model", None), "belief", None)
            high = sum(1 for p in (belief.fire_probability_map.values() if belief is not None else ()) if p >= 0.7)
            counts = collections.Counter()
            named = collections.defaultdict(list)
            snap = getattr(self, "latest_analysis_snapshot", None)
            for t in (getattr(snap, "all_triggers", ()) or ()):
                name = str(getattr(t, "trigger_type", ""))
                if name in ALARMS:
                    sc = getattr(getattr(t, "scope", None), "value", str(getattr(t, "scope", "")))
                    counts["%s|%s" % (name, sc)] += 1
                    if name in ("COLLISION_RISK", "DRIFT_TOO_HIGH"):
                        named["%s|%s" % (name, sc)].extend(
                            str(e) for e in (getattr(t, "affected_entities", ()) or ()))
                    elif name == "SEARCH_MODE_REQUIRED":
                        named["%s|%s" % (name, sc)].append(
                            "FLEET_FIRE_LOST" if "FLEET_FIRE_LOST" in str(getattr(t, "explanation_context", ""))
                            else "other")
            pr = getattr(self, "latest_planning_result", None)
            fd_ = pr.get("fail_safe_decision") if isinstance(pr, dict) else None
            noop = int(fd_ is not None and not str(getattr(fd_, "fail_safe_action", "") or "")
                       and not bool(getattr(fd_, "search_mode_active", False)))
            FLEET_ROWS.append([int(visible), int(high), int(high > 0 and visible == 0), dict(counts), noop,
                               {k: sorted(v) for k, v in named.items()}])
            srow = []
            for a in self.schedule.agents:
                if type(a) is not am.UAV or str(getattr(a, "current_role", "")) != "victim_searcher":
                    continue
                ws = lag._wind_search_state(self, str(a.unique_id))
                srow.append([str(a.unique_id), ws.get("coverage_y_commit"), int(bool(ws.get("north_strip_done"))),
                             int(bool(ws.get("south_strip_done"))), int(bool(ws.get("west_strip_done"))),
                             int(bool(ws.get("east_strip_done"))), ws.get("last_wind_direction"),
                             int(a.pos[1]) if a.pos is not None else None])
            SEARCH_ROWS.append(srow)
        except Exception as exc:  # observer only - recorded, never raised into the run
            FLEET_ROWS.append(["HOOK_ERR", repr(exc)[:200]])
        return r

    wf.WildFireModel.step = step

    probe = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_probe.py"),
                           run_name="sd_probe_module")
    sys.argv = [sys.argv[0]] + probe_args
    rc = probe["main"]()
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        d["mf2"] = {"uav": UAV_ROWS, "fleet": FLEET_ROWS, "search": SEARCH_ROWS, "gate": dict(GATE),
                    "route": dict(ROUTE), "strips": dict(STRIPS), "probe": "mf2_probe v1"}
        tmp = out_path + ".hktmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("MF2_PROBE RECORD FAILED: %r" % (exc,), file=sys.stderr)
        return 5
    print("MF2_PROBE_DONE")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
