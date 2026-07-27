"""Scenario seed: detectable victims and one victim-search UAV role."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from wildfire_model import WildFireModel


def _victim_search_uav_id(model: WildFireModel) -> str:
    uavs = [a for a in model.schedule.agents if type(a) is agents.UAV]
    return str(uavs[model.NUM_AGENTS - 1].unique_id)


def test_managed_victims_seeded_with_higher_confidence_and_confirmation() -> None:
    model = WildFireModel()

    assert len(model.managed_victims) >= 1
    for victim in model.managed_victims.values():
        assert victim.confidence >= 0.65
        assert victim.needs_confirmation is True


def test_last_uav_seeded_as_victim_searcher() -> None:
    model = WildFireModel()
    victim_search_uav_id = _victim_search_uav_id(model)

    assert victim_search_uav_id in model.managed_uav_states
    assert model.managed_uav_states[victim_search_uav_id].role == "victim_searcher"
    assert (
        model.uav_resource_model.by_uav_id[victim_search_uav_id].current_role
        == "victim_searcher"
    )
