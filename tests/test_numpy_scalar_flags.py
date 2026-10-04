"""isTrue round F-2 (outputs/isTrue_part1.txt 5.2; rulings in its section 10): NUMPY_SCALAR_FLAGS (ships 1).

utility_evaluation.plain_scalar hands the four planners' _is_truthy, planner_selection's maintain test, the ptruth /
ptruth_s / ptruth_p flag readers and safe_float (and through it _indicator / sig) a numpy bool / integer / floating
scalar as its Python twin. Every non-numpy value - and numpy.timedelta64 - passes unchanged, and no reader raises where
it did not. At NUMPY_SCALAR_FLAGS 0 the readers are the pre-fix readers exactly (the kill-switch tests pin it). The fix
tests FAIL on f686e932 (verified red in Part 2); every test sets its own configuration through monkeypatch.
"""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest

import agents
import common_fixed_variables as cfv
from src_extension.planning import fail_safe_planner, global_mission_planner, local_uav_path_planner
from src_extension.planning import planner_selection, rescue_planner
from src_extension.planning import utility_evaluation as ue

_JUNK = ("off", "", None, 0.5, -0.5, "0.5", "2.0", float("inf"), float("nan"), Decimal("0.5"), Fraction(1, 2),
         [], object())
_EXACT_ZEROS = (0, 0.0, "0", " 0 ", False, Decimal("0"), np.int64(0))
_ONES = (1, 1.0, "1", True, -1, 2, np.int64(1))

TRUE_TWINS = (np.True_, np.int64(1), np.int32(-3), np.uint8(2), np.float32(1.0), np.float64(0.5))
FALSE_TWINS = (np.False_, np.int64(0), np.float32(0.0), np.float64(0.0))
PLANNERS = (fail_safe_planner, global_mission_planner, local_uav_path_planner, rescue_planner)


def _off(monkeypatch):
    monkeypatch.setattr(cfv, "NUMPY_SCALAR_FLAGS", 0, raising=False)


# ============================================================================ the switch
def test_numpy_scalar_flags_ships_on():
    src = open(cfv.__file__, encoding="utf-8").read()
    assert "\nNUMPY_SCALAR_FLAGS = 1\n" in src
    assert agents.numpy_scalar_flags() is True


def test_numpy_scalar_flags_turns_off_only_on_an_exact_zero(monkeypatch):
    fn = getattr(agents, "numpy_scalar_flags")
    for raw in _EXACT_ZEROS:
        monkeypatch.setattr(cfv, "NUMPY_SCALAR_FLAGS", raw, raising=False)
        assert fn() is False, raw
    for raw in _ONES + _JUNK:
        monkeypatch.setattr(cfv, "NUMPY_SCALAR_FLAGS", raw, raising=False)
        assert fn() is True, raw
    monkeypatch.delattr(cfv, "NUMPY_SCALAR_FLAGS", raising=False)
    assert fn() is True, "missing"


# ============================================================================ plain_scalar
def test_f2_a_plain_scalar_returns_the_python_twin():
    assert ue.plain_scalar(np.True_) is True and ue.plain_scalar(np.False_) is False
    assert type(ue.plain_scalar(np.int64(3))) is int and ue.plain_scalar(np.int64(3)) == 3
    big = np.uint64(2 ** 64 - 1)
    assert type(ue.plain_scalar(big)) is int and ue.plain_scalar(big) == 2 ** 64 - 1
    assert type(ue.plain_scalar(np.float32(0.5))) is float and ue.plain_scalar(np.float32(0.5)) == 0.5
    assert type(ue.plain_scalar(np.float16(0.25))) is float and ue.plain_scalar(np.float16(0.25)) == 0.25
    assert type(ue.plain_scalar(np.longdouble(1.5))) is float and ue.plain_scalar(np.longdouble(1.5)) == 1.5
    assert type(ue.plain_scalar(np.float64(0.25))) is float and ue.plain_scalar(np.float64(0.25)) == 0.25


def test_f2_a2_every_other_value_is_returned_unchanged():
    for v in (True, False, 0, 1, 0.5, "yes", None, {}, [], (1,), Decimal("1"), Fraction(1, 2),
              np.datetime64("2020-01-01"), np.str_("on"), np.timedelta64(5, "s"), np.timedelta64("NaT"),
              np.timedelta64(5, "ns"),         # int() of a ns timedelta succeeds: only the exclusion keeps it
              np.complex128(1 + 2j), np.array(True)):
        assert ue.plain_scalar(v) is v, repr(v)


def test_f2_a3_timedelta64_never_raises_in_the_readers():
    # numpy.timedelta64 is a numpy.integer subclass whose int() can raise: it stays unchanged, readers as before
    for v in (np.timedelta64(5, "s"), np.timedelta64("NaT"), np.timedelta64(5, "ns")):
        assert ue.safe_float(v, -9.0) == -9.0
        for mod in PLANNERS:
            assert mod._is_truthy(v) is False


def test_f2_b_plain_scalar_is_inert_at_zero(monkeypatch):
    _off(monkeypatch)
    for v in TRUE_TWINS + FALSE_TWINS:
        assert ue.plain_scalar(v) is v


# ============================================================================ the readers
@pytest.mark.parametrize("mod", PLANNERS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_f2_c_planner_is_truthy_reads_numpy_scalars(monkeypatch, mod):
    # FAILS on f686e932: np.True_ / numpy integers / np.float32 fell through every branch to False
    for v in TRUE_TWINS:
        assert mod._is_truthy(v) is True, v
    for v in FALSE_TWINS:
        assert mod._is_truthy(v) is False, v
    _off(monkeypatch)
    for v in (np.True_, np.int64(1), np.float32(1.0)):
        assert mod._is_truthy(v) is False, v           # the pre-fix reading
    assert mod._is_truthy(np.float64(0.5)) is True     # a float subclass was always read correctly


def _maint(v):
    return SimpleNamespace(option_type="x", parameters={"do_nothing": v})


def test_f2_d_planner_selection_maintain_test(monkeypatch):
    # FAILS on f686e932
    assert planner_selection._is_maintain_option(_maint(np.True_)) is True
    assert planner_selection._is_maintain_option(_maint(np.int64(1))) is True
    assert planner_selection._is_maintain_option(_maint(np.False_)) is False
    assert planner_selection.find_maintain_option([_maint(np.False_), _maint(np.True_)]).parameters["do_nothing"]
    _off(monkeypatch)
    assert planner_selection._is_maintain_option(_maint(np.True_)) is False


def test_f2_e_safe_float(monkeypatch):
    # FAILS on f686e932: every numpy scalar but numpy.float64 returned the default
    assert ue.safe_float(np.True_, -9.0) == 1.0 and ue.safe_float(np.False_, -9.0) == 0.0
    assert ue.safe_float(np.int64(3), -9.0) == 3.0 and ue.safe_float(np.float32(0.5), -9.0) == 0.5
    assert ue.safe_float(np.float64(0.25), -9.0) == 0.25
    for v, want in ((None, -9.0), (True, 1.0), (2, 2.0), (0.5, 0.5), (" 1.5 ", 1.5), ("yes", -9.0), ({}, -9.0)):
        assert ue.safe_float(v, -9.0) == want, v
    assert planner_selection.safe_float is ue.safe_float and rescue_planner.safe_float is ue.safe_float
    _off(monkeypatch)
    for v in (np.True_, np.int64(3), np.float32(0.5)):
        assert ue.safe_float(v, -9.0) == -9.0, v       # the pre-fix reading
    assert ue.safe_float(np.float64(0.25), -9.0) == 0.25


def _opt(option_type, scope, **params):
    return SimpleNamespace(option_id="o", option_type=option_type, scope=scope, target_entity="uav_0",
                           parameters=params, confidence=0.9, expected_effect="", cost_estimate=0.1,
                           risk_estimate=0.1, explanation_hint="")


def _numbers(ev):
    """Every numeric / decision field of an OptionEvaluation (the explanation text is excluded)."""
    return (ev.feasible, ev.constraint_violations, ev.total_utility, ev.confidence_score, ev.stability_cost,
            ev.information_recovery_score,
            tuple((t.name, t.value, t.weight, t.contribution) for t in ev.utility_terms))


# One flag per evaluator, read by that evaluator's own ptruth closure and changing a term (option types hold no
# marker word, so only the parameter decides). Each row: (option_type, scope, flag).
EVALUATORS = (
    ("global_mission_option", "global", "role_change"),       # ptruth in _evaluate_global_mission_option (+ _indicator)
    ("rescue_option", "rescue", "dispatch"),                  # ptruth in _evaluate_rescue_option
    ("communication_option", "communication", "relay_mode"),  # ptruth in _evaluate_communication_option
    ("fail_safe_option", "system", "return_to_base"),         # ptruth in _evaluate_failsafe_option (x energy risk)
    ("path_option", "local", "keep_current_path"),            # ptruth_s in _compute_stability_bonus
)


@pytest.mark.parametrize("ot,scope,flag", EVALUATORS, ids=[e[2] for e in EVALUATORS])
def test_f2_f_the_numpy_twin_evaluates_identically(monkeypatch, ot, scope, flag):
    # FAILS on f686e932 for every row: the numpy flag read False, so a term (or the hysteresis bonus) changed
    U = ue.UtilityEvaluation()
    base = {"battery_level": 80.0, "victim_priority": 0.6, "mission_value": 0.5, "delivery_quality": 0.5,
            "energy_failure_risk": 0.5}                    # the fail-safe RTB flag scales with this risk
    py = U.evaluate_option(_opt(ot, scope, **base, **{flag: True}))
    npy = U.evaluate_option(_opt(ot, scope, **base, **{flag: np.True_}))
    off = U.evaluate_option(_opt(ot, scope, **base))
    assert _numbers(npy) == _numbers(py)
    assert _numbers(py) != _numbers(off)               # the flag matters in this evaluator
    _off(monkeypatch)
    assert _numbers(U.evaluate_option(_opt(ot, scope, **base, **{flag: np.True_}))) == _numbers(off)


def test_f2_g_confidence_adjustment_flag_ptruth_p(monkeypatch):
    # FAILS on f686e932: the numpy risky_action flag read False, so the uncertainty damp was skipped
    U = ue.UtilityEvaluation()
    profile = ue.get_weight_profile("normal_monitoring_mode")

    def adj(v):
        o = _opt("x_option", "global", uncertainty_level=0.5, risky_action=v)
        return U._apply_confidence_and_uncertainty_adjustment(1.0, o, (), None, profile)[0]

    assert adj(np.True_) == adj(True) != adj(False)
    _off(monkeypatch)
    assert adj(np.True_) == adj(False)


def test_f2_h_indicator_and_sig_through_safe_float(monkeypatch):
    # FAILS on f686e932: _indicator / sig sent the numpy bool to safe_float, which returned the default 0.0
    U = ue.UtilityEvaluation()
    for key, fn in (("role_change", U._compute_switching_cost),
                    ("negative_observation_recent", lambda o: U._compute_negative_information_adjustment(o)[0])):
        assert fn(_opt("x", "global", **{key: np.True_})) == fn(_opt("x", "global", **{key: True})), key
        assert fn(_opt("x", "global", **{key: np.True_})) != fn(_opt("x", "global", **{key: False})), key
    _off(monkeypatch)
    assert U._compute_switching_cost(_opt("x", "global", role_change=np.True_)) == \
        U._compute_switching_cost(_opt("x", "global", role_change=False))


def test_f2_i_the_dead_readers_are_untouched():
    """Ruling I-4: the shape-D literal flag readers stay as they are (a cleanup round lists them)."""
    src = open(ue.__file__, encoding="utf-8").read()
    for line in ('params.get("hard_collision_violation") is True', 'params.get("route_feasible") is False',
                 'params.get("requires_critical_communication") is True', 'params.get("fail_safe_mode") is not True'):
        assert line in src, line
