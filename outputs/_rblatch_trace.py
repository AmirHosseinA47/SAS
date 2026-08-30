"""Per-step trace of one firefighter from the moment route_blocked fires.

Answers Part 1 step 5: does the unit's situation ever improve during the idle
steps, i.e. does a live fire-free path to ANY victim needing rescue ever
reopen while the unit sits latched?

Uses the model's OWN reachability predicate (Firefighter._path_exists_avoiding_fire)
so the answer is directly comparable to what the trigger fix tests.
"""
from __future__ import annotations
import argparse, collections, contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation

TRACE = []
EVENTS = []          # status transitions + dispatch events for the tracked unit
MARKS = []


def _fire_cells(model):
    cells = set()
    for a in model.schedule.agents:
        if type(a) is am.Fire and a.is_burning():
            p = getattr(a, "pos", None)
            if p is not None:
                cells.add((int(p[0]), int(p[1])))
    return cells


def _min_fire_dist(cell, fires):
    if not fires:
        return None
    return min(abs(cell[0] - f[0]) + abs(cell[1] - f[1]) for f in fires)


_orig_mark = am.Firefighter._mark_route_blocked


def _traced_mark(self):
    before = str(getattr(self, "status", "") or "")
    _orig_mark(self)
    now = str(getattr(self, "status", "") or "")
    MARKS.append({
        "step": int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0),
        "ff": str(getattr(self, "unit_id", "")),
        "before": before, "after": now,
        "pos": tuple(int(v) for v in (self.pos or (-1, -1))),
    })


am.Firefighter._mark_route_blocked = _traced_mark


def snapshot_unit(model, ff, ff_id):
    """One row of the trace for firefighter `ff` at the current step."""
    step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
    pos = getattr(ff, "pos", None)
    cell = (int(pos[0]), int(pos[1])) if pos is not None else None
    fires = _fire_cells(model)
    tgt = getattr(ff, "target_pos", None)
    tgt_c = (int(tgt[0]), int(tgt[1])) if tgt is not None else None

    row = {
        "step": step,
        "pos": cell,
        "status": str(getattr(ff, "status", "") or ""),
        "assigned": bool(getattr(ff, "assigned", False)),
        "dead": bool(getattr(ff, "dead", False)),
        "exiting": bool(getattr(ff, "exiting", False)),
        "target_pos": tgt_c,
        "n_fire": len(fires),
        "nearest_fire": _min_fire_dist(cell, fires) if cell else None,
        "on_fire": cell in fires if cell else False,
    }

    # live path to its ORIGINAL target, if it still has one
    row["path_to_target"] = (
        bool(ff._path_exists_avoiding_fire(cell, tgt_c, fires))
        if (cell and tgt_c) else None
    )

    # live path to ANY victim still needing rescue - the recovery question
    reach = []
    unreach = []
    vms = getattr(model, "victim_marker_agents", {}) or {}
    for vid, vm in vms.items():
        try:
            if not model._victim_needs_rescue(str(vid), vm):
                continue
        except Exception:
            continue
        vp = getattr(vm, "pos", None)
        if vp is None:
            continue
        vc = (int(vp[0]), int(vp[1]))
        if cell is None:
            continue
        ok = bool(ff._path_exists_avoiding_fire(cell, vc, fires))
        (reach if ok else unreach).append((str(vid), vc))
    row["victims_pending"] = len(reach) + len(unreach)
    row["victims_reachable"] = len(reach)
    row["reachable_ids"] = [v[0] for v in reach]
    return row


def run(seed, params, steps, unit):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    terminal_step = None
    ran = 0
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        prev = {}
        for s in range(1, steps + 1):
            model.step()
            ran = s
            ffm = getattr(model, "firefighter_marker_agents", {}) or {}
            for fid, m in ffm.items():
                uid = str(getattr(m, "unit_id", "") or fid)
                if uid != unit and str(fid) != unit:
                    continue
                row = snapshot_unit(model, m, fid)
                TRACE.append(row)
                key = (row["status"], row["assigned"], row["target_pos"], row["dead"])
                if prev.get(fid) != key:
                    EVENTS.append({"step": s, "ff": uid, **{
                        k: row[k] for k in
                        ("status", "assigned", "target_pos", "dead", "pos")}})
                    prev[fid] = key
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = s
        ev = _build_evaluation(model, terminal_step, ran, params)
    ev["seed"] = seed
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--seed", type=int, default=333)
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--unit", default="ff_unit_1")
    ap.add_argument("--tag", default="trace")
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft}
    ev = run(a.seed, params, a.steps, a.unit)
    out = {"tag": a.tag, "scenario": a.scenario, "wind": a.wind, "seed": a.seed,
           "unit": a.unit, "eval": ev, "trace": TRACE, "events": EVENTS, "marks": MARKS}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_rblatch_trace_%s_%s_%s_%s.json" % (a.tag, a.scenario, a.wind, a.seed))
    with open(p, "w") as f:
        json.dump(out, f, default=str)
    print(p)
    print("eval:", {k: ev.get(k) for k in ("rescued", "dead", "firefighter_deaths")})
    print("marks:", MARKS)


main()
