"""Part-1 diagnostic: which _move_toward call site can actually reach
`scored == []` -> _mark_route_blocked, at current HEAD. Read-only."""
from __future__ import annotations
import contextlib, io as _io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

CALLS = []
_orig_move = am.Firefighter._move_toward


def _traced_move(self, target):
    line = sys._getframe(1).f_lineno
    nb = self._neighbor_cells()
    n_fire = sum(1 for c in nb if self._cell_contains_active_fire(c))
    CALLS.append({"line": line, "nb": len(nb), "n_fire": n_fire,
                  "scored_empty": n_fire == len(nb)})
    return _orig_move(self, target)


am.Firefighter._move_toward = _traced_move


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


def ignite(model, cell):
    for a in model.grid.get_cell_list_contents([cell]):
        if type(a) is am.Fire:
            a.burning, a.burnt, a.has_burned = True, False, True
            return a.is_burning()
    return False


def scenario(name, n_fire, self_fire, *, exiting):
    CALLS.clear()
    m = build()
    ff = list(m.firefighter_marker_agents.values())[0]
    cell = (25, 25)
    m.grid.move_agent(ff, cell)
    for ox, oy in [(1, 0), (-1, 0), (0, 1), (0, -1)][:n_fire]:
        ignite(m, (cell[0] + ox, cell[1] + oy))
    if self_fire:
        ignite(m, cell)
    ff.assigned = True
    ff.status = "en_route"
    if exiting:
        ff.exiting = True
        ff.exit_target = (25, 49)
        ff.target_pos = None
    else:
        ff.exiting = False
        ff.target_pos = (25, 40)
    need = ff._needs_immediate_survival_retreat()
    with contextlib.redirect_stdout(_io.StringIO()):
        ff.advance()
    sites = ",".join(str(c["line"]) for c in CALLS) or "-"
    empt = any(c["scored_empty"] for c in CALLS)
    print("%-46s need_retreat=%-5s call_site_line=%-6s scored_empty=%-5s "
          "status=%-14s pos=%s"
          % (name, need, sites, empt, ff.status, ff.pos))


print("mesa", __import__("mesa").__version__)
print("call sites: 472=survival-fallthrough  521=moving-to-victim  "
      "556=exiting-with-victim")
print()
print("--- ASSIGNED / NOT EXITING ---")
for n in (0, 3, 4):
    scenario("assigned nb_fire=%d" % n, n, False, exiting=False)
scenario("assigned nb_fire=4 + self on fire", 4, True, exiting=False)
print()
print("--- EXITING WITH VICTIM ---")
for n in (0, 3, 4):
    scenario("exiting  nb_fire=%d" % n, n, False, exiting=True)
scenario("exiting  nb_fire=4 + self on fire", 4, True, exiting=True)
