""" LocalObservationModel sync + SharedOperationalPicture rebuild."""

from __future__ import annotations

import wildfire_model
from src_extension.monitoring.monitoring_buffer import MonitoringBuffer
from src_extension.monitoring.monitoring_interfaces import LocalObservation


def test_local_observation_model_updated_and_sop_rebuilt_from_pipeline() -> None:
    model = wildfire_model.WildFireModel()
    uav_id = next(iter(model.local_observation_models))
    buf = MonitoringBuffer()
    obs = LocalObservation(
        uav_id=uav_id,
        timestamp=10.0,
        visible_fire_cells=[(4, 4)],
        visible_smoke_cells=[(5, 5)],
        visible_victim_candidates=[],
        current_position=(10, 10),
        intended_move=(0, 0),
        actual_move=(0, 0),
        drift_error=0.5,
        battery_level=70.0,
        battery_status="low",
        communication_status="ok",
        nearby_uavs=["1"],
        task_context={"role": "alpha", "assigned_task": "scan"},
        negative_observations=[((6, 6), 0.8, 10.0)],
        raw_information_gain=0.0,
        normalized_information_gain=0.0,
        local_uncertainty_patch=[(7, 7)],
        observation_confidence=0.88,
        belief_confirmation_flags=[],
        source="local_monitor",
        confidence=0.88,
    )
    buf.local_observations[uav_id] = obs

    model._apply_monitoring_to_knowledge(buf, 10.0)
    model.knowledge_manager.update_all_models(10.0)
    model._rebuild_shared_operational_picture(10.0, None)

    lo = model.local_observation_models[uav_id]
    assert lo.timestamp == 10.0
    assert (4, 4) in lo.visible_fire_cells
    assert (5, 5) in lo.visible_smoke_cells
    assert lo.local_battery_state == "low"
    assert lo.local_drift_state == "moderate"  # 0.25 < drift <= 0.75
    assert "1" in lo.nearby_uavs
    assert lo.current_task_context.get("role") == "alpha"
    assert (6, 6) in lo.negative_local_observations

    sop_snap = model.shared_operational_picture.snapshot()
    assert sop_snap["layers"]
    assert sop_snap["step_index"] == 10
    assert sop_snap["fire_belief_summary"]
    assert sop_snap["visibility_summary"]
