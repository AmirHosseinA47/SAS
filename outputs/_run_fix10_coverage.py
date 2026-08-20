"""Grid coverage fraction for fix10 (searcher observation disk, r=8).

Runs the same 16 combos / 5 seeds as evaluate_scenarios.py but instruments
searcher positions. UTF-8 output. Batches of at most 4.
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)
os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from common_fixed_variables import UAV_OBSERVATION_RADIUS
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation
from src_extension.adaptation.local_adaptation_generator import (
    apply_scenario_config,
    resolve_victim_searcher_uav_ids,
)
from wildfire_model import WildFireModel

PY = sys.executable
GRID = 50
OBS = float(UAV_OBSERVATION_RADIUS)
STEPS = 240
SCENARIOS = ("A", "B", "C", "D")
WINDS = ("north", "south", "east", "west")
OUT_PATH = os.path.join(_ROOT, "outputs", "fix10_coverage.txt")


def _params(scenario: str, wind: str) -> dict:
    preset = BUILTIN_SCENARIOS[scenario]
    return {
        "NUM_AGENTS": int(preset.get("NUM_AGENTS", 3)),
        "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
        "WIND_DIRECTION": str(wind),
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
    }


def _mark_obs(covered: set[tuple[int, int]], px: int, py: int, radius: float) -> None:
    r = int(math.ceil(radius))
    r2 = radius * radius
    for dx in range(-r, r + 1):
        cx = px + dx
        if cx < 0 or cx >= GRID:
            continue
        for dy in range(-r, r + 1):
            cy = py + dy
            if cy < 0 or cy >= GRID:
                continue
            if dx * dx + dy * dy <= r2:
                covered.add((cx, cy))


def run_seed(scenario: str, wind: str, seed: int) -> dict:
    params = _params(scenario, wind)
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        searcher_ids = resolve_victim_searcher_uav_ids(model)
        covered: set[tuple[int, int]] = set()
        for _ in range(STEPS):
            model.step()
            for agent in model.schedule.agents:
                if type(agent) is not am.UAV:
                    continue
                if str(agent.unique_id) not in searcher_ids:
                    continue
                pos = getattr(agent, "pos", None)
                if pos is None:
                    continue
                _mark_obs(covered, int(pos[0]), int(pos[1]), OBS)
        ev = _build_evaluation(model, None, STEPS, params)
    frac = len(covered) / float(GRID * GRID)
    return {
        "scenario": scenario,
        "wind": wind,
        "seed": seed,
        "covered": len(covered),
        "frac": frac,
        "never_detected": ev.get("never_detected"),
        "unreachable_causes": ev.get("unreachable_causes"),
    }


def run_combo(scenario: str, wind: str, seeds: list[int]) -> list[str]:
    lines: list[str] = []
    fracs: list[float] = []
    for seed in seeds:
        row = run_seed(scenario, wind, seed)
        fracs.append(row["frac"])
        lines.append(
            "  %s/%s seed=%s covered=%d frac=%.4f nd=%s causes=%s"
            % (
                scenario,
                wind,
                seed,
                row["covered"],
                row["frac"],
                row["never_detected"],
                row["unreachable_causes"],
            )
        )
    mean = sum(fracs) / float(len(fracs))
    lines.append(
        "%s | %s | %.4f | %s"
        % (scenario, wind, mean, ",".join("%.4f" % f for f in fracs))
    )
    return lines


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "worker":
        scenario, wind, seed_csv, out_path = argv[1], argv[2], argv[3], argv[4]
        seeds = [int(x) for x in seed_csv.split(",") if x]
        lines = run_combo(scenario, wind, seeds)
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print("\n".join(lines), flush=True)
        return 0

    in_seeds = [101, 202, 303, 404, 505]
    prefix = argv[0] if argv else "in"
    if prefix == "oos":
        in_seeds = [616, 727, 838, 949, 1061]
        out_path = os.path.join(_ROOT, "outputs", "fix10oos_coverage.txt")
    else:
        out_path = OUT_PATH
    py = sys.executable
    seed_csv = ",".join(str(s) for s in in_seeds)
    jobs: list[tuple[str, str, str]] = []
    for s in SCENARIOS:
        for w in WINDS:
            combo_path = os.path.join(
                _ROOT, "outputs", "_cov_%s_%s_%s.txt" % (prefix, s, w)
            )
            jobs.append((s, w, combo_path))

    def _run_one(job: tuple[str, str, str]) -> tuple[str, str, str, int, float]:
        s, w, combo_path = job
        t0 = time.time()
        args = [py, __file__, "worker", s, w, seed_csv, combo_path]
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.run(args, env=env, cwd=_ROOT)
        return s, w, combo_path, proc.returncode, time.time() - t0

    lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    log("Python %s" % sys.version.replace("\n", " "))
    log("mesa %s" % __import__("mesa").__version__)
    log("UAV_OBSERVATION_RADIUS=%s" % OBS)
    log("prefix=%s seeds=%s" % (prefix, in_seeds))
    log("scenario | wind | mean_coverage | per-seed")
    BATCH = 4
    rc_all = 0
    for i in range(0, len(jobs), BATCH):
        chunk = jobs[i : i + BATCH]
        log("BATCH %d-%d" % (i + 1, i + len(chunk)))
        with ThreadPoolExecutor(max_workers=BATCH) as ex:
            futs = [ex.submit(_run_one, job) for job in chunk]
            for fut in as_completed(futs):
                s, w, combo_path, rc, elapsed = fut.result()
                log("  DONE %s/%s exit=%d elapsed=%.1fs" % (s, w, rc, elapsed))
                rc_all = rc_all or rc
    means: list[tuple[str, str, float]] = []
    for s, w, combo_path in jobs:
        with open(combo_path, encoding="utf-8") as f:
            combo_text = f.read().rstrip("\n")
        for line in combo_text.splitlines():
            log(line)
            if line.startswith("%s | %s |" % (s, w)):
                parts = [p.strip() for p in line.split("|")]
                means.append((s, w, float(parts[2])))
    log("")
    log("=== mean coverage by combo ===")
    for s, w, mean in means:
        log("%s | %s | %.4f" % (s, w, mean))
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    log("wrote %s" % out_path)
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
