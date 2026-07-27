"""managed-system boundary completeness."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

from wildfire_model import WildFireModel


def _uav_agents(model: WildFireModel) -> list[object]:
    return [agent for agent in model.schedule.agents if type(agent).__name__ == "UAV"]


def test_managed_system_boundary_state_initializes_and_updates() -> None:
    model = WildFireModel()

    assert hasattr(model, "environment_bridge")
    bridge_snapshot = model.environment_bridge.snapshot(0.0)
    assert isinstance(bridge_snapshot, dict)
    assert bridge_snapshot
    assert bridge_snapshot["source"] == "environment_bridge"

    assert hasattr(model, "managed_victims")
    assert len(model.managed_victims) >= 2
    # Runtime beliefs are populated by monitoring/detection, not at model init.
    assert len(model.victim_runtime_model.victims) == 0

    assert hasattr(model, "managed_firefighters")
    assert len(model.managed_firefighters) >= 2
    assert len(model.firefighter_model.units) >= 2

    assert hasattr(model, "managed_uav_states")
    assert len(model.managed_uav_states) == len(_uav_agents(model))

    model.step()

    for agent in _uav_agents(model):
        state = model.managed_uav_states[str(agent.unique_id)]
        assert state.position == (float(agent.pos[0]), float(agent.pos[1]))
        assert state.battery_level == float(getattr(agent, "battery_level", state.battery_level))
        assert state.battery_status == str(
            getattr(agent, "battery_status", state.battery_status) or state.battery_status
        )
