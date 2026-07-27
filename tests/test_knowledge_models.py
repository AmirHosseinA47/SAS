"""Minimal tests for runtime knowledge models."""

from __future__ import annotations

from src_extension.knowledge.communication_model import CommunicationModel
from src_extension.knowledge.fire_runtime_model import FireRuntimeModel
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
from src_extension.knowledge.uav_resource_model import UAVResourceModel
from src_extension.knowledge.victim_runtime_model import VictimRuntimeModel
from src_extension.knowledge.visibility_model import ObservationStatus, VisibilityModel


def test_fire_runtime_model_core_behaviors() -> None:
    model = FireRuntimeModel()
    model.initialize_grid(width=3, height=3, default_probability=0.1, default_confidence=0.2)

    cell = (1, 1)
    base_prob = model.belief.fire_probability_map[cell]
    base_conf = model.belief.fire_confidence_map[cell]

    model.update_fire_observation(
        cell=cell,
        timestamp=1.0,
        source="uav_1",
        confidence=0.9,
        probability=0.95,
    )
    assert model.belief.fire_probability_map[cell] > base_prob
    assert model.belief.fire_confidence_map[cell] > base_conf

    prob_after_fire = model.belief.fire_probability_map[cell]
    conf_after_fire = model.belief.fire_confidence_map[cell]

    model.update_no_fire_observation(cell=cell, timestamp=2.0, source="uav_2", confidence=1.0)
    assert model.belief.fire_probability_map[cell] < prob_after_fire
    assert model.belief.negative_observation_map[cell] is True
    assert model.belief.negative_observation_time[cell] == 2.0

    prob_after_no_fire = model.belief.fire_probability_map[cell]
    conf_before_smoke = model.belief.fire_confidence_map[cell]
    model.mark_smoke_obscured(cell=cell, timestamp=3.0, source="uav_3", confidence=0.4)
    assert model.belief.fire_probability_map[cell] == prob_after_no_fire
    assert model.belief.fire_confidence_map[cell] < conf_before_smoke

    conf_before_decay = model.belief.fire_confidence_map[cell]
    model.apply_decay(current_time=6.0, confidence_decay_rate=0.05)
    assert model.belief.fire_confidence_map[cell] < conf_before_decay

    high_cell = (2, 2)
    model.update_fire_observation(
        cell=high_cell,
        timestamp=7.0,
        source="uav_1",
        confidence=1.0,
        probability=1.0,
    )
    regions = model.get_last_known_fire_regions(threshold=0.5)
    assert high_cell in regions


def test_visibility_model_core_behaviors() -> None:
    model = VisibilityModel()
    model.initialize_grid(width=3, height=3)

    observed_cell = (0, 0)
    smoke_cell = (1, 1)
    stale_cell = (2, 2)

    model.update_visible_cell(
        cell=observed_cell,
        timestamp=5.0,
        status=ObservationStatus.OBSERVED_FIRE,
        confidence=0.9,
    )
    assert observed_cell in model.state.visible_cells
    assert model.state.observation_status_map[observed_cell] == ObservationStatus.OBSERVED_FIRE

    model.update_smoke_obscured_cell(cell=smoke_cell, timestamp=5.0, confidence=0.4)
    assert smoke_cell in model.state.smoke_obscured_cells
    assert model.state.observation_status_map[smoke_cell] == ObservationStatus.SMOKE_OBSCURED

    model.update_visible_cell(
        cell=stale_cell,
        timestamp=1.0,
        status=ObservationStatus.OBSERVED_NO_FIRE,
        confidence=0.6,
    )
    model.update_staleness(current_time=20.0)
    assert model.state.observation_status_map[stale_cell] == ObservationStatus.STALE_INFORMATION
    assert model.state.staleness_map[stale_cell] > 10.0

    uncertain = model.get_uncertain_regions(confidence_threshold=0.5, staleness_threshold=10.0)
    assert smoke_cell in uncertain
    assert stale_cell in uncertain
    # Never-seen cell should remain distinguishable and uncertain.
    assert (0, 2) in uncertain

    conf_before_decay = model.state.cell_confidence_map[observed_cell]
    model.apply_time_decay(current_time=25.0)
    assert model.state.cell_confidence_map[observed_cell] < conf_before_decay


def test_victim_runtime_model_updates() -> None:
    model = VictimRuntimeModel()
    model.update_detection(
        victim_id="v1",
        position=(10.0, 20.0),
        timestamp=2.0,
        source="uav_1",
        confidence=0.8,
    )
    rec = model.victims["v1"]
    assert rec.estimated_position == (10.0, 20.0)
    assert rec.confidence_score == 0.8
    assert rec.status in {"detected", "candidate"}

    model.confirm_victim(victim_id="v1", timestamp=3.0, source="manager")
    rec = model.victims["v1"]
    assert rec.status == "confirmed"
    assert rec.confirmation_required_flag is False
    assert rec.last_confirmation_time == 3.0
    assert rec.provenance.confidence is not None

    model.mark_lost_contact(victim_id="v1", timestamp=5.0)
    rec = model.victims["v1"]
    assert rec.lost_contact_flag is True
    assert rec.status == "lost_contact"


def test_victim_confidence_decay_and_uncertainty_growth() -> None:
    model = VictimRuntimeModel()
    model.update_detection(
        victim_id="v_decay",
        position=(5.0, 6.0),
        timestamp=2.0,
        source="uav_1",
        confidence=0.9,
    )
    rec_before = model.victims["v_decay"]
    conf_before = rec_before.confidence_score
    radius_before = rec_before.position_uncertainty_radius
    model.apply_time_decay(current_time=12.0)
    rec_after = model.victims["v_decay"]
    assert rec_after.confidence_score is not None and conf_before is not None
    assert rec_after.confidence_score < conf_before
    assert rec_after.position_uncertainty_radius is not None and radius_before is not None
    assert rec_after.position_uncertainty_radius > radius_before


def test_uav_resource_model_role_and_battery() -> None:
    model = UAVResourceModel()
    model.update_role(uav_id="u1", new_role="search", timestamp=1.0)
    assert model.by_uav_id["u1"].role_switch_count == 0

    model.update_role(uav_id="u1", new_role="search", timestamp=2.0)
    assert model.by_uav_id["u1"].role_switch_count == 0

    model.update_role(uav_id="u1", new_role="relay", timestamp=3.0)
    assert model.by_uav_id["u1"].role_switch_count == 1
    assert model.by_uav_id["u1"].role_stability_timer == 0.0

    model.update_battery(uav_id="u1", battery_level=15.0, timestamp=4.0)
    assert model.by_uav_id["u1"].battery_level == 15.0
    assert model.by_uav_id["u1"].battery_status == "critical"


def test_communication_model_failure_and_relay_flag() -> None:
    model = CommunicationModel()
    model.update_message_result(
        message_id="m1",
        delivery_status="failed",
        timestamp=10.0,
        critical=True,
    )
    assert any(item.get("message_id") == "m1" for item in model.state.failed_messages)
    assert model.state.relay_needed_flag is True

    model.mark_relay_needed(True)
    assert model.state.relay_needed_flag is True


def test_shared_operational_picture_rebuild_and_dashboard_summary() -> None:
    sop = SharedOperationalPicture()
    sop.rebuild_from_models(
        step_index=7,
        fire_snapshot={
            "estimated_burning_cells": [[1, 1]],
            "fire_probability_map": {"1,1": 0.9},
            "fire_confidence_map": {"1,1": 0.8},
            "last_observed_fire_time": {"1,1": 12.0},
        },
        visibility_snapshot={
            "visible_cells": [[1, 1]],
            "smoke_obscured_cells": [],
            "observation_status_map": {"1,1": "observed_fire"},
            "unknown_or_uncertain_regions": [[2, 2]],
            "information_freshness_map": {"1,1": 0.9},
            "staleness_map": {"1,1": 1.0},
        },
        victim_snapshot={"victims": {"v1": {"confidence_score": 0.7}}},
        uav_snapshot={"by_uav_id": {"u1": {"battery_level": 80.0}}},
        firefighter_snapshot={"units": {"f1": {"availability_status": "available"}}},
        communication_snapshot={
            "state": {
                "delivery_confidence": 0.8,
                "shared_knowledge_sync_quality": 0.75,
                "relay_needed_flag": False,
            }
        },
        active_alerts=[{"level": "warning", "message": "smoke"}],
        mission_mode="rescue",
        active_adaptation_state="monitoring",
        source="global_manager",
        timestamp=15.0,
    )
    summary = sop.get_dashboard_summary()
    assert summary["what_is_believed"]["fire"]["value"]["fire_probability_map"]["1,1"] == 0.9
    assert summary["how_certain_it_is"]["global_confidence"] == 0.75
    assert summary["how_fresh_it_is"]["global_timestamp"] == 15.0
    assert summary["mission_mode"] == "rescue"


def test_fire_negative_observation_decay() -> None:
    model = FireRuntimeModel()
    model.initialize_grid(width=2, height=2, default_probability=0.8, default_confidence=0.9)
    cell = (0, 0)
    model.update_no_fire_observation(
        cell=cell,
        timestamp=1.0,
        source="uav_1",
        confidence=1.0,
    )
    assert cell in model.belief.negative_observation_map
    model.decay_negative_observations(current_time=50.0, decay_rate=0.05)
    assert model.belief.negative_observation_map.get(cell, False) is False


def test_fire_get_best_search_target_non_visible() -> None:
    fire_model = FireRuntimeModel()
    fire_model.initialize_grid(width=3, height=3, default_probability=0.0, default_confidence=0.1)
    target = (2, 1)
    fire_model.update_fire_observation(
        cell=target,
        timestamp=3.0,
        source="uav_2",
        confidence=0.8,
        probability=0.95,
    )
    best = fire_model.get_best_search_target(current_time=4.0, min_conf=0.3)
    assert best == target
