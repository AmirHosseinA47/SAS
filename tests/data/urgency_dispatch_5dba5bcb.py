"""Managing system, DISPATCH: urgency-aware re-dispatch order (urgency round U1; outputs/urgency_part1.txt
sections 6-10, rulings 21 and 23).

PURE: no model, grid or RNG access. Inputs are plain cells, sets and callables; the model builds them
(wildfire_model.WildFireModel._urgency_dispatch_view) and applies the order through today's loop body.

THE RULE (9.1). At a QUALIFYING kick - exactly one free unit, two or more waiting victims, at least one
burning cell (6) - the waiting victims are ordered by
    key(v) = (0, T(v), c(f, v), idx(v))   if v is PROMOTABLE
             (1, idx(v))                  otherwise (DEFERRED - kept in today's victim-index order),
where
    T(v)     FAE's arrival time at v's current cell (published rates, the true burning set, the wind;
             fire_arrival_estimate.arrival_time with FrontPriorityParams() defaults - never the SEARCHER_FP_*
             knobs, ruling U-6),
    c(f, v)  the SAFE-IN-TIME route (8.2): the hop count of a BFS from the free unit's cell over CLEAN cells
             (not burning, not smoky, not 4-adjacent to a burning cell), where a cell x is entered at hop k
             only if T*(x) > k, T*(x) = min of T over x and its in-grid 4-neighbours; the unit's own cell is
             exempt, the victim's cell is not,
    promotable  iff c(f, v) is finite and c(f, v) + 1 <= T(v) (8.3),
    idx(v)   the INTEGER victim index ("victim_10" after "victim_2").
Ties beyond the key do not exist (idx is unique). Nothing here unbinds, writes off or stores anything.
"""

from __future__ import annotations

import math
import re
from collections import deque
from typing import Callable, Iterable

from src_extension.planning.fire_arrival_estimate import FrontPriorityParams, arrival_time

Cell = tuple[int, int]
SEARCH_ORDER: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
_INDEX_RE = re.compile(r"(\d+)\s*$")


def victim_index(victim_id: object) -> int:
    """The integer index of a victim id ("victim_10" -> 10); ids without one sort last."""
    match = _INDEX_RE.search(str(victim_id))
    return int(match.group(1)) if match else 10 ** 9


def qualifies(n_waiting: int, n_free: int, any_burning: bool) -> bool:
    """A kick is ordered by urgency only with exactly one free unit, two or more waiting victims and a
    fire (6; ruling U-3: |F| = 1 covers every recorded scarce kick and never re-pairs)."""
    return int(n_free) == 1 and int(n_waiting) >= 2 and bool(any_burning)


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


def urgency_order(waiting: list[tuple[str, Cell]], unit_cell: Cell, burning: Iterable[Cell],
                  smoky: Iterable[Cell], wind: tuple[float, float] | None, x_size: int, y_size: int,
                  params: FrontPriorityParams | None = None) -> tuple[list[str], dict[str, dict]]:
    """Order `waiting` ([(victim_id, current cell)], today's index order) for the one free unit at
    `unit_cell`. Returns (ordered ids, per-victim records {T, c, promotable, key})."""
    burning = [(int(x), int(y)) for x, y in burning]
    t_grid = arrival_time(x_size, y_size, burning, wind, params if params is not None else FrontPriorityParams())
    unclean = unclean_cells(burning, smoky, x_size, y_size)
    unit = (int(unit_cell[0]), int(unit_cell[1]))
    hops = safe_route_hops(unit, x_size, y_size, unclean, lambda c: t_star(t_grid, c, x_size, y_size))
    records: dict[str, dict] = {}
    for vid, cell in waiting:
        vc = (int(cell[0]), int(cell[1]))
        t_v = float(t_grid[vc[0], vc[1]])
        c = hops.get(vc)
        if vc in unclean:
            c = None
        promotable = c is not None and (c + 1) <= t_v
        idx = victim_index(vid)
        key = (0, t_v, c, idx) if promotable else (1, idx)
        records[vid] = {"T": t_v, "c": c, "promotable": promotable, "key": key, "cell": vc}
    ordered = sorted((vid for vid, _cell in waiting), key=lambda v: records[v]["key"])
    return ordered, records


def triage_line(step: object, unit_id: object, ordered: list[str], records: dict[str, dict],
                served: str | None) -> str:
    """The ON-path [UrgencyTriage] console line, printed after the kick's binds (13.3; the instrument records the
    kick site). `served` is the victim actually bound, or None (printed "none") when every dispatch was refused."""
    parts = []
    for vid in ordered:
        rec = records[vid]
        t_v = rec["T"]
        t_txt = "inf" if math.isinf(t_v) else f"{t_v:.1f}"
        c_txt = "inf" if rec["c"] is None else str(rec["c"])
        parts.append(f"{vid}(T={t_txt},c={c_txt},{'P' if rec['promotable'] else 'D'})")
    served_txt = "none" if served is None else served
    return f"[UrgencyTriage] step={step} unit={unit_id} order=[{' '.join(parts)}] served={served_txt}"
