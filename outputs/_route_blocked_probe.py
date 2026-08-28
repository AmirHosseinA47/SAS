"""Constructed scenarios: when is route_blocked set? Read-only probe.

Rows 1-6 are the original six-row table (unchanged construction) so the
before/after comparison is like-for-like. Rows 7+ were added for the live-path
trigger, which the original construction cannot exercise: it only ever varies
the FF's own four neighbours, and the whole point of the new condition is that
it can fire while the neighbours are clear, and must NOT fire merely because
the local Manhattan gradient does not descend.
"""
from __future__ import annotations
import contextlib, io as _io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

SITES = {}
_orig_move = am.Firefighter._move_toward


def _traced_move(self, target):
    SITES.setdefault("lines", []).append(sys._getframe(1).f_lineno)
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


def _report(name, m, ff, cell, expect):
    burning_nb = sum(1 for c in ff._neighbor_cells() if ff._cell_contains_active_fire(c))
    self_fire = ff._cell_contains_active_fire(cell)
    tgt = ff.target_pos if not ff.exiting else ff.exit_target
    reachable = ff._path_exists_avoiding_fire(
        cell, (int(tgt[0]), int(tgt[1])), ff._fire_cells())
    SITES["lines"] = []
    with contextlib.redirect_stdout(_io.StringIO()):
        ff.advance()
    site = ",".join(str(x) for x in SITES.get("lines") or []) or "-"
    status = str(ff.status)
    ok = "OK " if status == expect else "FAIL"
    print("%s %-40s nb_fire=%d self_fire=%-5s path=%-5s site=%-5s -> status=%-14s moved=%-5s"
          % (ok, name, burning_nb, self_fire, reachable, site, status,
             ff.pos != cell))
    return status


def scenario(name, neighbours_on_fire, self_on_fire, expect):
    """Original construction: vary only the FF's own four neighbours."""
    m = build()
    ff = list(m.firefighter_marker_agents.values())[0]
    cell = (25, 25)
    m.grid.move_agent(ff, cell)
    for ox, oy in [(1, 0), (-1, 0), (0, 1), (0, -1)][:neighbours_on_fire]:
        ignite(m, (cell[0] + ox, cell[1] + oy))
    if self_on_fire:
        ignite(m, cell)
    ff.status = "assigned"
    ff.assigned = True
    ff.target_pos = (25, 40)
    ff.exiting = False
    return _report(name, m, ff, cell, expect)


def wall_scenario(name, *, gap=None, self_on_fire=False, exiting=False, expect="?",
                  extra_steps=0):
    """Fire wall at y=30 across the full grid width, FF at (25,25), goal beyond
    it at y=40. The FF's own four neighbours are CLEAR in every case here, so
    the original all-four-neighbours-burning condition can never fire; only a
    live-path test can tell 'walled in' from 'must take a detour'."""
    m = build()
    ff = list(m.firefighter_marker_agents.values())[0]
    cell = (25, 25)
    m.grid.move_agent(ff, cell)
    for x in range(0, 50):
        if gap is not None and x == gap:
            continue
        ignite(m, (x, 30))
    if self_on_fire:
        ignite(m, cell)
    ff.assigned = True
    ff.status = "assigned"
    if exiting:
        ff.exiting = True
        ff.exit_target = (25, 40)
        ff.target_pos = None
    else:
        ff.exiting = False
        ff.target_pos = (25, 40)
    status = _report(name, m, ff, cell, expect)
    for i in range(extra_steps):
        prev = ff.pos
        SITES["lines"] = []
        with contextlib.redirect_stdout(_io.StringIO()):
            ff.advance()
        site = ",".join(str(x) for x in SITES.get("lines") or []) or "-"
        print("     +step %d: site=%-5s -> status=%-14s moved=%s"
              % (i + 1, site, ff.status, ff.pos != prev))
        status = str(ff.status)
    return status


print("mesa", __import__("mesa").__version__, "| python", sys.version.split()[0])
print("call sites: 484=survival-fallthrough  533=moving-to-victim  568=exiting-with-victim")
print()
print("--- ORIGINAL SIX ROWS (neighbour-only construction) ---")
for n in (0, 1, 2, 3):
    scenario("neighbours_on_fire=%d" % n, n, False, "assigned")
scenario("neighbours_on_fire=4", 4, False, "route_blocked")
scenario("all-4 + standing IN fire", 4, True, "route_blocked")
print()
print("--- LIVE-PATH ROWS (neighbours all clear; wall at y=30) ---")
wall_scenario("walled off, no gap (GENUINELY STUCK)", gap=None, expect="route_blocked")
wall_scenario("wall with gap at x=0 (LONG DETOUR)", gap=0, expect="assigned")
wall_scenario("wall with gap at x=25 (direct-ish)", gap=25, expect="assigned")
# Standing in fire but with clear neighbours: _needs_immediate_survival_retreat
# is True and _survival_move() succeeds, so _move_toward is never reached that
# step and the trigger cannot evaluate (site "-"). The signal is not lost, only
# deferred: the +step lines below show it arriving at +2, once the unit has
# retreated far enough that _needs_immediate_survival_retreat goes False and
# site 522 runs. Scoped deliberately - _survival_move is out of bounds here.
wall_scenario("walled off + standing IN fire", gap=None, self_on_fire=True,
              expect="assigned", extra_steps=5)
wall_scenario("gap at x=0 + standing IN fire", gap=0, self_on_fire=True,
              expect="assigned")
wall_scenario("EXITING, walled off (scoped out)", gap=None, exiting=True,
              expect="assigned")
