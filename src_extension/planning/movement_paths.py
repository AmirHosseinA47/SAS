"""Firefighter movement layer: pure path helpers for movement fixes (a) and (b) and the stranding guard (MVG round;
outputs/urgency_part1d.txt, amendment C1 in its section 1d.13; the fixes as screened in the urgency round,
outputs/urgency_part1.txt section 22).

PURE: no model, grid or RNG access. Every input is a cell, a set, or a predicate the caller builds from
the unit's own helpers (agents.Firefighter). Nothing is stored between calls.

  (a) FF_APPROACH_PATH          approach_choice      Part 1 22.2.1
  (b) FF_RETREAT_KEEP_APPROACH  retreat_choice       Part 1 22.3.1
  guard FF_FIX_STRANDING_GUARD  stranding_guard      Part 1d 1d.2.2 (SG-T)

CLEAN = in bounds, not burning, not smoky, no burning 4-neighbour (the assigned-unit survival predicate).
G-ESC = the victim's clean region contains a grid-boundary cell (a clean way out exists).
Tie-breaks: the larger minimum fire distance, then SEARCH_ORDER (+x, -x, +y, -y) - agents.EXIT_LEG_SEARCH_ORDER.
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Iterable

from src_extension.planning.fire_arrival_estimate import FrontPriorityParams, arrival_time

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


# ---- The stranding guard SG-T (Part 1d 1d.2.2) ---------------------------------------------------------------------
# unclean_cells, t_star and safe_route_hops are U1's (urgency round, src_extension/planning/urgency_dispatch.py at
# 5dba5bcb), ported VERBATIM: U1 is not carried into this round (ruling, urgency report section 11), its safe-in-time
# route test is (ruling W-1 (a)). stranding_guard applies that test at the cell a fix would step to.

def _in_bounds(cell: Cell, x_size: int, y_size: int) -> bool:
    return 0 <= cell[0] < x_size and 0 <= cell[1] < y_size


def unclean_cells(burning: Iterable[Cell], smoky: Iterable[Cell], x_size: int, y_size: int) -> set[Cell]:
    """Burning, smoky, or 4-adjacent to a burning cell: the cells an assigned unit's survival rule refuses
    (agents.Firefighter._needs_immediate_survival_retreat)."""
    out: set[Cell] = set()
    for x, y in burning:
        cell = (int(x), int(y))
        out.add(cell)
        for ox, oy in SEARCH_ORDER:
            n = (cell[0] + ox, cell[1] + oy)
            if _in_bounds(n, x_size, y_size):
                out.add(n)
    for x, y in smoky:
        out.add((int(x), int(y)))
    return out


def t_star(t_grid, cell: Cell, x_size: int, y_size: int) -> float:
    """min of T over `cell` and its in-grid 4-neighbours."""
    best = float(t_grid[cell[0], cell[1]])
    for ox, oy in SEARCH_ORDER:
        n = (cell[0] + ox, cell[1] + oy)
        if _in_bounds(n, x_size, y_size):
            value = float(t_grid[n[0], n[1]])
            if value < best:
                best = value
    return best


def safe_route_hops(source: Cell, x_size: int, y_size: int, unclean: set[Cell],
                    t_star_of: Callable[[Cell], float]) -> dict[Cell, int]:
    """The time-expanded clean BFS of 8.2: hop counts from `source` (exempt, hop 0). A cell is entered at
    hop k >= 1 iff in bounds, not unclean and t_star_of(cell) > k. Passability only tightens with k, so the
    first discovery is the earliest feasible arrival."""
    hops = {source: 0}
    queue = deque([source])
    while queue:
        cell = queue.popleft()
        k = hops[cell] + 1
        for ox, oy in SEARCH_ORDER:
            n = (cell[0] + ox, cell[1] + oy)
            if n in hops or not _in_bounds(n, x_size, y_size) or n in unclean:
                continue
            if not t_star_of(n) > k:
                continue
            hops[n] = k
            queue.append(n)
    return hops


def stranding_guard(unit_cell: Cell, step_cell: Cell, victim_cell: Cell, burning: Iterable[Cell],
                    smoky: Iterable[Cell], wind: tuple[float, float] | None, x_size: int, y_size: int,
                    params: FrontPriorityParams | None = None) -> tuple[bool, int | None, float]:
    """SG-T (1d.2.2): (admit, c_n, T(v)) for a fix stepping from `unit_cell` u to `step_cell` n toward the victim at
    `victim_cell` v. T = FAE's arrival time over the true burning set and the wind (FrontPriorityParams() defaults,
    never the SEARCHER_FP_* knobs); c_n = the earliest hop at which v is entered on a time-expanded CLEAN route whose
    first step is u -> n (n entered at hop 1 iff clean now and T*(n) > 1; afterwards a cell at hop k iff clean now and
    T*(x) > k; u not re-entered); ADMIT iff c_n is finite and c_n + 1 <= T(v). The frozen reference implementation
    is outputs/_mvg_guard_diag.guard (test T-G7)."""
    u = (int(unit_cell[0]), int(unit_cell[1]))
    n = (int(step_cell[0]), int(step_cell[1]))
    v = (int(victim_cell[0]), int(victim_cell[1]))
    burning = [(int(x), int(y)) for x, y in burning]
    t_grid = arrival_time(x_size, y_size, burning, wind, params if params is not None else FrontPriorityParams())
    unclean = unclean_cells(burning, smoky, x_size, y_size)
    t_v = float(t_grid[v[0], v[1]])
    if n in unclean or not t_star(t_grid, n, x_size, y_size) > 1:
        return False, None, t_v
    hops = safe_route_hops(n, x_size, y_size, unclean | {u}, lambda x: t_star(t_grid, x, x_size, y_size) - 1)
    if v not in hops:
        return False, None, t_v
    c_n = 1 + hops[v]
    return (c_n + 1) <= t_v, c_n, t_v
