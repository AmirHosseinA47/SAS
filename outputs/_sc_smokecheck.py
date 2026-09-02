"""Why 359 scorched cells but only 299 painted #895e00?

Branch order: smoke wins over the burned family, so a scorched cell that is
still smoking renders #ababab. This confirms that reading rather than assuming it.
"""
from __future__ import annotations
import contextlib, io as _io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agents as am, common_fixed_variables as cfv, wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import _cell_color

rng = random.Random(101)
cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
apply_scenario_config(cfv, wf, NUM_AGENTS=4, NUM_VICTIMS=4, NUM_FIREFIGHTERS=2,
                      WIND_DIRECTION="east", BATCH_SIZE=300,
                      FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                      NUM_FIRE_TRACKERS=2, NUM_VICTIM_SEARCHERS=2)
with contextlib.redirect_stdout(_io.StringIO()):
    model = WildFireModel(); model.debug_log = False
    for _ in range(240):
        model.step()

scorched = smoking_scorched = painted = 0
burnt = smoking_burnt = 0
for a in model.schedule.agents:
    if type(a).__name__ != "Fire":
        continue
    if getattr(a, "burning", False):
        continue
    if getattr(a, "burnt", False):
        burnt += 1
        if a.smoke.is_smoke_active():
            smoking_burnt += 1
    elif getattr(a, "has_burned", False):
        scorched += 1
        if a.smoke.is_smoke_active():
            smoking_scorched += 1
        if _cell_color(a) == "#895e00":
            painted += 1
print("scorched (has_burned, not burnt, not burning) :", scorched)
print("  of which still smoking (render #ababab)     :", smoking_scorched)
print("  painted #895e00                             :", painted)
print("  %d - %d = %d   -> accounts for the gap: %s"
      % (scorched, smoking_scorched, scorched - smoking_scorched,
         scorched - smoking_scorched == painted))
print("burnt                                         :", burnt)
print("  of which still smoking                      :", smoking_burnt)
