"""Planner round Part 1: observe-mode probe + READ-ONLY per-step ingredient recorder.

Runs outputs/_gp_probe.py (the scoping round's probe, imported from the checkout named by
--repo, default the pinned dfbfbe7 worktree) in mode "observe" - hooks only, nothing armed -
and additionally, after every GlobalMissionPlanner.plan call, records the raw ingredients the
nine per-option values of the Part 1 design would be computed from. Nothing is written back:
every read is an attribute/dict read or a pure computation over copies; no RNG is drawn and
no model method with side effects is called. Observer purity is checked by comparing this
probe's outcome hashes with the nopatch runs of the same seeds.

Recorded per plan call ("shadow" list):
  step, utility mode, baseline score, role-option confidence, selected option id
  fire:  known burning / known front (fire_runtime_model.belief), ground-truth burning,
         known burning cells whose visibility status is stale / smoke / never-seen
  map:   visibility observation_status_map counts
  victims: victim_runtime_model statuses, managed_victims (status, confirmed), NUM_VICTIMS
  comm:  communication_model delivery_confidence and mode
  per UAV: role, pos, battery, rtb_active/docked, drift_level, role_stability_timer,
         role_switch_count, distance (manhattan and chebyshev) to the nearest known burning,
         front and never-seen cell, burning cells in its view (and only in its view), other
         UAVs within SECURITY_DISTANCE with their roles
  RECORDER v2 (added after the first Part 1 wave, for the exact section-3.7 battery_cost):
         per UAV the nearest NON-STALE believed-burning cell and the nearest never-seen cell
         as coordinates (Manhattan, ties to the lowest (x, y)); per step the OSCILLATION_RISK /
         INSTABILITY_DETECTED triggers with their affected entities (invariant I5).
"""
from __future__ import annotations
import argparse, collections, importlib.util, json, os, sys

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default="/home/user/sas_dfbfbe7")
ap.add_argument("--seed", type=int, required=True)
ap.add_argument("--wind", default="east")
ap.add_argument("--roles", choices=["half", "default"], default="half")
ap.add_argument("--steps", type=int, default=240)
ap.add_argument("--out", required=True)
a = ap.parse_args()

spec = importlib.util.spec_from_file_location(
    "_gp_probe", os.path.join(os.path.abspath(a.repo), "outputs", "_gp_probe.py"))
gp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gp)          # inserts <repo> at sys.path[0]

gp.install("observe")

from src_extension.planning import global_mission_planner as gmp   # noqa: E402
import common_fixed_variables as cfv                                # noqa: E402

SH: list = []
LAST: dict = {}
MAINTAIN_ID = "global_stability_maintain_current_config"

_orig_select = gmp._select_feasible_option


def _select(scored, options):
    out = _orig_select(scored, options)
    base = None
    mode = None
    role_conf = None
    top = []
    for i, e in enumerate(scored):
        oid = str(e.evaluation.option_id)
        if oid == MAINTAIN_ID:
            base = float(e.score)
            mode = (e.evaluation.predicted_effects or {}).get("utility_mode")
        if oid.startswith("global_role_assignment_") and role_conf is None:
            role_conf = getattr(e.option, "confidence", None)
        if i < 3:
            top.append([oid, round(float(e.score), 6)])
    LAST.clear()
    LAST.update(base=base, mode=mode, role_conf=role_conf, n_scored=len(scored),
                sel=str(getattr(out, "option_id", "") or ""), top=top)
    return out


gmp._select_feasible_option = _select

_orig_plan = gmp.GlobalMissionPlanner.plan


def _cheb(p, q):
    return max(abs(p[0] - q[0]), abs(p[1] - q[1]))


def _manh(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def _nearest(pos, cells):
    if not cells:
        return None, None
    best_m = None
    best_c = None
    for c in cells:
        m = _manh(pos, c)
        if best_m is None or m < best_m:
            best_m = m
        ch = _cheb(pos, c)
        if best_c is None or ch < best_c:
            best_c = ch
    return best_m, best_c


def _nearest_cell(pos, cells):
    """Manhattan-nearest cell, ties to the lowest (x, y); (None, None) when there is none."""
    best = None
    for c in cells:
        key = (_manh(pos, c), c[0], c[1])
        if best is None or key < best:
            best = key
    return (None, None) if best is None else ([best[1], best[2]], best[0])


def _ingredients(rm):
    m = rm["simulation_model"]
    vm = rm["visibility_model"].state
    osm = vm.observation_status_map
    status = {c: getattr(v, "value", str(v)) for c, v in osm.items()}
    cnt = collections.Counter(status.values())
    never = [c for c, s in status.items() if s == "never_seen"]
    bel = rm["fire_runtime_model"].belief
    B = [(int(c[0]), int(c[1])) for c in list(bel.estimated_burning_cells)]
    F = [(int(c[0]), int(c[1])) for c in list(bel.estimated_fire_front_cells)]
    b_status = collections.Counter(status.get(c, "none") for c in B)
    fresh = [c for c in B if status.get(c) != "stale_information"]
    gt = [tuple(int(v) for v in x.pos) for x in m.schedule.agents
          if type(x).__name__ == "Fire" and x.is_burning()]
    radius = int(getattr(cfv, "UAV_OBSERVATION_RADIUS", 8))
    secd = float(getattr(cfv, "SECURITY_DISTANCE", 10))
    uavs = sorted([x for x in m.schedule.agents if type(x).__name__ == "UAV"],
                  key=lambda x: int(x.unique_id))
    managed = getattr(m, "managed_uav_states", {}) or {}
    rmod = rm["uav_resource_model"].by_uav_id
    Bset = set(B)
    views = {}
    for u in uavs:
        px, py = int(u.pos[0]), int(u.pos[1])
        views[str(u.unique_id)] = {c for c in Bset if abs(c[0] - px) <= radius and abs(c[1] - py) <= radius}
    per = []
    for u in uavs:
        uid = str(u.unique_id)
        pos = (int(u.pos[0]), int(u.pos[1]))
        st = rmod.get(uid)
        others = set().union(*[v for k, v in views.items() if k != uid]) if len(views) > 1 else set()
        near = []
        for w in uavs:
            if w is u:
                continue
            d = ((pos[0] - w.pos[0]) ** 2 + (pos[1] - w.pos[1]) ** 2) ** 0.5
            if d <= secd:
                near.append([str(w.unique_id), getattr(managed.get(str(w.unique_id)), "role", None), round(d, 3)])
        dB = _nearest(pos, B)
        dF = _nearest(pos, F)
        dN = _nearest(pos, never)
        per.append({
            "id": uid, "role": getattr(managed.get(uid), "role", None), "pos": list(pos),
            "batt": round(float(getattr(u, "battery_level", -1.0)), 4),
            "rtb": bool(getattr(u, "rtb_active", False)), "dock": bool(getattr(u, "rtb_docked", False)),
            "drift": None if st is None or st.drift_level is None else round(float(st.drift_level), 4),
            "timer": None if st is None else round(float(st.role_stability_timer), 3),
            "nsw": None if st is None else int(st.role_switch_count),
            "dB": dB, "dF": dF, "dN": dN,
            "inview_B": len(views[uid]), "excl_B": len(views[uid] - others),
            "near": near,
            "cF": _nearest_cell(pos, fresh), "cN": _nearest_cell(pos, never),
        })
    vr = getattr(rm["victim_runtime_model"], "victims", {}) or {}
    mv = getattr(m, "managed_victims", {}) or {}
    cm = rm["communication_model"].state
    return {
        "B": len(B), "F": len(F), "gtB": len(gt), "B_status": dict(b_status),
        "vis": dict(cnt), "ncells": len(status),
        "unwatched_B": len(Bset - set().union(*views.values())) if views else len(Bset),
        "vr": {k: getattr(v, "status", None) for k, v in vr.items()},
        "mv": {k: [getattr(v, "status", None), bool(getattr(v, "confirmed", False))] for k, v in mv.items()},
        "nv": int(getattr(m, "NUM_VICTIMS", getattr(cfv, "NUM_VICTIMS", 0)) or 0),
        "comm": [cm.delivery_confidence, cm.communication_mode],
        "uav": per,
    }


def _plan(self, step_index, triggers=None, **kw):
    d = _orig_plan(self, step_index, triggers=triggers, **kw)
    rm = kw.get("runtime_models")
    try:
        rec = _ingredients(rm)
    except Exception as ex:  # pragma: no cover - recorded, never raised into the model
        rec = {"err": repr(ex)}
    rec.update(LAST)
    rec["step"] = gp.CUR["step"]
    snap = kw.get("analysis_snapshot")
    trig = []
    for t in (getattr(snap, "all_triggers", None) or ()):
        tt = str(getattr(t, "trigger_type", "") or "")
        if tt in ("OSCILLATION_RISK", "INSTABILITY_DETECTED"):
            trig.append([tt, list(getattr(t, "affected_entities", ()) or ())])
    rec["instab"] = trig
    SH.append(rec)
    return d


gmp.GlobalMissionPlanner.plan = _plan

ft, vs = (2, 2) if a.roles == "half" else (None, None)
p = gp.params(a.wind, ft, vs)
base = gp.run(a.seed, p, a.steps, track_roles=True)
res = dict(gp.REC)
res.update({"recorder": 2, "label": "D/%s/%s" % (a.wind, a.roles), "seed": a.seed, "steps": a.steps,
            "mode": "observe", "eval": base["eval"], "stdout_sha256": base["stdout_sha256"],
            "agent_positions_sha256": base["agent_positions_sha256"],
            "firemap_sha256": base["firemap_sha256"],
            "final_role_signature": base["final_role_signature"], "shadow": SH})
with open(a.out, "w", encoding="utf-8") as fh:
    json.dump(res, fh, default=str)
print("observe+shadow %s|%d evals=%d sel=%s shadow=%d" % (res["label"], a.seed, res["eval_calls"],
      json.dumps(res["selected_hist"]), len(SH)), flush=True)
