"""Managed UAV battery state and monitoring."""

from __future__ import annotations

import agents
import wildfire_model
from src_extension.monitoring.monitoring_buffer import MonitoringBuffer


def test_local_monitor_reads_uav_battery_and_resource_model_receives_it() -> None:
    model = wildfire_model.WildFireModel()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    uav.battery_level = 75.0
    uav.battery_status = "normal"

    obs = uav.local_monitor.collect_observation(uav, 1.0)
    assert obs.battery_level == 75.0

    buf = MonitoringBuffer()
    buf.local_observations[str(uav.unique_id)] = obs
    model._apply_uav_resource_updates(buf, 1.0)
    st = model.uav_resource_model.by_uav_id[str(uav.unique_id)]
    assert st.battery_level == 75.0


def test_battery_drains_after_advance_without_changing_move_contract() -> None:
    model = wildfire_model.WildFireModel()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    model.evaluation_timesteps_counter = 1
    uav.battery_level = 100.0
    uav.battery_status = "normal"
    before = uav.battery_level
    uav.advance()
    assert uav.battery_level < before
    assert uav.battery_level >= 0.0
