"""What-if probe for the idle-retreat latch + leash fix.

NOTHING on disk is edited. The proposed logic lives here as a monkeypatch so
the design can be tested before agents.py is touched.

Modes:
  --mode observe  : run STOCK behaviour; at every latched idle _survival_move
                    call, additionally compute (without applying) what the
                    proposed code would decide. Trajectory identical to
                    baseline, so it is directly comparable to the baseline
                    trace.
  --mode apply    : install the proposed _survival_move and run. Trajectory
                    diverges - this is the side-effect check.
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
from serve_dashboard import BUILTIN_SCENARIOS, _resolve_role_count_params

MAXC = am.IDLE_RETREAT_MAX_CELLS
CUR = {"seed": None}
# which halves of the fix are live: "latch" = 4a, "leash" = 4b
PIECES = {"latch": True, "leash": True}
DECIS = []     # per-call decision records (observe mode)
FFTRACE = []
DEATHS = []
MOVELOG = []   # every position change, for oscillation analysis (apply mode)


# --------------------------------------------------------------------------
# The PROPOSED logic, written exactly as it is intended to land in agents.py.
# --------------------------------------------------------------------------
def _retreat_candidates(self, cell, origin, last_cell, fire_cells, current_dist):
    candidates = []
    for ncell in self._neighbor_cells():
        if self._cell_contains_active_fire(ncell):
            continue
        if ncell == last_cell:
            continue
        from_origin = abs(ncell[0] - origin[0]) + abs(ncell[1] - origin[1])
        if from_origin > MAXC:
            continue
        risk = self._firefighter_cell_risk(ncell)
        new_dist = self._min_fire_distance(ncell, fire_cells)
        candidates.append({
            "cell": ncell, "risk": risk, "dist": new_dist,
            "improvement": new_dist - current_dist,
            "ideal": self._cell_is_ideal_idle_standoff(ncell, fire_cells),
            "required": self._cell_meets_required_idle_safety(ncell, fire_cells),
        })
    return candidates


def _pick_improving_retreat(self, candidates, current_dist, current_risk):
    ideal_reachable = [c for c in candidates if c["ideal"]]
    if ideal_reachable:
        return max(ideal_reachable, key=lambda c: (c["dist"], -int(c["risk"])))
    improving = [
        c for c in candidates
        if int(c["improvement"]) > 0
        or (int(c["risk"]) < current_risk and int(c["dist"]) >= current_dist)
    ]
    if improving:
        return max(improving, key=lambda c: (
            int(c["improvement"]), int(c["dist"]), -int(c["risk"])))
    return None


def _revalidate(self, cell, fire_cells, origin):
    """Proposed replacement for the bare `return` on the latched idle path."""
    last_cell = getattr(self, "_idle_retreat_last_cell", None)
    current_dist = self._min_fire_distance(cell, fire_cells)
    current_risk = self._firefighter_cell_risk(cell)
    cands = _retreat_candidates(self, cell, origin, last_cell, fire_cells, current_dist)
    chosen = _pick_improving_retreat(self, cands, current_dist, current_risk)
    if chosen is None:
        return None
    target = chosen["cell"]
    steps = int(getattr(self, "_idle_retreat_steps", 0) or 0)
    self._idle_retreat_last_cell = cell
    self.model.grid.move_agent(self, target)
    self._idle_retreat_steps = steps + 1
    # Clear ONLY the stall flag. Deliberately not `_reset_idle_retreat_state()`:
    # that would also drop `_idle_retreat_last_cell`, the anti-oscillation
    # memory, on the very path that is being added. The leash anchor and the
    # step budget stay as they are; the existing reset sites (the standby
    # branch, the ideal-standoff check, the at-cap arm) still fire normally
    # once the unit is actually safe.
    self._idle_retreat_stalled = False
    return target


_stock_surv = am.Firefighter._survival_move


def _proposed_survival_move(self):
    if self.pos is None:
        return
    cell = (int(self.pos[0]), int(self.pos[1]))
    fire_cells = self._fire_cells()

    if self._cell_is_ideal_idle_standoff(cell, fire_cells):
        self._reset_idle_retreat_state()
        return

    origin = getattr(self, "_idle_retreat_origin", None)
    # CHANGE 4b: re-anchor a provably stale origin. IDLE UNITS ONLY - for an
    # assigned unit `_assigned_one_step_retreat` moves without a leash test,
    # so d > MAXC is normal there and proves nothing.
    if origin is None or (
        PIECES["leash"]
        and not self.target_pos
        and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) > MAXC
    ):
        self._idle_retreat_origin = cell
        self._idle_retreat_steps = 0
        self._idle_retreat_stalled = False
        self._idle_retreat_last_cell = None
        origin = cell

    # CHANGE 4a: revalidate instead of trusting the flag.
    if bool(getattr(self, "_idle_retreat_stalled", False)):
        if self.target_pos:
            self._assigned_one_step_retreat(fire_cells)
            return
        if PIECES["latch"]:
            _revalidate(self, cell, fire_cells, origin)
        return

    steps = int(getattr(self, "_idle_retreat_steps", 0) or 0)
    at_cap = steps >= MAXC
    current_dist = self._min_fire_distance(cell, fire_cells)
    current_risk = self._firefighter_cell_risk(cell)
    last_cell = getattr(self, "_idle_retreat_last_cell", None)

    candidates = _retreat_candidates(
        self, cell, origin, last_cell, fire_cells, current_dist)

    if not candidates:
        if self.target_pos and self._assigned_one_step_retreat(fire_cells):
            return
        self._idle_retreat_stalled = True
        return

    chosen = None
    if not at_cap:
        chosen = _pick_improving_retreat(self, candidates, current_dist, current_risk)
        if chosen is None:
            chosen = max(candidates, key=lambda c: (int(c["dist"]), -int(c["risk"])))
            if not self.target_pos:
                self._idle_retreat_stalled = True
    else:
        required_reachable = [c for c in candidates if c["required"]]
        if required_reachable:
            chosen = max(required_reachable,
                         key=lambda c: (int(c["dist"]), -int(c["risk"])))
            if not self.target_pos:
                self._reset_idle_retreat_state()
        else:
            chosen = max(candidates, key=lambda c: (int(c["dist"]), -int(c["risk"])))
            if not self.target_pos:
                self._idle_retreat_stalled = True

    if chosen is None:
        if self.target_pos and self._assigned_one_step_retreat(fire_cells):
            return
        self._idle_retreat_stalled = True
        return

    target = chosen["cell"]
    if target == cell:
        if self.target_pos and self._assigned_one_step_retreat(fire_cells):
            return
        self._idle_retreat_stalled = True
        return

    self._idle_retreat_last_cell = cell
    self.model.grid.move_agent(self, target)
    self._idle_retreat_steps = steps + 1

    if self._cell_is_ideal_idle_standoff(target, self._fire_cells()):
        self._reset_idle_retreat_state()
    elif self._cell_meets_required_idle_safety(target, self._fire_cells()) and (
        (at_cap or self._idle_retreat_stalled) and not self.target_pos
    ):
        self._reset_idle_retreat_state()


# --------------------------------------------------------------------------
# Instrumentation
# --------------------------------------------------------------------------
def _mfd(cell, fires):
    if not fires:
        return 999
    return min(abs(cell[0] - f[0]) + abs(cell[1] - f[1]) for f in fires)


def _observe_wrapper(self):
    """Stock behaviour, plus a non-applied read of what the fix would decide."""
    rec = None
    if self.pos is not None:
        cell = (int(self.pos[0]), int(self.pos[1]))
        fires = self._fire_cells()
        idle = (not self.target_pos) and (not self.exiting)
        latched = bool(getattr(self, "_idle_retreat_stalled", False))
        origin = getattr(self, "_idle_retreat_origin", None)
        ideal_now = self._cell_is_ideal_idle_standoff(cell, fires)
        if idle and latched and not ideal_now:
            org = tuple(origin) if origin else cell
            d_org = abs(cell[0] - org[0]) + abs(cell[1] - org[1])
            stale = d_org > MAXC
            eff_origin = cell if stale else org
            eff_last = None if stale else getattr(self, "_idle_retreat_last_cell", None)
            cur_d = _mfd(cell, fires)
            cur_r = self._firefighter_cell_risk(cell)
            cands = _retreat_candidates(self, cell, eff_origin, eff_last, fires, cur_d)
            # after a re-anchor the latch is cleared, so the NORMAL path runs
            if stale:
                pick = _pick_improving_retreat(self, cands, cur_d, cur_r)
                if pick is None and cands:
                    pick = max(cands, key=lambda c: (int(c["dist"]), -int(c["risk"])))
                path = "reanchor_then_normal"
            else:
                pick = _pick_improving_retreat(self, cands, cur_d, cur_r)
                path = "revalidate"
            nb = self._neighbor_cells()
            free = [c for c in nb if not self._cell_contains_active_fire(c)]
            rec = {
                "seed": CUR["seed"],
                "step": int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0),
                "ff": str(getattr(self, "unit_id", "")),
                "pos": list(cell), "origin": (list(org) if origin else None),
                "d_origin": d_org, "stale_origin": stale, "path": path,
                "cur_dist": cur_d, "cur_risk": cur_r,
                "n_inbounds": len(nb), "n_free": len(free),
                "n_candidates": len(cands),
                "would_move": pick is not None,
                "would_target": (list(pick["cell"]) if pick else None),
                "would_dist": (int(pick["dist"]) if pick else None),
                "would_risk": (int(pick["risk"]) if pick else None),
                "would_ideal": (bool(pick["ideal"]) if pick else None),
                "dist_gain": (int(pick["dist"]) - cur_d if pick else None),
                "risk_gain": (cur_r - int(pick["risk"]) if pick else None),
                "on_fire": self._cell_contains_active_fire(cell),
            }
    _stock_surv(self)
    if rec is not None:
        rec["stock_moved"] = (
            (int(self.pos[0]), int(self.pos[1])) != tuple(rec["pos"])
            if self.pos else None
        )
        DECIS.append(rec)


def _apply_wrapper(self):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    latched = bool(getattr(self, "_idle_retreat_stalled", False))
    idle = (not self.target_pos) and (not self.exiting)
    fires = self._fire_cells()
    pre_d = _mfd(pre, fires) if pre else None
    _proposed_survival_move(self)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    if pre is not None and post is not None and post != pre:
        MOVELOG.append({
            "seed": CUR["seed"],
            "step": int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0),
            "ff": str(getattr(self, "unit_id", "")),
            "src": list(pre), "dst": list(post), "idle": idle,
            "latched_pre": latched,
            "pre_dist": pre_d, "post_dist": _mfd(post, self._fire_cells()),
        })


def _fires(model):
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
            fires = _fires(model)
            markers = getattr(model, "firefighter_marker_agents", {}) or {}
            for fid, m in markers.items():
                d = bool(getattr(m, "dead", False))
                pos = getattr(m, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                mr = getattr(m, "movement_reason", None) or {}
                row = {
                    "seed": seed, "step": s, "ff": fid,
                    "pos": (list(cell) if cell else None), "dead": d,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "target": (list(m.target_pos)
                               if getattr(m, "target_pos", None) else None),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                    "origin": (list(getattr(m, "_idle_retreat_origin", None))
                               if getattr(m, "_idle_retreat_origin", None) else None),
                    "cat": str(mr.get("category", "")),
                    "mfd": (_mfd(cell, fires) if cell else None),
                }
                if cell is not None and not d:
                    nb = m._neighbor_cells()
                    row["n_free"] = sum(
                        1 for n in nb if not m._cell_contains_active_fire(n))
                FFTRACE.append(row)
                if fid not in alive:
                    alive[fid] = d
                elif d and not alive[fid]:
                    DEATHS.append({"seed": seed, "step": s, "ff": fid,
                                   "pos": (list(cell) if cell else None),
                                   "stalled": row["stalled"], "cat": row["cat"]})
                alive[fid] = d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["observe", "apply"], required=True)
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--seeds", default="101")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--tag", default="")
    ap.add_argument("--pieces", default="both",
                    choices=["both", "latch", "leash", "none"],
                    help="which halves of the fix to install (apply mode)")
    a = ap.parse_args()

    PIECES["latch"] = a.pieces in ("both", "latch")
    PIECES["leash"] = a.pieces in ("both", "leash")

    if a.mode == "observe":
        am.Firefighter._survival_move = _observe_wrapper
    else:
        am.Firefighter._survival_move = _apply_wrapper

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
        sys.stderr.write("seed %s done: deaths=%d decisions=%d moves=%d\n"
                         % (seed, len(DEATHS), len(DECIS), len(MOVELOG)))
        sys.stderr.flush()
    tag = a.tag or ("%s_%s_%s_%s" % (a.mode, a.scenario, a.wind, a.roles))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_ir_wi_%s.json" % tag)
    with open(p, "w") as f:
        json.dump({"mode": a.mode, "wind": a.wind, "roles": a.roles,
                   "seeds": a.seeds, "steps": a.steps, "params": params,
                   "decisions": DECIS, "deaths": DEATHS,
                   "fftrace": FFTRACE, "movelog": MOVELOG},
                  f, separators=(",", ":"), default=str)
    print(p)


main()
