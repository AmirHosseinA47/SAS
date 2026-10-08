"""Dispatch round: the joint dispatcher J (outputs/dispatch_part1.txt sections 5-7; rulings section 20;
amendment A1 section 21) - as corrected by dispatch round 2 (outputs/dispatch2_part1.txt sections 2.8, 4-7;
rulings section 19).

Pure functions over plain data - no model, grid, agent or RNG access. wildfire_model builds the inputs (cells,
sets, dicts of distances, the ledger) and applies J's output through the RescueExecutor; this module only decides.

LIMIT 2 - solve_fill: free units x waiting victims, chosen exactly by the lexicographic key (round 2, 4.2)
    L1 most victims served, L1b most clean-approach pairs, L2' least total route time d*, L3' least worst d*,
    L4' fewest re-used pairs (an exact-tie tie-break), L5 smallest sorted (victim index, unit index) list, indices
    parsed as INTEGERS.
LIMIT 3 - progress_step / update_persistence / plan_replacements: the stall rule (S counted steps without the
    unit's OWN progress - progress = beating every cell it has stood on since its last progress, on the current
    board; a closed route counted apart, k_closed) and the margin rule (M steps better for P consecutive
    evaluations). Every challenger needs a clean approach; the new unit is the nearest qualifying one that the
    ledger allows, else the incumbent is kept. A REPLACE may use only a never-bound pair (ledger b = 0), a
    LATCH-FILL a pair bound at most once - the devices behind the no-reversal theorem (design 6.9).

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
    clean: bool = False


def count_configurations(n_units: int, n_victims: int) -> int:
    """Injective partial maps units -> victims: sum_k C(n_units, k) P(n_victims, k) (136 at 3 x 5)."""
    return sum(comb(n_units, k) * perm(n_victims, k) for k in range(min(n_units, n_victims) + 1))


def solve_fill(
    units: Sequence[str],
    victims: Sequence[str],
    distance: Mapping[tuple[str, str], int | None],
    ledger: Mapping[tuple[str, str], int],
    *,
    clean: Mapping[tuple[str, str], bool] | None = None,
    capped: Iterable[str] = (),
) -> list[FillPair]:
    """Limit 2's fill: the lexicographically best matching of free `units` to waiting `victims`.

    Round 2 key (outputs/dispatch2_part1.txt 4.2, rulings X-1 / X-2 / X-6):
        L1  most victims served;
        L1b most pairs with a CLEAN APPROACH (clean[(unit, victim)]; R-2 (b));
        L2' least total route time;  L3' least worst route time  (distance = d*, R-1);
        L4' fewest re-used pairs (ledger b >= 1) - an EXACT-TIE tie-break only (C1);
        L5  smallest sorted (victim index, unit index) list, indices parsed as integers.
    The ledger never enters L1-L3', so history never decides a choice between units or victims.
    distance[(unit, victim)] = the route distance d* (None or missing = no route; never allowed). Victims in
    `capped` are LATCH-FILL targets of round 1's step 2 (a pair with b >= 2 not allowed); the round-2 model never
    passes any (a latched-held victim is a contest under Limit 3, and Limit 2 alone passes none, as round 1).
    Returned in victim order.
    """
    unit_list = sorted({str(u) for u in units}, key=id_index)
    victim_list = sorted({str(v) for v in victims}, key=id_index)
    capped_set = {str(v) for v in capped}
    clean_map = clean if clean is not None else {}
    n_configs = count_configurations(len(unit_list), len(victim_list))
    if n_configs > MAX_CONFIGURATIONS:
        raise ValueError(
            f"joint dispatch: {n_configs} configurations for {len(unit_list)} units x {len(victim_list)} victims "
            f"exceed {MAX_CONFIGURATIONS} (design 5.5)"
        )

    options: dict[str, list[tuple[str, int, bool, bool]]] = {}
    for unit in unit_list:
        row: list[tuple[str, int, bool, bool]] = []
        for victim in victim_list:
            d = distance.get((unit, victim))
            if d is None:
                continue
            b = int(ledger.get((unit, victim), 0) or 0)
            if victim in capped_set and b >= 2:
                continue
            row.append((victim, int(d), b >= 1, bool(clean_map.get((unit, victim), False))))
        options[unit] = row

    best_key: tuple | None = None
    best_pairs: list[FillPair] = []

    def score(pairs: list[FillPair]) -> tuple:
        n = len(pairs)
        n_clean = sum(1 for p in pairs if p.clean)
        total = sum(p.distance for p in pairs)
        worst = max((p.distance for p in pairs), default=0)
        reused = sum(1 for p in pairs if p.reused)
        ids = sorted((id_index(p.victim), id_index(p.unit)) for p in pairs)
        return (-n, -n_clean, total, worst, reused, ids)

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
        for victim, d, reused, is_clean in options[unit]:
            if victim in used:
                continue
            chosen.append(FillPair(victim=victim, unit=unit, distance=d, reused=reused, clean=is_clean))
            walk(i + 1, used | {victim}, chosen)
            chosen.pop()

    walk(0, frozenset(), [])
    return sorted(best_pairs, key=lambda p: id_index(p.victim))


# --------------------------------------------------------------------------- LIMIT 3: progress and stall

@dataclass(frozen=True)
class Progress:
    """Per-binding progress state (outputs/dispatch2_part1.txt 2.8 R-1 and 5.2 C2), reset at every bind.

    history  H: the cells the unit has stood on at J-post evaluations since its last progress (the bind cell
             first), sorted and unique.
    k        J-posts with the unit's route OPEN and no progress (not FROZEN); 0 at progress.
    k_closed k_L: consecutive J-posts with the route CLOSED in the current closed spell (not FROZEN); reset to 0
             when the route opens.
    closed   whether the route was closed at the last evaluation.
    persist  the margin persistence counters, per spare (6.5; counted for every spare, fresh or not - C1)."""

    history: tuple[Cell, ...]
    k: int = 0
    k_closed: int = 0
    closed: bool = False
    age: int = 0
    persist: tuple[tuple[str, int], ...] = field(default_factory=tuple)

    def persist_map(self) -> dict[str, int]:
        return dict(self.persist)


def new_progress(cell: Cell) -> Progress:
    """The state of a binding at its bind: H = {the bind cell}, both counts 0 (2.8; review finding m1)."""
    return Progress(history=((int(cell[0]), int(cell[1])),))


def _finite_min(values: Iterable[int | None]) -> int | None:
    finite = [int(v) for v in values if v is not None]
    return min(finite) if finite else None


def progress_step(
    state: Progress,
    route_open: bool,
    d_now: int | None,
    c_now: int | None,
    d_hist: Sequence[int | None],
    c_hist: Sequence[int | None],
    cell_now: Cell,
    frozen: bool,
) -> Progress:
    """One J-post update (R-1, 2.8; C2, 5.2). Every distance is on the CURRENT board, to v's CURRENT cell:
    d = the fire-free route distance, c = the clean distance (None = none), each read at a unit cell with the
    unit-cell exemption; d_hist / c_hist are the same reads at the cells of state.history, in its order.

    CLOSED route (route_open False): no own progress is possible; H grows, k unchanged, k_closed + 1 unless
    FROZEN.
    OPEN route: k_closed resets to 0. PROGRESS iff the unit reached v (d = 0), or d_now beats the least finite d
    over H, or c_now (finite) beats the least finite c over H. A metric with no finite value over H is not compared
    (amendment A2, outputs/dispatch2_part2_notes.txt: an empty minimum read as infinite would let a two-cell loop
    on the clean-field boundary score progress every frame). On progress H = {cell_now}, k = 0; otherwise H grows
    and k + 1 unless FROZEN.
    """
    cell = (int(cell_now[0]), int(cell_now[1]))
    grown = tuple(sorted(set(state.history) | {cell}))
    if not route_open:
        return replace(
            state,
            history=grown,
            k_closed=state.k_closed + (0 if frozen else 1),
            closed=True,
            age=state.age + 1,
        )
    best_d = _finite_min(d_hist)
    best_c = _finite_min(c_hist)
    progressed = d_now is not None and (
        int(d_now) == 0
        or (best_d is not None and int(d_now) < best_d)
        or (c_now is not None and best_c is not None and int(c_now) < best_c)
    )
    if progressed:
        return replace(state, history=(cell,), k=0, k_closed=0, closed=False, age=state.age + 1)
    return replace(
        state,
        history=grown,
        k=state.k + (0 if frozen else 1),
        k_closed=0,
        closed=False,
        age=state.age + 1,
    )


def update_persistence(
    state: Progress,
    spare_distance: Mapping[str, int | None],
    delta_incumbent: int | None,
    margin: int,
) -> Progress:
    """The margin persistence counters of one binding (6.5, C1): spare B's count rises by one at each evaluation
    where d*(B, v) + margin <= delta(A, v), and resets otherwise - including every evaluation at which B is not a
    spare (absent from spare_distance). Counted for EVERY spare, fresh or re-used: the ledger is consulted only when
    the replacement is chosen (4.3)."""
    previous = state.persist_map()
    counts: dict[str, int] = {}
    for unit, d in spare_distance.items():
        if d is None or delta_incumbent is None:
            continue
        if int(d) + int(margin) <= int(delta_incumbent):
            counts[unit] = previous.get(unit, 0) + 1
    ordered = tuple(sorted(counts.items(), key=lambda kv: id_index(kv[0])))
    return replace(state, persist=ordered)


@dataclass(frozen=True)
class Contest:
    """A contestable binding at J-post (5.2): victim, its only binder, the binder's distance delta (d* if its route
    is open, the grid distance G if closed), whether the route is open, the two counts, the margin persistence
    counters, and whether the binder is LATCHED (labelled route_blocked; its replacement is a LATCH-FILL)."""

    victim: str
    incumbent: str
    delta: int
    route_open: bool
    k: int
    k_closed: int
    persist: Mapping[str, int]
    latched: bool = False

    @property
    def count(self) -> int:
        return self.k if self.route_open else self.k_closed


@dataclass(frozen=True)
class Replacement:
    victim: str
    old_unit: str
    new_unit: str
    cause: str  # "stall" | "margin"
    distance: int
    latched: bool = False


@dataclass(frozen=True)
class Barred:
    """A contest whose nearest qualifying spares (all at the least d*) are ledger-barred: no replacement (4.3)."""

    victim: str
    incumbent: str
    cause: str
    distance: int
    units: tuple[str, ...]


def plan_replacements_detail(
    contests: Sequence[Contest],
    spares: Sequence[str],
    distance: Mapping[tuple[str, str], int | None],
    ledger: Mapping[tuple[str, str], int],
    clean: Mapping[tuple[str, str], bool],
    *,
    stall_steps: int,
    margin_persist: int,
) -> tuple[list[Replacement], list[Barred]]:
    """Limit 3's replacements at one J-post (4.3, 5.2, 2.8 R-2 (a)).

    A contest is STALLED when its count (k if the route is open, k_closed if closed) reaches stall_steps.
    QUALIFYING spares (the ledger NOT consulted): unused in this frame, a clean approach (clean[(B, v)]), a route
    (distance[(B, v)] = d* not None), and
        STALL   d*(B, v) < delta + count;
        MARGIN  persistence count >= margin_persist (d*(B, v) + M <= delta at each of the last P evaluations).
    The new unit is the lowest-id ledger-ALLOWED spare among the qualifying spares at the least d* (D): a REPLACE
    needs b = 0, a LATCH-FILL (latched incumbent) b <= 1. If every qualifying spare at D is barred, no replacement
    for that victim in this frame (a Barred record); the spares stay available to other contests.
    Contest order: stalled first by largest count, then largest gain (delta - D, ledger-blind), then victim id;
    then margin contests by largest gain, then victim id. Each spare and each victim is used at most once.
    """
    spare_list = sorted({str(s) for s in spares}, key=id_index)
    used: set[str] = set()
    out: list[Replacement] = []
    barred: list[Barred] = []

    def allowed(unit: str, c: Contest) -> bool:
        b = int(ledger.get((unit, c.victim), 0) or 0)
        return b <= 1 if c.latched else b == 0

    def qualifying(c: Contest, stall: bool) -> list[tuple[int, str]]:
        found = []
        for unit in spare_list:
            if unit in used or not clean.get((unit, c.victim), False):
                continue
            d = distance.get((unit, c.victim))
            if d is None:
                continue
            if stall:
                if not int(d) < c.delta + c.count:
                    continue
            elif int(c.persist.get(unit, 0) or 0) < margin_persist:
                continue
            found.append((int(d), unit))
        return found

    def nearest(c: Contest, stall: bool) -> int | None:
        q = qualifying(c, stall)
        return min(d for d, _ in q) if q else None

    def decide(c: Contest, stall: bool) -> None:
        q = qualifying(c, stall)
        if not q:
            return
        least = min(d for d, _ in q)
        ties = sorted((u for d, u in q if d == least), key=id_index)
        ok = [u for u in ties if allowed(u, c)]
        cause = "stall" if stall else "margin"
        if not ok:
            barred.append(Barred(victim=c.victim, incumbent=c.incumbent, cause=cause, distance=least,
                                 units=tuple(ties)))
            return
        unit = ok[0]
        used.add(unit)
        out.append(Replacement(victim=c.victim, old_unit=c.incumbent, new_unit=unit, cause=cause, distance=least,
                               latched=c.latched))

    stalled = [c for c in contests if c.count >= stall_steps]
    margins = [c for c in contests if c.count < stall_steps]

    def stall_order(c: Contest) -> tuple:
        d = nearest(c, True)
        gain = (c.delta - d) if d is not None else -(10**9)
        return (-c.count, -gain, id_index(c.victim))

    for c in sorted(stalled, key=stall_order):
        decide(c, True)

    def margin_order(c: Contest) -> tuple:
        d = nearest(c, False)
        gain = (c.delta - d) if d is not None else -(10**9)
        return (-gain, id_index(c.victim))

    for c in sorted(margins, key=margin_order):
        decide(c, False)
    return out, barred


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
    """plan_replacements_detail without the Barred records."""
    return plan_replacements_detail(
        contests, spares, distance, ledger, clean, stall_steps=stall_steps, margin_persist=margin_persist
    )[0]


def grid_distance(a: Cell, b: Cell) -> int:
    """G (5.2): the length of a shortest 4-connected path through any cells - the grid has no impassable cell other
    than burning ones and the bounds - i.e. the Manhattan distance."""
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))
