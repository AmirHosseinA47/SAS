"""fix3a Part 1 - the A1 PROTOTYPE (depot-pocket searcher routing) as monkeypatches. NO SOURCE EDIT.

Two uses:
  pytest:   set PYTHONPATH=outputs  ->  pytest -p _fx3_proto_a1 <test files>
  full run: outputs/_fx3_a1run.py --a1 R+S+D -- <_fx3_probe.py args>
Env FX3_A1 = "+"-joined subset of R, S, D (default "R+S+D"; "none" = no patch).

R  THE NEAR FIELD OF A FIRE, PLANNED WITHIN (the pathfinding route, _attempt_pathfinding_toward_target,
   at the shipped 3b setting only - range >= 99 and SEARCHER_GATE_NEAR_FIELD on):
     - the near field is measured to BURNING cells only; smoke stays impassable (no step into a
       smoke cell - unchanged) but no longer vetoes a step at range;
     - within the near field (a burning cell within SEARCHER_GATE_NEAR_RANGE = 6 of the searcher,
       distance d0) the route is PLANNED under the veto's own constraint: every candidate cell must
       keep its distance to the nearest burning cell >= d0 (greedy and BFS alike), so the veto can
       never reject the plan;
     - no admissible step toward the target: step to a legal neighbour that strictly INCREASES the
       burning distance (the largest), else WAIT on the cell (a stay, like the fail-safe hold);
       labels ..._retarget_to_interior_fire_retreat / ..._fire_wait (both exempt from the gate, as
       every routed step already is).
     Outside the near field the route is the original planner with no veto (nothing to veto: the
     original veto needs a strict hazard within 6; with smoke only it now does not fire).
S  THE SWEEP STAYS OUT OF THE EDGE BAND: a victim searcher's sector bounds (used by the lawnmower
   sweep, its at-target test and its end-of-lane test) shrink to edge distance >= 4 (the edge filter's
   margin 3 + 1), and the sweep state is clamped into them - a sweep target the edge filter can never
   let the searcher reach is never issued.
D  THE CORNER: (1) the edge filter counts penetration of the band per axis,
     p(c) = max(0, 4 - dx_edge) + max(0, 4 - dy_edge); inside the band a move is legal iff it strictly
     reduces p (min-over-axes made every move from a corner cell such as (46,3) illegal); outside the
     band (p = 0) nothing changes; (2) the BFS / greedy escape treat another UAV's cell as blocked.
"""
from __future__ import annotations

import os

import src_extension.execution.uav_executor as ux

MODE = set((os.environ.get("FX3_A1") or "R+S+D").split("+")) - {"none", ""}
UX = ux.UAVExecutor
_MX, _MY = [1, 0, -1, 0], [0, -1, 0, 1]
BAND = 4          # edge distance a searcher may not enter laterally (the filter's margin 3, + 1)


def _grid_max(ex, agent):
    model = ex._resolve_model(agent)
    xm = int(getattr(model, "HEIGHT", getattr(model, "height", 50)) or 50) - 1
    ym = int(getattr(model, "WIDTH", getattr(model, "width", 50)) or 50) - 1
    return xm, ym


def _uav_cells(ex, agent):
    model = ex._resolve_model(agent)
    out = set()
    for a in getattr(getattr(model, "schedule", None), "agents", ()) or ():
        if type(a).__name__ == "UAV" and a is not agent and getattr(a, "pos", None) is not None:
            out.add((int(a.pos[0]), int(a.pos[1])))
    return out


# ------------------------------------------------------------------------------------------- D
if "D" in MODE:
    def _edge_blocked(self, agent, direction):
        model = self._resolve_model(agent)
        pos = getattr(agent, "pos", None)
        if model is None or pos is None:
            return False
        xm, ym = _grid_max(self, agent)
        x, y = int(pos[0]), int(pos[1])
        nx, ny = x + _MX[direction], y + _MY[direction]

        def p(cx, cy):
            return max(0, BAND - min(cx, xm - cx)) + max(0, BAND - min(cy, ym - cy))
        pb = p(x, y)
        if pb == 0:
            return False            # outside the band: the original filter never blocks here either
        return p(nx, ny) >= pb      # inside: only a move that strictly reduces the penetration

    UX._victim_edge_blocked_direction = _edge_blocked

    _opocket = UX._pocket_blocked_cells_for_escape

    def _pocket_blocked(self, agent, start):
        cells = set(_opocket(self, agent, start))
        cells |= _uav_cells(self, agent) - {tuple(start)}
        return cells

    UX._pocket_blocked_cells_for_escape = _pocket_blocked


# ------------------------------------------------------------------------------------------- S
if "S" in MODE:
    _obounds = UX._uav_sector_bounds

    def _bounds(self, model=None):
        b = _obounds(self, model)
        if b is None or not self._role_is_victim_searcher(self._read_uav_role()):
            return b
        resolved = model or self._model
        xm = int(getattr(resolved, "HEIGHT", 50) or 50) - 1
        ym = int(getattr(resolved, "WIDTH", 50) or 50) - 1
        return {"x_min": max(int(b["x_min"]), BAND), "x_max": min(int(b["x_max"]), xm - BAND),
                "y_min": max(int(b["y_min"]), BAND), "y_max": min(int(b["y_max"]), ym - BAND)}

    UX._uav_sector_bounds = _bounds

    _oinit = UX._init_wind_aware_sweep_state

    def _clamp_state(state, height, width):
        state["sweep_x"] = max(BAND, min(height - 1 - BAND, int(state["sweep_x"])))
        state["sweep_y"] = max(BAND, min(width - 1 - BAND, int(state["sweep_y"])))
        return state

    def _init(self, model, pos, bounds, height, width, wind_direction):
        return _clamp_state(_oinit(self, model, pos, bounds, height, width, wind_direction), height, width)

    UX._init_wind_aware_sweep_state = _init

    _osafe = UX._safe_victim_sweep_target

    def _safe(self, agent, state, model, sector_bounds, height, width, step, pos):
        _clamp_state(state, height, width)
        tx, ty = _osafe(self, agent, state, model, sector_bounds, height, width, step, pos)
        _clamp_state(state, height, width)
        return (float(max(BAND, min(height - 1 - BAND, int(tx)))), float(max(BAND, min(width - 1 - BAND, int(ty)))))

    UX._safe_victim_sweep_target = _safe


# ------------------------------------------------------------------------------------------- R
if "R" in MODE:
    _oroute = UX._attempt_pathfinding_toward_target
    _ocommit = UX._commit_execution_direction
    WAIT = "victim_search_wind_aware_retarget_to_interior_fire_wait"
    RETREAT = "victim_search_wind_aware_retarget_to_interior_fire_retreat"

    def _bfs(self, agent, start, goal, blocked, max_depth):
        from collections import deque
        if abs(start[0] - goal[0]) + abs(start[1] - goal[1]) <= 2:
            return None
        q = deque([start])
        seen = {start: None}
        pdir = {}
        depth = 0
        while q:
            if depth > max_depth:
                break
            for _ in range(len(q)):
                c = q.popleft()
                for d in range(4):
                    n = (c[0] + _MX[d], c[1] + _MY[d])
                    if n in seen or not self._cell_in_bounds(n) or n in blocked:
                        continue
                    seen[n] = c
                    pdir[n] = d
                    if abs(n[0] - goal[0]) + abs(n[1] - goal[1]) <= 2:
                        cur = n
                        while seen[cur] is not None and seen[cur] != start:
                            cur = seen[cur]
                        return pdir[cur]
                    q.append(n)
            depth += 1
        return None

    def _route(self, agent, target, *, action_label, prefer_bfs_action_label=False):
        if not (self._hazard_retreat_range() >= 99 and self._gate_near_field()):
            return _oroute(self, agent, target, action_label=action_label,
                           prefer_bfs_action_label=prefer_bfs_action_label)
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        model = self._resolve_model(agent)
        fire = self._collect_strict_active_fire_cells(model)
        near = int(self._gate_near_range())
        here = (int(pos[0]), int(pos[1]))
        xm, ym = _grid_max(self, agent)
        # exact Manhattan distance to the nearest burning cell for every cell: a multi-source BFS on
        # the obstacle-free 4-neighbour grid (one pass, instead of a min over every fire cell per cell)
        from collections import deque
        dist = {}
        dq = deque()
        for c in fire:
            dist[c] = 0
            dq.append(c)
        while dq:
            c = dq.popleft()
            for d in range(4):
                n = (c[0] + _MX[d], c[1] + _MY[d])
                if 0 <= n[0] <= xm and 0 <= n[1] <= ym and n not in dist:
                    dist[n] = dist[c] + 1
                    dq.append(n)

        def df(c):
            return dist.get((int(c[0]), int(c[1])), 99)
        d0 = df(here)
        # the CLEARANCE the route keeps from a burning cell: K = FX3_K (default the near range, 6 -
        # exactly the veto's "never closer while within 6"); admissible cells keep >= T = min(d0, K)
        K = int(os.environ.get("FX3_K") or near)
        if d0 > near:
            # no burning cell within the near range: the original planner, and nothing to veto
            forced = self._forced_progress_direction(agent, target)
            if forced is None:
                return None
            nxt = self._next_cell_for_direction(agent, forced)
            if nxt is None or self._strict_victim_hazard_level(nxt) != 0:
                return None
            method = str(getattr(self, "_last_escape_method", "") or "")
            if prefer_bfs_action_label and method.startswith("bfs"):
                return forced, "victim_search_escape_bfs"
            return forced, action_label
        # inside the near field: plan under the veto's own constraint (burning distance >= d0)
        self._last_escape_method = None
        goal = (int(round(float(target[0]))), int(round(float(target[1]))))
        pocket = self._pocket_blocked_cells_for_escape(agent, here)
        cur = abs(goal[0] - here[0]) + abs(goal[1] - here[1])
        best, best_prog = None, 0
        for d in range(4):
            n = (here[0] + _MX[d], here[1] + _MY[d])
            if not self._cell_in_bounds(n) or self._strict_victim_hazard_level(n) > 0:
                continue
            if not self._strict_path_lookahead_safe(agent, d, depth=1) or df(n) < min(d0, K) or n in pocket:
                continue
            prog = cur - (abs(goal[0] - n[0]) + abs(goal[1] - n[1]))
            if prog > best_prog:
                best, best_prog = d, prog
        method = "greedy"
        if best is None:
            smoke = self._collect_strict_smoke_cells(model)
            inadm = {c for c, v in dist.items() if v < min(d0, K)}
            md = self._bfs_escape_max_depth(agent)
            best = _bfs(self, agent, here, goal, set(fire) | set(smoke) | pocket | inadm, md)
            method = "bfs_smoke_safe"
            if best is None:
                best = _bfs(self, agent, here, goal, set(fire) | pocket | inadm, md)
                method = "bfs_fire_only"
        if best is not None:
            nxt = (here[0] + _MX[best], here[1] + _MY[best])
            if self._strict_victim_hazard_level(nxt) == 0:
                self._last_escape_method = method
                if prefer_bfs_action_label and method.startswith("bfs"):
                    return best, "victim_search_escape_bfs"
                return best, action_label
        # no admissible step toward the target: strictly away from the fire, else wait
        occupied = _uav_cells(self, agent)
        away, away_d = None, d0
        for d in range(4):
            n = (here[0] + _MX[d], here[1] + _MY[d])
            if not self._cell_in_bounds(n) or self._strict_victim_hazard_level(n) > 0 or n in occupied:
                continue
            if self._victim_edge_blocked_direction(agent, d):
                continue
            if df(n) > away_d:
                away, away_d = d, df(n)
        if away is not None:
            self._last_escape_method = "fire_retreat"
            return away, RETREAT
        self._last_escape_method = "fire_wait"
        return int(getattr(agent, "selected_dir", 0) or 0), WAIT

    UX._attempt_pathfinding_toward_target = _route

    def _commit(self, agent, chosen_dir, action):
        _ocommit(self, agent, chosen_dir, action)
        import agents as agents_module
        if str(action or "") == WAIT and agents_module.uav_hold_stationary():
            agent.execution_stay = True

    UX._commit_execution_direction = _commit
