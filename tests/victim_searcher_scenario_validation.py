"""Generic victim_searcher scenario matrix validation (role-based, no hardcoded UAV ids)."""

from __future__ import annotations

import os
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import (
    apply_scenario_config,
    resolve_primary_victim_searcher_uav_id,
    resolve_victim_searcher_uav_ids,
)
from wildfire_model import WildFireModel

STEPS = 200
SEED = 42
EDGE_MARGIN = 2
WINDS = ("north", "south", "east", "west")

SCENARIO_A = {"NUM_AGENTS": 2, "NUM_VICTIMS": 3, "NUM_FIREFIGHTERS": 3}
SCENARIO_B = {"NUM_AGENTS": 3, "NUM_VICTIMS": 2, "NUM_FIREFIGHTERS": 2}
SCENARIO_C = {"NUM_AGENTS": 5, "NUM_VICTIMS": 3, "NUM_FIREFIGHTERS": 3}
SCENARIO_D = {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2}
EDGE_CASES = [{"NUM_AGENTS": 1, "NUM_VICTIMS": 0, "NUM_FIREFIGHTERS": 0}]


@dataclass
class ScenarioRunResult:
    scenario_name: str
    wind: str
    variable_wind: bool = False
    victim_searcher_id: str | None = None
    no_victim_searcher: bool = False
    pass_run: bool = False
    failures: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def _is_edge(pos: tuple[int, int], height: int, width: int) -> bool:
    x, y = pos
    return (
        x <= EDGE_MARGIN
        or x >= height - 1 - EDGE_MARGIN
        or y <= EDGE_MARGIN
        or y >= width - 1 - EDGE_MARGIN
    )


def _strict_hazard(model: WildFireModel, pos: tuple[int, int]) -> bool:
    x, y = int(pos[0]), int(pos[1])
    for agent in model.schedule.agents:
        if type(agent).__name__ == "Fire" and getattr(agent, "pos", None) == (x, y):
            if getattr(agent, "is_burning", lambda: False)():
                return True
    vis = getattr(model, "visibility_model", None)
    if vis is not None:
        smoke = getattr(vis, "smoke_obscured_cells", None)
        if isinstance(smoke, (set, list, tuple)) and (x, y) in smoke:
            return True
    return False


def _max_bool_streak(flags: list[bool]) -> int:
    best = cur = 0
    for flag in flags:
        if flag:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _max_value_streak(values: list[object]) -> int:
    if not values:
        return 0
    best = cur = 1
    for i in range(1, len(values)):
        if values[i] == values[i - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def _max_camping_5x5(positions: list[tuple[int, int]]) -> int:
    if not positions:
        return 0
    best = cur = 1
    anchor = positions[0]
    for i in range(1, len(positions)):
        pos = positions[i]
        if abs(pos[0] - anchor[0]) <= 2 and abs(pos[1] - anchor[1]) <= 2:
            cur += 1
            best = max(best, cur)
        else:
            anchor = pos
            cur = 1
    return best


def _configure_scenario(
    *,
    scenario: dict[str, int],
    wind: str,
    variable_wind: bool = False,
) -> None:
    rng = random.Random(SEED)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    values = {**scenario, "FIRE_SPREAD_MULTIPLIER": 0.75, "BATCH_SIZE": 99_999, "FIXED_WIND": not variable_wind}
    if variable_wind:
        values["FIRST_DIR"] = "west"
        values["SECOND_DIR"] = "east"
        values["FIRST_DIR_PROB"] = 0.8
        values["MU"] = 0.9
    else:
        values["WIND_DIRECTION"] = wind
        os.environ["WIND_DIRECTION"] = wind
    apply_scenario_config(cfv, wf, **values)


def run_scenario(
    *,
    scenario_name: str,
    scenario: dict[str, int],
    wind: str = "north",
    variable_wind: bool = False,
    steps: int = STEPS,
) -> ScenarioRunResult:
    _configure_scenario(scenario=scenario, wind=wind, variable_wind=variable_wind)
    model = WildFireModel()
    model.debug_log = False
    height = int(getattr(model, "HEIGHT", 50))
    width = int(getattr(model, "WIDTH", 50))
    vs_id = resolve_primary_victim_searcher_uav_id(model)
    result = ScenarioRunResult(
        scenario_name=scenario_name,
        wind=wind,
        variable_wind=variable_wind,
        victim_searcher_id=vs_id,
        no_victim_searcher=not bool(vs_id),
    )
    if not vs_id:
        for _ in range(steps):
            model.step()
        result.pass_run = True
        result.metrics = {"note": "no victim_searcher role assigned"}
        return result

    positions: list[tuple[int, int]] = []
    targets: list[tuple[float, float] | None] = []
    actions: list[str] = []
    fire_smoke_hits = 0
    num_victims = int(scenario.get("NUM_VICTIMS", 0) or 0)
    searcher_detections = 0

    for _ in range(steps):
        model.step()
        agent = next((a for a in model.schedule.agents if str(a.unique_id) == vs_id), None)
        if agent is None:
            result.failures.append(f"victim_searcher {vs_id} missing mid-run")
            break
        pos = (int(agent.pos[0]), int(agent.pos[1]))
        positions.append(pos)
        if _strict_hazard(model, pos):
            fire_smoke_hits += 1
        pr = model.latest_planning_result or {}
        pd = (pr.get("path_decisions") or {}).get(vs_id)
        tgt = None
        if pd is not None:
            ctx = getattr(pd, "uncertainty_context", {}) or {}
            raw = ctx.get("target_position")
            if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                tgt = (float(raw[0]), float(raw[1]))
        targets.append(tgt)
        exec_r = (model.latest_execution_result or {}).get("local", {})
        ur = (exec_r.get("uav_results") or {}).get(vs_id, {})
        actions.append(str(ur.get("action") or ""))
        ws = (getattr(model, "_wind_search_target_state", {}) or {}).get(vs_id, {})
        searcher_detections = max(
            searcher_detections, int(ws.get("searcher_victim_detections", 0) or 0)
        )

    rounded_targets = [(round(t[0]), round(t[1])) if t is not None else None for t in targets]
    edge_flags = [_is_edge(p, height, width) for p in positions]
    hold_flags = [a == "hold" for a in actions]
    target_only = [t for t in rounded_targets if t is not None]
    failures: list[str] = []
    camping_5x5 = _max_camping_5x5(positions)
    unique_positions = len(set(positions))
    unique_targets = len({t for t in rounded_targets if t is not None})
    if _max_value_streak(target_only) > 20:
        failures.append("same_target>20")
    if _max_bool_streak(hold_flags) > 10:
        failures.append("hold>10")
    if _max_bool_streak(edge_flags) > 40:
        failures.append("edge_streak>40")
    if fire_smoke_hits > 2:
        failures.append("fire_smoke>2")
    if camping_5x5 > 30:
        failures.append("camping_5x5>30")
    if unique_positions < 20:
        failures.append("unique_positions<20")
    if num_victims > 0 and unique_targets < 8:
        failures.append("unique_targets<8")

    result.failures = failures
    result.pass_run = len(failures) == 0
    result.metrics = {
        "victim_searcher_ids": resolve_victim_searcher_uav_ids(model),
        "unique_positions": unique_positions,
        "unique_targets": unique_targets,
        "camping_5x5": camping_5x5,
        "strict_fire_smoke_steps": fire_smoke_hits,
        "searcher_victim_detections": searcher_detections,
        "num_victims": num_victims,
    }
    return result


def run_scenario_matrix() -> list[ScenarioRunResult]:
    results: list[ScenarioRunResult] = []
    for name, scenario in [("A", SCENARIO_A), ("B", SCENARIO_B), ("C", SCENARIO_C), ("D", SCENARIO_D)]:
        for wind in WINDS:
            results.append(run_scenario(scenario_name=name, scenario=scenario, wind=wind))
    results.append(
        run_scenario(scenario_name="A", scenario=SCENARIO_A, wind="west/east", variable_wind=True)
    )
    for idx, scenario in enumerate(EDGE_CASES):
        for wind in WINDS:
            results.append(run_scenario(scenario_name=f"edge_{idx}", scenario=scenario, wind=wind))
    return results
