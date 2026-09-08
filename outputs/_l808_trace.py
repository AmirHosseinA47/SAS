"""Seed-808 route_blocked latch tracer.

Read-only. Same scenario/params/RNG setup as outputs/_rblatch_campaign2.py so a
single-seed run reproduces that campaign's numbers for the same seed, plus a
BASE_STATION_MODE override so mode 0 and mode 3 can be run seed-matched.

Records, per step:
  - every firefighter marker (pos, status, assigned, exiting, dead, target_pos,
    bound victim id)
  - every victim marker (pos, status, needs_rescue)
  - every UAV (pos, battery, base_state, docked)
  - stdout lines emitted during that step
and, as events:
  - route_blocked firings, with the target and the live-BFS verdict
  - EVERY call of _revalidate_route_blocked_firefighters that had a blocked
    unit, with the exact branch each unit took (mirrored, not guessed)
  - _release_other_claimants calls and their per-unit relabel outcome
  - assigns, victim terminal transitions

usage: _l808_trace.py --seed 808 --wind east --mode 3 --tag m3
"""
from __future__ import annotations
import argparse, collections, contextlib, io as _io, json, os, random, sys, time

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation

CUR = {"step": 0, "model": None}
EVENTS: list[dict] = []
STEPS: list[dict] = []


def _cell(a):
    p = getattr(a, "pos", None)
    return [int(p[0]), int(p[1])] if p is not None else None


def _st(a):
    return str(getattr(a, "status", "") or "").strip().lower()


def _vid_of(ff):
    rv = getattr(ff, "rescued_victim", None)
    if rv is None:
        return None
    return str(getattr(rv, "victim_id", None) or getattr(rv, "unique_id", "") or "")


def ev(kind, **kw):
    d = {"step": CUR["step"], "kind": kind}
    d.update(kw)
    EVENTS.append(d)


# ---------------------------------------------------------------- hooks
_orig_mark = am.Firefighter._mark_route_blocked


def _traced_mark(self):
    before = _st(self)
    tgt = getattr(self, "target_pos", None)
    src = _cell(self)
    reach = None
    nbrs_all_fire = None
    try:
        nb = self._neighbor_cells()
        nbrs_all_fire = bool(nb) and all(self._cell_contains_active_fire(c) for c in nb)
        if tgt is not None and src is not None:
            reach = bool(self._path_exists_avoiding_fire(
                (src[0], src[1]), (int(tgt[0]), int(tgt[1])), self._fire_cells()))
    except Exception:
        pass
    _orig_mark(self)
    if _st(self) == "route_blocked" and before != "route_blocked":
        ev("route_blocked_fire", ff=str(getattr(self, "unit_id", "")), pos=src,
           target=[int(tgt[0]), int(tgt[1])] if tgt is not None else None,
           reachable=reach, neighbors_all_fire=nbrs_all_fire,
           exiting=bool(getattr(self, "exiting", False)),
           assigned=bool(getattr(self, "assigned", False)),
           bound_victim=_vid_of(self), prev_status=before)


am.Firefighter._mark_route_blocked = _traced_mark


_orig_reval = WildFireModel._revalidate_route_blocked_firefighters


def _mirror_reval(model):
    """Recompute, read-only, exactly what the pass will decide and why."""
    markers = getattr(model, "firefighter_marker_agents", None) or {}
    vmarkers = getattr(model, "victim_marker_agents", None) or {}
    per_unit = []
    blocked = []
    for ff_id, m in markers.items():
        s = _st(m)
        if s != "route_blocked":
            continue
        why = None
        if getattr(m, "dead", False):
            why = "skip:dead"
        elif getattr(m, "assigned", False):
            why = "skip:assigned"
        elif getattr(m, "exiting", False):
            why = "skip:exiting"
        elif getattr(m, "pos", None) is None:
            why = "skip:no_pos"
        if why:
            per_unit.append({"ff": str(getattr(m, "unit_id", ff_id)), "outcome": why,
                             "pos": _cell(m)})
        else:
            blocked.append((ff_id, m))
    if not blocked:
        return {"considered": 0, "per_unit": per_unit, "victim_cells": None,
                "gate": "no_eligible_blocked_unit" if per_unit else "none_blocked"}
    victim_cells = []
    victim_detail = []
    for vid, vm in vmarkers.items():
        needs = model._victim_needs_rescue(str(vid), vm)
        victim_detail.append({"vid": str(vid), "status": _st(vm), "needs": bool(needs),
                              "pos": _cell(vm)})
        if needs and getattr(vm, "pos", None) is not None:
            victim_cells.append((int(vm.pos[0]), int(vm.pos[1])))
    if not victim_cells:
        for ff_id, m in blocked:
            per_unit.append({"ff": str(getattr(m, "unit_id", ff_id)),
                             "outcome": "EARLY_RETURN:no_live_victim", "pos": _cell(m)})
        return {"considered": len(blocked), "per_unit": per_unit,
                "victim_cells": [], "victims": victim_detail,
                "gate": "EARLY_RETURN:no_live_victim"}
    fire_cells = None
    for ff_id, m in blocked:
        rec = {"ff": str(getattr(m, "unit_id", ff_id)), "pos": _cell(m)}
        try:
            if fire_cells is None:
                fire_cells = m._fire_cells()
            nb = m._neighbor_cells()
            if all(m._cell_contains_active_fire(c) for c in nb):
                rec["outcome"] = "skip:trapped_guard"
                per_unit.append(rec)
                continue
            c = (int(m.pos[0]), int(m.pos[1]))
            hits = [vc for vc in victim_cells
                    if m._path_exists_avoiding_fire(c, vc, fire_cells)]
            if not hits:
                rec["outcome"] = "skip:no_reachable_victim"
                rec["tested"] = [list(v) for v in victim_cells]
            else:
                rec["outcome"] = "CLEAR"
                rec["reached"] = [list(v) for v in hits]
        except Exception as exc:
            rec["outcome"] = "exception:%s" % type(exc).__name__
        per_unit.append(rec)
    return {"considered": len(blocked), "per_unit": per_unit,
            "victim_cells": [list(v) for v in victim_cells], "victims": victim_detail,
            "gate": "ran"}


def _traced_reval(self):
    diag = _mirror_reval(self)
    markers = getattr(self, "firefighter_marker_agents", None) or {}
    before = {k: _st(m) for k, m in markers.items()}
    _orig_reval(self)
    after = {k: _st(m) for k, m in markers.items()}
    if diag["gate"] != "none_blocked":
        changed = {k: [before[k], after[k]] for k in before if before[k] != after[k]}
        ev("reval", gate=diag["gate"], per_unit=diag["per_unit"],
           victim_cells=diag.get("victim_cells"), victims=diag.get("victims"),
           changed=changed)


WildFireModel._revalidate_route_blocked_firefighters = _traced_reval


_orig_release = WildFireModel._release_other_claimants


def _traced_release(self, victim_id, victim_marker, keep_ff_id, reason):
    markers = getattr(self, "firefighter_marker_agents", None) or {}
    before = {k: (_st(m), bool(getattr(m, "assigned", False)), _vid_of(m))
              for k, m in markers.items()}
    work_left = self._any_victim_needs_rescue()
    out = _orig_release(self, victim_id, victim_marker, keep_ff_id, reason)
    after = {k: (_st(m), bool(getattr(m, "assigned", False)), _vid_of(m))
             for k, m in markers.items()}
    ev("release_other_claimants", vid=str(victim_id), keep=str(keep_ff_id),
       reason=str(reason), released=[str(x) for x in (out or [])],
       work_left_before=bool(work_left),
       changed={k: [before[k], after[k]] for k in before if before[k] != after[k]},
       states={str(getattr(markers[k], "unit_id", k)): list(before[k]) for k in before})
    return out


WildFireModel._release_other_claimants = _traced_release


_orig_apply = WildFireModel.apply_physical_rescue_command


def _traced_apply(self, cmd):
    ok = _orig_apply(self, cmd)
    action = str(getattr(cmd, "action", "") or "").strip().lower()
    ff_id = str(getattr(cmd, "firefighter_id", "") or "")
    markers = getattr(self, "firefighter_marker_agents", None) or {}
    ff = markers.get(ff_id)
    rec = {"action": action, "ff_id": ff_id, "vid": str(getattr(cmd, "victim_id", "") or ""),
           "reason": str(getattr(cmd, "reason", "") or ""), "ok": bool(ok)}
    if ff is not None:
        rec["ff"] = str(getattr(ff, "unit_id", ff_id))
        rec["src"] = _cell(ff)
        tgt = getattr(ff, "target_pos", None)
        rec["target"] = [int(tgt[0]), int(tgt[1])] if tgt is not None else None
        rec["status_after"] = _st(ff)
        if ok and action == "assign" and rec["src"] and rec["target"]:
            try:
                rec["reachable_at_assign"] = bool(ff._path_exists_avoiding_fire(
                    tuple(rec["src"]), tuple(rec["target"]), ff._fire_cells()))
            except Exception:
                pass
    ev("rescue_cmd", **rec)
    return ok


WildFireModel.apply_physical_rescue_command = _traced_apply


# ---------------------------------------------------------------- run
def snapshot(model):
    ffs = []
    for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
        tgt = getattr(m, "target_pos", None)
        ffs.append({"id": str(getattr(m, "unit_id", fid)), "pos": _cell(m),
                    "status": _st(m), "assigned": bool(getattr(m, "assigned", False)),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "dead": bool(getattr(m, "dead", False)),
                    "target": [int(tgt[0]), int(tgt[1])] if tgt is not None else None,
                    "bound": _vid_of(m)})
    vs = []
    for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items():
        vs.append({"id": str(vid), "pos": _cell(m), "status": _st(m),
                   "needs": bool(model._victim_needs_rescue(str(vid), m))})
    uavs = []
    for a in getattr(model, "schedule", None).agents if getattr(model, "schedule", None) else []:
        if isinstance(a, am.UAV):
            uavs.append({"id": int(getattr(a, "unique_id", -1)), "pos": _cell(a),
                         "bat": round(float(getattr(a, "battery", 0.0) or 0.0), 2),
                         "base": str(getattr(a, "base_state", "") or ""),
                         "role": str(getattr(a, "role", "") or "")})
    return {"ff": ffs, "victims": vs, "uavs": uavs}


def run(seed, params, steps, tag):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    terminal_step = None
    ran = 0
    t0 = time.perf_counter()
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        CUR["model"] = model
        for s in range(1, steps + 1):
            CUR["step"] = s
            mark = buf.tell()
            model.step()
            ran = s
            buf.seek(mark)
            out_lines = [ln for ln in buf.read().splitlines() if ln.strip()]
            buf.seek(0, 2)
            snap = snapshot(model)
            snap["step"] = s
            snap["stdout"] = out_lines
            STEPS.append(snap)
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = s
        latched = []
        for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
            if _st(m) == "route_blocked" and not getattr(m, "dead", False):
                latched.append({"ff": str(getattr(m, "unit_id", fid)), "pos": _cell(m)})
        evd = _build_evaluation(model, terminal_step, ran, params)
    evd["seed"] = seed
    evd["wall_s"] = round(time.perf_counter() - t0, 1)
    return evd, latched, terminal_step


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seed", type=int, default=808)
    ap.add_argument("--mode", type=int, default=0)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--preseeds", default="")
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft,
              "BASE_STATION_MODE": a.mode}
    # optional: replay the shard's earlier seeds first, to prove no cross-seed leak
    for ps in [int(x) for x in a.preseeds.split(",") if x.strip()]:
        del EVENTS[:], STEPS[:]
        run(ps, params, a.steps, a.tag)
    del EVENTS[:], STEPS[:]
    evd, latched, terminal_step = run(a.seed, params, a.steps, a.tag)
    out = {"tag": a.tag, "seed": a.seed, "wind": a.wind, "mode": a.mode,
           "steps": a.steps, "params": params, "eval": evd, "latched": latched,
           "terminal_step": terminal_step, "events": EVENTS, "trace": STEPS}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_l808_%s.json" % a.tag)
    with open(p, "w") as f:
        json.dump(out, f, default=str)
    sys.stderr.write("%s seed=%s mode=%s rescued=%s dead=%s ff_deaths=%s "
                     "never_detected=%s latched=%s terminal=%s\n" % (
                         a.tag, a.seed, a.mode, evd.get("rescued"), evd.get("dead"),
                         evd.get("firefighter_deaths"), evd.get("never_detected"),
                         latched, terminal_step))
    print(p)


main()
