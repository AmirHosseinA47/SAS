"""Defect #9-A1 A/B: does a scorched-ground risk term move firefighter deaths?

"Scorched" = has_burned AND NOT burnt AND NOT burning AND fuel > 0: ground that
has already been through the fire but still holds fuel, so probability_of_fire()
is still live for it. The codebase has no name for this state and
_firefighter_cell_risk scores it identically to virgin green ground.

--arm selects a runtime-only variant. NOTHING is written to source.
    stock  HEAD e02377b untouched - no monkeypatch of any kind (provenance)
    none   the arm harness with penalty 0 - must be bit-identical to stock
    a      +1  : one rung BELOW the lowest existing rung (smoke, +10) on the
                 1_000_000 / 100 / 10 ladder the model already uses. Pure
                 tiebreak: it can never reorder a smoke-vs-clean or an
                 adjacent-vs-clear decision, only decisions where those
                 present-tense terms already tie.
    b      +10 : equal to the smoke term. Re-ignition risk treated as roughly
                 equivalent to current smoke presence, and able to reorder
                 against smoke.
    c      +100: the next rung UP - equal to the fire-adjacency term. Added
                 after a and b came out trajectory-identical on all 23 runs,
                 which means the a/b pair separated no magnitudes at all: every
                 decision the term touched was a tie between cells of equal
                 stock risk, where any positive penalty below the adjacency rung
                 gives the same ordering. Without a third point at a rung that
                 CAN reorder against the present-tense terms, the round would
                 have tested one effective magnitude while reporting two.

Records per run: outcomes, deaths with the ground type died on, per-step
firefighter ground-type occupancy (burnt / scorched / burning / green - the last
of these is the DISPLACEMENT check), moves onto each ground type, how often the
scorched term was non-zero at all (opportunity count, measured in every arm
including the controls), and a per-step signature over burning cells +
firefighter positions + UAV positions for exact trajectory comparison.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
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

PENALTY = {"stock": None, "none": 0, "a": 1, "b": 10, "c": 100}
CUR = {"arm": "stock", "seed": None, "pen": 0}
CNT = {"risk_calls": 0, "risk_calls_scorched": 0, "risk_calls_scorched_applied": 0}

_orig_risk = am.Firefighter._firefighter_cell_risk


def _cell_is_scorched(self, cell) -> bool:
    """Ground that has already burned once and still holds fuel.

    Reads only what a Fire agent already carries, through the same
    grid.get_cell_list_contents / type(agent) is Fire path the three existing
    cell predicates use. Needs no model or grid reference beyond self.model.grid,
    which _firefighter_cell_risk already has.
    """
    if self.model.grid.out_of_bounds(cell):
        return False
    try:
        contents = self.model.grid.get_cell_list_contents([cell])
    except Exception:
        return False
    for agent in contents:
        if type(agent) is not am.Fire:
            continue
        if agent.is_burning():
            return False
        if getattr(agent, "burnt", False):
            return False
        if not getattr(agent, "has_burned", False):
            return False
        return float(getattr(agent, "fuel", 0) or 0) > 0
    return False


def _risk_armed(self, cell):
    """Exactly the source edit under test, with the penalty as a parameter."""
    CNT["risk_calls"] += 1
    if self._cell_contains_active_fire(cell):
        return 1_000_000
    risk = 0
    if self._cell_adjacent_to_fire(cell):
        risk += 100
    if self._cell_has_active_smoke(cell):
        risk += 10
    if _cell_is_scorched(self, cell):
        CNT["risk_calls_scorched"] += 1
        pen = CUR["pen"]
        if pen:
            CNT["risk_calls_scorched_applied"] += 1
            risk += pen
    return risk


def _classify(fires):
    burning, burnt, scorched = set(), set(), set()
    for c, a in fires.items():
        if a.is_burning():
            burning.add(c)
        elif getattr(a, "burnt", False):
            burnt.add(c)
        elif getattr(a, "has_burned", False) and float(getattr(a, "fuel", 0) or 0) > 0:
            scorched.add(c)
    return burning, burnt, scorched


def _ground(cell, burning, burnt, scorched):
    if cell is None:
        return None
    if cell in burning:
        return "burning"
    if cell in burnt:
        return "burnt"
    if cell in scorched:
        return "scorched"
    return "green"


def run(seed, params, steps, arm):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    CUR["seed"] = seed

    occ = {"total": 0, "burnt": 0, "scorched": 0, "burning": 0, "green": 0}
    mv = {"total": 0, "onto_burnt": 0, "onto_scorched": 0,
          "onto_burning": 0, "onto_green": 0}
    deaths, fftrace, sigs = [], [], []
    prev_pos, prev_dead = {}, {}

    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        fires = {}
        for a in model.schedule.agents:
            if type(a) is am.Fire and getattr(a, "pos", None) is not None:
                fires[(int(a.pos[0]), int(a.pos[1]))] = a

        for step_i in range(1, steps + 1):
            model.step()
            burning, burnt, scorched = _classify(fires)

            uavs = sorted((int(a.pos[0]), int(a.pos[1]))
                          for a in model.schedule.agents
                          if type(a) is am.UAV and getattr(a, "pos", None) is not None)
            ffpos = []
            markers = getattr(model, "firefighter_marker_agents", {}) or {}
            for uid, ff in sorted(markers.items()):
                uid = str(uid)
                dead = bool(getattr(ff, "dead", False)) or \
                    str(getattr(ff, "status", "")).lower() == "dead"
                pos = getattr(ff, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                ffpos.append((uid, cell, dead))
                g = _ground(cell, burning, burnt, scorched)

                if not prev_dead.get(uid, False) and dead:
                    deaths.append({"seed": seed, "unit": uid, "step": step_i,
                                   "cell": (list(cell) if cell else None),
                                   "ground": g})
                prev_dead[uid] = dead
                if dead or cell is None:
                    continue
                fftrace.append({"seed": seed, "step": step_i, "unit": uid,
                                "cell": list(cell), "ground": g,
                                "status": str(getattr(ff, "status", "") or ""),
                                "assigned": bool(getattr(ff, "assigned", False)),
                                "exiting": bool(getattr(ff, "exiting", False))})
                occ["total"] += 1
                occ[g] += 1
                p = prev_pos.get(uid)
                if p is not None and p != cell:
                    mv["total"] += 1
                    mv["onto_" + g] += 1
                prev_pos[uid] = cell

            blob = repr((sorted(burning), ffpos, uavs))
            sigs.append(hashlib.sha1(blob.encode()).hexdigest()[:16])

        ev = _build_evaluation(model, None, steps, params)
        ev["seed"] = seed
    return {"seed": seed, "arm": arm,
            "eval": {k: ev.get(k) for k in
                     ("rescued", "dead", "unreachable", "firefighter_deaths",
                      "burnt_cells", "rescue_rate", "terminal_step")},
            "occ": occ, "mv": mv, "deaths": deaths,
            "fftrace": fftrace, "sig": sigs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", default="101")
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--arm", default="stock", choices=list(PENALTY))
    ap.add_argument("--tag", default="")
    a = ap.parse_args()

    CUR["arm"] = a.arm
    if PENALTY[a.arm] is not None:
        CUR["pen"] = PENALTY[a.arm]
        am.Firefighter._firefighter_cell_risk = _risk_armed

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

    runs = []
    for seed in [int(s) for s in a.seeds.split(",")]:
        runs.append(run(seed, params, a.steps, a.arm))
        sys.stderr.write("seed %s done\n" % seed)
        sys.stderr.flush()

    out = {"scenario": a.scenario, "wind": a.wind, "roles": a.roles,
           "steps": a.steps, "arm": a.arm, "penalty": PENALTY[a.arm],
           "params": params, "counters": CNT, "runs": runs}
    tag = a.tag or ("%s_%s_%s_%s" % (a.arm, a.wind, a.roles, a.seeds))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sc_%s.json" % tag)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    r = runs[0]
    print("%s arm=%-5s pen=%s ff_deaths=%d rescued=%d dead=%d | "
          "occ burnt/scorch/burn/green=%d/%d/%d/%d"
          % (tag, a.arm, PENALTY[a.arm], r["eval"]["firefighter_deaths"],
             r["eval"]["rescued"], r["eval"]["dead"],
             r["occ"]["burnt"], r["occ"]["scorched"], r["occ"]["burning"],
             r["occ"]["green"]))


main()
