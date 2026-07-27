"""Initial UAV role seeding at WildFireModel startup."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from wildfire_model import WildFireModel


def _uav_ids_in_order(model: WildFireModel) -> list[str]:
    uavs = [a for a in model.schedule.agents if type(a) is agents.UAV]
    return [str(a.unique_id) for a in uavs]


def test_all_uavs_have_non_empty_roles_after_init() -> None:
    model = WildFireModel()
    uav_ids = _uav_ids_in_order(model)
    assert uav_ids

    for uav_id in uav_ids:
        managed = model.managed_uav_states.get(uav_id)
        assert managed is not None
        assert str(getattr(managed, "role", "") or "").strip()

        resource = model.uav_resource_model.by_uav_id.get(uav_id)
        assert resource is not None
        assert str(getattr(resource, "current_role", "") or "").strip()


def test_last_uav_is_victim_searcher() -> None:
    model = WildFireModel()
    uav_ids = _uav_ids_in_order(model)
    last_id = uav_ids[-1]

    assert model.managed_uav_states[last_id].role == "victim_searcher"
    assert model.uav_resource_model.by_uav_id[last_id].current_role == "victim_searcher"


def test_other_uavs_are_fire_tracker() -> None:
    model = WildFireModel()
    uav_ids = _uav_ids_in_order(model)

    for uav_id in uav_ids[:-1]:
        assert model.managed_uav_states[uav_id].role == "fire_tracker"
        assert model.uav_resource_model.by_uav_id[uav_id].current_role == "fire_tracker"


def test_roles_in_managed_and_resource_model() -> None:
    model = WildFireModel()
    uav_ids = _uav_ids_in_order(model)

    for uav_id in uav_ids:
        managed_role = model.managed_uav_states[uav_id].role
        resource_role = model.uav_resource_model.by_uav_id[uav_id].current_role
        assert managed_role == resource_role
        assert managed_role in ("fire_tracker", "victim_searcher")
