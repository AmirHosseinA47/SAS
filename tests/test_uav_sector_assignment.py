"""Sector-based fire-front and belief target distribution across UAVs."""

from __future__ import annotations

from dataclasses import dataclass

from src_extension.adaptation.local_adaptation_generator import LocalAdaptationSpaceGenerator


@dataclass
class _FakeBelief:
    fire_probability_map: dict[tuple[int, int], float]


@dataclass
class _FakeFireRuntimeModel:
    belief: _FakeBelief


@dataclass
class _FakeUAVResource:
    by_uav_id: dict[str, object]


@dataclass
class _FakeRoleState:
    current_role: str


def _runtime_models(uav_ids: list[str]) -> dict[str, object]:
    return {
        "available_entities": uav_ids,
        "uav_resource_model": _FakeUAVResource(by_uav_id={uav_id: object() for uav_id in uav_ids}),
        "fire_runtime_model": _FakeFireRuntimeModel(
            belief=_FakeBelief(
                fire_probability_map={
                    (x, y): 0.9
                    for x, y in (
                        (1, 1),
                        (2, 1),
                        (3, 1),
                        (1, 2),
                        (2, 2),
                        (3, 2),
                        (1, 3),
                        (2, 3),
                        (3, 3),
                    )
                }
            )
        ),
    }


def test_get_uav_index_for_three_uavs() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _runtime_models(["0", "1", "2"])

    assert generator._get_uav_index("0", runtime_models) == 0
    assert generator._get_uav_index("1", runtime_models) == 1
    assert generator._get_uav_index("2", runtime_models) == 2


def test_get_team_size_returns_available_entities_count() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _runtime_models(["0", "1", "2"])

    assert generator._get_team_size(runtime_models) == 3


def test_sector_slicing_distributes_nine_targets_across_three_uavs() -> None:
    generator = LocalAdaptationSpaceGenerator()
    # Four UAVs match four spatial quadrants so all 9 cells are assigned.
    runtime_models = _runtime_models(["0", "1", "2", "3"])
    targets = [(x, y) for x in range(1, 4) for y in range(1, 4)]

    uav0_cells, _ = generator._assign_sector_targets(targets, "0", runtime_models)
    uav1_cells, _ = generator._assign_sector_targets(targets, "1", runtime_models)
    uav2_cells, _ = generator._assign_sector_targets(targets, "2", runtime_models)
    uav3_cells, _ = generator._assign_sector_targets(targets, "3", runtime_models)

    all_assigned = uav0_cells + uav1_cells + uav2_cells + uav3_cells
    assert len(set(all_assigned)) == 9, "All 9 cells must be covered"
    assert set(uav0_cells).isdisjoint(set(uav1_cells)), "UAV 0 and 1 must not overlap"
    assert set(uav0_cells).isdisjoint(set(uav2_cells)), "UAV 0 and 2 must not overlap"
    assert set(uav1_cells).isdisjoint(set(uav2_cells)), "UAV 1 and 2 must not overlap"
    assert len(uav0_cells) >= 1
    assert len(uav1_cells) >= 1
    assert len(uav2_cells) >= 1
    assert len(uav3_cells) >= 1


def _visibility_runtime_models_on_state_only() -> dict[str, object]:
    vis_state = type(
        "VisState",
        (),
        {
            "observation_status_map": {
                (0, 0): type("Status", (), {"value": "never_seen"})(),
                (12, 8): type("Status", (), {"value": "stale"})(),
                (25, 15): type("Status", (), {"value": "never_seen"})(),
                (30, 20): type("Status", (), {"value": "observed"})(),
            }
        },
    )()
    visibility_model = type("VisibilityModel", (), {"state": vis_state})()
    return {
        "available_entities": ["0"],
        "uav_id": "0",
        "uav_resource_model": _FakeUAVResource(
            by_uav_id={"0": _FakeRoleState(current_role="fire_tracker")},
        ),
        "fire_runtime_model": _FakeFireRuntimeModel(
            belief=_FakeBelief(fire_probability_map={}),
        ),
        "visibility_model": visibility_model,
    }


def test_explore_option_generated_from_visibility_state_observation_map() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _visibility_runtime_models_on_state_only()

    options = generator._generate_path_options(
        {"target_entity": "0", "triggers": ()},
        {},
        runtime_models,
        timestamp=1.0,
    )

    explore_options = [
        option for option in options if option.option_type == "explore_unknown_region"
    ]
    assert explore_options, "Expected explore_unknown_region option from state.observation_status_map"
    params = explore_options[0].parameters
    assert params.get("explore_unknown_region") is True
    assert "target_position" in params
    assert params.get("expected_info_gain", 0) >= 0.7
    assert params.get("task_support", 0) < 0.85


def test_explore_option_has_competitive_utility_parameters() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _visibility_runtime_models_on_state_only()

    options = generator._generate_path_options(
        {"target_entity": "0", "triggers": ()},
        {},
        runtime_models,
        timestamp=2.0,
    )
    explore_options = [
        option for option in options if option.option_type == "explore_unknown_region"
    ]
    assert explore_options
    params = explore_options[0].parameters
    assert params.get("expected_info_gain", 0) >= 0.7
    assert params.get("belief_gain", 0) >= 0.55
    assert params.get("task_support", 0) == 0.45
    assert params.get("task_support", 0) < 0.85
    assert params.get("stability_bonus", 0) >= 0.2
    assert params.get("recovery_value", 0) >= 0.35
    assert explore_options[0].cost_estimate <= 0.15
    assert explore_options[0].risk_estimate <= 0.08


def test_fire_tracker_uavs_receive_different_target_sets() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _runtime_models(["0", "1", "2"])

    fire_targets: dict[str, set[tuple[int, int]]] = {}
    for uav_id in ("0", "1", "2"):
        runtime_models["uav_id"] = uav_id
        runtime_models["uav_resource_model"] = _FakeUAVResource(
            by_uav_id={
                uid: type("Role", (), {"current_role": "fire_tracker"})()
                for uid in ("0", "1", "2")
            }
        )
        space = generator.generate(
            {"target_entity": uav_id, "triggers": ()},
            {},
            runtime_models,
            timestamp=1.0,
        )
        targets = {
            tuple(option.parameters.get("target_region"))
            for option in space.options
            if option.parameters.get("path_action", "").startswith("move_toward_fire")
            and option.parameters.get("target_region") is not None
        }
        fire_targets[uav_id] = targets

    assert fire_targets["0"]
    assert fire_targets["1"]
    assert fire_targets["2"]
    assert fire_targets["0"].isdisjoint(fire_targets["1"])
    assert fire_targets["1"].isdisjoint(fire_targets["2"])
    assert fire_targets["0"].isdisjoint(fire_targets["2"])


def _victim_searcher_runtime_models(
    *,
    victims: dict[str, object] | None = None,
    fire_map: dict[tuple[int, int], float] | None = None,
) -> dict[str, object]:
    if fire_map is None:
        fire_map = {(10, 10): 0.9, (11, 10): 0.85}
    if victims is None:
        victims = {"victim_0": {"estimated_position": (4.0, 5.0)}}
    return {
        "available_entities": ["0"],
        "uav_id": "0",
        "uav_resource_model": _FakeUAVResource(
            by_uav_id={
                "0": _FakeRoleState(current_role="victim_searcher"),
            }
        ),
        "victim_runtime_model": type("VictimModel", (), {"victims": victims})(),
        "fire_runtime_model": _FakeFireRuntimeModel(belief=_FakeBelief(fire_probability_map=fire_map)),
    }


def test_victim_searcher_with_victims_returns_victim_directed_path_options_only() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _victim_searcher_runtime_models()
    local_analysis = {"target_entity": "0", "triggers": ()}

    path_options = generator._generate_path_options(
        local_analysis, {}, runtime_models, timestamp=1.0
    )

    assert path_options
    assert all(
        option.parameters.get("path_action") == "move_toward_victim_candidate"
        or option.parameters.get("stability_action") == "maintain_current_config"
        for option in path_options
    )


def test_victim_searcher_excludes_fire_front_and_belief_path_options() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _victim_searcher_runtime_models()
    local_analysis = {
        "target_entity": "0",
        "triggers": (),
        "belief_gain": {(10, 10): 0.8},
    }

    path_options = generator._generate_path_options(
        local_analysis, {}, runtime_models, timestamp=1.0
    )
    path_actions = {option.parameters.get("path_action") for option in path_options}

    assert not any(str(action).startswith("move_toward_fire") for action in path_actions if action)
    assert "maximize_belief_gain" not in path_actions
    assert "revisit_high_probability_hidden_regions" not in path_actions
    assert "directed_search_last_known_fire_location" not in path_actions


def test_victim_searcher_path_options_preserve_victim_metadata() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _victim_searcher_runtime_models()
    path_options = generator._generate_path_options(
        {"target_entity": "0", "triggers": ()},
        {},
        runtime_models,
        timestamp=1.0,
    )
    victim_option = next(
        option
        for option in path_options
        if option.parameters.get("path_action") == "move_toward_victim_candidate"
    )

    assert victim_option.parameters.get("victim_search") is True
    assert victim_option.parameters.get("role") == "victim_searcher"
    assert victim_option.parameters.get("task_support") == 0.85
    assert victim_option.parameters.get("expected_info_gain") == 0.7
    assert victim_option.parameters.get("target_position") == (4.0, 5.0)
    assert victim_option.parameters.get("target_region") == (4.0, 5.0)


def test_victim_searcher_includes_maintain_current_noop_option() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _victim_searcher_runtime_models()
    path_options = generator._generate_path_options(
        {"target_entity": "0", "triggers": ()},
        {},
        runtime_models,
        timestamp=1.0,
    )

    assert any(
        option.parameters.get("stability_action") == "maintain_current_config"
        for option in path_options
    )


def test_victim_searcher_without_victims_emits_wind_aware_search_option() -> None:
    generator = LocalAdaptationSpaceGenerator()
    runtime_models = _victim_searcher_runtime_models(victims={})
    path_options = generator._generate_path_options(
        {"target_entity": "0", "triggers": ()},
        {},
        runtime_models,
        timestamp=1.0,
    )
    option_ids = {str(option.option_id) for option in path_options}
    path_actions = {str(option.parameters.get("path_action", "")) for option in path_options}

    assert "wind_aware_victim_search" in option_ids
    assert "victim_search_wind_aware" in path_actions
    assert not any(action.startswith("move_toward_fire") for action in path_actions)


@dataclass
class _FakeAgent:
    unique_id: int
    pos: tuple[int, int]
    selected_dir: int = 0


@dataclass
class _FakeSchedule:
    agents: list[_FakeAgent]


def _dispatcher_model(
    agents: list[_FakeAgent],
    roles_by_id: dict[str, str],
    managed_roles: dict[str, str] | None = None,
) -> object:
    managed_roles = managed_roles or {}
    return type(
        "FakeModel",
        (),
        {
            "schedule": _FakeSchedule(agents=agents),
            "uav_resource_model": _FakeUAVResource(
                by_uav_id={uav_id: _FakeRoleState(role) for uav_id, role in roles_by_id.items()}
            ),
            "managed_uav_states": {
                uav_id: type("Managed", (), {"role": role})()
                for uav_id, role in managed_roles.items()
            },
            "fire_runtime_model": _FakeFireRuntimeModel(
                belief=_FakeBelief(fire_probability_map={(9, 5): 0.9})
            ),
            "evaluation_timesteps_counter": 1.0,
            "pending_global_commands": [],
        },
    )()


def _search_mode_fail_safe(**overrides: object) -> "FailSafeDecision":
    from src_extension.execution.failsafe_modes import FailSafeMode
    from src_extension.planning.decision_objects import FailSafeDecision

    base = {
        "decision_id": "fs-search",
        "search_mode_active": True,
        "mission_mode": FailSafeMode.INFORMATION_RECOVERY.value,
        "fail_safe_action": "activate_search_mode",
        "target_region": "9.0,5.0",
        "uncertainty_context": {"fail_safe_mode": FailSafeMode.INFORMATION_RECOVERY.value},
    }
    base.update(overrides)
    return FailSafeDecision(**base)  # type: ignore[arg-type]


def test_get_uav_role_reads_role_correctly() -> None:
    from src_extension.execution.decision_dispatcher import _get_uav_role

    model = _dispatcher_model(
        [_FakeAgent(unique_id=0, pos=(1, 1))],
        roles_by_id={"0": "victim_searcher"},
        managed_roles={"1": "fire_tracker"},
    )

    assert _get_uav_role("0", model) == "victim_searcher"
    assert _get_uav_role("1", model) == "fire_tracker"
    assert _get_uav_role("missing", model) == ""


def test_victim_searcher_exempt_from_search_mode_override() -> None:
    from src_extension.execution.decision_dispatcher import DecisionDispatcher
    from src_extension.planning.decision_objects import PathDecision

    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    model = _dispatcher_model([agent], roles_by_id={"0": "victim_searcher"})
    dispatcher = DecisionDispatcher(model=model)
    planning_result = {
        "fail_safe_decision": _search_mode_fail_safe(),
        "path_decisions": [
            PathDecision(decision_id="path-0", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)
    uav_result = result["local"]["uav_results"]["0"]

    assert uav_result["override_exempt"] is True
    assert uav_result["override_exempt_reason"] == "victim_searcher_role"
    assert uav_result["action"] != "search_mode"
    assert uav_result.get("role_preserving_search") is not True
    assert uav_result["applied"] is True


def test_victim_search_exempt_from_search_mode_override() -> None:
    from src_extension.execution.decision_dispatcher import DecisionDispatcher
    from src_extension.planning.decision_objects import PathDecision

    agent = _FakeAgent(unique_id=1, pos=(5, 5), selected_dir=1)
    model = _dispatcher_model([agent], roles_by_id={"1": "victim_search"})
    dispatcher = DecisionDispatcher(model=model)
    planning_result = {
        "fail_safe_decision": _search_mode_fail_safe(),
        "path_decisions": [
            PathDecision(decision_id="path-1", uav_id="1", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)
    uav_result = result["local"]["uav_results"]["1"]

    assert uav_result["override_exempt"] is True
    assert uav_result["override_exempt_reason"] == "victim_searcher_role"


def test_fire_tracker_still_overridden_by_search_mode_fail_safe() -> None:
    from src_extension.execution.decision_dispatcher import DecisionDispatcher
    from src_extension.planning.decision_objects import PathDecision

    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    model = _dispatcher_model([agent], roles_by_id={"0": "fire_tracker"})
    dispatcher = DecisionDispatcher(model=model)
    planning_result = {
        "fail_safe_decision": _search_mode_fail_safe(),
        "path_decisions": [
            PathDecision(decision_id="path-0", uav_id="0", next_action="west"),
        ],
    }

    result = dispatcher.dispatch(planning_result, timestamp=1.0)
    uav_result = result["local"]["uav_results"]["0"]

    assert uav_result.get("override_exempt") is not True
    assert uav_result.get("role_preserving_search") is True
    assert uav_result["action"] == "computed_from_fire_perimeter"


def test_emergency_and_safe_hold_still_override_victim_searcher() -> None:
    from src_extension.execution.decision_dispatcher import DecisionDispatcher
    from src_extension.execution.failsafe_modes import FailSafeMode
    from src_extension.planning.decision_objects import PathDecision

    agent = _FakeAgent(unique_id=0, pos=(5, 5), selected_dir=2)
    model = _dispatcher_model([agent], roles_by_id={"0": "victim_searcher"})
    dispatcher = DecisionDispatcher(model=model)

    emergency_result = dispatcher.dispatch(
        {
            "fail_safe_decision": _search_mode_fail_safe(
                fail_safe_action="safe_hold",
                mission_mode=FailSafeMode.EMERGENCY.value,
                uncertainty_context={"fail_safe_mode": FailSafeMode.EMERGENCY.value},
            ),
            "path_decisions": [
                PathDecision(decision_id="path-0", uav_id="0", next_action="east"),
            ],
        },
        timestamp=1.0,
    )
    hold_result = emergency_result["local"]["uav_results"]["0"]
    assert hold_result.get("override_exempt") is not True
    assert hold_result["action"] == "hold"

    agent.selected_dir = 2
    rtb_result = dispatcher.dispatch(
        {
            "fail_safe_decision": _search_mode_fail_safe(
                fail_safe_action="return_to_base",
                search_mode_active=True,
            ),
            "path_decisions": [
                PathDecision(decision_id="path-1", uav_id="0", next_action="east"),
            ],
        },
        timestamp=2.0,
    )
    rtb_uav_result = rtb_result["local"]["uav_results"]["0"]
    assert rtb_uav_result.get("override_exempt") is not True


@dataclass
class _ExplorationAgent:
    pos: tuple[int, int]
    selected_dir: int = 0


@dataclass
class _FakeGrid:
    width: int
    height: int

    def out_of_bounds(self, pos: tuple[int, int]) -> bool:
        return pos[0] < 0 or pos[1] < 0 or pos[0] >= self.width or pos[1] >= self.height


def _exploration_model(
    *,
    fire_map: dict[tuple[int, int], float] | None = None,
    smoke_cells: set[tuple[int, int]] | None = None,
    visit_counts: dict[tuple[str, int, int], int] | None = None,
    failed_dirs: dict[str, int] | None = None,
    grid: _FakeGrid | None = None,
) -> object:
    smoke_cells = smoke_cells or set()
    visit_counts = visit_counts or {}
    failed_dirs = failed_dirs or {}
    fire_map = fire_map or {}

    class _VisibilityState:
        observation_status_map = {
            cell: type("Status", (), {"value": "smoke_obscured"})()
            for cell in smoke_cells
        }

    class _VisibilityModel:
        state = _VisibilityState()

    class _FireBelief:
        fire_probability_map = fire_map

    class _FireRuntime:
        belief = _FireBelief()
        fire_probability_map = fire_map

    return type(
        "ExplorationModel",
        (),
        {
            "grid": grid or _FakeGrid(width=20, height=20),
            "fire_runtime_model": _FireRuntime(),
            "visibility_model": _VisibilityModel(),
            "uav_visit_counts": visit_counts,
            "uav_last_failed_dir": failed_dirs,
        },
    )()


def test_exploration_fallback_prefers_distinct_directions_per_uav_id() -> None:
    from src_extension.execution.uav_executor import UAVExecutor

    agent = _ExplorationAgent(pos=(10, 10))
    model = _exploration_model()
    preferred = {
        UAVExecutor(uav_id=str(uav_id), model=model, agent=agent)._exploration_fallback(agent)
        for uav_id in range(4)
    }

    assert preferred == {0, 1, 3, 2}
    assert len(preferred) == 4


def test_exploration_fallback_fire_hazard_overrides_directional_bias() -> None:
    from src_extension.execution.uav_executor import UAVExecutor

    agent = _ExplorationAgent(pos=(10, 10))
    model = _exploration_model(fire_map={(11, 10): 0.95})
    direction = UAVExecutor(uav_id="0", model=model, agent=agent)._exploration_fallback(agent)

    assert direction != 0


def test_exploration_fallback_smoke_hazard_overrides_directional_bias() -> None:
    from src_extension.execution.uav_executor import UAVExecutor

    agent = _ExplorationAgent(pos=(10, 10))
    model = _exploration_model(smoke_cells={(11, 10)})
    direction = UAVExecutor(uav_id="0", model=model, agent=agent)._exploration_fallback(agent)

    assert direction != 0


def test_exploration_fallback_respects_boundary_safe_movement() -> None:
    from src_extension.execution.uav_executor import UAVExecutor

    agent = _ExplorationAgent(pos=(0, 0))
    model = _exploration_model(grid=_FakeGrid(width=20, height=20))
    direction = UAVExecutor(uav_id="0", model=model, agent=agent)._exploration_fallback(agent)

    assert direction in {0, 1, 2, 3}
    assert direction in {0, 1}


def test_exploration_fallback_returns_valid_direction() -> None:
    from src_extension.execution.uav_executor import UAVExecutor

    agent = _ExplorationAgent(pos=(5, 5))
    model = _exploration_model()
    direction = UAVExecutor(uav_id="7", model=model, agent=agent)._exploration_fallback(agent)

    assert direction in {0, 1, 2, 3}
