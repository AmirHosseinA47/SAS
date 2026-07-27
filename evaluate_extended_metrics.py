"""Extended batch metrics: fire_tracker smoke/fire steps + FF deaths/rescues.

Uses the same model setup as evaluate_scenarios.py.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import random
import statistics
import sys

os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

from evaluate_scenarios import _scenario_params
from serve_dashboard import _build_evaluation


def _active_fire_cells(model: WildFireModel) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for agent in model.schedule.agents:
        if type(agent).__name__ != "Fire":
            continue
        if getattr(agent, "is_burning", lambda: False)():
            cells.add((int(agent.pos[0]), int(agent.pos[1])))
    return cells


def _run_with_tracker_metrics(seed: int, params: dict, steps: int) -> dict:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    terminal_step = None
    step = 0
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        ft_ids = sorted(
            uid
            for uid in model.managed_uav_states
            if model._uav_assignment_role(uid) == "fire_tracker"
        )
        smoke_steps = {uid: 0 for uid in ft_ids}
        fire_steps = {uid: 0 for uid in ft_ids}
        for _ in range(steps):
            model.step()
            step += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                mission = panel.get("mission_status", {}) or {}
                if mission.get("all_victims_terminal"):
                    terminal_step = step
            for uid in ft_ids:
                agent = next(
                    (a for a in model.schedule.agents if str(a.unique_id) == uid),
                    None,
                )
                if agent is None or getattr(agent, "pos", None) is None:
                    continue
                x, y = int(agent.pos[0]), int(agent.pos[1])
                vis = getattr(model, "visibility_model", None)
                sm = getattr(vis, "smoke_obscured_cells", None) if vis else None
                if isinstance(sm, (set, list, tuple)) and (x, y) in sm:
                    smoke_steps[uid] += 1
                for fa in model.schedule.agents:
                    if (
                        type(fa).__name__ == "Fire"
                        and fa.pos == (x, y)
                        and fa.is_burning()
                    ):
                        fire_steps[uid] += 1

    evaluation = _build_evaluation(model, terminal_step, step, params)
    evaluation["seed"] = seed
    evaluation["tracker_smoke"] = smoke_steps
    evaluation["tracker_fire"] = fire_steps
    evaluation["tracker_smoke_total"] = sum(smoke_steps.values())
    evaluation["tracker_fire_total"] = sum(fire_steps.values())
    return evaluation


def _mean_std(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.stdev(values)


def _fmt_ms(mean: float | None, std: float | None) -> str:
    if mean is None:
        return "n/a"
    return f"{mean:.2f} +/- {std or 0.0:.2f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extended tracker + FF metrics.")
    parser.add_argument("--scenario", default="A", choices=["A", "B", "C", "D"])
    parser.add_argument("--wind", default="east", choices=["north", "south", "east", "west"])
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=300, dest="batch_size")
    parser.add_argument("--fire-spread", type=float, default=0.75, dest="fire_spread")
    parser.add_argument("--fixed-seed", type=int, default=42)
    parser.add_argument("--extra-seeds", type=str, default="", help="Comma-separated seeds")
    parser.add_argument("--uavs", type=int, default=None)
    parser.add_argument("--victims", type=int, default=None)
    parser.add_argument("--firefighters", type=int, default=None)
    args = parser.parse_args(argv)

    params = _scenario_params(args)
    seeds: list[int] = []
    if args.fixed_seed is not None:
        seeds.append(int(args.fixed_seed))
    if args.extra_seeds.strip():
        seeds.extend(int(s.strip()) for s in args.extra_seeds.split(",") if s.strip())
    while len(seeds) < args.n + (1 if args.fixed_seed is not None else 0):
        seeds.append(random.randint(1, 10_000_000))
    seeds = list(dict.fromkeys(seeds))
    random_seeds = [s for s in seeds if s != args.fixed_seed][: args.n]
    all_seeds = ([args.fixed_seed] if args.fixed_seed is not None else []) + random_seeds

    rows: list[dict] = []
    print(f"wind={params['WIND_DIRECTION']} steps={args.steps} seeds={all_seeds}")
    for seed in all_seeds:
        row = _run_with_tracker_metrics(seed, params, args.steps)
        rows.append(row)
        print(
            f"seed={seed} smoke={row['tracker_smoke']} fire={row['tracker_fire']} "
            f"resc={row['rescued']} dead={row['dead']} ff_deaths={row['firefighter_deaths']}"
        )

    random_rows = [r for r in rows if r["seed"] != args.fixed_seed]
    fixed_row = next((r for r in rows if r["seed"] == args.fixed_seed), None)

    print("--- mean+/-std (random seeds) ---")
    for key in ("tracker_smoke_total", "tracker_fire_total", "firefighter_deaths", "rescued", "dead"):
        nums = [float(r[key]) for r in random_rows]
        print(f"  {key}: {_fmt_ms(*_mean_std(nums))}")

    if fixed_row:
        print(f"--- seed={args.fixed_seed} ---")
        print(f"  tracker_smoke: {fixed_row['tracker_smoke']}")
        print(f"  tracker_fire: {fixed_row['tracker_fire']}")
        print(
            f"  rescued={fixed_row['rescued']} dead={fixed_row['dead']} "
            f"ff_deaths={fixed_row['firefighter_deaths']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
