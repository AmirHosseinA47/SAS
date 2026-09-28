"""fix1 item 1: the silent exit at BATCH_SIZE (outputs/fix1_part1.txt section 1).

WildFireModel.step() used to call sys.exit(0) on its (BATCH_SIZE + 2)-th call, and
evaluate_scenarios' default --batch-size 300 was independent of --steps, so a 360-step
evaluation exited 0 with no results. These tests pin the three halves of the fix: the
model refuses the over-limit step with an exception, the runner's batch always covers
the run, and a failed seed can never look like a success.
"""

from __future__ import annotations

import contextlib
import io
import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
import evaluate_scenarios as es
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import BatchLimitReached, WildFireModel


@pytest.fixture(autouse=True)
def _restore_module_config():
    """apply_scenario_config (and evaluate_scenarios.main) mutate cfv and wf; put every
    upper-case name back, delete names that did not exist, and restore agents.random."""
    saved = {mod: {n: getattr(mod, n) for n in dir(mod) if n.isupper()} for mod in (cfv, wf)}
    saved_random = agents.random
    yield
    for mod, values in saved.items():
        for name in [n for n in dir(mod) if n.isupper() and n not in values]:
            delattr(mod, name)
        for name, value in values.items():
            setattr(mod, name, value)
    agents.random = saved_random


def _small_model(batch_size: int) -> WildFireModel:
    rng = random.Random(7)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(cfv, wf, NUM_AGENTS=2, NUM_VICTIMS=2, NUM_FIREFIGHTERS=2,
                          WIND_DIRECTION="east", BATCH_SIZE=batch_size, PROBABILITY_MAP=False)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    return model


def test_model_refuses_the_over_limit_step_with_an_exception_not_an_exit() -> None:
    model = _small_model(batch_size=2)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(3):  # BATCH_SIZE + 1 steps are allowed
            model.step()
    assert model.evaluation_timesteps_counter == 3
    assert model.running is False  # mesa's stop signal, set at the last allowed step
    with contextlib.redirect_stdout(io.StringIO()):
        with pytest.raises(BatchLimitReached) as info:
            model.step()
    assert not isinstance(info.value, SystemExit)
    assert "BATCH_SIZE=2" in str(info.value)
    assert model.evaluation_timesteps_counter == 3  # the refused step did not run


def test_running_stays_true_before_the_last_allowed_step() -> None:
    model = _small_model(batch_size=5)
    with contextlib.redirect_stdout(io.StringIO()):
        model.step()
        model.step()
    assert getattr(model, "running", True) is True


@pytest.mark.parametrize("batch,steps,expected", [
    (None, 360, 360), (None, 240, 300), (None, 300, 300), (None, 0, 300), (359, 360, 359), (3, 6, 3),
])
def test_effective_batch_size_covers_the_run(batch, steps, expected) -> None:
    assert es.effective_batch_size(batch, steps) == expected


def test_batch_size_error_only_when_the_batch_cannot_run_the_steps() -> None:
    assert es.batch_size_error(None, 10_000) is None
    assert es.batch_size_error(359, 360) is None  # the model runs batch + 1 steps
    assert es.batch_size_error(3, 4) is None
    msg = es.batch_size_error(3, 6)
    assert msg is not None and "--batch-size 3" in msg and "--steps 6" in msg


def test_evaluate_exits_two_before_running_an_impossible_batch(capsys) -> None:
    rc = es.main(["--scenario", "D", "--n", "2", "--steps", "6", "--batch-size", "3",
                  "--seeds", "101,202"])
    out = capsys.readouterr()
    assert rc == 2
    assert "cannot run --steps 6" in out.err
    assert "seed=" not in out.out


def test_check_steps_advanced_rejects_a_short_run() -> None:
    class _Stub:
        evaluation_timesteps_counter = 4

    es.check_steps_advanced(_Stub(), 4)
    with pytest.raises(RuntimeError, match="advanced 4 of the 5"):
        es.check_steps_advanced(_Stub(), 5)


def _row(seed: int) -> dict:
    row = {key: 0 for key in es.METRIC_KEYS}
    row.update(seed=seed, terminal_step=None, all_terminal=False, unreachable_causes="",
               rescue_rate=0.0)
    return row


def test_a_seed_that_exits_is_a_failed_seed_and_the_batch_exits_one(monkeypatch, capsys) -> None:
    def fake_run_seed(seed, params, steps, **_kw):
        if seed == 202:
            raise SystemExit(0)  # the old silent-exit shape
        return _row(seed)

    monkeypatch.setattr(es, "_run_seed", fake_run_seed)
    rc = es.main(["--scenario", "D", "--n", "2", "--steps", "5", "--seeds", "101,202"])
    out = capsys.readouterr()
    assert rc == 1
    assert "seed=202" in out.out and "ERROR: SystemExit" in out.out
    assert "ERROR: SystemExit" in out.err
    assert "FAILED: 1 of 2 seed(s) errored: 202" in out.out
    assert "seed=101" in out.out  # the successful seed is still reported


def test_every_seed_failing_exits_one(monkeypatch, capsys) -> None:
    def fake_run_seed(seed, params, steps, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(es, "_run_seed", fake_run_seed)
    rc = es.main(["--scenario", "D", "--n", "1", "--steps", "5", "--seeds", "101"])
    out = capsys.readouterr()
    assert rc == 1
    assert "No successful runs." in out.out
    assert "FAILED: 1 of 1" in out.err


def test_a_real_run_without_batch_size_advances_every_step(capsys) -> None:
    rc = es.main(["--scenario", "D", "--n", "1", "--steps", "2", "--seeds", "101", "--csv"])
    out = capsys.readouterr()
    assert rc == 0
    assert "seed=101" in out.out and "ERROR" not in out.out
    assert "steps_run" in out.out
