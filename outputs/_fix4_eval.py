"""Temporary seed-matched matrix with unreachable cause split. Not a repo source file."""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)
os.environ.setdefault("MPLBACKEND", "Agg")

import evaluate_scenarios as ev
from src_extension.planning.rescue_planner import (
    UNREACHABLE_CAUSE_GEOGRAPHIC,
    UNREACHABLE_CAUSE_HORIZON,
    UNREACHABLE_CAUSE_UNDETECTED,
)


def _cause_of(state) -> str:
    cause = str(getattr(state, "unreachable_cause", "") or "").strip()
    if cause:
        return cause
    attrs = getattr(state, "attributes", None)
    if isinstance(attrs, dict):
        return str(attrs.get("unreachable_cause", "") or "").strip()
    return ""


def _run_seed(seed: int, params: dict, steps: int) -> dict:
    import contextlib
    import io as _io
    import random

    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from serve_dashboard import _build_evaluation
    from wildfire_model import WildFireModel

    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    terminal_step = None
    step = 0
    with contextlib.redirect_stdout(_io.StringIO()):
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
    geo = und = horizon = other = 0
    causes: list[str] = []
    for vid, st in (getattr(model, "managed_victims", None) or {}).items():
        status = str(getattr(st, "status", "") or "").strip().lower()
        if status != "unreachable":
            continue
        cause = _cause_of(st)
        causes.append("%s:%s" % (vid, cause or "unspecified"))
        if cause == UNREACHABLE_CAUSE_GEOGRAPHIC:
            geo += 1
        elif cause == UNREACHABLE_CAUSE_UNDETECTED:
            und += 1
        elif cause == UNREACHABLE_CAUSE_HORIZON:
            horizon += 1
        else:
            other += 1
    panel = model.get_dashboard_state()
    mission = panel.get("mission_status", {}) or {}
    evaluation["geographically_isolated"] = geo
    evaluation["never_detected"] = und
    evaluation["horizon_unresolved"] = horizon
    evaluation["unreachable_other"] = other
    evaluation["unreachable_causes"] = ";".join(sorted(causes))
    evaluation["dash_geo"] = int(mission.get("geographically_isolated_count") or 0)
    evaluation["dash_und"] = int(mission.get("never_detected_count") or 0)
    evaluation["dash_all_terminal"] = bool(mission.get("all_victims_terminal"))
    return evaluation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=["A", "B", "C", "D"])
    parser.add_argument("--wind", required=True, choices=["north", "south", "east", "west"])
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--steps", type=int, default=240)
    parser.add_argument("--seeds", default="101,202,303,404,505")
    parser.add_argument("--csv", action="store_true")
    args = parser.parse_args(argv)

    ns = argparse.Namespace(
        scenario=args.scenario,
        wind=args.wind,
        uavs=None,
        victims=None,
        firefighters=None,
        batch_size=300,
        fire_spread=0.75,
        n=args.n,
        seeds=args.seeds,
        seed_base=None,
    )
    params = ev._scenario_params(ns)
    seeds = ev._parse_seeds_arg(args.seeds)
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
        ),
        flush=True,
    )
    print("-" * 72, flush=True)
    for seed in seeds:
        row = _run_seed(seed, params, args.steps)
        rows.append(row)
        print(
            "seed=%-10d rescued=%d dead=%d unreachable=%d geo=%d never_detected=%d horizon=%d other=%d unresolved=%d rate=%.1f%% ff_deaths=%d burnt=%d terminal=%s all_terminal=%s"
            % (
                seed,
                row["rescued"],
                row["dead"],
                row["unreachable"],
                row["geographically_isolated"],
                row["never_detected"],
                row["horizon_unresolved"],
                row["unreachable_other"],
                row["candidate"],
                row["rescue_rate"],
                row["firefighter_deaths"],
                row["burnt_cells"],
                row["terminal_step"] if row["terminal_step"] is not None else "-",
                row["all_terminal"],
            ),
            flush=True,
        )
        if row["unreachable_causes"]:
            print("  causes: %s" % row["unreachable_causes"], flush=True)
    print("-" * 72, flush=True)
    print("Summary (mean) over %d run(s):" % len(rows), flush=True)
    for key in (
        "rescued",
        "dead",
        "unreachable",
        "geographically_isolated",
        "never_detected",
        "horizon_unresolved",
        "unreachable_other",
        "candidate",
    ):
        vals = [float(r[key]) for r in rows]
        print("  %s: %.2f" % (key, sum(vals) / len(vals)))
    if args.csv:
        out = io.StringIO()
        fieldnames = [
            "seed",
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
            "all_terminal",
            "total_victims",
            "scenario",
            "wind",
            "unreachable_causes",
        ]
        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        print(out.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
