"""Where can a _firefighter_cell_risk term act at all?  Decision-level census.

The four consumers of _firefighter_cell_risk do NOT weigh it equally:

  _survival_move:799 / _revalidate_idle_retreat_stall:983 pass it as
      `current_risk`, where it appears only in the admission clause
      `risk < current_risk and dist >= current_dist`.
  _retreat_candidates:888 attaches it per candidate, where every ranking key
      puts it LAST - (dist, -risk), (improvement, dist, -risk).  It never
      outranks fire distance; it only breaks exact ties.
  _move_toward:1119 consults it ONLY in the tier-4 fallback
      `min(scored, key=(risk, dist_after, preferred))`.  Tiers 1-3 - the normal
      approach to a victim - never read risk at all.

So on the APPROACH, which is the window the three named deaths need, a risk
term is inert unless the unit is already in tier 4.  This probe counts that
directly: how many approach steps reach tier 4, how many retreat rankings hold
a scorched candidate, and how often the chosen cell was scorched while a
non-scorched alternative of equal stock risk was available - the exact
population a tiebreak-sized penalty could flip.

Runs stock behaviour; the risk function is not altered.  Read-only.
"""
from __future__ import annotations
import argparse
import contextlib
import io as _io
import json
import os
import random
import sys

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

CUR = {"seed": None}
MT = []      # every _move_toward call
RC = []      # every _retreat_candidates return
SV = []      # every _survival_move call

_o_mt = am.Firefighter._move_toward
_o_rc = am.Firefighter._retreat_candidates
_o_sv = am.Firefighter._survival_move


def scorched(self, cell):
    if self.model.grid.out_of_bounds(cell):
        return False
    for a in self.model.grid.get_cell_list_contents([cell]):
        if type(a) is not am.Fire:
            continue
        if a.is_burning() or getattr(a, "burnt", False):
            return False
        if not getattr(a, "has_burned", False):
            return False
        return float(getattr(a, "fuel", 0) or 0) > 0
    return False


def step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def mt(self, target):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    tx, ty = (int(target[0]), int(target[1])) if target else (None, None)
    cand = []
    if pre is not None and target is not None:
        for n in self._neighbor_cells():
            if self._cell_contains_active_fire(n):
                continue
            cand.append({"cell": list(n),
                         "risk": int(self._firefighter_cell_risk(n)),
                         "adj": bool(self._cell_adjacent_to_fire(n)),
                         "smoke": bool(self._cell_has_active_smoke(n)),
                         "scorched": bool(scorched(self, n)),
                         "dist_after": abs(n[0] - tx) + abs(n[1] - ty)})
    _o_mt(self, target)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    MT.append({"seed": CUR["seed"], "step": step_no(self.model),
               "unit": str(getattr(self, "unit_id", "")),
               "pre": (list(pre) if pre else None),
               "post": (list(post) if post else None),
               "moved": pre != post,
               "tier": int(getattr(self, "_last_move_tier", 0) or 0),
               "n_free": len(cand),
               "post_scorched": (bool(scorched(self, post)) if post else None),
               "cand": cand})


def rc(self, cell, origin, last_cell, fire_cells, current_dist):
    out = _o_rc(self, cell, origin, last_cell, fire_cells, current_dist)
    RC.append({"seed": CUR["seed"], "step": step_no(self.model),
               "unit": str(getattr(self, "unit_id", "")),
               "cell": list(cell), "cur_dist": int(current_dist),
               "cur_risk": int(self._firefighter_cell_risk(cell)),
               "cur_scorched": bool(scorched(self, cell)),
               "idle": (not self.target_pos) and (not self.exiting),
               "cand": [{"cell": list(c["cell"]), "risk": int(c["risk"]),
                         "dist": int(c["dist"]),
                         "improvement": int(c["improvement"]),
                         "ideal": bool(c["ideal"]), "required": bool(c["required"]),
                         "scorched": bool(scorched(self, c["cell"]))}
                        for c in out]})
    return out


def sv(self):
    pre = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    n_rc = len(RC)
    _o_sv(self)
    post = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    SV.append({"seed": CUR["seed"], "step": step_no(self.model),
               "unit": str(getattr(self, "unit_id", "")),
               "pre": (list(pre) if pre else None),
               "post": (list(post) if post else None),
               "moved": pre != post,
               "post_scorched": (bool(scorched(self, post)) if post else None),
               "rc_idx": list(range(n_rc, len(RC)))})


am.Firefighter._move_toward = mt
am.Firefighter._retreat_candidates = rc
am.Firefighter._survival_move = sv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--steps", type=int, default=240)
    a = ap.parse_args()

    preset = BUILTIN_SCENARIOS["D"]
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
    rng = random.Random(a.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    CUR["seed"] = a.seed
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(a.steps):
            model.step()
        ev = _build_evaluation(model, None, a.steps, params)

    tag = "%s_%s_%d" % (a.wind, a.roles, a.seed)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_sc_dec_%s.json" % tag)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"tag": tag, "seed": a.seed, "wind": a.wind, "roles": a.roles,
                   "eval": {k: ev.get(k) for k in
                            ("rescued", "dead", "firefighter_deaths")},
                   "mt": MT, "rc": RC, "sv": SV}, f, separators=(",", ":"))
    print(p, "mt=%d rc=%d sv=%d ff=%d"
          % (len(MT), len(RC), len(SV), ev.get("firefighter_deaths")))


main()
