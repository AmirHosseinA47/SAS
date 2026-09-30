"""fix3a instrument: outputs/_mf2_probe.py (unchanged, which wraps outputs/_sd_probe.py) plus
PASS-THROUGH observers of the victim searcher's routing. Every hook calls the original with the
original arguments and returns its result unchanged; it draws from no RNG and writes no simulation
state (it reads a few wind-state keys and COPIES them). Proof obligation: a run of this probe must be
value-identical, on every _sd_probe / mf2 field, to the same configuration run without it.

usage: _fx3_probe.py [--hazard] -- <_sd_probe.py args ...>   (exactly like _mf2_probe.py)
  --hazard  also record ["H", fire_d, smoke_d, [[fire_d, smoke_d] per neighbour], near cells] after
            every route call (the strict burning / smoke cells within 8, [x, y, 0 fire | 1 smoke])

Adds d["fx3"] to the probe JSON:
  ev   {step: {uid: [event, ...]}} for victim searchers only, in call order. Events:
       ["x", pos, option_id, next_action, fs_search, ctx_flags]          execute() entry
       ["X", selected_dir, action]                                        execute() result
       ["T", target]                  _wind_aware_victim_search_target result
       ["R", target, label, result, method]   _attempt_pathfinding_toward_target
       ["F", target, result, method, blocked_n, blocked_next]  _forced_progress_direction
                                          (blocked_next: which of the 4 neighbours the pocket
                                           escape blocks, from a copy of the wind state)
       ["C", target, kind, result]    _choose_best_direction
       ["G", in_dir, in_label, out_dir, out_label]   the searcher hazard gate
       ["E", flags]                   edge-blocked flags of the 4 directions at execute() entry
  ws   {step: {uid: {key: value}}} wind-state snapshot after the step (searchers only)
"""
from __future__ import annotations

import copy
import json
import os
import runpy
import sys

WS_KEYS = ("pocket_streak", "pocket_center", "pocket_anchor", "escape_target", "force_coverage_escape",
           "force_interior_retarget", "force_sweep", "hazard_buffer_level", "coverage_y_commit",
           "current_target", "corridor_targets", "corridor_index", "last_grid_position",
           "blocked_backtrack_cells", "sweep_no_move_streak", "steps_since_detection",
           "searcher_victim_detections", "last_action", "same_target_streak", "dwell_count",
           "coverage_priority", "north_strip_done", "south_strip_done", "west_strip_done",
           "east_strip_done", "active_lane_axis",
           # v3 (fix3a round 2): the route's latch, its no-path count, the give-ups and refusals - read only
           "fire_route_target", "fire_route_nopath", "route_give_ups", "route_refusals", "route_given_up",
           "route_refusal_steps", "route_give_up_log")


def _j(v):
    """JSON-safe copy of a small value."""
    if isinstance(v, (list, tuple)):
        return [_j(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _j(x) for k, x in v.items()}
    if isinstance(v, float):
        return round(v, 3)
    if isinstance(v, (int, str, bool)) or v is None:
        return v
    return repr(v)[:60]


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
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as lag  # noqa: E402
    import src_extension.execution.uav_executor as ux  # noqa: E402

    cur = {"step": 0}
    EV: dict = {}
    WS: dict = {}
    ctx_uid = {"uid": None}

    def is_searcher(ex):
        try:
            return ex._role_is_victim_searcher(ex._read_uav_role())
        except Exception:
            return False

    def rec(ex, event):
        uid = str(ex.uav_id)
        EV.setdefault(cur["step"], {}).setdefault(uid, []).append(event)

    UX = ux.UAVExecutor

    oexec = UX.execute

    def execute(self, decision, timestamp=0.0, fail_safe_decision=None):
        s = is_searcher(self)
        if s:
            try:
                agent = self._resolve_agent()
                pos = list(agent.pos) if agent is not None and agent.pos is not None else None
                ctx = getattr(decision, "uncertainty_context", None) if decision is not None else None
                flags = sorted(k for k in ("needs_new_wind_target", "wind_target_reached",
                                           "force_wind_retarget", "force_wind_sweep",
                                           "force_coverage_escape")
                               if isinstance(ctx, dict) and ctx.get(k))
                rec(self, ["x", pos,
                           str(getattr(decision, "selected_option_id", "") or "") if decision else None,
                           str(getattr(decision, "next_action", "") or "") if decision else None,
                           int(bool(fail_safe_decision is not None
                                    and getattr(fail_safe_decision, "search_mode_active", False))),
                           flags])
                if agent is not None and agent.pos is not None:
                    rec(self, ["E", [int(self._victim_edge_blocked_direction(agent, d)) for d in range(4)]])
            except Exception as exc:
                rec(self, ["ERRx", repr(exc)[:120]])
        r = oexec(self, decision, timestamp, fail_safe_decision)
        if s:
            try:
                rec(self, ["X", r.get("selected_dir") if isinstance(r, dict) else None,
                           r.get("action") if isinstance(r, dict) else None])
            except Exception as exc:
                rec(self, ["ERRX", repr(exc)[:120]])
        return r

    UX.execute = execute

    otgt = UX._wind_aware_victim_search_target

    def wtarget(self, agent, model=None):
        r = otgt(self, agent, model)
        if is_searcher(self):
            rec(self, ["T", _j(r)])
        return r

    UX._wind_aware_victim_search_target = wtarget

    oroute = UX._attempt_pathfinding_toward_target
    HAZ = "--hazard" in argv[:argv.index("--")]

    def haz_view(self, agent):
        """HAZARD view (--hazard before -- only): the nearest burning / smoke distances from the searcher's
        cell and from each neighbour (read-only: the executor's own collectors)."""
        model = self._resolve_model(agent)
        fire = self._collect_strict_active_fire_cells(model)
        smoke = self._collect_strict_smoke_cells(model)
        x, y = int(agent.pos[0]), int(agent.pos[1])

        def dm(c, cells):
            return min((abs(c[0] - a) + abs(c[1] - b) for a, b in cells), default=99)
        mx, my = [1, 0, -1, 0], [0, -1, 0, 1]
        nb = [[dm((x + mx[k], y + my[k]), fire), dm((x + mx[k], y + my[k]), smoke)] for k in range(4)]
        near = sorted([list(c) + [0] for c in fire if abs(c[0] - x) + abs(c[1] - y) <= 8]
                      + [list(c) + [1] for c in smoke if abs(c[0] - x) + abs(c[1] - y) <= 8])
        return [dm((x, y), fire), dm((x, y), smoke), nb, near[:80]]

    def route(self, agent, target, **kw):
        r = oroute(self, agent, target, **kw)
        if is_searcher(self):
            rec(self, ["R", _j(target), kw.get("action_label"), _j(r),
                       str(getattr(self, "_last_escape_method", "") or "")])
            if HAZ:
                try:
                    rec(self, ["H"] + haz_view(self, agent))
                except Exception as exc:
                    rec(self, ["ERRH", repr(exc)[:120]])
        return r

    UX._attempt_pathfinding_toward_target = route

    oforced = UX._forced_progress_direction

    def forced(self, agent, target):
        blocked_next = None
        bn = None
        if is_searcher(self):
            try:
                model = self._resolve_model(agent)
                store = getattr(model, "_wind_search_target_state", None) if model is not None else None
                ws = copy.deepcopy(store.get(str(self.uav_id)) or {}) if isinstance(store, dict) else {}
                # a COPY of the wind state: the pocket-escape blocked set, recomputed read-only
                pa = (int(ws.get("pocket_streak", 0) or 0) >= 4 or bool(ws.get("force_coverage_escape"))
                      or ws.get("escape_target") is not None)
                start = (int(agent.pos[0]), int(agent.pos[1]))
                blocked = set()
                center = ws.get("pocket_center")
                if pa and isinstance(center, (list, tuple)) and len(center) >= 2:
                    cx, cy = int(center[0]), int(center[1])
                    sd = abs(start[0] - cx) + abs(start[1] - cy)
                    if (cx, cy) != start:
                        blocked.add((cx, cy))
                    for dx in range(-2, 3):
                        for dy in range(-2, 3):
                            c = (cx + dx, cy + dy)
                            if c != start and abs(c[0] - cx) + abs(c[1] - cy) < sd:
                                blocked.add(c)
                    lp = ws.get("last_grid_position")
                    if isinstance(lp, (list, tuple)) and len(lp) >= 2 and tuple(int(v) for v in lp[:2]) != start:
                        blocked.add((int(lp[0]), int(lp[1])))
                    for raw in ws.get("blocked_backtrack_cells") or ():
                        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                            c = (int(raw[0]), int(raw[1]))
                            if c != start:
                                blocked.add(c)
                mx, my = [1, 0, -1, 0], [0, -1, 0, 1]
                blocked_next = [int((start[0] + mx[d], start[1] + my[d]) in blocked) for d in range(4)]
                bn = len(blocked)
            except Exception as exc:
                blocked_next = "ERR %r" % (exc,)
        r = oforced(self, agent, target)
        if is_searcher(self):
            rec(self, ["F", _j(target), r, str(getattr(self, "_last_escape_method", "") or ""), bn,
                       blocked_next])
        return r

    UX._forced_progress_direction = forced

    ocbd = UX._choose_best_direction

    def cbd(self, agent, target, target_kind="general"):
        r = ocbd(self, agent, target, target_kind)
        if is_searcher(self):
            rec(self, ["C", _j(target), target_kind, r])
        return r

    UX._choose_best_direction = cbd

    # Part 3 observer: every lawnmower sweep target handed to a searcher (A1-S: none in the edge band)
    osweep = UX._safe_victim_sweep_target

    def sweep(self, agent, state, model, sector_bounds, height, width, step, pos):
        r = osweep(self, agent, state, model, sector_bounds, height, width, step, pos)
        if is_searcher(self):
            rec(self, ["S", _j(r)])
        return r

    UX._safe_victim_sweep_target = sweep

    ogate = UX._apply_victim_searcher_hazard_gate

    def gate(self, agent, chosen_dir, action):
        r = ogate(self, agent, chosen_dir, action)
        if is_searcher(self):
            rec(self, ["G", chosen_dir, action, r[0], r[1]])
        return r

    UX._apply_victim_searcher_hazard_gate = gate

    ostep = wf.WildFireModel.step
    MODEL = {}

    def step(self):
        cur["step"] += 1
        MODEL["m"] = self
        r = ostep(self)
        try:
            snap = {}
            store = getattr(self, "_wind_search_target_state", None)
            for a in self.schedule.agents:
                if type(a).__name__ != "UAV":
                    continue
                if str(getattr(a, "current_role", "")) != "victim_searcher":
                    continue
                ws = store.get(str(a.unique_id)) if isinstance(store, dict) else None
                if not isinstance(ws, dict):
                    continue
                snap[str(a.unique_id)] = {k: _j(ws.get(k)) for k in WS_KEYS if k in ws}
            WS[cur["step"]] = snap
        except Exception as exc:
            WS[cur["step"]] = {"ERR": repr(exc)[:200]}
        return r

    wf.WildFireModel.step = step

    mf2 = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_mf2_probe.py"),
                         run_name="mf2_probe_module")
    sys.argv = [sys.argv[0]] + argv
    rc = mf2["main"]()
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        rtb = {}
        m = MODEL.get("m")
        for a in (getattr(getattr(m, "schedule", None), "agents", ()) or ()):
            if type(a).__name__ != "UAV":
                continue
            rtb[str(a.unique_id)] = {"log": _j(getattr(a, "rtb_log", []) or []),
                                     "delay": _j(getattr(a, "rtb_delay_log", []) or []),
                                     "delay_steps": int(getattr(a, "rtb_delay_steps", 0) or 0),
                                     "boxed": int(getattr(a, "rtb_boxed_steps", 0) or 0),
                                     "trips": int(getattr(a, "rtb_trips", 0) or 0)}
        d["fx3"] = {"ev": {str(k): v for k, v in EV.items()},
                    "ws": {str(k): v for k, v in WS.items()}, "rtb": rtb, "probe": "fx3_probe v3"}
        tmp = out_path + ".fx3tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("FX3 WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 5
    return rc


if __name__ == "__main__":
    sys.exit(main())
