"""fix1 item 3: one role-split rule for every scenario.

searchers = max(1, floor(n / 2)), trackers = the rest. The model's default (no split
given), the harness's --roles half and the dashboard presets all use
agents.half_rule_role_split. ROLE_SPLIT_HALF_RULE ships 1; only an exact integral zero
restores the legacy default (n-1 trackers + the last UAV searching).
"""

from __future__ import annotations

import contextlib
import io
import math
import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import evaluate_scenarios as es
import wildfire_model as wf
from serve_dashboard import BUILTIN_SCENARIOS, scenarios_payload
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

_MISSING = object()


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


@pytest.mark.parametrize("n,split", [(0, (0, 0)), (1, (0, 1)), (2, (1, 1)), (3, (2, 1)), (4, (2, 2)),
                                     (5, (3, 2)), (6, (3, 3)), (7, (4, 3)), (8, (4, 4))])
def test_the_rule(n, split) -> None:
    assert agents.half_rule_role_split(n) == split


@pytest.mark.parametrize("raw", [0, 0.0, "0", False])
def test_switch_off_only_on_exact_zero(monkeypatch, raw) -> None:
    monkeypatch.setattr(cfv, "ROLE_SPLIT_HALF_RULE", raw)
    assert agents.role_split_half_rule() is False
    assert agents.default_role_split(5) == (4, 1)  # legacy n-1 + 1
    assert agents.default_role_split(1) == (0, 1)


@pytest.mark.parametrize("raw", [1, True, "1", 2, 0.5, "off", None, math.nan, _MISSING])
def test_anything_else_keeps_the_rule(monkeypatch, raw) -> None:
    if raw is _MISSING:
        monkeypatch.delattr(cfv, "ROLE_SPLIT_HALF_RULE", raising=False)
    else:
        monkeypatch.setattr(cfv, "ROLE_SPLIT_HALF_RULE", raw)
    assert agents.role_split_half_rule() is True
    assert agents.default_role_split(5) == (3, 2)


def _model(n, **params) -> WildFireModel:
    rng = random.Random(11)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=n, NUM_VICTIMS=2, NUM_FIREFIGHTERS=2,
                          WIND_DIRECTION="east", BATCH_SIZE=300, PROBABILITY_MAP=False,
                          NUM_FIRE_TRACKERS=params.pop("ft", None),
                          NUM_VICTIM_SEARCHERS=params.pop("vs", None), **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    return model


def _roles(model):
    uavs = sorted((a for a in model.schedule.agents if type(a) is agents.UAV), key=lambda a: int(a.unique_id))
    return [model._uav_assignment_role(str(a.unique_id)) for a in uavs]


@pytest.mark.parametrize("n,expected", [
    (3, ["fire_tracker", "fire_tracker", "victim_searcher"]),
    (4, ["fire_tracker", "fire_tracker", "victim_searcher", "victim_searcher"]),
    (5, ["fire_tracker"] * 3 + ["victim_searcher"] * 2),
])
def test_the_model_default_is_the_rule(n, expected) -> None:
    assert _roles(_model(n)) == expected


@pytest.mark.parametrize("n,expected", [
    (4, ["fire_tracker"] * 3 + ["victim_searcher"]),
    (5, ["fire_tracker"] * 4 + ["victim_searcher"]),
])
def test_switch_zero_restores_the_legacy_default(n, expected) -> None:
    assert _roles(_model(n, ROLE_SPLIT_HALF_RULE=0)) == expected


def test_explicit_counts_still_win() -> None:
    assert _roles(_model(4, ft=3, vs=1)) == ["fire_tracker"] * 3 + ["victim_searcher"]


def test_a_three_uav_team_is_identical_under_both_settings() -> None:
    """A and B (3 UAVs): the rule IS the legacy split, index for index."""
    assert _roles(_model(3)) == _roles(_model(3, ROLE_SPLIT_HALF_RULE=0))


def test_dashboard_presets_carry_the_rule() -> None:
    payload = scenarios_payload()
    got = {k: (v["NUM_FIRE_TRACKERS"], v["NUM_VICTIM_SEARCHERS"]) for k, v in payload.items()}
    # fix3a B1: B is a 4-UAV team (2 trackers + 2 searchers by the rule); 3 UAVs at SCENARIO_B_TEAM 0.
    assert got == {"A": (2, 1), "B": (2, 2), "C": (3, 2), "D": (2, 2)}
    assert "NUM_FIRE_TRACKERS" not in BUILTIN_SCENARIOS["C"]  # the source dict is not mutated


def test_dashboard_presets_follow_the_switch(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "ROLE_SPLIT_HALF_RULE", 0)
    got = {k: (v["NUM_FIRE_TRACKERS"], v["NUM_VICTIM_SEARCHERS"]) for k, v in scenarios_payload().items()}
    # fix3a B1: B's 4-UAV team takes the legacy n-1 / 1 split with the rule off.
    assert got == {"A": (2, 1), "B": (3, 1), "C": (4, 1), "D": (3, 1)}


def test_evaluate_header_states_the_split(monkeypatch, capsys) -> None:
    def fake_run_seed(seed, params, steps, **_kw):
        raise RuntimeError("not run")

    monkeypatch.setattr(es, "_run_seed", fake_run_seed)
    es.main(["--scenario", "C", "--n", "1", "--steps", "5", "--seeds", "1"])
    assert "5 UAV (3T+2S)" in capsys.readouterr().out
    es.main(["--scenario", "D", "--n", "1", "--steps", "5", "--seeds", "1"])
    assert "4 UAV (2T+2S)" in capsys.readouterr().out
