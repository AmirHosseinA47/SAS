"""Dump A/north 404 victim_0 assignment progress after late detect. Not a repo source file."""
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

for step in range(1, 241):
    model.step()
    if step < 200:
        continue
    vid = "victim_0"
    st = model.managed_victims[vid]
    mk = model.victim_marker_agents.get(vid)
    pair = model._find_active_firefighter_for_victim(vid, mk)
    vpos = getattr(mk, "pos", None) if mk is not None else None
    ff_id = pair[0] if pair else None
    ff_pos = None
    ff_status = None
    if pair:
        ff_pos = getattr(pair[1], "pos", None)
        ff_status = getattr(pair[1], "status", None)
    dist = None
    if vpos is not None and ff_pos is not None:
        dist = abs(int(vpos[0]) - int(ff_pos[0])) + abs(int(vpos[1]) - int(ff_pos[1]))
    print(
        "step=%d status=%s confirmed=%s assigned=%s ff=%s ff_status=%s vpos=%s ffpos=%s manhattan=%s"
        % (
            step,
            getattr(st, "status", None),
            getattr(st, "confirmed", None),
            bool(pair),
            ff_id,
            ff_status,
            vpos,
            ff_pos,
            dist,
        ),
        flush=True,
    )
