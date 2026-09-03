"""idle-retreat reset hole probe: does _reset_idle_retreat_state clearing
`_idle_retreat_last_cell` permit next-step reversals, and do they cost anything?

DIRECT OBSERVATION, NOT INFERENCE:
  * `_idle_retreat_last_cell` is replaced by a property. Every write is seen.
    A parallel SHADOW value tracks the same writes EXCEPT the one made inside
    `_reset_idle_retreat_state`. So "shadow is not None and real is None"
    means exactly: the reset cleared the guard and nothing has re-set it.
  * `_reset_idle_retreat_state` is wrapped and the CALLER LINE NUMBER recorded
    via sys._getframe(1).f_lineno, so each clear is attributed to a site.
  * `_retreat_candidates` is wrapped, so what the filter chain actually saw is
    recorded rather than reconstructed.
  * Every move is recorded at the moving call, tagged with its code path.

--arm keeplc : monkeypatch what-if. _reset_idle_retreat_state preserves
               `_idle_retreat_last_cell` (all other fields still cleared).
               Nothing is written to source.
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
RESETS, CAND, MOVES, DEATHS, EVALS, FFTRACE = [], [], [], [], [], []
MAXC = am.IDLE_RETREAT_MAX_CELLS


def _step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def _mfd(cell, fires):
    if not fires:
        return 999
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


# ---------------------------------------------------------------- shadow lc
_IN_RESET = set()          # ids of agents currently inside the reset


def _lc_get(self):
    return self.__dict__.get("_lc_real")


def _lc_set(self, v):
    self.__dict__["_lc_real"] = v
    if id(self) not in _IN_RESET:
        self.__dict__["_lc_shadow"] = v


am.Firefighter._idle_retreat_last_cell = property(_lc_get, _lc_set)


def _shadow(self):
    return self.__dict__.get("_lc_shadow")


# ---------------------------------------------------------------- wrappers
_orig_reset = am.Firefighter._reset_idle_retreat_state
_orig_cand = am.Firefighter._retreat_candidates
_orig_surv = am.Firefighter._survival_move
_orig_move = am.Firefighter._move_toward
_orig_asr = am.Firefighter._assigned_one_step_retreat
_orig_reval = am.Firefighter._revalidate_idle_retreat_stall


def _reset(self):
    line = sys._getframe(1).f_lineno
    pos = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    lc_before = self.__dict__.get("_lc_real")
    org = self.__dict__.get("_idle_retreat_origin")
    RESETS.append({
        "seed": CUR["seed"], "step": _step_no(self.model),
        "ff": str(getattr(self, "unit_id", "")), "site": line,
        "pos": (list(pos) if pos else None),
        "lc_before": (list(lc_before) if lc_before else None),
        "origin_before": (list(org) if org else None),
        "steps_before": int(getattr(self, "_idle_retreat_steps", 0) or 0),
        "stalled_before": bool(getattr(self, "_idle_retreat_stalled", False)),
        "idle": (not self.target_pos) and (not self.exiting),
        "cleared_lc": lc_before is not None,
    })
    _IN_RESET.add(id(self))
    try:
        if CUR["arm"] == "keeplc":
            self._idle_retreat_origin = None
            self._idle_retreat_steps = 0
            self._idle_retreat_stalled = False
            # `_idle_retreat_last_cell` deliberately PRESERVED
        else:
            _orig_reset(self)
    finally:
        _IN_RESET.discard(id(self))


def _cand(self, cell, origin, last_cell, fire_cells, current_dist):
    sh = _shadow(self)
    out = _orig_cand(self, cell, origin, last_cell, fire_cells, current_dist)
    CAND.append({
        "seed": CUR["seed"], "step": _step_no(self.model),
        "ff": str(getattr(self, "unit_id", "")),
        "cell": list(cell), "origin": list(origin),
        "last_cell": (list(last_cell) if last_cell else None),
        "shadow": (list(sh) if sh else None),
        "lc_cleared_by_reset": bool(last_cell is None and sh is not None),
        "shadow_in_out": bool(sh is not None
                              and any(tuple(c["cell"]) == tuple(sh) for c in out)),
        "cur_dist": int(current_dist),
        "n_out": len(out),
        "idle": (not self.target_pos) and (not self.exiting),
        "stalled": bool(getattr(self, "_idle_retreat_stalled", False)),
    })
    return out


def _log_move(self, path, pre, post, extra=None):
    fires = self._fire_cells()
    rec = {"seed": CUR["seed"], "step": _step_no(self.model),
           "ff": str(getattr(self, "unit_id", "")), "path": path,
           "pre": (list(pre) if pre else None),
           "post": (list(post) if post else None),
           "moved": bool(post != pre),
           "pre_dist": (_mfd(pre, fires) if pre else None),
           "post_dist": (_mfd(post, fires) if post else None),
           "idle": (not self.target_pos) and (not self.exiting),
           "target": (list(self.target_pos) if self.target_pos else None)}
    if extra:
        rec.update(extra)
    MOVES.append(rec)


def _surv(self):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    sh_pre = _shadow(self)
    lc_pre = self.__dict__.get("_lc_real")
    n0 = len(RESETS)
    _orig_surv(self)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    sites = [r["site"] for r in RESETS[n0:]
             if r["ff"] == str(getattr(self, "unit_id", ""))]
    _log_move(self, "survival", pre, post, {
        "lc_pre": (list(lc_pre) if lc_pre else None),
        "shadow_pre": (list(sh_pre) if sh_pre else None),
        "lc_was_cleared_pre": bool(lc_pre is None and sh_pre is not None),
        "reversal_vs_shadow": bool(post != pre and sh_pre is not None
                                   and tuple(post) == tuple(sh_pre)),
        "reset_sites": sites,
        "lc_post": (lambda v: list(v) if v else None)(self.__dict__.get("_lc_real")),
    })


def _mt(self, target):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    _orig_move(self, target)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    _log_move(self, "move_toward", pre, post)


def _asr(self, fire_cells=None):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    r = _orig_asr(self, fire_cells)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    if post != pre:
        _log_move(self, "assigned_one_step", pre, post)
    return r


def _reval(self, cell, origin, fire_cells):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    sh_pre = _shadow(self)
    r = _orig_reval(self, cell, origin, fire_cells)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    if post != pre:
        _log_move(self, "revalidate", pre, post, {
            "shadow_pre": (list(sh_pre) if sh_pre else None),
            "reversal_vs_shadow": bool(sh_pre is not None
                                       and tuple(post) == tuple(sh_pre))})
    return r


am.Firefighter._reset_idle_retreat_state = _reset
am.Firefighter._retreat_candidates = _cand
am.Firefighter._survival_move = _surv
am.Firefighter._move_toward = _mt
am.Firefighter._assigned_one_step_retreat = _asr
am.Firefighter._revalidate_idle_retreat_stall = _reval


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
                FFTRACE.append({
                    "seed": seed, "step": s, "ff": fid,
                    "pos": (list(cell) if cell else None), "dead": d,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "target": (list(m.target_pos)
                               if getattr(m, "target_pos", None) else None),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                    "mfd": (_mfd(cell, fires) if cell else None),
                    "cat": str(mr.get("category", "")),
                })
                if fid not in alive:
                    alive[fid] = d
                elif d and not alive[fid]:
                    DEATHS.append({"seed": seed, "step": s, "ff": fid,
                                   "pos": (list(cell) if cell else None),
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
    ap.add_argument("--arm", default="none", choices=["none", "keeplc"])
    ap.add_argument("--tag", default="")
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
        sys.stderr.write("seed %s done: resets=%d moves=%d\n"
                         % (seed, len(RESETS), len(MOVES)))
        sys.stderr.flush()
    out = {"scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "roles": a.roles, "arm": a.arm, "params": params,
           "resets": RESETS, "cand": CAND, "moves": MOVES,
           "deaths": DEATHS, "evals": EVALS, "fftrace": FFTRACE}
    tag = a.tag or ("%s_%s_%s_%s" % (a.scenario, a.wind, a.roles, a.arm))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_irh_%s.json" % tag)
    with open(p, "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(p)


main()
