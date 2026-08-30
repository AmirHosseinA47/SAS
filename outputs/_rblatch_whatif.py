"""WHAT-IF probe (no source edits): from step N, externally clear a latched
unit's route_blocked when a live path to a needy victim exists, and see whether
the EXISTING dispatch machinery ever picks it up.

Tests three escalating interventions so we learn the minimum sufficient hook:
  mode=clear      : only clear the flag (+ restore availability)
  mode=clear_kick : clear + call _try_dispatch_unresolved_confirmed_victims()
  mode=none       : baseline, no intervention
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
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation

LOG, DISPATCH = [], []

def _fire_cells(model):
    return {(int(a.pos[0]), int(a.pos[1])) for a in model.schedule.agents
            if type(a) is am.Fire and a.is_burning() and getattr(a, "pos", None)}

_orig_apply = WildFireModel.apply_physical_rescue_command
def _traced_apply(self, cmd):
    r = _orig_apply(self, cmd)
    DISPATCH.append({"step": int(getattr(self, "evaluation_timesteps_counter", 0) or 0),
                     "action": str(cmd.action), "vid": str(cmd.victim_id or ""),
                     "ff": str(cmd.firefighter_id or ""), "reason": str(cmd.reason or ""),
                     "ok": bool(r)})
    return r
WildFireModel.apply_physical_rescue_command = _traced_apply


def run(seed, params, steps, mode):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
    apply_scenario_config(cfv, wf, **params)
    ts, ran = None, 0
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel(); model.debug_log = False
        for s in range(1, steps + 1):
            model.step(); ran = s
            fires = _fire_cells(model)
            managed = getattr(model, "managed_victims", {}) or {}
            vms = getattr(model, "victim_marker_agents", {}) or {}
            # record victim confirmation state
            if s in (46, 60, 100, 150, 200, 240):
                LOG.append({"kind": "victims", "step": s, "data": {
                    str(v): {"marker": str(getattr(m, "status", "") or ""),
                             "confirmed": bool(getattr(managed.get(v), "confirmed", False)),
                             "state_status": str(getattr(managed.get(v), "status", "") or ""),
                             "needs": bool(model._victim_needs_rescue(str(v), m))}
                    for v, m in vms.items()}})
            if mode == "none":
                continue
            for fid, ff in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                if str(getattr(ff, "status", "") or "").strip().lower() != "route_blocked":
                    continue
                if getattr(ff, "dead", False) or getattr(ff, "pos", None) is None:
                    continue
                cell = (int(ff.pos[0]), int(ff.pos[1]))
                ok = []
                for vid, vm in vms.items():
                    if not model._victim_needs_rescue(str(vid), vm):
                        continue
                    p = getattr(vm, "pos", None)
                    if p is None:
                        continue
                    if ff._path_exists_avoiding_fire(cell, (int(p[0]), int(p[1])), fires):
                        ok.append(str(vid))
                if not ok:
                    continue
                ff.status = "assigned" if getattr(ff, "assigned", False) else "available"
                st = (getattr(model, "managed_firefighters", {}) or {}).get(fid)
                if st is not None:
                    try:
                        st.route_state = "idle"; st.availability = "available"
                    except Exception:
                        pass
                LOG.append({"kind": "cleared", "step": s, "ff": str(getattr(ff, "unit_id", fid)),
                            "pos": cell, "reachable": ok})
                if mode == "clear_kick":
                    try:
                        model._try_dispatch_unresolved_confirmed_victims()
                    except Exception as e:
                        LOG.append({"kind": "kick_error", "step": s, "err": repr(e)})
            if ts is None:
                if (model.get_dashboard_state().get("mission_status", {}) or {}).get("all_victims_terminal"):
                    ts = s
        ev = _build_evaluation(model, ts, ran, params)
    return ev

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", default="D"); ap.add_argument("--wind", default="east")
ap.add_argument("--seed", type=int, default=333); ap.add_argument("--steps", type=int, default=240)
ap.add_argument("--mode", default="clear")
a = ap.parse_args()
preset = BUILTIN_SCENARIOS[a.scenario]; n = preset["NUM_AGENTS"]; ft = n // 2 or 1
params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
          "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
          "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
          "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft}
ev = run(a.seed, params, a.steps, a.mode)
print("MODE=%s eval=%s" % (a.mode, {k: ev.get(k) for k in ("rescued","dead","firefighter_deaths")}))
cl = [l for l in LOG if l["kind"] == "cleared"]
print("clears: %d  (first %s)" % (len(cl), cl[0] if cl else None))
print("dispatch cmds after step 45:", [d for d in DISPATCH if d["step"] > 45][:20])
for l in LOG:
    if l["kind"] == "victims":
        print(" victims @%3d %s" % (l["step"], {k: (v["marker"], v["confirmed"], v["needs"]) for k, v in l["data"].items()}))
    elif l["kind"] == "kick_error":
        print(" KICK ERROR", l)
