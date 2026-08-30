"""Full-scene trace: every firefighter + every victim, per step, for one seed."""
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

ROWS, MARKS, DISPATCH = [], [], []

def _fire_cells(model):
    return {(int(a.pos[0]), int(a.pos[1])) for a in model.schedule.agents
            if type(a) is am.Fire and a.is_burning() and getattr(a, "pos", None)}

_orig_mark = am.Firefighter._mark_route_blocked
def _traced_mark(self):
    b = str(getattr(self, "status", "") or "")
    _orig_mark(self)
    MARKS.append({"step": int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0),
                  "ff": str(getattr(self, "unit_id", "")), "before": b,
                  "after": str(getattr(self, "status", "") or ""),
                  "pos": tuple(int(v) for v in (self.pos or (-1, -1))),
                  "target": tuple(int(v) for v in (self.target_pos or (-1, -1)))})
am.Firefighter._mark_route_blocked = _traced_mark

_orig_apply = WildFireModel.apply_physical_rescue_command
def _traced_apply(self, cmd):
    r = _orig_apply(self, cmd)
    DISPATCH.append({"step": int(getattr(self, "evaluation_timesteps_counter", 0) or 0),
                     "action": str(cmd.action), "vid": str(cmd.victim_id or ""),
                     "ff": str(cmd.firefighter_id or ""), "reason": str(cmd.reason or ""),
                     "ok": bool(r)})
    return r
WildFireModel.apply_physical_rescue_command = _traced_apply

def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
    apply_scenario_config(cfv, wf, **params)
    ts, ran = None, 0
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel(); model.debug_log = False
        for s in range(1, steps + 1):
            model.step(); ran = s
            fires = _fire_cells(model)
            ffs, vics = {}, {}
            for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                p = getattr(m, "pos", None)
                ffs[str(getattr(m, "unit_id", "") or fid)] = {
                    "pos": tuple(int(v) for v in p) if p else None,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "dead": bool(getattr(m, "dead", False)),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "target": tuple(int(v) for v in (getattr(m, "target_pos", None) or ())) or None,
                }
            for vid, vm in (getattr(model, "victim_marker_agents", {}) or {}).items():
                p = getattr(vm, "pos", None)
                try: needs = bool(model._victim_needs_rescue(str(vid), vm))
                except Exception: needs = False
                vics[str(vid)] = {"pos": tuple(int(v) for v in p) if p else None,
                                  "status": str(getattr(vm, "status", "") or ""),
                                  "needs": needs}
            ROWS.append({"step": s, "n_fire": len(fires), "ff": ffs, "vic": vics})
            if ts is None:
                if (model.get_dashboard_state().get("mission_status", {}) or {}).get("all_victims_terminal"):
                    ts = s
        ev = _build_evaluation(model, ts, ran, params)
    return ev

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", default="D"); ap.add_argument("--wind", default="east")
ap.add_argument("--seed", type=int, default=333); ap.add_argument("--steps", type=int, default=240)
ap.add_argument("--tag", default="full")
a = ap.parse_args()
preset = BUILTIN_SCENARIOS[a.scenario]; n = preset["NUM_AGENTS"]; ft = n // 2 or 1
params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
          "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
          "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
          "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft}
ev = run(a.seed, params, a.steps)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "_rblatch_full_%s_%s_%s_%s.json" % (a.tag, a.scenario, a.wind, a.seed))
json.dump({"eval": ev, "rows": ROWS, "marks": MARKS, "dispatch": DISPATCH},
          open(p, "w"), default=str)
print(p); print("eval:", {k: ev.get(k) for k in ("rescued", "dead", "firefighter_deaths")})
