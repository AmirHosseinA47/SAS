"""fix2 item 2 follow-up: the stationary-yield fixes (outputs/fix2_part3_prereg.txt amendment 4).

STATIONARY_YIELD_FIX (shipped 1; off only on an exact integral 0; read only while UAV_HOLD_STATIONARY):
  1  a yield never escapes for the grid edge / an off-grid heading; a yield step records no drift
  2  a yielder on the cell its partner needs steps aside
  3  no yield when either UAV is on a return leg, docked, or in the depot approach area (radius 3)
YIELD_ONLY_WHEN_CONTENDING (offered rule 4; ships 0; on only on an exact integral 1).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.analysis.trigger_objects import SafetyTrigger, Scope, Severity
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.planning.decision_objects import FailSafeDecision, PathDecision
from wildfire_model import WildFireModel


@pytest.fixture(autouse=True)
def _restore_module_config():
    saved = {mod: {n: getattr(mod, n) for n in dir(mod) if n.isupper()} for mod in (cfv, wf)}
    saved_random = agents.random
    yield
    for mod, values in saved.items():
        for name in [n for n in dir(mod) if n.isupper() and n not in values]:
            delattr(mod, name)
        for name, value in values.items():
            setattr(mod, name, value)
    agents.random = saved_random


@pytest.fixture
def fix(monkeypatch):
    def set_(value):
        monkeypatch.setattr(cfv, "STATIONARY_YIELD_FIX", value, raising=False)
    return set_


def _uavs(model):
    return sorted((a for a in model.schedule.agents if type(a) is agents.UAV), key=lambda a: a.unique_id)


def _model(cells, depot=False):
    """3 UAVs (the pinned default fleet: other modules leave NUM_AGENTS changed) on `cells`;
    no base station unless `depot` (then the shipped NW / SE depots)."""
    cfv.NUM_AGENTS = wf.NUM_AGENTS = 3
    if not depot:
        cfv.BASE_STATION_MODE = 0
    model = WildFireModel()
    u = _uavs(model)
    for uav, cell in zip(u, cells):
        model.grid.move_agent(uav, cell)
        uav.rtb_docked = False
        uav.rtb_active = False
    return model, u


def _collision(uid):
    return SafetyTrigger(trigger_type="COLLISION_RISK", severity=Severity.MEDIUM, confidence=0.75,
                         scope=Scope.LOCAL, affected_entities=(str(uid),), timestamp=1.0,
                         recommended_planner="local_uav_path_planner", explanation_context="test")


def _named(model, *uavs):
    model.latest_analysis_snapshot = SimpleNamespace(all_triggers=tuple(_collision(a.unique_id) for a in uavs))


# --------------------------------------------------------------------------- the switches

def test_shipped() -> None:
    assert cfv.STATIONARY_YIELD_FIX == 1 and agents.stationary_yield_fix() is True
    assert cfv.YIELD_ONLY_WHEN_CONTENDING == 0 and agents.yield_only_when_contending() is False
    assert agents.DEPOT_APPROACH_RADIUS == agents.COLLISION_RISK_RADIUS + 1 == 3


@pytest.mark.parametrize("value, expected", [(0, False), ("0", False), (0.0, False), (1, True),
                                             (0.5, True), (None, True)])
def test_fix_off_only_on_an_exact_integral_zero(fix, value, expected) -> None:
    fix(value)
    assert agents.stationary_yield_fix() is expected


def test_fix_is_read_only_while_the_stay_is_on(monkeypatch, fix) -> None:
    fix(1)
    monkeypatch.setattr(cfv, "UAV_HOLD_STATIONARY", 0)
    assert agents.stationary_yield_fix() is False


@pytest.mark.parametrize("value, expected", [(1, True), ("1", True), (0, False), (0.5, False), (None, False),
                                             (2, False)])
def test_rule4_on_only_on_an_exact_integral_one(monkeypatch, value, expected) -> None:
    monkeypatch.setattr(cfv, "YIELD_ONLY_WHEN_CONTENDING", value, raising=False)
    assert agents.yield_only_when_contending() is expected


# --------------------------------------------------------------------------- rule 3: the depot

def test_the_depot_approach_area() -> None:
    model, _ = _model([(20, 20), (30, 30), (40, 40)], depot=True)
    cells = model.base_station["cells"]
    assert (4, 45) in cells and (5, 45) not in cells              # the NW depot: x 0-4, y 45-49
    assert agents.in_depot_approach_area(model, (7, 45))          # 3 from (4, 45)
    assert not agents.in_depot_approach_area(model, (8, 45))      # 4
    assert agents.in_depot_approach_area(model, (5, 43))          # 1 + 2 = 3 from (4, 45)
    assert not agents.in_depot_approach_area(model, (25, 25))
    nodepot, _ = _model([(20, 20), (30, 30), (40, 40)])
    assert not agents.in_depot_approach_area(nodepot, (1, 1))


@pytest.mark.parametrize("value, yields", [(1, False), (0, True)])
def test_a_partner_in_the_approach_area_holds_no_one(fix, value, yields) -> None:
    fix(value)
    model, u = _model([(7, 45), (9, 45), (40, 10)], depot=True)   # u0 inside (3 from (4,45)), u1 outside (5)
    _named(model, u[1])
    model.evaluation_timesteps_counter = 30
    d = DecisionDispatcher(model=model)
    assert d._must_yield(str(u[1].unique_id)) is yields


@pytest.mark.parametrize("value, yields", [(1, False), (0, True)])
def test_a_uav_in_the_approach_area_does_not_yield(fix, value, yields) -> None:
    fix(value)
    model, u = _model([(9, 45), (7, 45), (40, 10)], depot=True)   # the yielder u1 is the one inside
    _named(model, u[1])
    model.evaluation_timesteps_counter = 30
    d = DecisionDispatcher(model=model)
    assert d._must_yield(str(u[1].unique_id)) is yields


def test_away_from_a_depot_the_yield_and_its_partners_stand(fix) -> None:
    fix(1)
    model, u = _model([(20, 20), (21, 21), (40, 10)], depot=True)
    _named(model, u[1])
    model.evaluation_timesteps_counter = 30
    d = DecisionDispatcher(model=model)
    assert d._must_yield(str(u[1].unique_id)) is True
    assert d.yield_partners(str(u[1].unique_id)) == (str(u[0].unique_id),)


def test_the_dispatcher_hands_the_partners_to_the_executor(fix) -> None:
    fix(1)
    model, u = _model([(20, 20), (21, 21), (40, 10)])
    _named(model, u[0], u[1])
    model.evaluation_timesteps_counter = 30
    d = DecisionDispatcher(model=model)
    fs = FailSafeDecision(decision_id="fs", selected_option_id="safety-hold", fail_safe_action="safe_hold",
                          mission_mode="safety_first", uncertainty_context={"fail_safe_mode": "safety_first"})
    paths = [PathDecision(decision_id="p%d" % i, uav_id=str(a.unique_id), selected_option_id="explore_x",
                          next_action="east") for i, a in enumerate(u)]
    seen = {}
    for a in u:
        ex = d._get_uav_executor(str(a.unique_id))
        orig = ex.execute

        def spy(decision, timestamp=0.0, fail_safe_decision=None, _o=orig, _id=str(a.unique_id)):
            seen[_id] = dict(decision.uncertainty_context or {})
            return _o(decision, timestamp, fail_safe_decision=fail_safe_decision)

        ex.execute = spy
    d._dispatch_local_paths(paths, 30.0, fs, fail_safe_override_active=True, override_reason="safety_first_mode")
    assert seen[str(u[1].unique_id)].get("fix2_yield_partners") == [str(u[0].unique_id)]
    assert "fix2_yield_partners" not in seen[str(u[0].unique_id)]


# --------------------------------------------------------------------------- rule 1: no edge escape

def _yielder_executor(model, uav):
    return UAVExecutor(uav_id=str(uav.unique_id), model=model, agent=uav)


@pytest.mark.parametrize("value, action", [(1, "hold"), (0, "hold_escape")])
def test_a_yield_on_the_grid_edge_stays(fix, value, action) -> None:
    fix(value)
    model, u = _model([(2, 20), (40, 40), (0, 20)])        # the searcher (highest id) on the x = 0 edge
    ex = _yielder_executor(model, u[2])
    _, got = ex._execute_hold(u[2], 2, yield_partners=[str(u[0].unique_id)])   # heading off the grid
    assert got == action


def test_the_stuck_escape_is_kept_as_the_backstop(fix) -> None:
    fix(1)
    model, u = _model([(20, 20), (40, 40), (25, 25)])
    model._uav_stuck_counts = {str(u[2].unique_id): 3}
    ex = _yielder_executor(model, u[2])
    _, got = ex._execute_hold(u[2], 0, yield_partners=[str(u[0].unique_id)])
    assert got == "hold_escape"


def test_a_plain_yield_stays_and_is_marked(fix) -> None:
    fix(1)
    model, u = _model([(20, 20), (40, 40), (22, 20)])
    ex = _yielder_executor(model, u[2])
    got_dir, got = ex._execute_hold(u[2], 1, yield_partners=[str(u[0].unique_id)])
    assert (got_dir, got) == (1, "hold") and u[2].execution_yield is True


# --------------------------------------------------------------------------- rule 2: step aside

@pytest.mark.parametrize("signal", ["commit", "refused"])
def test_the_yielder_on_the_partners_needed_cell_steps_aside(fix, signal) -> None:
    fix(1)
    model, u = _model([(20, 20), (40, 40), (21, 20)])
    p = u[0]
    if signal == "commit":                                  # the partner's committed move of this step
        p.execution_direction_applied, p.execution_stay, p.selected_dir = True, False, 0
    else:                                                   # its last move was refused into (21, 20)
        p.execution_direction_applied = False
        p._monitor_prev_intended_delta, p._monitor_prev_actual_delta = (1, 0), (0, 0)
    ex = _yielder_executor(model, u[2])
    got_dir, got = ex._execute_hold(u[2], 2, yield_partners=[str(p.unique_id)])
    # neighbours of (21, 20): (22, 20) d0, (21, 19) d1, (20, 20) the partner, (21, 21) d3 - equal
    # distances from the needed cell and the partner; (21, 21) is farthest from the grid edge
    assert (got_dir, got) == (3, "yield_step_aside")


def test_no_step_aside_when_the_partner_does_not_need_the_cell(fix) -> None:
    fix(1)
    model, u = _model([(20, 20), (40, 40), (21, 20)])
    p = u[0]
    p.execution_direction_applied, p.execution_stay, p.selected_dir = True, False, 1   # to (20, 19)
    ex = _yielder_executor(model, u[2])
    _, got = ex._execute_hold(u[2], 2, yield_partners=[str(p.unique_id)])
    assert got == "hold"


def test_no_free_cell_means_stay(fix) -> None:
    fix(1)
    model, u = _model([(1, 0), (0, 1), (0, 0)])            # a corner, both neighbours taken
    p = u[0]
    p.execution_direction_applied, p.execution_stay, p.selected_dir = True, False, 2   # into (0, 0)
    ex = _yielder_executor(model, u[2])
    _, got = ex._execute_hold(u[2], 2, yield_partners=[str(p.unique_id)])
    assert got == "hold"


def test_the_step_aside_avoids_a_depot_cell(fix) -> None:
    fix(1)
    model, u = _model([(3, 44), (40, 10), (4, 44)], depot=True)    # yielder just outside the NW depot
    p = u[0]
    p.execution_direction_applied, p.execution_stay, p.selected_dir = True, False, 0   # (3,44) -> (4,44)
    ex = _yielder_executor(model, u[2])
    got_dir, got = ex._execute_hold(u[2], 2, yield_partners=[str(p.unique_id)])
    assert got == "yield_step_aside"
    dx, dy = agents._MOVE_DELTAS[got_dir]
    assert (4 + dx, 44 + dy) not in model.base_station["cells"]


def test_the_step_aside_is_exempt_from_the_post_filters(fix) -> None:
    fix(1)
    model, u = _model([(20, 20), (40, 40), (21, 20)])
    p = u[0]
    p.execution_direction_applied, p.execution_stay, p.selected_dir = True, False, 0
    ex = _yielder_executor(model, u[2])
    decision = PathDecision(decision_id="y", uav_id=str(u[2].unique_id), selected_option_id="", next_action="hold",
                            uncertainty_context={"fix2_yield_partners": [str(p.unique_id)]})
    fs = FailSafeDecision(decision_id="fs", selected_option_id="safety-hold", fail_safe_action="safe_hold",
                          mission_mode="safety_first", uncertainty_context={"fail_safe_mode": "safety_first"})
    result = ex.execute(decision, 30.0, fail_safe_decision=fs)
    assert result["action"] == "yield_step_aside" and result["selected_dir"] == 3
    assert u[2].execution_stay is False


def _burn(model, cell):
    fire = next(a for a in model.grid.get_cell_list_contents([cell]) if type(a).__name__ == "Fire")
    fire.burning = True
    return fire


def test_the_step_aside_is_not_overridden_by_the_searcher_gate(fix) -> None:
    # the maintainer's missing revert check: a searcher's step aside near fire. Without the exemption
    # the near-field searcher gate (a strict hazard within 6) replaces the step aside with its own
    # hazard retreat; with it, the step aside stands - it already excludes burning / smoke / off-grid /
    # occupied cells and the partners' cells.
    fix(1)
    model, u = _model([(20, 20), (40, 40), (21, 20)])
    y, p = u[2], u[0]
    assert str(y.current_role) == "victim_searcher"
    p.execution_direction_applied, p.execution_stay, p.selected_dir = True, False, 0   # (20,20) -> (21,20)
    _burn(model, (21, 24))                                  # 4 north of the yielder: inside the gate's near field
    ex = _yielder_executor(model, y)
    assert ex._min_strict_hazard_distance((21, 20), ex._collect_strict_active_fire_cells(model),
                                          ex._collect_strict_smoke_cells(model)) <= agents.SEARCHER_GATE_NEAR_RANGE
    decision = PathDecision(decision_id="y", uav_id=str(y.unique_id), selected_option_id="", next_action="hold",
                            uncertainty_context={"fix2_yield_partners": [str(p.unique_id)]})
    fs = FailSafeDecision(decision_id="fs", selected_option_id="safety-hold", fail_safe_action="safe_hold",
                          mission_mode="safety_first", uncertainty_context={"fail_safe_mode": "safety_first"})
    result = ex.execute(decision, 30.0, fail_safe_decision=fs)
    assert result["action"] == "yield_step_aside"
    assert result["selected_dir"] == 3                      # (21, 21): the step aside's own choice
    dx, dy = agents._MOVE_DELTAS[result["selected_dir"]]
    assert ex._strict_victim_hazard_level((21 + dx, 20 + dy)) == 0     # never onto fire or smoke


# --------------------------------------------------------------------------- rule 1: no drift on a yield

@pytest.mark.parametrize("value, drift", [(1, 0.0), (0, 1.0)])
def test_a_refused_move_on_a_yield_step_is_not_drift(monkeypatch, fix, value, drift) -> None:
    fix(value)
    monkeypatch.setattr(cfv, "FAILSAFE_REAL_ALARMS", 1, raising=False)
    model, u = _model([(21, 20), (40, 40), (20, 20)])
    y = u[2]
    y.selected_dir = 0                              # into (21, 20): occupied, refused
    y.execution_direction_applied = True
    y.execution_action = "yield_step_aside"
    y.execution_stay = False
    y.execution_yield = True
    y.advance()
    assert tuple(y.pos) == (20, 20)
    assert y._monitor_prev_drift_error == drift


# --------------------------------------------------------------------------- offered rule 4

@pytest.mark.parametrize("rule4, partner_dir, yields", [
    (0, 2, True),      # off: any partner within 2 holds the yielder
    (1, 2, False),     # on: the partner moves away (target 3 from the yielder) - no contention
    (1, 0, True),      # on: the partner moves toward it (target next to the yielder)
])
def test_rule4_yield_only_when_contending(monkeypatch, fix, rule4, partner_dir, yields) -> None:
    fix(1)
    monkeypatch.setattr(cfv, "YIELD_ONLY_WHEN_CONTENDING", rule4, raising=False)
    model, u = _model([(20, 20), (40, 40), (22, 20)])
    p = u[0]
    p.execution_direction_applied, p.execution_stay, p.selected_dir = True, False, partner_dir
    _named(model, u[2])
    model.evaluation_timesteps_counter = 30
    d = DecisionDispatcher(model=model)
    assert d._must_yield(str(u[2].unique_id)) is yields
