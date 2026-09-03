"""Round: the `_reset_idle_retreat_state` last_cell hole (agents.py:859/863).

INSTRUMENT DESIGN - DIRECT OBSERVATION, NEVER POST-HOC INFERENCE.
The two false-positive episodes in this campaign (the 14/16 idle-death figure,
the six phantom "drops") both came from reconstructing a transition from a
per-step snapshot.  Nothing here is reconstructed:

  * `_idle_retreat_last_cell` becomes a property, so EVERY write is captured in
    LCWRITES with its caller line number, the step, the old and the new value.
    Any "shadow" definition is therefore derivable OFFLINE from the write log;
    the probe commits to none of them.
  * `_reset_idle_retreat_state` is wrapped and the CALLER LINE recorded via
    sys._getframe(1).f_lineno, so every clear is attributed to its site.
  * `_retreat_candidates` is wrapped and the FULL candidate set it returned is
    recorded, so "would the guard have refused this cell / was there a better
    one" is read out, not guessed.
  * Every position change is recorded AT THE CALL THAT MADE IT, tagged with the
    code path (`survival`, `move_toward`, `assigned_one_step`, `revalidate`).

Every hooked helper (`_fire_cells`, `_min_fire_distance`,
`_firefighter_cell_risk`, the cell predicates) is a pure read of grid state -
no RNG draw, no mutation - so the extra calls made for logging cannot perturb
the run.  `_irh_control.py` checks that empirically.

--arm keeplc : monkeypatch what-if.  `_reset_idle_retreat_state` clears every
               field EXCEPT `_idle_retreat_last_cell`.  Nothing is written to
               source.
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

CUR = {"seed": None, "arm": "none"}
LCWRITES, RESETS, CAND, MOVES, DEATHS, EVALS, FFTRACE = [], [], [], [], [], [], []
SURVCALLS = []


def _step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def _L(v):
    return list(v) if v is not None else None


def _mfd(cell, fires):
    if not fires or cell is None:
        return None
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


# ------------------------------------------------- last_cell full write log
_IN_RESET = set()


def _lc_get(self):
    return self.__dict__.get("_lc_real")


def _lc_set(self, v):
    old = self.__dict__.get("_lc_real")
    self.__dict__["_lc_real"] = v
    # caller line: frame 1 is whatever executed the assignment
    try:
        line = sys._getframe(1).f_lineno
    except Exception:
        line = -1
    model = getattr(self, "model", None)
    LCWRITES.append({
        "seed": CUR["seed"],
        "step": (_step_no(model) if model is not None else -1),
        "ff": str(getattr(self, "unit_id", "")),
        "site": line,
        "in_reset": id(self) in _IN_RESET,
        "old": _L(old),
        "new": _L(v),
    })


am.Firefighter._idle_retreat_last_cell = property(_lc_get, _lc_set)

_orig_reset = am.Firefighter._reset_idle_retreat_state
_orig_cand = am.Firefighter._retreat_candidates
_orig_surv = am.Firefighter._survival_move
_orig_move = am.Firefighter._move_toward
_orig_asr = am.Firefighter._assigned_one_step_retreat
_orig_reval = am.Firefighter._revalidate_idle_retreat_stall


def _reset(self):
    try:
        line = sys._getframe(1).f_lineno
    except Exception:
        line = -1
    pos = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    lc_before = self.__dict__.get("_lc_real")
    RESETS.append({
        "seed": CUR["seed"], "step": _step_no(self.model),
        "ff": str(getattr(self, "unit_id", "")), "site": line,
        "pos": _L(pos), "lc_before": _L(lc_before),
        "origin_before": _L(self.__dict__.get("_idle_retreat_origin")),
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
    out = _orig_cand(self, cell, origin, last_cell, fire_cells, current_dist)
    CAND.append({
        "seed": CUR["seed"], "step": _step_no(self.model),
        "ff": str(getattr(self, "unit_id", "")),
        "cell": _L(cell), "origin": _L(origin),
        "last_cell": _L(last_cell),
        "lc_real": _L(self.__dict__.get("_lc_real")),
        "cur_dist": int(current_dist),
        "idle": (not self.target_pos) and (not self.exiting),
        "stalled": bool(getattr(self, "_idle_retreat_stalled", False)),
        "out": [{"cell": list(c["cell"]), "dist": int(c["dist"]),
                 "risk": int(c["risk"]), "ideal": bool(c["ideal"]),
                 "required": bool(c["required"])} for c in out],
    })
    return out


def _log_move(self, path, pre, post, extra=None):
    fires = self._fire_cells()
    rec = {"seed": CUR["seed"], "step": _step_no(self.model),
           "ff": str(getattr(self, "unit_id", "")), "path": path,
           "pre": _L(pre), "post": _L(post), "moved": bool(post != pre),
           "pre_dist": _mfd(pre, fires), "post_dist": _mfd(post, fires),
           "pre_risk": (self._firefighter_cell_risk(pre) if pre else None),
           "post_risk": (self._firefighter_cell_risk(post) if post else None),
           "idle": (not self.target_pos) and (not self.exiting),
           "exiting": bool(self.exiting),
           "target": _L(self.target_pos)}
    if extra:
        rec.update(extra)
    MOVES.append(rec)


def _surv(self):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    lc_pre = self.__dict__.get("_lc_real")
    nR, nW, nC = len(RESETS), len(LCWRITES), len(CAND)
    _orig_surv(self)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    me = str(getattr(self, "unit_id", ""))
    SURVCALLS.append({
        "seed": CUR["seed"], "step": _step_no(self.model), "ff": me,
        "pre": _L(pre), "post": _L(post), "moved": bool(post != pre),
        "lc_pre": _L(lc_pre),
        "lc_post": _L(self.__dict__.get("_lc_real")),
        "idle": (not self.target_pos) and (not self.exiting),
        "reset_sites": [r["site"] for r in RESETS[nR:] if r["ff"] == me],
        "lc_write_sites": [w["site"] for w in LCWRITES[nW:] if w["ff"] == me],
        "n_cand_calls": len([c for c in CAND[nC:] if c["ff"] == me]),
    })
    _log_move(self, "survival", pre, post, {"lc_pre": _L(lc_pre)})


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
    lc_pre = self.__dict__.get("_lc_real")
    r = _orig_reval(self, cell, origin, fire_cells)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    if post != pre:
        _log_move(self, "revalidate", pre, post, {"lc_pre": _L(lc_pre)})
    return r


am.Firefighter._reset_idle_retreat_state = _reset
am.Firefighter._retreat_candidates = _cand
am.Firefighter._survival_move = _surv
am.Firefighter._move_toward = _mt
am.Firefighter._assigned_one_step_retreat = _asr
am.Firefighter._revalidate_idle_retreat_stall = _reval


def _fire_cells_model(model):
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
        for s in range(1, steps + 1):
            model.step()
            fires = _fire_cells_model(model)
            for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                d = bool(getattr(m, "dead", False))
                pos = getattr(m, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                mr = getattr(m, "movement_reason", None) or {}
                FFTRACE.append({
                    "seed": seed, "step": s, "ff": fid,
                    "pos": _L(cell), "dead": d,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "target": _L(getattr(m, "target_pos", None)),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                    "origin": _L(getattr(m, "_idle_retreat_origin", None)),
                    "irsteps": int(getattr(m, "_idle_retreat_steps", 0) or 0),
                    "mfd": _mfd(cell, fires),
                    "cat": str(mr.get("category", "")),
                })
                if fid not in alive:
                    alive[fid] = d
                elif d and not alive[fid]:
                    DEATHS.append({"seed": seed, "step": s, "ff": fid,
                                   "pos": _L(cell),
                                   "cat": str(mr.get("category", ""))})
                alive[fid] = d
        ev = _build_evaluation(model, None, steps, params)
        ev["seed"] = seed
        EVALS.append(ev)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", default="101")
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
        sys.stderr.write("seed %s done: resets=%d lcwrites=%d moves=%d\n"
                         % (seed, len(RESETS), len(LCWRITES), len(MOVES)))
        sys.stderr.flush()
    out = {"scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "roles": a.roles, "arm": a.arm, "params": params,
           "lcwrites": LCWRITES, "resets": RESETS, "cand": CAND,
           "survcalls": SURVCALLS, "moves": MOVES, "deaths": DEATHS,
           "evals": EVALS, "fftrace": FFTRACE}
    tag = a.tag or ("%s_%s_%s_%s" % (a.scenario, a.wind, a.roles, a.arm))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_irh2_%s.json" % tag)
    with open(p, "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(p)


main()
