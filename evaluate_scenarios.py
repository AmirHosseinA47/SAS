"""Batch headless evaluation over multiple random seeds.

Usage:
    python evaluate_scenarios.py --scenario A --wind east --n 20
    python evaluate_scenarios.py --n 5 --steps 300 --wind east
    python evaluate_scenarios.py --scenario A --wind north --n 5 --steps 240 --seeds 101,202,303,404,505
    python evaluate_scenarios.py --scenario A --wind north --n 5 --steps 240 --seed-base 100

Read-only with respect to simulation logic: uses the same model setup as
serve_dashboard.py and prints a summary (optionally CSV to stdout).
"""

from __future__ import annotations

import argparse
import csv
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

from serve_dashboard import (
    BUILTIN_SCENARIOS,
    _build_evaluation,
    _resolve_role_count_params,
    _resolve_seed,
)

METRIC_KEYS = (
    "rescued",
    "dead",
    "unreachable",
    "geographically_isolated",
    "never_detected",
    "horizon_unresolved",
    "unreachable_other",
    "candidate",
    "rescue_rate",
    "firefighter_deaths",
    "burnt_cells",
    "terminal_step",
    "steps_run",
)


def _scenario_params(args: argparse.Namespace) -> dict:
    preset = BUILTIN_SCENARIOS.get(args.scenario, {})
    num_agents = int(args.uavs if args.uavs is not None else preset.get("NUM_AGENTS", 3))
    fire_trackers, victim_searchers = _resolve_role_count_params(
        num_agents,
        getattr(args, "fire_trackers", None),
        getattr(args, "victim_searchers", None),
    )
    return {
        "NUM_AGENTS": num_agents,
        "NUM_VICTIMS": int(args.victims if args.victims is not None else preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(
            args.firefighters if args.firefighters is not None else preset.get("NUM_FIREFIGHTERS", 3)
        ),
        "WIND_DIRECTION": str(args.wind),
        "BATCH_SIZE": int(args.batch_size),
        "FIRE_SPREAD_MULTIPLIER": float(args.fire_spread),
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": fire_trackers,
        "NUM_VICTIM_SEARCHERS": victim_searchers,
    }


def _reproduce_line(args: argparse.Namespace, seeds: list[int]) -> str:
    parts = [
        "python evaluate_scenarios.py",
        "--scenario %s" % args.scenario,
        "--wind %s" % args.wind,
        "--n %d" % args.n,
        "--steps %d" % args.steps,
        "--seeds %s" % ",".join(str(s) for s in seeds),
    ]
    if args.uavs is not None:
        parts.append("--uavs %d" % args.uavs)
    if args.victims is not None:
        parts.append("--victims %d" % args.victims)
    if args.firefighters is not None:
        parts.append("--firefighters %d" % args.firefighters)
    if args.fire_spread != 0.75:
        parts.append("--fire-spread %s" % args.fire_spread)
    if args.batch_size != 300:
        parts.append("--batch-size %d" % args.batch_size)
    if getattr(args, "fire_trackers", None) is not None:
        parts.append("--fire-trackers %d" % args.fire_trackers)
    if getattr(args, "victim_searchers", None) is not None:
        parts.append("--victim-searchers %d" % args.victim_searchers)
    return "REPRODUCE: " + " ".join(parts)


def _run_seed(seed: int, params: dict, steps: int, *, quiet: bool = True) -> dict:
    import contextlib
    import io as _io

    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    terminal_step = None
    step = 0
    stdout_ctx = (
        contextlib.redirect_stdout(_io.StringIO())
        if quiet
        else contextlib.nullcontext()
    )
    with stdout_ctx:
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()
            step += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                mission = panel.get("mission_status", {}) or {}
                if mission.get("all_victims_terminal"):
                    terminal_step = step

    evaluation = _build_evaluation(model, terminal_step, step, params)
    evaluation["seed"] = seed
    return evaluation


def _mean_std(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.stdev(values)


def _parse_seeds_arg(raw: str) -> list[int]:
    parts = [p.strip() for p in raw.split(",")]
    if not parts or any(not p for p in parts):
        raise ValueError("--seeds must be a comma-separated list of integers (e.g. 101,202,303)")
    try:
        return [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError("--seeds must be a comma-separated list of integers (e.g. 101,202,303)") from exc


def _resolve_run_seeds(args: argparse.Namespace) -> list[int]:
    """Resolve the seed list for this batch: --seeds, --seed-base, or random."""
    if args.seeds is not None and args.seed_base is not None:
        raise ValueError("Provide either --seeds or --seed-base, not both")

    if args.seeds is not None:
        seeds = _parse_seeds_arg(args.seeds)
        if len(seeds) != args.n:
            raise ValueError(
                "--seeds length (%d) does not match --n (%d); provide exactly %d seed(s)"
                % (len(seeds), args.n, args.n)
            )
        return seeds

    if args.seed_base is not None:
        return [int(args.seed_base) + i for i in range(args.n)]

    return [_resolve_seed(None) for _ in range(args.n)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch evaluate WildFireModel over random seeds.")
    parser.add_argument("--scenario", default="A", choices=["A", "B", "C", "D"])
    parser.add_argument("--wind", default="east", choices=["north", "south", "east", "west"])
    parser.add_argument("--n", type=int, default=20, help="Number of random seeds to run")
    parser.add_argument("--steps", type=int, default=300, help="Maximum simulation steps per run")
    parser.add_argument("--batch-size", type=int, default=300, dest="batch_size")
    parser.add_argument("--fire-spread", type=float, default=0.75, dest="fire_spread")
    parser.add_argument("--uavs", type=int, default=None)
    parser.add_argument("--victims", type=int, default=None)
    parser.add_argument("--firefighters", type=int, default=None)
    parser.add_argument("--fire-trackers", type=int, default=None, dest="fire_trackers")
    parser.add_argument("--victim-searchers", type=int, default=None, dest="victim_searchers")
    parser.add_argument(
        "--seeds",
        default=None,
        help="Comma-separated list of integer seeds (length must equal --n)",
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=None,
        dest="seed_base",
        help="Derive deterministic seeds as seed_base, seed_base+1, ..., seed_base+n-1",
    )
    parser.add_argument("--csv", action="store_true", help="Print CSV rows to stdout")
    args = parser.parse_args(argv)

    if args.n < 1:
        print("N must be >= 1", file=sys.stderr)
        return 2

    try:
        seeds = _resolve_run_seeds(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # Random path only: print generated seeds so the run can be reproduced later.
    if args.seeds is None and args.seed_base is None:
        print("SEEDS: " + ",".join(str(s) for s in seeds))

    try:
        params = _scenario_params(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rows: list[dict] = []

    print(
        "Scenario %s | wind %s | %d UAV / %d victims / %d FF | steps=%d | N=%d"
        % (
            args.scenario,
            params["WIND_DIRECTION"],
            params["NUM_AGENTS"],
            params["NUM_VICTIMS"],
            params["NUM_FIREFIGHTERS"],
            args.steps,
            args.n,
        )
    )
    print("-" * 72)

    for seed in seeds:
        try:
            row = _run_seed(seed, params, args.steps)
        except Exception as exc:
            print("seed=%-10d ERROR: %s: %s" % (seed, type(exc).__name__, exc))
            continue
        rows.append(row)
        print(
            "seed=%-10d rescued=%d dead=%d unreachable=%d geo=%d never_detected=%d horizon=%d other=%d unresolved=%d rate=%.1f%% ff_deaths=%d burnt=%d terminal=%s all_terminal=%s"
            % (
                seed,
                row["rescued"],
                row["dead"],
                row["unreachable"],
                row.get("geographically_isolated", 0),
                row.get("never_detected", 0),
                row.get("horizon_unresolved", 0),
                row.get("unreachable_other", 0),
                row["candidate"],
                row["rescue_rate"],
                row["firefighter_deaths"],
                row["burnt_cells"],
                row["terminal_step"] if row["terminal_step"] is not None else "-",
                row.get("all_terminal"),
            )
        )
        if row.get("unreachable_causes"):
            print("  causes: %s" % row["unreachable_causes"])

    print("-" * 72)
    if not rows:
        print("No successful runs.")
        return 1
    total = len(rows)
    print("Summary (mean +/- std) over %d successful run(s):" % total)
    for key in METRIC_KEYS:
        nums = [float(r[key]) for r in rows if r.get(key) is not None]
        mean, std = _mean_std(nums)
        # terminal_step is None on runs that never reached an all-victims-terminal
        # state, so its mean is computed over a subset of rows. Always disclose the
        # contributing count for it; disclose it for any other metric only when that
        # metric is actually partial, so a future nullable field cannot be averaged
        # over a silent subset. Values are unchanged either way.
        if key == "terminal_step" or len(nums) < total:
            suffix = " (n=%d/%d)" % (len(nums), total)
        else:
            suffix = ""
        if mean is None:
            print("  %s: n/a%s" % (key, suffix))
        elif key == "rescue_rate":
            print("  %s: %.2f +/- %.2f%s" % (key, mean, std or 0.0, suffix))
        elif key == "terminal_step":
            print("  %s: %.1f +/- %.1f%s" % (key, mean, std or 0.0, suffix))
        else:
            print("  %s: %.2f +/- %.2f%s" % (key, mean, std or 0.0, suffix))
    non_terminal = sum(1 for r in rows if r.get("terminal_step") is None)
    print(
        "  non_terminal_runs: %d/%d (never reached all-victims-terminal within steps=%d)"
        % (non_terminal, total, args.steps)
    )

    if args.csv:
        out = io.StringIO()
        fieldnames = (
            ["seed"]
            + list(METRIC_KEYS)
            + ["all_terminal", "total_victims", "scenario", "wind", "unreachable_causes"]
        )
        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        print(out.getvalue())

    print(_reproduce_line(args, seeds))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
