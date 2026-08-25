"""Part 2 item 5: dump the ACTUAL shape and contents of
VisibilityModel.state.observation_status_map and get_uncertain_regions() at
several points in one run, split by the lane boundary chosen at step 0.

Answers: would an uncertainty-weighted allocation have picked a different split
than the even one the code uses today?
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
STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 240
NUM_VS = int(sys.argv[4]) if len(sys.argv) > 4 else 2
CHECKPOINTS = (0, 40, 120, 200, STEPS)

PARAMS = {
    "NUM_AGENTS": 5, "NUM_VICTIMS": 3, "NUM_FIREFIGHTERS": 3,
    "WIND_DIRECTION": WIND, "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75,
    "PROBABILITY_MAP": False,
    "NUM_FIRE_TRACKERS": 5 - NUM_VS, "NUM_VICTIM_SEARCHERS": NUM_VS,
}


def dump(model, t, lanes, first=False):
    vis = model.visibility_model
    s = vis.state
    osm = s.observation_status_map
    unc = vis.get_uncertain_regions()

    if first:
        k = next(iter(osm))
        v = osm[k]
        print("  observation_status_map: %s, len=%d" % (type(osm).__name__, len(osm)))
        print("     sample key   : %r (%s)" % (k, type(k).__name__))
        print("     sample value : %r (%s, .value=%r)" % (v, type(v).__name__, getattr(v, "value", None)))
        print("     key space    : every (x,y) with x in 0..HEIGHT-1, y in 0..WIDTH-1 "
              "(initialize_grid(width=HEIGHT, height=WIDTH))")
        print("  get_uncertain_regions(): %s of %s, len=%d"
              % (type(unc).__name__, type(next(iter(unc))).__name__ if unc else "-", len(unc)))
        print("     defined as: status in {SMOKE_OBSCURED, NEVER_SEEN, STALE_INFORMATION}"
              " or conf < 0.4 or staleness > 10.0")

    hist = {}
    for v in osm.values():
        key = getattr(v, "value", str(v))
        hist[key] = hist.get(key, 0) + 1
    print("")
    print("  [t=%d] global status histogram: %s" % (t, hist))
    print("  [t=%d] uncertain cells: %d / %d (%.1f%%)  ever-observed cells: %d"
          % (t, len(unc), len(osm), 100.0 * len(unc) / max(1, len(osm)),
             len(s.last_seen_timestamp_per_cell)))

    x_max = int(getattr(model, "HEIGHT", 50)) - 1
    y_max = int(getattr(model, "WIDTH", 50)) - 1
    for uid in sorted(lanes):
        lane = lanes[uid]
        cells = [(cx, cy) for cx in range(0, x_max + 1) for cy in range(0, y_max + 1)
                 if _lane_allows_cell(lane, cx, cy)]
        never = sum(1 for c in cells
                    if getattr(osm.get(c), "value", None) == "never_seen")
        stale = sum(1 for c in cells
                    if getattr(osm.get(c), "value", None) == "stale_information")
        u = sum(1 for c in cells if c in unc)
        print("     lane %s %-12s cells=%d never_seen=%-5d stale=%-5d uncertain=%-5d "
              "(never %.1f%% / unc %.1f%%)"
              % (uid, "%s[%d..%d]" % lane, len(cells), never, stale, u,
                 100.0 * never / max(1, len(cells)), 100.0 * u / max(1, len(cells))))

    # what an uncertainty-weighted split would have chosen, on the lane axis
    axis = lanes[sorted(lanes)[0]][0]
    lo_b, hi_b = (0, y_max) if axis == "y" else (0, x_max)
    mass = []
    for band in range(lo_b, hi_b + 1):
        if axis == "y":
            cells = [(cx, band) for cx in range(0, x_max + 1)]
        else:
            cells = [(band, cy) for cy in range(0, y_max + 1)]
        mass.append(sum(1 for c in cells if c in unc))
    total = sum(mass) or 1
    n = len(lanes)
    cuts = []
    acc = 0
    want = 1
    for band, m in enumerate(mass, start=lo_b):
        acc += m
        while want < n and acc >= total * want / n:
            cuts.append(band)
            want += 1
    print("     uncertainty mass on the %s axis: total=%d" % (axis, total))
    print("     even split cuts   : %s" % [
        lo_b + ((hi_b - lo_b + 1) * i) // n - 1 for i in range(1, n)
    ])
    print("     equal-MASS cuts   : %s  <-- what sub-item 3 would pick" % cuts)


def main():
    rng = random.Random(SEED)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **PARAMS)

    print("=" * 78)
    print("UNCERTAINTY / OBSERVATION-MAP DUMP  wind=%s seed=%d steps=%d searchers=%d"
          % (WIND, SEED, STEPS, NUM_VS))
    print("=" * 78)

    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False

    x_max = int(getattr(model, "HEIGHT", 50)) - 1
    y_max = int(getattr(model, "WIDTH", 50)) - 1
    ids = resolve_victim_searcher_uav_ids(model)
    lanes = {u: _searcher_crosswind_lane(model, u, WIND, 0, x_max, 0, y_max) for u in ids}
    print("lanes fixed at step 0: %s"
          % {u: "%s[%d..%d]" % v for u, v in lanes.items()})

    dump(model, 0, lanes, first=True)
    for t in range(1, STEPS + 1):
        with contextlib.redirect_stdout(_io.StringIO()):
            model.step()
        if t in CHECKPOINTS:
            dump(model, t, lanes)


if __name__ == "__main__":
    main()
