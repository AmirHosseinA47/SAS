"""Read-only probe: would available-only BFS have fired geographically_isolated on D/west 303?"""
from __future__ import annotations

import os
import random
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)
os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from serve_dashboard import BUILTIN_SCENARIOS
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

seed = 303
preset = BUILTIN_SCENARIOS["D"]
params = {
    "NUM_AGENTS": int(preset.get("NUM_AGENTS", 4)),
    "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 4)),
    "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 2)),
    "WIND_DIRECTION": "west",
    "BATCH_SIZE": 300,
    "FIRE_SPREAD_MULTIPLIER": 0.75,
    "PROBABILITY_MAP": False,
}
rng = random.Random(seed)
cfv.SYSTEM_RANDOM = rng
wf.SYSTEM_RANDOM = rng
am.random = rng
apply_scenario_config(cfv, wf, **params)
model = WildFireModel()
model.debug_log = False

streaks: dict[str, int] = {}
max_streaks: dict[str, int] = {}
fired_at: dict[str, int] = {}
n_busy_all = 0

for step in range(1, 241):
    model.step()
    ff_markers = model.firefighter_marker_agents or {}
    burning = model._active_burning_cells()
    living_starts = []
    avail_starts = []
    for ff in ff_markers.values():
        if getattr(ff, "dead", False):
            continue
        status = str(getattr(ff, "status", "") or "").strip().lower()
        if status == "dead":
            continue
        if getattr(ff, "exiting", False):
            continue
        pos = getattr(ff, "pos", None)
        if pos is None:
            continue
        cell = (int(pos[0]), int(pos[1]))
        living_starts.append(cell)
        if model._firefighter_available_for_dispatch(ff):
            avail_starts.append(cell)
    if living_starts and not avail_starts:
        n_busy_all += 1
    living_reach = model._safe_path_reachable_cells(living_starts, burning)
    avail_reach = model._safe_path_reachable_cells(avail_starts, burning)
    managed = model.managed_victims
    markers = model.victim_marker_agents
    for vid, st in managed.items():
        status = str(getattr(st, "status", "") or "").strip().lower()
        if status in ("rescued", "dead", "unreachable", "cancelled"):
            streaks[vid] = 0
            continue
        mk = markers.get(vid)
        pair = model._find_active_firefighter_for_victim(vid, mk)
        assigned = pair is not None
        confirmed = bool(getattr(st, "confirmed", False))
        vpos = getattr(mk, "pos", None) if mk is not None else None
        if vpos is None:
            vpos = getattr(st, "last_known_position", None)
        vcell = (
            (int(vpos[0]), int(vpos[1]))
            if vpos is not None and len(vpos) >= 2
            else None
        )
        living_ok = bool(vcell is not None and vcell in living_reach)
        avail_ok = bool(vcell is not None and vcell in avail_reach)
        if confirmed and (not assigned) and living_ok and (not avail_ok):
            streaks[vid] = streaks.get(vid, 0) + 1
        else:
            streaks[vid] = 0
        max_streaks[vid] = max(max_streaks.get(vid, 0), streaks.get(vid, 0))
        if streaks.get(vid, 0) >= 30 and vid not in fired_at:
            fired_at[vid] = step

print("max_streaks", max_streaks)
print("would_fire_geo_at", fired_at)
print("steps_all_ff_busy", n_busy_all)
print(
    "final_status",
    {vid: getattr(st, "status", None) for vid, st in model.managed_victims.items()},
)
print(
    "causes",
    {
        vid: getattr(st, "unreachable_cause", None)
        for vid, st in model.managed_victims.items()
    },
)
