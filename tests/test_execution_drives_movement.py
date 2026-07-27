"""Execution directions drive pre-schedule UAV movement intent."""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from wildfire_model import WildFireModel


def _first_uav(model: WildFireModel) -> agents.UAV:
    return next(a for a in model.schedule.agents if type(a) is agents.UAV)


def _apply_pre_schedule_direction_handling(model: WildFireModel) -> None:
    if model._has_pending_execution_directions():
        model._sync_new_direction_from_uav_selected_dirs()
    else:
        import wildfire_model as wf

        model.new_direction = [
            wf.SYSTEM_RANDOM.choice(range(0, wf.N_ACTIONS))
            for _ in range(0, model.NUM_AGENTS)
        ]
        model.set_drone_dirs()


def test_pending_execution_preserves_selected_dir_and_syncs_new_direction() -> None:
    model = WildFireModel()
    uav = _first_uav(model)
    uav.selected_dir = 0
    uav_id = str(uav.unique_id)

    model.latest_execution_result = {
        "local": {
            "applied": True,
            "uav_results": {
                uav_id: {"applied": True, "selected_dir": 0, "action": "east"},
            },
        },
    }
    model.new_direction = [3, 3]

    assert model._has_pending_execution_directions()
    _apply_pre_schedule_direction_handling(model)

    assert uav.selected_dir == 0
    uav_list = [a for a in model.schedule.agents if type(a) is agents.UAV]
    uav_slot = uav_list.index(uav)
    assert model.new_direction[uav_slot] == 0


def test_no_pending_execution_uses_random_baseline_and_set_drone_dirs() -> None:
    model = WildFireModel()
    uav = _first_uav(model)
    model.latest_execution_result = None

    assert not model._has_pending_execution_directions()

    with patch("wildfire_model.SYSTEM_RANDOM") as mock_random:
        mock_random.choice.return_value = 2
        _apply_pre_schedule_direction_handling(model)

    uav_count = len([a for a in model.schedule.agents if type(a) is agents.UAV])
    assert model.new_direction == [2] * uav_count
    assert uav.selected_dir == 2
