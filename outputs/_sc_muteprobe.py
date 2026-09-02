"""Does the spared-vegetation muting pass at serve_dashboard.py:127-145 ever fire?

Two independent checks on a real run:
  A. call _capture_frame and count how many cells carry "#2f4a1a"
  B. instrument the guard directly: count cells reaching the dark_n test
"""
from __future__ import annotations
import contextlib, io as _io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agents as am, common_fixed_variables as cfv, wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
import serve_dashboard as sd

rng = random.Random(101)
cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
apply_scenario_config(cfv, wf, NUM_AGENTS=4, NUM_VICTIMS=4, NUM_FIREFIGHTERS=2,
                      WIND_DIRECTION="east", BATCH_SIZE=300,
                      FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                      NUM_FIRE_TRACKERS=2, NUM_VICTIM_SEARCHERS=2)
with contextlib.redirect_stdout(_io.StringIO()):
    model = WildFireModel(); model.debug_log = False
    tot_mute = tot_cells = 0
    for step in range(1, 121):
        model.step()
        fr = sd._capture_frame(model, step)
        cells = fr["cells"]
        n_mute = sum(1 for v in cells.values() if v == "#2f4a1a")
        tot_mute += n_mute; tot_cells += len(cells)
        if step in (20, 40, 60, 80, 100, 120):
            print("step %3d  cells=%4d  #2f4a1a=%d" % (step, len(cells), n_mute), flush=True)
print()
print("TOTAL cells emitted over 120 frames :", tot_cells)
print("TOTAL '#2f4a1a' muted cells emitted :", tot_mute)

# B: replicate the guard logic independently on the final model state
fire_cells = {}
for c in model.schedule.agents:
    if type(c).__name__ != "Fire":
        continue
    fire_cells[(int(c.pos[0]), int(c.pos[1]))] = c
cells = {"%d,%d" % k: sd._cell_color(v) for k, v in fire_cells.items()}
reached_guard1 = sum(1 for (x, y) in fire_cells if "%d,%d" % (x, y) not in cells)
print("cells surviving guard 1 ('key in cells: continue') :", reached_guard1,
      "of", len(fire_cells))
