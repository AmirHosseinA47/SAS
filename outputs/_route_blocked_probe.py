"""Minimal constructed scenario: can route_blocked ever be set? Read-only probe."""
from __future__ import annotations
import contextlib, io as _io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel


def build():
    rng = random.Random(7)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=2, NUM_VICTIMS=1, NUM_FIREFIGHTERS=1,
                          WIND_DIRECTION="east", BATCH_SIZE=300,
                          FIRE_SPREAD_MULTIPLIER=0.75, PROBABILITY_MAP=False,
                          NUM_FIRE_TRACKERS=1, NUM_VICTIM_SEARCHERS=1)
    with contextlib.redirect_stdout(_io.StringIO()):
        m = WildFireModel()
        m.debug_log = False
    return m


def fire_at(model, cell):
    for a in model.grid.get_cell_list_contents([cell]):
        if type(a) is am.Fire:
            return a
    return None


def ignite(model, cell):
    f = fire_at(model, cell)
    if f is None:
        return False
    f.burning = True
    f.burnt = False
    f.has_burned = True
    return f.is_burning()


def scenario(name, neighbours_on_fire, self_on_fire):
    m = build()
    ff = list(m.firefighter_marker_agents.values())[0]
    cell = (25, 25)
    m.grid.move_agent(ff, cell)
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    ok = []
    for ox, oy in dirs[:neighbours_on_fire]:
        ok.append(ignite(m, (cell[0] + ox, cell[1] + oy)))
    selfok = ignite(m, cell) if self_on_fire else False
    ff.status = "assigned"
    ff.assigned = True
    ff.target_pos = (25, 40)
    ff.exiting = False
    burning_nb = sum(1 for c in ff._neighbor_cells() if ff._cell_contains_active_fire(c))
    self_fire = ff._cell_contains_active_fire(cell)
    with contextlib.redirect_stdout(_io.StringIO()):
        ff.advance()
    print("%-34s burning_nb=%d self_on_fire=%s -> status=%-14s moved_to=%s"
          % (name, burning_nb, self_fire, ff.status, ff.pos))
    return ff.status


print("mesa", __import__("mesa").__version__, "| python", sys.version.split()[0])
print()
for n in (0, 1, 2, 3, 4):
    scenario("neighbours_on_fire=%d" % n, n, False)
scenario("all-4 + standing IN fire", 4, True)
