"""Prove the KEPT helpers are load-bearing, i.e. that this was not an
over-deletion that left orphans behind on the other side.

The Part-1 gate says "no orphaned helpers or state left behind". That is two
claims, and the residual grep only proves the first:
  (1) nothing DELETED is still referenced   - proven by grep, zero residuals
  (2) nothing KEPT is now dead              - needs runtime evidence

This measures (2): every survivor of the cull is counted over a real run. A
survivor with 0 calls would mean the deletion should have gone further.

usage: _rh_survivors.py [steps]
"""
from __future__ import annotations
import contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.execution.mode_manager import ModeManager
from wildfire_model import WildFireModel

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
COUNTS: dict[str, int] = {}

SURVIVORS = [
    "update", "should_override_utility", "is_information_recovery_active",
    "_iter_analysis_triggers", "_to_reason_enums", "_collect_affected_entities",
    "_estimate_confidence", "_recovery_score", "_build_explanation",
    "_read_value", "_read_float", "_extend_entities",
]


def wrap(name):
    orig = getattr(ModeManager, name)
    raw = orig.__func__ if isinstance(orig, (staticmethod, classmethod)) else orig
    is_static = isinstance(ModeManager.__dict__.get(name), staticmethod)
    COUNTS[name] = 0

    def counted(*a, **k):
        COUNTS[name] += 1
        return raw(*a, **k)

    setattr(ModeManager, name, staticmethod(counted) if is_static else counted)


for n in SURVIVORS:
    wrap(n)

rng = random.Random(101)
cfv.SYSTEM_RANDOM = rng
wf.SYSTEM_RANDOM = rng
am.random = rng
apply_scenario_config(cfv, wf, NUM_AGENTS=4, NUM_VICTIMS=4, NUM_FIREFIGHTERS=2,
                      WIND_DIRECTION="east", BATCH_SIZE=300,
                      FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                      NUM_FIRE_TRACKERS=2, NUM_VICTIM_SEARCHERS=2)
buf = _io.StringIO()
with contextlib.redirect_stdout(buf):
    model = WildFireModel()
    model.debug_log = False
    for _ in range(STEPS):
        model.step()

print("ModeManager survivors, %d steps" % STEPS)
print("-" * 46)
dead = []
for n in SURVIVORS:
    c = COUNTS[n]
    flag = "" if c else "   <-- ZERO CALLS"
    if not c:
        dead.append(n)
    print("  %-32s %7d%s" % (n, c, flag))
print("-" * 46)
print("survivors with zero calls: %s" % (dead or "none"))
json.dump({"steps": STEPS, "counts": COUNTS, "zero_call": dead},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_rh_survivors.json"), "w", encoding="utf-8"), indent=2)
