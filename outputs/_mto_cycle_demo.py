"""Executable demonstration: does the REAL `_move_toward` cycle on a frozen board?

Not a hand-argument.  This binds the ACTUAL `agents.Firefighter._move_toward`
and the actual selection helpers it depends on (`_neighbor_cells`,
`_cell_adjacent_to_fire`, `_firefighter_cell_risk`, `_path_exists_avoiding_fire`)
to a stub whose ONLY overrides are the three grid-content predicates
(`_cell_contains_active_fire`, `_cell_has_active_smoke`, `_fire_cells`), which
read from explicit frozen sets instead of from Mesa agents.

So the tier chain, the tie-breaks, the risk scores and the route-blocked test
are the shipped code, verbatim.  Only the board is synthetic - and frozen,
which is the whole point: it removes the one thing that repairs a dither.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am


class FakeGrid:
    def __init__(self, w, h):
        self.width, self.height = w, h

    def out_of_bounds(self, cell):
        x, y = cell
        return not (0 <= x < self.width and 0 <= y < self.height)

    def move_agent(self, agent, cell):
        agent.pos = cell


class FakeModel:
    def __init__(self, w, h):
        self.grid = FakeGrid(w, h)

    _on_firefighter_route_blocked = None


class Stub(am.Firefighter):
    """Real _move_toward, real tiering, real risk. Frozen synthetic board."""

    def __init__(self, pos, fires, smokes, w=12, h=12):
        self.pos = pos
        self.model = FakeModel(w, h)
        self._fires = set(fires)
        self._smokes = set(smokes)
        self.exiting = False
        self.assigned = True
        self.status = "assigned"
        self.unit_id = "demo"
        self._last_move_tier = 0
        self._last_move_risk = 0
        self.blocked_calls = 0

    # --- the ONLY overrides: where fire and smoke live -------------------
    def _cell_contains_active_fire(self, cell):
        return tuple(cell) in self._fires

    def _cell_has_active_smoke(self, cell):
        return tuple(cell) in self._smokes

    def _fire_cells(self):
        return set(self._fires)

    def _mark_route_blocked(self):
        self.blocked_calls += 1
        self.status = "route_blocked"


def render(w, h, fires, smokes, target, path):
    seen = {}
    for i, p in enumerate(path):
        seen.setdefault(p, i)
    rows = []
    for y in range(h - 1, -1, -1):
        row = []
        for x in range(w):
            c = (x, y)
            if c == target:
                row.append(" T")
            elif c in fires:
                row.append(" #")
            elif c in smokes:
                row.append(" ~")
            elif c in seen:
                row.append("%2d" % seen[c])
            else:
                row.append(" .")
        rows.append("".join(row))
    return "\n".join("    " + r for r in rows)


def demo(name, start, target, fires, smokes, steps=24, w=12, h=12):
    ff = Stub(start, fires, smokes, w, h)
    path = [ff.pos]
    tiers = []
    for _ in range(steps):
        ff._move_toward(target)
        path.append(ff.pos)
        tiers.append(ff._last_move_tier)
    print()
    print("-" * 74)
    print("  %s" % name)
    print("-" * 74)
    print("    start %s   target %s   fires %s   smoke %s"
          % (start, target, sorted(fires), sorted(smokes)))
    print()
    print(render(w, h, fires, smokes, target, path))
    print()
    print("    path : " + " -> ".join(str(p) for p in path[:14])
          + (" ..." if len(path) > 14 else ""))
    print("    tiers: " + " ".join(str(t) for t in tiers[:13])
          + (" ..." if len(tiers) > 13 else ""))
    distinct = len(set(path))
    print("    %d steps, %d DISTINCT cells visited" % (steps, distinct))
    tail = path[2:]
    period = None
    for p in (2, 3, 4, 6):
        if len(tail) > 3 * p and all(tail[i] == tail[i + p]
                                     for i in range(len(tail) - p)):
            period = p
            break
    print("    route_blocked raised: %d time(s)" % ff.blocked_calls)
    if period:
        cyc = tail[:period]
        print("    ==> STABLE LIMIT CYCLE, period %d over %s"
              % (period, " <-> ".join(str(c) for c in cyc)))
        print("    ==> on a frozen board this NEVER terminates.")
    else:
        print("    ==> no stable cycle; reached %s" % str(path[-1]))
    return period


def main():
    print("=" * 74)
    print("  REAL agents.Firefighter._move_toward ON A FROZEN SYNTHETIC BOARD")
    print("=" * 74)
    print("  legend:  T target   # active fire   ~ smoke   N = step index first")
    print("           visited at that cell   . unvisited")

    # ---- 1. the tier1 <-> tier3 barrier cycle -------------------------------
    # Target at (2,5).  A solid fire wall at x=4 spanning the corridor, so the
    # cells at x=5 adjacent to it are all adjacent_fire.  The unit starts east
    # of the wall.  From (6,5) the improving step (5,5) is adjacent to fire, so
    # tier 1 is empty and tier 3 pushes it back east; from (7,5) the improving
    # step (6,5) is clean, so tier 1 pulls it west again.
    wall = {(4, y) for y in range(2, 9)}
    demo("1. FIRE WALL ACROSS THE APPROACH  (tier1 <-> tier3)",
         start=(7, 5), target=(2, 5), fires=wall, smokes=set())

    # ---- 2. same shape, made of smoke rather than fire ----------------------
    smoke = {(5, y) for y in range(3, 8)}
    demo("2. SMOKE BAND INSTEAD OF FIRE  (same cycle, no fire at all)",
         start=(7, 5), target=(2, 5), fires=set(), smokes=smoke)

    # ---- 3. control: no barrier, the same start and target -----------------
    # HARNESS CAVEAT: this stub calls `_move_toward` unconditionally, so it
    # keeps calling it after arrival.  The real `advance` tests
    # `self.pos == self.target_pos` BEFORE calling, and flips to `exiting`
    # instead, so the two-cell wobble visible at the END of this path once the
    # unit is standing on the target is an artefact of the harness and is NOT
    # claimed as model behaviour.  What the control establishes is the first
    # five steps: with no barrier the unit walks straight in on tier 1.
    demo("3. CONTROL - NO BARRIER (proves the cycle is the barrier, not the code)",
         start=(7, 5), target=(2, 5), fires=set(), smokes=set())

    # ---- 4. does route_blocked fire during the barrier cycle? --------------
    # The wall above does not separate the grid: the unit can walk around it,
    # so `_path_exists_avoiding_fire` is TRUE and route_blocked is never raised.
    # Seal the wall to the grid edges and see the difference.
    sealed = {(4, y) for y in range(0, 12)}
    demo("4. SEALED WALL - route_blocked IS raised, and the unit still cycles",
         start=(7, 5), target=(2, 5), fires=sealed, smokes=set())

    print()
    print("=" * 74)
    print("  WHAT A GUARD WOULD HAVE DONE, IN CASE 1")
    print("=" * 74)
    ff = Stub((7, 5), wall, set())
    ff._move_toward((2, 5))
    at = ff.pos
    print("    unit steps to %s (tier %d)" % (at, ff._last_move_tier))
    # now forbid the step back and see what the real tier chain yields
    back = (7, 5)
    print("    at %s the shipped code would return to %s. Forbid it:" % (at, back))
    cands = []
    for c in ff._neighbor_cells():
        if ff._cell_contains_active_fire(c):
            tagc = "ON FIRE (excluded before tiering)"
        elif ff._cell_adjacent_to_fire(c):
            tagc = "adjacent to fire  risk=%d" % ff._firefighter_cell_risk(c)
        elif ff._cell_has_active_smoke(c):
            tagc = "smoky  risk=%d" % ff._firefighter_cell_risk(c)
        else:
            tagc = "clean  risk=%d" % ff._firefighter_cell_risk(c)
        d = abs(c[0] - 2) + abs(c[1] - 5)
        cands.append((c, d, tagc, c == back))
    for c, d, tagc, isback in sorted(cands, key=lambda z: z[1]):
        print("        %-8s dist->target %2d   %-34s %s"
              % (str(c), d, tagc, "<- the forbidden step back" if isback else ""))
    print()
    print("    The forbidden cell is the ONLY clean one that does not increase")
    print("    distance-to-target.  A guard therefore hands the unit either a")
    print("    cell further from the victim, or a hazardous one.")


main()
