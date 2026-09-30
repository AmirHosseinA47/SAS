"""fix3a Part 1 - the A2 PROTOTYPE (free-cell docking) as monkeypatches. NO SOURCE EDIT.

Env FX3_A2 = "1" to install (imported by outputs/_fx3_a1run.py when --a2 1 is given).

THE RULE (BASE_STATION_MODE >= 2, mechanism 2 - the shipped return):
  pick(here, depots)  the NEAREST FREE CELL of the given depot footprints: every footprint cell with no
                      OTHER UAV on it, keyed (Manhattan distance, first greedy step blocked, depot index,
                      x, y) - "first greedy step blocked" = the cell _rtb_direction would move into from
                      here holds another UAV or is off the grid (so of two equally near cells the one
                      whose approach is open wins).
  trigger             battery <= 0.3 * d + margin with d = the distance to pick(here, ALL depots) - no
                      berth; the leg LATCHES that cell (rtb_target_berth) and its depot (rtb_target_depot).
  dock                the moment the UAV stands on ANY depot footprint cell (a footprint cell is free by
                      construction: the move rule never puts two UAVs on one cell).
  re-pick             each step of the leg, within the latched depot: when the latched cell holds another
                      UAV, or when the leg has been refused BASE_STATION_RETURN_STALL_LIMIT (3) consecutive
                      steps (then the stalled cell is excluded and the stall count restarts).
  steer               _rtb_direction(latched cell) - the existing memoryless, distance-monotone greedy.
  charge              only while docked AND inside a depot footprint (the positional test the berth code
                      never had - agents.py:388 gates on rtb_docked alone).
  Everything else (release at BASE_STATION_RECHARGE_RELEASE_LEVEL, the per-trip log, mechanism 1) as today.
"""
from __future__ import annotations

import os

import agents as am

VARIANT = os.environ.get("FX3_A2") or "0"
ON = VARIANT in ("1", "2")
# VARIANT 2 (the one the design adopts, after variant 1 failed C/W: two released trackers parked on the
# doorstep walled every approach, and a Manhattan-nearest target steered by the greedy _rtb_direction
# cannot detour): NEAREST = the shortest path that avoids every other UAV's cell (BFS, 4-neighbour),
# ties (path length, Manhattan, depot index, x, y); the leg STEERS along the first step of that path to
# the latched cell; the latched cell is re-picked when another UAV takes it or no UAV-free path to it
# remains; no path to any free cell of the latched depot -> the UAV stays (a stalled step).
_MX, _MY = [1, 0, -1, 0], [0, -1, 0, 1]


def _bfs_to(uav, targets):
    """Shortest UAV-free path from uav's cell to any cell of `targets` (a set). Returns
    (cell, first_direction, path_length) with ties broken on (length, Manhattan, depot-agnostic x, y),
    or None. The target cells themselves must be free of other UAVs (the caller filters)."""
    from collections import deque
    model = uav.model
    here = (int(uav.pos[0]), int(uav.pos[1]))
    if here in targets:
        return (here, None, 0)
    occupied = set()
    for a in model.schedule.agents:
        if type(a) is am.UAV and a is not uav and a.pos is not None:
            occupied.add((int(a.pos[0]), int(a.pos[1])))
    seen = {here: None}
    first = {}
    q = deque([here])
    found = []
    level = 0
    while q and not found:
        level += 1
        for _ in range(len(q)):
            c = q.popleft()
            for d in range(4):
                n = (c[0] + _MX[d], c[1] + _MY[d])
                if n in seen or model.grid.out_of_bounds(n) or n in occupied:
                    continue
                seen[n] = c
                first[n] = d if c == here else first[c]
                if n in targets:
                    found.append(n)
                q.append(n)
    if not found:
        return None
    best = min(found, key=lambda n: (abs(n[0] - here[0]) + abs(n[1] - here[1]), n[0], n[1]))
    return (best, first[best], level)


def _depots(model):
    st = getattr(model, "base_station", None) or {}
    return st.get("depots") or ()


def _occupied_by_other(uav, cell):
    try:
        return any(type(o) is am.UAV and o is not uav for o in uav.model.grid.get_cell_list_contents([cell]))
    except Exception:
        return True


def _first_step(uav, cell):
    here = (int(uav.pos[0]), int(uav.pos[1]))
    if cell == here:
        return None
    d = uav._rtb_direction(cell, False)
    return (here[0] + _MX[d], here[1] + _MY[d])


def pick(uav, depot_indices=None, exclude=()):
    model = uav.model
    here = (int(uav.pos[0]), int(uav.pos[1]))
    best = None
    for i, dep in enumerate(_depots(model)):
        if depot_indices is not None and i not in depot_indices:
            continue
        for cell in sorted(dep["cells"]):
            if cell in exclude or (cell != here and _occupied_by_other(uav, cell)):
                continue
            dist = abs(cell[0] - here[0]) + abs(cell[1] - here[1])
            fs = _first_step(uav, cell)
            blocked = int(fs is not None and (model.grid.out_of_bounds(fs) or _occupied_by_other(uav, fs)))
            key = (dist, blocked, i, cell)
            if best is None or key < best[0]:
                best = (key, cell, i)
    return None if best is None else (best[1], best[2])


if ON:
    _oapply = am.UAV._apply_return_to_base
    _obattery = am.UAV._update_battery_after_step

    def _apply(self):
        mode = am.base_station_mode()
        if mode < 2 or self.rtb_berth is None or self.pos is None or not _depots(self.model):
            return _oapply(self)
        step = int(getattr(self.model, "evaluation_timesteps_counter", 0))
        if self.rtb_docked:
            return _oapply(self)                       # the release branch, unchanged
        here = (int(self.pos[0]), int(self.pos[1]))
        if not self.rtb_active:
            p = pick(self)
            if p is None:
                return
            cell, dep = p
            if self.battery_level > self._rtb_trigger_level(cell):
                return
            self.rtb_active = True
            self.rtb_trips += 1
            self.rtb_stall_steps = 0
            self.rtb_recovery_cell = None
            self.rtb_recovery_steered = None
            self.rtb_target_berth = cell
            self.rtb_target_depot = dep
            self.fx3_repicks = 0
            self.rtb_log.append({
                "trigger_step": step, "trigger_level": float(self.battery_level),
                "trigger_distance": abs(here[0] - cell[0]) + abs(here[1] - cell[1]),
                "target_depot": int(dep), "target_berth": [int(cell[0]), int(cell[1])],
                "home_depot": int(self.rtb_home_depot), "arrival_step": None, "arrival_level": None,
                "dock_cell": None, "released_step": None, "released_level": None, "repicks": 0})
        # stall witness (maintained here, independent of BASE_STATION_DOCK_FIX)
        if self.rtb_last_pos is not None and self.rtb_last_pos == here:
            self.rtb_stall_steps += 1
        else:
            self.rtb_stall_steps = 0
        if self.model.base_station_contains(here):
            self.rtb_docked = True
            self.rtb_stall_steps = 0
            self.execution_action = "rtb_docked"
            if self.rtb_log:
                self.rtb_log[-1]["arrival_step"] = step
                self.rtb_log[-1]["arrival_level"] = float(self.battery_level)
                self.rtb_log[-1]["dock_cell"] = here
            return
        self.rtb_return_steps += 1
        if am.base_station_return_mechanism() != 2:
            return
        if VARIANT == "2":
            dep = int(self.rtb_target_depot or 0)
            free = {c for c in _depots(self.model)[dep]["cells"] if not _occupied_by_other(self, c)}
            target = self.rtb_target_berth
            route = _bfs_to(self, {target}) if target in free else None
            if route is None:
                route = _bfs_to(self, free)
                if route is not None:
                    self.rtb_target_berth = route[0]
                    if self.rtb_log:
                        self.rtb_log[-1]["repicks"] = int(self.rtb_log[-1].get("repicks", 0)) + 1
            self.rtb_last_pos = here
            self.execution_action = "rtb_return"
            self.execution_stay = False
            if route is None or route[1] is None:
                # boxed in (no UAV-free path to any free cell of the depot): no move this step - the
                # model's no-direction hold (move() refuses nothing, the monitor records no drift)
                self.execution_direction_applied = False
                self.fx3_boxed_steps = getattr(self, "fx3_boxed_steps", 0) + 1
                return
            self.execution_direction_applied = True
            self.selected_dir = route[1]
            return
        target = self.rtb_target_berth
        stalled_out = self.rtb_stall_steps >= am.base_station_return_stall_limit()
        if target is None or _occupied_by_other(self, target) or stalled_out:
            p = pick(self, depot_indices={int(self.rtb_target_depot or 0)},
                     exclude=({target} if (stalled_out and target is not None) else ()))
            if p is not None:
                self.rtb_target_berth = p[0]
                if self.rtb_log:
                    self.rtb_log[-1]["repicks"] = int(self.rtb_log[-1].get("repicks", 0)) + 1
            if stalled_out:
                self.rtb_stall_steps = 0
        target = self.rtb_target_berth
        direction = self._rtb_direction(target)
        self.rtb_last_pos = here
        self.selected_dir = direction
        self.execution_direction_applied = True
        self.execution_action = "rtb_return"
        self.execution_stay = False

    am.UAV._apply_return_to_base = _apply

    def _battery(self, moved):
        # the positional test: a UAV charges only while docked AND inside a depot footprint
        docked = self.rtb_docked
        inside = bool(self.pos is not None and self.model.base_station_contains(self.pos))
        if docked and not inside:
            self.rtb_docked = False                  # never true under this rule; counted if it were
            self.fx3_outside_charge_refused = getattr(self, "fx3_outside_charge_refused", 0) + 1
            try:
                _obattery(self, moved)
            finally:
                self.rtb_docked = docked
            return
        _obattery(self, moved)

    am.UAV._update_battery_after_step = _battery
