"""Ungated-firefighting round, Part 1: simulate the FF_FIREFIGHT_* default flip
WITHOUT editing source.

Loaded as a pytest plugin:  python -m pytest tests -p outputs._ug_simplugin
  UG_SIM=1  set the four flipped constants on the common_fixed_variables MODULE at
            plugin import. -p plugins import before collection, so every test module
            sees the flipped values exactly as if the source said so. A test's
            monkeypatch.setattr restores to the flipped value, as it would after a
            real flip. Every FF accessor in agents.py reads `cfv.<NAME>` at call
            time, so the star-import copies in wildfire_model/agents are irrelevant
            here (they are printed anyway, as the flip round's plugin did).
  UG_SIM=0  patch nothing. The control for this plugin's own early import.

Valid only because no test reloads a module, spawns a subprocess or ships a
conftest (re-checked at 11c3661: tests/ has no conftest.py and no file matches
reload( / subprocess / os.system / Popen).
The agents.py accessor FALLBACKS are NOT simulated; they are source edits. With
the constant present on the module a fallback is only reached by a test that
deletes or junks the attribute, i.e. by exactly the deliberate-pin tests.
Copied from outputs/_flip_simplugin.py (flip round), constants swapped.
"""
import os
import sys

import common_fixed_variables as cfv

FLIP = (
    ("FF_FIREFIGHT_EXTINGUISH", 1),
    ("FF_FIREFIGHT_FIREBREAK", 1),
    ("FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", 1),
    ("FF_FIREFIGHT_MISSION_GATE", 0),
)
UNCHANGED = (
    "FF_FIREFIGHT_DRY_RUN",
    "BASE_STATION_MODE", "BASE_STATION_FIREPROOF", "BASE_STATION_SPAWN_FIREFIGHTERS",
    "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE",
)
SIM = os.environ.get("UG_SIM", "0") == "1"

if SIM:
    for _name, _value in FLIP:
        setattr(cfv, _name, _value)


def _snapshot(module):
    return " ".join(
        "%s=%r" % (n, getattr(module, n, "<absent>"))
        for n in [f[0] for f in FLIP] + list(UNCHANGED)
    )


print("UGSIM PLUGIN sim=%d preloaded=%s cfv=%s | %s" % (
    int(SIM),
    sorted(m for m in ("wildfire_model", "agents") if m in sys.modules),
    cfv.__file__, _snapshot(cfv)), flush=True)


def pytest_terminal_summary(terminalreporter):
    """After every test: prove the patch was still live at the end of the session."""
    tr = terminalreporter
    tr.write_line("UGSIM END cfv | " + _snapshot(cfv))
    agents = sys.modules.get("agents")
    if agents is not None:
        tr.write_line(
            "UGSIM END accessors extinguish=%r firebreak=%r range=%r gate=%r dry=%r"
            % (agents.ff_firefight_extinguish(), agents.ff_firefight_firebreak(),
               agents.ff_firefight_engaged_retreat_range(),
               agents.ff_firefight_mission_gate(), agents.ff_firefight_dry_run()))
