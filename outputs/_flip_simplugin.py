"""Flip round, Part 1: simulate the BASE_STATION default flip WITHOUT editing source.

Loaded as a pytest plugin:  python -m pytest tests -p outputs._flip_simplugin
  FLIP_SIM=1  set the five flip constants on the common_fixed_variables MODULE at
              plugin import. -p plugins import before collection, so every test
              module and every module that star-imports cfv (wildfire_model,
              agents, ...) sees the flipped values exactly as if the source said
              so. A test's monkeypatch.setattr restores to the flipped value, as
              it would after a real flip.
  FLIP_SIM=0  patch nothing. The control for this plugin's own early import.

Valid only because no test reloads a module, spawns a subprocess or ships a
conftest (checked at b853617), so nothing re-reads the source constants.
The agents.py accessor FALLBACKS are not simulated; they are source edits.
"""
import os
import sys

import common_fixed_variables as cfv

FLIP = (
    ("BASE_STATION_MODE", 3),
    ("BASE_STATION_DEPOTS", 9),
    ("BASE_STATION_SPAWN_SPLIT", 2),
    ("UAV_RETURN_TO_BASE_RESERVE", 0.0),
    ("BASE_STATION_RETURN_MARGIN", 39.23),
)
UNCHANGED = (
    "BASE_STATION_RETURN_MECHANISM", "BASE_STATION_DOCK_FIX", "BASE_STATION_SIZE",
    "BASE_STATION_RETURN_STALL_LIMIT", "BASE_STATION_WAYPOINT_FIX",
    "BASE_STATION_SPAWN_FIREFIGHTERS", "ROUTE_BLOCK_STALE_CLEAR",
    "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE",
)
SIM = os.environ.get("FLIP_SIM", "0") == "1"

if SIM:
    for _name, _value in FLIP:
        setattr(cfv, _name, _value)


def _snapshot(module):
    return " ".join(
        "%s=%r" % (n, getattr(module, n, "<absent>"))
        for n in [f[0] for f in FLIP] + list(UNCHANGED)
    )


print("FLIPSIM PLUGIN sim=%d preloaded=%s cfv=%s | %s" % (
    int(SIM),
    sorted(m for m in ("wildfire_model", "agents") if m in sys.modules),
    cfv.__file__, _snapshot(cfv)), flush=True)


def pytest_terminal_summary(terminalreporter):
    """After every test: prove the patch was live in the star-import copies too."""
    tr = terminalreporter
    tr.write_line("FLIPSIM END cfv    | " + _snapshot(cfv))
    for modname in ("wildfire_model", "agents"):
        mod = sys.modules.get(modname)
        if mod is not None:
            tr.write_line("FLIPSIM END %-6s | %s" % (modname[:6], _snapshot(mod)))
    agents = sys.modules.get("agents")
    if agents is not None:
        tr.write_line(
            "FLIPSIM END accessors mode=%r depots=%r split=%r reserve=%r margin=%r"
            % (agents.base_station_mode(), agents.base_station_depots(),
               agents.base_station_spawn_split(), agents.uav_return_to_base_reserve(),
               agents.base_station_return_margin()))
