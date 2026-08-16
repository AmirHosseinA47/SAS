"""One-off diagnosis for A/north seed 404 non-terminal victim. Not a repo source file."""
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

seed = 404
preset = BUILTIN_SCENARIOS["A"]
params = {
    "NUM_AGENTS": int(preset.get("NUM_AGENTS", 3)),
    "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
    "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
    "WIND_DIRECTION": "north",
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


def dump(step: int) -> None:
    print("--- step", step, flush=True)
    geo = getattr(model, "_unreachable_geo_streak", {})
    und = getattr(model, "_unreachable_undetected_streak", {})
    for vid, st in sorted(model.managed_victims.items()):
        mk = model.victim_marker_agents.get(vid)
        pair = model._find_active_firefighter_for_victim(vid, mk)
        print(
            " ",
            vid,
            "status",
            getattr(st, "status", None),
            "marker",
            getattr(mk, "status", None) if mk else None,
            "confirmed",
            getattr(st, "confirmed", None),
            "assigned",
            bool(pair),
            "ff",
            pair[0] if pair else None,
            "geo_streak",
            geo.get(vid, 0),
            "und_streak",
            und.get(vid, 0),
            flush=True,
        )


watch = {1, 30, 60, 90, 120, 150, 180, 209, 210, 211, 240}
for step in range(1, 241):
    model.step()
    if step in watch:
        dump(step)

print("ESCAPE", getattr(model, "_unreachable_escape_log", []), flush=True)
print(
    "EVAL",
    {vid: getattr(st, "status", None) for vid, st in model.managed_victims.items()},
    flush=True,
)
