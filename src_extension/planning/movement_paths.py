"""Firefighter movement layer: pure path helpers for the urgency round's three movement fixes
(outputs/urgency_part1.txt section 22, amendment B1; rulings 23).

PURE: no model, grid or RNG access. Every input is a cell, a set, or a predicate the caller builds from
the unit's own helpers (agents.Firefighter). Nothing is stored between calls.

  (a) FF_APPROACH_PATH       approach_choice      22.2.1
  (b) FF_RETREAT_KEEP_APPROACH  retreat_choice    22.3.1
  (c) FF_CARRY_REPLAN        least_exposure_first_step (C-1), shelter_step (C-2)   22.4.1

CLEAN = in bounds, not burning, not smoky, no burning 4-neighbour (the assigned-unit survival predicate).
G-ESC = the victim's clean region contains a grid-boundary cell (a clean way out exists).
Tie-breaks: the larger minimum fire distance, then SEARCH_ORDER (+x, -x, +y, -y) - agents.EXIT_LEG_SEARCH_ORDER.
"""

from __future__ import annotations

import heapq
from collections import deque
from typing import Callable, Iterable

Cell = tuple[int, int]
SEARCH_ORDER: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


def neighbours(cell: Cell, in_bounds: Callable[[Cell], bool]) -> list[Cell]:
    out = []
    for ox, oy in SEARCH_ORDER:
        n = (cell[0] + ox, cell[1] + oy)
        if in_bounds(n):
            out.append(n)
    return out


def clean_distance_field(target: Cell, is_clean: Callable[[Cell], bool],
                         in_bounds: Callable[[Cell], bool]) -> dict[Cell, int]:
    """BFS distance over CLEAN cells from `target`. The target must itself be clean: otherwise no clean path
    ends there and the field is empty. Distances are symmetric on this undirected 4-grid."""
    if not in_bounds(target) or not is_clean(target):
        return {}
    dist = {target: 0}
    queue = deque([target])
    while queue:
        cell = queue.popleft()
        for n in neighbours(cell, in_bounds):
            if n in dist or not is_clean(n):
                continue
            dist[n] = dist[cell] + 1
            queue.append(n)
    return dist


def region_has_exit(field: dict[Cell, int], is_boundary: Callable[[Cell], bool]) -> bool:
    """G-ESC: the clean region the field spans touches the grid boundary."""
    return any(is_boundary(c) for c in field)


def _order_index(origin: Cell, cell: Cell) -> int:
    offset = (cell[0] - origin[0], cell[1] - origin[1])
    return SEARCH_ORDER.index(offset) if offset in SEARCH_ORDER else len(SEARCH_ORDER)


def _best(origin: Cell, cells: list[Cell], fire_dist: Callable[[Cell], int]) -> Cell:
    """The larger fire distance, then search order."""
    return max(cells, key=lambda c: (fire_dist(c), -_order_index(origin, c)))


def approach_choice(unit_cell: Cell, field: dict[Cell, int], has_exit: bool, today_cell: Cell | None,
                    fire_dist: Callable[[Cell], int], in_bounds: Callable[[Cell], bool]) -> Cell | None:
    """Fix (a): the cell to step to, or None to keep today's step.

    Acts only when a shortest clean path exists from the unit (finite, non-zero distance), the victim's clean
    region has a clean way out, and today's step is NOT a neighbour on a shortest clean path (TODAY-FIRST,
    ruling V-6). Then: among the neighbours n with D(n) = D(unit) - 1, the larger fire distance, then search
    order."""
    d = field.get(unit_cell)
    if d is None or d == 0 or not has_exit:
        return None
    on_path = [n for n in neighbours(unit_cell, in_bounds) if field.get(n) == d - 1]
    if not on_path or today_cell in on_path:
        return None
    return _best(unit_cell, on_path, fire_dist)


def retreat_choice(unit_cell: Cell, field: dict[Cell, int], has_exit: bool, today_cell: Cell | None,
                   is_clean: Callable[[Cell], bool], fire_dist: Callable[[Cell], int],
                   in_bounds: Callable[[Cell], bool]) -> Cell | None:
    """Fix (b): the retreat cell, or None to run today's retreat verbatim.

    B = the clean neighbours with the smallest finite D (the victim's clean region, which must have a clean
    way out). Acts only when B is non-empty and today's retreat cell is not in B."""
    if not field or not has_exit:
        return None
    finite = [n for n in neighbours(unit_cell, in_bounds) if is_clean(n) and n in field]
    if not finite:
        return None
    dmin = min(field[n] for n in finite)
    best = [n for n in finite if field[n] == dmin]
    if today_cell in best:
        return None
    return _best(unit_cell, best, fire_dist)


def least_exposure_first_step(start: Cell, is_burning: Callable[[Cell], bool],
                              is_fire_adjacent: Callable[[Cell], bool], is_smoky: Callable[[Cell], bool],
                              is_boundary: Callable[[Cell], bool],
                              in_bounds: Callable[[Cell], bool]) -> Cell | None:
    """C-1: the first step of a least-exposure path over NON-BURNING cells to any non-burning boundary cell.

    Dijkstra with cost (fire-adjacent cells entered, smoky cells entered, length), compared lexicographically.
    The start is exempt. A goal is recognised when popped (minimum cost); ties by push order with
    SEARCH_ORDER (the replay's F5E rule, with the hazard count split into fire-adjacent and smoky)."""
    best = {start: (0, 0, 0)}
    prev: dict[Cell, Cell | None] = {start: None}
    heap = [(0, 0, 0, 0, start)]
    counter = 0
    while heap:
        fa, sm, length, _n, cell = heapq.heappop(heap)
        if best.get(cell) != (fa, sm, length):
            continue
        if cell != start and is_boundary(cell):
            node = cell
            while prev[node] != start:
                node = prev[node]
            return node
        for n in neighbours(cell, in_bounds):
            if is_burning(n):
                continue
            key = (fa + (1 if is_fire_adjacent(n) else 0), sm + (1 if is_smoky(n) else 0), length + 1)
            if n not in best or key < best[n]:
                best[n] = key
                prev[n] = cell
                counter += 1
                heapq.heappush(heap, (key[0], key[1], key[2], counter, n))
    return None


def shelter_step(start: Cell, is_burning: Callable[[Cell], bool], is_fire_adjacent: Callable[[Cell], bool],
                 is_smoky: Callable[[Cell], bool], fire_dist: Callable[[Cell], int],
                 in_bounds: Callable[[Cell], bool]) -> Cell | None:
    """C-2: in a pocket (no non-burning route to any boundary), the first step toward the safest pocket cell,
    or `start` to stay, or None when no non-burning neighbour exists (enclosed: C-3).

    Pocket = the non-burning cells reachable from `start` (start exempt). Target = the largest minimum fire
    distance, then not smoky, then the smallest depth, then discovery order. The start is a candidate only if
    it is not burning, so a carrier on a burning cell always moves.

    The step is the first step of a SHORTEST pocket path to the target that enters the fewest fire-adjacent
    cells, then the fewest smoky cells (22.4.4 g2 / g4; the reading of "step toward it" recorded in the Part 2
    notes), then push order with SEARCH_ORDER as in C-1. A shortest path keeps 22.4.3's monotone approach."""
    if not any(not is_burning(n) for n in neighbours(start, in_bounds)):
        return None
    depth = {start: 0}
    order = [start]
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        for n in neighbours(cell, in_bounds):
            if n in depth or is_burning(n):
                continue
            depth[n] = depth[cell] + 1
            order.append(n)
            queue.append(n)
    candidates = [c for c in order if not (c == start and is_burning(start))]
    rank = {c: i for i, c in enumerate(order)}
    target = max(candidates, key=lambda c: (fire_dist(c), 0 if is_smoky(c) else 1, -depth[c], -rank[c]))
    if target == start:
        return start
    best = {start: (0, 0, 0)}
    first: dict[Cell, Cell | None] = {start: None}
    heap = [(0, 0, 0, 0, start)]
    counter = 0
    while heap:
        length, fa, sm, _n, cell = heapq.heappop(heap)
        if best.get(cell) != (length, fa, sm):
            continue
        if cell == target:
            return first[cell]
        for n in neighbours(cell, in_bounds):
            if is_burning(n):
                continue
            key = (length + 1, fa + (1 if is_fire_adjacent(n) else 0), sm + (1 if is_smoky(n) else 0))
            if n not in best or key < best[n]:
                best[n] = key
                first[n] = n if cell == start else first[cell]
                counter += 1
                heapq.heappush(heap, (key[0], key[1], key[2], counter, n))
    return None
