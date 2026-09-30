"""Global planner round: GLOBAL_PLANNER_MODE and the global planner for UAV roles.

Design: outputs/planner_part1.txt (sections 2-6; the test list is 8.2; the maintainer's
rulings are section 11). With GLOBAL_PLANNER_MODE = 1 the global role family offers, per
available UAV, "switch this UAV to the other live role", valued on nine world quantities
(src_extension/adaptation/role_option_values.py) and ranked by the UNCHANGED scorer against
the UNCHANGED do-nothing baseline; the planner reader turns "role + named UAV" into a
MissionDecision; the GlobalExecutor writes the role and tells the model, which resets the
switched UAV's stale per-UAV state. With 0 (shipped) none of that runs.

Drives the real WildFireModel (built, never stepped) with its knowledge models laid out by
hand: the fire belief, the visibility status map, the victims' detection flags and the
per-UAV resource state. UAVs are moved to fixed, far-apart cells so no test depends on the
spawn layout. Every test passes GLOBAL_PLANNER_MODE explicitly; the shipped default is
pinned only in the switch section.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import dataclasses
import enum
import io
import math
import os
import random
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy
import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation import role_option_values as rov
from src_extension.adaptation.constraint_filter import ConstraintFilter
from src_extension.adaptation.global_adaptation_generator import GlobalAdaptationSpaceGenerator
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.execution.global_executor import GlobalExecutor
from src_extension.knowledge.visibility_model import ObservationStatus
from src_extension.planning import global_mission_planner as gmp
from src_extension.planning.decision_objects import MissionDecision
from src_extension.planning.utility_evaluation import UtilityEvaluation
from wildfire_model import WildFireModel

REPO = Path(__file__).resolve().parents[1]
MODE_IR = "information_recovery_mode"
BASELINE_ID = "global_stability_maintain_current_config"
FT = "fire_tracker"
VS = "victim_searcher"
# Far-apart working cells (pairwise >= 30 apart), away from both depots.
CELLS = {"2500": (10, 10), "2501": (10, 40), "2502": (40, 10), "2503": (40, 40)}

_CONFIG_NAMES = (
    "GLOBAL_PLANNER_MODE",
    "SYSTEM_RANDOM",
    "NUM_AGENTS",
    "NUM_VICTIMS",
    "NUM_FIREFIGHTERS",
    "WIND_DIRECTION",
    "BATCH_SIZE",
    "FIRE_SPREAD_MULTIPLIER",
    "PROBABILITY_MAP",
    "NUM_FIRE_TRACKERS",
    "NUM_VICTIM_SEARCHERS",
    "BASE_STATION_MODE",
    "SECURITY_DISTANCE",
)


@pytest.fixture(autouse=True)
def _restore_module_config():
    """apply_scenario_config mutates cfv and wf; put every touched name back (an absent
    name is deleted again), and agents.random. The teardown canary asserts the accessor
    reads what it read at setup, so a leaked switch fails HERE in any test order."""
    saved = {}
    for mod in (cfv, wf):
        saved[mod] = {name: (hasattr(mod, name), getattr(mod, name, None)) for name in _CONFIG_NAMES}
    saved_agents_random = agents.random
    setup_value = agents.global_planner_mode()
    yield
    for mod, values in saved.items():
        for name, (present, value) in values.items():
            if present:
                setattr(mod, name, value)
            elif hasattr(mod, name):
                delattr(mod, name)
    agents.random = saved_agents_random
    assert agents.global_planner_mode() == setup_value, "GLOBAL_PLANNER_MODE leaked out of the test"


# ---------------------------------------------------------------------------
# construction helpers
# ---------------------------------------------------------------------------

def _model(planner=1, ft=2, vs=2, seed: int = 101, **extra) -> WildFireModel:
    """A real, seeded, never-stepped model (4 UAVs, 4 victims, the harness's scenario keys)
    with GLOBAL_PLANNER_MODE passed explicitly and the UAVs on CELLS."""
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        NUM_AGENTS=4,
        NUM_VICTIMS=4,
        NUM_FIREFIGHTERS=2,
        WIND_DIRECTION="east",
        BATCH_SIZE=300,
        FIRE_SPREAD_MULTIPLIER=0.75,
        PROBABILITY_MAP=False,
        NUM_FIRE_TRACKERS=ft,
        NUM_VICTIM_SEARCHERS=vs,
        GLOBAL_PLANNER_MODE=planner,
        **extra,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    for uid, cell in CELLS.items():
        _place(model, uid, cell)
    _world(model)
    for state in model.uav_resource_model.by_uav_id.values():
        state.role_stability_timer = 30.0
    return model


def _uav(model, uid: str):
    return next(a for a in model.schedule.agents if type(a) is agents.UAV and str(a.unique_id) == uid)


def _place(model, uid: str, cell) -> None:
    agent = _uav(model, uid)
    model.grid.move_agent(agent, tuple(cell))
    model.uav_resource_model.by_uav_id[uid].current_position = (float(cell[0]), float(cell[1]))


def _all_cells(model):
    return list(model.visibility_model.state.observation_status_map.keys())


def _world(model, fresh=(), stale=(), never=(), undetected: int = 0) -> None:
    """Lay out the managing system's picture: every cell OBSERVED_NO_FIRE except the
    believed-burning cells (fresh -> OBSERVED_FIRE, stale -> STALE_INFORMATION) and the
    never-seen cells; the first `undetected` managed victims undetected, the rest detected."""
    status = model.visibility_model.state.observation_status_map
    for c in list(status):
        status[c] = ObservationStatus.OBSERVED_NO_FIRE
    for c in never:
        status[tuple(c)] = ObservationStatus.NEVER_SEEN
    for c in fresh:
        status[tuple(c)] = ObservationStatus.OBSERVED_FIRE
    for c in stale:
        status[tuple(c)] = ObservationStatus.STALE_INFORMATION
    model.fire_runtime_model.belief.estimated_burning_cells = {tuple(c) for c in list(fresh) + list(stale)}
    for i, vid in enumerate(sorted(model.managed_victims)):
        model.managed_victims[vid].confirmed = i >= undetected


def _rm(model) -> dict:
    """runtime_models exactly as WildFireModel._run_adaptation_space_generation builds them."""
    rm = {
        "fire_runtime_model": model.fire_runtime_model,
        "visibility_model": model.visibility_model,
        "victim_runtime_model": model.victim_runtime_model,
        "uav_resource_model": model.uav_resource_model,
        "communication_model": model.communication_model,
        "firefighter_model": model.firefighter_model,
        "mission_goal_model": model.mission_goal_model,
        "local_path_context_models": model.local_path_context_models,
        "available_entities": list(model.local_observation_models.keys()),
        "global_observation_snapshot": model.latest_global_snapshot,
        "simulation_model": model,
    }
    rm["mission_goals"] = model.mission_goal_model.runtime_context()
    return rm


def _ginput(triggers=()) -> dict:
    return {"target_entity": "mission", "all_triggers": list(triggers), "triggers": list(triggers)}


def _role_options(model, triggers=()):
    return GlobalAdaptationSpaceGenerator()._generate_role_assignment_options(_ginput(triggers), _rm(model), 1.0)


def _switch(model, uid: str, triggers=()):
    """The switch option that moves `uid`, or None."""
    for opt in _role_options(model, triggers):
        if opt.parameters.get("target_uav_id") == uid:
            return opt
    return None


def _targets(model, triggers=()):
    return {o.parameters["target_uav_id"] for o in _role_options(model, triggers) if "target_uav_id" in o.parameters}


def _baseline():
    return GlobalAdaptationSpaceGenerator()._generate_global_noop_option(1.0)


def _evaluate(option, mode=MODE_IR):
    return UtilityEvaluation().evaluate_option(option, None, None, mode)


def _term(evaluation, name):
    return next(t for t in evaluation.utility_terms if t.name == name)


def _select(model, mode=MODE_IR):
    options = tuple(_role_options(model)) + (_baseline(),)
    scored = UtilityEvaluation().score_options(options, mode=mode)
    selected = gmp._select_feasible_option(scored, options)
    return selected.option_id, {e.evaluation.option_id: e.score for e in scored}


class _One(enum.IntEnum):
    ONE = 1


class _Raises:
    def __int__(self):
        raise RuntimeError("no int")

    def __eq__(self, other):
        raise RuntimeError("no eq")

    __hash__ = object.__hash__


def _harness_parse_value():
    """_ffr_harness._parse_value, compiled from the file (importing the harness would run
    nothing, but this keeps the test free of its import-time sys.path edits)."""
    src = (REPO / "outputs" / "_ffr_harness.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_parse_value")
    ns: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "_ffr_harness._parse_value", "exec"), ns)
    return ns["_parse_value"]


# ---------------------------------------------------------------------------
# the switch: GLOBAL_PLANNER_MODE and its accessor (D-1: ON only on an exact 1)
# ---------------------------------------------------------------------------

def test_shipped_default_is_zero_and_off():
    assert cfv.GLOBAL_PLANNER_MODE == 0
    assert type(cfv.GLOBAL_PLANNER_MODE) is int
    assert agents.global_planner_mode() == 0


_ON = [1, 1.0, "1", True, " 1 ", "+1", "01", Decimal("1"), numpy.int64(1), numpy.float64(1.0), _One.ONE]
_OFF = [None, 0, 0.0, "0", " 0 ", False, Decimal("0"), "0.0", "1.0", "2.0", 0.5, "0.5", Decimal("0.5"),
        1.5, 2, -1, math.inf, -math.inf, math.nan, "on", "off", "true", "True", "yes", "", "1_0", _Raises()]


@pytest.mark.parametrize("raw", _ON, ids=[repr(v) for v in _ON])
def test_accessor_on_forms(raw):
    cfv.GLOBAL_PLANNER_MODE = raw
    value = agents.global_planner_mode()
    assert value == 1 and type(value) is int


@pytest.mark.parametrize("raw", _OFF, ids=[repr(v) for v in _OFF])
def test_accessor_off_forms(raw):
    cfv.GLOBAL_PLANNER_MODE = raw
    value = agents.global_planner_mode()
    assert value == 0 and type(value) is int


def test_accessor_missing_attribute_is_off():
    cfv.GLOBAL_PLANNER_MODE = 1
    del cfv.GLOBAL_PLANNER_MODE
    assert agents.global_planner_mode() == 0


_HARNESS_ON = ["1", "01", "+1", "1.0", "1e0", "true"]
_HARNESS_OFF = ["0", "0.0", "0.5", "2", "on", "none", "inf", "nan", "1_0"]


@pytest.mark.parametrize("text,want", [(t, 1) for t in _HARNESS_ON] + [(t, 0) for t in _HARNESS_OFF])
def test_accessor_through_the_harness_parser(text, want):
    parsed = _harness_parse_value()(text)
    apply_scenario_config(cfv, wf, GLOBAL_PLANNER_MODE=parsed)
    assert agents.global_planner_mode() == want


def test_accessor_reads_at_call_time_through_apply_scenario_config():
    apply_scenario_config(cfv, wf, GLOBAL_PLANNER_MODE=1)
    assert agents.global_planner_mode() == 1
    apply_scenario_config(cfv, wf, GLOBAL_PLANNER_MODE=0)
    assert agents.global_planner_mode() == 0


def test_the_string_one_point_zero_is_off_but_the_harness_float_is_on():
    cfv.GLOBAL_PLANNER_MODE = "1.0"
    assert agents.global_planner_mode() == 0
    cfv.GLOBAL_PLANNER_MODE = _harness_parse_value()("1.0")
    assert agents.global_planner_mode() == 1


# ---------------------------------------------------------------------------
# OFF identity: mode 0 generates today's role family, and nothing new runs
# ---------------------------------------------------------------------------

_LEGACY_ROLES = ("fire_tracking", "victim_search", "victim_confirmation", "victim_tracking", "communication_relay")
_BASE_NONE = {"current_role": None, "role_stability_timer": None, "role_switch_count": None,
              "battery_state": None, "resource_state": None}


def test_mode_zero_role_family_is_the_dfbfbe7_literal():
    model = _model(planner=0)
    opts = _role_options(model)
    got = [(o.option_id, o.option_type, o.target_entity, o.parameters, o.cost_estimate, o.risk_estimate,
            o.confidence) for o in opts]
    want = [("global_role_assignment_%s" % r, "role_assignment", "mission", {**_BASE_NONE, "assigned_role": r},
             1.0, 0.2, 0.5) for r in _LEGACY_ROLES]
    want.append(("global_role_assignment_maintain_current", "role_assignment", "mission",
                 {**_BASE_NONE, "action": "maintain_current_role"}, 0.0, 0.0, 0.5))
    assert got == want


def test_mode_zero_never_calls_the_mode_one_builder_or_the_value_functions(monkeypatch):
    calls = []
    monkeypatch.setattr(GlobalAdaptationSpaceGenerator, "_generate_role_switch_options",
                        lambda *a, **k: calls.append("builder") or [])
    monkeypatch.setattr(GlobalAdaptationSpaceGenerator, "_role_switch_specs",
                        lambda *a, **k: calls.append("specs") or [])
    for name in ("switch_option_values", "share", "battery_cost", "collision_risk", "drift_risk",
                 "switching_cost", "fire_demand", "stale_demand", "victim_demand", "uncertainty_demand",
                 "zero_values"):
        monkeypatch.setattr(rov, name, lambda *a, _n=name, **k: calls.append(_n))
    model = _model(planner=0)
    space = GlobalAdaptationSpaceGenerator().generate(_ginput(), _rm(model), 1.0)
    assert calls == []
    for opt in space.options:
        assert "target_uav_id" not in opt.parameters
        assert not (set(rov.NINE_VALUES) & set(opt.parameters))


def test_mode_zero_selected_string_role_option_still_gives_no_assignment():
    model = _model(planner=0)
    opt = _role_options(model)[0]
    assert gmp._uav_assignments_from_params(opt.parameters) == {}


# ---------------------------------------------------------------------------
# the reader fix (5.1)
# ---------------------------------------------------------------------------

def test_reader_string_with_target_names_the_uav():
    assert gmp._uav_assignments_from_params({"assigned_role": VS, "target_uav_id": "2500"}) == {"2500": VS}


def test_reader_string_without_target_stays_empty():
    assert gmp._uav_assignments_from_params({"assigned_role": VS}) == {}
    assert gmp._uav_assignments_from_params({"assigned_role": VS, "target_uav_id": ""}) == {}
    assert gmp._uav_assignments_from_params({"assigned_role": VS, "target_uav_id": None}) == {}


def test_reader_dict_forms_unchanged():
    assert gmp._uav_assignments_from_params({"uav_assignments": {"1": "a"}, "assigned_role": VS,
                                             "target_uav_id": "2"}) == {"1": "a"}
    assert gmp._uav_assignments_from_params({"role_assignments": {1: "b"}}) == {"1": "b"}
    assert gmp._uav_assignments_from_params({"assigned_role": {"3": "c"}, "target_uav_id": "9"}) == {"3": "c"}


# ---------------------------------------------------------------------------
# the mode-1 role family (2.2)
# ---------------------------------------------------------------------------

def test_mode_one_family_shape():
    model = _model()
    opts = _role_options(model)
    ids = [o.option_id for o in opts]
    assert ids == ["global_role_assignment_victim_searcher_2500", "global_role_assignment_victim_searcher_2501",
                   "global_role_assignment_fire_tracker_2502", "global_role_assignment_fire_tracker_2503",
                   "global_role_assignment_maintain_current"]
    for opt in opts[:4]:
        p = opt.parameters
        assert opt.option_type == "role_assignment" and opt.target_entity == p["target_uav_id"]
        assert isinstance(p["assigned_role"], str) and p["assigned_role"] == p["to_role"] != p["from_role"]
        assert opt.confidence == 1.0 and opt.cost_estimate == 1.0 and opt.risk_estimate == 0.2
        for k in rov.NINE_VALUES:
            assert type(p[k]) is float and math.isfinite(p[k])
        assert p["communication_contribution"] == 0.0
        for k in _BASE_NONE:
            assert p[k] is None
    maintain = opts[-1].parameters
    assert all(maintain[k] == 0.0 for k in rov.NINE_VALUES)


def test_mode_one_delay_change_carries_explicit_zeros():
    model = _model()
    trig = SimpleNamespace(trigger_type="OSCILLATION_RISK", affected_entities=("2500",),
                           explanation_context="OSCILLATION_RISK uav=2500: role_switch_count=3")
    opts = _role_options(model, triggers=[trig])
    delay = [o for o in opts if o.option_id == "global_role_assignment_delay_change"]
    assert len(delay) == 1
    assert all(delay[0].parameters[k] == 0.0 for k in rov.NINE_VALUES)
    # I5 removed 2500, which leaves 2501 the last available tracker (I2)
    assert _targets(model, [trig]) == {"2502", "2503"}


def test_constraint_filter_accepts_the_switch_options():
    model = _model()
    opts = _role_options(model)
    kept = ConstraintFilter().filter_options(list(opts), _rm(model), model.mission_goal_model)
    assert [o.option_id for o in kept] == [o.option_id for o in opts]


# ---------------------------------------------------------------------------
# invariants I1-I5
# ---------------------------------------------------------------------------

def test_i1_returning_or_docked_uav_gets_no_option():
    model = _model(ft=3, vs=1)
    _uav(model, "2500").rtb_active = True
    _uav(model, "2501").rtb_docked = True
    ids = _targets(model)
    assert "2500" not in ids and "2501" not in ids


def test_i1_margin_of_ten_moving_steps_above_the_trigger():
    model = _model(ft=3, vs=1)
    agent = _uav(model, "2500")
    trigger = agents.rtb_trigger_level_at(agent, CELLS["2500"])
    state = model.uav_resource_model.by_uav_id["2500"]
    state.battery_level = trigger + 3.0 + 1e-6
    assert _switch(model, "2500") is not None
    state.battery_level = trigger + 3.0
    assert _switch(model, "2500") is None


def test_i1_margin_does_not_apply_without_a_returning_base_station():
    model = _model(ft=3, vs=1, BASE_STATION_MODE=1)
    state = model.uav_resource_model.by_uav_id["2500"]
    state.battery_level = 16.0
    opt = _switch(model, "2500")
    assert opt is not None
    assert agents.rtb_trigger_level_at(_uav(model, "2500"), CELLS["2500"]) == 15.0


def test_i2_the_last_available_member_of_a_role_gets_no_option():
    model = _model(ft=3, vs=1)
    ids = _targets(model)
    assert ids == {"2500", "2501", "2502"}          # the single searcher 2503 cannot leave
    _uav(model, "2501").rtb_active = True
    _uav(model, "2502").rtb_active = True
    ids = _targets(model)
    assert ids == set()                             # 2500 is now the last AVAILABLE tracker


def test_i3_only_real_changes():
    model = _model()
    for opt in _role_options(model)[:-1]:
        assert opt.parameters["from_role"] != opt.parameters["to_role"]


def test_i4_ids_come_from_the_resource_model():
    model = _model()
    del model.uav_resource_model.by_uav_id["2501"]
    ids = [o.parameters.get("target_uav_id") for o in _role_options(model) if "target_uav_id" in o.parameters]
    assert "2501" not in ids and set(ids) <= set(model.uav_resource_model.by_uav_id)


@pytest.mark.parametrize("ttype", ["OSCILLATION_RISK", "INSTABILITY_DETECTED"])
def test_i5_a_uav_named_unstable_gets_no_option(ttype):
    model = _model(ft=3, vs=1)
    trig = SimpleNamespace(trigger_type=ttype, affected_entities=("2501",))
    ids = _targets(model, [trig])
    assert "2501" not in ids and "2500" in ids
    as_dict = {"trigger_type": ttype, "affected_entities": ["2500"]}
    ids = _targets(model, [as_dict])
    assert "2500" not in ids


def test_drift_none_is_zero_and_no_victims_gives_zero_victim_demand():
    model = _model()
    model.uav_resource_model.by_uav_id["2500"].drift_level = None
    assert _switch(model, "2500").parameters["drift_risk"] == 0.0
    model.managed_victims.clear()
    assert _switch(model, "2500").parameters["victim_contribution"] == 0.0
    assert rov.victim_demand(0, 0) == 0.0


def test_roles_are_read_managed_store_first_with_the_victim_search_alias():
    model = _model()
    model.managed_uav_states["2502"].role = "victim_search"
    opt = _switch(model, "2502")
    assert opt.parameters["from_role"] == VS and opt.parameters["to_role"] == FT


# ---------------------------------------------------------------------------
# one score test per value: only that value's input differs; the other eight are equal
# ---------------------------------------------------------------------------

_TERM = {
    "fire_contribution": "C_fire", "victim_contribution": "C_victim", "communication_contribution": "C_comm",
    "uncertainty_reduction": "G_uncertainty_reduction", "information_recovery": "G_information_recovery",
    "collision_risk": "R_collision", "battery_cost": "Cost_battery", "drift_risk": "R_drift",
    "switching_cost": "Cost_switch",
}
_COSTS = ("collision_risk", "battery_cost", "drift_risk", "switching_cost")


def _state_pair(value):
    """(uid, setup_a, setup_b): two states that differ only in `value`'s input."""
    far = [(x, y) for x in range(20, 35) for y in range(20, 45)]      # away from every UAV
    if value == "fire_contribution":             # 2502 VS->FT; a fresh cell under it keeps d = 0
        return "2502", lambda m: _world(m, fresh=[CELLS["2502"]]), \
            lambda m: _world(m, fresh=[CELLS["2502"]] + far[:100])
    if value == "victim_contribution":           # 2500 FT->VS
        return "2500", lambda m: _world(m, undetected=0), lambda m: _world(m, undetected=2)
    if value == "uncertainty_reduction":         # 2500 FT->VS; a never-seen cell under it keeps d = 0
        return "2500", lambda m: _world(m, never=[CELLS["2500"]]), \
            lambda m: _world(m, never=[CELLS["2500"]] + far[:200])
    if value == "information_recovery":          # 2502 VS->FT; no fresh cell: no target, d constant
        return "2502", lambda m: _world(m), lambda m: _world(m, stale=far[:60])

    def near(m):
        _place(m, "2502", (12, 12))
    if value == "collision_risk":                # 2500 FT->VS; searcher 2502 moves near it
        return "2500", lambda m: None, near

    def batt(level):
        def f(m):
            _world(m, never=[(10, 15)])
            m.uav_resource_model.by_uav_id["2500"].battery_level = level
        return f
    if value == "battery_cost":
        return "2500", batt(100.0), batt(70.0)

    def drift(level):
        def f(m):
            m.uav_resource_model.by_uav_id["2500"].drift_level = level
        return f
    if value == "drift_risk":
        return "2500", drift(None), drift(1.0)

    def timer(t):
        def f(m):
            m.uav_resource_model.by_uav_id["2500"].role_stability_timer = t
        return f
    if value == "switching_cost":
        return "2500", timer(30.0), timer(3.0)
    raise AssertionError(value)


_WITH_INPUT = [v for v in rov.NINE_VALUES if v != "communication_contribution"]


@pytest.mark.parametrize("value", _WITH_INPUT)
def test_score_moves_with_each_value(value):
    uid, set_a, set_b = _state_pair(value)
    model = _model()
    set_a(model)
    opt_a = _switch(model, uid)
    set_b(model)
    opt_b = _switch(model, uid)
    va, vb = opt_a.parameters, opt_b.parameters
    for other in rov.NINE_VALUES:
        if other != value:
            assert va[other] == vb[other], other
    assert va[value] != vb[value]
    ea, eb = _evaluate(opt_a), _evaluate(opt_b)
    ta, tb = _term(ea, _TERM[value]), _term(eb, _TERM[value])
    assert ta.value == pytest.approx(va[value]) and tb.value == pytest.approx(vb[value])
    assert ta.contribution != tb.contribution
    d_value = vb[value] - va[value]
    d_score = eb.total_utility - ea.total_utility
    sign = 1.0 if value not in _COSTS else -1.0
    assert d_score * d_value * sign > 0


def test_communication_is_present_zero_and_read_by_the_scorer():
    model = _model()
    for opt in _role_options(model)[:-1]:
        assert "communication_contribution" in opt.parameters
        assert opt.parameters["communication_contribution"] == 0.0
    opt = _switch(model, "2500")
    live = dataclasses.replace(opt, parameters={**opt.parameters, "communication_contribution": 0.5})
    e0, e1 = _evaluate(opt), _evaluate(live)
    assert _term(e1, "C_comm").contribution > _term(e0, "C_comm").contribution
    assert e1.total_utility > e0.total_utility


def test_switch_options_are_charged_the_switching_cost():
    model = _model()
    ev = _evaluate(_switch(model, "2500"))
    assert _term(ev, "Cost_switch").value == pytest.approx(rov.switching_cost(30.0))
    assert ev.predicted_effects.get("role_reassignment") is True


# ---------------------------------------------------------------------------
# one selection test per value with an input: that input alone flips the decision
# ---------------------------------------------------------------------------

def _victims_win(m):
    """2500 FT->VS wins on outstanding victims; 2501 is kept out of the race (timer 0)."""
    _world(m, undetected=4)
    m.uav_resource_model.by_uav_id["2501"].role_stability_timer = 0.0


def _sel_case(value):
    far = [(x, y) for x in range(20, 45) for y in range(15, 45)]
    if value == "fire_contribution":
        def base(m, n):
            _world(m, fresh=[CELLS["2502"]] + far[: n - 1])
            m.uav_resource_model.by_uav_id["2503"].role_stability_timer = 0.0
        return "2502", lambda m: base(m, 300), lambda m: base(m, 100)
    if value == "victim_contribution":
        def base(m, k):
            _victims_win(m)
            _world(m, undetected=k)
        return "2500", lambda m: base(m, 4), lambda m: base(m, 1)
    if value == "uncertainty_reduction":
        def base(m, n):
            cells = [CELLS["2500"]] + [c for c in _all_cells(m) if c != CELLS["2500"]]
            _world(m, never=cells[:n])
            m.uav_resource_model.by_uav_id["2501"].role_stability_timer = 0.0
        return "2500", lambda m: base(m, 2500), lambda m: base(m, 150)
    if value == "information_recovery":
        def base(m, n):
            _world(m, stale=far[:n])
            m.uav_resource_model.by_uav_id["2503"].role_stability_timer = 0.0
        return "2502", lambda m: base(m, 289), lambda m: base(m, 20)
    if value == "collision_risk":
        def near(m):
            _victims_win(m)
            _place(m, "2502", (12, 12))
        return "2500", _victims_win, near
    if value == "battery_cost":
        def batt(level):
            def f(m):
                _victims_win(m)
                _world(m, never=[(10, 15)], undetected=4)
                m.uav_resource_model.by_uav_id["2500"].battery_level = level
            return f
        return "2500", batt(100.0), batt(60.0)
    if value == "drift_risk":
        def drift(m):
            _victims_win(m)
            m.uav_resource_model.by_uav_id["2500"].drift_level = 1.0
        return "2500", _victims_win, drift
    if value == "switching_cost":
        def recent(m):
            _victims_win(m)
            m.uav_resource_model.by_uav_id["2500"].role_stability_timer = 0.0
        return "2500", _victims_win, recent
    raise AssertionError(value)


@pytest.mark.parametrize("value", _WITH_INPUT)
def test_each_value_alone_flips_the_selection(value):
    uid, set_win, set_lose = _sel_case(value)
    model = _model()
    set_win(model)
    sel, scores = _select(model)
    want = [o.option_id for o in _role_options(model) if o.parameters.get("target_uav_id") == uid][0]
    assert sel == want
    assert scores[want] - scores[BASELINE_ID] > 1e-6
    set_lose(model)
    sel, scores = _select(model)
    assert sel == BASELINE_ID
    assert scores[BASELINE_ID] - max(s for k, s in scores.items() if k != BASELINE_ID) > 1e-6


# ---------------------------------------------------------------------------
# the share rule: a switch and its immediate reversal are exact opposites
# ---------------------------------------------------------------------------

_SHARE = ("fire_contribution", "victim_contribution", "uncertainty_reduction", "information_recovery")


@pytest.mark.parametrize("ft,vs,uid", [(2, 2, "2500"), (2, 2, "2503"), (3, 1, "2501")])
def test_share_terms_are_antisymmetric(ft, vs, uid):
    model = _model(ft=ft, vs=vs)
    _world(model, fresh=[(30, 30), (31, 30)], stale=[(20, 20)], never=[(25, 25)], undetected=3)
    forward = _switch(model, uid)
    to_role = forward.parameters["to_role"]
    model.managed_uav_states[uid].role = to_role
    model.uav_resource_model.by_uav_id[uid].current_role = to_role
    reverse = _switch(model, uid)
    assert reverse.parameters["to_role"] == forward.parameters["from_role"]
    for k in _SHARE:
        assert forward.parameters[k] + reverse.parameters[k] == pytest.approx(0.0, abs=1e-12)
        assert abs(forward.parameters[k]) > 0


def test_share_rule_formula():
    holders = {FT: 2, VS: 2}
    assert rov.share(0.6, FT, FT, VS, holders) == pytest.approx(-0.3)
    assert rov.share(0.6, VS, FT, VS, holders) == pytest.approx(0.2)
    assert rov.share(0.6, FT, VS, FT, {FT: 1, VS: 3}) == pytest.approx(0.3)


def test_value_ranges():
    assert rov.switching_cost(0.0) == 1.0 and rov.switching_cost(30.0) == pytest.approx(0.15)
    assert rov.switching_cost(1e9) == pytest.approx(0.15)
    assert rov.battery_cost(10.0, 12.0, 20.0, 5, 0.3) == 1.0
    assert rov.battery_cost(100.0, 40.0, None, None, 0.3) == 0.0
    assert rov.battery_cost(100.0, 40.0, 45.0, 10, 0.3) == pytest.approx((3.0 + 5.0) / 60.0)
    assert rov.battery_cost(41.0, 40.0, 45.0, 100, 0.3) == 1.0
    assert rov.drift_risk(math.sqrt(2)) == 1.0 and rov.drift_risk(0.0) == 0.0
    assert rov.collision_risk(2, 4) == pytest.approx(2 / 3)
    assert rov.fire_demand(10_000) == 1.0 and rov.stale_demand(289) == 1.0
    assert rov.uncertainty_demand(1250, 2500) == 0.5


# ---------------------------------------------------------------------------
# the trigger-level helper (3.7)
# ---------------------------------------------------------------------------

def test_trigger_helper_equals_the_uav_trigger_at_its_own_cell(monkeypatch):
    """FREE_CELL_DOCKING = 0 (a5a496db): the berth trigger. fix3a A2 (shipped 1): the trigger measures to the
    nearest free footprint cell (UAV._apply_return_to_base_free_cell) and so does the helper."""
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 0, raising=False)
    model = _model()
    for uid in CELLS:
        agent = _uav(model, uid)
        for cell in [(0, 0), (4, 45), (25, 25), (49, 49), (45, 4), (12, 37)]:
            model.grid.move_agent(agent, cell)
            berth = agent._rtb_select_berth()
            agent.rtb_target_berth = None
            agent.rtb_target_depot = None
            assert agents.rtb_trigger_level_at(agent, cell) == agent._rtb_trigger_level(berth)


def test_trigger_helper_equals_the_free_cell_trigger_at_its_own_cell(monkeypatch):
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 1, raising=False)
    model = _model()
    for uid in CELLS:
        agent = _uav(model, uid)
        for cell in [(0, 0), (4, 45), (25, 25), (49, 49), (45, 4), (12, 37)]:
            model.grid.move_agent(agent, cell)
            depots = agent._free_cell_depots()
            free_cell, _depot = agent._nearest_free_dock_cell(depots, agent._other_uav_cells())
            assert agents.rtb_trigger_level_at(agent, cell) == agent._rtb_trigger_level(free_cell)


def test_trigger_helper_is_pure():
    model = _model()
    agent = _uav(model, "2500")
    before = copy.copy(agent.__dict__)
    agents.rtb_trigger_level_at(agent, (20, 20))
    assert agent.__dict__ == before


# ---------------------------------------------------------------------------
# hygiene: the model hook and the executor call (6.2 S3, 6.3)
# ---------------------------------------------------------------------------

def _seed_stores(model):
    for uid in CELLS:
        model._uav_sector_assignments[uid] = {"x_min": 1, "x_max": 2, "y_min": 3, "y_max": 4}
        model._wind_search_target_state[uid] = {"commit_target": (1, 1)}
        model._victim_sweep_state[uid] = {"cursor": 7}


def test_hook_resets_exactly_the_switched_uav():
    model = _model()
    _seed_stores(model)
    before = copy.deepcopy((model._uav_sector_assignments, model._wind_search_target_state,
                            model._victim_sweep_state))
    model.on_uav_role_changed("2501", FT, VS)
    assert model._uav_sector_assignments["2501"] == {"x_min": 0, "x_max": wf.HEIGHT - 1,
                                                     "y_min": 0, "y_max": wf.WIDTH - 1}
    assert "2501" not in model._wind_search_target_state and "2501" not in model._victim_sweep_state
    for i, store in enumerate((model._uav_sector_assignments, model._wind_search_target_state,
                               model._victim_sweep_state)):
        for uid in ("2500", "2502", "2503"):
            assert store[uid] == before[i][uid]


def test_hook_is_inert_at_mode_zero():
    model = _model(planner=0)
    _seed_stores(model)
    before = copy.deepcopy((model._uav_sector_assignments, model._wind_search_target_state,
                            model._victim_sweep_state))
    model.on_uav_role_changed("2501", FT, VS)
    assert (model._uav_sector_assignments, model._wind_search_target_state, model._victim_sweep_state) == before


def test_executor_calls_the_hook_only_on_a_real_change(monkeypatch):
    model = _model()
    calls = []
    monkeypatch.setattr(model, "on_uav_role_changed", lambda *a: calls.append(a))
    ex = GlobalExecutor(model=model)
    ex.execute(MissionDecision(decision_id="m-1", uav_assignments={"2500": VS}))
    assert calls == [("2500", FT, VS)]
    assert model.managed_uav_states["2500"].role == VS
    assert model.uav_resource_model.by_uav_id["2500"].current_role == VS
    ex.execute(MissionDecision(decision_id="m-2", uav_assignments={"2500": VS}))   # re-assertion
    ex.execute(MissionDecision(decision_id="m-3", uav_assignments={"2500": "Victim_Searcher"}))
    assert calls == [("2500", FT, VS)]


def test_executor_without_the_hook_runs_as_before():
    state = SimpleNamespace(role="scout")
    resource = SimpleNamespace(calls=[])
    resource.update_role = lambda uid, role, **k: resource.calls.append((uid, role))
    model = SimpleNamespace(uav_resource_model=resource, managed_uav_states={"7": state})
    out = GlobalExecutor(model=model).execute(MissionDecision(decision_id="m", uav_assignments={"7": "relay"}))
    assert out["assignments"] == {"7": "relay"} and state.role == "relay" and resource.calls == [("7", "relay")]


def test_hook_runs_after_fail_safe_and_before_local_paths(monkeypatch):
    model = _model()
    order = []
    monkeypatch.setattr(model, "on_uav_role_changed", lambda *a: order.append("hook"))
    disp = DecisionDispatcher(model=model)
    monkeypatch.setattr(disp, "_dispatch_fail_safe", lambda *a, **k: order.append("fail_safe") or {})
    monkeypatch.setattr(disp, "_dispatch_local_paths", lambda *a, **k: order.append("local") or {})
    monkeypatch.setattr(disp._rescue, "execute", lambda *a, **k: {})
    monkeypatch.setattr(disp, "_dispatch_communication", lambda *a, **k: {})
    disp.dispatch({"mission_decision": MissionDecision(decision_id="m", uav_assignments={"2500": VS})})
    assert order == ["fail_safe", "hook", "local"]


# ---------------------------------------------------------------------------
# purity: generating at mode 1 writes nothing
# ---------------------------------------------------------------------------

def _snapshot(model):
    uavs = sorted((a for a in model.schedule.agents if type(a) is agents.UAV), key=lambda a: a.unique_id)
    return copy.deepcopy((
        {k: v for k, v in model.__dict__.items()
         if k in ("_wind_search_target_state", "_uav_sector_assignments", "_victim_sweep_state",
                  "managed_uav_states", "managed_victims")},
        sorted(model.__dict__.keys()),
        dataclasses.asdict(model.uav_resource_model),
        sorted(model.fire_runtime_model.belief.estimated_burning_cells),
        dict(model.visibility_model.state.observation_status_map),
        [{k: v for k, v in a.__dict__.items()
          if k not in ("model", "random", "local_monitor", "latest_local_observation")} for a in uavs],
    ))


def test_generation_at_mode_one_is_pure():
    model = _model()
    _world(model, fresh=[(30, 30)], stale=[(20, 20)], never=[(25, 25)], undetected=2)
    before = _snapshot(model)
    rng_before = (cfv.SYSTEM_RANDOM.getstate(), agents.random.getstate(), random.getstate())
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        GlobalAdaptationSpaceGenerator().generate(_ginput(), _rm(model), 1.0)
    assert out.getvalue() == ""
    assert (cfv.SYSTEM_RANDOM.getstate(), agents.random.getstate(), random.getstate()) == rng_before
    assert _snapshot(model) == before


# ---------------------------------------------------------------------------
# integration: generate -> filter -> plan -> MissionDecision -> executor -> hook
# ---------------------------------------------------------------------------

def test_integration_a_winning_switch_reaches_the_uav():
    model = _model()
    _victims_win(model)
    rm = _rm(model)
    space = GlobalAdaptationSpaceGenerator().generate(_ginput(), rm, 1.0)
    kept = ConstraintFilter().filter_options(list(space.options), rm, model.mission_goal_model)
    snapshot = SimpleNamespace(global_space=SimpleNamespace(options=kept))
    decision = gmp.GlobalMissionPlanner().plan(5, adaptation_space_snapshot=snapshot, runtime_models=rm)
    assert decision.selected_option_id == "global_role_assignment_victim_searcher_2500"
    assert decision.uav_assignments == {"2500": VS}
    _seed_stores(model)
    GlobalExecutor(model=model).execute(decision)
    assert model._uav_assignment_role("2500") == VS
    assert _uav(model, "2500").current_role == VS
    assert "2500" not in model._victim_sweep_state
