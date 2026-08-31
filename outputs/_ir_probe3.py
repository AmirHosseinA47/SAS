"""Standby/release-posture death instrumentation.

Read-only: patches nothing on disk, only wraps methods at runtime in-process.
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import (
    BUILTIN_SCENARIOS,
    _build_evaluation,
    _resolve_role_count_params,
)

CUR = {"model": None, "seed": None}
SURV = []        # every _survival_move call, with candidate forensics
FFTRACE = []     # per-step per-FF snapshot
DEATHS = []
LIFECYCLE = []   # assign / unassign / recycle events
IGNITION = {}    # (seed, cell) -> first step observed burning
VICTIMS0 = []
EVALS = []      # end-of-run outcome metrics, one per seed


def _step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def _mfd(cell, fires):
    if not fires:
        return 999
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


def _counterfactual(ff, fires):
    """What the unit COULD have done, ignoring last_cell / leash / latch.

    Lets "nowhere to retreat" be attributed to a real dead end vs a
    self-imposed candidate filter.
    """
    cell = (int(ff.pos[0]), int(ff.pos[1]))
    cur = _mfd(cell, fires)
    nb = ff._neighbor_cells()
    free = [c for c in nb if not ff._cell_contains_active_fire(c)]
    safe = [c for c in free if ff._cell_meets_required_idle_safety(c, fires)]
    ideal = [c for c in free if ff._cell_is_ideal_idle_standoff(c, fires)]
    best = max((_mfd(c, fires) for c in free), default=None)
    return {
        "cur_dist": cur,
        "n_inbounds": len(nb),
        "n_free": len(free),
        "n_safe": len(safe),
        "n_ideal": len(ideal),
        "best_free_dist": best,
        "strictly_better_exists": (best is not None and best > cur),
        "free_cells": [list(c) for c in free],
    }


_orig_surv = am.Firefighter._survival_move


def _surv(self):
    model = self.model
    fires = self._fire_cells()
    pre_pos = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    rec = {
        "step": _step_no(model), "seed": CUR["seed"],
        "ff": str(getattr(self, "unit_id", "")),
        "pos": list(pre_pos) if pre_pos else None,
        "idle": (not self.target_pos) and (not self.exiting),
        "target_pos": (list(self.target_pos) if self.target_pos else None),
        "exiting": bool(self.exiting),
        "stalled_pre": bool(getattr(self, "_idle_retreat_stalled", False)),
        "origin": (list(getattr(self, "_idle_retreat_origin", None))
                   if getattr(self, "_idle_retreat_origin", None) else None),
        "retreat_steps": int(getattr(self, "_idle_retreat_steps", 0) or 0),
        "last_cell": (list(getattr(self, "_idle_retreat_last_cell", None))
                      if getattr(self, "_idle_retreat_last_cell", None) else None),
        "on_fire": self._cell_contains_active_fire(pre_pos) if pre_pos else None,
        "smoke": self._cell_has_active_smoke(pre_pos) if pre_pos else None,
        "ideal_now": (self._cell_is_ideal_idle_standoff(pre_pos, fires)
                      if pre_pos else None),
    }
    if pre_pos is not None:
        rec.update(_counterfactual(self, fires))

        # Replicate the real candidate filter chain to attribute exclusions.
        origin = getattr(self, "_idle_retreat_origin", None) or pre_pos
        last_cell = getattr(self, "_idle_retreat_last_cell", None)
        excl_fire = excl_last = excl_leash = 0
        kept = []
        for n in self._neighbor_cells():
            if self._cell_contains_active_fire(n):
                excl_fire += 1
                continue
            if last_cell is not None and n == tuple(last_cell):
                excl_last += 1
                continue
            if (abs(n[0] - origin[0]) + abs(n[1] - origin[1])) > am.IDLE_RETREAT_MAX_CELLS:
                excl_leash += 1
                continue
            kept.append(n)
        rec.update({"excl_fire": excl_fire, "excl_lastcell": excl_last,
                    "excl_leash": excl_leash, "n_candidates": len(kept),
                    "cand_best_dist": max((_mfd(c, fires) for c in kept),
                                          default=None)})

    _orig_surv(self)

    post_pos = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    rec.update({
        "post_pos": list(post_pos) if post_pos else None,
        "moved": post_pos != pre_pos,
        "stalled_post": bool(getattr(self, "_idle_retreat_stalled", False)),
        "post_dist": _mfd(post_pos, self._fire_cells()) if post_pos else None,
    })
    SURV.append(rec)


am.Firefighter._survival_move = _surv


_orig_recycle = wf.WildFireModel._recycle_firefighter_after_exit


def _recycle(self, ff_marker):
    before = getattr(ff_marker, "pos", None)
    _orig_recycle(self, ff_marker)
    after = getattr(ff_marker, "pos", None)
    LIFECYCLE.append({
        "seed": CUR["seed"], "step": _step_no(self), "kind": "recycle",
        "ff": str(getattr(ff_marker, "unit_id", "")),
        "pos_before": (list(before) if before else None),
        "pos_after": (list(after) if after else None),
    })


wf.WildFireModel._recycle_firefighter_after_exit = _recycle


_orig_cmd = wf.WildFireModel.apply_physical_rescue_command


def _cmd(self, command):
    action = str(getattr(command, "action", "") or "")
    ff_id = str(getattr(command, "firefighter_id", "") or "")
    ffm = (getattr(self, "firefighter_marker_agents", {}) or {}).get(ff_id)
    before = {
        "pos": (list(ffm.pos) if ffm is not None and getattr(ffm, "pos", None) else None),
        "assigned": bool(getattr(ffm, "assigned", False)) if ffm is not None else None,
        "exiting": bool(getattr(ffm, "exiting", False)) if ffm is not None else None,
        "carrying": ((getattr(ffm, "rescued_victim", None) is not None)
                     if ffm is not None else None),
        "target": (list(ffm.target_pos)
                   if ffm is not None and getattr(ffm, "target_pos", None) else None),
    }
    ok = _orig_cmd(self, command)
    if action in ("assign", "unassign"):
        LIFECYCLE.append({
            "seed": CUR["seed"], "step": _step_no(self), "kind": action,
            "ff": ff_id, "victim": str(getattr(command, "victim_id", "") or ""),
            "ok": bool(ok), "before": before,
            "reason": str(getattr(command, "reason", "") or ""),
            "after_target": (list(ffm.target_pos)
                             if ffm is not None and getattr(ffm, "target_pos", None)
                             else None),
            "after_carrying": ((getattr(ffm, "rescued_victim", None) is not None)
                               if ffm is not None else None),
        })
    return ok


wf.WildFireModel.apply_physical_rescue_command = _cmd


def _fire_cells(model):
    out = set()
    for a in model.schedule.agents:
        if type(a) is am.Fire and a.is_burning():
            p = getattr(a, "pos", None)
            if p is not None:
                out.add((int(p[0]), int(p[1])))
    return out


def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    CUR["seed"] = seed
    alive = {}
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        CUR["model"] = model
        for a in model.schedule.agents:
            if type(a) is am.Victim and getattr(a, "pos", None) is not None:
                VICTIMS0.append({"seed": seed,
                                 "vid": str(getattr(a, "victim_id", "")),
                                 "pos": [int(a.pos[0]), int(a.pos[1])]})
        for s in range(1, steps + 1):
            model.step()
            fires = _fire_cells(model)
            for c in fires:
                IGNITION.setdefault((seed, c), s)
            ffm = getattr(model, "firefighter_marker_agents", {}) or {}
            for fid, m in ffm.items():
                d = bool(getattr(m, "dead", False))
                pos = getattr(m, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                mr = getattr(m, "movement_reason", None) or {}
                row = {
                    "seed": seed, "step": s, "ff": fid,
                    "pos": (list(cell) if cell else None),
                    "dead": d,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "target": (list(m.target_pos)
                               if getattr(m, "target_pos", None) else None),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "carrying": getattr(m, "rescued_victim", None) is not None,
                    "rescue_completed": bool(getattr(m, "rescue_completed", False)),
                    "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                    "retreat_steps": int(getattr(m, "_idle_retreat_steps", 0) or 0),
                    "origin": (list(getattr(m, "_idle_retreat_origin", None))
                               if getattr(m, "_idle_retreat_origin", None) else None),
                    "cat": str(mr.get("category", "")),
                    "fine": str(mr.get("fine_category", "")),
                    "mfd": (_mfd(cell, fires) if cell else None),
                }
                if cell is not None and not d:
                    nb = m._neighbor_cells()
                    row["n_inb"] = len(nb)
                    row["n_free"] = sum(
                        1 for n in nb if not m._cell_contains_active_fire(n))
                FFTRACE.append(row)
                if fid not in alive:
                    alive[fid] = d
                elif d and not alive[fid]:
                    DEATHS.append({
                        "seed": seed, "step": s, "ff": fid,
                        "pos": (list(cell) if cell else None),
                        "status": row["status"], "assigned": row["assigned"],
                        "target": row["target"], "exiting": row["exiting"],
                        "carrying": row["carrying"], "stalled": row["stalled"],
                        "cat": row["cat"],
                    })
                alive[fid] = d
        ev = _build_evaluation(model, None, steps, params)
        ev["seed"] = seed
        EVALS.append(ev)
    CUR["model"] = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", default="101,202,303,404,505")
    ap.add_argument("--roles", default="half", choices=["half", "default"],
                    help="half = prior ffdeath probe (n//2 trackers); "
                         "default = evaluate_scenarios.py CLI defaults")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    if a.roles == "half":
        ft = n // 2 or 1
        vs = n - ft
    else:
        ft, vs = _resolve_role_count_params(n, None, None)
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
              "WIND_DIRECTION": a.wind, "BATCH_SIZE": 300,
              "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}
    for seed in [int(s) for s in a.seeds.split(",")]:
        run(seed, params, a.steps)
        sys.stderr.write("seed %s done: %d deaths, %d surv-calls\n"
                         % (seed, len(DEATHS), len(SURV)))
        sys.stderr.flush()
    out = {"scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "roles": a.roles, "params": params,
           "deaths": DEATHS, "surv": SURV, "fftrace": FFTRACE,
           "evals": EVALS,
           "lifecycle": LIFECYCLE, "victims0": VICTIMS0,
           "ignition": {"%d|%d,%d" % (k[0], k[1][0], k[1][1]): v
                        for k, v in IGNITION.items()},
           "consts": {"IDLE_RETREAT_SAFETY_BUFFER": am.IDLE_RETREAT_SAFETY_BUFFER,
                      "IDLE_RETREAT_MAX_CELLS": am.IDLE_RETREAT_MAX_CELLS}}
    tag = a.tag or ("%s_%s_%s" % (a.scenario, a.wind, a.roles))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_ir_p3_%s.json" % tag)
    with open(p, "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(p)


main()
