"""LocalObservation → runtime knowledge (no UAV-local grid re-query)."""

from __future__ import annotations

import wildfire_model
from src_extension.knowledge.visibility_model import ObservationStatus
from src_extension.monitoring.monitoring_buffer import MonitoringBuffer
from src_extension.monitoring.monitoring_interfaces import LocalObservation


def test_local_observation_drives_fire_visibility_and_resource_knowledge() -> None:
    model = wildfire_model.WildFireModel()
    buf = MonitoringBuffer()
    obs = LocalObservation(
        uav_id="0",
        timestamp=10.0,
        visible_fire_cells=[(1, 1)],
        visible_smoke_cells=[(2, 2)],
        visible_victim_candidates=[],
        current_position=(5, 5),
        intended_move=(0, 0),
        actual_move=(0, 0),
        drift_error=2.5,
        battery_level=80.0,
        battery_status="nominal",
        communication_status="ok",
        nearby_uavs=[],
        task_context={"role": "scout", "assigned_task": "patrol"},
        negative_observations=[((3, 3), 0.9, 10.0)],
        raw_information_gain=1.0,
        normalized_information_gain=0.1,
        local_uncertainty_patch=[],
        observation_confidence=0.85,
        belief_confirmation_flags=[],
        source="local_monitor",
        confidence=0.85,
    )
    buf.local_observations["0"] = obs

    model._apply_fire_updates(buf, 10.0)
    model._apply_visibility_updates(buf, 10.0)
    model._apply_uav_resource_updates(buf, 10.0)

    fm = model.fire_runtime_model.belief
    assert fm.fire_probability_map.get((1, 1), 0.0) >= 0.45
    assert fm.negative_observation_map.get((3, 3)) is True

    vm = model.visibility_model.state
    assert (2, 2) in vm.smoke_obscured_cells
    assert vm.observation_status_map.get((3, 3)) == ObservationStatus.OBSERVED_NO_FIRE

    ur = model.uav_resource_model.by_uav_id["0"]
    assert ur.drift_level == 2.5
    assert ur.current_role == "scout"
    assert ur.assigned_task == "patrol"
