"""Part 2 probe: instrumented multi-searcher matrix.

Per run records, per searcher lane:
  - obs_frac  (fraction of the lane's cells ever observed by run end)
  - never_seen / stale / uncertain counts at checkpoints
  - never_detected victims attributable to the lane
  - lane-compliance (fraction of steps the searcher stood inside its own lane)
  - whether the searcher-id list (and hence the lane map) ever changed mid-run

Read-only with respect to simulation logic.
"""
from __future__ import annotations

import contextlib
import io as _io
import json
import os
import random
import sys

os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import (
    _lane_allows_cell,
    _searcher_crosswind_lane,
    apply_scenario_config,
    resolve_victim_searcher_uav_ids,
)
from wildfire_model import WildFireModel

from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation

CHECKPOINTS = (40, 120, 200)


def _params(scenario, wind, uavs, trackers, searchers):
    preset = BUILTIN_SCENARIOS[scenario]
    return {
        "NUM_AGENTS": uavs,
        "NUM_VICTIMS": int(preset["NUM_VICTIMS"]),
        "NUM_FIREFIGHTERS": int(preset["NUM_FIREFIGHTERS"]),
        "WIND_DIRECTION": wind,
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": trackers,
        "NUM_VICTIM_SEARCHERS": searchers,
    }


def _bounds(model):
    h = int(getattr(model, "HEIGHT", 50))
    w = int(getattr(model, "WIDTH", 50))
    return 0, h - 1, 0, w - 1


def _lane_map(model, wind):
    x_min, x_max, y_min, y_max = _bounds(model)
    ids = resolve_victim_searcher_uav_ids(model)
    return ids, {
        uid: _searcher_crosswind_lane(model, uid, wind, x_min, x_max, y_min, y_max)
        for uid in ids
    }


def _lane_cells(model, lane):
    x_min, x_max, y_min, y_max = _bounds(model)
    return [
        (cx, cy)
        for cx in range(x_min, x_max + 1)
        for cy in range(y_min, y_max + 1)
        if _lane_allows_cell(lane, cx, cy)
    ]


def _lane_stats(model, lane_cells, uncertain):
    vis = model.visibility_model
    s = vis.state
    seen_ts = s.last_seen_timestamp_per_cell
    status = s.observation_status_map
    counts = {}
    ever = 0
    unc = 0
    for cell in lane_cells:
        st = status.get(cell)
        key = getattr(st, "value", str(st))
        counts[key] = counts.get(key, 0) + 1
        if cell in seen_ts:
            ever += 1
        if cell in uncertain:
            unc += 1
    total = max(1, len(lane_cells))
    return {
        "cells": len(lane_cells),
        "ever_observed": ever,
        "obs_frac": round(ever / total, 4),
        "uncertain": unc,
        "uncertain_frac": round(unc / total, 4),
        "status_counts": counts,
    }


def _victim_lane(model, lanes, pos):
    cx, cy = int(round(pos[0])), int(round(pos[1]))
    hits = [uid for uid, lane in lanes.items() if _lane_allows_cell(lane, cx, cy)]
    return hits


def run_one(scenario, wind, seed, steps, uavs, trackers, searchers, dump_checkpoints=False):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    params = _params(scenario, wind, uavs, trackers, searchers)
    apply_scenario_config(cfv, wf, **params)

    result = {
        "scenario": scenario, "wind": wind, "seed": seed, "steps": steps,
        "uavs": uavs, "trackers": trackers, "searchers": searchers,
    }
    checkpoint_dumps = []

    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False

        ids0, lanes0 = _lane_map(model, wind)
        result["ids_t0"] = list(ids0)
        result["lanes_t0"] = {k: (None if v is None else list(v)) for k, v in lanes0.items()}
        lane_cells0 = {uid: _lane_cells(model, lanes0[uid]) for uid in ids0}

        id_change_events = []
        in_lane_steps = {uid: 0 for uid in ids0}
        pos_steps = {uid: 0 for uid in ids0}
        terminal_step = None
        step = 0

        for t in range(1, steps + 1):
            model.step()
            step = t
            ids, lanes = _lane_map(model, wind)
            if list(ids) != list(ids0):
                id_change_events.append({"step": t, "ids": list(ids)})
                ids0 = ids
                lanes0 = lanes
                lane_cells0 = {uid: _lane_cells(model, lanes[uid]) for uid in ids}

            rmodel = model.uav_resource_model
            for uid in ids:
                st = rmodel.by_uav_id.get(uid)
                p = getattr(st, "current_position", None) if st is not None else None
                if p is None:
                    continue
                pos_steps[uid] = pos_steps.get(uid, 0) + 1
                if _lane_allows_cell(lanes.get(uid), int(round(p[0])), int(round(p[1]))):
                    in_lane_steps[uid] = in_lane_steps.get(uid, 0) + 1

            if terminal_step is None:
                panel = model.get_dashboard_state()
                mission = panel.get("mission_status", {}) or {}
                if mission.get("all_victims_terminal"):
                    terminal_step = t

            if t in CHECKPOINTS:
                unc = model.visibility_model.get_uncertain_regions()
                snap = {
                    "step": t,
                    "ids": list(ids),
                    "global_uncertain": len(unc),
                    "global_ever_observed": len(
                        model.visibility_model.state.last_seen_timestamp_per_cell
                    ),
                    "lanes": {
                        uid: _lane_stats(model, lane_cells0[uid], unc) for uid in ids
                    },
                }
                checkpoint_dumps.append(snap)

        unc_final = model.visibility_model.get_uncertain_regions()
        ids, lanes = _lane_map(model, wind)
        final_lane_cells = {uid: _lane_cells(model, lanes[uid]) for uid in ids}
        result["lane_final"] = {
            uid: _lane_stats(model, final_lane_cells[uid], unc_final) for uid in ids
        }
        result["lane_compliance"] = {
            uid: round(in_lane_steps.get(uid, 0) / max(1, pos_steps.get(uid, 1)), 4)
            for uid in ids
        }
        result["id_change_events"] = id_change_events
        result["checkpoints"] = checkpoint_dumps
        result["global_ever_observed"] = len(
            model.visibility_model.state.last_seen_timestamp_per_cell
        )
        result["global_uncertain"] = len(unc_final)

        # victim outcome attribution per lane
        victims = []
        for vid, st in (getattr(model, "managed_victims", {}) or {}).items():
            pos = getattr(st, "last_known_position", None) or (0, 0)
            status = str(getattr(st, "status", "")).lower()
            cause = ""
            for attr in ("unreachable_cause", "cause", "unreachable_reason"):
                v = getattr(st, attr, None)
                if v:
                    cause = str(v)
                    break
            victims.append({
                "victim_id": vid,
                "pos": [round(float(pos[0]), 1), round(float(pos[1]), 1)],
                "status": status,
                "cause": cause,
                "lanes": _victim_lane(model, lanes, pos),
            })
        result["victims"] = victims

        ev = _build_evaluation(model, terminal_step, step, params)

    for k in ("rescued", "dead", "unreachable", "never_detected",
              "geographically_isolated", "horizon_unresolved", "unreachable_other",
              "candidate", "rescue_rate", "burnt_cells", "terminal_step",
              "unreachable_causes"):
        result[k] = ev.get(k)
    return result


def main(argv):
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--scenario", required=True)
    p.add_argument("--wind", required=True)
    p.add_argument("--seeds", required=True)
    p.add_argument("--steps", type=int, default=240)
    p.add_argument("--uavs", type=int, required=True)
    p.add_argument("--fire-trackers", type=int, required=True, dest="trackers")
    p.add_argument("--victim-searchers", type=int, required=True, dest="searchers")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    seeds = [int(s) for s in a.seeds.split(",")]
    rows = []
    for seed in seeds:
        row = run_one(a.scenario, a.wind, seed, a.steps, a.uavs, a.trackers, a.searchers)
        rows.append(row)
        lf = row["lane_final"]
        fr = " ".join("%s=%.3f" % (u, lf[u]["obs_frac"]) for u in sorted(lf))
        print("seed=%-5d rescued=%s dead=%s unreach=%s nd=%s | lane obs_frac: %s | "
              "id_changes=%d | compliance=%s"
              % (seed, row["rescued"], row["dead"], row["unreachable"],
                 row["never_detected"], fr, len(row["id_change_events"]),
                 {u: row["lane_compliance"][u] for u in sorted(row["lane_compliance"])}),
              flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    print("WROTE %s" % a.out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
