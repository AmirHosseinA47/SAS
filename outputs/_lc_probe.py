"""last_cell guard instrumentation, hooked at _retreat_candidates itself.

Records the EXACT (cell, origin, last_cell, current_dist) the filter chain
saw - no reconstruction of the 62b4fbe leash re-anchor needed - plus what
each filter removed and what a last-resort re-admission would yield.

--arm selects a runtime-only what-if variant of the last_cell exclusion:
    none  stock b6527f7
    a     cur_dist == 0  -> drop the last_cell filter entirely for that scan
    b     cur_dist == 0  -> re-admit last_cell only if the set is otherwise
                           empty (fire + leash still apply to it)
    c     any cur_dist   -> re-admit last_cell only if the set is otherwise
                           empty (fire + leash still apply to it)
Nothing is written to source; every arm is a monkeypatch.
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
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params

CUR = {"model": None, "seed": None, "arm": "none"}
CAND = []      # every _retreat_candidates call
SURV = []      # every _survival_move call
MOVET = []     # every _move_toward call
RBLK = []      # every _mark_route_blocked transition
DEATHS = []
EVALS = []
FFTRACE = []


def _step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def _mfd(cell, fires):
    if not fires:
        return 999
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


_orig_cand = am.Firefighter._retreat_candidates
_orig_surv = am.Firefighter._survival_move
_orig_move = am.Firefighter._move_toward
_orig_rb = am.Firefighter._mark_route_blocked
MAXC = am.IDLE_RETREAT_MAX_CELLS


def _leash_ok(ncell, origin):
    return (abs(ncell[0] - origin[0]) + abs(ncell[1] - origin[1])) <= MAXC


def _cand(self, cell, origin, last_cell, fire_cells, current_dist):
    arm = CUR["arm"]
    # --- stock chain, recorded in full ---
    free = [n for n in self._neighbor_cells()
            if not self._cell_contains_active_fire(n)]
    after_last = [n for n in free if n != last_cell]
    stock = [n for n in after_last if _leash_ok(n, origin)]
    lc_free = last_cell is not None and last_cell in free
    lc_leash = last_cell is not None and _leash_ok(last_cell, origin)
    lc_admissible = bool(lc_free and lc_leash)
    sole = bool(len(free) == 1 and lc_free and free[0] == last_cell)
    emptied_by_lc = bool((not stock) and lc_admissible)
    rec = {
        "seed": CUR["seed"], "step": _step_no(self.model),
        "ff": str(getattr(self, "unit_id", "")), "arm": arm,
        "cell": list(cell), "origin": list(origin),
        "last_cell": (list(last_cell) if last_cell else None),
        "cur_dist": int(current_dist),
        "on_fire": bool(self._cell_contains_active_fire(cell)),
        "idle": (not self.target_pos) and (not self.exiting),
        "target": (list(self.target_pos) if self.target_pos else None),
        "exiting": bool(self.exiting),
        "stalled": bool(getattr(self, "_idle_retreat_stalled", False)),
        "n_free": len(free), "free": [list(c) for c in free],
        "n_stock": len(stock),
        "lc_removed": len(free) - len(after_last),
        "lc_admissible": lc_admissible,
        "sole_exit": sole,               # last_cell was the ONLY free neighbour
        "emptied_by_lc": emptied_by_lc,  # last_cell is what emptied the set
        "lc_safe": (self._cell_meets_required_idle_safety(last_cell, fire_cells)
                    if lc_admissible else None),
        "lc_dist": (_mfd(last_cell, fire_cells) if lc_admissible else None),
        "readmitted": False,
    }
    CAND.append(rec)

    # --- arm ---
    if arm == "a" and int(current_dist) == 0:
        out = _orig_cand(self, cell, origin, None, fire_cells, current_dist)
    else:
        out = _orig_cand(self, cell, origin, last_cell, fire_cells, current_dist)
        if (not out) and last_cell is not None and (
            arm == "c" or (arm == "b" and int(current_dist) == 0)
        ):
            out = _orig_cand(self, cell, origin, None, fire_cells, current_dist)
            rec["readmitted"] = bool(out)
    rec["n_returned"] = len(out)
    return out


def _surv(self):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    fires = self._fire_cells()
    rec = {
        "seed": CUR["seed"], "step": _step_no(self.model),
        "ff": str(getattr(self, "unit_id", "")),
        "pos": (list(pre) if pre else None),
        "idle": (not self.target_pos) and (not self.exiting),
        "target": (list(self.target_pos) if self.target_pos else None),
        "exiting": bool(self.exiting),
        "stalled_pre": bool(getattr(self, "_idle_retreat_stalled", False)),
        "last_cell_pre": (list(getattr(self, "_idle_retreat_last_cell", None))
                          if getattr(self, "_idle_retreat_last_cell", None) else None),
        "cur_dist": (_mfd(pre, fires) if pre else None),
        "on_fire": (self._cell_contains_active_fire(pre) if pre else None),
    }
    _orig_surv(self)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    rec.update({"post": (list(post) if post else None),
                "moved": post != pre,
                "stalled_post": bool(getattr(self, "_idle_retreat_stalled", False)),
                "post_dist": (_mfd(post, self._fire_cells()) if post else None)})
    SURV.append(rec)


def _mt(self, target):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    _orig_move(self, target)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    MOVET.append({"seed": CUR["seed"], "step": _step_no(self.model),
                  "ff": str(getattr(self, "unit_id", "")),
                  "pre": (list(pre) if pre else None),
                  "post": (list(post) if post else None),
                  "moved": post != pre,
                  "target": (list(target) if target else None)})


def _rb(self):
    was = str(getattr(self, "status", "") or "").strip().lower()
    _orig_rb(self)
    if was != "route_blocked":
        RBLK.append({"seed": CUR["seed"], "step": _step_no(self.model),
                     "ff": str(getattr(self, "unit_id", "")),
                     "pos": (list(self.pos) if self.pos else None),
                     "assigned_after": bool(getattr(self, "assigned", False)),
                     "target_after": (list(self.target_pos)
                                      if self.target_pos else None)})


am.Firefighter._retreat_candidates = _cand
am.Firefighter._survival_move = _surv
am.Firefighter._move_toward = _mt
am.Firefighter._mark_route_blocked = _rb


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
        for s in range(1, steps + 1):
            model.step()
            fires = _fire_cells(model)
            for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                d = bool(getattr(m, "dead", False))
                pos = getattr(m, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                mr = getattr(m, "movement_reason", None) or {}
                nfree = None
                if cell is not None and not d:
                    nfree = sum(1 for n in m._neighbor_cells()
                                if not m._cell_contains_active_fire(n))
                FFTRACE.append({
                    "seed": seed, "step": s, "ff": fid,
                    "pos": (list(cell) if cell else None), "dead": d,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "target": (list(m.target_pos)
                               if getattr(m, "target_pos", None) else None),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                    "last_cell": (list(getattr(m, "_idle_retreat_last_cell", None))
                                  if getattr(m, "_idle_retreat_last_cell", None) else None),
                    "mfd": (_mfd(cell, fires) if cell else None),
                    "n_free": nfree, "cat": str(mr.get("category", "")),
                })
                if fid not in alive:
                    alive[fid] = d
                elif d and not alive[fid]:
                    DEATHS.append({"seed": seed, "step": s, "ff": fid,
                                   "pos": (list(cell) if cell else None),
                                   "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                                   "cat": str(mr.get("category", ""))})
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
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--arm", default="none", choices=["none", "a", "b", "c"])
    ap.add_argument("--tag", default="")
    ap.add_argument("--prefix", default="_lc")
    a = ap.parse_args()
    CUR["arm"] = a.arm
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
        sys.stderr.write("seed %s done: deaths=%d cand=%d\n"
                         % (seed, len(DEATHS), len(CAND)))
        sys.stderr.flush()
    out = {"scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "roles": a.roles, "arm": a.arm, "params": params,
           "cand": CAND, "surv": SURV, "movetoward": MOVET, "route_blocked": RBLK,
           "deaths": DEATHS, "evals": EVALS, "fftrace": FFTRACE,
           "consts": {"IDLE_RETREAT_SAFETY_BUFFER": am.IDLE_RETREAT_SAFETY_BUFFER,
                      "IDLE_RETREAT_MAX_CELLS": am.IDLE_RETREAT_MAX_CELLS}}
    tag = a.tag or ("%s_%s_%s_%s" % (a.scenario, a.wind, a.roles, a.arm))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "%s_%s.json" % (a.prefix, tag))
    with open(p, "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(p)


main()
