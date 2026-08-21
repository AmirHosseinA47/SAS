"""Managing system: apply path decisions to a managed UAV.

Managing → managed: applies PathDecision by setting selected_dir only
movement occurs in the simulator step, not here.
"""

from __future__ import annotations

from typing import Any

from common_fixed_variables import (
    LAUNCH_GRACE_STEPS,
    normalize_wind_direction,
    wind_vector_from_direction,
)
from ..adaptation.local_adaptation_generator import (
    LocalAdaptationSpaceGenerator,
    NO_VICTIM_DETECT_BOOST_AFTER,
    WIND_MAX_WIND_AWARE_HOLDS,
    WIND_PATH_LOOKAHEAD_DEPTH,
    WIND_POCKET_CAMP_THRESHOLD,
    WIND_SWEEP_NO_MOVE_ESCAPE,
    _blacklist_target_neighborhood,
    _is_saturated_cell,
    _step_index_from_runtime,
    _sync_wind_search_streaks,
    _wind_search_state,
)
from ..dashboard.movement_explainability import (
    movement_transition_key,
    notable_uav_movement_category,
)
from ..planning.decision_objects import FailSafeDecision, PathDecision
from .execution_log import ExecutionLog, ExecutionResult

_CARDINAL_TO_DIR: dict[str, int] = {
    "east": 0,
    "south": 1,
    "west": 2,
    "north": 3,
}
_DIR_TO_CARDINAL = ("east", "south", "west", "north")
_CARDINAL_WORDS = frozenset(_CARDINAL_TO_DIR.keys())

_MOVE_X = [1, 0, -1, 0]
_MOVE_Y = [0, -1, 0, 1]
BFS_ESCAPE_MAX_DEPTH = 100
_VICTIM_HAZARD_BUFFER = 2

_FIRE_ROLES = frozenset({"fire_tracker", "fire_search", "fire_mapper", "scout"})
_VICTIM_ROLES = frozenset({"victim_searcher", "victim_search"})
_HOLD_PATH_MARKERS = ("keep_current_path", "hold_current_path", "maintain_current_path")
STANDOFF_MIN = 1
STANDOFF_MAX = 3
STANDOFF_IDEAL = (STANDOFF_MIN + STANDOFF_MAX) / 2.0
STANDOFF_IN_BAND_BONUS = 100.0
STANDOFF_TOO_FAR_PENALTY = 15.0
STANDOFF_TOO_CLOSE_PENALTY = 50.0
STANDOFF_APPROACH_REWARD = 10.0
STANDOFF_RETREAT_PENALTY = 8.0
STANDOFF_SMOKE_CLEARANCE = 2
STANDOFF_MAX_ESCAPE = 10
STANDOFF_ENVELOPE_EXPAND_FIRE = 25
STANDOFF_ENVELOPE_EXPAND_SMOKE = 10
_FIRE_TRACKER_HARD_HAZARD_SCORE = -10000.0
_SMOKE_HAZARD_TOKENS = frozenset(
    {
        "smoke",
        "smoky",
        "smoke_obscured",
        "smoke_observed",
        "obscured",
        "low_visibility",
        "reduced_visibility",
    }
)

_TRACKER_HAZARD_CACHE_ATTR = "_uav_executor_tracker_hazard_cache"


def _empty_tracker_hazard_cache() -> dict[str, Any]:
    return {
        "step": -1,
        "hazard_cells": set(),
        "burning_cells": set(),
        "active_smoke_cells": set(),
        "smoke_obscured_cells": set(),
    }


def _is_planner_intentional_hold(decision: PathDecision | None) -> bool:
    if decision is None:
        return False
    selected_id = str(getattr(decision, "selected_option_id", "") or "").lower()
    return any(marker in selected_id for marker in _HOLD_PATH_MARKERS)


def _is_fail_safe_hold_decision(
    decision: PathDecision | None,
    fail_safe_decision: FailSafeDecision | None,
) -> bool:
    if fail_safe_decision is not None:
        fs_action = str(
            getattr(fail_safe_decision, "fail_safe_action", "") or ""
        ).lower()
        fs_mode = str(getattr(fail_safe_decision, "mission_mode", "") or "").lower()
        if fs_action in {"hold", "safe_hold", "hold_position"} or fs_mode in {
            "emergency",
            "safety_first",
        }:
            return True
    if decision is None:
        return False
    action = str(getattr(decision, "next_action", "") or "").lower()
    if action != "hold":
        return False
    if _is_planner_intentional_hold(decision):
        return False
    selected_id = str(getattr(decision, "selected_option_id", "") or "")
    if not selected_id:
        return True
    return False


class UAVExecutor:
    """Managing-side applier: path decisions → managed UAV direction intent."""

    def __init__(
        self,
        uav_id: str,
        model: Any | None = None,
        agent: Any | None = None,
        execution_log: ExecutionLog | None = None,
    ) -> None:
        self.uav_id = uav_id
        self._model = model
        self._agent = agent
        self._execution_log = execution_log

    def _commit_execution_direction(
        self, agent: Any, chosen_dir: int, action: str,
    ) -> None:
        agent.selected_dir = int(chosen_dir)
        agent.execution_direction_applied = True
        agent.execution_action = str(action or "set_direction")
        self._record_uav_movement_reason(agent, str(action or "set_direction"))

    def _movement_category_for_action(self, role: str, action: str) -> str:
        role_norm = str(role or "").strip().lower()
        action_l = str(action or "").strip().lower()
        if role_norm == "fire_tracker":
            if "hold_escape" in action_l:
                return "tracker_escape"
            if "fire_smoke_escape" in action_l:
                return "tracker_smoke_escape"
            if "fire_flank_relocate" in action_l:
                return "tracker_flank_relocate"
            if "fire_flank_hold" in action_l:
                return "tracker_flank_hold"
            if "standoff" in action_l:
                return "tracker_standoff"
            if action_l == "hold":
                return "tracker_hold"
            return "tracker_move"
        if role_norm in {"victim_searcher", "victim_search"}:
            if "hazard" in action_l or "escape" in action_l:
                return "searcher_hazard_retreat"
            if "wind_aware" in action_l or action_l == "search":
                return "searcher_coverage"
            if action_l == "hold":
                return "searcher_hold"
            return "searcher_move"
        return "uav_move"

    def _record_uav_movement_reason(self, agent: Any, action: str) -> None:
        role = str(self._read_uav_role() or "").strip().lower()
        category = self._movement_category_for_action(role, action)
        model = self._resolve_model(agent)
        pos = getattr(agent, "pos", None)
        factors: dict[str, object] = {"action": action, "role": role}
        reason = f"{role or 'uav'} movement: {action}"

        if role == "fire_tracker" and pos is not None:
            ax, ay = int(pos[0]), int(pos[1])
            fire_cells = self._collect_active_fire_cells(model)
            nearest = None
            if fire_cells:
                nearest = min(abs(ax - fx) + abs(ay - fy) for fx, fy in fire_cells)
            bounds = self._fire_tracker_flank_bounds(model)
            side_label = "full"
            if bounds is not None:
                axis = str(bounds.get("split_axis", "none"))
                flank_idx = int(bounds.get("flank_index", 0) or 0)
                flank_count = int(bounds.get("flank_count", 1) or 1)
                half = "low" if flank_idx < max(1, flank_count) // 2 else "high"
                side_label = f"{half}/{axis}" if axis in {"x", "y"} else "full"
            smoke_free = not self._cell_in_smoke_envelope((ax, ay), clearance=1)
            eff_min = self._effective_standoff_min(model)
            factors.update(
                {
                    "nearest_fire_dist": nearest,
                    "standoff_min": eff_min,
                    "flank_side": side_label,
                    "smoke_free": smoke_free,
                }
            )
            if category == "tracker_escape":
                reason = (
                    f"escaping: fire reached standoff cell "
                    f"(nearest-fire dist {nearest}, smoke-free={smoke_free})"
                )
            elif category == "tracker_flank_relocate":
                reason = (
                    f"relocating to assigned flank {side_label} "
                    f"(nearest-fire dist {nearest})"
                )
            elif category in {"tracker_flank_hold", "tracker_hold"}:
                reason = (
                    f"holding flank standoff (side={side_label}, "
                    f"nearest-fire dist {nearest}, smoke-free={smoke_free})"
                )
            elif category == "tracker_smoke_escape":
                reason = (
                    f"escaping smoke/fire hazard "
                    f"(nearest-fire dist {nearest}, smoke-free={smoke_free})"
                )
            else:
                reason = (
                    f"fire_tracker standoff move (side={side_label}, "
                    f"nearest-fire dist {nearest}, smoke-free={smoke_free})"
                )
        elif role in {"victim_searcher", "victim_search"}:
            target = None
            ws: dict[str, object] = {}
            if model is not None:
                ws = _wind_search_state(model, self.uav_id)
                ct = ws.get("current_target")
                if isinstance(ct, (list, tuple)) and len(ct) >= 2:
                    target = (float(ct[0]), float(ct[1]))
            if target is None:
                expl = getattr(agent, "last_explanation", None)
                if isinstance(expl, dict):
                    raw = expl.get("target")
                    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                        target = (float(raw[0]), float(raw[1]))
            factors["coverage_target"] = target
            factors["force_coverage_escape"] = bool(ws.get("force_coverage_escape"))
            factors["force_interior_retarget"] = bool(ws.get("force_interior_retarget"))
            if category == "searcher_hazard_retreat":
                reason = "hazard retreat: smoke/fire ahead"
            elif category == "searcher_coverage":
                if target is not None:
                    reason = (
                        f"searching region toward ({target[0]:.0f},{target[1]:.0f}): "
                        "highest uncovered-uncertainty"
                    )
                else:
                    reason = "searching region: highest uncovered-uncertainty"
            elif bool(ws.get("force_coverage_escape")):
                reason = "escaping narrow band (coverage diversity)"
                category = "searcher_coverage_escape"
            else:
                reason = f"victim_searcher move toward coverage target {target}"

        fine_cat = str(category)
        notable_cat = notable_uav_movement_category(role, fine_cat)
        prev_notable = str(getattr(agent, "_movement_last_notable_category", "") or "")
        transition_key = movement_transition_key("uav", notable_cat, factors)
        movement_reason = {
            "category": notable_cat,
            "fine_category": fine_cat,
            "prev_category": prev_notable,
            "reason": reason,
            "key_factors": factors,
        }
        try:
            agent.movement_reason = dict(movement_reason)
            if model is not None:
                pending = getattr(model, "_movement_step_pending", None)
                if not isinstance(pending, dict):
                    pending = {}
                    model._movement_step_pending = pending
                step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
                pending[str(getattr(agent, "unique_id", ""))] = {
                    "step": step,
                    "agent_kind": "uav",
                    "source_module": "uav_move",
                    "target_id": str(getattr(agent, "unique_id", "")),
                    "category": notable_cat,
                    "fine_category": fine_cat,
                    "prev_notable_category": prev_notable,
                    "prev_transition_key": str(
                        getattr(agent, "_movement_last_transition_key", "") or ""
                    ),
                    "transition_key": transition_key,
                    "reason": reason,
                    "key_factors": dict(factors),
                }
            existing = getattr(agent, "last_explanation", None)
            merged = dict(existing) if isinstance(existing, dict) else {}
            merged.update(
                {
                    "movement_category": notable_cat,
                    "movement_fine_category": fine_cat,
                    "movement_reason": reason,
                    "movement_factors": factors,
                }
            )
            agent.last_explanation = merged
        except Exception:
            pass

    def execute(
        self,
        decision: PathDecision | None,
        timestamp: float = 0.0,
        fail_safe_decision: FailSafeDecision | None = None,
    ) -> dict[str, object]:
        agent = self._resolve_agent()
        if agent is None:
            return {"applied": False, "reason": "agent_not_found", "uav_id": self.uav_id}

        if fail_safe_decision is not None and fail_safe_decision.search_mode_active:
            role_kind = self._role_kind(self._read_uav_role())
            if role_kind in {"victim", "fire"}:
                return self._execute_role_preserving_search(
                    agent,
                    decision,
                    fail_safe_decision,
                    timestamp,
                    role_kind,
                )
            return self._execute_search_mode(
                agent, fail_safe_decision, timestamp, decision
            )

        if decision is None:
            return {"applied": False, "reason": "no_decision"}

        role = self._read_uav_role()
        role_kind = self._role_kind(role)
        action = decision.next_action.strip().lower() if decision.next_action else ""
        chosen_dir = int(getattr(agent, "selected_dir", 0))

        if action == "hold":
            ctx = getattr(decision, "uncertainty_context", None)
            selected_id = str(getattr(decision, "selected_option_id", "") or "")
            model = self._resolve_model(agent)
            if self._role_is_victim_searcher(role) and not _is_fail_safe_hold_decision(
                decision, fail_safe_decision
            ):
                if model is not None:
                    ws = _wind_search_state(model, self.uav_id)
                    if self._victim_near_edge_escape_required(agent, model):
                        ws["force_interior_retarget"] = True
                        if int(ws.get("pocket_streak", 0) or 0) >= WIND_POCKET_CAMP_THRESHOLD // 2:
                            ws["force_coverage_escape"] = True
                chosen_dir, action = self._resolve_direction_intent(
                    agent,
                    decision,
                    role_kind,
                    "victim_search_wind_aware",
                )
            else:
                wind_state = _wind_search_state(model, self.uav_id) if model is not None else {}
                wind_aware_hold = int(wind_state.get("wind_aware_hold_streak", 0) or 0)
                hold_streak = int(wind_state.get("hold_streak", 0) or 0)
                near_boundary = self._position_at_boundary(agent) or self._distance_from_boundary(
                    int(agent.pos[0]),
                    int(agent.pos[1]),
                    model,
                ) < 2.0
                wind_aware = selected_id == "wind_aware_victim_search"
                if (
                    role_kind == "victim"
                    and wind_aware
                    and isinstance(ctx, dict)
                    and (
                        ctx.get("needs_new_wind_target")
                        or ctx.get("wind_target_reached")
                        or ctx.get("force_wind_retarget")
                        or ctx.get("force_wind_sweep")
                        or wind_aware_hold >= WIND_MAX_WIND_AWARE_HOLDS
                        or hold_streak >= WIND_MAX_WIND_AWARE_HOLDS
                        or near_boundary
                        or bool(wind_state.get("force_interior_retarget"))
                        or bool(wind_state.get("force_sweep"))
                    )
                ):
                    chosen_dir, action = self._resolve_direction_intent(
                        agent,
                        decision,
                        role_kind,
                        "victim_search_wind_aware",
                    )
                else:
                    chosen_dir, action = self._execute_hold(agent, chosen_dir)
        else:
            chosen_dir, action = self._resolve_direction_intent(
                agent, decision, role_kind, action
            )

        if self._role_is_victim_searcher(role) and action != "hold":
            pathfinding_routed = (
                "retarget_to_interior" in str(action or "")
                and str(getattr(self, "_last_escape_method", "") or "") != ""
            )
            if action != "victim_search_escape_bfs" and not pathfinding_routed:
                chosen_dir, action = self._apply_victim_searcher_hazard_gate(
                    agent, chosen_dir, action,
                )
        elif action != "hold" and not (
            str(action).startswith("hold_escape")
            and str(self._read_uav_role() or "").strip().lower() == "fire_tracker"
        ):
            chosen_dir, action = self._apply_final_direction_safety(
                agent, chosen_dir, action
            )
        self._sync_wind_search_execution_state(agent, decision, action)
        self._commit_execution_direction(agent, chosen_dir, action)

        if self._execution_log is not None:
            self._execution_log.add(
                ExecutionResult(
                    decision_id=decision.decision_id,
                    executor_type="uav",
                    target_entity=self.uav_id,
                    action=action if action == "hold" else action or "set_direction",
                    status="success",
                    timestamp=timestamp,
                    intended_effect=decision.next_action or decision.explanation,
                    actual_result=f"selected_dir={chosen_dir}",
                    feedback_event={
                        "selected_dir": chosen_dir,
                        "action": action,
                        "role": role or "",
                    },
                    confidence_before=decision.confidence_score,
                    confidence_after=decision.confidence_score,
                    explanation=decision.explanation,
                )
            )

        return {
            "applied": True,
            "uav_id": self.uav_id,
            "decision_id": decision.decision_id,
            "selected_dir": chosen_dir,
            "action": action if action else "set_direction",
        }

    def _execute_role_preserving_search(
        self,
        agent: Any,
        decision: PathDecision | None,
        fail_safe_decision: FailSafeDecision,
        timestamp: float,
        role_kind: str,
    ) -> dict[str, object]:
        path_decision = decision
        if path_decision is None:
            path_decision = PathDecision(
                decision_id=fail_safe_decision.decision_id,
                uav_id=self.uav_id,
                next_action=(
                    "explore_unknown_region"
                    if role_kind == "fire"
                    else "search"
                ),
                explanation=fail_safe_decision.explanation,
            )
        action = (
            path_decision.next_action.strip().lower()
            if path_decision.next_action
            else ""
        )
        if not action:
            action = "explore_unknown_region" if role_kind == "fire" else "search"
        chosen_dir, action_label = self._resolve_direction_intent(
            agent,
            path_decision,
            role_kind,
            action,
        )
        chosen_dir, action_label = self._apply_final_direction_safety(
            agent, chosen_dir, action_label
        )
        self._commit_execution_direction(agent, chosen_dir, action_label)
        role = self._read_uav_role()

        if self._execution_log is not None:
            self._execution_log.add(
                ExecutionResult(
                    decision_id=path_decision.decision_id,
                    executor_type="uav",
                    target_entity=self.uav_id,
                    action=action_label,
                    status="success",
                    timestamp=timestamp,
                    intended_effect=path_decision.next_action or action_label,
                    actual_result=f"selected_dir={chosen_dir}",
                    feedback_event={
                        "selected_dir": chosen_dir,
                        "action": action_label,
                        "role": role or "",
                        "role_preserving_search": True,
                    },
                    confidence_before=path_decision.confidence_score,
                    confidence_after=path_decision.confidence_score,
                    explanation=path_decision.explanation,
                )
            )

        return {
            "applied": True,
            "uav_id": self.uav_id,
            "decision_id": path_decision.decision_id,
            "selected_dir": chosen_dir,
            "action": action_label,
            "role_preserving_search": True,
        }

    def _execute_hold(self, agent: Any, current_dir: int) -> tuple[int, str]:
        if not self._hold_needs_escape(agent, current_dir):
            return current_dir, "hold"
        escape_dir = self._hold_escape_direction(agent)
        if escape_dir is None:
            return current_dir, "hold"
        return escape_dir, "hold_escape"

    def _uav_stuck_count(self, agent: Any) -> int:
        model = self._resolve_model(agent)
        if model is None:
            return 0
        stuck_counts = getattr(model, "_uav_stuck_counts", None)
        if not isinstance(stuck_counts, dict):
            return 0
        return int(stuck_counts.get(str(self.uav_id), 0) or 0)

    def _position_at_boundary(self, agent: Any) -> bool:
        pos = getattr(agent, "pos", None)
        model = self._resolve_model(agent)
        if pos is None or model is None:
            return False
        x, y = int(pos[0]), int(pos[1])
        x_max = self._grid_dimension(model, ("grid_height", "HEIGHT", "height"))
        y_max = self._grid_dimension(model, ("grid_width", "WIDTH", "width"))
        if x_max is None or y_max is None:
            return False
        return x <= 0 or y <= 0 or x >= x_max - 1 or y >= y_max - 1

    def _distance_from_boundary(
        self,
        x: int,
        y: int,
        model: Any | None,
    ) -> float:
        if model is None:
            return 0.0
        x_max = self._grid_dimension(model, ("grid_height", "HEIGHT", "height"))
        y_max = self._grid_dimension(model, ("grid_width", "WIDTH", "width"))
        if x_max is None or y_max is None:
            return 0.0
        return float(min(x, y, x_max - 1 - x, y_max - 1 - y))

    def _hold_needs_escape(self, agent: Any, current_dir: int) -> bool:
        if self._uav_stuck_count(agent) >= 3:
            return True
        if self._position_at_boundary(agent):
            return True
        if self._can_check_bounds(agent) and not self._direction_in_bounds(
            agent, current_dir
        ):
            return True
        if str(self._read_uav_role() or "").strip().lower() == "fire_tracker":
            return self._fire_tracker_hold_needs_escape(agent)
        return False

    def _fire_tracker_hold_needs_escape(self, agent: Any) -> bool:
        pos = getattr(agent, "pos", None)
        if pos is None:
            return False
        model = self._resolve_model(agent)
        cell = (int(pos[0]), int(pos[1]))
        cache = self._get_tracker_hazard_cache(model)
        if cell in cache["burning_cells"]:
            return True
        if cell in cache["active_smoke_cells"] or cell in cache["smoke_obscured_cells"]:
            return True
        burning = cache["burning_cells"]
        if burning:
            nearest = min(
                abs(cell[0] - fx) + abs(cell[1] - fy) for fx, fy in burning
            )
            if nearest < self._effective_standoff_min(model):
                return True
        return False

    def _hold_escape_direction(self, agent: Any) -> int | None:
        if str(self._read_uav_role() or "").strip().lower() == "fire_tracker":
            fire_escape = self._fire_tracker_hold_escape_direction(agent)
            if fire_escape is not None:
                return fire_escape
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        model = self._resolve_model(agent)
        x, y = int(pos[0]), int(pos[1])
        current_boundary_dist = self._distance_from_boundary(x, y, model)
        scored: list[tuple[float, float, int]] = []
        for direction in range(4):
            if not self._direction_in_bounds(agent, direction):
                continue
            nx = x + _MOVE_X[direction]
            ny = y + _MOVE_Y[direction]
            if self._cell_is_movement_hazard((nx, ny)):
                continue
            next_boundary_dist = self._distance_from_boundary(nx, ny, model)
            score = (next_boundary_dist - current_boundary_dist) * 10.0
            if model is not None:
                obs_radius = getattr(
                    model,
                    "UAV_OBSERVATION_RADIUS",
                    getattr(model, "observation_radius", 8),
                )
                managed = getattr(model, "managed_uav_states", {}) or {}
                uid = str(self.uav_id)
                for other_uid, ustate in managed.items():
                    if str(other_uid) == uid:
                        continue
                    other_pos = getattr(ustate, "position", None)
                    if other_pos is None:
                        continue
                    try:
                        dx = float(nx) - float(other_pos[0])
                        dy = float(ny) - float(other_pos[1])
                        dist = (dx * dx + dy * dy) ** 0.5
                        if dist < float(obs_radius):
                            score -= 6.0 * (1.0 - dist / float(obs_radius))
                        else:
                            score += min(dist, float(obs_radius)) * 0.05
                    except Exception:
                        continue
            scored.append((score, next_boundary_dist, direction))
        if not scored:
            return None
        return max(scored, key=lambda item: (item[0], item[1]))[2]

    def _fire_tracker_hold_escape_direction(self, agent: Any) -> int | None:
        model = self._resolve_model(agent)
        cache = self._get_tracker_hazard_cache(model)
        fire_cells = set(cache["burning_cells"])
        if not fire_cells:
            fire_cells = self._collect_active_fire_cells(model)
        if fire_cells:
            fire_targets = [
                (float(fx), float(fy)) for fx, fy in sorted(fire_cells)
            ]
            target = self._fire_tracker_outward_escape_target(
                agent, fire_targets, fire_cells,
            )
            if target is not None:
                direction = self._choose_best_direction_fire(
                    agent,
                    target,
                    fire_cells=fire_cells,
                    escape_mode=True,
                )
                cell = self._next_cell_for_direction(agent, direction)
                if cell is not None and not self._fire_tracker_cell_disqualified(
                    cell, model=model,
                ):
                    return direction
        return self._fire_tracker_hold_escape_one_step(agent, fire_cells)

    def _fire_tracker_hold_escape_one_step(
        self,
        agent: Any,
        fire_cells: set[tuple[int, int]],
    ) -> int | None:
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        model = self._resolve_model(agent)
        x, y = int(pos[0]), int(pos[1])
        cache = self._get_tracker_hazard_cache(model)
        hazard_cells = cache["hazard_cells"]
        cur_fire_dist = (
            min(abs(x - fx) + abs(y - fy) for fx, fy in fire_cells)
            if fire_cells
            else 99.0
        )
        cur_hazard_dist = self._min_tracker_hazard_distance(
            (x, y), hazard_cells, model=model,
        )
        safe_scored: list[tuple[float, int]] = []
        fallback_scored: list[tuple[float, float, float, int]] = []
        for direction in range(4):
            if not self._direction_in_bounds(agent, direction):
                continue
            nx = x + _MOVE_X[direction]
            ny = y + _MOVE_Y[direction]
            cell = (nx, ny)
            disqualified = self._fire_tracker_cell_disqualified(cell, model=model)
            new_fire_dist = (
                min(abs(nx - fx) + abs(ny - fy) for fx, fy in fire_cells)
                if fire_cells
                else 99.0
            )
            new_hazard_dist = self._min_tracker_hazard_distance(
                cell, hazard_cells, model=model,
            )
            score = new_fire_dist * 20.0 + new_hazard_dist * 15.0
            if new_fire_dist > cur_fire_dist:
                score += 30.0
            if new_hazard_dist > cur_hazard_dist:
                score += 25.0
            if not disqualified:
                safe_scored.append((score, direction))
            else:
                fallback_scored.append(
                    (new_fire_dist, new_hazard_dist, score, direction)
                )
        if safe_scored:
            return max(safe_scored, key=lambda item: item[0])[1]
        if fallback_scored:
            off_fire = [item for item in fallback_scored if item[0] > 0.0]
            pool = off_fire if off_fire else fallback_scored
            return max(
                pool,
                key=lambda item: (item[0], item[1], item[2]),
            )[3]
        return None

    def _execute_search_mode(
        self,
        agent: Any,
        fail_safe_decision: FailSafeDecision,
        timestamp: float,
        decision: PathDecision | None,
    ) -> dict[str, object]:
        target = self._safe_search_target(
            agent,
            self._sector_biased_target(
                self._search_target(fail_safe_decision, timestamp)
            ),
        )
        decision_id = (
            fail_safe_decision.decision_id
            if decision is None
            else decision.decision_id
        )

        if target is None:
            chosen_dir = self._exploration_fallback(agent)
            action = "search_mode"
            chosen_dir, action = self._apply_final_direction_safety(
                agent, chosen_dir, action
            )
            self._commit_execution_direction(agent, chosen_dir, action)
            if self._execution_log is not None:
                self._execution_log.add(
                    ExecutionResult(
                        decision_id=decision_id,
                        executor_type="uav",
                        target_entity=self.uav_id,
                        action=action,
                        status="partial_success",
                        timestamp=timestamp,
                        intended_effect=fail_safe_decision.target_region,
                        actual_result="no_search_target",
                        feedback_event={"reason": "no_search_target"},
                        confidence_before=fail_safe_decision.confidence_score,
                        confidence_after=fail_safe_decision.confidence_score,
                        explanation=fail_safe_decision.explanation,
                    )
                )
            return {
                "applied": False,
                "status": "partial_success",
                "reason": "no_search_target",
                "uav_id": self.uav_id,
                "decision_id": decision_id,
                "selected_dir": chosen_dir,
                "action": action,
            }

        try:
            uav_index = int(
                "".join(filter(str.isdigit, str(self.uav_id) or "0")) or "0"
            ) % 4
        except Exception:
            uav_index = 0
        model = getattr(agent, "model", None) or self._model
        if self._sector_filtering_active(model) and self._uav_sector_bounds(model):
            offset_target = self._safe_search_target(agent, target)
        else:
            _SEARCH_OFFSETS = ((0, 0), (5, 0), (0, 5), (-5, 0))
            ox, oy = _SEARCH_OFFSETS[uav_index]
            tx = float(target[0]) + ox
            ty = float(target[1]) + oy
            if model is not None:
                width = self._grid_dimension(model, ("grid_width", "WIDTH", "width"))
                height = self._grid_dimension(model, ("grid_height", "HEIGHT", "height"))
                if width is not None and height is not None:
                    tx = min(max(tx, 0.0), float(width - 1))
                    ty = min(max(ty, 0.0), float(height - 1))
            offset_target = self._safe_search_target(agent, (tx, ty))
        chosen_dir = self._choose_best_direction(agent, offset_target)
        action = "search_mode"
        chosen_dir, action = self._apply_final_direction_safety(
            agent, chosen_dir, action
        )
        self._commit_execution_direction(agent, chosen_dir, action)

        if self._execution_log is not None:
            self._execution_log.add(
                ExecutionResult(
                    decision_id=decision_id,
                    executor_type="uav",
                    target_entity=self.uav_id,
                    action=action,
                    status="success",
                    timestamp=timestamp,
                    intended_effect=fail_safe_decision.target_region,
                    actual_result=f"selected_dir={chosen_dir}",
                    feedback_event={
                        "search_target": target,
                        "selected_dir": chosen_dir,
                    },
                    confidence_before=fail_safe_decision.confidence_score,
                    confidence_after=fail_safe_decision.confidence_score,
                    explanation=fail_safe_decision.explanation,
                )
            )

        return {
            "applied": True,
            "uav_id": self.uav_id,
            "decision_id": decision_id,
            "selected_dir": chosen_dir,
            "action": action,
            "search_target": target,
        }

    def _role_kind(self, role: str | None) -> str:
        normalized = (role or "").strip().lower()
        if normalized in _VICTIM_ROLES or "victim" in normalized:
            return "victim"
        if normalized in _FIRE_ROLES or "fire" in normalized:
            return "fire"
        return "general"

    @staticmethod
    def _role_is_victim_searcher(role: str | None) -> bool:
        normalized = (role or "").strip().lower()
        return normalized in {"victim_searcher", "victim_search"} or (
            "victim" in normalized and "search" in normalized
        )

    def _resolve_direction_intent(
        self,
        agent: Any,
        decision: PathDecision,
        role_kind: str,
        action: str,
    ) -> tuple[int, str]:
        chosen_dir = int(getattr(agent, "selected_dir", 0))

        if role_kind == "victim":
            target = self._nearest_target(self._victim_positions_from_runtime())
            if target is None:
                model = getattr(agent, "model", None) or self._model
                victim_id = self._victim_id_from_decision(decision, model)
                if victim_id is None:
                    target = None
                else:
                    target = self._target_from_decision(decision)
                    if target is not None and model is not None:
                        victim_model = getattr(model, "victim_runtime_model", None)
                        victims = (
                            getattr(victim_model, "victims", None)
                            if victim_model is not None
                            else None
                        )
                        victim_entry = (
                            victims.get(victim_id)
                            if isinstance(victims, dict)
                            else None
                        )
                        if self._victim_handled_for_uav_target(
                            victim_id, victim_entry or {}, model
                        ):
                            target = None
            if target is not None:
                chosen = self._choose_best_direction(
                    agent, target, target_kind="victim"
                )
                action_label = "computed_from_target"
                model = getattr(agent, "model", None) or self._model
                uid = str(self.uav_id)
                escape_mem = (
                    getattr(model, "_victim_escape_memory", {})
                    if model is not None
                    else {}
                )
                if not isinstance(escape_mem, dict):
                    escape_mem = {}
                entry = escape_mem.get(uid, {})
                if not isinstance(entry, dict):
                    entry = {}
                pos = getattr(agent, "pos", None)
                if pos is not None:
                    ax, ay = float(pos[0]), float(pos[1])
                    tx, ty = float(target[0]), float(target[1])
                    cur_dist = abs(ax - tx) + abs(ay - ty)
                    last_dist = entry.get("last_dist_to_target")
                    escape_steps = int(entry.get("escape_steps_remaining", 0) or 0)
                    escape_dir = entry.get("escape_dir")
                    cleared_escape = False
                    if (
                        last_dist is not None
                        and cur_dist <= float(last_dist) - 3.0
                    ):
                        entry = {
                            "escape_dir": None,
                            "escape_steps_remaining": 0,
                            "last_dist_to_target": cur_dist,
                        }
                        if model is not None:
                            if not hasattr(model, "_victim_escape_memory"):
                                model._victim_escape_memory = {}
                            model._victim_escape_memory[uid] = entry
                        cleared_escape = True
                    elif escape_steps > 0 and escape_dir is not None:
                        committed_dir = int(escape_dir)
                        if self._direction_in_bounds(agent, committed_dir):
                            escape_steps -= 1
                            entry["escape_steps_remaining"] = escape_steps
                            entry["escape_dir"] = committed_dir
                            entry["last_dist_to_target"] = cur_dist
                            if model is not None:
                                if not hasattr(model, "_victim_escape_memory"):
                                    model._victim_escape_memory = {}
                                model._victim_escape_memory[uid] = entry
                            return committed_dir, "victim_escape_committed"
                    elif (
                        not cleared_escape
                        and last_dist is not None
                        and cur_dist >= float(last_dist) - 0.5
                    ):
                        oscillation_candidates: list[
                            tuple[float, bool, int]
                        ] = []
                        for direction in range(4):
                            if not self._direction_in_bounds(agent, direction):
                                continue
                            nx = int(pos[0]) + _MOVE_X[direction]
                            ny = int(pos[1]) + _MOVE_Y[direction]
                            candidate_distance = (
                                abs(float(nx) - tx) + abs(float(ny) - ty)
                            )
                            progress = cur_dist - candidate_distance
                            hazardous = self._cell_high_fire(
                                (nx, ny)
                            ) or self._cell_smoke_obscured((nx, ny))
                            oscillation_candidates.append(
                                (progress, hazardous, direction)
                            )
                        best_escape_dir: int | None = None
                        if oscillation_candidates:
                            safe_positive = [
                                item
                                for item in oscillation_candidates
                                if not item[1] and item[0] > 0
                            ]
                            if safe_positive:
                                best_escape_dir = max(
                                    safe_positive, key=lambda item: item[0]
                                )[2]
                            else:
                                safe_candidates = [
                                    item
                                    for item in oscillation_candidates
                                    if not item[1]
                                ]
                                if safe_candidates:
                                    best_escape_dir = max(
                                        safe_candidates,
                                        key=lambda item: item[0],
                                    )[2]
                                else:
                                    best_escape_dir = max(
                                        oscillation_candidates,
                                        key=lambda item: item[0],
                                    )[2]
                        if best_escape_dir is not None:
                            entry = {
                                "escape_dir": best_escape_dir,
                                "escape_steps_remaining": 5,
                                "last_dist_to_target": cur_dist,
                            }
                            if model is not None:
                                if not hasattr(model, "_victim_escape_memory"):
                                    model._victim_escape_memory = {}
                                model._victim_escape_memory[uid] = entry
                            return best_escape_dir, "victim_escape_committed"
                    elif not cleared_escape:
                        entry = {
                            "escape_dir": None,
                            "escape_steps_remaining": 0,
                            "last_dist_to_target": cur_dist,
                        }
                        if model is not None:
                            if not hasattr(model, "_victim_escape_memory"):
                                model._victim_escape_memory = {}
                            model._victim_escape_memory[uid] = entry
                stuck_counts = (
                    getattr(model, "_uav_stuck_counts", {})
                    if model is not None
                    else {}
                )
                is_stuck = int(stuck_counts.get(uid, 0) or 0) >= 2
                pos = getattr(agent, "pos", None)
                if is_stuck:
                    action_label = "victim_stuck_escape"
                    ax, ay = float(pos[0]), float(pos[1])
                    tx, ty = float(target[0]), float(target[1])
                    current_distance = abs(ax - tx) + abs(ay - ty)
                    fire_map = self._read_fire_probability_map()
                    obs_map: dict[Any, Any] = {}
                    if model is not None:
                        visibility = getattr(model, "visibility_model", None)
                        if visibility is not None:
                            status_map = getattr(
                                getattr(visibility, "state", None),
                                "observation_status_map",
                                None,
                            )
                            if isinstance(status_map, dict):
                                obs_map = status_map
                    failed_dir = -1
                    try:
                        failed_map = getattr(model, "uav_last_failed_dir", None)
                        if isinstance(failed_map, dict):
                            failed_dir = int(failed_map.get(uid, -1))
                    except Exception:
                        pass
                    escape_scored: list[tuple[float, int, float, float, int, int]] = []
                    for direction in range(4):
                        if not self._direction_in_bounds(agent, direction):
                            continue
                        nx = int(pos[0]) + _MOVE_X[direction]
                        ny = int(pos[1]) + _MOVE_Y[direction]
                        candidate_distance = abs(float(nx) - tx) + abs(float(ny) - ty)
                        progress = current_distance - candidate_distance
                        score = 0.0
                        score -= candidate_distance * 0.2
                        score += progress * 2.0
                        if progress < 0:
                            score -= 4.0
                        hazard = 0.0
                        if self._cell_high_fire((nx, ny)):
                            score -= 8.0
                            hazard += 8.0
                        if self._cell_smoke_obscured((nx, ny)):
                            score -= 4.0
                            hazard += 4.0
                        nx2 = nx + _MOVE_X[direction]
                        ny2 = ny + _MOVE_Y[direction]
                        fire_prob_2 = fire_map.get((float(nx2), float(ny2)))
                        if fire_prob_2 is None:
                            fire_prob_2 = fire_map.get((nx2, ny2))
                        if fire_prob_2 is None:
                            fire_prob_2 = 0.0
                        if float(fire_prob_2) >= 0.5:
                            score -= 4.0
                            hazard += 4.0
                        smoke_status_2 = obs_map.get((float(nx2), float(ny2)))
                        if smoke_status_2 is None:
                            smoke_status_2 = obs_map.get((nx2, ny2), "")
                        if isinstance(smoke_status_2, str) and "smoke" in smoke_status_2.lower():
                            score -= 2.0
                            hazard += 2.0
                        elif (
                            hasattr(smoke_status_2, "value")
                            and "smoke" in str(smoke_status_2.value).lower()
                        ):
                            score -= 2.0
                            hazard += 2.0
                        score -= self._visit_penalty(nx, ny) * 0.5
                        if self._is_failed_direction(direction):
                            score -= 5.0
                        preferred = self._direction_toward(agent, target)
                        if direction == preferred:
                            score += 0.5
                        if (
                            direction == preferred
                            and progress > 0
                            and hazard < 8.0
                            and not self._cell_smoke_obscured((nx, ny))
                        ):
                            score += 1.5
                        if model is not None:
                            obs_radius = getattr(
                                model,
                                "UAV_OBSERVATION_RADIUS",
                                getattr(model, "observation_radius", 8),
                            )
                            managed = getattr(model, "managed_uav_states", {}) or {}
                            for other_uid, ustate in managed.items():
                                if str(other_uid) == uid:
                                    continue
                                other_pos = getattr(ustate, "position", None)
                                if other_pos is None:
                                    continue
                                try:
                                    dx = float(nx) - float(other_pos[0])
                                    dy = float(ny) - float(other_pos[1])
                                    dist = (dx * dx + dy * dy) ** 0.5
                                    if dist < float(obs_radius):
                                        score -= 6.0 * (1.0 - dist / float(obs_radius))
                                except Exception:
                                    continue
                        escape_scored.append(
                            (score, direction, progress, hazard, nx, ny)
                        )

                    if escape_scored:
                        safe_candidates = [
                            item
                            for item in escape_scored
                            if not self._cell_high_fire((item[4], item[5]))
                            and not self._cell_smoke_obscured((item[4], item[5]))
                        ]
                        safe_improving = [
                            item for item in safe_candidates if item[2] > 0
                        ]
                        if safe_improving:
                            pool = safe_improving
                        elif safe_candidates:
                            pool = safe_candidates
                        else:
                            improving = [
                                item for item in escape_scored if item[2] > 0
                            ]
                            pool = improving if improving else escape_scored
                        min_hazard = min(item[3] for item in pool)
                        low_hazard = [
                            item for item in pool if item[3] <= min_hazard + 0.01
                        ]
                        non_failed = [
                            item for item in low_hazard if item[1] != failed_dir
                        ]
                        pick_from = non_failed if non_failed else low_hazard
                        chosen = max(pick_from, key=lambda item: item[0])[1]
                return chosen, action_label
            else:
                model = getattr(agent, "model", None) or self._model
                uid = str(self.uav_id)
                pos = getattr(agent, "pos", None)

                sweep_states = (
                    getattr(model, "_victim_sweep_state", {})
                    if model is not None
                    else {}
                )
                if model is not None and not isinstance(
                    getattr(model, "_victim_sweep_state", None), dict
                ):
                    model._victim_sweep_state = {}
                    sweep_states = model._victim_sweep_state
                state = sweep_states.get(uid)

                H = (
                    int(getattr(model, "HEIGHT", getattr(model, "height", 50)))
                    if model
                    else 50
                )
                W = (
                    int(getattr(model, "WIDTH", getattr(model, "width", 50)))
                    if model
                    else 50
                )
                STEP = 8

                wind_dir = self._get_wind_direction(model)
                ctx = getattr(decision, "uncertainty_context", None)
                if not isinstance(ctx, dict):
                    ctx = {}
                needs_retarget = bool(
                    ctx.get("needs_new_wind_target")
                    or ctx.get("wind_target_reached")
                    or ctx.get("force_wind_retarget")
                    or ctx.get("force_wind_sweep")
                )
                wind_state = _wind_search_state(model, uid)
                escape_raw = wind_state.get("escape_target")
                if isinstance(escape_raw, (list, tuple)) and len(escape_raw) >= 2:
                    wind_state["hazard_buffer_level"] = 2
                    escape_target = (float(escape_raw[0]), float(escape_raw[1]))
                    pos = getattr(agent, "pos", None)
                    if pos is not None:
                        dist_escape = abs(float(pos[0]) - escape_target[0]) + abs(
                            float(pos[1]) - escape_target[1]
                        )
                        if dist_escape <= 2.0:
                            wind_state["escape_target"] = None
                            wind_state["pocket_anchor"] = None
                            wind_state["pocket_streak"] = 0
                            wind_state["force_coverage_escape"] = False
                        else:
                            routed = self._attempt_pathfinding_toward_target(
                                agent,
                                escape_target,
                                action_label="victim_search_wind_aware_retarget_to_interior",
                                prefer_bfs_action_label=True,
                            )
                            if routed is not None:
                                return routed
                            chosen = self._choose_best_direction(
                                agent, escape_target, target_kind="victim"
                            )
                            chosen_dir, action_label = self._apply_victim_searcher_hazard_gate(
                                agent,
                                chosen,
                                "victim_search_wind_aware_retarget_to_interior",
                            )
                            return chosen_dir, action_label
                force_sweep = bool(wind_state.get("force_sweep")) or bool(
                    ctx.get("force_wind_sweep")
                )
                if force_sweep:
                    needs_retarget = True
                else:
                    planner_wind = self._planner_wind_aware_target_from_decision(decision)
                    if planner_wind is not None and not needs_retarget:
                        wind_target, wind_meta = planner_wind
                        if self._wind_target_is_saturated(model, wind_target):
                            planner_wind = None
                            needs_retarget = True
                    if planner_wind is not None and not needs_retarget:
                        wind_target, wind_meta = planner_wind
                        chosen_dir, action_label = self._apply_victim_searcher_hazard_gate(
                            agent,
                            self._choose_best_direction(
                                agent, wind_target, target_kind="victim"
                            ),
                            "victim_search_wind_aware",
                        )
                        self._record_wind_aware_explanation(
                            agent,
                            wind_direction=str(
                                wind_meta.get("wind_direction", wind_dir) or wind_dir
                            ),
                            target=wind_target,
                            model=model,
                            source="planner",
                            reason="planner selected safe downwind search target",
                        )
                        return chosen_dir, action_label

                    force_coverage = bool(
                        wind_state.get("force_coverage_escape")
                        or ctx.get("force_coverage_escape")
                        or int(wind_state.get("sweep_no_move_streak", 0) or 0)
                        >= WIND_SWEEP_NO_MOVE_ESCAPE
                        or int(wind_state.get("pocket_streak", 0) or 0)
                        >= WIND_POCKET_CAMP_THRESHOLD
                    )
                    force_interior = bool(
                        wind_state.get("force_interior_retarget")
                        or ctx.get("force_wind_retarget")
                        or force_coverage
                        or self._victim_near_edge_escape_required(agent, model)
                    )
                    if force_coverage:
                        wind_state["force_coverage_escape"] = True
                        wind_state["force_interior_retarget"] = True
                        wind_state["force_sweep"] = False
                        force_sweep = False
                    wind_target = self._wind_aware_victim_search_target(agent, model)
                    if wind_target is not None:
                        if force_coverage or force_interior:
                            action_label = "victim_search_wind_aware_retarget_to_interior"
                        elif needs_retarget:
                            action_label = "victim_search_wind_aware_retarget"
                        else:
                            action_label = "victim_search_wind_aware"
                        if force_coverage or force_interior:
                            return self._apply_retarget_with_pathfinding_fallback(
                                agent, wind_target, action_label,
                            )
                        chosen_dir, action_label = self._apply_victim_searcher_hazard_gate(
                            agent,
                            self._choose_best_direction(
                                agent, wind_target, target_kind="victim"
                            ),
                            action_label,
                        )
                        return chosen_dir, action_label

                if force_sweep and int(wind_state.get("pocket_streak", 0) or 0) >= 12:
                    wind_state["force_sweep"] = False
                    force_sweep = False
                    wind_state["force_coverage_escape"] = True

                if force_sweep and (
                    bool(wind_state.get("force_coverage_escape"))
                    or int(wind_state.get("pocket_streak", 0) or 0) >= WIND_POCKET_CAMP_THRESHOLD
                ):
                    wind_state["force_sweep"] = False
                    force_sweep = False
                    wind_target = self._wind_aware_victim_search_target(agent, model)
                    if wind_target is not None:
                        return self._apply_retarget_with_pathfinding_fallback(
                            agent,
                            wind_target,
                            "victim_search_wind_aware_retarget_to_interior",
                        )

                if state is None:
                    bounds = (
                        self._uav_sector_bounds(model)
                        if self._sector_filtering_active(model)
                        else None
                    )
                    state = self._init_wind_aware_sweep_state(
                        model,
                        pos,
                        bounds,
                        H,
                        W,
                        wind_dir,
                    )
                    sweep_states[uid] = state
                elif str(state.get("wind_direction", "")) != wind_dir:
                    bounds = (
                        self._uav_sector_bounds(model)
                        if self._sector_filtering_active(model)
                        else None
                    )
                    state = self._init_wind_aware_sweep_state(
                        model,
                        pos,
                        bounds,
                        H,
                        W,
                        wind_dir,
                    )
                    sweep_states[uid] = state

                tx = state["sweep_x"]
                ty = state["sweep_y"]
                sector_bounds = (
                    self._uav_sector_bounds(model)
                    if self._sector_filtering_active(model)
                    else None
                )

                if pos is not None:
                    cur_x, cur_y = int(pos[0]), int(pos[1])

                    at_target = abs(cur_x - tx) <= 1 and abs(cur_y - ty) <= 1
                    y_end = (W - 1) if state["sweep_dir"] == 1 else 0
                    if sector_bounds is not None:
                        y_end = (
                            sector_bounds["y_max"]
                            if state["sweep_dir"] == 1
                            else sector_bounds["y_min"]
                        )

                    if at_target and abs(cur_y - y_end) <= 1:
                        next_x = min(tx + STEP, H - 1)
                        if sector_bounds is not None:
                            next_x = min(next_x, sector_bounds["x_max"])
                            if next_x >= sector_bounds["x_max"]:
                                next_x = sector_bounds["x_min"]
                        elif next_x >= H - 1:
                            next_x = 0
                        state["sweep_x"] = next_x
                        state["sweep_dir"] = -state["sweep_dir"]
                        state["sweep_y"] = (
                            sector_bounds["y_min"]
                            if sector_bounds is not None
                            and state["sweep_dir"] == 1
                            else (
                                sector_bounds["y_max"]
                                if sector_bounds is not None
                                else (0 if state["sweep_dir"] == 1 else W - 1)
                            )
                        )
                        sweep_states[uid] = state
                    elif at_target:
                        state["sweep_y"] = ty + state["sweep_dir"] * STEP
                        if sector_bounds is not None:
                            state["sweep_y"] = max(
                                sector_bounds["y_min"],
                                min(sector_bounds["y_max"], state["sweep_y"]),
                            )
                        else:
                            state["sweep_y"] = max(0, min(W - 1, state["sweep_y"]))
                        sweep_states[uid] = state

                sweep_target = self._safe_victim_sweep_target(
                    agent,
                    state,
                    model,
                    sector_bounds,
                    H,
                    W,
                    STEP,
                    pos,
                )
                sweep_dir = self._choose_best_direction(
                    agent, sweep_target, target_kind="victim"
                )
                sweep_action = "victim_search_wind_aware_sweep"
                if needs_retarget or bool(wind_state.get("force_sweep")):
                    sweep_action = "victim_search_wind_aware_sweep"
                chosen_dir, sweep_action = self._apply_victim_searcher_hazard_gate(
                    agent,
                    sweep_dir,
                    sweep_action,
                )
                return chosen_dir, sweep_action

        if role_kind == "fire":
            fire_resolved = self._try_resolve_fire_role_direction(
                agent, decision, action
            )
            if fire_resolved is not None:
                return fire_resolved

        if action in _CARDINAL_WORDS:
            return (
                self._choose_best_direction(
                    agent,
                    self._cardinal_target_cell(agent, _CARDINAL_TO_DIR[action]),
                ),
                action,
            )

        waypoints = decision.waypoints_by_uav.get(self.uav_id)
        if waypoints:
            return self._choose_best_direction(agent, waypoints[0]), "waypoint"

        if decision.path_segment:
            return (
                self._choose_best_direction(agent, decision.path_segment[0]),
                "path_segment",
            )

        if action and action not in _CARDINAL_WORDS:
            target = self._target_from_decision(decision)
            if target is not None:
                return self._choose_best_direction(agent, target), "computed_from_target"

        target = self._nearest_sector_target(self._uncertainty_positions_from_runtime())
        if target is None:
            target = self._sector_biased_target(self._target_from_decision(decision))
        if target is not None:
            return self._choose_best_direction(agent, target), "computed_from_target"

        return self._exploration_fallback(
            agent, victim_search=(role_kind == "victim")
        ), "exploration_fallback"

    def _target_from_decision(self, decision: PathDecision) -> tuple[float, float] | None:
        ctx = decision.uncertainty_context
        if isinstance(ctx, dict):
            for key in ("target_position", "target_region", "waypoint", "target_location"):
                parsed = self._normalize_target(ctx.get(key))
                if parsed is not None:
                    return parsed
        waypoints = decision.waypoints_by_uav.get(self.uav_id)
        if waypoints:
            return waypoints[0]
        if decision.path_segment:
            return decision.path_segment[0]
        return None

    def _victim_id_from_decision(
        self,
        decision: PathDecision,
        model: Any | None = None,
    ) -> str | None:
        ctx = decision.uncertainty_context
        victim_id: str | None = None
        if isinstance(ctx, dict):
            raw_id = ctx.get("victim_id")
            if raw_id is not None and str(raw_id).strip():
                victim_id = str(raw_id).strip()
        if victim_id is None:
            option_id = str(getattr(decision, "selected_option_id", "") or "")
            prefix = "local_path_move_toward_victim_candidate_"
            if option_id.startswith(prefix):
                suffix = option_id[len(prefix) :].strip()
                if suffix:
                    victim_id = suffix
        if victim_id is None:
            return None
        resolved_model = model or self._model
        if resolved_model is None:
            return victim_id
        victim_model = getattr(resolved_model, "victim_runtime_model", None)
        victims = (
            getattr(victim_model, "victims", None)
            if victim_model is not None
            else None
        )
        victim_entry = (
            victims.get(victim_id) if isinstance(victims, dict) else None
        )
        if self._victim_handled_for_uav_target(
            victim_id, victim_entry or {}, resolved_model
        ):
            return None
        return victim_id

    def _victim_handled_for_uav_target(
        self,
        victim_id: str,
        victim: Any,
        model: Any,
    ) -> bool:
        terminal_statuses = frozenset(
            {"dead", "cancelled", "rescued", "unreachable"}
        )
        handled_statuses = terminal_statuses | frozenset(
            {"confirmed", "assigned", "delayed"}
        )
        managed = getattr(model, "managed_victims", None)
        if isinstance(managed, dict):
            state = managed.get(victim_id)
            if state is not None:
                status = str(getattr(state, "status", "") or "").strip().lower()
                if status in terminal_statuses:
                    return True
                if getattr(state, "dead", False):
                    return True
                if getattr(state, "cancelled", False):
                    return True
                if getattr(state, "rescued", False):
                    return True
                if getattr(state, "unreachable", False):
                    return True
                if getattr(state, "rescue_assigned", False):
                    return True
                if getattr(state, "confirmed", False):
                    return True
                if getattr(state, "assigned", False):
                    return True
                if status in handled_statuses:
                    return True
        markers = getattr(model, "victim_marker_agents", None)
        if isinstance(markers, dict):
            marker = markers.get(victim_id)
            if marker is not None:
                marker_status = str(
                    getattr(marker, "status", "") or ""
                ).strip().lower()
                if marker_status in terminal_statuses:
                    return True
        if isinstance(victim, dict):
            if victim.get("dead") or victim.get("cancelled"):
                return True
            if victim.get("rescued") or victim.get("unreachable"):
                return True
            if victim.get("confirmed") or victim.get("rescue_assigned"):
                return True
            if victim.get("assigned"):
                return True
            status = str(victim.get("status", "") or "").strip().lower()
            if status in handled_statuses:
                return True
        else:
            status = str(getattr(victim, "status", "") or "").strip().lower()
            if status in terminal_statuses:
                return True
            rescue_state = str(
                getattr(victim, "rescue_state", "") or ""
            ).strip().lower()
            if rescue_state in terminal_statuses | frozenset({"completed", "handled"}):
                return True
            if getattr(victim, "dead", False):
                return True
            if getattr(victim, "cancelled", False):
                return True
            if getattr(victim, "rescued", False):
                return True
            if getattr(victim, "unreachable", False):
                return True
            if getattr(victim, "rescue_assigned", False):
                return True
            if getattr(victim, "confirmed", False):
                return True
            if getattr(victim, "assigned", False):
                return True
            if status in handled_statuses:
                return True
        return False

    def _victim_positions_from_runtime(self) -> list[tuple[float, float]]:
        model = self._model
        if model is None:
            return []
        victim_model = getattr(model, "victim_runtime_model", None)
        if victim_model is None:
            return []
        victims = getattr(victim_model, "victims", None)
        if not isinstance(victims, dict):
            return []
        positions: list[tuple[float, float]] = []
        for victim_id, victim in victims.items():
            if self._victim_handled_for_uav_target(str(victim_id), victim, model):
                continue
            if isinstance(victim, dict):
                for key in ("estimated_position", "position", "current_position"):
                    parsed = self._normalize_target(victim.get(key))
                    if parsed is not None:
                        positions.append(parsed)
                        break
            else:
                for key in ("estimated_position", "position", "current_position"):
                    parsed = self._normalize_target(getattr(victim, key, None))
                    if parsed is not None:
                        positions.append(parsed)
                        break
        return positions

    def _fire_positions_from_runtime(self) -> list[tuple[float, float]]:
        fire_map = self._read_fire_probability_map()
        if not fire_map:
            return []
        front_cells: list[tuple[int, int]] = []
        all_high: list[tuple[int, int]] = []
        for cell_pos, raw_prob in fire_map.items():
            normalized = self._normalize_cell_pos(cell_pos)
            if normalized is None or float(raw_prob) < 0.3:
                continue
            all_high.append(normalized)
            if self._is_fire_front_cell_simple(normalized, fire_map):
                front_cells.append(normalized)
        preferred = front_cells if front_cells else all_high
        return [(float(c[0]), float(c[1])) for c in preferred]

    def _cell_in_bounds(self, cell: tuple[int, int]) -> bool:
        model = self._model
        if model is None:
            return True
        grid = getattr(model, "grid", None)
        out_of_bounds = getattr(grid, "out_of_bounds", None) if grid is not None else None
        if callable(out_of_bounds):
            return not out_of_bounds(cell)
        width = self._grid_dimension(model, ("grid_width", "WIDTH", "width"))
        height = self._grid_dimension(model, ("grid_height", "HEIGHT", "height"))
        if width is None or height is None:
            return True
        return 0 <= cell[0] < height and 0 <= cell[1] < width

    def _cell_is_movement_hazard(self, cell: tuple[int, int]) -> bool:
        return self._cell_danger_level(cell) > 0

    def _next_cell_for_direction(
        self,
        agent: Any,
        direction: int,
    ) -> tuple[int, int] | None:
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        return (
            int(pos[0]) + _MOVE_X[direction],
            int(pos[1]) + _MOVE_Y[direction],
        )

    def _direction_danger_level(self, agent: Any, direction: int) -> int:
        if self._can_check_bounds(agent) and not self._direction_in_bounds(
            agent, direction
        ):
            return 3
        cell = self._next_cell_for_direction(agent, direction)
        if cell is None:
            return 3
        return self._cell_danger_level(cell)

    def _cell_danger_level(self, cell: tuple[int, int]) -> int:
        if not self._cell_in_bounds(cell):
            return 3
        if self._cell_high_fire(cell):
            return 2
        if self._cell_smoke_obscured(cell):
            return 1
        return 0

    def _direction_moves_to_hazard(self, agent: Any, direction: int) -> bool:
        return self._direction_danger_level(agent, direction) > 0

    def _filter_scored_by_hard_safety(
        self,
        agent: Any,
        scored: list[tuple[Any, ...]],
        *,
        direction_index: int = 1,
    ) -> list[tuple[Any, ...]]:
        if not scored:
            return scored
        ranked = [
            (
                item,
                self._direction_danger_level(agent, int(item[direction_index])),
            )
            for item in scored
        ]
        min_level = min(level for _, level in ranked)
        return [item for item, level in ranked if level == min_level]

    def _direction_escape_score(
        self,
        agent: Any,
        direction: int,
        danger_level: int,
    ) -> float:
        cell = self._next_cell_for_direction(agent, direction)
        if cell is None:
            return -float("inf")
        model = self._resolve_model(agent)
        score = self._distance_from_boundary(cell[0], cell[1], model) * 10.0
        if danger_level > 0:
            score -= float(danger_level) * 100.0
        if model is not None:
            obs_radius = getattr(
                model,
                "UAV_OBSERVATION_RADIUS",
                getattr(model, "observation_radius", 8),
            )
            managed = getattr(model, "managed_uav_states", {}) or {}
            uid = str(self.uav_id)
            for other_uid, ustate in managed.items():
                if str(other_uid) == uid:
                    continue
                other_pos = getattr(ustate, "position", None)
                if other_pos is None:
                    continue
                try:
                    dx = float(cell[0]) - float(other_pos[0])
                    dy = float(cell[1]) - float(other_pos[1])
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist < float(obs_radius):
                        score -= 6.0 * (1.0 - dist / float(obs_radius))
                    else:
                        score += min(dist, float(obs_radius)) * 0.05
                except Exception:
                    continue
        return score

    def _safe_direction_or_escape(
        self,
        agent: Any,
        proposed_dir: int,
    ) -> tuple[int, bool]:
        proposed_level = self._direction_danger_level(agent, proposed_dir)
        if proposed_level == 0:
            return proposed_dir, False

        best_dir = proposed_dir
        best_level = proposed_level
        best_score = self._direction_escape_score(agent, proposed_dir, proposed_level)
        for direction in range(4):
            level = self._direction_danger_level(agent, direction)
            score = self._direction_escape_score(agent, direction, level)
            if level < best_level or (level == best_level and score > best_score):
                best_level = level
                best_score = score
                best_dir = direction
        return best_dir, best_dir != proposed_dir

    def _apply_final_direction_safety(
        self,
        agent: Any,
        chosen_dir: int,
        action: str,
    ) -> tuple[int, str]:
        final_dir, changed = self._safe_direction_or_escape(agent, chosen_dir)
        if changed:
            suffix = "hazard_escape"
            action = f"{action}_{suffix}" if action else suffix
        return final_dir, action

    def _strict_victim_hazard_level(self, cell: tuple[int, int]) -> int:
        if not self._cell_in_bounds(cell):
            return 3
        if self._cell_has_burning_fire(cell):
            return 2
        if self._cell_has_active_smoke(cell) or self._cell_smoke_obscured_active(cell):
            return 1
        return 0

    def _cell_smoke_obscured_active(self, cell: tuple[int, int]) -> bool:
        model = self._model
        if model is None:
            return False
        visibility = getattr(model, "visibility_model", None)
        if visibility is None:
            return False
        smoke_cells = getattr(visibility, "smoke_obscured_cells", None)
        if isinstance(smoke_cells, (set, list, tuple)) and cell in smoke_cells:
            return True
        status_map = getattr(
            getattr(visibility, "state", None), "observation_status_map", None
        )
        if not isinstance(status_map, dict):
            return False
        for key in (cell, (float(cell[0]), float(cell[1]))):
            status = status_map.get(key)
            if status is None:
                continue
            label = str(getattr(status, "value", status) or "").strip().lower()
            if label == "smoke_obscured":
                return True
        return False

    def _strict_neighbor_fire_risk(self, cell: tuple[int, int]) -> bool:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if self._strict_victim_hazard_level((cell[0] + dx, cell[1] + dy)) > 0:
                return True
        return False

    def _pocket_blocked_cells_for_escape(
        self, agent: Any, start: tuple[int, int],
    ) -> set[tuple[int, int]]:
        model = self._resolve_model(agent)
        if model is None:
            return set()
        ws = _wind_search_state(model, self.uav_id)
        pocket_active = (
            int(ws.get("pocket_streak", 0) or 0) >= 4
            or bool(ws.get("force_coverage_escape"))
            or ws.get("escape_target") is not None
        )
        if not pocket_active:
            return set()
        center = ws.get("pocket_center")
        if not isinstance(center, (list, tuple)) or len(center) < 2:
            return set()
        cx, cy = int(center[0]), int(center[1])
        start_dist = abs(start[0] - cx) + abs(start[1] - cy)
        blocked: set[tuple[int, int]] = set()
        center_cell = (cx, cy)
        if center_cell != start:
            blocked.add(center_cell)
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                cell = (cx + dx, cy + dy)
                if cell == start:
                    continue
                cell_dist = abs(cell[0] - cx) + abs(cell[1] - cy)
                if cell_dist < start_dist:
                    blocked.add(cell)
        last_pos = ws.get("last_grid_position")
        if isinstance(last_pos, (list, tuple)) and len(last_pos) >= 2:
            last_cell = (int(last_pos[0]), int(last_pos[1]))
            if last_cell != start:
                blocked.add(last_cell)
        for raw in ws.get("blocked_backtrack_cells") or ():
            if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                cell = (int(raw[0]), int(raw[1]))
                if cell != start:
                    blocked.add(cell)
        return blocked

    def _bfs_escape_max_depth(self, agent: Any) -> int:
        model = self._resolve_model(agent)
        if model is None:
            return BFS_ESCAPE_MAX_DEPTH
        height = int(getattr(model, "HEIGHT", getattr(model, "height", 50)) or 50)
        width = int(getattr(model, "WIDTH", getattr(model, "width", 50)) or 50)
        return max(BFS_ESCAPE_MAX_DEPTH, height + width + 5)

    def _attempt_pathfinding_toward_target(
        self,
        agent: Any,
        target: tuple[float, float],
        *,
        action_label: str,
        prefer_bfs_action_label: bool = False,
    ) -> tuple[int, str] | None:
        forced = self._forced_progress_direction(agent, target)
        if forced is None:
            return None
        next_cell = self._next_cell_for_direction(agent, forced)
        if next_cell is None or self._strict_victim_hazard_level(next_cell) != 0:
            return None
        escape_method = str(getattr(self, "_last_escape_method", "") or "")
        if prefer_bfs_action_label and escape_method.startswith("bfs"):
            return forced, "victim_search_escape_bfs"
        return forced, action_label

    def _apply_retarget_with_pathfinding_fallback(
        self,
        agent: Any,
        target: tuple[float, float],
        action_label: str,
    ) -> tuple[int, str]:
        routed = self._attempt_pathfinding_toward_target(
            agent,
            target,
            action_label=action_label,
            prefer_bfs_action_label=False,
        )
        if routed is not None:
            return routed
        chosen_dir, final_label = self._apply_victim_searcher_hazard_gate(
            agent,
            self._choose_best_direction(agent, target, target_kind="victim"),
            action_label,
        )
        return chosen_dir, final_label

    def _bfs_escape_direction(
        self,
        agent: Any,
        target: tuple[float, float],
        *,
        avoid_smoke: bool = True,
        max_depth: int = 30,
    ) -> int | None:
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        model = self._resolve_model(agent)
        start = (int(pos[0]), int(pos[1]))
        goal = (int(round(float(target[0]))), int(round(float(target[1]))))

        fire_cells = self._collect_strict_active_fire_cells(model)
        smoke_cells = self._collect_strict_smoke_cells(model) if avoid_smoke else set()
        blocked = fire_cells | smoke_cells | self._pocket_blocked_cells_for_escape(agent, start)

        def _within_goal_radius(cell: tuple[int, int]) -> bool:
            return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1]) <= 2

        def _passable(cell: tuple[int, int]) -> bool:
            return self._cell_in_bounds(cell) and cell not in blocked

        if _within_goal_radius(start):
            return None

        from collections import deque

        queue: deque[tuple[int, int]] = deque([start])
        visited: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        parent_dir: dict[tuple[int, int], int] = {}
        depth = 0
        while queue:
            if depth > max_depth:
                break
            level_size = len(queue)
            for _ in range(level_size):
                cell = queue.popleft()
                for direction in range(4):
                    ncell = (
                        cell[0] + _MOVE_X[direction],
                        cell[1] + _MOVE_Y[direction],
                    )
                    if ncell in visited:
                        continue
                    if not _passable(ncell):
                        continue
                    visited[ncell] = cell
                    parent_dir[ncell] = direction
                    if _within_goal_radius(ncell):
                        cur = ncell
                        while visited[cur] is not None and visited[cur] != start:
                            cur = visited[cur]  # type: ignore[assignment]
                        return parent_dir[cur]
                    queue.append(ncell)
            depth += 1
        return None

    def _forced_progress_direction(
        self, agent: Any, target: tuple[float, float],
    ) -> int | None:
        self._last_escape_method = None
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        x, y = int(pos[0]), int(pos[1])
        tx, ty = float(target[0]), float(target[1])
        current_dist = abs(tx - x) + abs(ty - y)
        best_dir: int | None = None
        best_progress = 0
        for direction in range(4):
            nx = x + _MOVE_X[direction]
            ny = y + _MOVE_Y[direction]
            cell = (nx, ny)
            if not self._cell_in_bounds(cell):
                continue
            if self._strict_victim_hazard_level(cell) > 0:
                continue
            if not self._strict_path_lookahead_safe(agent, direction, depth=1):
                continue
            new_dist = abs(tx - nx) + abs(ty - ny)
            progress = current_dist - new_dist
            if progress > best_progress:
                best_progress = progress
                best_dir = direction
        if best_dir is not None:
            nx = x + _MOVE_X[best_dir]
            ny = y + _MOVE_Y[best_dir]
            pocket_blocked = self._pocket_blocked_cells_for_escape(agent, (x, y))
            if (nx, ny) not in pocket_blocked:
                self._last_escape_method = "greedy"
                return best_dir
            best_dir = None

        direction = self._bfs_escape_direction(
            agent, target, avoid_smoke=True, max_depth=self._bfs_escape_max_depth(agent),
        )
        if direction is not None:
            self._last_escape_method = "bfs_smoke_safe"
            return direction

        direction = self._bfs_escape_direction(
            agent, target, avoid_smoke=False, max_depth=self._bfs_escape_max_depth(agent),
        )
        if direction is not None:
            self._last_escape_method = "bfs_fire_only"
            return direction

        return None

    def _hazard_buffer_for_agent(self, agent: Any) -> int:
        model = self._resolve_model(agent)
        if model is None:
            return _VICTIM_HAZARD_BUFFER
        ws = _wind_search_state(model, self.uav_id)
        level = int(ws.get("hazard_buffer_level", 0) or 0)
        if level >= 2:
            return 0
        if level >= 1:
            return 1
        return _VICTIM_HAZARD_BUFFER

    def _victim_edge_blocked_direction(self, agent: Any, direction: int) -> bool:
        model = self._resolve_model(agent)
        pos = getattr(agent, "pos", None)
        if model is None or pos is None:
            return False
        x_max = int(getattr(model, "HEIGHT", getattr(model, "height", 50)) or 50) - 1
        y_max = int(getattr(model, "WIDTH", getattr(model, "width", 50)) or 50) - 1
        x, y = int(pos[0]), int(pos[1])
        nx = x + _MOVE_X[direction]
        ny = y + _MOVE_Y[direction]
        margin = 3
        dist_before = min(x, y, x_max - x, y_max - y)
        dist_after = min(nx, ny, x_max - nx, y_max - ny)
        if dist_before <= margin and dist_after <= dist_before:
            return True
        return False

    def _strict_path_lookahead_safe(
        self, agent: Any, direction: int, depth: int = WIND_PATH_LOOKAHEAD_DEPTH,
    ) -> bool:
        if self._victim_edge_blocked_direction(agent, direction):
            return False
        pos = getattr(agent, "pos", None)
        if pos is None:
            return False
        model = self._resolve_model(agent)
        fire_cells = self._collect_strict_active_fire_cells(model)
        smoke_cells = self._collect_strict_smoke_cells(model)
        buffer = self._hazard_buffer_for_agent(agent)
        x, y = int(pos[0]), int(pos[1])
        for _ in range(max(1, int(depth))):
            x += _MOVE_X[direction]
            y += _MOVE_Y[direction]
            cell = (x, y)
            if not self._cell_in_bounds(cell):
                return False
            if self._strict_victim_hazard_level(cell) > 0:
                return False
            if self._cell_within_victim_hazard_buffer(
                cell,
                fire_cells=fire_cells,
                smoke_cells=smoke_cells,
                buffer=buffer,
            ):
                return False
        return True

    def _victim_near_edge_escape_required(self, agent: Any, model: Any | None) -> bool:
        if model is None or not self._role_is_victim_searcher(self._read_uav_role()):
            return False
        pos = getattr(agent, "pos", None)
        if pos is None:
            return False
        return self._distance_from_boundary(int(pos[0]), int(pos[1]), model) <= 5.0

    def _collect_strict_active_fire_cells(self, model: Any | None) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        if model is None:
            return cells
        schedule = getattr(model, "schedule", None)
        if schedule is None:
            return cells
        import agents as agents_module
        for item in getattr(schedule, "agents", ()) or ():
            if type(item) is not agents_module.Fire:
                continue
            fpos = getattr(item, "pos", None)
            if fpos is None:
                continue
            is_burning = getattr(item, "is_burning", None)
            if callable(is_burning) and is_burning():
                cells.add((int(fpos[0]), int(fpos[1])))
        return cells

    def _collect_strict_smoke_cells(self, model: Any | None) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        if model is None:
            return cells
        visibility = getattr(model, "visibility_model", None)
        if visibility is None:
            return cells
        smoke_cells = getattr(visibility, "smoke_obscured_cells", None)
        if isinstance(smoke_cells, (set, list, tuple)):
            for item in smoke_cells:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    cells.add((int(item[0]), int(item[1])))
        status_map = getattr(
            getattr(visibility, "state", None), "observation_status_map", None
        )
        if isinstance(status_map, dict):
            for key, status in status_map.items():
                label = str(getattr(status, "value", status) or "").strip().lower()
                if label != "smoke_obscured":
                    continue
                if isinstance(key, (list, tuple)) and len(key) >= 2:
                    cells.add((int(key[0]), int(key[1])))
        return cells

    def _min_strict_hazard_distance(
        self,
        cell: tuple[int, int],
        fire_cells: set[tuple[int, int]] | None = None,
        smoke_cells: set[tuple[int, int]] | None = None,
    ) -> float:
        model = self._model
        hazards = set(fire_cells or ())
        hazards.update(smoke_cells or ())
        if not hazards:
            if fire_cells is None:
                hazards.update(self._collect_strict_active_fire_cells(model))
            if smoke_cells is None:
                hazards.update(self._collect_strict_smoke_cells(model))
        if not hazards:
            return 99.0
        cx, cy = cell
        return float(min(abs(cx - hx) + abs(cy - hy) for hx, hy in hazards))

    def _cell_within_victim_hazard_buffer(
        self,
        cell: tuple[int, int],
        buffer: int = _VICTIM_HAZARD_BUFFER,
        fire_cells: set[tuple[int, int]] | None = None,
        smoke_cells: set[tuple[int, int]] | None = None,
    ) -> bool:
        if self._strict_victim_hazard_level(cell) > 0:
            return True
        return self._min_strict_hazard_distance(cell, fire_cells, smoke_cells) <= float(
            max(0, int(buffer))
        )

    def _victim_wind_blocked_direction(self, agent: Any, direction: int) -> bool:
        return self._victim_edge_blocked_direction(agent, direction)

    def _retreat_to_safe_interior_direction(self, agent: Any) -> int | None:
        model = self._resolve_model(agent)
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        fire_cells = self._collect_strict_active_fire_cells(model)
        smoke_cells = self._collect_strict_smoke_cells(model)
        best_dir: int | None = None
        best_score = -float("inf")
        pos = getattr(agent, "pos", None)
        for direction in range(4):
            if self._victim_wind_blocked_direction(agent, direction):
                continue
            cell = self._next_cell_for_direction(agent, direction)
            if cell is None or self._strict_victim_hazard_level(cell) > 0:
                continue
            buffer = self._hazard_buffer_for_agent(agent)
            if self._cell_within_victim_hazard_buffer(
                cell, fire_cells=fire_cells, smoke_cells=smoke_cells, buffer=buffer,
            ):
                continue
            if not self._strict_path_lookahead_safe(agent, direction):
                continue
            score = self._distance_from_boundary(cell[0], cell[1], model) * 14.0
            hazard_dist = self._min_strict_hazard_distance(cell, fire_cells, smoke_cells)
            score += hazard_dist * 8.0
            if pos is not None:
                curr_dist = self._distance_from_boundary(int(pos[0]), int(pos[1]), model)
                next_dist = self._distance_from_boundary(cell[0], cell[1], model)
                if next_dist > curr_dist:
                    score += 18.0
            if score > best_score:
                best_score = score
                best_dir = direction
        if best_dir is not None:
            return best_dir
        for direction in range(4):
            if self._victim_wind_blocked_direction(agent, direction):
                continue
            cell = self._next_cell_for_direction(agent, direction)
            if cell is None or self._strict_victim_hazard_level(cell) > 0:
                continue
            score = self._distance_from_boundary(cell[0], cell[1], model) * 10.0
            score += self._min_strict_hazard_distance(cell, fire_cells, smoke_cells) * 6.0
            if score > best_score:
                best_score = score
                best_dir = direction
        return best_dir

    def _apply_victim_searcher_hazard_gate(
        self, agent: Any, chosen_dir: int, action: str,
    ) -> tuple[int, str]:
        pos = getattr(agent, "pos", None)
        if pos is not None and self._strict_victim_hazard_level((int(pos[0]), int(pos[1]))) > 0:
            retreat = self._retreat_to_safe_interior_direction(agent)
            if retreat is not None:
                return retreat, "victim_search_hazard_retreat"
            return chosen_dir, "victim_search_hazard_retreat"

        if self._victim_wind_blocked_direction(agent, chosen_dir):
            retreat = self._retreat_to_safe_interior_direction(agent)
            if retreat is not None:
                if "retarget_to_interior" in action or "retarget" in action:
                    return retreat, "victim_search_wind_aware_retarget_to_interior"
                return retreat, action

        model = self._resolve_model(agent)
        ws = _wind_search_state(model, self.uav_id) if model is not None else {}
        if int(ws.get("pocket_streak", 0) or 0) >= WIND_POCKET_CAMP_THRESHOLD:
            ws["hazard_buffer_level"] = 2
            ws["force_coverage_escape"] = True

        model = self._resolve_model(agent)
        pos = getattr(agent, "pos", None)
        if pos is not None and model is not None:
            if self._distance_from_boundary(int(pos[0]), int(pos[1]), model) <= 2.0:
                retreat = self._retreat_to_safe_interior_direction(agent)
                if retreat is not None:
                    if "retarget_to_interior" in action or "retarget" in action:
                        return retreat, "victim_search_wind_aware_retarget_to_interior"
                    return retreat, action

        if self._strict_path_lookahead_safe(agent, chosen_dir):
            return chosen_dir, action

        model = self._resolve_model(agent)
        fire_cells = self._collect_strict_active_fire_cells(model)
        smoke_cells = self._collect_strict_smoke_cells(model)
        best_dir = chosen_dir
        best_score = -float("inf")
        for direction in range(4):
            if self._victim_wind_blocked_direction(agent, direction):
                continue
            if not self._strict_path_lookahead_safe(agent, direction):
                continue
            cell = self._next_cell_for_direction(agent, direction)
            if cell is None:
                continue
            score = self._distance_from_boundary(cell[0], cell[1], model) * 10.0
            score += self._min_strict_hazard_distance(cell, fire_cells, smoke_cells) * 5.0
            if direction == chosen_dir:
                score += 0.5
            if score > best_score:
                best_score = score
                best_dir = direction

        if self._strict_path_lookahead_safe(agent, best_dir):
            if best_dir != chosen_dir:
                return best_dir, "victim_search_hazard_retreat"
            return best_dir, action

        retreat = self._retreat_to_safe_interior_direction(agent)
        if retreat is not None:
            return retreat, "victim_search_hazard_retreat"
        return best_dir, "victim_search_hazard_retreat"

    def _sync_wind_search_execution_state(
        self,
        agent: Any,
        decision: PathDecision | None,
        action: str,
    ) -> None:
        role = self._read_uav_role()
        wind_aware = (
            decision is not None
            and str(getattr(decision, "selected_option_id", "") or "")
            == "wind_aware_victim_search"
        )
        if not self._role_is_victim_searcher(role) and not wind_aware:
            return
        model = self._resolve_model(agent)
        if model is None:
            return
        pos = getattr(agent, "pos", None)
        grid_pos = (int(pos[0]), int(pos[1])) if pos is not None else None
        ctx = getattr(decision, "uncertainty_context", None)
        target = None
        if isinstance(ctx, dict):
            raw = ctx.get("target_position") or ctx.get("target_region")
            if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                target = (float(raw[0]), float(raw[1]))
        wind_state = _wind_search_state(model, self.uav_id)
        height = int(getattr(model, "HEIGHT", getattr(model, "height", 50)) or 50)
        width = int(getattr(model, "WIDTH", getattr(model, "width", 50)) or 50)
        step_index = _step_index_from_runtime({"simulation_model": model})
        if grid_pos is not None:
            prior_synced = wind_state.get("last_synced_grid_position")
            if isinstance(prior_synced, (list, tuple)) and len(prior_synced) >= 2:
                prior_cell = (int(prior_synced[0]), int(prior_synced[1]))
                if prior_cell != grid_pos:
                    backtracks = list(wind_state.get("blocked_backtrack_cells") or [])
                    if prior_cell not in backtracks:
                        backtracks.append(prior_cell)
                    wind_state["blocked_backtrack_cells"] = backtracks[-8:]
            wind_state["last_synced_grid_position"] = [grid_pos[0], grid_pos[1]]
        _sync_wind_search_streaks(
            wind_state,
            grid_position=grid_pos,
            action=action,
            target=target,
            x_min=0,
            x_max=height - 1,
            y_min=0,
            y_max=width - 1,
            wind_aware_active=True,
            step_index=step_index,
        )
        wind_state["last_action"] = str(action or "")
        if action == "victim_search_wind_aware_sweep":
            wind_state["force_sweep"] = False
        if "hazard_retreat" in str(action or ""):
            wind_state["force_interior_retarget"] = True
            wind_state["corridor_index"] = 0
            wind_state["corridor_targets"] = []
            if grid_pos is not None:
                _blacklist_target_neighborhood(
                    wind_state,
                    (float(grid_pos[0]), float(grid_pos[1])),
                    _step_index_from_runtime({"simulation_model": model}),
                )

    def _safe_search_target(
        self,
        agent: Any,
        target: tuple[float, float] | None,
    ) -> tuple[float, float] | None:
        if target is None:
            return None
        normalized = self._normalize_cell_pos(target)
        if normalized is None:
            return target
        cx, cy = normalized
        if self._cell_danger_level((cx, cy)) == 0:
            return (float(cx), float(cy))

        safe_candidates: list[tuple[float, float]] = []
        for direction in range(4):
            nx = cx + _MOVE_X[direction]
            ny = cy + _MOVE_Y[direction]
            cell = (nx, ny)
            if self._cell_danger_level(cell) == 0:
                safe_candidates.append((float(nx), float(ny)))

        model = self._resolve_model(agent)
        bounds = (
            self._uav_sector_bounds(model)
            if self._sector_filtering_active(model)
            else None
        )
        if not safe_candidates:
            for radius in range(1, 13):
                ring: list[tuple[int, int]] = []
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        if max(abs(dx), abs(dy)) != radius:
                            continue
                        cell = (cx + dx, cy + dy)
                        if self._cell_danger_level(cell) != 0:
                            continue
                        if bounds is not None and not self._position_in_sector(
                            (float(cell[0]), float(cell[1])), bounds
                        ):
                            continue
                        ring.append(cell)
                if ring:
                    pos = getattr(agent, "pos", None)
                    if pos is not None:
                        ring.sort(
                            key=lambda cell: abs(cell[0] - int(pos[0]))
                            + abs(cell[1] - int(pos[1]))
                        )
                    safe_candidates.extend(
                        (float(cell[0]), float(cell[1])) for cell in ring
                    )
                    break

        if safe_candidates:
            nearest = self._nearest_target(safe_candidates)
            if nearest is not None:
                return nearest
            return safe_candidates[0]
        return (float(cx), float(cy))

    def _nearest_fire_perimeter_target(
        self,
        agent: Any,
        fire_targets: list[tuple[float, float]],
    ) -> tuple[float, float] | None:
        fire_cells: set[tuple[int, int]] = set()
        for target in fire_targets:
            normalized = self._normalize_cell_pos(target)
            if normalized is not None:
                fire_cells.add(normalized)
        perimeter: list[tuple[float, float]] = []
        seen: set[tuple[int, int]] = set()
        for fx, fy in fire_cells:
            for direction in range(4):
                nx = fx + _MOVE_X[direction]
                ny = fy + _MOVE_Y[direction]
                cell = (nx, ny)
                if cell in seen:
                    continue
                seen.add(cell)
                if not self._cell_in_bounds(cell):
                    continue
                if self._fire_tracker_cell_disqualified(cell):
                    continue
                perimeter.append((float(nx), float(ny)))
        if not perimeter:
            return None

        model = self._resolve_model(agent)
        pool = self._filter_pool_for_fire_tracker_flank(perimeter, model)
        return self._pick_best_fire_tracker_standoff_target(agent, pool, fire_cells)

    def _fire_tracker_flank_bounds(self, model: Any | None = None) -> dict[str, int] | None:
        resolved = model or self._model
        if resolved is None:
            return None
        if str(self._read_uav_role() or "").strip().lower() != "fire_tracker":
            return None
        assignments = getattr(resolved, "_uav_sector_assignments", None)
        if not isinstance(assignments, dict):
            return None
        return assignments.get(str(self.uav_id))

    def _filter_pool_for_fire_tracker_flank(
        self,
        pool: list[tuple[float, float]],
        model: Any | None = None,
    ) -> list[tuple[float, float]]:
        bounds = self._fire_tracker_flank_bounds(model)
        if bounds is None:
            return pool
        return [
            target for target in pool if self._position_in_sector(target, bounds)
        ]

    def _tracker_in_flank_band(self, agent: Any, model: Any | None = None) -> bool:
        pos = getattr(agent, "pos", None)
        bounds = self._fire_tracker_flank_bounds(model)
        if pos is None or bounds is None:
            return True
        return self._position_in_sector((float(pos[0]), float(pos[1])), bounds)

    @staticmethod
    def _nearest_active_fire_distance(
        cell: tuple[int, int],
        fire_cells: set[tuple[int, int]],
    ) -> float:
        cx, cy = cell
        return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fire_cells)

    def _score_fire_tracker_standoff_distance(
        self, nearest_fire: float, *, standoff_min: int | None = None,
    ) -> float:
        eff_min = STANDOFF_MIN if standoff_min is None else int(standoff_min)
        dist = float(nearest_fire)
        if dist < eff_min:
            return (
                _FIRE_TRACKER_HARD_HAZARD_SCORE
                + (eff_min - dist) * STANDOFF_TOO_CLOSE_PENALTY
            )
        if dist <= STANDOFF_MAX:
            ideal = (eff_min + STANDOFF_MAX) / 2.0
            return STANDOFF_IN_BAND_BONUS - abs(dist - ideal) * 8.0
        return (
            STANDOFF_IN_BAND_BONUS * 0.35
            - (dist - STANDOFF_MAX) * STANDOFF_TOO_FAR_PENALTY
        )

    def _score_fire_tracker_standoff_target(
        self,
        target: tuple[float, float],
        fire_cells: set[tuple[int, int]],
        agent: Any | None = None,
    ) -> float:
        cell = (int(round(target[0])), int(round(target[1])))
        hazard_cells = self._collect_tracker_hazard_cells(
            self._resolve_model(agent) if agent is not None else self._model
        )
        if self._fire_tracker_cell_disqualified(cell, hazard_cells=hazard_cells):
            return _FIRE_TRACKER_HARD_HAZARD_SCORE
        nearest = self._nearest_active_fire_distance(cell, fire_cells)
        model = self._resolve_model(agent) if agent is not None else self._model
        eff_min = self._effective_standoff_min(model)
        score = self._score_fire_tracker_standoff_distance(
            nearest, standoff_min=eff_min,
        )
        hazard_dist = self._min_tracker_hazard_distance(cell, hazard_cells)
        score += hazard_dist * 12.0
        if self._cell_in_smoke_envelope(cell, hazard_cells=hazard_cells, clearance=2):
            score -= 80.0
        model = self._resolve_model(agent) if agent is not None else self._model
        bounds = self._fire_tracker_flank_bounds(model)
        if bounds is not None and not self._position_in_sector(
            (float(cell[0]), float(cell[1])), bounds
        ):
            score -= 500.0
        if agent is not None and bounds is not None:
            pos = getattr(agent, "pos", None)
            if pos is not None and not self._position_in_sector(
                (float(pos[0]), float(pos[1])), bounds
            ):
                score += 40.0
        if agent is not None:
            pos = getattr(agent, "pos", None)
            if pos is not None:
                ax, ay = float(pos[0]), float(pos[1])
                score -= (abs(ax - target[0]) + abs(ay - target[1])) * 0.02
        return score

    def _collect_close_standoff_candidates(
        self,
        fire_cells: set[tuple[int, int]],
        *,
        model: Any | None = None,
    ) -> list[tuple[float, float]]:
        eff_min = self._effective_standoff_min(model)
        eff_max = self._effective_standoff_max(model)
        candidates: list[tuple[float, float]] = []
        seen: set[tuple[int, int]] = set()
        for fx, fy in fire_cells:
            for direction in range(4):
                for step in range(eff_min, eff_max + 2):
                    nx = fx + _MOVE_X[direction] * step
                    ny = fy + _MOVE_Y[direction] * step
                    cell = (nx, ny)
                    if cell in seen or not self._cell_in_bounds(cell):
                        continue
                    seen.add(cell)
                    if self._fire_tracker_cell_disqualified(cell):
                        continue
                    candidates.append((float(nx), float(ny)))
        return candidates

    def _collect_flank_band_standoff_candidates(
        self,
        agent: Any,
        fire_cells: set[tuple[int, int]],
        *,
        model: Any | None = None,
    ) -> list[tuple[float, float]]:
        resolved = model or self._resolve_model(agent)
        bounds = self._fire_tracker_flank_bounds(resolved)
        if bounds is None or not fire_cells:
            return self._collect_close_standoff_candidates(
                fire_cells, model=resolved,
            )

        eff_min = self._effective_standoff_min(resolved)
        eff_max = self._effective_standoff_max(resolved)
        in_band_fire = {
            cell
            for cell in fire_cells
            if self._position_in_sector((float(cell[0]), float(cell[1])), bounds)
        }
        source_fires = in_band_fire if in_band_fire else fire_cells
        candidates: list[tuple[float, float]] = []
        seen: set[tuple[int, int]] = set()
        for fx, fy in source_fires:
            for direction in range(4):
                for step in range(eff_min, eff_max + 2):
                    nx = fx + _MOVE_X[direction] * step
                    ny = fy + _MOVE_Y[direction] * step
                    cell = (nx, ny)
                    if cell in seen or not self._cell_in_bounds(cell):
                        continue
                    if not self._position_in_sector((float(nx), float(ny)), bounds):
                        continue
                    seen.add(cell)
                    if self._fire_tracker_cell_disqualified(cell, model=resolved):
                        continue
                    candidates.append((float(nx), float(ny)))
        if candidates:
            return candidates

        for x in range(bounds["x_min"], bounds["x_max"] + 1):
            for y in range(bounds["y_min"], bounds["y_max"] + 1):
                cell = (x, y)
                if cell in seen:
                    continue
                if self._fire_tracker_cell_disqualified(cell, model=resolved):
                    continue
                nearest = self._nearest_active_fire_distance(cell, fire_cells)
                if eff_min <= nearest <= eff_max + 1:
                    seen.add(cell)
                    candidates.append((float(x), float(y)))
        return candidates

    def _nearest_flank_band_target(
        self,
        agent: Any,
        fire_cells: set[tuple[int, int]],
        *,
        model: Any | None = None,
    ) -> tuple[float, float] | None:
        resolved = model or self._resolve_model(agent)
        bounds = self._fire_tracker_flank_bounds(resolved)
        pos = getattr(agent, "pos", None)
        if bounds is None or pos is None:
            return None
        standoff = self._collect_flank_band_standoff_candidates(
            agent, fire_cells, model=resolved,
        )
        if standoff:
            ax, ay = float(pos[0]), float(pos[1])
            return min(
                standoff,
                key=lambda target: abs(target[0] - ax) + abs(target[1] - ay),
            )
        best_target: tuple[float, float] | None = None
        best_distance = float("inf")
        ax, ay = float(pos[0]), float(pos[1])
        for x in range(bounds["x_min"], bounds["x_max"] + 1):
            for y in range(bounds["y_min"], bounds["y_max"] + 1):
                cell = (x, y)
                if self._fire_tracker_cell_disqualified(cell, model=resolved):
                    continue
                distance = abs(float(x) - ax) + abs(float(y) - ay)
                if distance < best_distance:
                    best_distance = distance
                    best_target = (float(x), float(y))
        return best_target

    def _pick_best_fire_tracker_standoff_target(
        self,
        agent: Any,
        pool: list[tuple[float, float]],
        fire_cells: set[tuple[int, int]],
    ) -> tuple[float, float] | None:
        if not pool:
            return None
        best_target: tuple[float, float] | None = None
        best_score = -float("inf")
        for target in pool:
            score = self._score_fire_tracker_standoff_target(target, fire_cells, agent)
            if score > best_score:
                best_score = score
                best_target = target
        return best_target

    def _standoff_fire_cells(
        self,
        fire_targets: list[tuple[float, float]] | None = None,
    ) -> set[tuple[int, int]]:
        active = self._collect_active_fire_cells()
        if active:
            return set(active)
        if fire_targets:
            mapped = self._fire_cells_from_target_positions(fire_targets)
            if mapped:
                return mapped
        return set()

    def _fire_safe_standoff_target(
        self,
        agent: Any,
        fire_targets: list[tuple[float, float]],
    ) -> tuple[float, float] | None:
        fire_cells: set[tuple[int, int]] = set()
        for target in fire_targets:
            normalized = self._normalize_cell_pos(target)
            if normalized is not None:
                fire_cells.add(normalized)
        standoff_fire = self._standoff_fire_cells(fire_targets)
        if standoff_fire:
            fire_cells = standoff_fire
        candidates = self._collect_flank_band_standoff_candidates(
            agent, fire_cells, model=self._resolve_model(agent),
        )
        if not candidates:
            return self._fire_tracker_outward_escape_target(
                agent, fire_targets, fire_cells
            )

        model = self._resolve_model(agent)
        picked = self._pick_best_fire_tracker_standoff_target(agent, candidates, fire_cells)
        if picked is not None:
            return picked
        return self._fire_tracker_outward_escape_target(agent, fire_targets, fire_cells)

    def _fire_tracker_far_from_fire(
        self,
        agent: Any,
        fire_cells: set[tuple[int, int]],
        max_dist: int | None = None,
    ) -> bool:
        pos = getattr(agent, "pos", None)
        if pos is None or not fire_cells:
            return False
        ax, ay = int(pos[0]), int(pos[1])
        nearest = min(abs(ax - fx) + abs(ay - fy) for fx, fy in fire_cells)
        limit = STANDOFF_MAX + 2 if max_dist is None else int(max_dist)
        return nearest > limit

    def _try_resolve_fire_role_direction(
        self,
        agent: Any,
        decision: PathDecision,
        action: str,
    ) -> tuple[int, str] | None:
        fire_targets = self._fire_positions_from_runtime()
        fire_cells = self._standoff_fire_cells(fire_targets)

        model = self._resolve_model(agent)
        eff_min = self._effective_standoff_min(model)
        pos = getattr(agent, "pos", None)
        if pos is not None and fire_cells:
            ax, ay = int(pos[0]), int(pos[1])
            cur_dist = min(
                abs(ax - fx) + abs(ay - fy) for fx, fy in fire_cells
            )
            if (
                cur_dist < eff_min
                or self._cell_in_smoke_envelope((ax, ay), clearance=1)
                or self._cell_has_burning_fire((ax, ay))
            ):
                escape = self._fire_tracker_outward_escape_target(
                    agent, fire_targets, fire_cells
                )
                if escape is not None:
                    return (
                        self._choose_best_direction_fire(
                            agent,
                            escape,
                            fire_cells=fire_cells,
                            escape_mode=True,
                        ),
                        "fire_smoke_escape",
                    )

        if self._fire_tracker_position_unsafe(agent, fire_cells):
            escape = self._fire_tracker_outward_escape_target(
                agent, fire_targets, fire_cells
            )
            if escape is not None:
                return (
                    self._choose_best_direction_fire(
                        agent,
                        escape,
                        fire_cells=fire_cells,
                        escape_mode=True,
                    ),
                    "fire_smoke_escape",
                )

        model = self._resolve_model(agent)
        if fire_cells and not self._tracker_in_flank_band(agent, model):
            standoff_targets = fire_targets
            if not standoff_targets:
                standoff_targets = [
                    (float(fx), float(fy)) for fx, fy in sorted(fire_cells)
                ]
            relocate = self._fire_safe_standoff_target(agent, standoff_targets)
            if relocate is None:
                relocate = self._nearest_flank_band_target(
                    agent, fire_cells, model=model,
                )
            if relocate is not None:
                return (
                    self._choose_best_direction_fire(
                        agent,
                        relocate,
                        fire_cells=fire_cells,
                    ),
                    "fire_flank_relocate",
                )

        if self._fire_tracker_hold_needs_escape(agent):
            escape_dir = self._fire_tracker_hold_escape_direction(agent)
            if escape_dir is not None:
                return escape_dir, "hold_escape"

        eff_min = self._effective_standoff_min(model)
        if fire_cells and self._fire_tracker_at_safe_standoff(agent, fire_cells):
            pos = getattr(agent, "pos", None)
            cur_dist = None
            if pos is not None:
                ax, ay = int(pos[0]), int(pos[1])
                cur_dist = min(
                    abs(ax - fx) + abs(ay - fy) for fx, fy in fire_cells
                )
            in_band = self._tracker_in_flank_band(agent, model)
            if cur_dist is not None and cur_dist >= eff_min and in_band:
                if not self._fire_tracker_far_from_fire(agent, fire_cells):
                    lateral = self._fire_tracker_lateral_hold_target(
                        agent, fire_cells
                    )
                    hold_target = lateral
                    if hold_target is None and pos is not None:
                        hold_target = (float(pos[0]), float(pos[1]))
                    if hold_target is not None:
                        direction = self._choose_best_direction_fire(
                            agent,
                            hold_target,
                            fire_cells=fire_cells,
                            hold_mode=True,
                        )
                        return direction, "fire_flank_hold"

        target = None
        label = "fire_safe_standoff"
        if fire_targets:
            target = self._fire_safe_standoff_target(agent, fire_targets)

        if target is None:
            target = self._nearest_smoke_free_fire_perimeter_target(
                agent, fire_targets
            )
            if target is not None:
                label = "computed_from_fire_perimeter"

        planner_target = self._flank_target_from_decision(decision)
        if target is None and planner_target is not None:
            planned_cell = (
                int(round(planner_target[0])),
                int(round(planner_target[1])),
            )
            if fire_cells:
                planned_dist = self._nearest_active_fire_distance(
                    planned_cell, fire_cells
                )
                if STANDOFF_MIN <= planned_dist <= STANDOFF_MAX + 1:
                    target = planner_target
                    label = "fire_flank_standoff"
            elif not self._fire_tracker_cell_disqualified(planned_cell):
                target = planner_target
                label = "fire_flank_standoff"

        if target is None:
            parsed = self._target_from_decision(decision)
            if parsed is not None:
                cell = (int(round(parsed[0])), int(round(parsed[1])))
                if not self._fire_tracker_cell_disqualified(cell):
                    target = parsed
                    label = "computed_from_target"

        if fire_cells and fire_targets:
            pos = getattr(agent, "pos", None)
            if pos is not None:
                ax, ay = int(pos[0]), int(pos[1])
                uav_fire_dist = min(
                    abs(ax - fx) + abs(ay - fy) for fx, fy in fire_cells
                )
                if uav_fire_dist > STANDOFF_MAX + 1:
                    closer = self._fire_safe_standoff_target(agent, fire_targets)
                    if closer is not None:
                        target = closer
                        label = "fire_safe_standoff"

        if target is not None and fire_cells:
            target_cell = (int(round(target[0])), int(round(target[1])))
            nearest = self._nearest_active_fire_distance(target_cell, fire_cells)
            if nearest > STANDOFF_MAX + 1 and fire_targets:
                closer = self._fire_safe_standoff_target(agent, fire_targets)
                if closer is not None:
                    target = closer
                    label = "fire_safe_standoff"

        if target is None:
            return None

        bounds = self._fire_tracker_flank_bounds(model)
        if bounds is not None and not self._position_in_sector(
            (float(target[0]), float(target[1])), bounds
        ):
            standoff_targets = fire_targets
            if not standoff_targets and fire_cells:
                standoff_targets = [
                    (float(fx), float(fy)) for fx, fy in sorted(fire_cells)
                ]
            flank_target = None
            if standoff_targets:
                flank_target = self._fire_safe_standoff_target(
                    agent, standoff_targets,
                )
            if flank_target is None and fire_cells:
                flank_target = self._nearest_flank_band_target(
                    agent, fire_cells, model=model,
                )
            if flank_target is not None:
                target = flank_target
                label = "fire_flank_relocate"

        if action == "explore_unknown_region" and fire_targets:
            standoff = self._fire_safe_standoff_target(agent, fire_targets)
            if standoff is not None:
                target = standoff
            return (
                self._choose_best_direction_fire(
                    agent, target, fire_cells=fire_cells
                ),
                "explore_unknown_region",
            )

        return (
            self._choose_best_direction_fire(agent, target, fire_cells=fire_cells),
            label,
        )

    def _flank_target_from_decision(
        self,
        decision: PathDecision,
    ) -> tuple[float, float] | None:
        ctx = getattr(decision, "uncertainty_context", None)
        if not isinstance(ctx, dict):
            return None
        flank_hold = bool(ctx.get("flank_standoff_hold"))
        if ctx.get("flank_hold_target") is not None or flank_hold:
            keys = (
                "flank_hold_target",
                "target_position",
                "target_region",
                "target_location",
            )
        else:
            keys = ("target_position", "target_region", "target_location")
        for key in keys:
            parsed = self._normalize_target(ctx.get(key))
            if parsed is None:
                continue
            cell = (int(round(parsed[0])), int(round(parsed[1])))
            if self._fire_tracker_cell_disqualified(cell):
                continue
            if key == "flank_hold_target" or flank_hold:
                return parsed
            return parsed
        return None

    def _effective_standoff_min(self, model: Any | None = None) -> int:
        cache = self._get_tracker_hazard_cache(model)
        hazard_cells = cache["hazard_cells"]
        burning_cells = cache["burning_cells"]
        fire_count = len(hazard_cells & burning_cells)
        if len(hazard_cells) >= STANDOFF_ENVELOPE_EXPAND_FIRE or fire_count >= 12:
            return max(STANDOFF_MIN + 1, 3)
        if len(hazard_cells) >= STANDOFF_ENVELOPE_EXPAND_SMOKE or fire_count >= 6:
            return STANDOFF_MIN + 1
        return STANDOFF_MIN

    def _effective_standoff_max(self, model: Any | None = None) -> int:
        eff_min = self._effective_standoff_min(model)
        return max(STANDOFF_MAX, eff_min + 1, STANDOFF_MAX_ESCAPE // 2)

    @staticmethod
    def _tracker_cache_step_key(model: Any | None) -> int:
        if model is None:
            return -1
        counter = getattr(model, "evaluation_timesteps_counter", None)
        if counter is not None:
            return int(counter)
        schedule = getattr(model, "schedule", None)
        if schedule is not None:
            return int(getattr(schedule, "steps", 0) or 0)
        return -1

    def _collect_smoke_hazard_status_cells(self, model: Any | None) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        if model is None:
            return cells
        visibility = getattr(model, "visibility_model", None)
        if visibility is None:
            return cells
        status_map = getattr(
            getattr(visibility, "state", None), "observation_status_map", None
        )
        if not isinstance(status_map, dict):
            return cells
        for key, status in status_map.items():
            label = str(getattr(status, "value", status) or "")
            if not self._smoke_label_is_hazard(label):
                continue
            if isinstance(key, (list, tuple)) and len(key) >= 2:
                cells.add((int(key[0]), int(key[1])))
            elif isinstance(key, tuple) and len(key) >= 2:
                cells.add((int(key[0]), int(key[1])))
        return cells

    def _build_tracker_hazard_cache(self, model: Any | None) -> dict[str, Any]:
        """Build tracker hazard lookup once per model step (same semantics as before)."""
        resolved = model
        if resolved is None:
            return _empty_tracker_hazard_cache()

        burning_cells: set[tuple[int, int]] = set()
        active_smoke_cells: set[tuple[int, int]] = set()
        schedule = getattr(resolved, "schedule", None)
        if schedule is not None:
            for agent in getattr(schedule, "agents", ()) or ():
                if type(agent).__name__ != "Fire":
                    continue
                pos = getattr(agent, "pos", None)
                if pos is None:
                    continue
                cell = (int(pos[0]), int(pos[1]))
                is_burning = getattr(agent, "is_burning", None)
                if callable(is_burning) and is_burning():
                    burning_cells.add(cell)
                elif getattr(agent, "burning", False):
                    burning_cells.add(cell)
                smoke = getattr(agent, "smoke", None)
                if smoke is None:
                    continue
                is_active = getattr(smoke, "is_smoke_active", None)
                if callable(is_active) and is_active():
                    active_smoke_cells.add(cell)
                elif getattr(smoke, "smoke", False):
                    active_smoke_cells.add(cell)

        smoke_obscured_cells = set(active_smoke_cells)
        smoke_obscured_cells.update(self._collect_smoke_hazard_status_cells(resolved))

        hazards: set[tuple[int, int]] = set()
        hazards.update(self._collect_strict_active_fire_cells(resolved))
        hazards.update(self._collect_strict_smoke_cells(resolved))
        if schedule is not None:
            for agent in getattr(schedule, "agents", ()) or ():
                if type(agent).__name__ != "Fire":
                    continue
                pos = getattr(agent, "pos", None)
                if pos is None:
                    continue
                cell = (int(pos[0]), int(pos[1]))
                if cell in burning_cells:
                    hazards.add(cell)
                if cell in active_smoke_cells:
                    hazards.add(cell)

        imminent: set[tuple[int, int]] = set()
        for hx, hy in list(hazards):
            for direction in range(4):
                nx = hx + _MOVE_X[direction]
                ny = hy + _MOVE_Y[direction]
                neighbor = (nx, ny)
                if not self._cell_in_bounds(neighbor):
                    continue
                if neighbor in burning_cells:
                    continue
                if (
                    neighbor in active_smoke_cells
                    or neighbor in smoke_obscured_cells
                ):
                    imminent.add(neighbor)
                elif neighbor not in hazards:
                    imminent.add(neighbor)
        hazards.update(imminent)

        return {
            "step": self._tracker_cache_step_key(resolved),
            "hazard_cells": hazards,
            "burning_cells": burning_cells,
            "active_smoke_cells": active_smoke_cells,
            "smoke_obscured_cells": smoke_obscured_cells,
        }

    def _get_tracker_hazard_cache(self, model: Any | None = None) -> dict[str, Any]:
        resolved = model or self._model
        if resolved is None:
            return _empty_tracker_hazard_cache()
        step = self._tracker_cache_step_key(resolved)
        stored = getattr(resolved, _TRACKER_HAZARD_CACHE_ATTR, None)
        if (
            isinstance(stored, dict)
            and stored.get("step") == step
            and "hazard_cells" in stored
        ):
            return stored
        entry = self._build_tracker_hazard_cache(resolved)
        setattr(resolved, _TRACKER_HAZARD_CACHE_ATTR, entry)
        return entry

    def _collect_tracker_hazard_cells(
        self, model: Any | None = None,
    ) -> set[tuple[int, int]]:
        """Burning fire + active/obscured smoke used for envelope clearance."""
        cache = self._get_tracker_hazard_cache(model)
        return cache["hazard_cells"]

    def _min_tracker_hazard_distance(
        self,
        cell: tuple[int, int],
        hazard_cells: set[tuple[int, int]] | None = None,
        *,
        model: Any | None = None,
    ) -> float:
        if hazard_cells is None:
            hazard_cells = self._get_tracker_hazard_cache(model)["hazard_cells"]
        if not hazard_cells:
            return 99.0
        cx, cy = cell
        return float(min(abs(cx - hx) + abs(cy - hy) for hx, hy in hazard_cells))

    def _cell_in_smoke_envelope(
        self,
        cell: tuple[int, int],
        *,
        hazard_cells: set[tuple[int, int]] | None = None,
        clearance: int | None = None,
    ) -> bool:
        buffer = (
            STANDOFF_SMOKE_CLEARANCE
            if clearance is None
            else max(0, int(clearance))
        )
        return self._min_tracker_hazard_distance(cell, hazard_cells) <= float(buffer)

    def _fire_tracker_position_unsafe(
        self,
        agent: Any,
        fire_cells: set[tuple[int, int]] | None = None,
    ) -> bool:
        pos = getattr(agent, "pos", None)
        if pos is None:
            return False
        cell = (int(pos[0]), int(pos[1]))
        model = self._resolve_model(agent)
        cache = self._get_tracker_hazard_cache(model)
        if cell in cache["burning_cells"]:
            return True
        if cell in cache["active_smoke_cells"] or cell in cache["smoke_obscured_cells"]:
            return True
        if self._cell_in_smoke_envelope(
            cell,
            hazard_cells=cache["hazard_cells"],
            clearance=1,
        ):
            return True
        if fire_cells and self._cell_adjacent_to_fire_cells(cell, fire_cells):
            return True
        return False

    def _collect_escape_standoff_candidates(
        self,
        fire_cells: set[tuple[int, int]],
        *,
        max_dist: int | None = None,
    ) -> list[tuple[float, float]]:
        limit = int(max_dist if max_dist is not None else STANDOFF_MAX_ESCAPE)
        limit = max(STANDOFF_MAX + 1, limit)
        candidates: list[tuple[float, float]] = []
        seen: set[tuple[int, int]] = set()
        for fx, fy in fire_cells:
            for direction in range(4):
                for step in range(STANDOFF_MIN, limit + 1):
                    nx = fx + _MOVE_X[direction] * step
                    ny = fy + _MOVE_Y[direction] * step
                    cell = (nx, ny)
                    if cell in seen or not self._cell_in_bounds(cell):
                        continue
                    seen.add(cell)
                    candidates.append((float(nx), float(ny)))
        return candidates

    def _fire_tracker_outward_escape_target(
        self,
        agent: Any,
        fire_targets: list[tuple[float, float]] | None,
        fire_cells: set[tuple[int, int]],
    ) -> tuple[float, float] | None:
        if not fire_cells:
            return None
        model = self._resolve_model(agent)
        hazard_cells = self._collect_tracker_hazard_cells(model)
        candidates = self._collect_escape_standoff_candidates(
            fire_cells, max_dist=STANDOFF_MAX_ESCAPE
        )
        if not candidates:
            return None
        pool = self._filter_pool_for_fire_tracker_flank(candidates, model)
        pos = getattr(agent, "pos", None)
        ax = ay = 0.0
        if pos is not None:
            ax, ay = float(pos[0]), float(pos[1])
        best_target: tuple[float, float] | None = None
        best_score = -float("inf")
        for target in pool:
            cell = (int(round(target[0])), int(round(target[1])))
            if self._fire_tracker_cell_disqualified(cell, hazard_cells=hazard_cells):
                continue
            hazard_dist = self._min_tracker_hazard_distance(cell, hazard_cells)
            if hazard_dist < 1.0:
                continue
            fire_dist = self._nearest_active_fire_distance(cell, fire_cells)
            score = hazard_dist * 25.0
            if STANDOFF_MIN <= fire_dist <= STANDOFF_MAX_ESCAPE:
                score += 40.0 - abs(fire_dist - STANDOFF_IDEAL) * 3.0
            score -= (abs(ax - target[0]) + abs(ay - target[1])) * 0.08
            if score > best_score:
                best_score = score
                best_target = target
        if best_target is not None:
            return best_target
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        ax, ay = int(pos[0]), int(pos[1])
        best_dir_score = -float("inf")
        best_escape: tuple[float, float] | None = None
        for direction in range(4):
            nx = ax + _MOVE_X[direction]
            ny = ay + _MOVE_Y[direction]
            cell = (nx, ny)
            if not self._cell_in_bounds(cell):
                continue
            if self._fire_tracker_cell_disqualified(cell, hazard_cells=hazard_cells):
                continue
            hazard_dist = self._min_tracker_hazard_distance(cell, hazard_cells)
            if hazard_dist < 1.0:
                continue
            bounds = self._fire_tracker_flank_bounds(model)
            if bounds is not None and not self._position_in_sector(
                (float(nx), float(ny)), bounds
            ):
                continue
            score = hazard_dist * 30.0
            if score > best_dir_score:
                best_dir_score = score
                best_escape = (float(nx), float(ny))
        return best_escape

    def _fire_cells_from_target_positions(
        self,
        fire_targets: list[tuple[float, float]],
    ) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for target in fire_targets:
            normalized = self._normalize_cell_pos(target)
            if normalized is not None:
                cells.add(normalized)
        return cells

    def _fire_tracker_cell_disqualified(
        self,
        cell: tuple[int, int],
        *,
        hazard_cells: set[tuple[int, int]] | None = None,
        model: Any | None = None,
    ) -> bool:
        if not self._cell_in_bounds(cell):
            return True
        cache = self._get_tracker_hazard_cache(model or self._model)
        if cell in cache["burning_cells"]:
            return True
        if cell in cache["smoke_obscured_cells"]:
            return True
        if cell in cache["active_smoke_cells"]:
            return True
        if self._cell_high_fire(cell):
            return True
        if hazard_cells is None:
            hazard_cells = cache["hazard_cells"]
        if self._cell_in_smoke_envelope(
            cell, hazard_cells=hazard_cells, clearance=1,
        ):
            return True
        return False

    @staticmethod
    def _cell_adjacent_to_fire_cells(
        cell: tuple[int, int],
        fire_cells: set[tuple[int, int]],
    ) -> bool:
        cx, cy = cell
        for fx, fy in fire_cells:
            if abs(cx - fx) + abs(cy - fy) <= 1:
                return True
        return False

    def _fire_tracker_at_safe_standoff(
        self,
        agent: Any,
        fire_cells: set[tuple[int, int]],
    ) -> bool:
        pos = getattr(agent, "pos", None)
        if pos is None or not fire_cells:
            return False
        cx, cy = int(pos[0]), int(pos[1])
        cell = (cx, cy)
        if self._fire_tracker_cell_disqualified(cell):
            return False
        if self._cell_in_smoke_envelope(cell, clearance=1):
            return False
        if self._cell_adjacent_to_fire_cells(cell, fire_cells):
            return False
        eff_min = self._effective_standoff_min(self._resolve_model(agent))
        nearest = min(abs(cx - fx) + abs(cy - fy) for fx, fy in fire_cells)
        return eff_min <= nearest <= STANDOFF_MAX + 1

    def _fire_tracker_lateral_hold_target(
        self,
        agent: Any,
        fire_cells: set[tuple[int, int]],
    ) -> tuple[float, float] | None:
        pos = getattr(agent, "pos", None)
        if pos is None or not fire_cells:
            return None
        ax, ay = int(pos[0]), int(pos[1])
        current_dist = min(abs(ax - fx) + abs(ay - fy) for fx, fy in fire_cells)
        centroid_x = sum(fx for fx, _ in fire_cells) / float(len(fire_cells))
        centroid_y = sum(fy for _, fy in fire_cells) / float(len(fire_cells))
        radial_x = ax - centroid_x
        radial_y = ay - centroid_y
        best_score = -float("inf")
        best_target: tuple[float, float] | None = None
        model = self._resolve_model(agent)
        bounds = self._fire_tracker_flank_bounds(model)
        for direction in range(4):
            nx = ax + _MOVE_X[direction]
            ny = ay + _MOVE_Y[direction]
            cell = (nx, ny)
            if not self._cell_in_bounds(cell):
                continue
            if bounds is not None and not self._position_in_sector(
                (float(nx), float(ny)), bounds
            ):
                continue
            if self._fire_tracker_cell_disqualified(cell):
                continue
            if self._cell_adjacent_to_fire_cells(cell, fire_cells):
                continue
            new_dist = min(abs(nx - fx) + abs(ny - fy) for fx, fy in fire_cells)
            if new_dist < STANDOFF_MIN:
                continue
            if new_dist < current_dist - 1:
                continue
            step_dx = _MOVE_X[direction]
            step_dy = _MOVE_Y[direction]
            radial_dot = abs(step_dx * radial_x + step_dy * radial_y)
            score = 8.0 - radial_dot * 0.35
            score -= abs(new_dist - current_dist) * 2.5
            if score > best_score:
                best_score = score
                best_target = (float(nx), float(ny))
        return best_target

    def _nearest_smoke_free_fire_perimeter_target(
        self,
        agent: Any,
        fire_targets: list[tuple[float, float]],
    ) -> tuple[float, float] | None:
        fire_cells = self._fire_cells_from_target_positions(fire_targets)
        perimeter: list[tuple[float, float]] = []
        seen: set[tuple[int, int]] = set()
        for fx, fy in fire_cells:
            for direction in range(4):
                nx = fx + _MOVE_X[direction]
                ny = fy + _MOVE_Y[direction]
                cell = (nx, ny)
                if cell in seen:
                    continue
                seen.add(cell)
                if not self._perimeter_cell_acceptable(cell):
                    continue
                perimeter.append((float(nx), float(ny)))
        if not perimeter:
            return None

        model = self._resolve_model(agent)
        pool = self._filter_pool_for_fire_tracker_flank(perimeter, model)
        return self._pick_best_fire_tracker_standoff_target(agent, pool, fire_cells)

    def _fire_tracker_hold_direction(self, agent: Any) -> int:
        pos = getattr(agent, "pos", None)
        if pos is None:
            return 0
        best_dir = int(getattr(agent, "selected_dir", 0) or 0) % 4
        best_score = -float("inf")
        for direction in range(4):
            if not self._direction_in_bounds(agent, direction):
                continue
            cell = self._next_cell_for_direction(agent, direction)
            if cell is None:
                continue
            if self._cell_has_burning_fire(cell):
                continue
            score = 0.0
            if self._cell_smoke_obscured(cell):
                score -= 500.0
            if self._cell_high_fire(cell):
                score -= 300.0
            if score > best_score:
                best_score = score
                best_dir = direction
        return best_dir

    def _choose_best_direction_fire(
        self,
        agent: Any,
        target: tuple[float, float],
        *,
        fire_cells: set[tuple[int, int]] | None = None,
        hold_mode: bool = False,
        escape_mode: bool = False,
    ) -> int:
        if fire_cells is None:
            fire_cells = self._collect_active_fire_cells()
        model = self._resolve_model(agent)
        hazard_cells = self._collect_tracker_hazard_cells(model)
        preferred = self._direction_toward(agent, target)
        candidates = (
            preferred,
            (preferred + 1) % 4,
            (preferred + 3) % 4,
            (preferred + 2) % 4,
        )
        ax, ay = float(agent.pos[0]), float(agent.pos[1])
        tx, ty = float(target[0]), float(target[1])
        current_distance = abs(ax - tx) + abs(ay - ty)
        cur_fire_dist: float | None = None
        if fire_cells:
            cur_fire_dist = min(
                abs(ax - fx) + abs(ay - fy) for fx, fy in fire_cells
            )
        cur_hazard_dist: float | None = None
        if hazard_cells:
            cur_hazard_dist = self._min_tracker_hazard_distance(
                (int(ax), int(ay)), hazard_cells
            )
        bounds = self._fire_tracker_flank_bounds(model)
        was_in_band = (
            self._position_in_sector((ax, ay), bounds)
            if bounds is not None
            else True
        )
        scored: list[tuple[float, int, float]] = []
        for direction in candidates:
            if not self._direction_in_bounds(agent, direction):
                continue
            nx = int(agent.pos[0]) + _MOVE_X[direction]
            ny = int(agent.pos[1]) + _MOVE_Y[direction]
            cell = (nx, ny)
            if self._cell_has_burning_fire(cell):
                continue
            if self._fire_tracker_cell_disqualified(cell, hazard_cells=hazard_cells):
                continue
            candidate_distance = abs(float(nx) - tx) + abs(float(ny) - ty)
            progress = current_distance - candidate_distance
            score = 0.0
            score -= candidate_distance * 0.1
            new_hazard_dist = self._min_tracker_hazard_distance(cell, hazard_cells)
            if escape_mode or (
                cur_hazard_dist is not None and cur_hazard_dist <= STANDOFF_SMOKE_CLEARANCE + 1
            ):
                score += new_hazard_dist * 15.0
                if cur_hazard_dist is not None and new_hazard_dist > cur_hazard_dist:
                    score += 20.0
                elif cur_hazard_dist is not None and new_hazard_dist < cur_hazard_dist:
                    score -= 25.0
            if hold_mode:
                if progress == 0:
                    score += 6.0
                elif progress > 0:
                    score -= progress * 3.0
                if cur_fire_dist is not None and fire_cells:
                    new_fire_dist = min(
                        abs(nx - fx) + abs(ny - fy) for fx, fy in fire_cells
                    )
                    if new_fire_dist < cur_fire_dist:
                        score -= 12.0
                    elif abs(new_fire_dist - cur_fire_dist) <= 1:
                        score += 3.0
            else:
                score += progress * 0.8
                if progress < 0:
                    score -= 2.0
                if bounds is not None and not was_in_band:
                    score += progress * 1.2
                if cur_fire_dist is not None and fire_cells:
                    new_fire_dist = min(
                        abs(nx - fx) + abs(ny - fy) for fx, fy in fire_cells
                    )
                    if new_fire_dist < STANDOFF_MIN:
                        score += _FIRE_TRACKER_HARD_HAZARD_SCORE
                    elif cur_fire_dist > STANDOFF_MAX:
                        if new_fire_dist < cur_fire_dist:
                            score += STANDOFF_APPROACH_REWARD
                        elif new_fire_dist > cur_fire_dist:
                            score -= STANDOFF_RETREAT_PENALTY
                        cur_pen = abs(cur_fire_dist - STANDOFF_IDEAL)
                        new_pen = abs(new_fire_dist - STANDOFF_IDEAL)
                        if new_pen < cur_pen:
                            score += STANDOFF_APPROACH_REWARD
                    elif STANDOFF_MIN <= cur_fire_dist <= STANDOFF_MAX + 1:
                        if new_fire_dist < STANDOFF_MIN:
                            score += _FIRE_TRACKER_HARD_HAZARD_SCORE
                        elif new_fire_dist < cur_fire_dist:
                            score -= 3.0
                        elif abs(new_fire_dist - cur_fire_dist) <= 1:
                            score += 2.0
            score -= self._visit_penalty(nx, ny) * 0.5
            if bounds is not None:
                in_band = self._position_in_sector((float(nx), float(ny)), bounds)
                if in_band and not was_in_band:
                    score += 25.0
                elif not in_band and was_in_band:
                    score -= 12.0
                elif not in_band:
                    score -= 10.0
                if not was_in_band:
                    if ax < bounds["x_min"] and nx > ax:
                        score += 15.0
                    elif ax > bounds["x_max"] and nx < ax:
                        score += 15.0
                    if ay < bounds["y_min"] and ny > ay:
                        score += 15.0
                    elif ay > bounds["y_max"] and ny < ay:
                        score += 15.0
            if self._is_failed_direction(direction):
                score -= 5.0
            if direction == preferred and not hold_mode:
                score += 0.5
            scored.append((score, direction, progress))
        if scored:
            return max(scored)[1]
        return self._fire_tracker_hold_direction(agent)

    def _perimeter_cell_acceptable(self, cell: tuple[int, int]) -> bool:
        if not self._cell_in_bounds(cell):
            return False
        if self._cell_has_burning_fire(cell):
            return False
        if self._fire_tracker_cell_disqualified(cell):
            return False
        return True

    @staticmethod
    def _normalize_wind_direction(direction: object | None) -> str:
        return normalize_wind_direction(direction)

    @staticmethod
    def _wind_vector_from_direction(direction: object | None) -> tuple[float, float]:
        return wind_vector_from_direction(direction)

    def _get_wind_direction(self, model: Any | None = None) -> str:
        resolved = model or self._model
        if resolved is not None:
            bridge = getattr(resolved, "environment_bridge", None)
            if bridge is not None:
                summary = getattr(bridge, "get_wind_summary", None)
                if callable(summary):
                    wind_data = summary()
                    if isinstance(wind_data, dict) and wind_data.get("direction"):
                        return self._normalize_wind_direction(wind_data["direction"])
            wind_agent = getattr(resolved, "wind", None)
            if wind_agent is not None:
                return self._normalize_wind_direction(
                    getattr(wind_agent, "wind_direction", None)
                )
        return self._normalize_wind_direction(None)

    def _collect_active_fire_cells(self, model: Any | None = None) -> set[tuple[int, int]]:
        resolved = model or self._model
        cells: set[tuple[int, int]] = set()
        if resolved is None:
            return cells
        schedule = getattr(resolved, "schedule", None)
        if schedule is not None:
            import agents as agents_module

            for agent in getattr(schedule, "agents", ()) or ():
                if type(agent) is not agents_module.Fire:
                    continue
                pos = getattr(agent, "pos", None)
                if pos is None:
                    continue
                is_burning = getattr(agent, "is_burning", None)
                if callable(is_burning) and is_burning():
                    cells.add((int(pos[0]), int(pos[1])))
        fire_map = self._read_fire_probability_map()
        for cell_pos, raw_prob in fire_map.items():
            if float(raw_prob) < 0.55:
                continue
            normalized = self._normalize_cell_pos(cell_pos)
            if normalized is not None:
                cells.add(normalized)
        return cells

    def _record_wind_aware_explanation(
        self,
        agent: Any,
        *,
        wind_direction: str,
        target: tuple[float, float],
        model: Any | None,
        source: str = "executor",
        reason: str | None = None,
    ) -> None:
        default_reason = (
            "prioritized safe downwind area because wind pushes fire/smoke "
            "toward that region"
        )
        explanation = {
            "decision": "victim_search_wind_aware",
            "source": source,
            "wind_direction": wind_direction,
            "target": [float(target[0]), float(target[1])],
            "reason": reason if reason is not None else default_reason,
        }
        try:
            agent.last_explanation = dict(explanation)
        except Exception:
            pass
        if model is not None and getattr(model, "debug_log", False):
            planner_tag = (
                " planner_source=local_adaptation_generator"
                if source == "planner"
                else ""
            )
            print(
                "explain=wind_aware_search"
                f"{planner_tag} "
                f"wind={wind_direction} target=({target[0]:.1f},{target[1]:.1f})"
            )

    def _planner_wind_aware_target_from_decision(
        self,
        decision: Any,
    ) -> tuple[tuple[float, float], dict[str, Any]] | None:
        if decision is None:
            return None
        selected_id = str(getattr(decision, "selected_option_id", "") or "")
        ctx = getattr(decision, "uncertainty_context", None)
        if not isinstance(ctx, dict):
            ctx = {}
        search_policy = str(ctx.get("search_policy", "") or "")
        if selected_id != "wind_aware_victim_search" and search_policy != "wind_aware":
            return None
        if ctx.get("needs_new_wind_target") or ctx.get("wind_target_reached"):
            return None
        target = self._normalize_target(
            ctx.get("target_position") or ctx.get("target_region")
        )
        if target is None:
            return None
        cell = (int(round(target[0])), int(round(target[1])))
        if self._cell_high_fire(cell) or self._cell_smoke_obscured(cell):
            return None
        wind_direction = str(ctx.get("wind_direction", "") or "")
        return (
            target,
            {
                "wind_direction": wind_direction,
                "wind_vector": ctx.get("wind_vector"),
                "source": ctx.get("source", "local_adaptation_generator"),
                "reason": ctx.get("reason", "downwind_priority"),
            },
        )

    def _runtime_models_for_wind_search(self, model: Any) -> dict[str, Any]:
        return {
            "simulation_model": model,
            "fire_runtime_model": getattr(model, "fire_runtime_model", None),
            "visibility_model": getattr(model, "visibility_model", None),
            "victim_runtime_model": getattr(model, "victim_runtime_model", None),
            "uav_resource_model": getattr(model, "uav_resource_model", None),
            "global_observation_snapshot": getattr(model, "latest_global_snapshot", None),
        }

    def _sync_agent_position_to_resource_model(self, agent: Any, model: Any) -> None:
        pos = getattr(agent, "pos", None)
        resource = getattr(model, "uav_resource_model", None)
        if pos is None or resource is None:
            return
        by_uav = getattr(resource, "by_uav_id", None)
        if not isinstance(by_uav, dict) or self.uav_id not in by_uav:
            return
        state = by_uav[self.uav_id]
        position = (float(pos[0]), float(pos[1]))
        if hasattr(state, "current_position"):
            state.current_position = position
        elif isinstance(state, dict):
            state["current_position"] = position

    def _wind_target_is_saturated(self, model: Any, target: tuple[float, float]) -> bool:
        if model is None:
            return False
        state = _wind_search_state(model, self.uav_id)
        step_index = _step_index_from_runtime({"simulation_model": model})
        return _is_saturated_cell(
            state,
            int(round(target[0])),
            int(round(target[1])),
            step_index,
        )

    def _wind_aware_victim_search_target(
        self,
        agent: Any,
        model: Any | None = None,
    ) -> tuple[float, float] | None:
        """Pick a safe cell downwind of the active fire front for victim search."""
        resolved = model or self._model or getattr(agent, "model", None)
        if resolved is None:
            return None
        wind_dir = self._get_wind_direction(resolved)
        wind_vec = self._wind_vector_from_direction(wind_dir)
        runtime_models = self._runtime_models_for_wind_search(resolved)
        self._sync_agent_position_to_resource_model(agent, resolved)
        target = LocalAdaptationSpaceGenerator()._compute_wind_aware_search_target(
            runtime_models,
            self.uav_id,
            wind_dir,
            wind_vec,
        )
        if target is None:
            target = self._wind_aware_victim_search_target_legacy(agent, resolved)
        if target is not None:
            last_targets = getattr(resolved, "_wind_aware_last_targets", None)
            if not isinstance(last_targets, dict):
                last_targets = {}
            last_targets[str(self.uav_id)] = target
            resolved._wind_aware_last_targets = last_targets
            self._record_wind_aware_explanation(
                agent,
                wind_direction=wind_dir,
                target=target,
                model=resolved,
                source="executor",
            )
        return target

    def _wind_aware_victim_search_target_legacy(
        self,
        agent: Any,
        resolved: Any,
    ) -> tuple[float, float] | None:
        """Executor-local fallback when generator runtime context is incomplete."""
        wind_vec = self._wind_vector_from_direction(self._get_wind_direction(resolved))
        fire_cells = self._collect_active_fire_cells(resolved)
        if not fire_cells:
            return None

        fx = sum(c[0] for c in fire_cells) / float(len(fire_cells))
        fy = sum(c[1] for c in fire_cells) / float(len(fire_cells))

        H = int(getattr(resolved, "HEIGHT", getattr(resolved, "height", 50)))
        W = int(getattr(resolved, "WIDTH", getattr(resolved, "width", 50)))
        bounds = (
            self._uav_sector_bounds(resolved)
            if self._sector_filtering_active(resolved)
            else None
        )
        if bounds is not None:
            x_min, x_max = int(bounds["x_min"]), int(bounds["x_max"])
            y_min, y_max = int(bounds["y_min"]), int(bounds["y_max"])
        else:
            x_min, x_max = 0, H - 1
            y_min, y_max = 0, W - 1

        pos = getattr(agent, "pos", None)
        ax = float(pos[0]) if pos is not None else (x_min + x_max) / 2.0
        ay = float(pos[1]) if pos is not None else (y_min + y_max) / 2.0

        wind_state = _wind_search_state(resolved, self.uav_id)
        step_index = _step_index_from_runtime({"simulation_model": resolved})
        best_score = -float("inf")
        best_target: tuple[float, float] | None = None
        stride = 2

        for cx in range(x_min, x_max + 1, stride):
            for cy in range(y_min, y_max + 1, stride):
                cell = (cx, cy)
                if not self._cell_in_bounds(cell):
                    continue
                if not self._victim_sweep_cell_is_approachable(cell):
                    continue
                if _is_saturated_cell(wind_state, cx, cy, step_index):
                    continue
                downwind = (float(cx) - fx) * wind_vec[0] + (float(cy) - fy) * wind_vec[1]
                allow_fire_side = bool(
                    wind_state.get("force_coverage_escape")
                ) or int(wind_state.get("steps_since_detection", 0) or 0) >= NO_VICTIM_DETECT_BOOST_AFTER
                if downwind <= 0.0 and not allow_fire_side:
                    continue
                hazard_dist = self._min_hazard_distance(cell)
                dist_agent = abs(cx - ax) + abs(cy - ay)
                capped_downwind = min(max(0.0, downwind), 20.0)
                score = (
                    capped_downwind * 3.0
                    + hazard_dist * 0.75
                    - self._visit_penalty(cx, cy) * 0.9
                    - dist_agent * 0.12
                )
                if cx <= x_min + 2 or cx >= x_max - 2 or cy <= y_min + 2 or cy >= y_max - 2:
                    score -= 7.0
                if dist_agent <= 2.0:
                    score -= 12.0
                if score > best_score:
                    best_score = score
                    best_target = (float(cx), float(cy))
        return best_target

    def _init_wind_aware_sweep_state(
        self,
        model: Any,
        pos: Any | None,
        bounds: dict[str, int] | None,
        height: int,
        width: int,
        wind_direction: str,
    ) -> dict[str, Any]:
        """Initialize lawnmower sweep origin/progression based on wind spread direction."""
        wind_dir = self._normalize_wind_direction(wind_direction)
        if bounds is not None:
            x_min = int(bounds["x_min"])
            x_max = int(bounds["x_max"])
            y_min = int(bounds["y_min"])
            y_max = int(bounds["y_max"])
        else:
            x_min, x_max = 0, height - 1
            y_min, y_max = 0, width - 1

        if wind_dir == "north":
            sweep_x = x_min
            sweep_y = y_max
            sweep_dir = -1
            primary_axis = "y"
        elif wind_dir == "south":
            sweep_x = x_min
            sweep_y = y_min
            sweep_dir = 1
            primary_axis = "y"
        elif wind_dir == "east":
            sweep_x = x_min
            sweep_y = y_min
            sweep_dir = 1
            primary_axis = "y"
        elif wind_dir == "west":
            sweep_x = x_max
            sweep_y = y_min
            sweep_dir = 1
            primary_axis = "y"
        else:
            sweep_x = x_min
            sweep_y = y_min
            sweep_dir = 1
            primary_axis = "y"

        if bounds is not None and pos is not None:
            sweep_x = max(x_min, min(x_max, int(pos[0])))

        return {
            "sweep_x": sweep_x,
            "sweep_y": sweep_y,
            "sweep_dir": sweep_dir,
            "wind_direction": wind_dir,
            "primary_axis": primary_axis,
        }

    def _victim_search_cell_is_safe(self, cell: tuple[int, int]) -> bool:
        return self._victim_sweep_cell_is_approachable(cell)

    def _victim_sweep_cell_is_approachable(self, cell: tuple[int, int]) -> bool:
        if not self._cell_in_bounds(cell):
            return False
        if self._cell_has_burning_fire(cell):
            return False
        if self._cell_smoke_obscured(cell):
            return False
        if self._cell_danger_level(cell) > 0:
            return False
        return True

    def _safe_victim_sweep_target(
        self,
        agent: Any,
        state: dict[str, Any],
        model: Any | None,
        sector_bounds: dict[str, int] | None,
        height: int,
        width: int,
        step: int,
        pos: tuple[int, int] | None,
    ) -> tuple[float, float]:
        uid = str(self.uav_id)
        sweep_states = getattr(model, "_victim_sweep_state", {}) if model else {}
        for _ in range(32):
            tx = int(state["sweep_x"])
            ty = int(state["sweep_y"])
            if self._victim_sweep_cell_is_approachable((tx, ty)):
                return (float(tx), float(ty))
            if pos is None:
                break
            cur_x, cur_y = int(pos[0]), int(pos[1])
            at_target = abs(cur_x - tx) <= 1 and abs(cur_y - ty) <= 1
            y_end = (width - 1) if state["sweep_dir"] == 1 else 0
            if sector_bounds is not None:
                y_end = (
                    sector_bounds["y_max"]
                    if state["sweep_dir"] == 1
                    else sector_bounds["y_min"]
                )
            if at_target and abs(cur_y - y_end) <= 1:
                next_x = min(tx + step, height - 1)
                if sector_bounds is not None:
                    next_x = min(next_x, sector_bounds["x_max"])
                    if next_x >= sector_bounds["x_max"]:
                        next_x = sector_bounds["x_min"]
                elif next_x >= height - 1:
                    next_x = 0
                state["sweep_x"] = next_x
                state["sweep_dir"] = -state["sweep_dir"]
                state["sweep_y"] = (
                    sector_bounds["y_min"]
                    if sector_bounds is not None and state["sweep_dir"] == 1
                    else (
                        sector_bounds["y_max"]
                        if sector_bounds is not None
                        else (0 if state["sweep_dir"] == 1 else width - 1)
                    )
                )
            elif at_target:
                state["sweep_y"] = ty + state["sweep_dir"] * step
                if sector_bounds is not None:
                    state["sweep_y"] = max(
                        sector_bounds["y_min"],
                        min(sector_bounds["y_max"], state["sweep_y"]),
                    )
                else:
                    state["sweep_y"] = max(0, min(width - 1, state["sweep_y"]))
            else:
                state["sweep_y"] = ty + state["sweep_dir"] * step
                if sector_bounds is not None:
                    state["sweep_y"] = max(
                        sector_bounds["y_min"],
                        min(sector_bounds["y_max"], state["sweep_y"]),
                    )
                else:
                    state["sweep_y"] = max(0, min(width - 1, state["sweep_y"]))
            if model is not None and isinstance(sweep_states, dict):
                sweep_states[uid] = state
        return (float(state["sweep_x"]), float(state["sweep_y"]))

    def _cell_near_hazard(self, cell: tuple[int, int], radius: int = 2) -> bool:
        cx, cy = cell
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                chebyshev = max(abs(dx), abs(dy))
                manhattan = abs(dx) + abs(dy)
                if chebyshev > radius and manhattan > radius:
                    continue
                if chebyshev > radius:
                    continue
                neighbor = (cx + dx, cy + dy)
                if self._cell_danger_level(neighbor) > 0:
                    return True
                if self._cell_high_fire(neighbor):
                    return True
                if self._cell_smoke_obscured(neighbor):
                    return True
        return False

    def _min_hazard_distance(self, cell: tuple[int, int], max_scan: int = 8) -> float:
        cx, cy = cell
        best = float(max_scan + 1)
        for dx in range(-max_scan, max_scan + 1):
            for dy in range(-max_scan, max_scan + 1):
                neighbor = (cx + dx, cy + dy)
                if (
                    self._cell_danger_level(neighbor) > 0
                    or self._cell_high_fire(neighbor)
                    or self._cell_smoke_obscured(neighbor)
                ):
                    best = min(best, float(max(abs(dx), abs(dy))))
        return best

    def _uncertainty_positions_from_runtime(self) -> list[tuple[float, float]]:
        model = self._model
        if model is None:
            return []
        visibility = getattr(model, "visibility_model", None)
        if visibility is None:
            return []
        status_map = getattr(getattr(visibility, "state", None), "observation_status_map", None)
        if not isinstance(status_map, dict):
            return []
        out: list[tuple[float, float]] = []
        for cell, status in status_map.items():
            label = getattr(status, "value", status)
            text = str(label).lower()
            if "never_seen" in text or "stale" in text:
                normalized = self._normalize_cell_pos(cell)
                if normalized is not None:
                    out.append((float(normalized[0]), float(normalized[1])))
        return out

    def _sector_filtering_active(self, model: Any | None = None) -> bool:
        resolved = model or self._model
        if resolved is None:
            agent = self._resolve_agent()
            resolved = getattr(agent, "model", None) if agent is not None else None
        if resolved is None:
            return False
        role = self._read_uav_role()
        if str(role or "").strip().lower() == "fire_tracker":
            return False
        step = int(getattr(resolved, "evaluation_timesteps_counter", 0))
        return step >= int(LAUNCH_GRACE_STEPS)

    def _uav_sector_bounds(self, model: Any | None = None) -> dict[str, int] | None:
        resolved = model or self._model
        if resolved is None:
            return None
        assignments = getattr(resolved, "_uav_sector_assignments", None)
        if not isinstance(assignments, dict):
            return None
        return assignments.get(str(self.uav_id))

    def _position_in_sector(
        self,
        position: tuple[float, float],
        bounds: dict[str, int] | None,
    ) -> bool:
        if bounds is None:
            return True
        x = int(round(float(position[0])))
        y = int(round(float(position[1])))
        return (
            bounds["x_min"] <= x <= bounds["x_max"]
            and bounds["y_min"] <= y <= bounds["y_max"]
        )

    def _filter_targets_for_sector(
        self,
        targets: list[tuple[float, float]],
        model: Any | None = None,
    ) -> list[tuple[float, float]]:
        if not self._sector_filtering_active(model):
            return targets
        bounds = self._uav_sector_bounds(model)
        if bounds is None:
            return targets
        in_sector = [
            target
            for target in targets
            if self._position_in_sector(target, bounds)
        ]
        return in_sector if in_sector else targets

    def _nearest_sector_target(
        self,
        targets: list[tuple[float, float]],
    ) -> tuple[float, float] | None:
        return self._nearest_target(self._filter_targets_for_sector(targets))

    def _sector_biased_target(
        self,
        target: tuple[float, float] | None,
    ) -> tuple[float, float] | None:
        model = self._model
        if not self._sector_filtering_active(model):
            return target
        bounds = self._uav_sector_bounds(model)
        if target is not None and self._position_in_sector(target, bounds):
            return target
        sector_targets = self._filter_targets_for_sector(
            self._uncertainty_positions_from_runtime(),
            model,
        )
        if sector_targets:
            nearest = self._nearest_target(sector_targets)
            if nearest is not None:
                return nearest
        return target

    def _nearest_target(
        self,
        targets: list[tuple[float, float]],
    ) -> tuple[float, float] | None:
        agent = self._resolve_agent()
        if agent is None or not targets:
            return None
        pos = getattr(agent, "pos", None)
        if pos is None:
            return targets[0]
        ax, ay = float(pos[0]), float(pos[1])
        best = min(
            targets,
            key=lambda t: (float(t[0]) - ax) ** 2 + (float(t[1]) - ay) ** 2,
        )
        return best

    def _choose_best_direction(
        self,
        agent: Any,
        target: tuple[float, float],
        target_kind: str = "general",
    ) -> int:
        preferred = self._direction_toward(agent, target)
        candidates = (
            preferred,
            (preferred + 1) % 4,
            (preferred + 3) % 4,
            (preferred + 2) % 4,
        )
        victim_mode = target_kind == "victim"
        scored: list[tuple[float, int, float]] = []
        ax, ay = float(agent.pos[0]), float(agent.pos[1])
        tx, ty = float(target[0]), float(target[1])
        current_distance = abs(ax - tx) + abs(ay - ty)
        fire_map = self._read_fire_probability_map()
        obs_map: dict[Any, Any] = {}
        model = self._model
        if model is not None:
            visibility = getattr(model, "visibility_model", None)
            if visibility is not None:
                status_map = getattr(
                    getattr(visibility, "state", None),
                    "observation_status_map",
                    None,
                )
                if isinstance(status_map, dict):
                    obs_map = status_map
        for direction in candidates:
            if not self._direction_in_bounds(agent, direction):
                continue
            nx = int(agent.pos[0]) + _MOVE_X[direction]
            ny = int(agent.pos[1]) + _MOVE_Y[direction]
            if victim_mode:
                if self._victim_wind_blocked_direction(agent, direction):
                    continue
                if not self._strict_path_lookahead_safe(agent, direction):
                    continue
                if self._strict_victim_hazard_level((nx, ny)) > 0:
                    continue
            candidate_distance = abs(float(nx) - tx) + abs(float(ny) - ty)
            progress = current_distance - candidate_distance
            score = 0.0
            score -= candidate_distance * (0.2 if victim_mode else 0.1)
            if victim_mode:
                score += progress * 2.0
                if progress < 0:
                    score -= 4.0
            if self._cell_high_fire((nx, ny)):
                score -= 8.0
            if self._cell_smoke_obscured((nx, ny)):
                score -= 4.0
            nx2 = nx + _MOVE_X[direction]
            ny2 = ny + _MOVE_Y[direction]
            fire_prob_2 = fire_map.get((float(nx2), float(ny2)))
            if fire_prob_2 is None:
                fire_prob_2 = fire_map.get((nx2, ny2))
            if fire_prob_2 is None:
                fire_prob_2 = 0.0
            if float(fire_prob_2) >= 0.5:
                score -= 4.0
            smoke_status_2 = obs_map.get((float(nx2), float(ny2)))
            if smoke_status_2 is None:
                smoke_status_2 = obs_map.get((nx2, ny2), "")
            if isinstance(smoke_status_2, str) and "smoke" in smoke_status_2.lower():
                score -= 2.0
            elif hasattr(smoke_status_2, "value") and "smoke" in str(smoke_status_2.value).lower():
                score -= 2.0
            score -= self._visit_penalty(nx, ny) * 0.5
            if self._is_failed_direction(direction):
                score -= 5.0
            if direction == preferred:
                score += 0.5
            if (
                victim_mode
                and direction == preferred
                and progress > 0
                and not self._cell_high_fire((nx, ny))
                and not self._cell_smoke_obscured((nx, ny))
            ):
                score += 1.5
            model = getattr(agent, "model", None) or self._model
            if model is not None:
                obs_radius = getattr(
                    model,
                    "UAV_OBSERVATION_RADIUS",
                    getattr(model, "observation_radius", 8),
                )
                managed = getattr(model, "managed_uav_states", {}) or {}
                for uid, ustate in managed.items():
                    if str(uid) == str(self.uav_id):
                        continue
                    other_pos = getattr(ustate, "position", None)
                    if other_pos is None:
                        continue
                    try:
                        dx = float(nx) - float(other_pos[0])
                        dy = float(ny) - float(other_pos[1])
                        dist = (dx * dx + dy * dy) ** 0.5
                        if dist < float(obs_radius):
                            score -= 6.0 * (1.0 - dist / float(obs_radius))
                    except Exception:
                        continue
            scored.append((score, direction, progress))
        if scored:
            pool = self._filter_scored_by_hard_safety(agent, scored)
            if victim_mode:
                improving = [item for item in pool if item[2] > 0]
                if improving:
                    return max(improving)[1]
            return max(pool)[1]
        return self._exploration_fallback(agent, victim_search=victim_mode)

    def _exploration_fallback(
        self,
        agent: Any,
        *,
        victim_search: bool = False,
    ) -> int:
        candidates = [0, 1, 3, 2]
        scored: list[tuple[float, int]] = []
        fire_map = self._read_fire_probability_map()
        obs_map: dict[Any, Any] = {}
        model = self._model
        if model is not None:
            visibility = getattr(model, "visibility_model", None)
            if visibility is not None:
                status_map = getattr(
                    getattr(visibility, "state", None),
                    "observation_status_map",
                    None,
                )
                if isinstance(status_map, dict):
                    obs_map = status_map
        for direction in candidates:
            if not self._direction_in_bounds(agent, direction):
                continue
            nx = int(agent.pos[0]) + _MOVE_X[direction]
            ny = int(agent.pos[1]) + _MOVE_Y[direction]
            if victim_search and not self._victim_search_cell_is_safe((nx, ny)):
                continue
            score = 1.0
            if self._cell_high_fire((nx, ny)):
                score -= 8.0
            if self._cell_smoke_obscured((nx, ny)):
                score -= 4.0
            if victim_search and self._cell_near_hazard((nx, ny), radius=2):
                score -= 10.0
            nx2 = nx + _MOVE_X[direction]
            ny2 = ny + _MOVE_Y[direction]
            fire_prob_2 = fire_map.get((float(nx2), float(ny2)))
            if fire_prob_2 is None:
                fire_prob_2 = fire_map.get((nx2, ny2))
            if fire_prob_2 is None:
                fire_prob_2 = 0.0
            if float(fire_prob_2) >= 0.5:
                score -= 4.0
            smoke_status_2 = obs_map.get((float(nx2), float(ny2)))
            if smoke_status_2 is None:
                smoke_status_2 = obs_map.get((nx2, ny2), "")
            if isinstance(smoke_status_2, str) and "smoke" in smoke_status_2.lower():
                score -= 2.0
            elif hasattr(smoke_status_2, "value") and "smoke" in str(smoke_status_2.value).lower():
                score -= 2.0
            score -= self._visit_penalty(nx, ny) * 0.8
            if self._is_failed_direction(direction):
                score -= 6.0
            if self._sector_filtering_active(model):
                bounds = self._uav_sector_bounds(model)
                if bounds is not None:
                    if self._position_in_sector((float(nx), float(ny)), bounds):
                        score += 1.5
                    else:
                        score -= 0.5
            scored.append((score, direction))
        if scored:
            try:
                uav_index = int(
                    "".join(filter(str.isdigit, str(self.uav_id) or "0")) or "0"
                ) % 4
                exploration_bias = {
                    0: 0,
                    1: 1,
                    2: 3,
                    3: 2,
                }.get(uav_index, 0)
                scored = [
                    (
                        score + 0.5 if direction == exploration_bias else score,
                        direction,
                    )
                    for score, direction in scored
                ]
            except Exception:
                pass
            pool = self._filter_scored_by_hard_safety(agent, scored)
            return max(pool)[1]
        return int(getattr(agent, "selected_dir", 0))

    def _visit_penalty(self, x: int, y: int) -> float:
        model = self._model
        if model is None:
            return 0.0
        counts = getattr(model, "uav_visit_counts", None)
        if not isinstance(counts, dict):
            return 0.0
        return float(counts.get((self.uav_id, x, y), 0))

    def _is_failed_direction(self, direction: int) -> bool:
        model = self._model
        if model is None:
            return False
        failed = getattr(model, "uav_last_failed_dir", None)
        if not isinstance(failed, dict):
            return False
        return int(failed.get(self.uav_id, -1)) == int(direction)

    def _cell_high_fire(self, cell: tuple[int, int], threshold: float = 0.3) -> bool:
        if self._cell_has_burning_fire(cell):
            return True
        fire_map = self._read_fire_probability_map()
        if not fire_map:
            return False
        prob = self._map_probability(fire_map, cell)
        return prob is not None and prob >= threshold

    def _cell_smoke_obscured(self, cell: tuple[int, int]) -> bool:
        if self._cell_has_active_smoke(cell):
            return True
        model = self._model
        if model is None:
            return False
        visibility = getattr(model, "visibility_model", None)
        if visibility is None:
            return False
        status_map = getattr(
            getattr(visibility, "state", None), "observation_status_map", None
        )
        if not isinstance(status_map, dict):
            return False
        for key in (cell, (float(cell[0]), float(cell[1]))):
            status = status_map.get(key)
            if status is None:
                continue
            label = getattr(status, "value", status)
            if self._smoke_label_is_hazard(str(label)):
                return True
        return False

    @staticmethod
    def _smoke_label_is_hazard(label: str) -> bool:
        text = str(label or "").strip().lower()
        if not text:
            return False
        if text in _SMOKE_HAZARD_TOKENS:
            return True
        for token in _SMOKE_HAZARD_TOKENS:
            if token in text:
                return True
        return False

    def _cell_agents(self, cell: tuple[int, int]) -> list[Any]:
        model = self._model
        if model is None:
            return []
        grid = getattr(model, "grid", None)
        if grid is None:
            return []
        get_contents = getattr(grid, "get_cell_list_contents", None)
        if not callable(get_contents):
            return []
        try:
            contents = get_contents([cell])
            return list(contents) if contents else []
        except Exception:
            return []

    def _cell_has_burning_fire(self, cell: tuple[int, int]) -> bool:
        for agent in self._cell_agents(cell):
            if type(agent).__name__ != "Fire":
                continue
            is_burning = getattr(agent, "is_burning", None)
            if callable(is_burning) and is_burning():
                return True
            if getattr(agent, "burning", False):
                return True
        return False

    def _cell_has_active_smoke(self, cell: tuple[int, int]) -> bool:
        for agent in self._cell_agents(cell):
            if type(agent).__name__ != "Fire":
                continue
            smoke = getattr(agent, "smoke", None)
            if smoke is None:
                continue
            is_active = getattr(smoke, "is_smoke_active", None)
            if callable(is_active) and is_active():
                return True
            if getattr(smoke, "smoke", False):
                return True
        return False

    @staticmethod
    def _cardinal_target_cell(
        agent: Any,
        direction: int,
    ) -> tuple[float, float]:
        pos = getattr(agent, "pos", None)
        if pos is None:
            return (0.0, 0.0)
        return (
            float(pos[0]) + float(_MOVE_X[int(direction) % 4]),
            float(pos[1]) + float(_MOVE_Y[int(direction) % 4]),
        )

    def _search_target(
        self,
        fail_safe_decision: FailSafeDecision,
        timestamp: float,
    ) -> tuple[float, float] | None:
        target = self._target_from_region(fail_safe_decision.target_region)
        if target is not None:
            return target

        model = self._model
        if model is None:
            return None
        fire_runtime = getattr(model, "fire_runtime_model", None)
        if fire_runtime is None:
            return None
        get_target = getattr(fire_runtime, "get_best_search_target", None)
        if not callable(get_target):
            return None

        call_time = timestamp
        if call_time == 0.0:
            call_time = float(getattr(model, "evaluation_timesteps_counter", 0.0))

        for attempt in (
            lambda: get_target(call_time, min_conf=0.3),
            lambda: get_target(current_time=call_time, min_conf=0.3),
            lambda: get_target(min_conf=0.3),
        ):
            try:
                raw = attempt()
            except TypeError:
                continue
            parsed = self._normalize_target(raw)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _target_from_region(target_region: str) -> tuple[float, float] | None:
        if not target_region.strip():
            return None
        cleaned = target_region.strip().replace("(", "").replace(")", "")
        parts = cleaned.split(",")
        if len(parts) < 2:
            return None
        try:
            return (float(parts[0].strip()), float(parts[1].strip()))
        except ValueError:
            return None

    @staticmethod
    def _normalize_target(raw: object) -> tuple[float, float] | None:
        if raw is None:
            return None
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            try:
                return (float(raw[0]), float(raw[1]))
            except (TypeError, ValueError):
                return None
        return None

    def _read_uav_role(self) -> str | None:
        model = self._model
        if model is None:
            return None
        resource_model = getattr(model, "uav_resource_model", None)
        if resource_model is None:
            return None
        by_uav_id = getattr(resource_model, "by_uav_id", None)
        if not isinstance(by_uav_id, dict) or self.uav_id not in by_uav_id:
            return None
        state = by_uav_id[self.uav_id]
        role = getattr(state, "current_role", None)
        if role is None and isinstance(state, dict):
            role = state.get("current_role", state.get("role"))
        return str(role) if role is not None else None

    def _read_fire_probability_map(self) -> dict[Any, float]:
        model = self._model
        if model is None:
            return {}
        fire_runtime_model = getattr(model, "fire_runtime_model", None)
        if fire_runtime_model is None:
            return {}
        direct_map = getattr(fire_runtime_model, "fire_probability_map", None)
        if isinstance(direct_map, dict) and direct_map:
            return dict(direct_map)
        belief = getattr(fire_runtime_model, "belief", None)
        if belief is not None:
            belief_map = getattr(belief, "fire_probability_map", None)
            if isinstance(belief_map, dict):
                return dict(belief_map)
        return {}

    @staticmethod
    def _is_fire_front_cell_simple(
        cell: tuple[int, int],
        fire_probability_map: dict[Any, float],
        threshold: float = 0.3,
    ) -> bool:
        center_prob = UAVExecutor._map_probability(fire_probability_map, cell)
        if center_prob is None or center_prob < threshold:
            return False
        x, y = cell
        high_neighbors = 0
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            neighbor_prob = UAVExecutor._map_probability(fire_probability_map, neighbor)
            if neighbor_prob is not None and neighbor_prob >= threshold:
                high_neighbors += 1
        return high_neighbors < 4

    def _resolve_agent(self) -> Any | None:
        if self._agent is not None:
            return self._agent
        model = self._model
        if model is None:
            return None
        schedule = getattr(model, "schedule", None)
        if schedule is None:
            return None
        for agent in getattr(schedule, "agents", []):
            if str(getattr(agent, "unique_id", "")) == self.uav_id:
                return agent
            if str(getattr(agent, "uav_id", "")) == self.uav_id:
                return agent
        return None

    def _direction_toward(self, agent: Any, target: tuple[float, float]) -> int:
        current = int(getattr(agent, "selected_dir", 0))
        pos = getattr(agent, "pos", None)
        if pos is None:
            return current
        dx = float(target[0]) - float(pos[0])
        dy = float(target[1]) - float(pos[1])
        if dx == 0.0 and dy == 0.0:
            return current
        if abs(dx) >= abs(dy):
            if dx > 0:
                chosen = 0
            elif dx < 0:
                chosen = 2
            else:
                return current
        elif dy < 0:
            chosen = 1
        elif dy > 0:
            chosen = 3
        else:
            return current
        return self._first_boundary_safe_direction(agent, chosen)

    def _first_boundary_safe_direction(self, agent: Any, chosen: int) -> int:
        if not self._can_check_bounds(agent):
            return chosen
        for direction in (chosen, (chosen + 1) % 4, (chosen + 3) % 4, (chosen + 2) % 4):
            if self._direction_in_bounds(agent, direction):
                return direction
        return chosen

    def _resolve_model(self, agent: Any) -> Any | None:
        return getattr(agent, "model", None) or self._model

    def _can_check_bounds(self, agent: Any) -> bool:
        model = self._resolve_model(agent)
        if model is None:
            return False
        grid = getattr(model, "grid", None)
        if grid is not None and callable(getattr(grid, "out_of_bounds", None)):
            return True
        width = self._grid_dimension(model, ("grid_width", "WIDTH", "width"))
        height = self._grid_dimension(model, ("grid_height", "HEIGHT", "height"))
        return width is not None and height is not None

    @staticmethod
    def _grid_dimension(model: Any, attribute_names: tuple[str, ...]) -> int | None:
        for name in attribute_names:
            value = getattr(model, name, None)
            if value is not None:
                return int(value)
        return None

    @staticmethod
    def _normalize_cell_pos(cell_pos: Any) -> tuple[int, int] | None:
        if isinstance(cell_pos, (list, tuple)) and len(cell_pos) >= 2:
            try:
                return (int(cell_pos[0]), int(cell_pos[1]))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _map_probability(
        fire_probability_map: dict[Any, float],
        cell_pos: tuple[int, int],
    ) -> float | None:
        prob = fire_probability_map.get(cell_pos)
        if prob is None:
            prob = fire_probability_map.get((float(cell_pos[0]), float(cell_pos[1])))
        if prob is None:
            return None
        return float(prob)

    def _direction_in_bounds(self, agent: Any, direction: int) -> bool:
        pos = getattr(agent, "pos", None)
        if pos is None:
            return True
        nx = int(pos[0]) + _MOVE_X[direction]
        ny = int(pos[1]) + _MOVE_Y[direction]
        model = self._resolve_model(agent)
        if model is None:
            return True
        grid = getattr(model, "grid", None)
        out_of_bounds = getattr(grid, "out_of_bounds", None) if grid is not None else None
        if callable(out_of_bounds):
            return not out_of_bounds((nx, ny))
        width = self._grid_dimension(model, ("grid_width", "WIDTH", "width"))
        height = self._grid_dimension(model, ("grid_height", "HEIGHT", "height"))
        if width is None or height is None:
            return True
        return 0 <= nx < width and 0 <= ny < height
