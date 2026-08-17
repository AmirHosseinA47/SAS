"""Local adaptation space generator skeleton."""

import math
from typing import Any

from common_fixed_variables import normalize_wind_direction, wind_vector_from_direction

from ..planning.mission_goal_integration import (
    boost_confidence,
    goal_priority_enabled,
    mission_goal_option_metadata,
    path_constraint_flags,
    read_mission_goals,
)
from .adaptation_option_objects import AdaptationOption, LocalAdaptationOption, Scope
from .trigger_input import adaptation_trigger_metadata
from .adaptation_results import LocalAdaptationSpace


def _read_local_path_context(
    local_models: Any,
    runtime_models: Any,
    uav_id: str | None = None,
) -> dict[str, Any]:
    """Return live local path context snapshot when available."""
    model = None
    if isinstance(local_models, dict):
        model = local_models.get("local_path_context_model")
    if model is None and isinstance(runtime_models, dict):
        by_uav = runtime_models.get("local_path_context_models")
        if isinstance(by_uav, dict):
            if uav_id is not None:
                model = by_uav.get(str(uav_id))
            elif len(by_uav) == 1:
                model = next(iter(by_uav.values()))
        if model is None:
            model = runtime_models.get("local_path_context_model")
    if model is None:
        return {}
    runtime_context = getattr(model, "runtime_context", None)
    if callable(runtime_context):
        snapshot = runtime_context()
        return dict(snapshot) if isinstance(snapshot, dict) else {}
    snapshot = getattr(model, "snapshot", None)
    if callable(snapshot):
        result = snapshot()
        return dict(result) if isinstance(result, dict) else {}
    return {}


WIND_DOWNWIND_CAP = 20.0
WIND_EDGE_MARGIN = 2
WIND_EDGE_PENALTY = 7.0
WIND_SOUTH_EDGE_PENALTY = 15.0
WIND_VISIT_PENALTY_SCALE = 0.9
WIND_COVERAGE_PENALTY = 4.0
WIND_RECENT_TARGET_PENALTY = 5.0
WIND_REACHED_PENALTY = 12.0
WIND_SATURATE_DWELL_STEPS = 2
WIND_SATURATE_COOLDOWN_STEPS = 12
WIND_RECENT_TARGET_HISTORY = 8
WIND_CORRIDOR_MAX_WAYPOINTS = 16
WIND_CORRIDOR_STRIDE = 3
WIND_EDGE_STREAK_FORCE_RETARGET = 6
WIND_HOLD_STREAK_FORCE_RETARGET = 5
WIND_SAME_TARGET_FORCE_RETARGET = 10
WIND_SAME_TARGET_RESET_STREAK = 10
WIND_TARGET_BLACKLIST_COOLDOWN = 15
WIND_MAX_WIND_AWARE_HOLDS = 2
WIND_FIRE_FRONT_MIN_DISTANCE = 12
WIND_FIRE_FRONT_DISTANCE_SCALE = 4.0
WIND_SMOKE_FRONT_DISTANCE_SCALE = 3.0
WIND_EAST_INTERIOR_MARGIN = 6
WIND_PATH_LOOKAHEAD_DEPTH = 3
WIND_VICTIM_HAZARD_BUFFER = 2
WIND_POCKET_CAMP_THRESHOLD = 20
WIND_INTERIOR_MARGIN = 6
WIND_SWEEP_NO_MOVE_ESCAPE = 5
HYBRID_WIND_WEIGHT = 1.0
HYBRID_COVERAGE_WEIGHT = 1.15
HYBRID_VICTIM_WEIGHT = 1.0
HYBRID_HAZARD_WEIGHT = 0.85
HYBRID_INTERIOR_WEIGHT = 0.9
NO_VICTIM_DETECT_BOOST_AFTER = 40
CORRIDOR_DIVERSITY_X_BAND = 38
CORRIDOR_DIVERSITY_MIN_STEPS = 20
CORRIDOR_NARROW_X_SPAN = 18
CORRIDOR_WEST_TARGET_X_MAX = 25
CORRIDOR_WEST_CAMP_X = 12
POST_RESCUE_COVERAGE_DURATION = 50
COVERAGE_INTERIOR_X_MIN = 8
COVERAGE_INTERIOR_X_MAX = 30
COVERAGE_SWEEP_BAND_MARGIN = 6
COVERAGE_UNVISITED_X_BONUS = 14.0
COVERAGE_UNVISITED_Y_BONUS = 12.0
COVERAGE_EDGE_SWEEP_BONUS = 10.0
COVERAGE_Y_SWEEP_MIN_STEPS = 15
COVERAGE_Y_COMMIT_TARGET_MARGIN = 4
COVERAGE_Y_COMMIT_PENETRATE_MARGIN = 6
COVERAGE_Y_COMMIT_GRADUAL_STEP = 6
TERMINAL_VICTIM_STATUSES = frozenset({"rescued", "dead", "unreachable", "cancelled"})


def _coverage_safe_x_min(x_min: int) -> int:
    return int(x_min) + WIND_EDGE_MARGIN


def _coverage_safe_x_max(x_max: int) -> int:
    return int(x_max) - WIND_EDGE_MARGIN


def _coverage_safe_y_min(y_min: int) -> int:
    return int(y_min) + WIND_EDGE_MARGIN


def _coverage_safe_y_max(y_max: int) -> int:
    return int(y_max) - WIND_EDGE_MARGIN


def _coverage_interior_x_max(x_max: int) -> int:
    """Eastern safe bound scales with grid size."""
    return _coverage_safe_x_max(x_max)


def _coverage_x_span(wind_state: dict[str, Any]) -> tuple[int | None, int | None]:
    recent = list(wind_state.get("recent_x_positions") or [])
    if not recent:
        return None, None
    values = [int(x) for x in recent]
    return min(values), max(values)


def _coverage_y_span(wind_state: dict[str, Any]) -> tuple[int | None, int | None]:
    recent = list(wind_state.get("recent_y_positions") or [])
    if not recent:
        return None, None
    values = [int(y) for y in recent]
    return min(values), max(values)


def _west_strip_reached(wind_state: dict[str, Any], safe_x_min: int) -> bool:
    """True once the searcher has occupied the reachable west interior.

    The static downwind west edge (x <= 3) is not a stable camp; A/west 505
    median x was 11. Release west-first pull at that reachable band so an
    upwind (east) sweep can start before the never_detected timeout.
    """
    x_lo, _ = _coverage_x_span(wind_state)
    if x_lo is None:
        return False
    return int(x_lo) <= int(safe_x_min) + COVERAGE_SWEEP_BAND_MARGIN + 4


def _east_strip_reached(wind_state: dict[str, Any], safe_x_max: int) -> bool:
    _, x_hi = _coverage_x_span(wind_state)
    if x_hi is None:
        return False
    return int(x_hi) >= int(safe_x_max) - COVERAGE_SWEEP_BAND_MARGIN - 4


def _mark_x_strip_progress(
    wind_state: dict[str, Any], safe_x_min: int, safe_x_max: int,
) -> None:
    if _west_strip_reached(wind_state, safe_x_min):
        wind_state["west_strip_done"] = True
    if _east_strip_reached(wind_state, safe_x_max):
        wind_state["east_strip_done"] = True


def _west_sweep_pending(wind_state: dict[str, Any], safe_x_min: int) -> bool:
    if bool(wind_state.get("west_strip_done")):
        return False
    return not _west_strip_reached(wind_state, safe_x_min)


def _east_sweep_pending(wind_state: dict[str, Any], safe_x_max: int) -> bool:
    if bool(wind_state.get("east_strip_done")):
        return False
    return not _east_strip_reached(wind_state, safe_x_max)


def _allow_east_force(wind_state: dict[str, Any]) -> bool:
    """Second-sweep east pull is only for west wind (upwind of the fire)."""
    w = str(wind_state.get("last_wind_direction") or "").strip().lower()
    return w == "west"


def _uncovered_region_bonus(
    cx: int,
    cy: int,
    wind_state: dict[str, Any],
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
) -> float:
    bonus = 0.0
    safe_x_lo = _coverage_safe_x_min(x_min)
    safe_x_hi = _coverage_safe_x_max(x_max)
    safe_y_lo = _coverage_safe_y_min(y_min)
    safe_y_hi = _coverage_safe_y_max(y_max)
    x_lo, x_hi = _coverage_x_span(wind_state)
    y_lo, y_hi = _coverage_y_span(wind_state)
    if x_lo is not None and x_lo > safe_x_lo + 3 and cx <= x_lo:
        bonus += COVERAGE_UNVISITED_X_BONUS + (x_lo - cx) * 0.75
    if x_hi is not None and x_hi < safe_x_hi - 3 and cx >= x_hi:
        bonus += COVERAGE_UNVISITED_X_BONUS + (cx - x_hi) * 0.75
    if y_lo is not None and y_lo > safe_y_lo + 3 and cy <= y_lo:
        bonus += COVERAGE_UNVISITED_Y_BONUS + (y_lo - cy) * 0.65
    if y_hi is not None and y_hi < safe_y_hi - 3 and cy >= y_hi:
        bonus += COVERAGE_UNVISITED_Y_BONUS + (cy - y_hi) * 0.65
    if x_lo is not None and x_hi is not None:
        span = x_hi - x_lo
        grid_span = max(1, safe_x_hi - safe_x_lo)
        if span < grid_span * 0.55:
            if cx <= safe_x_lo + COVERAGE_SWEEP_BAND_MARGIN:
                bonus += COVERAGE_EDGE_SWEEP_BONUS
            if cx >= safe_x_hi - COVERAGE_SWEEP_BAND_MARGIN:
                bonus += COVERAGE_EDGE_SWEEP_BONUS * 0.85
    return bonus


def _corridor_target_x_cap(
    wind_state: dict[str, Any],
    x_min: int,
    x_max: int,
    *,
    coverage_active: bool,
) -> int:
    recent = list(wind_state.get("recent_x_positions") or [])
    safe_x_hi = _coverage_safe_x_max(x_max)
    if len(recent) >= CORRIDOR_DIVERSITY_MIN_STEPS:
        tail = [int(x) for x in recent[-CORRIDOR_DIVERSITY_MIN_STEPS:]]
        if tail and all(x >= CORRIDOR_DIVERSITY_X_BAND for x in tail):
            return max(_coverage_safe_x_min(x_min), min(tail) - 8)
        if (
            tail
            and all(x <= CORRIDOR_WEST_CAMP_X for x in tail)
            and str(wind_state.get("last_wind_direction") or "").strip().lower() == "west"
        ):
            return safe_x_hi
    if coverage_active:
        return safe_x_hi
    return max(_coverage_safe_x_min(x_min), min(CORRIDOR_WEST_TARGET_X_MAX, safe_x_hi))


_VICTIM_SEARCHER_ROLES = frozenset({"victim_searcher", "victim_search"})


def apply_scenario_globals(module: Any, **values: Any) -> None:
    for key, value in values.items():
        setattr(module, key, value)


def apply_scenario_config(cfv_module: Any, wf_module: Any, **values: Any) -> None:
    for key, value in values.items():
        setattr(cfv_module, key, value)
        setattr(wf_module, key, value)


def resolve_victim_searcher_uav_ids(model_or_runtime: Any) -> list[str]:
    if model_or_runtime is None:
        return []
    schedule = getattr(model_or_runtime, "schedule", None)
    agents_list = getattr(schedule, "agents", None) if schedule is not None else None
    if not agents_list:
        return []
    import agents as agents_module

    managed = getattr(model_or_runtime, "managed_uav_states", {}) or {}
    resource = getattr(model_or_runtime, "uav_resource_model", None)
    by_id = getattr(resource, "by_uav_id", None) if resource is not None else None
    ids: list[str] = []
    for agent in agents_list:
        if type(agent) is not agents_module.UAV:
            continue
        uid = str(getattr(agent, "unique_id", ""))
        if not uid:
            continue
        role = ""
        state = managed.get(uid)
        if state is not None:
            role = str(getattr(state, "role", "") or getattr(state, "current_role", "") or "")
        if not role and isinstance(by_id, dict) and uid in by_id:
            rs = by_id[uid]
            role = str(getattr(rs, "current_role", "") or "")
            if not role and isinstance(rs, dict):
                role = str(rs.get("current_role", rs.get("role", "")) or "")
        if role.strip().lower() in _VICTIM_SEARCHER_ROLES:
            ids.append(uid)
    if ids:
        return sorted(ids, key=lambda x: int(x) if x.isdigit() else x)
    n_agents = int(getattr(model_or_runtime, "NUM_AGENTS", 0) or 0)
    if n_agents <= 0:
        return []
    uavs = sorted(
        [a for a in agents_list if type(a) is agents_module.UAV],
        key=lambda a: int(getattr(a, "unique_id", 0)),
    )
    if uavs:
        return [str(uavs[min(n_agents, len(uavs)) - 1].unique_id)]
    return []


def resolve_primary_victim_searcher_uav_id(model_or_runtime: Any) -> str | None:
    ids = resolve_victim_searcher_uav_ids(model_or_runtime)
    return ids[0] if ids else None


def _wind_label_from_vector(wind_vector: tuple[float, float]) -> str:
    wvx, wvy = float(wind_vector[0]), float(wind_vector[1])
    if abs(wvx) >= abs(wvy):
        return "east" if wvx >= 0.0 else "west"
    return "north" if wvy >= 0.0 else "south"


def _searcher_crosswind_lane(
    simulation: Any,
    uav_id: str,
    wind_direction: str,
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
) -> tuple[str, int, int] | None:
    """Disjoint cross-wind band for this searcher, or None when n <= 1."""
    ids = resolve_victim_searcher_uav_ids(simulation)
    n = len(ids)
    if n <= 1:
        return None
    try:
        idx = ids.index(str(uav_id))
    except ValueError:
        return None
    w = normalize_wind_direction(wind_direction)
    if w in ("east", "west"):
        span = y_max - y_min + 1
        lo = y_min + (span * idx) // n
        hi = y_min + (span * (idx + 1)) // n - 1
        if idx == n - 1:
            hi = y_max
        return ("y", lo, hi)
    span = x_max - x_min + 1
    lo = x_min + (span * idx) // n
    hi = x_min + (span * (idx + 1)) // n - 1
    if idx == n - 1:
        hi = x_max
    return ("x", lo, hi)


def _lane_allows_cell(
    lane: tuple[str, int, int] | None, cx: int, cy: int,
) -> bool:
    if lane is None:
        return True
    axis, lo, hi = lane
    if axis == "y":
        return lo <= cy <= hi
    return lo <= cx <= hi


def _simulation_from_runtime(runtime_models: Any) -> Any | None:
    if isinstance(runtime_models, dict):
        return runtime_models.get("simulation_model")
    return getattr(runtime_models, "simulation_model", None)


def _step_index_from_runtime(runtime_models: Any) -> int:
    sim = _simulation_from_runtime(runtime_models)
    if sim is not None:
        try:
            return int(getattr(sim, "evaluation_timesteps_counter", 0) or 0)
        except (TypeError, ValueError):
            pass
    return 0


def _default_wind_search_state() -> dict[str, Any]:
    return {
        "current_target": None,
        "dwell_count": 0,
        "recent_targets": [],
        "saturated_until": {},
        "corridor_targets": [],
        "corridor_index": 0,
        "recent_corridor_targets": [],
        "edge_streak": 0,
        "hold_streak": 0,
        "same_target_streak": 0,
        "wind_aware_hold_streak": 0,
        "last_grid_position": None,
        "last_action": None,
        "force_interior_retarget": False,
        "force_sweep": False,
        "force_east_interior": False,
        "force_coverage_escape": False,
        "pocket_streak": 0,
        "pocket_center": None,
        "pocket_anchor": None,
        "escape_target": None,
        "sweep_no_move_streak": 0,
        "last_committed_position": None,
        "coverage_priority": 0.0,
        "hazard_buffer_level": 0,
        "searcher_victim_detections": 0,
        "steps_since_detection": 0,
        "last_wind_direction": None,
        "fire_tracker_detection_boost": 0.0,
        "post_rescue_coverage_steps_remaining": 0,
        "recent_x_positions": [],
        "recent_y_positions": [],
        "coverage_y_commit": None,
        "unresolved_victim_count": 0,
        "west_strip_done": False,
        "east_strip_done": False,
    }


def _wind_search_state(simulation: Any | None, uav_id: str) -> dict[str, Any]:
    if simulation is None:
        return _default_wind_search_state()
    store = getattr(simulation, "_wind_search_target_state", None)
    if not isinstance(store, dict):
        store = {}
        simulation._wind_search_target_state = store
    state = store.get(str(uav_id))
    if not isinstance(state, dict):
        state = _default_wind_search_state()
        store[str(uav_id)] = state
    defaults = _default_wind_search_state()
    for key, value in defaults.items():
        if key not in state:
            state[key] = value if not isinstance(value, list) else []
    if not isinstance(state.get("recent_targets"), list):
        state["recent_targets"] = []
    if not isinstance(state.get("saturated_until"), dict):
        state["saturated_until"] = {}
    if not isinstance(state.get("corridor_targets"), list):
        state["corridor_targets"] = []
    if not isinstance(state.get("recent_corridor_targets"), list):
        state["recent_corridor_targets"] = []
    if not isinstance(state.get("recent_x_positions"), list):
        state["recent_x_positions"] = []
    if not isinstance(state.get("recent_y_positions"), list):
        state["recent_y_positions"] = []
    if "coverage_y_commit" not in state:
        state["coverage_y_commit"] = None
    return state


def _manhattan(ax: float, ay: float, bx: float, by: float) -> float:
    return abs(ax - bx) + abs(ay - by)


def _cell_on_edge(
    cx: int,
    cy: int,
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    margin: int = WIND_EDGE_MARGIN,
) -> bool:
    return (
        cx <= x_min + margin
        or cx >= x_max - margin
        or cy <= y_min + margin
        or cy >= y_max - margin
    )


def _visit_count_for_cell(
    simulation: Any | None,
    uav_id: str,
    cx: int,
    cy: int,
) -> int:
    if simulation is None:
        return 0
    counts = getattr(simulation, "uav_visit_counts", None)
    if not isinstance(counts, dict):
        return 0
    return int(counts.get((str(uav_id), int(cx), int(cy)), 0) or 0)


def _observation_coverage_penalty(
    runtime_models: Any,
    cx: int,
    cy: int,
) -> float:
    visibility = None
    if isinstance(runtime_models, dict):
        visibility = runtime_models.get("visibility_model")
    else:
        visibility = getattr(runtime_models, "visibility_model", None)
    if visibility is None:
        return 0.0
    status_map = getattr(getattr(visibility, "state", None), "observation_status_map", None)
    if not isinstance(status_map, dict):
        return 0.0
    status = status_map.get((cx, cy))
    if status is None:
        status = status_map.get((float(cx), float(cy)))
    if status is None:
        return 0.0
    label = str(getattr(status, "value", status) or "").lower()
    if label in {"observed_no_fire", "observed_fire"}:
        return WIND_COVERAGE_PENALTY
    if label == "stale_information":
        return WIND_COVERAGE_PENALTY * 0.35
    return 0.0


def _never_seen_proximity_bonus(
    runtime_models: Any,
    cx: int,
    cy: int,
    *,
    obs_radius: int = 8,
) -> float:
    visibility = None
    if isinstance(runtime_models, dict):
        visibility = runtime_models.get("visibility_model")
    else:
        visibility = getattr(runtime_models, "visibility_model", None)
    if visibility is None:
        return 0.0
    status_map = getattr(getattr(visibility, "state", None), "observation_status_map", None)
    if not isinstance(status_map, dict):
        return 0.0
    bonus = 0.0
    for cell_pos, status in status_map.items():
        label = str(getattr(status, "value", status) or "").lower()
        if "never_seen" not in label and label != "stale_information":
            continue
        if isinstance(cell_pos, (list, tuple)) and len(cell_pos) >= 2:
            nx, ny = int(cell_pos[0]), int(cell_pos[1])
        else:
            continue
        dist = abs(cx - nx) + abs(cy - ny)
        if dist <= obs_radius:
            bonus += 4.0
        elif dist <= obs_radius + 8:
            bonus += max(0.0, 2.5 - (dist - obs_radius) * 0.3)
    return bonus


def _is_saturated_cell(
    state: dict[str, Any],
    cx: int,
    cy: int,
    step_index: int,
) -> bool:
    saturated = state.get("saturated_until")
    if not isinstance(saturated, dict):
        return False
    for key in ((cx, cy), (float(cx), float(cy)), f"{cx},{cy}"):
        until = saturated.get(key)
        if until is None:
            continue
        try:
            if int(until) > int(step_index):
                return True
            saturated.pop(key, None)
        except (TypeError, ValueError):
            continue
    for (tx, ty), until in list(saturated.items()):
        try:
            if int(until) <= int(step_index):
                saturated.pop((tx, ty), None)
                continue
            if abs(int(cx) - int(tx)) + abs(int(cy) - int(ty)) <= 2:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _recent_target_penalty(state: dict[str, Any], cx: int, cy: int) -> float:
    penalty = 0.0
    for prior in state.get("recent_targets") or []:
        if not isinstance(prior, (list, tuple)) or len(prior) < 2:
            continue
        px, py = float(prior[0]), float(prior[1])
        dist = abs(cx - px) + abs(cy - py)
        if dist <= 1:
            penalty += WIND_RECENT_TARGET_PENALTY
        elif dist <= 3:
            penalty += WIND_RECENT_TARGET_PENALTY * 0.55
    return penalty


def _score_wind_aware_cell(
    *,
    cx: int,
    cy: int,
    downwind: float,
    hazard_dist: float,
    dist_agent: float,
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    runtime_models: Any,
    simulation: Any | None,
    uav_id: str,
    wind_state: dict[str, Any],
    require_positive_downwind: bool,
) -> float | None:
    if require_positive_downwind and downwind <= 0.0:
        return None
    capped_downwind = min(max(0.0, float(downwind)), WIND_DOWNWIND_CAP)
    score = capped_downwind * 3.0 + hazard_dist * 0.75 - dist_agent * 0.12
    if _cell_on_edge(cx, cy, x_min, x_max, y_min, y_max):
        score -= WIND_EDGE_PENALTY
    visit_pen = _visit_count_for_cell(simulation, uav_id, cx, cy)
    score -= visit_pen * WIND_VISIT_PENALTY_SCALE
    score -= _observation_coverage_penalty(runtime_models, cx, cy)
    score -= _recent_target_penalty(wind_state, cx, cy)
    if dist_agent <= 2.0:
        score -= WIND_REACHED_PENALTY
    elif dist_agent <= 4.0:
        score -= WIND_REACHED_PENALTY * 0.45
    return score


def _interior_margin_score(
    cx: int, cy: int, x_min: int, x_max: int, y_min: int, y_max: int,
) -> float:
    dist = _distance_to_boundary(cx, cy, x_min, x_max, y_min, y_max)
    if dist >= WIND_INTERIOR_MARGIN:
        return HYBRID_INTERIOR_WEIGHT * float(WIND_INTERIOR_MARGIN)
    return HYBRID_INTERIOR_WEIGHT * float(dist)


def _pocket_penalty(wind_state: dict[str, Any], cx: int, cy: int) -> float:
    center = wind_state.get("pocket_center")
    if not isinstance(center, (list, tuple)) or len(center) < 2:
        return 0.0
    dist = abs(cx - int(center[0])) + abs(cy - int(center[1]))
    if dist <= 2:
        return float(int(wind_state.get("pocket_streak", 0) or 0)) * 0.15
    return 0.0


def _victim_likelihood_score(runtime_models: Any, cx: int, cy: int) -> float:
    victim_model = None
    if isinstance(runtime_models, dict):
        victim_model = runtime_models.get("victim_runtime_model")
    else:
        victim_model = getattr(runtime_models, "victim_runtime_model", None)
    victims = getattr(victim_model, "victims", None) if victim_model is not None else None
    if not isinstance(victims, dict) or not victims:
        return 0.0
    best = 0.0
    for victim in victims.values():
        pos = None
        if isinstance(victim, dict):
            raw = victim.get("estimated_position") or victim.get("position")
            if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                pos = raw
        else:
            raw = getattr(victim, "estimated_position", None) or getattr(victim, "position", None)
            if raw is not None:
                pos = raw
        if pos is None:
            continue
        dist = abs(cx - float(pos[0])) + abs(cy - float(pos[1]))
        conf = float(getattr(victim, "confidence", 0.0) or 0.0)
        if isinstance(victim, dict):
            conf = float(victim.get("confidence", 0.0) or 0.0)
        best = max(best, conf * max(0.0, 12.0 - dist * 0.35))
    return best * HYBRID_VICTIM_WEIGHT


def _count_unresolved_victims(simulation: Any | None) -> int:
    managed = getattr(simulation, "managed_victims", None) if simulation is not None else None
    if not isinstance(managed, dict):
        return 0
    markers = getattr(simulation, "victim_marker_agents", None)
    unresolved = 0
    for vid, state in managed.items():
        if state is None:
            continue
        status = str(getattr(state, "status", "") or "").strip().lower()
        if status in TERMINAL_VICTIM_STATUSES:
            continue
        if bool(getattr(state, "rescued", False)):
            continue
        if bool(getattr(state, "dead", False)):
            continue
        if bool(getattr(state, "cancelled", False)):
            continue
        if bool(getattr(state, "unreachable", False)):
            continue
        if isinstance(markers, dict) and vid in markers:
            marker = markers[vid]
            marker_status = str(getattr(marker, "status", "") or "").strip().lower()
            if marker_status in TERMINAL_VICTIM_STATUSES:
                continue
        unresolved += 1
    return unresolved


def _corridor_diversity_failure(wind_state: dict[str, Any]) -> bool:
    recent = list(wind_state.get("recent_x_positions") or [])
    if len(recent) < CORRIDOR_DIVERSITY_MIN_STEPS:
        return False
    tail = [int(x) for x in recent[-CORRIDOR_DIVERSITY_MIN_STEPS:]]
    if not tail:
        return False
    if all(x >= CORRIDOR_DIVERSITY_X_BAND for x in tail):
        return True
    if (
        all(x <= CORRIDOR_WEST_CAMP_X for x in tail)
        and str(wind_state.get("last_wind_direction") or "").strip().lower() == "west"
    ):
        return True
    if max(tail) - min(tail) <= CORRIDOR_NARROW_X_SPAN:
        return True
    return False


def _coverage_mode_active(wind_state: dict[str, Any]) -> bool:
    unresolved = int(wind_state.get("unresolved_victim_count", 0) or 0)
    if unresolved <= 0:
        return False
    steps = int(wind_state.get("steps_since_detection", 0) or 0)
    boost = float(wind_state.get("fire_tracker_detection_boost", 0.0) or 0.0)
    post_rescue = int(wind_state.get("post_rescue_coverage_steps_remaining", 0) or 0)
    if steps > NO_VICTIM_DETECT_BOOST_AFTER:
        return True
    if _corridor_diversity_failure(wind_state):
        return True
    if boost > 0.2:
        return True
    if post_rescue > 0:
        return True
    return True


def _grid_y_half_split(y_min: int, y_max: int) -> tuple[int, int]:
    lower_max = (y_min + y_max) // 2
    return lower_max, lower_max + 1


def _coverage_y_lower_camping(
    wind_state: dict[str, Any], y_min: int, y_max: int,
) -> bool:
    recent = list(wind_state.get("recent_y_positions") or [])
    if len(recent) < COVERAGE_Y_SWEEP_MIN_STEPS:
        return False
    _, upper_min = _grid_y_half_split(y_min, y_max)
    penetrate_y = upper_min + COVERAGE_SWEEP_BAND_MARGIN
    tail = [int(y) for y in recent[-COVERAGE_Y_SWEEP_MIN_STEPS:]]
    return bool(tail) and max(tail) < penetrate_y


def _coverage_y_upper_camping(
    wind_state: dict[str, Any], y_min: int, y_max: int,
) -> bool:
    recent = list(wind_state.get("recent_y_positions") or [])
    if len(recent) < COVERAGE_Y_SWEEP_MIN_STEPS:
        return False
    lower_max, upper_min = _grid_y_half_split(y_min, y_max)
    tail = [int(y) for y in recent[-COVERAGE_Y_SWEEP_MIN_STEPS:]]
    return bool(tail) and min(tail) >= upper_min


def _coverage_y_commit_penetrated(
    commit: str,
    agent_y: float,
    y_min: int,
    y_max: int,
) -> bool:
    ay = float(agent_y)
    if commit == "north":
        return ay >= y_max - COVERAGE_Y_COMMIT_PENETRATE_MARGIN
    if commit == "south":
        return ay <= y_min + COVERAGE_Y_COMMIT_PENETRATE_MARGIN
    return False


def _update_coverage_y_commit(
    wind_state: dict[str, Any],
    y_min: int,
    y_max: int,
    agent_y: float | None = None,
) -> None:
    commit = wind_state.get("coverage_y_commit")
    if commit in ("north", "south"):
        if agent_y is not None and _coverage_y_commit_penetrated(
            str(commit), float(agent_y), y_min, y_max
        ):
            wind_state["coverage_y_commit"] = None
            return
        return
    if _coverage_y_lower_camping(wind_state, y_min, y_max):
        wind_state["coverage_y_commit"] = "north"
    elif _coverage_y_upper_camping(wind_state, y_min, y_max):
        wind_state["coverage_y_commit"] = "south"


def _coverage_y_commit_target_y(
    wind_state: dict[str, Any], y_min: int, y_max: int,
) -> int | None:
    commit = wind_state.get("coverage_y_commit")
    if commit == "north":
        return y_max - COVERAGE_Y_COMMIT_TARGET_MARGIN
    if commit == "south":
        return y_min + COVERAGE_Y_COMMIT_TARGET_MARGIN
    return None


def _coverage_y_force_min(wind_state: dict[str, Any], y_min: int, y_max: int) -> int | None:
    _update_coverage_y_commit(wind_state, y_min, y_max)
    return _coverage_y_commit_target_y(wind_state, y_min, y_max) if (
        wind_state.get("coverage_y_commit") == "north"
    ) else None


def _coverage_y_force_max(wind_state: dict[str, Any], y_min: int, y_max: int) -> int | None:
    _update_coverage_y_commit(wind_state, y_min, y_max)
    return _coverage_y_commit_target_y(wind_state, y_min, y_max) if (
        wind_state.get("coverage_y_commit") == "south"
    ) else None


def _finalize_coverage_target(
    target: tuple[float, float] | None,
    wind_state: dict[str, Any],
    *,
    x_min: int | None = None,
    y_min: int,
    y_max: int,
    x_max: int | None = None,
    ax: float | None = None,
    ay: float | None = None,
) -> tuple[float, float] | None:
    if target is None:
        return target
    tx = float(target[0])
    ty = float(target[1])
    safe_x_min = (
        _coverage_safe_x_min(x_min)
        if x_min is not None
        else COVERAGE_INTERIOR_X_MIN
    )
    safe_x_max = (
        _coverage_safe_x_max(x_max)
        if x_max is not None
        else COVERAGE_INTERIOR_X_MAX
    )
    if _coverage_mode_active(wind_state):
        tx = max(safe_x_min, min(safe_x_max, tx))
        wind_label = str(wind_state.get("last_wind_direction") or "").strip().lower()
        west_goal = float(safe_x_min + COVERAGE_SWEEP_BAND_MARGIN)
        east_goal = float(safe_x_max - COVERAGE_SWEEP_BAND_MARGIN)
        if wind_label == "west":
            _mark_x_strip_progress(wind_state, safe_x_min, safe_x_max)
            if (
                _west_sweep_pending(wind_state, safe_x_min)
                and ax is not None
                and float(ax) > safe_x_min + 4
            ):
                tx = min(tx, west_goal)
            elif (
                _east_sweep_pending(wind_state, safe_x_max)
                and _allow_east_force(wind_state)
                and ax is not None
                and float(ax) < safe_x_max - 4
            ):
                tx = max(tx, east_goal)
        else:
            x_lo, x_hi = _coverage_x_span(wind_state)
            if (
                x_lo is not None
                and x_lo > safe_x_min + 3
                and ax is not None
                and float(ax) > safe_x_min + 4
            ):
                tx = min(tx, west_goal)
            elif (
                x_hi is not None
                and x_hi < safe_x_max - 3
                and ax is not None
                and float(ax) < safe_x_max - 4
            ):
                tx = max(tx, east_goal)
    if int(wind_state.get("unresolved_victim_count", 0) or 0) > 0:
        if ay is not None:
            _update_coverage_y_commit(wind_state, y_min, y_max, float(ay))
        else:
            _update_coverage_y_commit(wind_state, y_min, y_max)
    commit = wind_state.get("coverage_y_commit")
    if commit in ("north", "south"):
        forced_y = _coverage_y_commit_target_y(wind_state, y_min, y_max)
        if commit == "north" and forced_y is not None:
            ty = max(float(forced_y), ty)
        elif commit == "south" and forced_y is not None:
            ty = min(float(forced_y), ty)
    return (tx, ty)


def _record_victim_searcher_x_band(
    wind_state: dict[str, Any],
    agent_x: int | float | None,
    agent_y: int | float | None = None,
) -> None:
    if agent_x is not None:
        recent = list(wind_state.get("recent_x_positions") or [])
        recent.append(int(round(float(agent_x))))
        wind_state["recent_x_positions"] = recent[-30:]
    if agent_y is not None:
        recent_y = list(wind_state.get("recent_y_positions") or [])
        recent_y.append(int(round(float(agent_y))))
        wind_state["recent_y_positions"] = recent_y[-30:]


def _update_unresolved_coverage_state(
    simulation: Any | None,
    wind_state: dict[str, Any],
    *,
    agent_x: int | float | None = None,
    agent_y: int | float | None = None,
) -> None:
    wind_state["unresolved_victim_count"] = _count_unresolved_victims(simulation)
    post_rescue = int(wind_state.get("post_rescue_coverage_steps_remaining", 0) or 0)
    if post_rescue > 0:
        wind_state["post_rescue_coverage_steps_remaining"] = post_rescue - 1
    if agent_x is not None or agent_y is not None:
        _record_victim_searcher_x_band(wind_state, agent_x, agent_y)


def _apply_unresolved_coverage_mode(wind_state: dict[str, Any]) -> bool:
    if not _coverage_mode_active(wind_state):
        return False
    wind_state["coverage_priority"] = max(
        float(wind_state.get("coverage_priority", 0.0) or 0.0),
        0.9,
    )
    wind_state["force_coverage_escape"] = True
    wind_state["force_interior_retarget"] = True
    wind_state["force_sweep"] = False
    return True


def _coverage_priority(wind_state: dict[str, Any]) -> float:
    base = float(wind_state.get("coverage_priority", 0.0) or 0.0)
    steps = int(wind_state.get("steps_since_detection", 0) or 0)
    detections = int(wind_state.get("searcher_victim_detections", 0) or 0)
    boost = float(wind_state.get("fire_tracker_detection_boost", 0.0) or 0.0)
    if detections <= 0 and steps >= NO_VICTIM_DETECT_BOOST_AFTER:
        base = max(base, 0.55)
    if bool(wind_state.get("force_coverage_escape")):
        base = max(base, 0.85)
    if int(wind_state.get("post_rescue_coverage_steps_remaining", 0) or 0) > 0:
        base = max(base, 0.85)
    if int(wind_state.get("unresolved_victim_count", 0) or 0) > 0 and _coverage_mode_active(
        wind_state
    ):
        base = max(base, 0.9)
    return min(1.5, base + boost)


def _score_hybrid_search_cell(
    *,
    cx: int,
    cy: int,
    downwind: float,
    hazard_dist: float,
    smoke_dist: float,
    dist_agent: float,
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    runtime_models: Any,
    simulation: Any | None,
    uav_id: str,
    wind_state: dict[str, Any],
) -> float | None:
    coverage_w = _coverage_priority(wind_state)
    unresolved = int(wind_state.get("unresolved_victim_count", 0) or 0)
    if coverage_w >= 0.9 or unresolved > 0:
        wind_w = HYBRID_WIND_WEIGHT * 0.15
    else:
        wind_w = HYBRID_WIND_WEIGHT * max(0.15, 1.0 - coverage_w * 0.65)
    if unresolved > 0:
        wind_w *= 0.35
    capped_downwind = min(max(0.0, float(downwind)), WIND_DOWNWIND_CAP)
    score = capped_downwind * 3.0 * wind_w
    score += min(hazard_dist, smoke_dist) * HYBRID_HAZARD_WEIGHT
    score += _interior_margin_score(cx, cy, x_min, x_max, y_min, y_max)
    score += _victim_likelihood_score(runtime_models, cx, cy)
    coverage_pen = _observation_coverage_penalty(runtime_models, cx, cy)
    score -= coverage_pen * HYBRID_COVERAGE_WEIGHT * (1.0 + coverage_w)
    if coverage_w >= 0.55 or unresolved > 0:
        score += _never_seen_proximity_bonus(runtime_models, cx, cy) * (1.0 + coverage_w)
    if unresolved > 0:
        score += _uncovered_region_bonus(
            cx, cy, wind_state, x_min, x_max, y_min, y_max,
        )
    score -= _pocket_penalty(wind_state, cx, cy)
    if _cell_on_edge(cx, cy, x_min, x_max, y_min, y_max, margin=WIND_INTERIOR_MARGIN):
        score -= WIND_EDGE_PENALTY
    visit_pen = _visit_count_for_cell(simulation, uav_id, cx, cy)
    score -= visit_pen * WIND_VISIT_PENALTY_SCALE
    score -= _recent_target_penalty(wind_state, cx, cy)
    score -= dist_agent * 0.1
    if dist_agent <= 2.0:
        score -= WIND_REACHED_PENALTY
    elif dist_agent <= 4.0:
        score -= WIND_REACHED_PENALTY * 0.45
    if bool(wind_state.get("force_coverage_escape")):
        center = wind_state.get("pocket_center")
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            score += (abs(cx - int(center[0])) + abs(cy - int(center[1]))) * 0.35
    return score


def _update_pocket_and_coverage_state(
    wind_state: dict[str, Any],
    grid_position: tuple[int, int] | None,
    step_index: int,
) -> None:
    if grid_position is None:
        return
    last_pos = wind_state.get("last_committed_position")
    if last_pos == grid_position:
        wind_state["sweep_no_move_streak"] = int(wind_state.get("sweep_no_move_streak", 0) or 0) + 1
    else:
        wind_state["sweep_no_move_streak"] = 0
        wind_state["last_committed_position"] = grid_position

    anchor = wind_state.get("pocket_anchor")
    gx, gy = int(grid_position[0]), int(grid_position[1])
    if not isinstance(anchor, (list, tuple)) or len(anchor) < 2:
        wind_state["pocket_anchor"] = grid_position
        wind_state["pocket_center"] = grid_position
        wind_state["pocket_streak"] = 1
    else:
        ax, ay = int(anchor[0]), int(anchor[1])
        if abs(gx - ax) <= 2 and abs(gy - ay) <= 2:
            wind_state["pocket_streak"] = int(wind_state.get("pocket_streak", 0) or 0) + 1
            wind_state["pocket_center"] = anchor
        else:
            wind_state["pocket_anchor"] = grid_position
            wind_state["pocket_center"] = grid_position
            wind_state["pocket_streak"] = 1
            wind_state["escape_target"] = None

    pocket = int(wind_state.get("pocket_streak", 0) or 0)
    no_move = int(wind_state.get("sweep_no_move_streak", 0) or 0)
    wind_state["steps_since_detection"] = int(wind_state.get("steps_since_detection", 0) or 0) + 1
    steps = int(wind_state.get("steps_since_detection", 0) or 0)
    if int(wind_state.get("searcher_victim_detections", 0) or 0) <= 0 and steps >= 25 and steps % 25 == 0:
        wind_state["force_coverage_escape"] = True
        wind_state["coverage_priority"] = max(float(wind_state.get("coverage_priority", 0.0) or 0.0), 0.65)
    boost = float(wind_state.get("fire_tracker_detection_boost", 0.0) or 0.0)
    if boost >= 0.06 and int(wind_state.get("searcher_victim_detections", 0) or 0) <= 0:
        wind_state["force_coverage_escape"] = True
        wind_state["coverage_priority"] = max(float(wind_state.get("coverage_priority", 0.0) or 0.0), 0.7)

    if pocket >= WIND_POCKET_CAMP_THRESHOLD or no_move >= WIND_SWEEP_NO_MOVE_ESCAPE:
        wind_state["force_coverage_escape"] = True
        wind_state["force_interior_retarget"] = True
        wind_state["force_sweep"] = False
        if pocket >= WIND_POCKET_CAMP_THRESHOLD:
            wind_state["hazard_buffer_level"] = 2 if pocket >= WIND_POCKET_CAMP_THRESHOLD + 15 else 1
            _blacklist_target_neighborhood(
                wind_state,
                (float(grid_position[0]), float(grid_position[1])),
                step_index,
            )
        wind_state["coverage_priority"] = max(
            float(wind_state.get("coverage_priority", 0.0) or 0.0),
            0.75,
        )
    elif pocket < 5:
        anchor = wind_state.get("pocket_anchor")
        if isinstance(anchor, (list, tuple)) and len(anchor) >= 2 and grid_position is not None:
            dist = abs(grid_position[0] - int(anchor[0])) + abs(grid_position[1] - int(anchor[1]))
            if dist > 6:
                wind_state["force_coverage_escape"] = False
                wind_state["pocket_anchor"] = None
                wind_state["escape_target"] = None
                if int(wind_state.get("hazard_buffer_level", 0) or 0) < 2:
                    wind_state["hazard_buffer_level"] = 0


def _gradual_escape_target(
    ax: float,
    ay: float,
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    fire_cells: set[tuple[int, int]],
    smoke_cells: set[tuple[int, int]],
    step: float = 12.0,
) -> tuple[float, float]:
    cx = float((x_min + x_max) // 2)
    cy = float((y_min + y_max) // 2)
    dx, dy = cx - ax, cy - ay
    dist = abs(dx) + abs(dy)
    if dist <= 1.0:
        return (cx, cy)
    scale = min(1.0, step / dist)
    tx = int(round(ax + dx * scale))
    ty = int(round(ay + dy * scale))
    tx = max(x_min + 1, min(x_max - 1, tx))
    ty = max(y_min + 1, min(y_max - 1, ty))
    if (tx, ty) in fire_cells or (tx, ty) in smoke_cells:
        for direction in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = tx + direction[0], ty + direction[1]
            if (nx, ny) not in fire_cells and (nx, ny) not in smoke_cells:
                return (float(nx), float(ny))
    return (float(tx), float(ty))


def _opposite_quadrant_escape_target(
    wind_state: dict[str, Any],
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    fire_cells: set[tuple[int, int]],
    smoke_cells: set[tuple[int, int]],
) -> tuple[float, float] | None:
    center = wind_state.get("pocket_center")
    if not isinstance(center, (list, tuple)) or len(center) < 2:
        mid_x = (x_min + x_max) // 2
        mid_y = (y_min + y_max) // 2
        return (float(mid_x), float(mid_y))
    pcx, pcy = int(center[0]), int(center[1])
    margin = WIND_INTERIOR_MARGIN
    tx = x_max - margin if pcx < (x_min + x_max) // 2 else x_min + margin
    ty = y_max - margin if pcy < (y_min + y_max) // 2 else y_min + margin
    candidates = [
        (tx, ty),
        (tx, (y_min + y_max) // 2),
        ((x_min + x_max) // 2, ty),
        ((x_min + x_max) // 2, (y_min + y_max) // 2),
    ]
    for cx, cy in candidates:
        if (cx, cy) not in fire_cells and (cx, cy) not in smoke_cells:
            return (float(cx), float(cy))
    return (float(tx), float(ty))


def _touch_wind_search_dwell(
    wind_state: dict[str, Any],
    uav_pos: tuple[float, float] | None,
    target: tuple[float, float] | None,
    step_index: int,
) -> None:
    if uav_pos is None or target is None:
        return
    ax, ay = float(uav_pos[0]), float(uav_pos[1])
    tx, ty = float(target[0]), float(target[1])
    dist = _manhattan(ax, ay, tx, ty)
    current = wind_state.get("current_target")
    if current != (tx, ty):
        wind_state["current_target"] = (tx, ty)
        wind_state["dwell_count"] = 0
    if dist <= 2.0:
        wind_state["dwell_count"] = int(wind_state.get("dwell_count", 0) or 0) + 1
    else:
        wind_state["dwell_count"] = 0
    if int(wind_state.get("dwell_count", 0) or 0) >= WIND_SATURATE_DWELL_STEPS:
        saturated = wind_state.setdefault("saturated_until", {})
        saturated[(int(round(tx)), int(round(ty)))] = (
            int(step_index) + WIND_SATURATE_COOLDOWN_STEPS
        )
        wind_state["dwell_count"] = 0


def _record_wind_search_target(
    wind_state: dict[str, Any],
    target: tuple[float, float],
) -> None:
    tx, ty = float(target[0]), float(target[1])
    rounded = (tx, ty)
    wind_state["current_target"] = rounded
    recent = list(wind_state.get("recent_targets") or [])
    recent = [item for item in recent if item != rounded]
    recent.insert(0, rounded)
    wind_state["recent_targets"] = recent[:WIND_RECENT_TARGET_HISTORY]


def _distance_to_boundary(
    cx: int,
    cy: int,
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
) -> int:
    return min(cx - x_min, x_max - cx, cy - y_min, y_max - cy)


def _south_edge_extra_penalty(
    wind_direction: str,
    cy: int,
    y_min: int,
    wind_state: dict[str, Any],
) -> float:
    if normalize_wind_direction(wind_direction) != "south":
        return 0.0
    penalty = 0.0
    if cy <= y_min + 1:
        penalty += WIND_SOUTH_EDGE_PENALTY
    recent_corridor = wind_state.get("recent_corridor_targets") or []
    southern_hits = sum(
        1
        for item in recent_corridor
        if isinstance(item, (list, tuple))
        and len(item) >= 2
        and int(round(float(item[1]))) <= y_min + 1
    )
    penalty += southern_hits * (WIND_SOUTH_EDGE_PENALTY * 0.35)
    return penalty


def _min_smoke_distance(cell: tuple[int, int], smoke_cells: set[tuple[int, int]]) -> float:
    if not smoke_cells:
        return 99.0
    cx, cy = cell
    return float(min(abs(cx - sx) + abs(cy - sy) for sx, sy in smoke_cells))


def _corridor_front_distance_penalty(fire_dist: float, smoke_dist: float) -> float:
    front = min(fire_dist, smoke_dist)
    penalty = 0.0
    if front < WIND_FIRE_FRONT_MIN_DISTANCE:
        penalty += (WIND_FIRE_FRONT_MIN_DISTANCE - front) * 14.0
    if front < WIND_VICTIM_HAZARD_BUFFER:
        penalty += 50.0
    return penalty


def _downwind_edge_blocked(
    wind_direction: str, cx: int, cy: int, x_min: int, x_max: int, y_min: int, y_max: int,
) -> bool:
    w = normalize_wind_direction(wind_direction)
    if w == "north" and cy >= y_max - 3:
        return True
    if w == "south" and cy <= y_min + 2:
        return True
    if w == "east" and cx >= x_max - 4:
        return True
    if w == "west" and cx <= x_min + 3:
        return True
    return False


def _east_edge_extra_penalty(wind_direction: str, cx: int, x_max: int) -> float:
    if normalize_wind_direction(wind_direction) != "east":
        return 0.0
    if cx >= x_max - (WIND_EAST_INTERIOR_MARGIN - 1):
        return WIND_EDGE_PENALTY * 2.5
    return 0.0


def _blacklist_target_neighborhood(
    wind_state: dict[str, Any], target: tuple[float, float] | None, step_index: int,
) -> None:
    if target is None:
        return
    tx, ty = int(round(float(target[0]))), int(round(float(target[1])))
    saturated = wind_state.setdefault("saturated_until", {})
    until = int(step_index) + WIND_TARGET_BLACKLIST_COOLDOWN
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            saturated[(tx + dx, ty + dy)] = until


def _reset_corridor_on_same_target_streak(
    wind_state: dict[str, Any], step_index: int, current_target: tuple[float, float] | None,
) -> None:
    _blacklist_target_neighborhood(wind_state, current_target, step_index)
    wind_state["corridor_index"] = 0
    wind_state["corridor_targets"] = []
    wind_state["same_target_streak"] = 0
    wind_state["force_interior_retarget"] = True
    wind_state["last_rounded_target"] = None


def _sync_wind_search_streaks(
    wind_state: dict[str, Any],
    *,
    grid_position: tuple[int, int] | None,
    action: str | None,
    target: tuple[float, float] | None,
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    wind_aware_active: bool = False,
    step_index: int = 0,
) -> None:
    if grid_position is not None:
        on_edge = _cell_on_edge(
            grid_position[0],
            grid_position[1],
            x_min,
            x_max,
            y_min,
            y_max,
        )
        if on_edge:
            wind_state["edge_streak"] = int(wind_state.get("edge_streak", 0) or 0) + 1
        else:
            wind_state["edge_streak"] = 0

    action_label = str(action or "").strip().lower()
    if action_label == "hold":
        wind_state["hold_streak"] = int(wind_state.get("hold_streak", 0) or 0) + 1
        if wind_aware_active:
            wind_state["wind_aware_hold_streak"] = (
                int(wind_state.get("wind_aware_hold_streak", 0) or 0) + 1
            )
    else:
        wind_state["hold_streak"] = 0
        if wind_aware_active or "wind_aware" in action_label:
            wind_state["wind_aware_hold_streak"] = 0

    rounded_target = None
    if target is not None:
        rounded_target = (int(round(float(target[0]))), int(round(float(target[1]))))
    prior_target = wind_state.get("last_rounded_target")
    if rounded_target is not None:
        if prior_target == rounded_target:
            wind_state["same_target_streak"] = (
                int(wind_state.get("same_target_streak", 0) or 0) + 1
            )
        else:
            wind_state["same_target_streak"] = 0
        wind_state["last_rounded_target"] = rounded_target

    edge_streak = int(wind_state.get("edge_streak", 0) or 0)
    hold_streak = int(wind_state.get("hold_streak", 0) or 0)
    same_target_streak = int(wind_state.get("same_target_streak", 0) or 0)
    wind_state["force_interior_retarget"] = (
        edge_streak > WIND_EDGE_STREAK_FORCE_RETARGET
        or hold_streak > WIND_HOLD_STREAK_FORCE_RETARGET
        or same_target_streak > WIND_SAME_TARGET_FORCE_RETARGET
        or int(wind_state.get("wind_aware_hold_streak", 0) or 0) > WIND_MAX_WIND_AWARE_HOLDS
        or bool(wind_state.get("force_coverage_escape"))
    )
    wind_state["_last_step_index"] = int(step_index)
    _update_pocket_and_coverage_state(wind_state, grid_position, int(step_index))
    if bool(wind_state.get("force_coverage_escape")):
        wind_state["force_sweep"] = False
    else:
        wind_state["force_sweep"] = bool(
            wind_state.get("force_sweep")
            or edge_streak > WIND_EDGE_STREAK_FORCE_RETARGET + 5
            or hold_streak > WIND_HOLD_STREAK_FORCE_RETARGET + 3
        )
    if grid_position is not None:
        wind_state["last_grid_position"] = grid_position
        _record_victim_searcher_x_band(wind_state, grid_position[0], grid_position[1])
        _update_coverage_y_commit(
            wind_state,
            y_min,
            y_max,
            float(grid_position[1]),
        )
    if action is not None:
        wind_state["last_action"] = action_label


def _record_corridor_target(wind_state: dict[str, Any], target: tuple[float, float]) -> None:
    rounded = (float(target[0]), float(target[1]))
    recent = list(wind_state.get("recent_corridor_targets") or [])
    recent = [item for item in recent if item != rounded]
    recent.insert(0, rounded)
    wind_state["recent_corridor_targets"] = recent[:WIND_RECENT_TARGET_HISTORY]


def _advance_corridor_index(wind_state: dict[str, Any]) -> bool:
    corridor = list(wind_state.get("corridor_targets") or [])
    index = int(wind_state.get("corridor_index", 0) or 0)
    if not corridor:
        return False
    next_index = index + 1
    if next_index >= len(corridor):
        wind_state["force_sweep"] = True
        return False
    wind_state["corridor_index"] = next_index
    return True


class LocalAdaptationSpaceGenerator:
    """Builds local adaptation option spaces."""

    def _generate_local_noop_option(
        self,
        uav_id: str,
        timestamp: float,
        originating_trigger: str | None = None,
        *,
        mission_goals: dict[str, Any] | None = None,
    ) -> LocalAdaptationOption:
        trigger = (
            originating_trigger if originating_trigger is not None else "local_analysis"
        )
        goals = mission_goals or {}
        return self._build_local_adaptation_option(
            option_id=f"local_stability_maintain_current_config_{uav_id}",
            option_type="stability_control",
            target_entity=str(uav_id),
            parameters={
                "stability_action": "maintain_current_config",
                "do_nothing": True,
            },
            mission_goals=goals,
            reason="local_stability_baseline",
            action="maintain_current_config",
            expected_effect="Keep current local UAV configuration; no adaptation applied",
            cost_estimate=0.0,
            risk_estimate=0.0,
            confidence=1.0,
            timestamp=timestamp,
            originating_trigger=trigger,
            explanation_hint=(
                "Do-nothing local baseline; always present for stability comparison"
            ),
        )

    @staticmethod
    def _merge_mission_goal_parameters(
        parameters: dict[str, Any],
        mission_goals: dict[str, Any],
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        merged = dict(parameters)
        merged.update(path_constraint_flags(merged))
        merged.update(mission_goal_option_metadata(mission_goals, reason=reason))
        return merged

    @staticmethod
    def _adjust_option_confidence(
        confidence: float,
        mission_goals: dict[str, Any],
        *,
        action: str,
        parameters: dict[str, Any],
    ) -> float:
        if not mission_goals:
            return confidence
        adjusted = confidence
        if goal_priority_enabled(mission_goals, "prioritize_victim_search") and (
            parameters.get("victim_search")
            or action in {
                "victim_search_wind_aware",
                "move_toward_victim_candidate",
                "focus_sensing_on_victim_confirmation",
            }
        ):
            adjusted = boost_confidence(adjusted, 0.12)
        if goal_priority_enabled(mission_goals, "prioritize_fire_perimeter_tracking") and (
            parameters.get("fire_front_target")
            or action.startswith("move_toward_fire")
            or action == "revisit_high_probability_hidden_regions"
            or action == "directed_search_last_known_fire_location"
            or action == "focus_sensing_on_fire_belief"
        ):
            adjusted = boost_confidence(adjusted, 0.1)
        survivability_actions = {
            "avoid_smoke",
            "avoid_collision",
            "avoid_high_drift",
            "hold_current_path",
            "cautious_movement",
            "hold_position",
            "drift_aware_movement",
            "smooth_transition_movement",
            "keep_current_path",
            "keep_current_assignment",
            "do_nothing",
            "delayed_adaptation",
            "gradual_adaptation",
            "partial_adaptation",
            "reduced_communication",
            "maintain_current_sensing",
            "reduce_sensing_battery_save",
        }
        if goal_priority_enabled(mission_goals, "prioritize_uav_survivability") and action in (
            survivability_actions
        ):
            adjusted = boost_confidence(adjusted, 0.08)
        information_actions = {
            "maximize_information_gain",
            "maximize_belief_gain",
            "explore_unknown_region",
            "focus_sensing_on_uncertainty",
            "increase_sensing_frequency",
            "focus_sensing_on_fire_belief",
            "adaptive_horizon",
            "increased_replanning_frequency",
            "short_horizon",
            "aggressive_exploration",
            "directed_belief_hotspot_search",
            "prioritize_critical_messages",
        }
        if goal_priority_enabled(mission_goals, "prioritize_information_gain") and action in (
            information_actions
        ):
            adjusted = boost_confidence(adjusted, 0.1)
        smoke_penalty = float(parameters.get("next_step_smoke_penalty", 0.0) or 0.0)
        if smoke_penalty >= 500.0:
            adjusted = max(0.05, adjusted - 0.35)
        elif smoke_penalty >= 100.0:
            adjusted = max(0.1, adjusted - 0.18)
        if parameters.get("greedy_step_would_enter_smoke"):
            adjusted = max(0.08, adjusted - 0.22)
        if parameters.get("flank_standoff_hold") and smoke_penalty <= 0.0:
            adjusted = boost_confidence(adjusted, 0.06)
        return adjusted

    _adjust_path_confidence = _adjust_option_confidence

    def _build_local_adaptation_option(
        self,
        *,
        option_id: str,
        option_type: str,
        target_entity: str,
        parameters: dict[str, Any],
        mission_goals: dict[str, Any],
        reason: str,
        action: str,
        expected_effect: str,
        cost_estimate: float,
        risk_estimate: float,
        confidence: float,
        timestamp: float,
        originating_trigger: str,
        explanation_hint: str,
    ) -> LocalAdaptationOption:
        merged_parameters = self._merge_mission_goal_parameters(
            parameters,
            mission_goals,
            reason=reason,
        )
        return LocalAdaptationOption(
            option_id=option_id,
            option_type=option_type,
            target_entity=target_entity,
            parameters=merged_parameters,
            expected_effect=expected_effect,
            cost_estimate=cost_estimate,
            risk_estimate=risk_estimate,
            confidence=self._adjust_option_confidence(
                confidence,
                mission_goals,
                action=action,
                parameters=merged_parameters,
            ),
            scope=Scope.local,
            timestamp=timestamp,
            originating_trigger=originating_trigger,
            explanation_hint=explanation_hint,
        )

    def generate(
        self,
        local_analysis_result: Any,
        local_models: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> LocalAdaptationSpace:
        options: list[AdaptationOption] = []

        options.extend(
            self._generate_path_options(
                local_analysis_result,
                local_models,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_horizon_options(
                local_analysis_result,
                local_models,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_movement_strategy_options(
                local_analysis_result,
                local_models,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_sensing_options(
                local_analysis_result,
                local_models,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_communication_options(
                local_analysis_result,
                local_models,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_stability_options(
                local_analysis_result,
                local_models,
                runtime_models,
                timestamp,
            )
        )

        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        uav_id = str(
            read_value(
                local_analysis_result,
                "target_entity",
                read_value(runtime_models, "uav_id", "local_uav"),
            )
        )
        options.append(
            self._generate_local_noop_option(
                uav_id,
                timestamp,
                None,
                mission_goals=read_mission_goals(runtime_models),
            )
        )

        return LocalAdaptationSpace(
            options=options,
            trigger_references=[],
            explanation_summaries=[],
            timestamp=timestamp,
        )

    def _generate_path_options(
        self,
        local_analysis_result: Any,
        local_models: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            local_analysis_result,
            default_label="local_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        local_uncertainty = read_value(
            local_analysis_result,
            "local_uncertainty",
            read_value(local_models, "local_uncertainty", {}),
        )
        belief_gain = read_value(
            local_analysis_result,
            "belief_gain",
            read_value(local_models, "belief_gain", {}),
        )
        negative_observations = read_value(
            local_analysis_result,
            "negative_observations",
            read_value(local_models, "negative_observations", {}),
        )
        hidden_fire_regions = read_value(
            local_analysis_result,
            "high_probability_hidden_regions",
            read_value(local_models, "high_probability_hidden_regions", []),
        )
        last_known_fire_location = read_value(
            local_analysis_result,
            "last_known_fire_location",
            read_value(local_models, "last_known_fire_location", None),
        )
        target_entity = read_value(
            local_analysis_result,
            "target_entity",
            read_value(runtime_models, "uav_id", "local_uav"),
        )
        base_parameters = {
            "local_uncertainty": local_uncertainty,
            "belief_gain": belief_gain,
            "negative_observations": negative_observations,
            **mission_goal_option_metadata(
                read_mission_goals(runtime_models),
                reason="local_path_options",
            ),
        }
        mission_goals = read_mission_goals(runtime_models)
        uav_id = str(target_entity)
        current_role = self._read_uav_role(runtime_models, uav_id)
        if current_role in ("victim_searcher", "victim_search"):
            live_victim_targets = self._collect_active_live_victim_targets(
                runtime_models
            )
            if live_victim_targets:
                victim_path_options = self._build_path_options_toward_targets(
                    live_victim_targets,
                    target_entity,
                    base_parameters,
                    confidence,
                    originating_trigger,
                    timestamp,
                    current_role,
                    mission_goals=mission_goals,
                )
                victim_path_options.append(
                    self._generate_local_noop_option(
                        uav_id,
                        timestamp,
                        originating_trigger,
                    )
                )
                return victim_path_options
            wind_option = self._try_generate_wind_aware_victim_search_option(
                uav_id=uav_id,
                target_entity=target_entity,
                base_parameters=base_parameters,
                confidence=confidence,
                originating_trigger=originating_trigger,
                timestamp=timestamp,
                current_role=current_role,
                runtime_models=runtime_models,
                mission_goals=mission_goals,
            )
            victim_search_options: list[AdaptationOption] = []
            if wind_option is not None:
                victim_search_options.append(wind_option)
            victim_search_options.append(
                self._generate_local_noop_option(
                    uav_id,
                    timestamp,
                    originating_trigger,
                )
            )
            return victim_search_options

        generated: list[AdaptationOption] = []
        fire_probability_map = self._read_fire_probability_map(runtime_models)
        negative_observation_map = (
            negative_observations if isinstance(negative_observations, dict) else {}
        )
        front_cells, all_high_cells = self._classify_fire_cells(
            fire_probability_map,
            negative_observation_map,
            runtime_models=runtime_models,
        )
        if front_cells:
            if current_role == "fire_tracker":
                preferred_fire_cells = self._prefer_flank_perimeter_cells(
                    front_cells,
                    fire_probability_map,
                    negative_observation_map,
                    runtime_models=runtime_models,
                )
            else:
                preferred_fire_cells = front_cells
        else:
            preferred_fire_cells = all_high_cells
        fire_target_cells: list[tuple[int, int]] = []
        for cell in preferred_fire_cells:
            normalized_cell = self._normalize_cell_pos(cell)
            if normalized_cell is not None:
                fire_target_cells.append(normalized_cell)
        fire_target_cells, sector_params = self._assign_sector_targets(
            fire_target_cells,
            uav_id,
            runtime_models,
        )
        if current_role == "fire_tracker" and fire_target_cells:
            fire_target_cells, _fire_tracker_meta = self._resolve_fire_tracker_target_cells(
                fire_target_cells,
                runtime_models=runtime_models,
                uav_id=uav_id,
                fire_probability_map=fire_probability_map,
            )
            if fire_target_cells:
                fire_target_cells, sector_params = self._assign_sector_targets(
                    fire_target_cells,
                    uav_id,
                    runtime_models,
                )
        front_cell_set = {self._normalize_cell_pos(cell) for cell in front_cells}

        path_options: list[tuple[str, str, dict[str, Any], str]] = []
        for index, normalized_cell in enumerate(fire_target_cells[:5]):
            is_front = normalized_cell in front_cell_set
            overlap_penalty = float(
                negative_observation_map.get(
                    normalized_cell,
                    negative_observation_map.get(cell, 0.0),
                )
                or 0.0
            )
            if current_role == "fire_tracker":
                option_params = self._fire_tracker_path_parameters(
                    normalized_cell,
                    runtime_models=runtime_models,
                    uav_id=uav_id,
                    fire_probability_map=fire_probability_map,
                    is_front=is_front,
                    overlap_penalty=overlap_penalty,
                    sector_params=sector_params,
                )
                path_options.append(
                    (
                        f"move_toward_fire_{'front' if is_front else 'high'}_{index}",
                        f"move_toward_fire_{'front' if is_front else 'high'}",
                        option_params,
                        "Move toward smoke-free flank hold outside fire/smoke",
                    )
                )
                continue
            path_options.append(
                (
                    f"move_toward_fire_{'front' if is_front else 'high'}_{index}",
                    f"move_toward_fire_{'front' if is_front else 'high'}",
                    {
                        "target_region": normalized_cell,
                        "target_position": normalized_cell,
                        "fire_front_target": is_front,
                        "overlap_penalty": overlap_penalty,
                        "already_observed_penalty": overlap_penalty,
                        **sector_params,
                    },
                    (
                        "Move toward fire-front cell"
                        if is_front
                        else "Move toward high-probability fire cell"
                    ),
                )
            )

        _vis = (
            runtime_models.get("visibility_model")
            if isinstance(runtime_models, dict)
            else getattr(runtime_models, "visibility_model", None)
        )
        _explore_target: tuple[float, float] | None = None
        if _vis is not None:
            _obs_map = getattr(_vis, "observation_status_map", None)
            if not _obs_map:
                _state = getattr(_vis, "state", None)
                if _state is not None:
                    _obs_map = getattr(_state, "observation_status_map", {}) or {}
            if not _obs_map:
                _obs_map = {}
            _never_seen: list[tuple[int, int]] = []
            for _cp, _st in _obs_map.items():
                _st_str = (_st.value if hasattr(_st, "value") else str(_st)).lower()
                if "never_seen" in _st_str or "stale" in _st_str:
                    try:
                        _never_seen.append((int(_cp[0]), int(_cp[1])))
                    except Exception:
                        continue
            if _never_seen:
                _exp_cells, _ = self._assign_sector_targets(
                    _never_seen, uav_id, runtime_models
                )
                if _exp_cells:
                    _explore_target = (float(_exp_cells[0][0]), float(_exp_cells[0][1]))

        if _explore_target is not None:
            _exp_params = {
                "target_position": _explore_target,
                "target_region": f"{_explore_target[0]},{_explore_target[1]}",
                "expected_info_gain": 0.75,
                "belief_gain": 0.55,
                "task_support": 0.45,
                "stability_bonus": 0.2,
                "recovery_value": 0.35,
                "explore_unknown_region": True,
                "sector_assigned": True,
            }
            generated.append(
                LocalAdaptationOption(
                    option_id=f"explore_unknown_region_{uav_id}_{timestamp:.0f}",
                    option_type="explore_unknown_region",
                    target_entity=uav_id,
                    parameters=self._merge_mission_goal_parameters(
                        _exp_params,
                        mission_goals,
                        reason="information_recovery_explore",
                    ),
                    expected_effect="Move toward unvisited grid region",
                    cost_estimate=0.15,
                    risk_estimate=0.08,
                    confidence=self._adjust_path_confidence(
                        confidence,
                        mission_goals,
                        action="explore_unknown_region",
                        parameters=_exp_params,
                    ),
                    scope=Scope.local,
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint="Explore unvisited region alongside fire tracking",
                )
            )

        explore_path_option: tuple[str, str, dict[str, Any], str] | None = None
        if not fire_target_cells:
            vis = (
                runtime_models.get("visibility_model")
                if isinstance(runtime_models, dict)
                else getattr(runtime_models, "visibility_model", None)
            )
            explore_cells: list[tuple[int, int]] = []
            if vis is not None:
                obs_map = getattr(vis, "observation_status_map", None)
                if not obs_map:
                    _vis_state = getattr(vis, "state", None)
                    if _vis_state is not None:
                        obs_map = getattr(_vis_state, "observation_status_map", {}) or {}
                if not obs_map:
                    obs_map = {}
                for cell_pos, status in obs_map.items():
                    status_str = (
                        status.value if hasattr(status, "value") else str(status)
                    ).lower()
                    if "never_seen" in status_str or "stale" in status_str:
                        try:
                            explore_cells.append(
                                (int(cell_pos[0]), int(cell_pos[1]))
                            )
                        except Exception:
                            continue
            if explore_cells:
                explore_cells, _ = self._assign_sector_targets(
                    explore_cells, uav_id, runtime_models
                )
                if explore_cells:
                    tgt = explore_cells[0]
                    explore_path_option = (
                        "explore_unknown_region_0",
                        "explore_unknown_region",
                        {
                            "target_region": tgt,
                            "target_position": (float(tgt[0]), float(tgt[1])),
                            "expected_info_gain": 0.7,
                            "task_support": 0.5,
                        },
                        "Explore unknown region",
                    )
        if explore_path_option is not None:
            path_options.append(explore_path_option)

        belief_cells: list[tuple[int, int]] = []
        for source in (belief_gain, local_uncertainty):
            if not isinstance(source, dict):
                continue
            for key in source:
                normalized_cell = self._normalize_cell_pos(key)
                if normalized_cell is not None:
                    belief_cells.append(normalized_cell)
        belief_target_cells, belief_sector_params = self._assign_sector_targets(
            belief_cells,
            uav_id,
            runtime_models,
        )
        belief_target_position = (
            belief_target_cells[0]
            if belief_target_cells
            else LocalAdaptationSpaceGenerator._first_coord_from_map(belief_gain)
            or LocalAdaptationSpaceGenerator._first_coord_from_map(local_uncertainty)
        )

        path_options.extend([
            ("hold_current_path", "hold_current_path", {}, "Hold current path"),
            ("recompute_path", "recompute_path", {}, "Recompute local path"),
            ("avoid_smoke", "avoid_smoke", {}, "Adapt path to avoid smoke"),
            ("avoid_high_drift", "avoid_high_drift", {}, "Adapt path to avoid high drift"),
            ("avoid_collision", "avoid_collision", {}, "Adapt path to avoid collision risk"),
            (
                "maximize_information_gain",
                "maximize_information_gain",
                {"target_source": "local_uncertainty"},
                "Adapt path to maximize information gain",
            ),
            (
                "maximize_belief_gain",
                "maximize_belief_gain",
                {
                    "target_source": "belief_gain",
                    "target_position": belief_target_position,
                    "target_regions": belief_target_cells,
                    **belief_sector_params,
                },
                "Adapt path to maximize belief gain",
            ),
            (
                "revisit_high_probability_hidden_regions",
                "revisit_high_probability_hidden_regions",
                {
                    "target_regions": fire_target_cells
                    if fire_target_cells
                    else hidden_fire_regions,
                    "fire_front_target": bool(front_cells),
                    "overlap_penalty": sum(
                        float(negative_observation_map.get(cell, 0.0) or 0.0)
                        for cell in fire_target_cells[:5]
                    ),
                    **sector_params,
                },
                "Revisit high-probability hidden regions",
            ),
            (
                "directed_search_last_known_fire_location",
                "directed_search_last_known_fire_location",
                {
                    "target_location": (
                        fire_target_cells[0]
                        if fire_target_cells
                        else last_known_fire_location
                    ),
                    "fire_front_target": bool(front_cells),
                    **sector_params,
                },
                "Search toward last-known fire location",
            ),
            (
                "avoid_redundant_scanning_negative_observations",
                "avoid_redundant_scanning_negative_observations",
                {"avoid_source": "negative_observations"},
                "Avoid redundant scanning using negative observations",
            ),
        ])

        for option_id, action, parameters, expected_effect in path_options:
            if current_role == "fire_tracker":
                parameters = self._sanitize_fire_tracker_path_parameters(
                    parameters,
                    runtime_models=runtime_models,
                    uav_id=uav_id,
                    fire_probability_map=fire_probability_map,
                )
            merged_parameters = self._merge_mission_goal_parameters(
                {**base_parameters, **parameters, "path_action": action},
                mission_goals,
                reason="local_path_options",
            )
            generated.append(
                LocalAdaptationOption(
                    option_id=f"local_path_{option_id}",
                    option_type="path_planning",
                    target_entity=target_entity,
                    parameters=merged_parameters,
                    expected_effect=expected_effect,
                    cost_estimate=1.0,
                    risk_estimate=0.2,
                    confidence=self._adjust_path_confidence(
                        confidence,
                        mission_goals,
                        action=action,
                        parameters=merged_parameters,
                    ),
                    scope=Scope.local,
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint="Path planning option only; no UAV path is modified.",
                )
            )
        return generated

    @staticmethod
    def _get_team_size(runtime_models: Any) -> int:
        if isinstance(runtime_models, dict):
            entities = runtime_models.get("available_entities")
            resource_model = runtime_models.get("uav_resource_model")
        else:
            entities = getattr(runtime_models, "available_entities", None)
            resource_model = getattr(runtime_models, "uav_resource_model", None)
        if isinstance(entities, (list, tuple)) and entities:
            return len(entities)
        by_uav_id = getattr(resource_model, "by_uav_id", None) if resource_model is not None else None
        if isinstance(by_uav_id, dict) and by_uav_id:
            return len(by_uav_id)
        return 1

    @staticmethod
    def _get_uav_index(uav_id: str, runtime_models: Any) -> int:
        uav_key = str(uav_id)
        if isinstance(runtime_models, dict):
            entities = runtime_models.get("available_entities")
            resource_model = runtime_models.get("uav_resource_model")
        else:
            entities = getattr(runtime_models, "available_entities", None)
            resource_model = getattr(runtime_models, "uav_resource_model", None)
        if isinstance(entities, (list, tuple)) and entities:
            ordered = sorted(str(entity) for entity in entities)
            if uav_key in ordered:
                return ordered.index(uav_key)
        by_uav_id = getattr(resource_model, "by_uav_id", None) if resource_model is not None else None
        if isinstance(by_uav_id, dict) and by_uav_id:
            ordered = sorted(str(entity) for entity in by_uav_id.keys())
            if uav_key in ordered:
                return ordered.index(uav_key)
        team_size = LocalAdaptationSpaceGenerator._get_team_size(runtime_models)
        try:
            return int(uav_key) % max(team_size, 1)
        except ValueError:
            return 0

    def _fire_tracker_uav_ids(self, runtime_models: Any) -> list[str]:
        if isinstance(runtime_models, dict):
            resource_model = runtime_models.get("uav_resource_model")
            simulation = runtime_models.get("simulation_model")
        else:
            resource_model = getattr(runtime_models, "uav_resource_model", None)
            simulation = getattr(runtime_models, "simulation_model", None)
        ids: list[str] = []
        if resource_model is not None:
            by_uav_id = getattr(resource_model, "by_uav_id", None)
            if isinstance(by_uav_id, dict):
                for uid, state in by_uav_id.items():
                    role = getattr(state, "current_role", None)
                    if role is None and isinstance(state, dict):
                        role = state.get("current_role", state.get("role"))
                    if str(role or "").strip().lower() == "fire_tracker":
                        ids.append(str(uid))
        if not ids and simulation is not None:
            schedule = getattr(simulation, "schedule", None)
            if schedule is not None:
                import agents as agents_module

                for agent in getattr(schedule, "agents", ()) or ():
                    if type(agent) is agents_module.UAV:
                        uid = str(getattr(agent, "unique_id", ""))
                        if uid and self._read_uav_role(runtime_models, uid) == "fire_tracker":
                            ids.append(uid)
        return sorted(ids, key=lambda uid: int(uid) if uid.isdigit() else uid)

    def _assign_fire_tracker_flank_targets(
        self,
        target_cells: list[tuple[int, int]],
        uav_id: str,
        runtime_models: Any,
        sector_params: dict[str, Any],
    ) -> tuple[list[tuple[int, int]], dict[str, Any]]:
        if not target_cells:
            return [], sector_params
        tracker_ids = self._fire_tracker_uav_ids(runtime_models)
        cy = sum(cell[1] for cell in target_cells) / float(len(target_cells))
        if len(tracker_ids) <= 1:
            assigned = list(target_cells)
        else:
            try:
                idx = tracker_ids.index(str(uav_id))
            except ValueError:
                idx = self._get_uav_index(uav_id, runtime_models)
            if idx == 0:
                assigned = [cell for cell in target_cells if cell[1] <= cy]
            else:
                assigned = [cell for cell in target_cells if cell[1] > cy]
            if not assigned:
                assigned = list(target_cells)
        sector_params = dict(sector_params)
        sector_params["sector_assigned"] = len(tracker_ids) > 1
        sector_params["flank_split"] = "north_south"
        return assigned, sector_params

    def _assign_sector_targets(
        self,
        target_cells: list[tuple[int, int]],
        uav_id: str,
        runtime_models: Any,
    ) -> tuple[list[tuple[int, int]], dict[str, Any]]:
        smoke_cells = self._read_smoke_obscured_cells(runtime_models)
        filtered_cells = self._filter_smoke_cells(target_cells, smoke_cells)
        uav_index = self._get_uav_index(uav_id, runtime_models)
        n_uavs = self._get_team_size(runtime_models)
        sector_params = {
            "sector_assigned": n_uavs > 1,
            "sector_index": uav_index,
            "sector_count": n_uavs,
        }
        if not filtered_cells:
            return [], sector_params
        role = self._read_uav_role(runtime_models, uav_id)
        if str(role or "").strip().lower() == "fire_tracker":
            return self._assign_fire_tracker_flank_targets(
                filtered_cells, uav_id, runtime_models, sector_params
            )
        cx = sum(c[0] for c in filtered_cells) / len(filtered_cells)
        cy = sum(c[1] for c in filtered_cells) / len(filtered_cells)
        quadrants: dict[int, list[tuple[int, int]]] = {0: [], 1: [], 2: [], 3: []}
        for cell in filtered_cells:
            q = (0 if cell[0] <= cx else 1) + (0 if cell[1] <= cy else 2)
            quadrants[q].append(cell)
        assigned = quadrants.get(uav_index % 4, [])
        if not assigned:
            assigned = filtered_cells
        if n_uavs > 1:
            sector_params["sector_assigned"] = True
        return assigned, sector_params

    @staticmethod
    def _first_coord_from_map(value: object) -> tuple[float, float] | None:
        if not isinstance(value, dict) or not value:
            return None
        key = next(iter(value.keys()))
        if isinstance(key, (list, tuple)) and len(key) >= 2:
            try:
                return (float(key[0]), float(key[1]))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _read_fire_probability_map(runtime_models: Any) -> dict[Any, float]:
        if isinstance(runtime_models, dict):
            fire_runtime_model = runtime_models.get("fire_runtime_model")
        else:
            fire_runtime_model = getattr(runtime_models, "fire_runtime_model", None)
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
            prob = fire_probability_map.get((cell_pos[0], cell_pos[1]))
        if prob is None:
            return None
        return float(prob)

    @staticmethod
    def _is_fire_front_cell(
        cell_pos: Any,
        fire_probability_map: dict[Any, float],
        negative_observation_map: dict[Any, Any] | None = None,
        threshold: float = 0.3,
    ) -> bool:
        del negative_observation_map
        normalized = LocalAdaptationSpaceGenerator._normalize_cell_pos(cell_pos)
        if normalized is None:
            return False
        center_prob = LocalAdaptationSpaceGenerator._map_probability(
            fire_probability_map,
            normalized,
        )
        if center_prob is None or center_prob < threshold:
            return False
        x, y = normalized
        high_neighbors = 0
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            neighbor_prob = LocalAdaptationSpaceGenerator._map_probability(
                fire_probability_map,
                neighbor,
            )
            if neighbor_prob is not None and neighbor_prob >= threshold:
                high_neighbors += 1
        return high_neighbors < 4

    @staticmethod
    def _read_smoke_obscured_cells(runtime_models: Any | None) -> set[tuple[int, int]]:
        smoke_cells: set[tuple[int, int]] = set()
        if runtime_models is None:
            return smoke_cells
        if isinstance(runtime_models, dict):
            vis = runtime_models.get("visibility_model")
        else:
            vis = getattr(runtime_models, "visibility_model", None)
        if vis is None:
            return smoke_cells
        raw = getattr(vis, "smoke_obscured_cells", None)
        if raw is None:
            state = getattr(vis, "state", None)
            if state is not None:
                raw = getattr(state, "smoke_obscured_cells", None)
        if isinstance(raw, (set, frozenset, list, tuple)):
            for position in raw:
                if not isinstance(position, (list, tuple)) or len(position) < 2:
                    continue
                try:
                    smoke_cells.add((int(position[0]), int(position[1])))
                except (TypeError, ValueError):
                    continue
        return smoke_cells

    @staticmethod
    def _prefer_flank_perimeter_cells(
        front_cells: list[tuple[int, int]],
        fire_probability_map: dict[Any, float],
        negative_observation_map: dict[Any, Any] | None,
        *,
        runtime_models: Any | None = None,
        threshold: float = 0.3,
    ) -> list[tuple[int, int]]:
        """Order smoke-free front cells: lateral flank/perimeter ahead of downwind plume tip."""
        if len(front_cells) <= 1:
            return list(front_cells)

        cx = sum(cell[0] for cell in front_cells) / float(len(front_cells))
        cy = sum(cell[1] for cell in front_cells) / float(len(front_cells))
        wx, wy = 1.0, 0.0
        if runtime_models is not None:
            wind_obs = LocalAdaptationSpaceGenerator._resolve_wind_observation(
                runtime_models
            )
            if wind_obs is not None:
                _, wind_vec, _ = wind_obs
                wx = float(wind_vec[0])
                wy = float(wind_vec[1])
        mag = math.hypot(wx, wy)
        if mag < 1e-6:
            wx, wy = 1.0, 0.0
            mag = 1.0
        wx /= mag
        wy /= mag
        lateral_x, lateral_y = -wy, wx
        negative_map = negative_observation_map or {}

        scored: list[tuple[float, tuple[int, int]]] = []
        for cell in front_cells:
            dx = float(cell[0]) - cx
            dy = float(cell[1]) - cy
            lateral = abs(dx * lateral_x + dy * lateral_y)
            downwind = dx * wx + dy * wy
            prob = float(
                LocalAdaptationSpaceGenerator._map_probability(
                    fire_probability_map,
                    cell,
                )
                or 0.0
            )
            high_neighbors = 0
            x, y = cell
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                neighbor_prob = LocalAdaptationSpaceGenerator._map_probability(
                    fire_probability_map,
                    neighbor,
                )
                if neighbor_prob is not None and neighbor_prob >= threshold:
                    high_neighbors += 1
            overlap_penalty = float(
                negative_map.get(cell, negative_map.get((x, y), 0.0)) or 0.0
            )
            score = (
                lateral * 2.0
                - max(0.0, downwind) * 0.75
                - prob * 0.35
                - high_neighbors * 0.15
                - overlap_penalty * 0.1
            )
            scored.append((score, cell))

        scored.sort(key=lambda item: (-item[0], item[1][0], item[1][1]))
        return [cell for _, cell in scored]

    @staticmethod
    def _filter_smoke_cells(
        cells: list[tuple[int, int]],
        smoke_cells: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        if not smoke_cells:
            return list(cells)
        return [
            cell
            for cell in cells
            if LocalAdaptationSpaceGenerator._normalize_cell_pos(cell) not in smoke_cells
        ]

    @staticmethod
    def _cell_is_unsafe_for_fire_tracker(
        cell: tuple[int, int],
        *,
        smoke_cells: set[tuple[int, int]],
        fire_cells: set[tuple[int, int]],
        fire_probability_map: dict[Any, float] | None = None,
        fire_prob_threshold: float = 0.3,
    ) -> bool:
        if cell in fire_cells:
            return True
        if cell in smoke_cells:
            return True
        if fire_probability_map is not None:
            prob = LocalAdaptationSpaceGenerator._map_probability(
                fire_probability_map,
                cell,
            )
            if prob is not None and prob >= fire_prob_threshold:
                return True
        return False

    @staticmethod
    def _compute_flank_hold_standoff_cell(
        front_cell: tuple[int, int],
        *,
        fire_probability_map: dict[Any, float],
        smoke_cells: set[tuple[int, int]],
        fire_cells: set[tuple[int, int]],
        wind_vector: tuple[float, float],
        bounds: tuple[int, int, int, int],
        standoff: int = 2,
    ) -> tuple[int, int] | None:
        """Lateral/upwind smoke-free standoff from a fire-front cell for flank observation."""
        x_min, x_max, y_min, y_max = bounds
        wx = float(wind_vector[0])
        wy = float(wind_vector[1])
        mag = math.hypot(wx, wy)
        if mag < 1e-6:
            wx, wy = 1.0, 0.0
        else:
            wx /= mag
            wy /= mag
        lateral_x, lateral_y = -wy, wx
        fx, fy = front_cell

        candidates: list[tuple[int, int]] = []
        for dist in range(1, max(1, standoff) + 1):
            for sign in (1, -1):
                candidates.append(
                    (
                        int(round(fx + lateral_x * dist * sign)),
                        int(round(fy + lateral_y * dist * sign)),
                    )
                )
            candidates.append(
                (
                    int(round(fx - wx * dist)),
                    int(round(fy - wy * dist)),
                )
            )

        best: tuple[int, int] | None = None
        best_score = -1e18
        for cell in candidates:
            cx, cy = cell
            if cx < x_min or cx > x_max or cy < y_min or cy > y_max:
                continue
            if LocalAdaptationSpaceGenerator._cell_is_unsafe_for_fire_tracker(
                cell,
                smoke_cells=smoke_cells,
                fire_cells=fire_cells,
                fire_probability_map=fire_probability_map,
            ):
                continue
            prob = float(
                LocalAdaptationSpaceGenerator._map_probability(
                    fire_probability_map,
                    cell,
                )
                or 0.0
            )
            lateral = abs((cx - fx) * lateral_x + (cy - fy) * lateral_y)
            upwind = (cx - fx) * (-wx) + (cy - fy) * (-wy)
            score = lateral * 2.5 + max(0.0, upwind) * 1.5 - prob * 0.75
            if score > best_score:
                best_score = score
                best = cell
        return best

    @staticmethod
    def _find_nearest_smoke_free_cell(
        origin: tuple[int, int],
        *,
        smoke_cells: set[tuple[int, int]],
        fire_cells: set[tuple[int, int]],
        bounds: tuple[int, int, int, int],
        max_radius: int = 6,
    ) -> tuple[int, int] | None:
        x_min, x_max, y_min, y_max = bounds
        ox, oy = origin
        best: tuple[int, int] | None = None
        best_dist: int | None = None
        for radius in range(1, max_radius + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    cx, cy = ox + dx, oy + dy
                    if cx < x_min or cx > x_max or cy < y_min or cy > y_max:
                        continue
                    if (cx, cy) in smoke_cells or (cx, cy) in fire_cells:
                        continue
                    dist = abs(dx) + abs(dy)
                    if best_dist is None or dist < best_dist:
                        best_dist = dist
                        best = (cx, cy)
            if best is not None:
                return best
        return None

    @staticmethod
    def _pick_fire_tracker_smoke_safe_step(
        uav_pos: tuple[float, float],
        goal: tuple[int, int],
        *,
        smoke_cells: set[tuple[int, int]],
        fire_cells: set[tuple[int, int]],
        bounds: tuple[int, int, int, int],
        fire_probability_map: dict[Any, float] | None = None,
    ) -> tuple[tuple[int, int], bool, float]:
        """Return (move_target, next_step_is_smoke, smoke_penalty) for fire_tracker."""
        ux = int(round(float(uav_pos[0])))
        uy = int(round(float(uav_pos[1])))
        gx, gy = goal
        current = (ux, uy)
        if current == (gx, gy):
            in_smoke = current in smoke_cells
            return current, in_smoke, 1000.0 if in_smoke else 0.0

        x_min, x_max, y_min, y_max = bounds
        candidates: list[tuple[float, int, int, int]] = []
        for nx, ny in ((ux + 1, uy), (ux - 1, uy), (ux, uy + 1), (ux, uy - 1)):
            if nx < x_min or nx > x_max or ny < y_min or ny > y_max:
                continue
            if (nx, ny) in fire_cells:
                continue
            dist_goal = abs(nx - gx) + abs(ny - gy)
            smoke_penalty = 1000.0 if (nx, ny) in smoke_cells else 0.0
            fire_penalty = 0.0
            if fire_probability_map is not None:
                prob = LocalAdaptationSpaceGenerator._map_probability(
                    fire_probability_map,
                    (nx, ny),
                )
                if prob is not None and prob >= 0.3:
                    continue
            score = dist_goal + smoke_penalty + fire_penalty
            candidates.append((score, dist_goal, nx, ny))

        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
            chosen = (candidates[0][2], candidates[0][3])
            in_smoke = chosen in smoke_cells
            return chosen, in_smoke, 1000.0 if in_smoke else 0.0

        if not LocalAdaptationSpaceGenerator._cell_is_unsafe_for_fire_tracker(
            current,
            smoke_cells=smoke_cells,
            fire_cells=fire_cells,
            fire_probability_map=fire_probability_map,
        ):
            dist_hold = abs(ux - gx) + abs(uy - gy)
            if dist_hold <= 2:
                return current, False, 0.0

        if current not in smoke_cells and current not in fire_cells:
            return current, False, 0.0

        fallback = LocalAdaptationSpaceGenerator._find_nearest_smoke_free_cell(
            current,
            smoke_cells=smoke_cells,
            fire_cells=fire_cells,
            bounds=bounds,
        )
        if fallback is not None:
            return fallback, False, 500.0
        return current, current in smoke_cells, 1500.0

    def _resolve_fire_tracker_target_cells(
        self,
        front_or_high_cells: list[tuple[int, int]],
        *,
        runtime_models: Any,
        uav_id: str,
        fire_probability_map: dict[Any, float],
    ) -> tuple[list[tuple[int, int]], dict[str, Any]]:
        """Map flank front cells to smoke-free standoff holds and smoke-safe move targets."""
        smoke_cells = self._read_smoke_obscured_cells(runtime_models)
        fire_cells = self._collect_active_fire_cells(runtime_models)
        bounds = self._grid_bounds(runtime_models)
        wind_vec = (1.0, 0.0)
        wind_obs = self._resolve_wind_observation(runtime_models)
        if wind_obs is not None:
            _, wind_vec, _ = wind_obs
        uav_pos = self._read_uav_position(runtime_models, uav_id)

        hold_cells: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for cell in front_or_high_cells:
            hold = self._compute_flank_hold_standoff_cell(
                cell,
                fire_probability_map=fire_probability_map,
                smoke_cells=smoke_cells,
                fire_cells=fire_cells,
                wind_vector=wind_vec,
                bounds=bounds,
            )
            chosen = hold if hold is not None else cell
            if chosen in smoke_cells or chosen in fire_cells:
                nearest = self._find_nearest_smoke_free_cell(
                    chosen,
                    smoke_cells=smoke_cells,
                    fire_cells=fire_cells,
                    bounds=bounds,
                )
                if nearest is not None:
                    chosen = nearest
            if chosen not in seen:
                seen.add(chosen)
                hold_cells.append(chosen)

        meta: dict[str, Any] = {
            "flank_hold_targets": list(hold_cells),
            "smoke_obscured_count": len(smoke_cells),
        }
        if uav_pos is not None and hold_cells:
            move_target, next_smoke, smoke_penalty = self._pick_fire_tracker_smoke_safe_step(
                uav_pos,
                hold_cells[0],
                smoke_cells=smoke_cells,
                fire_cells=fire_cells,
                bounds=bounds,
                fire_probability_map=fire_probability_map,
            )
            meta["primary_move_target"] = move_target
            meta["primary_next_step_smoke"] = next_smoke
            meta["primary_smoke_penalty"] = smoke_penalty
        return hold_cells, meta

    def _fire_tracker_path_parameters(
        self,
        hold_cell: tuple[int, int],
        *,
        runtime_models: Any,
        uav_id: str,
        fire_probability_map: dict[Any, float],
        is_front: bool,
        overlap_penalty: float,
        sector_params: dict[str, Any],
    ) -> dict[str, Any]:
        smoke_cells = self._read_smoke_obscured_cells(runtime_models)
        fire_cells = self._collect_active_fire_cells(runtime_models)
        bounds = self._grid_bounds(runtime_models)
        uav_pos = self._read_uav_position(runtime_models, uav_id)
        move_target = hold_cell
        next_step_smoke = False
        smoke_penalty = 0.0
        if uav_pos is not None:
            move_target, next_step_smoke, smoke_penalty = (
                self._pick_fire_tracker_smoke_safe_step(
                    uav_pos,
                    hold_cell,
                    smoke_cells=smoke_cells,
                    fire_cells=fire_cells,
                    bounds=bounds,
                    fire_probability_map=fire_probability_map,
                )
            )
        greedy_smoke = False
        if uav_pos is not None:
            ux = int(round(float(uav_pos[0])))
            uy = int(round(float(uav_pos[1])))
            gx, gy = hold_cell
            dx = 0 if ux == gx else (1 if gx > ux else -1)
            dy = 0 if uy == gy else (1 if gy > uy else -1)
            if abs(gx - ux) >= abs(gy - uy) and dx != 0:
                greedy = (ux + dx, uy)
            elif dy != 0:
                greedy = (ux, uy + dy)
            else:
                greedy = (ux, uy)
            greedy_smoke = greedy in smoke_cells or greedy in fire_cells

        return {
            "target_region": move_target,
            "target_position": move_target,
            "flank_hold_target": hold_cell,
            "fire_front_target": is_front,
            "flank_standoff_hold": True,
            "overlap_penalty": overlap_penalty,
            "already_observed_penalty": overlap_penalty,
            "next_step_smoke_penalty": smoke_penalty,
            "greedy_step_would_enter_smoke": greedy_smoke,
            "next_step_smoke_obscured": next_step_smoke,
            **sector_params,
        }

    def _sanitize_fire_tracker_path_parameters(
        self,
        parameters: dict[str, Any],
        *,
        runtime_models: Any,
        uav_id: str,
        fire_probability_map: dict[Any, float],
    ) -> dict[str, Any]:
        """Ensure any fire_tracker path target uses a smoke/fire-safe next step."""
        goal: tuple[int, int] | None = None
        for key in ("flank_hold_target", "target_position", "target_region", "target_location"):
            raw = parameters.get(key)
            if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                try:
                    goal = (int(round(float(raw[0]))), int(round(float(raw[1]))))
                    break
                except (TypeError, ValueError):
                    continue
            if isinstance(raw, str) and "," in raw:
                parts = raw.split(",", 1)
                try:
                    goal = (int(round(float(parts[0]))), int(round(float(parts[1]))))
                    break
                except (TypeError, ValueError):
                    continue
        uav_pos = self._read_uav_position(runtime_models, uav_id)
        if uav_pos is None:
            return parameters
        smoke_cells = self._read_smoke_obscured_cells(runtime_models)
        fire_cells = self._collect_active_fire_cells(runtime_models)
        bounds = self._grid_bounds(runtime_models)
        if goal is None:
            ux = int(round(float(uav_pos[0])))
            uy = int(round(float(uav_pos[1])))
            if (ux, uy) in smoke_cells or (ux, uy) in fire_cells:
                fallback = self._find_nearest_smoke_free_cell(
                    (ux, uy),
                    smoke_cells=smoke_cells,
                    fire_cells=fire_cells,
                    bounds=bounds,
                )
                if fallback is not None:
                    updated = dict(parameters)
                    updated["target_position"] = fallback
                    updated["target_region"] = fallback
                    updated["next_step_smoke_penalty"] = 500.0
                    return updated
            return parameters
        move_target, next_smoke, smoke_penalty = self._pick_fire_tracker_smoke_safe_step(
            uav_pos,
            goal,
            smoke_cells=smoke_cells,
            fire_cells=fire_cells,
            bounds=bounds,
            fire_probability_map=fire_probability_map,
        )
        updated = dict(parameters)
        updated["target_position"] = move_target
        updated["target_region"] = move_target
        updated["flank_hold_target"] = goal
        updated["next_step_smoke_penalty"] = smoke_penalty
        updated["next_step_smoke_obscured"] = next_smoke
        updated["flank_standoff_hold"] = True
        return updated

    def _classify_fire_cells(
        self,
        fire_probability_map: dict[Any, float],
        negative_observation_map: dict[Any, Any] | None = None,
        *,
        runtime_models: Any | None = None,
        threshold: float = 0.3,
    ) -> tuple[list[Any], list[Any]]:
        smoke_cells = self._read_smoke_obscured_cells(runtime_models)
        front_cells: list[Any] = []
        all_high_cells: list[Any] = []
        negative_map = negative_observation_map or {}
        for cell_pos, raw_prob in fire_probability_map.items():
            normalized = self._normalize_cell_pos(cell_pos)
            if normalized is None:
                continue
            if float(raw_prob) < threshold:
                continue
            all_high_cells.append(normalized)
            if self._is_fire_front_cell(
                normalized,
                fire_probability_map,
                negative_map,
                threshold,
            ):
                front_cells.append(normalized)
        front_cells = self._filter_smoke_cells(front_cells, smoke_cells)
        all_high_cells = self._filter_smoke_cells(all_high_cells, smoke_cells)
        return front_cells, all_high_cells

    @staticmethod
    def _read_uav_role(runtime_models: Any, uav_id: str) -> str | None:
        if isinstance(runtime_models, dict):
            resource_model = runtime_models.get("uav_resource_model")
        else:
            resource_model = getattr(runtime_models, "uav_resource_model", None)
        if resource_model is None:
            return None
        by_uav_id = getattr(resource_model, "by_uav_id", None)
        if not isinstance(by_uav_id, dict) or uav_id not in by_uav_id:
            return None
        state = by_uav_id[uav_id]
        role = getattr(state, "current_role", None)
        if role is None and isinstance(state, dict):
            role = state.get("current_role", state.get("role"))
        return str(role) if role is not None else None

    @staticmethod
    def _collect_victim_positions(
        runtime_models: Any,
    ) -> list[tuple[str, tuple[float, float]]]:
        if isinstance(runtime_models, dict):
            victim_model = runtime_models.get("victim_runtime_model")
        else:
            victim_model = getattr(runtime_models, "victim_runtime_model", None)
        if victim_model is None:
            return []
        victims = getattr(victim_model, "victims", None)
        if not isinstance(victims, dict):
            return []
        targets: list[tuple[str, tuple[float, float]]] = []
        for victim_id, victim in victims.items():
            position = LocalAdaptationSpaceGenerator._extract_victim_position(victim)
            if position is not None:
                targets.append((str(victim_id), position))
        return targets

    @staticmethod
    def _collect_active_live_victim_targets(
        runtime_models: Any,
    ) -> list[tuple[str, tuple[float, float]]]:
        """Victims that still need UAV search (exclude rescued/assigned/handled)."""
        all_targets = LocalAdaptationSpaceGenerator._collect_victim_positions(
            runtime_models
        )
        if not all_targets:
            return []
        sim = (
            runtime_models.get("simulation_model")
            if isinstance(runtime_models, dict)
            else None
        )
        live: list[tuple[str, tuple[float, float]]] = []
        if isinstance(runtime_models, dict):
            victim_model = runtime_models.get("victim_runtime_model")
        else:
            victim_model = getattr(runtime_models, "victim_runtime_model", None)
        victims = (
            getattr(victim_model, "victims", None)
            if victim_model is not None
            else None
        )
        if not isinstance(victims, dict):
            return all_targets
        for victim_id, position in all_targets:
            entry = victims.get(victim_id)
            if LocalAdaptationSpaceGenerator._victim_needs_live_search(
                str(victim_id), entry, sim
            ):
                live.append((victim_id, position))
        return live

    @staticmethod
    def _victim_needs_live_search(
        victim_id: str,
        victim: Any,
        model: Any | None,
    ) -> bool:
        terminal_statuses = frozenset(
            {"dead", "cancelled", "rescued", "unreachable"}
        )
        handled_statuses = terminal_statuses | frozenset(
            {"confirmed", "assigned", "delayed"}
        )
        if model is not None:
            managed = getattr(model, "managed_victims", None)
            if isinstance(managed, dict):
                state = managed.get(victim_id)
                if state is not None:
                    status = str(getattr(state, "status", "") or "").strip().lower()
                    if status in terminal_statuses:
                        return False
                    for flag in (
                        "dead",
                        "cancelled",
                        "rescued",
                        "unreachable",
                        "rescue_assigned",
                        "confirmed",
                        "assigned",
                    ):
                        if getattr(state, flag, False):
                            return False
                    if status in handled_statuses:
                        return False
        if isinstance(victim, dict):
            status = str(victim.get("status", "") or "").strip().lower()
            if status in terminal_statuses:
                return False
            for key in ("rescued", "dead", "cancelled", "unreachable", "assigned"):
                if victim.get(key):
                    return False
        elif victim is not None:
            status = str(getattr(victim, "status", "") or "").strip().lower()
            if status in terminal_statuses:
                return False
            for key in ("rescued", "dead", "cancelled", "unreachable", "assigned"):
                if getattr(victim, key, False):
                    return False
        return True

    @staticmethod
    def _resolve_wind_observation(
        runtime_models: Any,
    ) -> tuple[str, tuple[float, float], str] | None:
        """Primary: GlobalObservationSnapshot; fallback bridge/model/config."""
        if isinstance(runtime_models, dict):
            snapshot = runtime_models.get("global_observation_snapshot")
            sim = runtime_models.get("simulation_model")
        else:
            snapshot = getattr(runtime_models, "global_observation_snapshot", None)
            sim = getattr(runtime_models, "simulation_model", None)

        if snapshot is not None:
            wind_dir = str(
                getattr(snapshot, "wind_direction", None)
                or (snapshot.get("wind_direction") if isinstance(snapshot, dict) else "")
                or ""
            ).strip()
            if wind_dir:
                wind_vec = getattr(snapshot, "wind_vector", None)
                if wind_vec is None and isinstance(snapshot, dict):
                    wind_vec = snapshot.get("wind_vector")
                if not isinstance(wind_vec, (list, tuple)) or len(wind_vec) < 2:
                    wind_vec = wind_vector_from_direction(wind_dir)
                else:
                    wind_vec = (float(wind_vec[0]), float(wind_vec[1]))
                normalized = normalize_wind_direction(wind_dir)
                if normalized:
                    return normalized, wind_vec, "global_monitor"

        if sim is not None:
            bridge = getattr(sim, "environment_bridge", None)
            if bridge is not None and hasattr(bridge, "get_wind_summary"):
                try:
                    summary = bridge.get_wind_summary()
                except Exception:
                    summary = {}
                if isinstance(summary, dict):
                    wind_dir = str(summary.get("direction", "") or "").strip()
                    if wind_dir:
                        wv = summary.get("vector")
                        if isinstance(wv, (list, tuple)) and len(wv) >= 2:
                            wind_vec = (float(wv[0]), float(wv[1]))
                        else:
                            wind_vec = wind_vector_from_direction(wind_dir)
                        normalized = normalize_wind_direction(wind_dir)
                        if normalized:
                            return normalized, wind_vec, "environment_bridge"

        try:
            import os

            from common_fixed_variables import WIND_DIRECTION as CFG_WIND_DIRECTION

            for raw in (
                os.environ.get("WIND_DIRECTION", "").strip(),
                str(CFG_WIND_DIRECTION or "").strip(),
            ):
                if not raw:
                    continue
                normalized = normalize_wind_direction(raw)
                if normalized:
                    return (
                        normalized,
                        wind_vector_from_direction(normalized),
                        "config",
                    )
        except Exception:
            pass
        return None

    @staticmethod
    def _has_meaningful_fire(
        runtime_models: Any,
        *,
        threshold: float = 0.3,
    ) -> bool:
        if LocalAdaptationSpaceGenerator._collect_active_fire_cells(runtime_models):
            return True
        fire_map = LocalAdaptationSpaceGenerator._read_fire_probability_map(
            runtime_models
        )
        for raw_prob in fire_map.values():
            try:
                if float(raw_prob) >= threshold:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    @staticmethod
    def _collect_active_fire_cells(runtime_models: Any) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        sim = (
            runtime_models.get("simulation_model")
            if isinstance(runtime_models, dict)
            else getattr(runtime_models, "simulation_model", None)
        )
        if sim is not None:
            schedule = getattr(sim, "schedule", None)
            agent_list = getattr(schedule, "agents", None) if schedule else None
            if agent_list:
                for agent in agent_list:
                    status = getattr(agent, "burnt_status", None)
                    status_val = (
                        getattr(status, "value", status)
                        if status is not None
                        else None
                    )
                    status_str = str(status_val or "").lower()
                    if status_str not in ("burning", "burned", "on_fire", "fire"):
                        continue
                    pos = getattr(agent, "pos", None)
                    normalized = LocalAdaptationSpaceGenerator._normalize_cell_pos(
                        pos
                    )
                    if normalized is not None:
                        cells.add(normalized)
        fire_map = LocalAdaptationSpaceGenerator._read_fire_probability_map(
            runtime_models
        )
        for cell_pos, raw_prob in fire_map.items():
            try:
                if float(raw_prob) < 0.3:
                    continue
            except (TypeError, ValueError):
                continue
            normalized = LocalAdaptationSpaceGenerator._normalize_cell_pos(cell_pos)
            if normalized is not None:
                cells.add(normalized)
        return cells

    @staticmethod
    def _read_uav_position(
        runtime_models: Any,
        uav_id: str,
    ) -> tuple[float, float] | None:
        if isinstance(runtime_models, dict):
            resource_model = runtime_models.get("uav_resource_model")
        else:
            resource_model = getattr(runtime_models, "uav_resource_model", None)
        if resource_model is None:
            return None
        by_uav = getattr(resource_model, "by_uav_id", None)
        if not isinstance(by_uav, dict) or uav_id not in by_uav:
            return None
        state = by_uav[uav_id]
        pos = getattr(state, "position", None)
        if pos is None and isinstance(state, dict):
            pos = state.get("position")
        return LocalAdaptationSpaceGenerator._normalize_position(pos)

    @staticmethod
    def _grid_bounds(runtime_models: Any) -> tuple[int, int, int, int]:
        sim = (
            runtime_models.get("simulation_model")
            if isinstance(runtime_models, dict)
            else getattr(runtime_models, "simulation_model", None)
        )
        height = int(getattr(sim, "HEIGHT", getattr(sim, "height", 50)) if sim else 50)
        width = int(getattr(sim, "WIDTH", getattr(sim, "width", 50)) if sim else 50)
        return 0, height - 1, 0, width - 1

    @staticmethod
    def _cell_high_fire_probability(
        cell: tuple[int, int],
        fire_map: dict[Any, float],
        *,
        threshold: float = 0.5,
    ) -> bool:
        prob = LocalAdaptationSpaceGenerator._map_probability(fire_map, cell)
        return prob is not None and prob >= threshold

    @staticmethod
    def _min_fire_distance(
        cell: tuple[int, int],
        fire_cells: set[tuple[int, int]],
    ) -> float:
        if not fire_cells:
            return 0.0
        cx, cy = cell
        return float(
            min(abs(cx - fx) + abs(cy - fy) for fx, fy in fire_cells)
        )

    def _pick_global_coverage_escape_target(
        self,
        *,
        runtime_models: Any,
        uav_id: str,
        wind_vector: tuple[float, float],
        fire_cells: set[tuple[int, int]],
        smoke_cells: set[tuple[int, int]],
        fx: float,
        fy: float,
        ax: float,
        ay: float,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        simulation: Any | None,
        wind_state: dict[str, Any],
        step_index: int,
    ) -> tuple[float, float] | None:
        wvx, wvy = float(wind_vector[0]), float(wind_vector[1])
        best_score = -float("inf")
        best_point: tuple[float, float] | None = None
        coverage_w = _coverage_priority(wind_state)
        coverage_active = _coverage_mode_active(wind_state)
        min_escape_dist = 14.0 if bool(wind_state.get("force_coverage_escape")) else 6.0
        if coverage_w >= 0.9:
            min_escape_dist = max(min_escape_dist, 20.0)
        safe_x_min = _coverage_safe_x_min(x_min)
        safe_x_max = _coverage_safe_x_max(x_max)
        if coverage_active and ax < safe_x_min + 4:
            min_escape_dist = max(4.0, min(min_escape_dist, 8.0))
        corridor_fail = _corridor_diversity_failure(wind_state)
        lower_y_max, upper_y_min = _grid_y_half_split(y_min, y_max)
        corridor_x_cap = _corridor_target_x_cap(
            wind_state, x_min, x_max, coverage_active=coverage_active,
        )
        _update_coverage_y_commit(wind_state, y_min, y_max, float(ay))
        commit = wind_state.get("coverage_y_commit")
        y_force_min = _coverage_y_commit_target_y(wind_state, y_min, y_max) if (
            commit == "north"
        ) else None
        y_force_max = _coverage_y_commit_target_y(wind_state, y_min, y_max) if (
            commit == "south"
        ) else None
        if commit == "north" and ay < y_max - COVERAGE_Y_COMMIT_PENETRATE_MARGIN:
            min_escape_dist = min(min_escape_dist, 5.0)
        elif commit == "south" and ay > y_min + COVERAGE_Y_COMMIT_PENETRATE_MARGIN:
            min_escape_dist = min(min_escape_dist, 5.0)
        center = wind_state.get("pocket_center")
        lane = _searcher_crosswind_lane(
            simulation,
            uav_id,
            _wind_label_from_vector(wind_vector),
            x_min,
            x_max,
            y_min,
            y_max,
        )
        _mark_x_strip_progress(wind_state, safe_x_min, safe_x_max)
        west_pending = _west_sweep_pending(wind_state, safe_x_min)
        east_pending = _east_sweep_pending(wind_state, safe_x_max)
        for cx in range(x_min + 1, x_max):
            for cy in range(y_min + 1, y_max):
                if not _lane_allows_cell(lane, cx, cy):
                    continue
                if corridor_fail and cx > corridor_x_cap:
                    continue
                if coverage_active:
                    if cx < safe_x_min or cx > safe_x_max:
                        continue
                    if commit == "north" and cy < upper_y_min:
                        continue
                    if commit == "south" and cy > lower_y_max:
                        continue
                    if y_force_min is not None and cy < y_force_min:
                        continue
                    if y_force_max is not None and cy > y_force_max:
                        continue
                if (cx - x_min) % 2 != 0 and (cy - y_min) % 2 != 0 and not bool(
                    wind_state.get("force_coverage_escape")
                ):
                    continue
                if (cx, cy) in fire_cells or (cx, cy) in smoke_cells:
                    continue
                if _is_saturated_cell(wind_state, cx, cy, step_index):
                    continue
                dist_agent = abs(cx - ax) + abs(cy - ay)
                if dist_agent < min_escape_dist:
                    continue
                downwind = (float(cx) - fx) * wvx + (float(cy) - fy) * wvy
                hazard_dist = self._min_fire_distance((cx, cy), fire_cells)
                smoke_dist = _min_smoke_distance((cx, cy), smoke_cells)
                score = _score_hybrid_search_cell(
                    cx=cx,
                    cy=cy,
                    downwind=downwind,
                    hazard_dist=hazard_dist,
                    smoke_dist=smoke_dist,
                    dist_agent=dist_agent,
                    x_min=x_min,
                    x_max=x_max,
                    y_min=y_min,
                    y_max=y_max,
                    runtime_models=runtime_models,
                    simulation=simulation,
                    uav_id=uav_id,
                    wind_state=wind_state,
                )
                if score is None:
                    continue
                score += _never_seen_proximity_bonus(runtime_models, cx, cy) * (
                    1.0 + coverage_w
                )
                score += _uncovered_region_bonus(
                    cx, cy, wind_state, x_min, x_max, y_min, y_max,
                )
                score += dist_agent * 0.35
                if coverage_active:
                    if _wind_label_from_vector(wind_vector) == "west":
                        if (
                            west_pending
                            and ax > safe_x_min + 4
                            and cx < ax
                        ):
                            score += (ax - cx) * 0.75
                        elif (
                            east_pending
                            and _allow_east_force(wind_state)
                            and ax < safe_x_max - 4
                            and cx > ax
                        ):
                            score += (cx - ax) * 0.75
                    elif ax > safe_x_min + 4 and cx < ax:
                        score += (ax - cx) * 0.75
                if coverage_active and y_force_min is not None and cy >= y_force_min:
                    score += (cy - y_force_min) * 0.45
                if coverage_active and commit == "north" and y_force_min is not None:
                    if ay < y_max - COVERAGE_Y_COMMIT_PENETRATE_MARGIN:
                        north_band = float(ay) + COVERAGE_Y_COMMIT_GRADUAL_STEP
                        if float(cy) <= north_band:
                            score += (float(cy) - float(ay)) * 0.55
                    score += max(0.0, float(cy) - float(ay)) * 0.35
                if coverage_active and commit == "south" and y_force_max is not None:
                    score += max(0.0, float(ay) - float(cy)) * 0.35
                if isinstance(center, (list, tuple)) and len(center) >= 2:
                    score += (abs(cx - int(center[0])) + abs(cy - int(center[1]))) * 0.45
                if score > best_score:
                    best_score = score
                    best_point = (float(cx), float(cy))
        if best_point is None and isinstance(center, (list, tuple)) and len(center) >= 2:
            cx = int((x_min + x_max) // 2)
            cy = int((y_min + y_max) // 2)
            if corridor_fail:
                cx = min(cx, corridor_x_cap)
                if coverage_active:
                    cx = max(
                        safe_x_min,
                        min(safe_x_max, cx),
                    )
                    if commit == "north" and y_force_min is not None:
                        cy = max(y_force_min, cy)
                    elif commit == "south" and y_force_max is not None:
                        cy = min(y_force_max, cy)
            if (cx, cy) not in fire_cells and (cx, cy) not in smoke_cells:
                best_point = (float(cx), float(cy))
        return _finalize_coverage_target(
            best_point, wind_state, x_min=x_min, y_min=y_min, y_max=y_max, x_max=x_max, ax=ax, ay=ay,
        )

    def _generate_corridor_waypoints(
        self,
        *,
        runtime_models: Any,
        uav_id: str,
        wind_direction: str,
        wind_vector: tuple[float, float],
        fire_cells: set[tuple[int, int]],
        smoke_cells: set[tuple[int, int]],
        fx: float,
        fy: float,
        ax: float,
        ay: float,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        simulation: Any | None,
        wind_state: dict[str, Any],
        step_index: int,
        force_interior: bool,
    ) -> list[tuple[float, float]]:
        ix_min = x_min + WIND_EDGE_MARGIN
        ix_max = x_max - WIND_EDGE_MARGIN
        iy_min = y_min + WIND_EDGE_MARGIN
        iy_max = y_max - WIND_EDGE_MARGIN
        if ix_min > ix_max or iy_min > iy_max:
            return []

        wvx, wvy = float(wind_vector[0]), float(wind_vector[1])
        wind_norm = normalize_wind_direction(wind_direction)
        scored: list[tuple[float, tuple[float, float], float]] = []
        coverage_active = _coverage_mode_active(wind_state)
        _update_coverage_y_commit(wind_state, y_min, y_max, float(ay))
        commit = wind_state.get("coverage_y_commit")
        lower_y_max, upper_y_min = _grid_y_half_split(y_min, y_max)
        y_force_min = _coverage_y_commit_target_y(wind_state, y_min, y_max) if (
            commit == "north"
        ) else None
        y_force_max = _coverage_y_commit_target_y(wind_state, y_min, y_max) if (
            commit == "south"
        ) else None

        def cell_blocked(cx: int, cy: int) -> bool:
            cell = (cx, cy)
            if cell in fire_cells or cell in smoke_cells:
                return True
            if not bool(wind_state.get("force_coverage_escape")):
                if _downwind_edge_blocked(wind_norm, cx, cy, x_min, x_max, y_min, y_max):
                    return True
            if _is_saturated_cell(wind_state, cx, cy, step_index):
                return True
            return False

        x_values = range(ix_min, ix_max + 1, WIND_CORRIDOR_STRIDE)
        y_values = range(iy_min, iy_max + 1, WIND_CORRIDOR_STRIDE)
        safe_x_min = _coverage_safe_x_min(x_min)
        safe_x_max = _coverage_safe_x_max(x_max)
        lane = _searcher_crosswind_lane(
            simulation, uav_id, wind_norm, x_min, x_max, y_min, y_max,
        )
        _mark_x_strip_progress(wind_state, safe_x_min, safe_x_max)
        west_pending = _west_sweep_pending(wind_state, safe_x_min)
        east_pending = _east_sweep_pending(wind_state, safe_x_max)
        for cx in x_values:
            for cy in y_values:
                if not _lane_allows_cell(lane, cx, cy):
                    continue
                if coverage_active:
                    if cx < safe_x_min or cx > safe_x_max:
                        continue
                    if commit == "north" and cy < upper_y_min:
                        continue
                    if commit == "south" and cy > lower_y_max:
                        continue
                    if y_force_min is not None and cy < y_force_min:
                        continue
                    if y_force_max is not None and cy > y_force_max:
                        continue
                if cell_blocked(cx, cy):
                    continue
                downwind = (float(cx) - fx) * wvx + (float(cy) - fy) * wvy
                hazard_dist = self._min_fire_distance((cx, cy), fire_cells)
                smoke_dist = _min_smoke_distance((cx, cy), smoke_cells)
                dist_agent = abs(cx - ax) + abs(cy - ay)
                score = _score_hybrid_search_cell(
                    cx=cx,
                    cy=cy,
                    downwind=downwind,
                    hazard_dist=hazard_dist,
                    smoke_dist=smoke_dist,
                    dist_agent=dist_agent,
                    x_min=x_min,
                    x_max=x_max,
                    y_min=y_min,
                    y_max=y_max,
                    runtime_models=runtime_models,
                    simulation=simulation,
                    uav_id=uav_id,
                    wind_state=wind_state,
                )
                if score is None:
                    continue
                score += _uncovered_region_bonus(
                    cx, cy, wind_state, x_min, x_max, y_min, y_max,
                )
                if (
                    coverage_active
                    and wind_norm == "west"
                    and not west_pending
                    and east_pending
                    and _allow_east_force(wind_state)
                ):
                    score += max(0.0, float(cx) - ax) * 0.75
                if coverage_active and y_force_min is not None and cy >= y_force_min:
                    score += (cy - y_force_min) * 0.45
                if coverage_active and commit == "north" and y_force_min is not None:
                    if ay < y_max - COVERAGE_Y_COMMIT_PENETRATE_MARGIN:
                        north_band = float(ay) + COVERAGE_Y_COMMIT_GRADUAL_STEP
                        if float(cy) <= north_band:
                            score += (float(cy) - float(ay)) * 0.55
                    score += max(0.0, float(cy) - float(ay)) * 0.35
                if coverage_active and commit == "south" and y_force_max is not None:
                    score += max(0.0, float(ay) - float(cy)) * 0.35
                if force_interior and _distance_to_boundary(cx, cy, x_min, x_max, y_min, y_max) < WIND_INTERIOR_MARGIN:
                    score -= WIND_EDGE_PENALTY * 2.0
                front_dist = min(hazard_dist, smoke_dist)
                scored.append((score, (float(cx), float(cy)), front_dist))

        if not scored:
            return []

        min_front = float(WIND_FIRE_FRONT_MIN_DISTANCE)
        if bool(wind_state.get("force_coverage_escape")):
            min_front = max(2.0, min_front * 0.45)
        safer = [item for item in scored if item[2] >= min_front]
        if safer:
            scored = safer

        scored.sort(key=lambda item: -item[0])

        waypoints: list[tuple[float, float]] = []
        seen: set[tuple[int, int]] = set()
        for _, point, _ in scored:
            key = (int(round(point[0])), int(round(point[1])))
            if key in seen:
                continue
            seen.add(key)
            waypoints.append(point)
            if len(waypoints) >= WIND_CORRIDOR_MAX_WAYPOINTS:
                break
        return waypoints

    def _compute_wind_aware_search_target(
        self,
        runtime_models: Any,
        uav_id: str,
        wind_direction: str,
        wind_vector: tuple[float, float],
    ) -> tuple[float, float] | None:
        fire_cells = self._collect_active_fire_cells(runtime_models)
        if not fire_cells:
            return None
        smoke_cells = self._read_smoke_obscured_cells(runtime_models)
        fx = sum(c[0] for c in fire_cells) / float(len(fire_cells))
        fy = sum(c[1] for c in fire_cells) / float(len(fire_cells))
        x_min, x_max, y_min, y_max = self._grid_bounds(runtime_models)
        uav_pos = self._read_uav_position(runtime_models, uav_id)
        ax = float(uav_pos[0]) if uav_pos is not None else (x_min + x_max) / 2.0
        ay = float(uav_pos[1]) if uav_pos is not None else (y_min + y_max) / 2.0
        simulation = _simulation_from_runtime(runtime_models)
        step_index = _step_index_from_runtime(runtime_models)
        wind_state = _wind_search_state(simulation, uav_id)
        grid_pos = (
            (int(round(ax)), int(round(ay))) if uav_pos is not None else None
        )
        _sync_wind_search_streaks(
            wind_state,
            grid_position=grid_pos,
            action=wind_state.get("last_action"),
            target=wind_state.get("current_target"),
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
            step_index=step_index,
        )

        _update_unresolved_coverage_state(
            simulation,
            wind_state,
            agent_x=grid_pos[0] if grid_pos is not None else None,
            agent_y=grid_pos[1] if grid_pos is not None else None,
        )
        coverage_mode = _apply_unresolved_coverage_mode(wind_state)

        if coverage_mode and _corridor_diversity_failure(wind_state):
            escape = self._pick_global_coverage_escape_target(
                runtime_models=runtime_models,
                uav_id=uav_id,
                wind_vector=wind_vector,
                fire_cells=fire_cells,
                smoke_cells=smoke_cells,
                fx=fx,
                fy=fy,
                ax=ax,
                ay=ay,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                simulation=simulation,
                wind_state=wind_state,
                step_index=step_index,
            )
            if escape is not None:
                wind_state["corridor_targets"] = [escape]
                wind_state["corridor_index"] = 0
                wind_state["escape_target"] = escape
                _record_wind_search_target(wind_state, escape)
                _record_corridor_target(wind_state, escape)
                if grid_pos is not None:
                    _record_victim_searcher_x_band(wind_state, grid_pos[0], grid_pos[1])
                return escape

        pocket = int(wind_state.get("pocket_streak", 0) or 0)
        if wind_state.get("force_sweep"):
            if pocket >= WIND_POCKET_CAMP_THRESHOLD or bool(wind_state.get("force_coverage_escape")):
                wind_state["force_sweep"] = False
            else:
                return None

        if int(wind_state.get("same_target_streak", 0) or 0) > WIND_SAME_TARGET_RESET_STREAK:
            _reset_corridor_on_same_target_streak(
                wind_state, step_index, wind_state.get("current_target"),
            )

        wind_norm = normalize_wind_direction(wind_direction)
        prior_wind = wind_state.get("last_wind_direction")
        if prior_wind is not None and normalize_wind_direction(prior_wind) != wind_norm:
            wind_state["corridor_index"] = 0
            wind_state["corridor_targets"] = []
            wind_state["force_interior_retarget"] = True
        wind_state["last_wind_direction"] = wind_norm

        force_interior = bool(
            wind_state.get("force_interior_retarget")
            or wind_state.get("force_coverage_escape")
        )
        if grid_pos is not None and _cell_on_edge(
            grid_pos[0], grid_pos[1], x_min, x_max, y_min, y_max, margin=WIND_INTERIOR_MARGIN,
        ):
            force_interior = True
            wind_state["force_interior_retarget"] = True

        pocket = int(wind_state.get("pocket_streak", 0) or 0)
        committed = wind_state.get("escape_target")
        if isinstance(committed, (list, tuple)) and len(committed) >= 2 and grid_pos is not None:
            if _manhattan(ax, ay, float(committed[0]), float(committed[1])) > 3.0:
                committed_final = _finalize_coverage_target(
                    (float(committed[0]), float(committed[1])),
                    wind_state,
                    x_min=x_min,
                    y_min=y_min,
                    y_max=y_max,
                    x_max=x_max,
                    ax=ax,
                    ay=ay,
                )
                if committed_final is not None:
                    return committed_final
            wind_state["escape_target"] = None
            wind_state["pocket_anchor"] = None
            wind_state["pocket_streak"] = 0
            wind_state["force_coverage_escape"] = False

        if bool(wind_state.get("force_coverage_escape")) or pocket >= WIND_POCKET_CAMP_THRESHOLD:
            if (
                not _coverage_mode_active(wind_state)
                and (
                    pocket >= WIND_POCKET_CAMP_THRESHOLD
                    or bool(wind_state.get("force_coverage_escape"))
                )
            ):
                opp = _gradual_escape_target(
                    ax, ay, x_min, x_max, y_min, y_max, fire_cells, smoke_cells,
                )
                if opp is not None:
                    wind_state["escape_target"] = opp
                    wind_state["corridor_targets"] = [opp]
                    wind_state["corridor_index"] = 0
                    wind_state["force_sweep"] = False
                    wind_state["hazard_buffer_level"] = 2
                    _record_wind_search_target(wind_state, opp)
                    _record_corridor_target(wind_state, opp)
                    return _finalize_coverage_target(
                        opp, wind_state, x_min=x_min, y_min=y_min, y_max=y_max, x_max=x_max, ax=ax, ay=ay,
                    )
            escape = self._pick_global_coverage_escape_target(
                runtime_models=runtime_models,
                uav_id=uav_id,
                wind_vector=wind_vector,
                fire_cells=fire_cells,
                smoke_cells=smoke_cells,
                fx=fx,
                fy=fy,
                ax=ax,
                ay=ay,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                simulation=simulation,
                wind_state=wind_state,
                step_index=step_index,
            )
            if escape is not None:
                wind_state["corridor_targets"] = [escape]
                wind_state["corridor_index"] = 0
                _record_wind_search_target(wind_state, escape)
                _record_corridor_target(wind_state, escape)
                wind_state["force_sweep"] = False
                if grid_pos is not None:
                    center = wind_state.get("pocket_center")
                    if isinstance(center, (list, tuple)) and len(center) >= 2:
                        dist = abs(grid_pos[0] - int(center[0])) + abs(grid_pos[1] - int(center[1]))
                        if dist > 6:
                            wind_state["force_coverage_escape"] = False
                            wind_state["pocket_streak"] = 0
                            wind_state["hazard_buffer_level"] = max(
                                0, int(wind_state.get("hazard_buffer_level", 0) or 0) - 1
                            )
                return escape

        current_target = wind_state.get("current_target")
        if isinstance(current_target, (list, tuple)) and len(current_target) >= 2:
            _touch_wind_search_dwell(
                wind_state,
                uav_pos,
                (float(current_target[0]), float(current_target[1])),
                step_index,
            )
            dist_to_target = _manhattan(
                ax,
                ay,
                float(current_target[0]),
                float(current_target[1]),
            )
            if dist_to_target <= 2.0 or int(wind_state.get("dwell_count", 0) or 0) >= WIND_SATURATE_DWELL_STEPS:
                _advance_corridor_index(wind_state)
                force_interior = True

        corridor = list(wind_state.get("corridor_targets") or [])
        if not corridor:
            corridor = self._generate_corridor_waypoints(
                runtime_models=runtime_models,
                uav_id=uav_id,
                wind_direction=wind_direction,
                wind_vector=wind_vector,
                fire_cells=fire_cells,
                smoke_cells=smoke_cells,
                fx=fx,
                fy=fy,
                ax=ax,
                ay=ay,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                simulation=simulation,
                wind_state=wind_state,
                step_index=step_index,
                force_interior=force_interior,
            )
            wind_state["corridor_targets"] = corridor
            wind_state["corridor_index"] = 0
        elif force_interior:
            corridor = self._generate_corridor_waypoints(
                runtime_models=runtime_models,
                uav_id=uav_id,
                wind_direction=wind_direction,
                wind_vector=wind_vector,
                fire_cells=fire_cells,
                smoke_cells=smoke_cells,
                fx=fx,
                fy=fy,
                ax=ax,
                ay=ay,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                simulation=simulation,
                wind_state=wind_state,
                step_index=step_index,
                force_interior=True,
            )
            wind_state["corridor_targets"] = corridor
            if int(wind_state.get("corridor_index", 0) or 0) >= len(corridor):
                wind_state["force_sweep"] = True
                return None

        if not corridor:
            wind_state["force_sweep"] = True
            return None

        index = int(wind_state.get("corridor_index", 0) or 0)
        if index >= len(corridor):
            wind_state["force_sweep"] = True
            return None

        best_target = corridor[index]
        if force_interior:
            interior_candidates = [
                point for point in corridor
                if _distance_to_boundary(
                    int(round(point[0])), int(round(point[1])),
                    x_min, x_max, y_min, y_max,
                ) >= WIND_INTERIOR_MARGIN
            ]
            if interior_candidates:
                commit = wind_state.get("coverage_y_commit")
                if commit == "north":
                    northward = [
                        point for point in interior_candidates
                        if float(point[1]) >= float(ay)
                    ]
                    if northward:
                        interior_candidates = northward
                    best_target = max(
                        interior_candidates,
                        key=lambda point: (
                            float(point[1]),
                            abs(point[0] - ax) + abs(point[1] - ay),
                        ),
                    )
                elif commit == "south":
                    southward = [
                        point for point in interior_candidates
                        if float(point[1]) <= float(ay)
                    ]
                    if southward:
                        interior_candidates = southward
                    best_target = min(
                        interior_candidates,
                        key=lambda point: (
                            -float(point[1]),
                            abs(point[0] - ax) + abs(point[1] - ay),
                        ),
                    )
                elif bool(wind_state.get("force_coverage_escape")):
                    center = wind_state.get("pocket_center")
                    if isinstance(center, (list, tuple)) and len(center) >= 2:
                        best_target = max(
                            interior_candidates,
                            key=lambda point: (
                                abs(point[0] - float(center[0]))
                                + abs(point[1] - float(center[1]))
                            ),
                        )
                    else:
                        best_target = interior_candidates[0]
                else:
                    best_target = min(
                        interior_candidates,
                        key=lambda point: abs(point[0] - ax) + abs(point[1] - ay),
                    )

        _record_wind_search_target(wind_state, best_target)
        _record_corridor_target(wind_state, best_target)
        wind_state["force_interior_retarget"] = False
        wind_state["force_east_interior"] = False
        if grid_pos is not None:
            _record_victim_searcher_x_band(wind_state, grid_pos[0], grid_pos[1])
        if simulation is not None:
            simulation._wind_search_target_state = getattr(
                simulation, "_wind_search_target_state", {}
            )
        return _finalize_coverage_target(
            best_target, wind_state, x_min=x_min, y_min=y_min, y_max=y_max, x_max=x_max, ax=ax, ay=ay,
        )

    def _try_generate_wind_aware_victim_search_option(
        self,
        *,
        uav_id: str,
        target_entity: str,
        base_parameters: dict[str, Any],
        confidence: float,
        originating_trigger: str,
        timestamp: float,
        current_role: str,
        runtime_models: Any,
        mission_goals: dict[str, Any] | None = None,
    ) -> LocalAdaptationOption | None:
        goals = mission_goals or read_mission_goals(runtime_models)
        wind_obs = self._resolve_wind_observation(runtime_models)
        if wind_obs is None:
            return None
        wind_direction, wind_vector, wind_source = wind_obs
        if not self._has_meaningful_fire(runtime_models):
            return None
        target_position = self._compute_wind_aware_search_target(
            runtime_models,
            uav_id,
            wind_direction,
            wind_vector,
        )
        if target_position is None:
            return None
        simulation = _simulation_from_runtime(runtime_models)
        wind_state = _wind_search_state(simulation, uav_id)
        uav_pos = self._read_uav_position(runtime_models, uav_id)
        if uav_pos is not None:
            _record_victim_searcher_x_band(wind_state, uav_pos[0], uav_pos[1])
        option_confidence = self._adjust_path_confidence(
            confidence,
            goals,
            action="victim_search_wind_aware",
            parameters={"victim_search": True},
        )
        if goal_priority_enabled(goals, "prioritize_victim_search"):
            option_confidence = boost_confidence(option_confidence, 0.05)
        return LocalAdaptationOption(
            option_id="wind_aware_victim_search",
            option_type="wind_aware_victim_search",
            target_entity=target_entity,
            parameters=self._merge_mission_goal_parameters(
                {
                    **base_parameters,
                    "path_action": "victim_search_wind_aware",
                    "next_action": "victim_search_wind_aware",
                    "wind_direction": wind_direction,
                    "wind_vector": list(wind_vector),
                    "target_position": target_position,
                    "target_region": target_position,
                    "reason": "downwind_priority",
                    "safety_filter": "avoid_fire_smoke",
                    "search_policy": "wind_aware",
                    "source": "local_adaptation_generator",
                    "wind_source": wind_source,
                    "task_support": 0.95,
                    "expected_info_gain": 0.65,
                    "coverage_priority": float(wind_state.get("coverage_priority", 0.0) or 0.0),
                    "unresolved_victim_count": int(
                        wind_state.get("unresolved_victim_count", 0) or 0
                    ),
                    "post_rescue_coverage_steps_remaining": int(
                        wind_state.get("post_rescue_coverage_steps_remaining", 0) or 0
                    ),
                    "corridor_diversity_failure": _corridor_diversity_failure(wind_state),
                    "victim_search": True,
                    "role": current_role,
                    "mission_goal_boost": goal_priority_enabled(
                        goals, "prioritize_victim_search"
                    ),
                },
                goals,
                reason="prioritize_victim_search",
            ),
            expected_effect=(
                "Wind-aware downwind victim search toward safe area ahead of fire spread"
            ),
            cost_estimate=0.35,
            risk_estimate=0.25,
            confidence=option_confidence,
            scope=Scope.local,
            timestamp=timestamp,
            originating_trigger=originating_trigger,
            explanation_hint=(
                f"Search downwind ({wind_direction}) for victims ahead of fire/smoke spread"
            ),
        )

    @staticmethod
    def _extract_victim_position(victim: Any) -> tuple[float, float] | None:
        if isinstance(victim, dict):
            for key in ("estimated_position", "position", "current_position"):
                raw = victim.get(key)
                if raw is not None:
                    return LocalAdaptationSpaceGenerator._normalize_position(raw)
            return None
        for key in ("estimated_position", "position", "current_position"):
            raw = getattr(victim, key, None)
            if raw is not None:
                return LocalAdaptationSpaceGenerator._normalize_position(raw)
        return None

    @staticmethod
    def _normalize_position(raw: Any) -> tuple[float, float] | None:
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            try:
                return (float(raw[0]), float(raw[1]))
            except (TypeError, ValueError):
                return None
        return None

    def _build_path_options_toward_targets(
        self,
        targets: list[tuple[str, tuple[float, float]]],
        target_entity: str,
        base_parameters: dict[str, Any],
        confidence: float,
        originating_trigger: str,
        timestamp: float,
        current_role: str,
        mission_goals: dict[str, Any] | None = None,
    ) -> list[AdaptationOption]:
        goals = mission_goals or {}
        options: list[AdaptationOption] = []
        for index, (victim_id, position) in enumerate(targets):
            path_parameters = {
                **base_parameters,
                "path_action": "move_toward_victim_candidate",
                "target_position": position,
                "target_region": position,
                "expected_info_gain": 0.7,
                "task_support": 0.85,
                "victim_search": True,
                "role": current_role,
                "victim_id": victim_id,
            }
            options.append(
                LocalAdaptationOption(
                    option_id=f"local_path_move_toward_victim_candidate_{victim_id}",
                    option_type="path_planning",
                    target_entity=target_entity,
                    parameters=self._merge_mission_goal_parameters(
                        path_parameters,
                        goals,
                        reason="prioritize_victim_search",
                    ),
                    expected_effect=f"Move toward victim candidate {victim_id}",
                    cost_estimate=0.8,
                    risk_estimate=0.15,
                    confidence=self._adjust_path_confidence(
                        confidence,
                        goals,
                        action="move_toward_victim_candidate",
                        parameters=path_parameters,
                    ),
                    scope=Scope.local,
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint=(
                        "Victim-search path option; steers toward candidate victim position."
                    ),
                )
            )
            if index >= 4:
                break
        return options

    def _generate_horizon_options(
        self,
        local_analysis_result: Any,
        local_models: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            local_analysis_result,
            default_label="local_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        local_uncertainty = read_value(
            local_analysis_result,
            "local_uncertainty",
            read_value(local_models, "local_uncertainty", None),
        )
        communication_reliability = read_value(
            local_analysis_result,
            "communication_reliability",
            read_value(runtime_models, "communication_reliability", None),
        )
        environment_stability = read_value(
            local_analysis_result,
            "environment_stability",
            read_value(local_models, "environment_stability", None),
        )
        target_entity = read_value(
            local_analysis_result,
            "target_entity",
            read_value(runtime_models, "uav_id", "local_uav"),
        )
        base_parameters = {
            "local_uncertainty": local_uncertainty,
            "communication_reliability": communication_reliability,
            "environment_stability": environment_stability,
        }
        mission_goals = read_mission_goals(runtime_models)
        horizon_options = [
            (
                "short_horizon",
                "short_horizon",
                {"favored_by": ["high_uncertainty", "poor_communication"]},
                "Use a shorter local planning horizon",
                "High uncertainty or poor communication can favor shorter horizons.",
            ),
            (
                "long_horizon",
                "long_horizon",
                {"favored_by": ["stable_environment"]},
                "Use a longer local planning horizon",
                "Stable environment signals can favor longer horizons.",
            ),
            (
                "adaptive_horizon",
                "adaptive_horizon",
                {"favored_by": ["changing_uncertainty", "changing_communication"]},
                "Adapt the local planning horizon dynamically",
                "Adaptive horizon can respond to changing uncertainty and communication.",
            ),
            (
                "increased_replanning_frequency",
                "increased_replanning_frequency",
                {"favored_by": ["high_uncertainty", "poor_communication"]},
                "Increase local replanning frequency",
                "Frequent replanning can help under uncertainty or weak communication.",
            ),
        ]

        return [
            self._build_local_adaptation_option(
                option_id=f"local_horizon_{option_id}",
                option_type="horizon_control",
                target_entity=target_entity,
                parameters={**base_parameters, **parameters, "horizon_action": action},
                mission_goals=mission_goals,
                reason="prioritize_information_gain"
                if action in {"adaptive_horizon", "increased_replanning_frequency", "short_horizon"}
                else "local_horizon_options",
                action=action,
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, parameters, expected_effect, explanation_hint in (
                horizon_options
            )
        ]

    def _generate_movement_strategy_options(
        self,
        local_analysis_result: Any,
        local_models: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, trigger_context, confidence, trigger_signals = adaptation_trigger_metadata(
            local_analysis_result,
            default_label="local_analysis",
        )
        trigger_context = trigger_context.lower()
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        drift_state = read_value(
            local_analysis_result,
            "drift_state",
            read_value(local_models, "drift_state", None),
        )
        local_uncertainty = read_value(
            local_analysis_result,
            "local_uncertainty",
            read_value(local_models, "local_uncertainty", None),
        )
        belief_hotspots = read_value(
            local_analysis_result,
            "belief_hotspots",
            read_value(local_models, "belief_hotspots", []),
        )
        target_entity = read_value(
            local_analysis_result,
            "target_entity",
            read_value(runtime_models, "uav_id", "local_uav"),
        )
        oscillation_risk = read_value(
            local_analysis_result,
            "oscillation_risk",
            read_value(local_models, "oscillation_risk", False),
        )
        path_context = _read_local_path_context(local_models, runtime_models, str(target_entity))
        stuck_count = read_value(local_analysis_result, "stuck_count", None)
        if path_context:
            oscillation_risk = bool(oscillation_risk) or bool(
                path_context.get("oscillation_risk")
            )
            if stuck_count is None:
                stuck_count = path_context.get("stuck_count")
        oscillation_risk = bool(oscillation_risk) or any(
            term in trigger_context
            for term in ("oscillation", "oscillating", "unstable", "instability")
        )
        base_parameters = {
            "drift_state": drift_state,
            "local_uncertainty": local_uncertainty,
            "belief_hotspots": belief_hotspots,
            "oscillation_risk": oscillation_risk,
        }
        if stuck_count is not None:
            base_parameters["stuck_count"] = stuck_count
        if path_context:
            for key in (
                "navigation_confidence",
                "path_safety_score",
                "local_risk_estimate",
                "movement_stability",
                "target_switch_count",
            ):
                if key in path_context and path_context[key] is not None:
                    base_parameters[key] = path_context[key]
        mission_goals = read_mission_goals(runtime_models)
        movement_options = [
            (
                "aggressive_exploration",
                "aggressive_exploration",
                {"target_source": "local_uncertainty"},
                "Use aggressive exploration movement",
                "Movement strategy option only; UAV movement is not executed.",
            ),
            (
                "cautious_movement",
                "cautious_movement",
                {},
                "Use cautious movement",
                "Movement strategy option only; UAV movement is not executed.",
            ),
            (
                "drift_aware_movement",
                "drift_aware_movement",
                {"target_source": "drift_state"},
                "Use drift-aware movement",
                "Movement strategy option only; UAV movement is not executed.",
            ),
            (
                "hold_position",
                "hold_position",
                {},
                "Hold current position",
                "Hold-position option is always available.",
            ),
            (
                "directed_belief_hotspot_search",
                "directed_belief_hotspot_search",
                {"target_regions": belief_hotspots},
                "Search toward belief hotspots",
                "Movement strategy option only; UAV movement is not executed.",
            ),
        ]
        if oscillation_risk:
            movement_options.append(
                (
                    "smooth_transition_movement",
                    "smooth_transition_movement",
                    {"triggered_by": "oscillation_risk"},
                    "Use smooth transition movement",
                    "Oscillation risk suggests considering smoother movement transitions.",
                )
            )

        return [
            self._build_local_adaptation_option(
                option_id=f"local_movement_{option_id}",
                option_type="movement_strategy",
                target_entity=target_entity,
                parameters={**base_parameters, **parameters, "movement_action": action},
                mission_goals=mission_goals,
                reason="prioritize_uav_survivability"
                if action
                in {
                    "cautious_movement",
                    "hold_position",
                    "drift_aware_movement",
                    "smooth_transition_movement",
                }
                else "prioritize_information_gain"
                if action in {"aggressive_exploration", "directed_belief_hotspot_search"}
                else "local_movement_options",
                action=action,
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, parameters, expected_effect, explanation_hint in (
                movement_options
            )
        ]

    def _generate_sensing_options(
        self,
        local_analysis_result: Any,
        local_models: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        def as_region_list(source: Any) -> list[Any]:
            if isinstance(source, dict):
                return list(source.keys())
            if isinstance(source, (list, tuple, set)):
                return list(source)
            return []

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            local_analysis_result,
            default_label="local_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        local_uncertainty = read_value(
            local_analysis_result,
            "local_uncertainty",
            read_value(local_models, "local_uncertainty", {}),
        )
        fire_belief = read_value(
            local_analysis_result,
            "fire_belief",
            read_value(local_models, "fire_belief", {}),
        )
        victim_confidence = read_value(
            local_analysis_result,
            "victim_confidence",
            read_value(local_models, "victim_confidence", {}),
        )
        stale_regions = as_region_list(
            read_value(
                local_analysis_result,
                "stale_regions",
                read_value(local_models, "stale_regions", []),
            )
        )
        recently_confirmed_empty_regions = as_region_list(
            read_value(
                local_analysis_result,
                "recently_confirmed_empty_regions",
                read_value(local_models, "recently_confirmed_empty_regions", []),
            )
        )
        avoid_regions = [
            region for region in recently_confirmed_empty_regions if region not in stale_regions
        ]
        target_entity = read_value(
            local_analysis_result,
            "target_entity",
            read_value(runtime_models, "uav_id", "local_uav"),
        )
        base_parameters = {
            "local_uncertainty": local_uncertainty,
            "fire_belief": fire_belief,
            "victim_confidence": victim_confidence,
            "stale_regions": stale_regions,
            "avoid_recently_confirmed_empty_regions": avoid_regions,
        }
        mission_goals = read_mission_goals(runtime_models)

        def nonempty_map(m: Any) -> bool:
            return isinstance(m, dict) and len(m) > 0

        has_sensing_evidence = (
            nonempty_map(local_uncertainty)
            or nonempty_map(fire_belief)
            or nonempty_map(victim_confidence)
            or len(stale_regions) > 0
        )

        if has_sensing_evidence:
            sensing_options: list[tuple[str, str, dict[str, Any], str, str]] = [
                (
                    "increase_sensing_frequency",
                    "increase_sensing_frequency",
                    {"priority_regions": stale_regions},
                    "Increase sensing frequency",
                    (
                        "Enumerated sensing option only: prioritize revisiting stale regions; "
                        "no sensing schedule is executed."
                    ),
                ),
                (
                    "focus_sensing_on_uncertainty",
                    "focus_sensing_on_uncertainty",
                    {"target_source": "local_uncertainty"},
                    "Focus sensing on uncertain regions",
                    (
                        "Enumerated sensing option only: steer attention toward local uncertainty; "
                        "no sensing change is executed."
                    ),
                ),
                (
                    "focus_sensing_on_fire_belief",
                    "focus_sensing_on_fire_belief",
                    {"target_source": "fire_belief"},
                    "Focus sensing on fire belief regions",
                    (
                        "Enumerated sensing option only: align sensing emphasis with fire belief map; "
                        "no sensing change is executed."
                    ),
                ),
                (
                    "focus_sensing_on_victim_confirmation",
                    "focus_sensing_on_victim_confirmation",
                    {"target_source": "victim_confidence"},
                    "Focus sensing on victim confirmation",
                    (
                        "Enumerated sensing option only: emphasize victim-confirmation sensing; "
                        "no sensing change is executed."
                    ),
                ),
            ]
        else:
            stability_hint = (
                "Stability baseline sensing option; no sensing parameters are applied or executed."
            )
            sensing_options = [
                (
                    "maintain_current_sensing",
                    "maintain_current_sensing",
                    {},
                    "Maintain current sensing configuration",
                    stability_hint,
                ),
                (
                    "reduce_sensing_battery_save",
                    "reduce_sensing_battery_save",
                    {},
                    "Reduce sensing duty cycle to conserve onboard energy",
                    stability_hint,
                ),
            ]

        if not sensing_options:
            fallback_hint = (
                "Fallback stability sensing option; no sensing parameters are applied or executed."
            )
            sensing_options = [
                (
                    "maintain_current_sensing",
                    "maintain_current_sensing",
                    {},
                    "Maintain current sensing configuration",
                    fallback_hint,
                ),
                (
                    "reduce_sensing_battery_save",
                    "reduce_sensing_battery_save",
                    {},
                    "Reduce sensing duty cycle to conserve onboard energy",
                    fallback_hint,
                ),
            ]

        return [
            LocalAdaptationOption(
                option_id=f"local_sensing_{option_id}",
                option_type="sensing_strategy",
                target_entity=target_entity,
                parameters=self._merge_mission_goal_parameters(
                    {**base_parameters, **parameters, "sensing_action": action},
                    mission_goals,
                    reason="prioritize_information_gain"
                    if action
                    in {
                        "focus_sensing_on_uncertainty",
                        "increase_sensing_frequency",
                    }
                    else "local_sensing_options",
                ),
                expected_effect=expected_effect,
                cost_estimate=0.0 if not has_sensing_evidence else 1.0,
                risk_estimate=0.0 if not has_sensing_evidence else 0.2,
                confidence=(
                    1.0
                    if not has_sensing_evidence
                    else self._adjust_path_confidence(
                        confidence,
                        mission_goals,
                        action=action,
                        parameters=parameters,
                    )
                ),
                scope=Scope.local,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, parameters, expected_effect, explanation_hint in (
                sensing_options
            )
        ]

    def _generate_communication_options(
        self,
        local_analysis_result: Any,
        local_models: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            local_analysis_result,
            default_label="local_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        delivery_confidence = read_value(
            local_analysis_result,
            "delivery_confidence",
            read_value(local_models, "delivery_confidence", None),
        )
        shared_knowledge_sync_quality = read_value(
            local_analysis_result,
            "shared_knowledge_sync_quality",
            read_value(local_models, "shared_knowledge_sync_quality", None),
        )
        target_entity = read_value(
            local_analysis_result,
            "target_entity",
            read_value(runtime_models, "uav_id", "local_uav"),
        )
        base_parameters = {
            "delivery_confidence": delivery_confidence,
            "shared_knowledge_sync_quality": shared_knowledge_sync_quality,
        }
        mission_goals = read_mission_goals(runtime_models)
        communication_options = [
            (
                "normal_communication",
                "normal_communication",
                "Use normal communication strategy",
                "Communication option only; no communication behavior is changed.",
            ),
            (
                "relay_mode",
                "relay_mode",
                "Consider relay-mode communication",
                "Relay behavior is not activated by this option.",
            ),
            (
                "reduced_communication",
                "reduced_communication",
                "Reduce communication activity",
                "Communication option only; no communication behavior is changed.",
            ),
            (
                "prioritize_critical_messages",
                "prioritize_critical_messages",
                "Prioritize critical messages",
                "Delivery confidence and sync quality can inform critical message priority.",
            ),
        ]

        return [
            self._build_local_adaptation_option(
                option_id=f"local_communication_{option_id}",
                option_type="communication_strategy",
                target_entity=target_entity,
                parameters={**base_parameters, "communication_action": action},
                mission_goals=mission_goals,
                reason="prioritize_uav_survivability"
                if action == "reduced_communication"
                else "prioritize_information_gain"
                if action == "prioritize_critical_messages"
                else "local_communication_options",
                action=action,
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, expected_effect, explanation_hint in communication_options
        ]

    def _generate_stability_options(
        self,
        local_analysis_result: Any,
        local_models: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, trigger_context, confidence, trigger_signals = adaptation_trigger_metadata(
            local_analysis_result,
            default_label="local_analysis",
        )
        trigger_context = trigger_context.lower()
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        current_path = read_value(
            local_analysis_result,
            "current_path",
            read_value(local_models, "current_path", None),
        )
        current_assignment = read_value(
            local_analysis_result,
            "current_assignment",
            read_value(local_models, "current_assignment", None),
        )
        stability_state = read_value(
            local_analysis_result,
            "stability_state",
            read_value(local_models, "stability_state", None),
        )
        instability_detected = any(
            term in trigger_context
            for term in ("instability", "unstable", "oscillation", "oscillating")
        )
        target_entity = read_value(
            local_analysis_result,
            "target_entity",
            read_value(runtime_models, "uav_id", "local_uav"),
        )
        base_parameters = {
            "current_path": current_path,
            "current_assignment": current_assignment,
            "stability_state": stability_state,
            "instability_detected": instability_detected,
        }
        mission_goals = read_mission_goals(runtime_models)
        stability_options = [
            (
                "do_nothing",
                "do_nothing",
                "Make no local adaptation",
                "Always available stability option; no changes are executed.",
            ),
            (
                "keep_current_path",
                "keep_current_path",
                "Keep current path for stability",
                "Stability option only; current path is not modified.",
            ),
            (
                "keep_current_assignment",
                "keep_current_assignment",
                "Keep current assignment for stability",
                "Stability option only; current assignment is not modified.",
            ),
            (
                "partial_adaptation",
                "partial_adaptation",
                "Apply only partial local adaptation",
                "Partial adaptation can limit abrupt local changes.",
            ),
            (
                "gradual_adaptation",
                "gradual_adaptation",
                "Apply local adaptation gradually",
                "Gradual adaptation can support local stability.",
            ),
        ]
        if instability_detected:
            stability_options.append(
                (
                    "delayed_adaptation",
                    "delayed_adaptation",
                    "Delay local adaptation during instability",
                    "Instability or oscillation trigger suggests delaying adaptation.",
                )
            )

        return [
            self._build_local_adaptation_option(
                option_id=f"local_stability_{option_id}",
                option_type="stability_control",
                target_entity=target_entity,
                parameters={**base_parameters, "stability_action": action},
                mission_goals=mission_goals,
                reason="prioritize_uav_survivability"
                if action
                in {
                    "do_nothing",
                    "keep_current_path",
                    "keep_current_assignment",
                    "delayed_adaptation",
                    "gradual_adaptation",
                    "partial_adaptation",
                }
                else "local_stability_options",
                action=action,
                expected_effect=expected_effect,
                cost_estimate=0.0 if option_id == "do_nothing" else 1.0,
                risk_estimate=0.0 if option_id == "do_nothing" else 0.2,
                confidence=confidence,
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, expected_effect, explanation_hint in stability_options
        ]
