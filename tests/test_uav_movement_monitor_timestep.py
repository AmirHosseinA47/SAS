"""Intended vs actual movement in LocalObservation match the current advance() timestep."""

from __future__ import annotations

import math

import agents
import wildfire_model
from common_fixed_variables import euclidean_distance


def test_local_observation_movement_fields_match_current_advance_step() -> None:
    model = wildfire_model.WildFireModel()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    model.evaluation_timesteps_counter = 1

    # fix2 item 1: a COMMANDED move (the executor applied a direction). A step with no managed
    # direction is a deliberate stay and intends its own cell - the test below.
    uav.execution_direction_applied = True
    pos_before = (int(uav.pos[0]), int(uav.pos[1]))
    move_x = [1, 0, -1, 0]
    move_y = [0, -1, 0, 1]
    intended_delta = (move_x[uav.selected_dir], move_y[uav.selected_dir])

    uav.advance()
    pos_after = (int(uav.pos[0]), int(uav.pos[1]))
    obs = uav.latest_local_observation
    assert obs is not None

    expected_actual = (pos_after[0] - pos_before[0], pos_after[1] - pos_before[1])
    assert obs.intended_move == intended_delta
    assert obs.actual_move == expected_actual

    target_x = pos_before[0] + intended_delta[0]
    target_y = pos_before[1] + intended_delta[1]
    expected_drift = euclidean_distance(
        float(target_x), float(target_y), float(pos_after[0]), float(pos_after[1])
    )
    assert math.isclose(obs.drift_error, expected_drift, rel_tol=0.0, abs_tol=1e-9)

    assert obs.battery_level == float(uav.battery_level)


def test_a_step_with_no_managed_direction_intends_its_own_cell(monkeypatch) -> None:
    """fix2 item 1: with FAILSAFE_REAL_ALARMS on (shipped) a UAV that received no managed direction
    stays and is not drifting - the observation's intended_move and drift_error agree on (0, 0).
    Off: intended = selected_dir's delta, and the stay reads as drift 1."""
    import common_fixed_variables as cfv

    for value, expected_intended_is_zero in ((1, True), (0, False)):
        monkeypatch.setattr(cfv, "FAILSAFE_REAL_ALARMS", value)
        monkeypatch.setattr(cfv, "UAV_HOLD_STATIONARY", value)
        model = wildfire_model.WildFireModel()
        uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
        model.evaluation_timesteps_counter = 1
        pos_before = (int(uav.pos[0]), int(uav.pos[1]))
        uav.advance()                                  # no executor ran: no managed direction
        obs = uav.latest_local_observation
        assert (int(uav.pos[0]), int(uav.pos[1])) == pos_before
        assert uav.execution_action == "no_managed_direction_hold"
        if expected_intended_is_zero:
            assert obs.intended_move == (0, 0) and obs.drift_error == 0.0
        else:
            assert obs.intended_move != (0, 0) and obs.drift_error == 1.0
