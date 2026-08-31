"""route_blocked unassign-inflow instrumentation.

Read-only: patches nothing on disk, only wraps methods at runtime in-process.
Derived from outputs/_ir_probe3.py (idle-retreat round) with the release-point
instrumentation this round needs added:

  * every Firefighter._move_toward call, with the two route_blocked trigger
    conditions evaluated separately AT ENTRY:
      - scored_empty : every in-bounds neighbour burning (the "if not scored:"
                       branch -> unassign happens and NO move is possible)
      - no_bfs_path  : route_blocked_now -> BFS says target unreachable, but
                       free neighbours remain (unassign happens and the call
                       KEEPS GOING and moves the unit)
  * every Firefighter._mark_route_blocked firing, with the full release-moment
    posture of the unit
  * every apply_physical_rescue_command assign/unassign, tagged with the
    _move_toward call it happened inside, so route_blocked-triggered unassigns
    can be separated from victim_dead / casualty recalls
  * per-step per-FF trace incl. required-idle-safety + adjacency + enclosure,
    so the post-release trajectory (died / escaped / when) is reconstructable.
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
SURV = []        # every _survival_move call
FFTRACE = []     # per-step per-FF snapshot
DEATHS = []
LIFECYCLE = []   # assign / unassign / recycle events
MOVES = []       # interesting _move_toward calls
RB = []          # every _mark_route_blocked firing
EVALS = []
MT_STACK = []    # active _move_toward contexts
_MT_SEQ = [0]


def _step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def _mfd(cell, fires):
    if not fires:
        return 999
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


def _posture(ff, fires):
    """Everything the model could know about this unit's cell right now."""
    cell = (int(ff.pos[0]), int(ff.pos[1]))
    nb = ff._neighbor_cells()
    free = [c for c in nb if not ff._cell_contains_active_fire(c)]
    safe = [c for c in free if ff._cell_meets_required_idle_safety(c, fires)]
    ideal = [c for c in free if ff._cell_is_ideal_idle_standoff(c, fires)]
    cur = _mfd(cell, fires)
    best = max((_mfd(c, fires) for c in free), default=None)
    return {
        "pos": list(cell),
        "mfd": cur,
        "n_inbounds": len(nb),
        "n_free": len(free),
        "n_safe": len(safe),
        "n_ideal": len(ideal),
        "enclosed": len(free) == 0,   # the C1 / "all neighbours burning" test
        "best_free_mfd": best,
        "strictly_better_exists": (best is not None and best > cur),
        "on_fire": ff._cell_contains_active_fire(cell),
        "smoke": ff._cell_has_active_smoke(cell),
        "adj_fire": ff._cell_adjacent_to_fire(cell),
        "cell_safe": ff._cell_meets_required_idle_safety(cell, fires),
        "free_cells": [list(c) for c in free],
    }


# ---------------------------------------------------------------- _move_toward
_orig_mt = am.Firefighter._move_toward


def _mt(self, target):
    model = self.model
    fires = self._fire_cells()
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    _MT_SEQ[0] += 1
    mid = _MT_SEQ[0]
    rec = {
        "mid": mid, "seed": CUR["seed"], "step": _step_no(model),
        "ff": str(getattr(self, "unit_id", "")),
        "target": [int(target[0]), int(target[1])],
        "exiting": bool(self.exiting),
        "assigned": bool(getattr(self, "assigned", False)),
        "carrying": getattr(self, "rescued_victim", None) is not None,
        "status_pre": str(getattr(self, "status", "") or ""),
        "rb_events": [], "unassigns": [],
    }
    if pre is not None:
        rec.update(_posture(self, fires))
        # exactly the two conditions inside _move_toward
        rec["scored_empty"] = rec["n_free"] == 0
        rec["no_bfs_path"] = (
            (not self.exiting)
            and not self._path_exists_avoiding_fire(
                pre, (int(target[0]), int(target[1])), fires)
        )
    MT_STACK.append(rec)
    try:
        _orig_mt(self, target)
    finally:
        MT_STACK.pop()
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    post_fires = self._fire_cells()
    rec["post_pos"] = list(post) if post else None
    rec["moved"] = post != pre
    rec["post_mfd"] = _mfd(post, post_fires) if post else None
    rec["post_adj_fire"] = self._cell_adjacent_to_fire(post) if post else None
    rec["post_on_fire"] = self._cell_contains_active_fire(post) if post else None
    rec["post_safe"] = (
        self._cell_meets_required_idle_safety(post, post_fires) if post else None)
    rec["status_post"] = str(getattr(self, "status", "") or "")
    # only the interesting ones; a full trace is order 1e6 rows
    if (rec.get("no_bfs_path") or rec.get("scored_empty")
            or rec["rb_events"] or rec["unassigns"]):
        MOVES.append(rec)


am.Firefighter._move_toward = _mt


# --------------------------------------------------------- _mark_route_blocked
_orig_mrb = am.Firefighter._mark_route_blocked


def _mrb(self):
    already = str(getattr(self, "status", "") or "").strip().lower() == "route_blocked"
    fires = self._fire_cells()
    rec = {
        "seed": CUR["seed"], "step": _step_no(self.model),
        "ff": str(getattr(self, "unit_id", "")),
        "already_blocked": already,
        "fired": not already,
        "assigned": bool(getattr(self, "assigned", False)),
        "exiting": bool(self.exiting),
        "carrying": getattr(self, "rescued_victim", None) is not None,
        "target": (list(self.target_pos) if getattr(self, "target_pos", None) else None),
        "mid": (MT_STACK[-1]["mid"] if MT_STACK else None),
    }
    if self.pos is not None:
        rec.update(_posture(self, fires))
    if MT_STACK:
        MT_STACK[-1]["rb_events"].append(len(RB))
    RB.append(rec)
    _orig_mrb(self)


am.Firefighter._mark_route_blocked = _mrb


# ------------------------------------------------------------------- lifecycle
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


def _dispatch_reachability(model, ffm, victim_cell):
    """At ASSIGN time: was the chosen unit's route already blocked, and did any
    OTHER dispatchable unit have an open route to the same victim?

    This is the measurement Part 2 step 6 turns on: if the chosen unit's route
    is open at commitment, no upstream reachability gate could have prevented
    the later route_blocked; if it is closed AND a rival's is open, a
    reachability-aware pairing would have picked differently.
    """
    if victim_cell is None or getattr(ffm, "pos", None) is None:
        return {}
    fires = ffm._fire_cells()
    src = (int(ffm.pos[0]), int(ffm.pos[1]))
    chosen_open = ffm._path_exists_avoiding_fire(src, victim_cell, fires)
    alt_open, alt_blocked, alt = 0, 0, []
    for oid, om in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
        if om is ffm or getattr(om, "pos", None) is None:
            continue
        if not model._firefighter_available_for_dispatch(om):
            continue
        osrc = (int(om.pos[0]), int(om.pos[1]))
        ok = om._path_exists_avoiding_fire(osrc, victim_cell, fires)
        dist = abs(osrc[0] - victim_cell[0]) + abs(osrc[1] - victim_cell[1])
        alt.append({"ff": str(getattr(om, "unit_id", oid)), "open": bool(ok),
                    "dist": dist})
        if ok:
            alt_open += 1
        else:
            alt_blocked += 1
    return {
        "dsp_route_open": bool(chosen_open),
        "dsp_dist": abs(src[0] - victim_cell[0]) + abs(src[1] - victim_cell[1]),
        "dsp_alt_open": alt_open,
        "dsp_alt_blocked": alt_blocked,
        "dsp_alts": alt,
        "dsp_victim_cell": list(victim_cell),
    }


def _cmd(self, command):
    action = str(getattr(command, "action", "") or "")
    ff_id = str(getattr(command, "firefighter_id", "") or "")
    ffm = (getattr(self, "firefighter_marker_agents", {}) or {}).get(ff_id)
    rec = None
    if action in ("assign", "unassign") and ffm is not None:
        fires = ffm._fire_cells() if getattr(ffm, "pos", None) is not None else set()
        rec = {
            "seed": CUR["seed"], "step": _step_no(self), "kind": action,
            "ff": str(getattr(ffm, "unit_id", ff_id) or ff_id),
            "ff_id": ff_id,
            "victim": str(getattr(command, "victim_id", "") or ""),
            "reason": str(getattr(command, "reason", "") or ""),
            "mid": (MT_STACK[-1]["mid"] if MT_STACK else None),
            "in_move_toward": bool(MT_STACK),
            "status_pre": str(getattr(ffm, "status", "") or ""),
            "assigned_pre": bool(getattr(ffm, "assigned", False)),
            "exiting_pre": bool(getattr(ffm, "exiting", False)),
            "carrying_pre": getattr(ffm, "rescued_victim", None) is not None,
            "target_pre": (list(ffm.target_pos)
                           if getattr(ffm, "target_pos", None) else None),
        }
        if getattr(ffm, "pos", None) is not None:
            rec.update({("rel_" + k): v for k, v in _posture(ffm, fires).items()})
        if action == "assign":
            meta = dict(getattr(command, "metadata", None) or {})
            vpos = meta.get("target_pos")
            vm = meta.get("victim_marker")
            if vpos is None and vm is None:
                vms = getattr(self, "victim_marker_agents", None)
                if isinstance(vms, dict):
                    vm = vms.get(str(getattr(command, "victim_id", "") or ""))
            if vpos is None and vm is not None:
                vpos = getattr(vm, "pos", None)
            vcell = ((int(vpos[0]), int(vpos[1])) if vpos is not None else None)
            try:
                rec.update(_dispatch_reachability(self, ffm, vcell))
            except Exception:
                pass
        if MT_STACK:
            MT_STACK[-1]["unassigns"].append(len(LIFECYCLE))
    ok = _orig_cmd(self, command)
    if rec is not None:
        rec["ok"] = bool(ok)
        rec["status_post"] = str(getattr(ffm, "status", "") or "")
        rec["target_post"] = (list(ffm.target_pos)
                              if getattr(ffm, "target_pos", None) else None)
        LIFECYCLE.append(rec)
    return ok


wf.WildFireModel.apply_physical_rescue_command = _cmd


# ---------------------------------------------------------- _survival_move tap
_orig_surv = am.Firefighter._survival_move


def _surv(self):
    model = self.model
    fires = self._fire_cells()
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    rec = {
        "step": _step_no(model), "seed": CUR["seed"],
        "ff": str(getattr(self, "unit_id", "")),
        "idle": (not self.target_pos) and (not self.exiting),
        "stalled_pre": bool(getattr(self, "_idle_retreat_stalled", False)),
    }
    if pre is not None:
        rec.update(_posture(self, fires))
    _orig_surv(self)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    rec.update({
        "post_pos": list(post) if post else None,
        "moved": post != pre,
        "stalled_post": bool(getattr(self, "_idle_retreat_stalled", False)),
        "post_mfd": _mfd(post, self._fire_cells()) if post else None,
    })
    SURV.append(rec)


am.Firefighter._survival_move = _surv


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
            ffm = getattr(model, "firefighter_marker_agents", {}) or {}
            for fid, m in ffm.items():
                d = bool(getattr(m, "dead", False))
                pos = getattr(m, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                mr = getattr(m, "movement_reason", None) or {}
                row = {
                    "seed": seed, "step": s, "ff": str(getattr(m, "unit_id", fid)),
                    "ff_id": fid,
                    "pos": (list(cell) if cell else None),
                    "dead": d,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "target": (list(m.target_pos)
                               if getattr(m, "target_pos", None) else None),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "carrying": getattr(m, "rescued_victim", None) is not None,
                    "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                    "cat": str(mr.get("category", "")),
                    "mfd": (_mfd(cell, fires) if cell else None),
                }
                if cell is not None and not d:
                    nb = m._neighbor_cells()
                    free = [n for n in nb if not m._cell_contains_active_fire(n)]
                    row["n_inb"] = len(nb)
                    row["n_free"] = len(free)
                    row["enclosed"] = len(free) == 0
                    row["adj_fire"] = m._cell_adjacent_to_fire(cell)
                    row["cell_safe"] = m._cell_meets_required_idle_safety(cell, fires)
                FFTRACE.append(row)
                if fid not in alive:
                    alive[fid] = d
                elif d and not alive[fid]:
                    DEATHS.append({
                        "seed": seed, "step": s,
                        "ff": str(getattr(m, "unit_id", fid)), "ff_id": fid,
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
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--tag", default="")
    ap.add_argument("--prefix", default="_ui_p1")
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
        sys.stderr.write("seed %s done: %d deaths, %d rb, %d mt\n"
                         % (seed, len(DEATHS), len(RB), len(MOVES)))
        sys.stderr.flush()
    out = {"scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "roles": a.roles, "params": params,
           "deaths": DEATHS, "surv": SURV, "fftrace": FFTRACE,
           "evals": EVALS, "lifecycle": LIFECYCLE, "moves": MOVES, "rb": RB,
           "consts": {"IDLE_RETREAT_SAFETY_BUFFER": am.IDLE_RETREAT_SAFETY_BUFFER,
                      "IDLE_RETREAT_MAX_CELLS": am.IDLE_RETREAT_MAX_CELLS}}
    tag = a.tag or ("%s_%s_%s" % (a.scenario, a.wind, a.roles))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "%s_%s.json" % (a.prefix, tag))
    with open(p, "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(p)


main()
