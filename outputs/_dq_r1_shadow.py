"""Dispatch round: the joint dispatcher J (outputs/dispatch_part1.txt sections 5-7; rulings section 20;
amendment A1 section 21).

Pure functions over plain data - no model, grid, agent or RNG access. wildfire_model builds the inputs (cells,
sets, dicts of distances, the ledger) and applies J's output through the RescueExecutor; this module only decides.

LIMIT 2 - solve_fill: free units x waiting victims, chosen exactly by the lexicographic key (design 5.4)
    L1 most victims served, L2 fewest re-used pairs, L3 least total route time, L4 least worst route time,
    L5 smallest sorted (victim index, unit index) list, indices parsed as INTEGERS.
LIMIT 3 - progress_step / update_persistence / plan_replacements: the stall rule (design 6.3-6.4: S counted
    steps without the unit's OWN progress, fire and victim motion factored out, a clean approach required of
    the challenger) and the margin rule (design 6.5: M steps better for P consecutive evaluations). A REPLACE
    may use only a never-bound pair (ledger b = 0) - the device behind the no-reversal theorem (design 6.9).

Route distances come from bfs_distances rooted at the VICTIM over cells that are not blocked; route_distance
reads a unit's cell with the unit's own exemption (the route test never tests its source), so
route_distance(...) is not None  <=>  Firefighter._path_exists_avoiding_fire(unit, victim, burning).
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Mapping as _MappingABC
from dataclasses import dataclass, field, replace
from math import comb, perm
from typing import Iterable, Mapping, Sequence

Cell = tuple[int, int]

# 4-connected, in the movers' neighbour order (+x, -x, +y, -y).
_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))

# Design 5.5: exhaustive enumeration, refused (never silently degraded) above this many configurations.
MAX_CONFIGURATIONS = 100_000

_TRAILING_INT = re.compile(r"(\d+)$")


def id_index(identifier: str) -> tuple[int, str]:
    """Integer tie-break key: the trailing integer of an id ("ff_unit_10" -> 10, "victim_3" -> 3), then the
    id itself. An id without a trailing integer sorts after every numbered id."""
    text = str(identifier)
    match = _TRAILING_INT.search(text)
    return (int(match.group(1)) if match else 10**9, text)


# --------------------------------------------------------------------------- route distances

class GridDistances(_MappingABC):
    """BFS distances on a flat array (index x * y_size + y; -1 = not reached), read as a Mapping Cell -> int
    holding exactly the reached cells - the same contents the dict-based search produced, without its per-cell
    tuple and hash cost (design 12.2's per-search budget)."""

    __slots__ = ("_dist", "_x_size", "_y_size")

    def __init__(self, dist: list[int], x_size: int, y_size: int) -> None:
        self._dist = dist
        self._x_size = x_size
        self._y_size = y_size

    def _index(self, cell: object) -> int:
        try:
            x, y = int(cell[0]), int(cell[1])  # type: ignore[index]
        except (TypeError, IndexError, ValueError):
            return -1
        if 0 <= x < self._x_size and 0 <= y < self._y_size:
            return x * self._y_size + y
        return -1

    def __contains__(self, cell: object) -> bool:
        i = self._index(cell)
        return i >= 0 and self._dist[i] >= 0

    def __getitem__(self, cell: Cell) -> int:
        i = self._index(cell)
        if i < 0 or self._dist[i] < 0:
            raise KeyError(cell)
        return self._dist[i]

    def get(self, cell: Cell, default: int | None = None) -> int | None:
        i = self._index(cell)
        return default if i < 0 or self._dist[i] < 0 else self._dist[i]

    def __iter__(self):
        y_size = self._y_size
        for i, d in enumerate(self._dist):
            if d >= 0:
                yield (i // y_size, i % y_size)

    def __len__(self) -> int:
        return sum(1 for d in self._dist if d >= 0)


def _bfs_dict(source: Cell, x_size: int, y_size: int, blocked_set: set[Cell] | frozenset[Cell]) -> dict[Cell, int]:
    """The plain dict search - used only for a source outside the grid (never a victim's cell)."""
    start = (int(source[0]), int(source[1]))
    dist: dict[Cell, int] = {start: 0}
    queue: deque[Cell] = deque([start])
    while queue:
        cx, cy = queue.popleft()
        nd = dist[(cx, cy)] + 1
        for ox, oy in _NEIGHBOURS:
            nx, ny = cx + ox, cy + oy
            if nx < 0 or ny < 0 or nx >= x_size or ny >= y_size:
                continue
            cell = (nx, ny)
            if cell in dist or cell in blocked_set:
                continue
            dist[cell] = nd
            queue.append(cell)
    return dist


def bfs_distances(source: Cell, x_size: int, y_size: int, blocked: Iterable[Cell]) -> Mapping[Cell, int]:
    """4-connected BFS from `source` over in-bounds cells not in `blocked`. The source itself is never tested
    (a victim's cell may burn - the destination exemption of the units' route test). Returns a read-only
    Mapping Cell -> distance holding exactly the reached cells."""
    blocked_set = blocked if isinstance(blocked, (set, frozenset)) else set(blocked)
    sx, sy = int(source[0]), int(source[1])
    if not (0 <= sx < x_size and 0 <= sy < y_size):
        return _bfs_dict(source, x_size, y_size, blocked_set)
    n = x_size * y_size
    dist = [-1] * n
    for bx, by in blocked_set:
        if 0 <= bx < x_size and 0 <= by < y_size:
            dist[bx * y_size + by] = -2
    start = sx * y_size + sy
    dist[start] = 0
    queue = [start]
    head = 0
    last_row = (x_size - 1) * y_size
    while head < len(queue):
        i = queue[head]
        head += 1
        nd = dist[i] + 1
        y = i % y_size
        if i < last_row and dist[i + y_size] == -1:
            dist[i + y_size] = nd
            queue.append(i + y_size)
        if i >= y_size and dist[i - y_size] == -1:
            dist[i - y_size] = nd
            queue.append(i - y_size)
        if y < y_size - 1 and dist[i + 1] == -1:
            dist[i + 1] = nd
            queue.append(i + 1)
        if y > 0 and dist[i - 1] == -1:
            dist[i - 1] = nd
            queue.append(i - 1)
    for bx, by in blocked_set:
        if 0 <= bx < x_size and 0 <= by < y_size and dist[bx * y_size + by] == -2:
            dist[bx * y_size + by] = -1
    return GridDistances(dist, x_size, y_size)


def route_distance(dist: Mapping[Cell, int], cell: Cell, blocked: Iterable[Cell]) -> int | None:
    """d at a unit's cell, from a BFS rooted at the victim. The unit's own cell is exempt like the source of the
    route test: if it is blocked it is reached through its nearest reached 4-neighbour. None = no route."""
    here = (int(cell[0]), int(cell[1]))
    if here in dist:
        return dist[here]
    blocked_set = blocked if isinstance(blocked, (set, frozenset)) else set(blocked)
    if here not in blocked_set:
        return None
    best: int | None = None
    for ox, oy in _NEIGHBOURS:
        near = (here[0] + ox, here[1] + oy)
        if near in dist and (best is None or dist[near] < best):
            best = dist[near]
    return None if best is None else best + 1


def unclean_cells(burning: Iterable[Cell], smoky: Iterable[Cell]) -> set[Cell]:
    """Cells where an assigned unit cannot stand (design 6.3): burning, smoky, or 4-adjacent to a burning cell -
    the cells that trigger Firefighter._needs_immediate_survival_retreat for an assigned unit."""
    burning_set = set(burning)
    out = set(burning_set) | set(smoky)
    for bx, by in burning_set:
        for ox, oy in _NEIGHBOURS:
            out.add((bx + ox, by + oy))
    return out


# --------------------------------------------------------------------------- LIMIT 2: the fill

@dataclass(frozen=True)
class FillPair:
    victim: str
    unit: str
    distance: int
    reused: bool


def count_configurations(n_units: int, n_victims: int) -> int:
    """Injective partial maps units -> victims: sum_k C(n_units, k) P(n_victims, k) (136 at 3 x 5)."""
    return sum(comb(n_units, k) * perm(n_victims, k) for k in range(min(n_units, n_victims) + 1))


def solve_fill(
    units: Sequence[str],
    victims: Sequence[str],
    distance: Mapping[tuple[str, str], int | None],
    ledger: Mapping[tuple[str, str], int],
    *,
    capped: Iterable[str] = (),
) -> list[FillPair]:
    """Limit 2's fill (design 5.4-5.6): the lexicographically best matching of free `units` to waiting `victims`.

    distance[(unit, victim)] is the route distance (None or missing = no route; never allowed).
    ledger[(unit, victim)] = b, the binds of that pair so far. A pair with b >= 1 is RE-USED (L2 prefers fresh
    pairs among maximum matchings). Victims in `capped` are LATCH-FILL targets: a pair with b >= 2 is not
    allowed for them (design 5.6). Returned in victim order.
    """
    unit_list = sorted({str(u) for u in units}, key=id_index)
    victim_list = sorted({str(v) for v in victims}, key=id_index)
    capped_set = {str(v) for v in capped}
    n_configs = count_configurations(len(unit_list), len(victim_list))
    if n_configs > MAX_CONFIGURATIONS:
        raise ValueError(
            f"joint dispatch: {n_configs} configurations for {len(unit_list)} units x {len(victim_list)} victims "
            f"exceed {MAX_CONFIGURATIONS} (design 5.5)"
        )

    options: dict[str, list[tuple[str, int, bool]]] = {}
    for unit in unit_list:
        row: list[tuple[str, int, bool]] = []
        for victim in victim_list:
            d = distance.get((unit, victim))
            if d is None:
                continue
            b = int(ledger.get((unit, victim), 0) or 0)
            if victim in capped_set and b >= 2:
                continue
            row.append((victim, int(d), b >= 1))
        options[unit] = row

    best_key: tuple | None = None
    best_pairs: list[FillPair] = []

    def score(pairs: list[FillPair]) -> tuple:
        n = len(pairs)
        total = sum(p.distance for p in pairs)
        worst = max((p.distance for p in pairs), default=0)
        reused = sum(1 for p in pairs if p.reused)
        ids = sorted((id_index(p.victim), id_index(p.unit)) for p in pairs)
        return (-n, reused, total, worst, ids)

    def walk(i: int, used: frozenset[str], chosen: list[FillPair]) -> None:
        nonlocal best_key, best_pairs
        if i == len(unit_list):
            key = score(chosen)
            if best_key is None or key < best_key:
                best_key = key
                best_pairs = list(chosen)
            return
        unit = unit_list[i]
        walk(i + 1, used, chosen)
        for victim, d, reused in options[unit]:
            if victim in used:
                continue
            chosen.append(FillPair(victim=victim, unit=unit, distance=d, reused=reused))
            walk(i + 1, used | {victim}, chosen)
            chosen.pop()

    walk(0, frozenset(), [])
    return sorted(best_pairs, key=lambda p: id_index(p.victim))


# --------------------------------------------------------------------------- LIMIT 3: progress and stall

@dataclass(frozen=True)
class Progress:
    """Per-binding progress state (design 6.3), reset at every bind."""

    best: int
    k: int
    d_prev: int
    cell_prev: Cell
    age: int = 0
    persist: tuple[tuple[str, int], ...] = field(default_factory=tuple)

    def persist_map(self) -> dict[str, int]:
        return dict(self.persist)


def new_progress(d: int, cell: Cell) -> Progress:
    """The state of a binding at its bind (design 7.1 step 4)."""
    return Progress(best=int(d), k=0, d_prev=int(d), cell_prev=(int(cell[0]), int(cell[1])))


def progress_step(state: Progress, d_now: int | None, x_now: int | None, cell_now: Cell, frozen: bool) -> Progress:
    """One J-post update (design 6.3).

    d_now = the incumbent's route distance from its CURRENT cell, x_now = from its PREVIOUS cell - both on the
    current burning set and the victim's current cell. e = x_now - d_prev is the change the unit did not cause
    (fire, either sign; the victim, any direction); the reference `best` shifts by it, so only the unit's own
    moves can beat it. `frozen` (no unit has a clean approach) stops k from advancing. A closed route (either
    distance None) leaves the state untouched: the unit's own route test raises route_blocked at its next move.
    """
    if d_now is None or x_now is None:
        return state
    best = state.best + (int(x_now) - state.d_prev)
    k = state.k
    if d_now == 0:
        best, k = 0, 0
    elif d_now < best:
        best, k = int(d_now), 0
    elif not frozen:
        k += 1
    return replace(
        state,
        best=best,
        k=k,
        d_prev=int(d_now),
        cell_prev=(int(cell_now[0]), int(cell_now[1])),
        age=state.age + 1,
    )


def update_persistence(
    state: Progress,
    spare_distance: Mapping[str, int | None],
    d_incumbent: int | None,
    margin: int,
    fresh: Mapping[str, bool],
) -> Progress:
    """The margin persistence counters of one binding (design 6.5): spare B's count rises by one at each
    evaluation where (B, v) is fresh and d(B, v) + margin <= d(A, v), and resets otherwise - including every
    evaluation at which B is not a spare (it is absent from spare_distance)."""
    previous = state.persist_map()
    counts: dict[str, int] = {}
    for unit, d in spare_distance.items():
        if d is None or d_incumbent is None or not fresh.get(unit, False):
            continue
        if int(d) + int(margin) <= int(d_incumbent):
            counts[unit] = previous.get(unit, 0) + 1
    ordered = tuple(sorted(counts.items(), key=lambda kv: id_index(kv[0])))
    return replace(state, persist=ordered)


@dataclass(frozen=True)
class Contest:
    """A contestable binding at J-post (design 6.2): victim, its only (active) binder, its current route distance,
    its stall count and its margin persistence counters."""

    victim: str
    incumbent: str
    d: int
    k: int
    persist: Mapping[str, int]


@dataclass(frozen=True)
class Replacement:
    victim: str
    old_unit: str
    new_unit: str
    cause: str  # "stall" | "margin"
    distance: int


def plan_replacements(
    contests: Sequence[Contest],
    spares: Sequence[str],
    distance: Mapping[tuple[str, str], int | None],
    ledger: Mapping[tuple[str, str], int],
    clean: Mapping[tuple[str, str], bool],
    *,
    stall_steps: int,
    margin_persist: int,
) -> list[Replacement]:
    """Limit 3's replacements at one J-post (design 6.4, 6.5, 6.7 step 3).

    STALL (k >= stall_steps): spare B replaces A iff (B, v) is fresh, B has a clean approach (clean[(B, v)])
    and d(B, v) < d(A, v) + k; candidates by least d(B, v), then integer id. Stalled incumbents are served first,
    by largest k, then largest gain, then victim id.
    MARGIN (k < stall_steps): spare B replaces A iff (B, v) is fresh and its persistence count reached
    margin_persist; candidates by largest gain d(A, v) - d(B, v), then integer id; incumbents by largest gain.
    Each spare and each victim is used at most once.
    """
    spare_list = sorted({str(s) for s in spares}, key=id_index)
    used: set[str] = set()
    out: list[Replacement] = []

    def fresh(unit: str, victim: str) -> bool:
        return int(ledger.get((unit, victim), 0) or 0) == 0

    def stall_candidates(c: Contest) -> list[tuple[int, tuple[int, str], str]]:
        found = []
        for unit in spare_list:
            if unit in used or not fresh(unit, c.victim) or not clean.get((unit, c.victim), False):
                continue
            d = distance.get((unit, c.victim))
            if d is None or not int(d) < c.d + c.k:
                continue
            found.append((int(d), id_index(unit), unit))
        return sorted(found)

    def margin_candidates(c: Contest) -> list[tuple[int, tuple[int, str], str]]:
        found = []
        for unit in spare_list:
            if unit in used or not fresh(unit, c.victim):
                continue
            if int(c.persist.get(unit, 0) or 0) < margin_persist:
                continue
            d = distance.get((unit, c.victim))
            if d is None:
                continue
            found.append((-(c.d - int(d)), id_index(unit), unit))
        return sorted(found)

    stalled = [c for c in contests if c.k >= stall_steps]
    margins = [c for c in contests if c.k < stall_steps]

    def stall_order(c: Contest) -> tuple:
        cands = stall_candidates(c)
        gain = (c.d - cands[0][0]) if cands else -(10**9)
        return (-c.k, -gain, id_index(c.victim))

    for c in sorted(stalled, key=stall_order):
        cands = stall_candidates(c)
        if not cands:
            continue
        d, _, unit = cands[0]
        used.add(unit)
        out.append(Replacement(victim=c.victim, old_unit=c.incumbent, new_unit=unit, cause="stall", distance=d))

    def margin_order(c: Contest) -> tuple:
        cands = margin_candidates(c)
        gain = -cands[0][0] if cands else -(10**9)
        return (-gain, id_index(c.victim))

    for c in sorted(margins, key=margin_order):
        cands = margin_candidates(c)
        if not cands:
            continue
        neg_gain, _, unit = cands[0]
        used.add(unit)
        out.append(
            Replacement(victim=c.victim, old_unit=c.incumbent, new_unit=unit, cause="margin", distance=c.d + neg_gain)
        )
    return out
