"""Deterministic MAPE integration: wind direction affects victim-searcher trajectories."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Callable

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.execution.uav_executor import UAVExecutor
from wildfire_model import WildFireModel

DEFAULT_SEED = 42
DEFAULT_STEPS = 40
GRID_CENTER = (cfv.HEIGHT // 2, cfv.WIDTH // 2)


@dataclass
class WindSimTrace:
    wind: str
    positions: list[tuple[int, int]] = field(default_factory=list)
    wind_aware_actions: int = 0
    victim_target_actions: int = 0
    wind_explanations: list[dict] = field(default_factory=list)
    wind_option_hits: int = 0
    wind_planning_targets: list[tuple[float, float]] = field(default_factory=list)
    exec_actions: list[str] = field(default_factory=list)
    final_target: tuple[float, float] | None = None
    model: WildFireModel | None = None

    @property
    def final_position(self) -> tuple[int, int] | None:
        return self.positions[-1] if self.positions else None

    @property
    def final_quadrant(self) -> str | None:
        if not self.positions:
            return None
        return _position_quadrant(self.positions[-1])


def _seed_deterministic_environment(wind: str, seed: int = DEFAULT_SEED) -> random.Random:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    cfv.WIND_DIRECTION = wind
    cfv.FIRE_SPREAD_MULTIPLIER = 0.75
    cfv.BATCH_SIZE = 99_999
    os.environ["WIND_DIRECTION"] = wind
    return rng


def _apply_model_wind(model: WildFireModel, wind: str) -> None:
    wind_agent = getattr(model, "wind", None)
    if wind_agent is not None:
        wind_agent.wind_direction = wind
    model._sync_environment_wind(float(getattr(model, "evaluation_timesteps_counter", 0)))


def _victim_searcher_id(model: WildFireModel) -> str:
    for uid, state in model.managed_uav_states.items():
        if getattr(state, "role", "") == "victim_searcher":
            return str(uid)
    uavs = [a for a in model.schedule.agents if type(a) is agents.UAV]
    if uavs:
        return str(uavs[-1].unique_id)
    raise AssertionError("no victim_searcher UAV")


def _uav_agent(model: WildFireModel, uav_id: str) -> agents.UAV:
    for agent in model.schedule.agents:
        if type(agent) is agents.UAV and str(agent.unique_id) == str(uav_id):
            return agent
    raise AssertionError(f"uav {uav_id} not found")


def _last_exec_action(model: WildFireModel, uav_id: str) -> str | None:
    execution = getattr(model, "latest_execution_result", None)
    if not isinstance(execution, dict):
        return None
    local = execution.get("local")
    if not isinstance(local, dict):
        return None
    uav_results = local.get("uav_results")
    if not isinstance(uav_results, dict):
        return None
    result = uav_results.get(str(uav_id))
    if not isinstance(result, dict):
        return None
    action = result.get("action")
    return str(action) if action is not None else None


def _latest_path_decision(model: WildFireModel, uav_id: str) -> object | None:
    planning = getattr(model, "latest_planning_result", None)
    if planning is None:
        return None
    if isinstance(planning, dict):
        decisions = planning.get("path_decisions", {})
    else:
        decisions = getattr(planning, "path_decisions", None)
    if isinstance(decisions, dict):
        return decisions.get(str(uav_id))
    if isinstance(decisions, (list, tuple)):
        for item in decisions:
            if str(getattr(item, "uav_id", "")) == str(uav_id):
                return item
    return None


def _planner_target_from_model(model: WildFireModel, uav_id: str) -> tuple[float, float] | None:
    decision = _latest_path_decision(model, uav_id)
    if decision is None:
        return None
    ctx = getattr(decision, "uncertainty_context", None)
    if not isinstance(ctx, dict):
        return None
    raw = ctx.get("target_position") or ctx.get("target_region")
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return None
    return (float(raw[0]), float(raw[1]))


def _position_quadrant(pos: tuple[int, int], center: tuple[int, int] = GRID_CENTER) -> str:
    x, y = pos
    cx, cy = center
    ns = "north" if y >= cy else "south"
    ew = "east" if x >= cx else "west"
    return f"{ns}_{ew}"


def _configure_no_live_victims(model: WildFireModel) -> None:
    """Keep victim markers out of UAV radius so wind-aware search stays active."""
    model.victim_runtime_model.victims.clear()
    hide_cell = (1, 1)
    for victim_id, marker in model.victim_marker_agents.items():
        if marker.pos is not None:
            model.grid.move_agent(marker, hide_cell)
        managed = model.managed_victims.get(victim_id)
        if managed is not None:
            managed.status = "rescued"
            managed.rescued = True
            managed.confirmed = False
            managed.needs_confirmation = False
        marker.status = "rescued"


def _configure_live_victim(
    model: WildFireModel,
    *,
    victim_id: str = "victim_0",
    position: tuple[float, float] = (30.0, 30.0),
) -> None:
    _configure_no_live_victims(model)
    grid_pos = (int(round(position[0])), int(round(position[1])))
    marker = model.victim_marker_agents[victim_id]
    model.grid.move_agent(marker, grid_pos)
    marker.status = "detected"
    managed = model.managed_victims[victim_id]
    managed.status = "detected"
    managed.rescued = False
    managed.confirmed = False
    managed.needs_confirmation = False
    managed.last_known_position = position
    for other_id in list(model.managed_victims.keys()):
        if other_id == victim_id:
            continue
        other = model.managed_victims[other_id]
        other.status = "rescued"
        other.rescued = True
        model.victim_marker_agents[other_id].status = "rescued"
    model.victim_runtime_model.victims.clear()
    model.victim_runtime_model.update_detection(
        victim_id=victim_id,
        position=position,
        timestamp=1.0,
        source="test_fixture",
        confidence=0.9,
    )


def _latest_wind_option_target(model: WildFireModel) -> tuple[float, float] | None:
    snap = getattr(model, "latest_adaptation_space_snapshot", None)
    if snap is None:
        return None
    for space in getattr(snap, "local_spaces", ()) or ():
        for opt in getattr(space, "options", ()) or ():
            if getattr(opt, "option_id", "") != "wind_aware_victim_search":
                continue
            params = getattr(opt, "parameters", None)
            if not isinstance(params, dict):
                continue
            raw = params.get("target_position") or params.get("target_region")
            if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                return (float(raw[0]), float(raw[1]))
    return None


def _count_wind_options(model: WildFireModel) -> int:
    return 1 if _latest_wind_option_target(model) is not None else 0


def _run_wind_simulation(
    wind: str,
    steps: int = DEFAULT_STEPS,
    *,
    seed: int = DEFAULT_SEED,
    setup: Callable[[WildFireModel], None] | None = None,
) -> WindSimTrace:
    _seed_deterministic_environment(wind, seed=seed)
    model = WildFireModel()
    _apply_model_wind(model, wind)
    if setup is not None:
        setup(model)
    else:
        _configure_no_live_victims(model)

    vs_id = _victim_searcher_id(model)
    agent = _uav_agent(model, vs_id)
    trace = WindSimTrace(wind=wind)

    for _ in range(steps):
        model.step()
        pos = agent.pos
        trace.positions.append((int(pos[0]), int(pos[1])))

        action = _last_exec_action(model, vs_id)
        if action:
            trace.exec_actions.append(action)
        if action == "victim_search_wind_aware":
            trace.wind_aware_actions += 1
        elif action == "computed_from_target":
            trace.victim_target_actions += 1

        expl = getattr(agent, "last_explanation", None)
        if isinstance(expl, dict) and expl.get("decision") == "victim_search_wind_aware":
            trace.wind_explanations.append(dict(expl))

        if _count_wind_options(model):
            trace.wind_option_hits += 1
            opt_target = _latest_wind_option_target(model)
            if opt_target is not None:
                trace.wind_planning_targets.append(opt_target)

    trace.final_target = _planner_target_from_model(model, vs_id)
    trace.model = model
    return trace


def _assert_wind_aware_behavior(trace: WindSimTrace) -> None:
    assert trace.wind_aware_actions >= 1, (
        f"{trace.wind}: expected victim_search_wind_aware action"
    )
    assert len(trace.wind_explanations) >= 1, (
        f"{trace.wind}: expected wind-aware explanation on agent"
    )
    assert trace.wind_option_hits >= 1, (
        f"{trace.wind}: expected wind_aware_victim_search adaptation option"
    )


def _assert_position_not_on_hazard(model: WildFireModel, pos: tuple[int, int]) -> None:
    vs_id = _victim_searcher_id(model)
    agent = _uav_agent(model, vs_id)
    executor = UAVExecutor(uav_id=vs_id, model=model, agent=agent)
    cell = (int(pos[0]), int(pos[1]))
    assert not executor._cell_high_fire(cell), f"position {pos} on active fire"
    assert not executor._cell_smoke_obscured(cell), f"position {pos} in smoke"


def _assert_planning_targets_differ(a: WindSimTrace, b: WindSimTrace) -> None:
    a_targets = set(a.wind_planning_targets)
    b_targets = set(b.wind_planning_targets)
    assert a_targets or b_targets, "expected wind planning targets during MAPE run"
    if a_targets and b_targets:
        assert a_targets != b_targets, (
            f"wind planning targets should differ: {a.wind}={a_targets} {b.wind}={b_targets}"
        )
    if a.final_target is not None and b.final_target is not None:
        assert a.final_target != b.final_target


def _assert_trajectory_or_region_diverged(a: WindSimTrace, b: WindSimTrace) -> None:
    """Physical positions may converge; planner targets / mid-run path should differ."""
    _assert_planning_targets_differ(a, b)
    mid = max(1, len(a.positions) // 2) - 1
    diverged = (
        a.final_position != b.final_position
        or a.positions[mid] != b.positions[mid]
        or a.final_quadrant != b.final_quadrant
    )
    assert diverged, (
        f"expected distinct trajectory or region for {a.wind} vs {b.wind}: "
        f"final=({a.final_position}, {b.final_position}) mid=({a.positions[mid]}, {b.positions[mid]})"
    )


def test_north_vs_south_trajectories_diverge_over_40_steps() -> None:
    north = _run_wind_simulation("north", steps=40, seed=DEFAULT_SEED)
    south = _run_wind_simulation("south", steps=40, seed=DEFAULT_SEED)

    _assert_wind_aware_behavior(north)
    _assert_wind_aware_behavior(south)
    _assert_trajectory_or_region_diverged(north, south)


def test_east_vs_west_trajectories_diverge_over_40_steps() -> None:
    east = _run_wind_simulation("east", steps=40, seed=DEFAULT_SEED)
    west = _run_wind_simulation("west", steps=40, seed=DEFAULT_SEED)

    _assert_wind_aware_behavior(east)
    _assert_wind_aware_behavior(west)
    _assert_trajectory_or_region_diverged(east, west)


def test_all_cardinals_produce_distinct_regions_and_safe_positions() -> None:
    steps = 35
    traces = {
        wind: _run_wind_simulation(wind, steps=steps, seed=DEFAULT_SEED)
        for wind in ("north", "south", "east", "west")
    }

    final_positions: set[tuple[int, int]] = set()
    planning_targets: set[tuple[float, float]] = set()

    for wind, trace in traces.items():
        _assert_wind_aware_behavior(trace)
        assert trace.final_position is not None
        final_positions.add(trace.final_position)
        planning_targets.update(trace.wind_planning_targets)
        if trace.final_target is not None:
            planning_targets.add(trace.final_target)

    distinct_regions = len(planning_targets) if planning_targets else len(final_positions)
    assert distinct_regions >= 3, (
        f"expected >=3 distinct planning targets or positions, "
        f"targets={planning_targets} positions={final_positions}"
    )

    for trace in traces.values():
        assert trace.final_position is not None
        assert trace.model is not None
        _assert_position_not_on_hazard(trace.model, trace.final_position)


def test_known_victim_overrides_wind_aware_exploration() -> None:
    """While victim is live, pursuit stays victim-directed (not wind-aware)."""

    def _setup(model: WildFireModel) -> None:
        # Low-fire corner keeps victim alive long enough to observe pursuit behavior.
        _configure_live_victim(model, victim_id="victim_0", position=(8.0, 8.0))
        vs_id = _victim_searcher_id(model)
        agent = _uav_agent(model, vs_id)
        model.grid.move_agent(agent, (6, 8))

    trace = _run_wind_simulation("north", steps=18, seed=DEFAULT_SEED, setup=_setup)

    victim_directed_labels = (
        "computed_from_target",
        "victim_escape_committed",
        "victim_stuck_escape",
    )
    early_window = trace.exec_actions[:14]
    victim_directed = any(a in victim_directed_labels for a in early_window)
    assert victim_directed, (
        f"expected victim_searcher to pursue known victim early, actions={early_window}"
    )
    assert not any(a == "victim_search_wind_aware" for a in early_window), (
        "wind-aware exploration must not override an active live victim target"
    )
    early_wind_options = trace.wind_planning_targets[:14]
    assert not early_wind_options, (
        "adaptation should not plan wind_aware_victim_search while live victim exists"
    )
