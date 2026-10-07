"""Shared helpers for the MVG round's tests (outputs/urgency_part1d.txt 1d.8 (4); tests/test_movement_fixes.py and
tests/test_stranding_guard.py).

Not a test module (no test_ prefix). A port of the urgency round's tests/urgency_test_support.py (branch urgency,
5dba5bcb) without its U1 and fix (c) material: the round's switches are FF_APPROACH_PATH, FF_RETREAT_KEEP_APPROACH
and FF_FIX_STRANDING_GUARD; restore_config is the urgency round's FULL-configuration restore, unchanged. Each helper
drives the REAL WildFireModel: fire is set on its Fire agents (burning as a numpy bool, the way the simulator stores
it after its first tick), units and victims are parked on chosen cells, and the code under test (Firefighter.advance,
the choice and verdict methods) is called directly - no model.step is needed.

Base-safe: nothing here reads a name this round adds, so the helpers also run against the urgency round's code (the
golden digests of test_stranding_guard.py T-G3 are recorded that way).
"""

from __future__ import annotations

import importlib.util
import os
import random
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np

import agents
import common_fixed_variables as cfv
from wildfire_model import PhysicalRescueCommand, WildFireModel

V0, V1, V2, V3, V4 = "victim_0", "victim_1", "victim_2", "victim_3", "victim_4"
FF_A, FF_B, FF_C = "ff_unit_0", "ff_unit_1", "ff_unit_2"
SWITCH_NAMES = ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_FIX_STRANDING_GUARD")


def _load_pristine_config() -> dict[str, object]:
    """The import-time value of every UPPERCASE name of common_fixed_variables.py, read from a FRESH copy of the file -
    not from the shared module, which other test files change (apply_scenario_config, plain assignment) and leave
    changed. The file imports only random and numpy, so executing a copy has no side effect."""
    spec = importlib.util.spec_from_file_location("_mvg_pristine_cfv", Path(cfv.__file__))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {name: value for name, value in vars(module).items() if name.isupper()}


PRISTINE_CONFIG = _load_pristine_config()


def restore_config(monkeypatch) -> None:
    """Every UPPERCASE configuration name back to its import-time value on cfv and on the two modules that copy it with
    `from common_fixed_variables import *` (wildfire_model, agents; neither defines a name of its own that cfv has),
    and every UPPERCASE name another test ADDED to cfv removed - all through monkeypatch, so undone after the test.

    The full suite runs dozens of files that leave scenario settings behind (wind, base-station, planner and exit-leg
    modes, batch size, ...); the team pins of pinned_model do not cover them, and a real-model trajectory depends on
    them. Called by the autouse fixture of both round test files, BEFORE the test sets its own switches."""
    import wildfire_model as wf

    for name, value in PRISTINE_CONFIG.items():
        for module in (cfv, wf, agents):
            if name in vars(module) and vars(module)[name] is not value:
                monkeypatch.setattr(module, name, value)
    for name in [n for n in vars(cfv) if n.isupper() and n not in PRISTINE_CONFIG]:
        monkeypatch.delattr(cfv, name)


def switches(monkeypatch, approach: object = 0, retreat: object = 0, guard: object = 1, **params: object) -> None:
    """Set the MVG round's switches on the cfv MODULE (read at call time by the agents accessors): the two fixes and
    the stranding guard (all three shipped 1 since the flip; the fixes default to 0 here, so a test that does not name
    them pins today's movement)."""
    monkeypatch.setattr(cfv, "FF_APPROACH_PATH", approach, raising=False)
    monkeypatch.setattr(cfv, "FF_RETREAT_KEEP_APPROACH", retreat, raising=False)
    monkeypatch.setattr(cfv, "FF_FIX_STRANDING_GUARD", guard, raising=False)
    for name, value in params.items():
        monkeypatch.setattr(cfv, name, value, raising=False)


def pinned_model(monkeypatch, seed: int = 9613) -> WildFireModel:
    """Scenario A's team (3 UAV / 5 victims / 3 firefighters) pinned on cfv AND wf, with seeded randomness -
    other tests leave apply_scenario_config values set (memory: real-model tests pin the team)."""
    import wildfire_model as wf

    rng = random.Random(seed)
    for mod in (cfv, wf):
        monkeypatch.setattr(mod, "SYSTEM_RANDOM", rng, raising=False)
        for name, value in (("NUM_AGENTS", 3), ("NUM_VICTIMS", 5), ("NUM_FIREFIGHTERS", 3)):
            monkeypatch.setattr(mod, name, value, raising=False)
    monkeypatch.setattr(agents, "random", rng, raising=False)
    monkeypatch.setattr(cfv, "VICTIM_SPAWN_MODE", 0, raising=False)
    model = WildFireModel()
    model.debug_log = False
    return model


# ------------------------------------------------------------------------------------------- fire

def fire_agents(model: WildFireModel) -> list:
    return [a for a in model.schedule.agents if type(a) is agents.Fire]


def fire_at(model: WildFireModel, cell: tuple[int, int]):
    for agent in model.grid.get_cell_list_contents([cell]):
        if type(agent) is agents.Fire:
            return agent
    raise AssertionError(f"no Fire agent at {cell}")


def quiet_fire(model: WildFireModel) -> None:
    for fire in fire_agents(model):
        fire.burning = False
        fire.smoke.smoke = False


def burn(model: WildFireModel, cells, *, numpy_bool: bool = True) -> None:
    """Set cells burning - by default as numpy.bool_(True), the simulator's own type after its first tick."""
    for cell in cells:
        fire_at(model, cell).burning = np.bool_(True) if numpy_bool else True


def unburn(model: WildFireModel, cells) -> None:
    for cell in cells:
        fire_at(model, cell).burning = False


def smoke(model: WildFireModel, cells) -> None:
    for cell in cells:
        fire_at(model, cell).smoke.smoke = True


# ------------------------------------------------------------------------------- units and victims

def ff(model: WildFireModel, ff_id: str):
    return model.firefighter_marker_agents[ff_id]


def victim(model: WildFireModel, vid: str):
    return model.victim_marker_agents[vid]


def place_units(model: WildFireModel, units: dict[str, tuple[int, int]]) -> None:
    """Every unit in `units` free and parked on its cell; every other unit dead (out of the pool)."""
    for ff_id, marker in model.firefighter_marker_agents.items():
        marker.assigned = False
        marker.target_pos = None
        marker.rescued_victim = None
        marker.exiting = False
        marker.exit_target = None
        marker.rescue_completed = False
        if ff_id in units:
            marker.dead = False
            marker.status = "available"
            if marker.pos is None:
                model.grid.place_agent(marker, units[ff_id])
            else:
                model.grid.move_agent(marker, units[ff_id])
        else:
            marker.dead = True
            marker.status = "dead"


def place_victims(model: WildFireModel, victims: dict[str, tuple[int, int]], detected=None) -> None:
    """Victims in `victims` parked on their cells; detected = those ids (default: all of `victims`). Every other
    victim and every non-detected one is UNDETECTED (confirmed False, no runtime record)."""
    detected = set(victims) if detected is None else set(detected)
    runtime = getattr(model, "victim_runtime_model", None)
    records = getattr(runtime, "victims", None)
    if isinstance(records, dict):
        records.clear()
    for vid, marker in model.victim_marker_agents.items():
        state = model.managed_victims[vid]
        if vid in victims:
            cell = victims[vid]
            if marker.pos is None:
                model.grid.place_agent(marker, cell)
            else:
                model.grid.move_agent(marker, cell)
            if hasattr(marker, "spawn_cell"):
                marker.spawn_cell = cell
            if hasattr(marker, "leash_anchor"):
                marker.leash_anchor = cell
        state.rescued = False
        state.cancelled = False
        state.unreachable = False
        state.rescue_assigned = False
        state.assigned = False
        if vid in detected:
            state.confirmed = True
            state.status = "confirmed"
            marker.status = "confirmed"
        else:
            state.confirmed = False
            state.status = "candidate"
            marker.status = "candidate"


def assign(model: WildFireModel, vid: str, ff_id: str, reason: str = "initial") -> bool:
    """A bind straight through the model's command sink."""
    marker = victim(model, vid)
    return bool(
        model.apply_physical_rescue_command(
            PhysicalRescueCommand(
                action="assign",
                victim_id=vid,
                firefighter_id=ff_id,
                reason=reason,
                metadata={"victim_marker": marker, "target_pos": tuple(marker.pos)},
            )
        )
    )


def binders(model: WildFireModel, vid: str, *, active_only: bool = False) -> list[str]:
    marker = victim(model, vid)
    out = []
    for ff_id, unit in model.firefighter_marker_agents.items():
        if getattr(unit, "dead", False) or getattr(unit, "rescued_victim", None) is not marker:
            continue
        if active_only and str(unit.status).lower() in ("route_blocked", "dead"):
            continue
        out.append(ff_id)
    return sorted(out)


def bound_to(model: WildFireModel, ff_id: str):
    rv = getattr(ff(model, ff_id), "rescued_victim", None)
    if rv is None:
        return None
    for vid, marker in model.victim_marker_agents.items():
        if marker is rv:
            return vid
    return "?"


def move(model: WildFireModel, ff_id: str, cell: tuple[int, int]) -> None:
    model.grid.move_agent(ff(model, ff_id), cell)


def set_step(model: WildFireModel, step: int) -> None:
    model.evaluation_timesteps_counter = int(step)
