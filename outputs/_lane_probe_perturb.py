"""Part 1 probe #2: force a mid-run searcher loss and watch the lanes reshuffle.

Runs n=3 searchers for PRE steps, then demotes ONE searcher to fire_tracker
(the same mutation GlobalExecutor would perform if a role decision ever carried
per-UAV assignments), then runs POST more steps.  Reports the lane map before
and after, whether cached per-UAV wind_state survives the reshuffle, and the
per-lane coverage on either side of the event.
"""
from __future__ import annotations

import contextlib
import io as _io
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

WIND = sys.argv[1] if len(sys.argv) > 1 else "east"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 101
PRE = int(sys.argv[3]) if len(sys.argv) > 3 else 80
POST = int(sys.argv[4]) if len(sys.argv) > 4 else 80
VICTIM_SLOT = int(sys.argv[5]) if len(sys.argv) > 5 else 1  # which searcher dies

PARAMS = {
    "NUM_AGENTS": 5, "NUM_VICTIMS": 3, "NUM_FIREFIGHTERS": 3,
    "WIND_DIRECTION": WIND, "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75,
    "PROBABILITY_MAP": False, "NUM_FIRE_TRACKERS": 2, "NUM_VICTIM_SEARCHERS": 3,
}


def bounds(model):
    return 0, int(getattr(model, "HEIGHT", 50)) - 1, 0, int(getattr(model, "WIDTH", 50)) - 1


def lane_map(model, wind):
    x_min, x_max, y_min, y_max = bounds(model)
    ids = resolve_victim_searcher_uav_ids(model)
    return ids, {u: _searcher_crosswind_lane(model, u, wind, x_min, x_max, y_min, y_max)
                 for u in ids}


def lane_cells(model, lane):
    x_min, x_max, y_min, y_max = bounds(model)
    return [(cx, cy) for cx in range(x_min, x_max + 1)
            for cy in range(y_min, y_max + 1) if _lane_allows_cell(lane, cx, cy)]


def obs_frac(model, cells):
    seen = model.visibility_model.state.last_seen_timestamp_per_cell
    return sum(1 for c in cells if c in seen) / max(1, len(cells))


def report_lanes(tag, ids, lanes, model):
    print("  %s ids=%s" % (tag, ids))
    for u in ids:
        lane = lanes[u]
        cells = lane_cells(model, lane)
        print("     uav %s lane=%s width=%d obs_frac=%.3f"
              % (u, "None" if lane is None else "%s[%d..%d]" % lane,
                 0 if lane is None else lane[2] - lane[1] + 1, obs_frac(model, cells)))


def wind_state_dump(model, ids):
    store = getattr(model, "_wind_search_target_state", {}) or {}
    for u in ids:
        st = store.get(str(u))
        if not isinstance(st, dict):
            print("     uav %s wind_state: <absent>" % u)
            continue
        ct = st.get("corridor_targets") or []
        print("     uav %s wind_state: corridor_targets=%d idx=%s current_target=%s "
              "saturated=%d y_commit=%s recent_targets=%d"
              % (u, len(ct), st.get("corridor_index"), st.get("current_target"),
                 len(st.get("saturated_until") or {}), st.get("coverage_y_commit"),
                 len(st.get("recent_targets") or [])))


def stale_targets(model, ids, lanes):
    """Cached targets that lie OUTSIDE the searcher's current lane."""
    store = getattr(model, "_wind_search_target_state", {}) or {}
    out = {}
    for u in ids:
        st = store.get(str(u))
        if not isinstance(st, dict):
            continue
        lane = lanes.get(u)
        bad = []
        for pt in (st.get("corridor_targets") or []):
            if not _lane_allows_cell(lane, int(round(pt[0])), int(round(pt[1]))):
                bad.append((int(round(pt[0])), int(round(pt[1]))))
        cur = st.get("current_target")
        cur_bad = None
        if isinstance(cur, (list, tuple)) and len(cur) >= 2:
            if not _lane_allows_cell(lane, int(round(cur[0])), int(round(cur[1]))):
                cur_bad = (int(round(cur[0])), int(round(cur[1])))
        out[u] = (bad, cur_bad, len(st.get("corridor_targets") or []))
    return out


def main():
    rng = random.Random(SEED)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **PARAMS)

    print("=" * 78)
    print("MID-RUN SEARCHER LOSS PROBE  wind=%s seed=%d pre=%d post=%d n_searchers=3"
          % (WIND, SEED, PRE, POST))
    print("=" * 78)

    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(PRE):
            model.step()

    ids_pre, lanes_pre = lane_map(model, WIND)
    print("")
    print("[t=%d] BEFORE the loss" % PRE)
    report_lanes("", ids_pre, lanes_pre, model)
    wind_state_dump(model, ids_pre)
    pre_cells = {u: lane_cells(model, lanes_pre[u]) for u in ids_pre}
    pre_frac = {u: obs_frac(model, pre_cells[u]) for u in ids_pre}

    # --- the loss: demote one searcher exactly as GlobalExecutor would ---
    victim = ids_pre[min(VICTIM_SLOT, len(ids_pre) - 1)]
    managed = model.managed_uav_states
    rm = model.uav_resource_model
    managed[victim].role = "fire_tracker"
    if victim in rm.by_uav_id:
        rm.by_uav_id[victim].current_role = "fire_tracker"
    print("")
    print(">>> DEMOTED searcher %s (slot %d of %d) to fire_tracker at t=%d"
          % (victim, VICTIM_SLOT, len(ids_pre), PRE))

    ids_post, lanes_post = lane_map(model, WIND)
    print("")
    print("[t=%d] IMMEDIATELY AFTER the loss (before any step)" % PRE)
    report_lanes("", ids_post, lanes_post, model)
    print("   lane deltas:")
    for u in ids_post:
        a = lanes_pre.get(u)
        b = lanes_post.get(u)
        print("     uav %s  %s  ->  %s   %s"
              % (u,
                 "None" if a is None else "%s[%d..%d]" % a,
                 "None" if b is None else "%s[%d..%d]" % b,
                 "UNCHANGED" if a == b else "RESHUFFLED"))
    print("   inherited territory (cells now owned that the owner never observed):")
    for u in ids_post:
        newc = set(lane_cells(model, lanes_post[u]))
        oldc = set(pre_cells.get(u) or [])
        gained = newc - oldc
        seen = model.visibility_model.state.last_seen_timestamp_per_cell
        unseen_gained = sum(1 for c in gained if c not in seen)
        print("     uav %s gained %d cells, %d of them never observed by anyone"
              % (u, len(gained), unseen_gained))
    print("   cached wind_state targets now OUT of the owner's lane:")
    for u, (bad, cur_bad, total) in stale_targets(model, ids_post, lanes_post).items():
        print("     uav %s: %d/%d corridor targets out-of-lane, current_target_out=%s"
              % (u, len(bad), total, cur_bad))
    wind_state_dump(model, ids_post)

    # --- keep running ---
    with contextlib.redirect_stdout(_io.StringIO()):
        for _ in range(POST):
            model.step()

    ids_end, lanes_end = lane_map(model, WIND)
    print("")
    print("[t=%d] AFTER %d more steps" % (PRE + POST, POST))
    report_lanes("", ids_end, lanes_end, model)
    print("   per-lane coverage gain across the event:")
    for u in ids_end:
        cells_now = lane_cells(model, lanes_end[u])
        print("     uav %s obs_frac %.3f (its OLD lane at t=%d) -> %.3f (its NEW lane at t=%d)"
              % (u, pre_frac.get(u, float('nan')), PRE, obs_frac(model, cells_now), PRE + POST))
    print("   demoted uav %s: still stepping, role=%r"
          % (victim, getattr(managed[victim], "role", None)))
    x_min, x_max, y_min, y_max = bounds(model)
    orphan = lanes_pre.get(victim)
    if orphan is not None:
        oc = lane_cells(model, orphan)
        print("   ORPHANED lane %s[%d..%d]: obs_frac %.3f -> %.3f"
              % (orphan[0], orphan[1], orphan[2],
                 pre_frac.get(victim, float("nan")), obs_frac(model, oc)))


if __name__ == "__main__":
    main()
