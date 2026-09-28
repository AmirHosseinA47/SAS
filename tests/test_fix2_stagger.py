"""fix2 item 4: staggered launch batteries (outputs/fix2_part1.txt section 4, ruling D-9).

STAGGERED_LAUNCH_BATTERY (shipped 1; off only on an exact integral 0):
  L_i = 100 - delta * r_i,  delta = 0.3 * 220 / n,  r_i = the UAV's return rank - the s searchers at
  floor(k * n / s), the trackers on the remaining ranks in unique-id order. Scenario B multiplies:
  launch = 0.5 x L_i (fix1's composition).
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

T, S = "fire_tracker", "victim_searcher"


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


def test_shipped_on() -> None:
    assert cfv.STAGGERED_LAUNCH_BATTERY == 1 and agents.staggered_launch_battery() is True
    assert agents.UAV_STAGGER_CYCLE_STEPS == 220


def test_flight_drain_matches_the_uav() -> None:
    model = WildFireModel()
    uav = next(a for a in model.schedule.agents if type(a) is agents.UAV)
    assert agents.FLIGHT_DRAIN_PER_STEP == pytest.approx(uav.battery_drain_per_step + uav.battery_drain_per_move)


@pytest.mark.parametrize("value, expected", [(0, False), ("0", False), (0.0, False), (1, True),
                                             (0.5, True), (None, True)])
def test_off_only_on_an_exact_integral_zero(monkeypatch, value, expected) -> None:
    monkeypatch.setattr(cfv, "STAGGERED_LAUNCH_BATTERY", value, raising=False)
    assert agents.staggered_launch_battery() is expected


@pytest.mark.parametrize("roles, expected", [
    ([T, T, S], [78.0, 56.0, 100.0]),                     # A / B: one searcher at full charge
    ([T, T, S, S], [83.5, 50.5, 100.0, 67.0]),            # D: searchers half a cycle apart
    ([T, T, T, S, S], [86.8, 60.4, 47.2, 100.0, 73.6]),   # C
    ([S], [100.0]),                                        # one UAV: nothing to stagger
    ([T, T], [100.0, 67.0]),                               # no searcher: trackers ranks 0, 1
])
def test_the_rule(roles, expected) -> None:
    assert agents.staggered_launch_bases(roles) == pytest.approx(expected)


def test_off_is_full_charge(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "STAGGERED_LAUNCH_BATTERY", 0)
    assert agents.staggered_launch_bases([T, T, S, S]) == [100.0] * 4


def test_every_launch_is_above_the_berth_trigger() -> None:
    for n in range(2, 9):
        roles = [T] * (n - max(1, n // 2)) + [S] * max(1, n // 2)
        assert min(agents.staggered_launch_bases(roles)) > 39.23


def _launch(**params):
    apply_scenario_config(cfv, wf, **params)
    model = WildFireModel()
    uavs = sorted((a for a in model.schedule.agents if type(a) is agents.UAV), key=lambda a: a.unique_id)
    return [round(u.battery_level, 6) for u in uavs]


def test_model_scenario_d_launches_staggered() -> None:
    assert _launch(NUM_AGENTS=4) == pytest.approx([83.5, 50.5, 100.0, 67.0])


def test_model_scenario_b_composes_with_the_fraction() -> None:
    assert _launch(NUM_AGENTS=3, UAV_LAUNCH_BATTERY_FRACTION=0.5) == pytest.approx([39.0, 28.0, 50.0])


def test_model_off_is_c08456b(monkeypatch) -> None:
    monkeypatch.setattr(cfv, "STAGGERED_LAUNCH_BATTERY", 0)
    assert _launch(NUM_AGENTS=4) == [100.0] * 4
    assert _launch(NUM_AGENTS=3, UAV_LAUNCH_BATTERY_FRACTION=0.5) == [50.0] * 3
