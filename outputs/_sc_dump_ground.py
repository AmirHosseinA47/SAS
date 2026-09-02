from __future__ import annotations
import contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agents as am, common_fixed_variables as cfv, wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import _cell_color
BASE = os.path.dirname(os.path.abspath(__file__))
rng = random.Random(101)
cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
apply_scenario_config(cfv, wf, NUM_AGENTS=4, NUM_VICTIMS=4, NUM_FIREFIGHTERS=2,
                      WIND_DIRECTION="east", BATCH_SIZE=300,
                      FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                      NUM_FIRE_TRACKERS=2, NUM_VICTIM_SEARCHERS=2)
with contextlib.redirect_stdout(_io.StringIO()):
    model = WildFireModel(); model.debug_log = False
    for _ in range(60):
        model.step()
def ground(a):
    if getattr(a, "burning", False): return "burning"
    if getattr(a, "burnt", False): return "burnt"
    if getattr(a, "has_burned", False): return "scorched"
    return "virgin"
out = [[int(a.pos[0]), int(a.pos[1]), ground(a), _cell_color(a)]
       for a in model.schedule.agents if type(a).__name__ == "Fire"]
with open(os.path.join(BASE, "_sc_ground.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh)
print("WROTE _sc_ground.json", len(out))
