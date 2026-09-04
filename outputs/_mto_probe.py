"""Round: `_move_toward` oscillation (agents.py:1081).

INSTRUMENT DESIGN - DIRECT OBSERVATION, SELF-VALIDATING.

The brief's caution (the 14/16 false idle-death figure, the six phantom
"drops") is about reconstructing a transition from a per-step snapshot.
Nothing here is reconstructed that way:

  * Every position change is recorded AT THE CALL THAT MADE IT, tagged with
    the code path that made it (`move_toward`, `survival`, `assigned_one_step`,
    `revalidate`).  Tight reversals are read off that log, not off snapshots.
  * The full decision context of every `_move_toward` call is recorded: the
    scored neighbour pool (dist_after / improving / maintaining / adjacent_fire
    / smoke / preferred / risk for EVERY neighbour), the preferred cell,
    dist_before, route_blocked_now, target, exiting, assigned.
  * The pool is RECOMPUTED in the wrapper from the same pure read-only helpers
    the real method uses, then CROSS-VALIDATED: the wrapper predicts the cell
    and tier the real method will pick, the real method then runs, and
    predicted-vs-actual is recorded per call.  If prediction is 100% the
    recorded pool is provably the pool the real code saw.  Any mismatch is
    counted and reported rather than hidden.
  * `_last_move_tier` / `_last_move_risk` are read back from the object AFTER
    the real call, so tier is ground truth, not inference.

Every helper the wrapper calls (`_neighbor_cells`, `_cell_contains_active_fire`,
`_cell_adjacent_to_fire`, `_cell_has_active_smoke`, `_firefighter_cell_risk`,
`_fire_cells`, `_path_exists_avoiding_fire`) is a pure read of grid state - no
RNG draw, no mutation.  `_mto_control.py` checks that empirically against a
no-monkeypatch run.
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
MOVES, MTCALLS, DEATHS, EVALS, FFTRACE = [], [], [], [], []
PREDSTATS = {"n": 0, "cell_ok": 0, "tier_ok": 0, "mismatch": []}


def _step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def _L(v):
    return list(v) if v is not None else None


def _mfd(cell, fires):
    if not fires or cell is None:
        return None
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


_orig_surv = am.Firefighter._survival_move
_orig_move = am.Firefighter._move_toward
_orig_asr = am.Firefighter._assigned_one_step_retreat
_orig_reval = am.Firefighter._revalidate_idle_retreat_stall


def _log_move(self, path, pre, post, extra=None):
    fires = self._fire_cells()
    rec = {"seed": CUR["seed"], "step": _step_no(self.model),
           "ff": str(getattr(self, "unit_id", "")), "path": path,
           "pre": _L(pre), "post": _L(post), "moved": bool(post != pre),
           "pre_dist": _mfd(pre, fires), "post_dist": _mfd(post, fires),
           "idle": (not self.target_pos) and (not self.exiting),
           "exiting": bool(self.exiting),
           "target": _L(self.target_pos)}
    if extra:
        rec.update(extra)
    MOVES.append(rec)


def _recompute(self, target):
    """Mirror of agents.py:1081-1170 using only pure read helpers.

    Returns the full decision context the real method is about to compute.
    Kept line-for-line parallel to the source so drift is visible on review;
    correctness is not taken on trust - the caller cross-validates the
    predicted (cell, tier) against what the real method actually did.
    """
    tx, ty = target
    cx, cy = self.pos
    dx, dy = tx - cx, ty - cy
    if abs(dx) >= abs(dy):
        nx = cx + (1 if dx > 0 else -1 if dx < 0 else 0)
        ny = cy
    else:
        nx = cx
        ny = cy + (1 if dy > 0 else -1 if dy < 0 else 0)
    preferred = (nx, ny)
    dist_before = abs(cx - tx) + abs(cy - ty)

    route_blocked_now = False
    if not self.exiting:
        route_blocked_now = not self._path_exists_avoiding_fire(
            (int(cx), int(cy)), (int(tx), int(ty)), self._fire_cells(),
        )

    scored = []
    for cell in self._neighbor_cells():
        onfire = self._cell_contains_active_fire(cell)
        rec = {
            "cell": cell,
            "on_fire": onfire,
            "dist_after": abs(cell[0] - tx) + abs(cell[1] - ty),
            "adjacent_fire": self._cell_adjacent_to_fire(cell),
            "smoke": self._cell_has_active_smoke(cell),
            "preferred": cell == preferred,
            "risk": self._firefighter_cell_risk(cell),
        }
        rec["improving"] = rec["dist_after"] < dist_before
        rec["maintaining"] = rec["dist_after"] == dist_before
        scored.append(rec)

    live = [s for s in scored if not s["on_fire"]]
    pred_cell, pred_tier = None, None
    if live:
        pools = [
            [i for i in live
             if i["improving"] and not i["adjacent_fire"] and not i["smoke"]],
            [i for i in live
             if i["maintaining"] and not i["adjacent_fire"] and not i["smoke"]],
            [i for i in live if not i["adjacent_fire"] and not i["smoke"]],
        ]
        for ti, pool in enumerate(pools, start=1):
            if pool:
                ci = min(pool,
                         key=lambda i: (i["dist_after"],
                                        0 if i["preferred"] else 1))
                pred_cell, pred_tier = ci["cell"], ti
                break
        if pred_cell is None:
            ci = min(live, key=lambda i: (i["risk"], i["dist_after"],
                                          0 if i["preferred"] else 1))
            pred_cell, pred_tier = ci["cell"], 4

    # Current cell's own hazard profile - needed to answer "was the cell it
    # returned to safe" and "would a guard have forced it somewhere worse".
    here = {
        "on_fire": self._cell_contains_active_fire((cx, cy)),
        "adjacent_fire": self._cell_adjacent_to_fire((cx, cy)),
        "smoke": self._cell_has_active_smoke((cx, cy)),
        "risk": int(self._firefighter_cell_risk((cx, cy))),
    }
    return {
        "preferred": _L(preferred),
        "dist_before": int(dist_before),
        "route_blocked_now": bool(route_blocked_now),
        "n_live": len(live),
        "scored": [{"cell": list(s["cell"]), "on_fire": s["on_fire"],
                    "dist_after": s["dist_after"], "improving": s["improving"],
                    "maintaining": s["maintaining"],
                    "adjacent_fire": s["adjacent_fire"], "smoke": s["smoke"],
                    "preferred": s["preferred"], "risk": int(s["risk"])}
                   for s in scored],
        "here": here,
        "pred_cell": _L(pred_cell),
        "pred_tier": pred_tier,
    }


def _mt(self, target):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    ctx = _recompute(self, target)
    status_pre = str(getattr(self, "status", "") or "")
    _orig_move(self, target)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    tier = getattr(self, "_last_move_tier", None)
    risk = getattr(self, "_last_move_risk", None)

    PREDSTATS["n"] += 1
    cell_ok = ((ctx["pred_cell"] is None and post == pre)
               or (ctx["pred_cell"] == _L(post)))
    tier_ok = (ctx["pred_tier"] is None) or (ctx["pred_tier"] == tier)
    if cell_ok:
        PREDSTATS["cell_ok"] += 1
    if tier_ok:
        PREDSTATS["tier_ok"] += 1
    if not (cell_ok and tier_ok) and len(PREDSTATS["mismatch"]) < 50:
        PREDSTATS["mismatch"].append({
            "seed": CUR["seed"], "step": _step_no(self.model),
            "ff": str(getattr(self, "unit_id", "")),
            "pre": _L(pre), "post": _L(post),
            "pred_cell": ctx["pred_cell"], "pred_tier": ctx["pred_tier"],
            "tier": tier, "scored": ctx["scored"],
        })

    rec = {"seed": CUR["seed"], "step": _step_no(self.model),
           "ff": str(getattr(self, "unit_id", "")),
           "pre": _L(pre), "post": _L(post), "moved": bool(post != pre),
           "target": _L(target),
           "target_pos": _L(getattr(self, "target_pos", None)),
           "exit_target": _L(getattr(self, "exit_target", None)),
           "exiting": bool(self.exiting),
           "assigned": bool(getattr(self, "assigned", False)),
           "carrying": getattr(self, "rescued_victim", None) is not None,
           "status_pre": status_pre,
           "status_post": str(getattr(self, "status", "") or ""),
           "tier": (int(tier) if tier is not None else None),
           "risk": (int(risk) if risk is not None else None),
           "cell_ok": bool(cell_ok), "tier_ok": bool(tier_ok)}
    rec.update(ctx)
    MTCALLS.append(rec)
    _log_move(self, "move_toward", pre, post, {"tier": rec["tier"]})


def _surv(self):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    _orig_surv(self)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    _log_move(self, "survival", pre, post)


def _asr(self, fire_cells=None):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    r = _orig_asr(self, fire_cells)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    if post != pre:
        _log_move(self, "assigned_one_step", pre, post)
    return r


def _reval(self, cell, origin, fire_cells):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    r = _orig_reval(self, cell, origin, fire_cells)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    if post != pre:
        _log_move(self, "revalidate", pre, post)
    return r


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
            markers = getattr(model, "firefighter_marker_agents", {}) or {}
            for fid, m in markers.items():
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
    ap.add_argument("--arm", default="none", choices=["none"])
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
        sys.stderr.write("seed %s done: mt=%d moves=%d predok=%d/%d\n"
                         % (seed, len(MTCALLS), len(MOVES),
                            PREDSTATS["cell_ok"], PREDSTATS["n"]))
        sys.stderr.flush()
    out = {"scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "roles": a.roles, "arm": a.arm, "params": params,
           "mtcalls": MTCALLS, "moves": MOVES, "deaths": DEATHS,
           "evals": EVALS, "fftrace": FFTRACE, "predstats": PREDSTATS}
    tag = a.tag or ("%s_%s_%s_%s" % (a.scenario, a.wind, a.roles, a.arm))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_mto_%s.json" % tag)
    with open(p, "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(p)


main()
