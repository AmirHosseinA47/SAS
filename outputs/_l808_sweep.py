"""Lightweight latch-frequency sweep: one (seed, mode) run per process.

Same scenario/params/RNG setup as outputs/_rblatch_campaign2.py, plus a
BASE_STATION_MODE override. Records only what is needed to COUNT and CLASSIFY
end-of-run route_blocked latches, so it is much cheaper than _l808_trace.py.

Per latched unit it records the classification the diagnosis needs:
  flag_step / flag_pos / assigned_at_flag / bound_at_flag
  unassigned_before_last_victim_terminal   (the D6-adjacent gap's signature)
  seen_by_release_helper                   (did _release_other_claimants bind it)
  enclosed_at_last_terminal / enclosed_at_end
  last_victim_terminal_step

usage: _l808_sweep.py --seed 808 --mode 3 --wind east --out <path>
Read-only w.r.t. the model.
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

CUR = {"step": 0}
FIRES: list[dict] = []
RELEASES: list[dict] = []
UNASSIGNS: list[dict] = []
STATS = collections.Counter()


def _cell(a):
    p = getattr(a, "pos", None)
    return [int(p[0]), int(p[1])] if p is not None else None


def _st(a):
    return str(getattr(a, "status", "") or "").strip().lower()


_orig_mark = am.Firefighter._mark_route_blocked


def _traced_mark(self):
    before = _st(self)
    tgt = getattr(self, "target_pos", None)
    _orig_mark(self)
    if _st(self) == "route_blocked" and before != "route_blocked":
        STATS["fires"] += 1
        nb_fire = None
        try:
            nb = self._neighbor_cells()
            nb_fire = bool(nb) and all(self._cell_contains_active_fire(c) for c in nb)
        except Exception:
            pass
        FIRES.append({"step": CUR["step"], "ff": str(getattr(self, "unit_id", "")),
                      "pos": _cell(self),
                      "target": [int(tgt[0]), int(tgt[1])] if tgt is not None else None,
                      "assigned": bool(getattr(self, "assigned", False)),
                      "enclosed": nb_fire, "prev": before})


am.Firefighter._mark_route_blocked = _traced_mark


_orig_release = WildFireModel._release_other_claimants


def _traced_release(self, victim_id, victim_marker, keep_ff_id, reason):
    markers = getattr(self, "firefighter_marker_agents", None) or {}
    blocked_before = {str(getattr(m, "unit_id", k)): {
        "assigned": bool(getattr(m, "assigned", False)),
        "bound": getattr(m, "rescued_victim", None) is not None,
        "pos": _cell(m)}
        for k, m in markers.items() if _st(m) == "route_blocked"}
    work_left = self._any_victim_needs_rescue()
    out = _orig_release(self, victim_id, victim_marker, keep_ff_id, reason)
    after = {str(getattr(m, "unit_id", k)): _st(m) for k, m in markers.items()}
    RELEASES.append({"step": CUR["step"], "vid": str(victim_id), "reason": str(reason),
                     "keep": str(keep_ff_id), "released": [str(x) for x in (out or [])],
                     "work_left_before": bool(work_left),
                     "blocked_units_at_call": blocked_before,
                     "status_after": after})
    return out


WildFireModel._release_other_claimants = _traced_release


_orig_apply = WildFireModel.apply_physical_rescue_command


def _traced_apply(self, cmd):
    ok = _orig_apply(self, cmd)
    action = str(getattr(cmd, "action", "") or "").strip().lower()
    if ok and action in ("unassign", "assign"):
        ff_id = str(getattr(cmd, "firefighter_id", "") or "")
        markers = getattr(self, "firefighter_marker_agents", None) or {}
        ff = markers.get(ff_id)
        UNASSIGNS.append({"step": CUR["step"], "action": action,
                          "ff": str(getattr(ff, "unit_id", ff_id)) if ff else ff_id,
                          "vid": str(getattr(cmd, "victim_id", "") or ""),
                          "reason": str(getattr(cmd, "reason", "") or "")})
    return ok


WildFireModel.apply_physical_rescue_command = _traced_apply


def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    terminal_step = None
    last_needs_step = None      # last step on which some victim still needed rescue
    ran = 0
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        blocked_tail = collections.Counter()
        for s in range(1, steps + 1):
            CUR["step"] = s
            model.step()
            ran = s
            if model._any_victim_needs_rescue():
                last_needs_step = s
            else:
                for k, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                    if _st(m) == "route_blocked" and not getattr(m, "dead", False):
                        blocked_tail[str(getattr(m, "unit_id", k))] += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = s
        latched = []
        for k, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
            if _st(m) != "route_blocked" or getattr(m, "dead", False):
                continue
            uid = str(getattr(m, "unit_id", k))
            enclosed = None
            try:
                nb = m._neighbor_cells()
                enclosed = bool(nb) and all(m._cell_contains_active_fire(c) for c in nb)
            except Exception:
                pass
            fires = [f for f in FIRES if f["ff"] == uid]
            last_fire = fires[-1] if fires else None
            # was it still bound to a victim at the last release call?
            seen = None
            for r in reversed(RELEASES):
                if uid in r["blocked_units_at_call"]:
                    seen = {"step": r["step"], "reason": r["reason"],
                            "released": uid in r["released"],
                            "work_left_before": r["work_left_before"],
                            "assigned": r["blocked_units_at_call"][uid]["assigned"],
                            "bound": r["blocked_units_at_call"][uid]["bound"]}
                    break
            latched.append({
                "ff": uid, "pos": _cell(m), "enclosed_at_end": enclosed,
                "flag_step": last_fire["step"] if last_fire else None,
                "flag_pos": last_fire["pos"] if last_fire else None,
                "assigned_at_flag": last_fire["assigned"] if last_fire else None,
                "enclosed_at_flag": last_fire["enclosed"] if last_fire else None,
                "last_release_sighting": seen,
                "steps_blocked_after_last_live_victim": blocked_tail.get(uid, 0),
            })
        ev = _build_evaluation(model, terminal_step, ran, params)
    ev["seed"] = seed
    ev["wall_s"] = round(time.perf_counter() - t0, 1)
    return ev, latched, terminal_step, last_needs_step


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--mode", type=int, required=True)
    ap.add_argument("--ffspawn", type=int, default=None,
                    help="BASE_STATION_SPAWN_FIREFIGHTERS override; omit to keep the default")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft,
              "BASE_STATION_MODE": a.mode}
    if a.ffspawn is not None:
        params["BASE_STATION_SPAWN_FIREFIGHTERS"] = a.ffspawn
    ev, latched, terminal_step, last_needs = run(a.seed, params, a.steps)
    out = {"seed": a.seed, "mode": a.mode, "wind": a.wind, "steps": a.steps,
           "eval": ev, "latched": latched, "terminal_step": terminal_step,
           "last_victim_needs_step": last_needs, "fires": FIRES,
           "releases": RELEASES, "assign_log": UNASSIGNS, "stats": dict(STATS)}
    with open(a.out, "w") as f:
        json.dump(out, f, default=str)
    sys.stderr.write("seed=%s mode=%s rescued=%s dead=%s ffd=%s nd=%s latched=%d %s (%ss)\n" % (
        a.seed, a.mode, ev.get("rescued"), ev.get("dead"), ev.get("firefighter_deaths"),
        ev.get("never_detected"), len(latched), [x["ff"] for x in latched], ev.get("wall_s")))
    print(a.out)


main()
