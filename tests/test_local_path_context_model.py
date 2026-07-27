"""LocalPathContextModel live runtime knowledge and integration tests."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import agents
import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

from src_extension.adaptation.local_adaptation_generator import (
    LocalAdaptationSpaceGenerator,
    _read_local_path_context,
)
from src_extension.analysis.local_uav_analyzer import LocalUAVAnalyzer
from src_extension.knowledge.local_observation_model import LocalObservationModel
from src_extension.knowledge.local_path_context_model import LocalPathContextModel
from src_extension.knowledge.uav_resource_model import UAVResourceRuntimeState
from src_extension.planning.local_uav_path_planner import LocalUAVPathPlanner
from wildfire_model import WildFireModel


def _resource_state(uav_id: str, **kwargs: object) -> UAVResourceRuntimeState:
    return UAVResourceRuntimeState(uav_id=uav_id, **kwargs)


def test_refresh_updates_required_fields() -> None:
    model = LocalPathContextModel(uav_id="u1")
    model.refresh_from_runtime(
        timestamp=1.0,
        position=(10.0, 12.0),
        selected_direction=2,
        current_action="west",
        current_target=(8.0, 12.0),
        last_positions=[(9.0, 12.0), (10.0, 12.0)],
        last_directions=[0, 2, 0, 2],
        stuck_count=2,
        target_switch_count=1,
        nearby_fire=0.6,
        nearby_smoke=0.3,
        congestion_pressure=0.2,
        boundary_pressure=0.1,
        drift_level=0.15,
        sector_alignment_score=0.85,
    )
    snap = model.snapshot()
    assert snap["current_target"] == (8.0, 12.0)
    assert snap["current_action"] == "west"
    assert snap["selected_direction"] == 2
    assert len(snap["last_positions"]) >= 2
    assert snap["stuck_count"] == 2
    assert snap["target_switch_count"] == 1
    assert snap["nearby_fire"] == pytest.approx(0.6)
    assert snap["nearby_smoke"] == pytest.approx(0.3)
    assert 0.0 <= snap["navigation_confidence"] <= 1.0
    assert 0.0 <= snap["path_safety_score"] <= 1.0
    assert snap["movement_stability"] is not None


def test_oscillation_score_increases_with_ping_pong() -> None:
    low = LocalPathContextModel.compute_oscillation_score(
        [(1.0, 1.0), (2.0, 1.0)],
        [0, 1],
    )
    high = LocalPathContextModel.compute_oscillation_score(
        [(1.0, 1.0), (2.0, 1.0), (1.0, 1.0), (2.0, 1.0)],
        [0, 2, 0, 2],
    )
    assert high > low


def test_stuck_count_propagates_to_snapshot() -> None:
    model = LocalPathContextModel(uav_id="u1")
    model.refresh_from_runtime(timestamp=1.0, stuck_count=4, position=(1.0, 1.0))
    assert model.snapshot()["stuck_count"] == 4


def test_hazard_proximity_updates_nearby_fire_and_smoke() -> None:
    model = LocalPathContextModel(uav_id="u1")
    model.refresh_from_runtime(
        timestamp=1.0,
        position=(5.0, 5.0),
        nearby_fire=0.8,
        nearby_smoke=0.55,
    )
    snap = model.snapshot()
    assert snap["nearby_fire"] == pytest.approx(0.8)
    assert snap["nearby_smoke"] == pytest.approx(0.55)
    assert snap["local_risk_estimate"] > 0.0


def test_target_switch_count_tracked_on_refresh() -> None:
    model = LocalPathContextModel(uav_id="u1")
    model.refresh_from_runtime(
        timestamp=1.0,
        position=(1.0, 1.0),
        current_target=(4.0, 4.0),
        target_switch_count=2,
    )
    assert model.snapshot()["target_switch_count"] == 2


def test_navigation_confidence_updates_from_runtime() -> None:
    model = LocalPathContextModel(uav_id="u1")
    model.refresh_from_runtime(
        timestamp=1.0,
        position=(1.0, 1.0),
        navigation_confidence=0.42,
        nearby_fire=0.1,
        nearby_smoke=0.1,
    )
    assert model.snapshot()["navigation_confidence"] == pytest.approx(0.42)


def test_analyzer_uses_path_context_for_stuck_and_oscillation() -> None:
    analyzer = LocalUAVAnalyzer()
    path_ctx = LocalPathContextModel(uav_id="u1")
    path_ctx.refresh_from_runtime(
        timestamp=1.0,
        position=(1.0, 1.0),
        last_positions=[(1.0, 1.0), (2.0, 1.0), (1.0, 1.0), (2.0, 1.0)],
        last_directions=[0, 2, 0, 2],
        stuck_count=4,
        nearby_fire=0.8,
        nearby_smoke=0.2,
        congestion_pressure=0.0,
        boundary_pressure=0.0,
        drift_level=0.0,
        navigation_confidence=0.3,
    )
    path_ctx.local_collision_risk_estimates = {"congestion": 0.0, "local_risk": 0.8}
    result = analyzer.analyze(
        "u1",
        LocalObservationModel(uav_id="u1"),
        path_ctx,
        _resource_state("u1", local_plan_reliability=0.9),
        {},
        1.0,
    )
    trigger_types = {t.trigger_type for t in result.local_trigger_list}
    assert "UAV_STUCK" in trigger_types
    assert "PATH_OSCILLATION" in trigger_types
    assert "LOW_NAVIGATION_CONFIDENCE" in trigger_types


def test_adaptation_reads_path_context_for_movement_options() -> None:
    path_ctx = LocalPathContextModel(uav_id="2500")
    path_ctx.refresh_from_runtime(
        timestamp=1.0,
        position=(1.0, 1.0),
        last_positions=[(1.0, 1.0), (2.0, 1.0), (1.0, 1.0), (2.0, 1.0)],
        last_directions=[0, 2, 0, 2],
        stuck_count=3,
    )
    gen = LocalAdaptationSpaceGenerator()
    options = gen._generate_movement_strategy_options(
        {"target_entity": "2500", "drift_state": "nominal"},
        {"local_path_context_model": path_ctx},
        {"uav_id": "2500"},
        1.0,
    )
    assert options
    params = options[0].parameters
    assert params.get("stuck_count") == 3
    assert params.get("oscillation_risk") is True
    assert _read_local_path_context({"local_path_context_model": path_ctx}, {}, "2500")


def test_planner_accesses_path_context_from_runtime_models() -> None:
    path_ctx = LocalPathContextModel(uav_id="2500")
    path_ctx.refresh_from_runtime(
        timestamp=1.0,
        position=(3.0, 4.0),
        navigation_confidence=0.77,
        nearby_fire=0.05,
        nearby_smoke=0.05,
    )
    planner = LocalUAVPathPlanner(uav_id="2500")
    hold_option = SimpleNamespace(
        option_id="local_stability_keep_current_path",
        option_type="stability_control",
        target_entity="2500",
        parameters={"keep_current_path": True},
        confidence=0.8,
        scope=SimpleNamespace(value="local"),
    )
    space = SimpleNamespace(options=(hold_option,))
    decision = planner.plan(
        1,
        local_adaptation_space=space,
        runtime_models={"local_path_context_models": {"2500": path_ctx}},
    )
    assert decision is not None
    ctx = decision.uncertainty_context or {}
    assert ctx.get("navigation_confidence") == pytest.approx(0.77)
    assert ctx.get("path_safety_score") is not None


def test_wildfire_model_refreshes_path_context_after_step() -> None:
    model = WildFireModel()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    uav_id = str(uav.unique_id)
    path_model = model.local_path_context_models[uav_id]
    before = path_model.snapshot()
    assert before.get("timestamp") is None

    with patch("wildfire_model.SYSTEM_RANDOM") as mock_random:
        mock_random.choice.return_value = 0
        model.step()

    after = path_model.snapshot()
    assert after.get("timestamp") is not None
    assert after.get("selected_direction") is not None
    assert isinstance(after.get("last_positions"), list)


def test_wildfire_model_target_switch_detection() -> None:
    model = WildFireModel()
    uav_id = sorted(model.local_path_context_models.keys())[0]
    path_model = model.local_path_context_models[uav_id]
    path_model.refresh_from_runtime(
        timestamp=1.0,
        position=(1.0, 1.0),
        current_target=(5.0, 5.0),
    )
    model._uav_last_targets[uav_id] = (5.0, 5.0)
    model.latest_planning_result = {
        "path_decisions": {
            uav_id: SimpleNamespace(
                uncertainty_context={"target_position": (9.0, 9.0)},
            )
        }
    }
    model._refresh_local_path_context_models(2.0)
    snap = path_model.snapshot()
    assert snap["current_target"] == (9.0, 9.0)
    assert snap["target_switch_count"] >= 1


def test_legacy_update_context_still_works() -> None:
    model = LocalPathContextModel(uav_id="legacy")
    model.update_context(
        timestamp=1.0,
        path_stability_score=0.7,
        task_support_score=0.6,
    )
    snap = model.snapshot()
    assert snap["path_stability_score"] == pytest.approx(0.7)
    assert snap["task_support_score"] == pytest.approx(0.6)
