"""Part 1 probe: is the searcher lane assignment stable, and what happens on
role change / searcher removal?  Read-only w.r.t. simulation logic."""
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
    _searcher_crosswind_lane,
    apply_scenario_config,
    resolve_victim_searcher_uav_ids,
)
from wildfire_model import WildFireModel

WIND = sys.argv[1] if len(sys.argv) > 1 else "east"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 101
STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 60
NUM_AGENTS = int(sys.argv[4]) if len(sys.argv) > 4 else 5
NUM_VS = int(sys.argv[5]) if len(sys.argv) > 5 else 2

PARAMS = {
    "NUM_AGENTS": NUM_AGENTS,
    "NUM_VICTIMS": 3,
    "NUM_FIREFIGHTERS": 3,
    "WIND_DIRECTION": WIND,
    "BATCH_SIZE": 300,
    "FIRE_SPREAD_MULTIPLIER": 0.75,
    "PROBABILITY_MAP": False,
    "NUM_FIRE_TRACKERS": NUM_AGENTS - NUM_VS,
    "NUM_VICTIM_SEARCHERS": NUM_VS,
}


def bounds(model):
    h = int(getattr(model, "HEIGHT", 50))
    w = int(getattr(model, "WIDTH", 50))
    return 0, h - 1, 0, w - 1


def lanes_now(model, wind):
    x_min, x_max, y_min, y_max = bounds(model)
    ids = resolve_victim_searcher_uav_ids(model)
    out = {}
    for uid in ids:
        out[uid] = _searcher_crosswind_lane(
            model, uid, wind, x_min, x_max, y_min, y_max
        )
    return ids, out


def fmt(ids, lanes):
    return "ids=%s lanes=%s" % (
        ids,
        {k: (None if v is None else "%s[%d..%d]" % v) for k, v in lanes.items()},
    )


def role_snapshot(model):
    managed = getattr(model, "managed_uav_states", {}) or {}
    rm = getattr(model, "uav_resource_model", None)
    by_id = getattr(rm, "by_uav_id", {}) if rm is not None else {}
    rows = []
    for uid in sorted(managed, key=lambda x: int(x) if x.isdigit() else x):
        st = managed[uid]
        rs = by_id.get(uid)
        rows.append(
            "  uav=%s managed.role=%r resource.current_role=%r switch_count=%s"
            % (
                uid,
                getattr(st, "role", None),
                getattr(rs, "current_role", None) if rs is not None else "<absent>",
                getattr(rs, "role_switch_count", None) if rs is not None else "-",
            )
        )
    return "\n".join(rows)


def _lane_math(ids, uid, wind):
    """Reproduce _searcher_crosswind_lane arithmetic on a 0..49 span."""
    n = len(ids)
    if n <= 1:
        return None
    idx = ids.index(uid)
    lo_b, hi_b = 0, 49
    span = hi_b - lo_b + 1
    lo = lo_b + (span * idx) // n
    hi = lo_b + (span * (idx + 1)) // n - 1
    if idx == n - 1:
        hi = hi_b
    axis = "y" if wind in ("east", "west") else "x"
    return "%s:%s[%d..%d]w%d" % (uid, axis, lo, hi, hi - lo + 1)


def main():
    rng = random.Random(SEED)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **PARAMS)

    print("=" * 78)
    print("LANE STABILITY PROBE  wind=%s seed=%d steps=%d n_uav=%d n_searchers=%d"
          % (WIND, SEED, STEPS, NUM_AGENTS, NUM_VS))
    print("=" * 78)

    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False

    print("")
    print("--- roles at t=0 (after construction) ---")
    print(role_snapshot(model))
    ids0, lanes0 = lanes_now(model, WIND)
    print("t=0  " + fmt(ids0, lanes0))

    history = []
    with contextlib.redirect_stdout(_io.StringIO()):
        for t in range(1, STEPS + 1):
            model.step()
            ids, lanes = lanes_now(model, WIND)
            history.append((t, tuple(ids), tuple(sorted(lanes.items()))))

    changed = [h for h in history if h[1] != tuple(ids0)]
    lane_changed = [h for h in history if h[2] != tuple(sorted(lanes0.items()))]
    print("")
    print("--- stability over %d steps ---" % STEPS)
    print("steps where searcher id LIST changed: %d" % len(changed))
    for h in changed[:8]:
        print("   t=%d ids=%s" % (h[0], list(h[1])))
    print("steps where LANE MAP changed: %d" % len(lane_changed))
    for h in lane_changed[:8]:
        print("   t=%d lanes=%s" % (h[0], dict(h[2])))
    print("")
    print("--- roles at t=%d ---" % STEPS)
    print(role_snapshot(model))
    ids_end, lanes_end = lanes_now(model, WIND)
    print("t=%d  %s" % (STEPS, fmt(ids_end, lanes_end)))

    # ---------------- forced perturbation experiments ----------------
    print("")
    print("=" * 78)
    print("FORCED PERTURBATION EXPERIMENTS (mutating a live model on purpose)")
    print("=" * 78)

    managed = model.managed_uav_states
    rm = model.uav_resource_model

    # E1: role change - flip the FIRST searcher to fire_tracker
    first = ids_end[0]
    saved_role = getattr(managed[first], "role", None)
    saved_rm = getattr(rm.by_uav_id.get(first), "current_role", None)
    managed[first].role = "fire_tracker"
    if first in rm.by_uav_id:
        rm.by_uav_id[first].current_role = "fire_tracker"
    ids_e1, lanes_e1 = lanes_now(model, WIND)
    print("")
    print("E1  role-change: searcher %s -> fire_tracker" % first)
    print("    before: " + fmt(ids_end, lanes_end))
    print("    after : " + fmt(ids_e1, lanes_e1))
    print("    -> n went %d -> %d" % (len(ids_end), len(ids_e1)))
    for uid in ids_e1:
        print("       uav %s lane %s -> %s" % (uid, lanes_end.get(uid), lanes_e1.get(uid)))
    managed[first].role = saved_role
    if first in rm.by_uav_id:
        rm.by_uav_id[first].current_role = saved_rm

    # E2: role change - flip the LAST searcher to fire_tracker
    last = ids_end[-1]
    saved_role = getattr(managed[last], "role", None)
    saved_rm = getattr(rm.by_uav_id.get(last), "current_role", None)
    managed[last].role = "fire_tracker"
    if last in rm.by_uav_id:
        rm.by_uav_id[last].current_role = "fire_tracker"
    ids_e2, lanes_e2 = lanes_now(model, WIND)
    print("")
    print("E2  role-change: searcher %s -> fire_tracker" % last)
    print("    before: " + fmt(ids_end, lanes_end))
    print("    after : " + fmt(ids_e2, lanes_e2))
    for uid in ids_e2:
        print("       uav %s lane %s -> %s" % (uid, lanes_end.get(uid), lanes_e2.get(uid)))
    managed[last].role = saved_role
    if last in rm.by_uav_id:
        rm.by_uav_id[last].current_role = saved_rm

    # E2b: role change on ALL but one searcher -> n drops to 1
    saved = {}
    for uid in ids_end[1:]:
        saved[uid] = (getattr(managed[uid], "role", None),
                      getattr(rm.by_uav_id.get(uid), "current_role", None))
        managed[uid].role = "fire_tracker"
        if uid in rm.by_uav_id:
            rm.by_uav_id[uid].current_role = "fire_tracker"
    ids_e2b, lanes_e2b = lanes_now(model, WIND)
    print("")
    print("E2b all-but-one searcher demoted -> n=%d" % len(ids_e2b))
    print("    after : " + fmt(ids_e2b, lanes_e2b))
    for uid, (r, rr) in saved.items():
        managed[uid].role = r
        if uid in rm.by_uav_id:
            rm.by_uav_id[uid].current_role = rr

    # E3: physical removal from the schedule (simulated death)
    victim_uav = None
    for a in list(model.schedule.agents):
        if type(a) is am.UAV and str(a.unique_id) == first:
            victim_uav = a
            break
    if victim_uav is not None:
        try:
            model.schedule.remove(victim_uav)
            ids_e3, lanes_e3 = lanes_now(model, WIND)
            print("")
            print("E3  schedule removal (death) of searcher %s" % first)
            print("    before: " + fmt(ids_end, lanes_end))
            print("    after : " + fmt(ids_e3, lanes_e3))
            for uid in ids_e3:
                print("       uav %s lane %s -> %s"
                      % (uid, lanes_end.get(uid), lanes_e3.get(uid)))
            model.schedule.add(victim_uav)
        except Exception as exc:
            print("")
            print("E3  removal failed: %s: %s" % (type(exc).__name__, exc))

    # E4: pure-function reshuffle math on a 0..49 span
    print("")
    print("E4  pure-function reshuffle math (no model), span 0..49")
    for wind in ("east", "north"):
        print("    wind=%s (axis=%s)" % (wind, "y" if wind in ("east", "west") else "x"))
        for ids in (["1"], ["1", "2"], ["1", "2", "3"], ["1", "3"], ["2", "3"],
                    ["1", "2", "3", "4"], ["1", "2", "4"], ["1", "2", "3", "4", "5"]):
            print("       n=%d ids=%-18s %s"
                  % (len(ids), ids, [_lane_math(ids, u, wind) for u in ids]))


if __name__ == "__main__":
    main()
