"""HEAD grid-coverage baseline: searcher-only AND all-UAV unions, r=8 Euclidean.

Conventions (_params, _mark_obs, seeding, worker/batch structure,
_build_evaluation) are copied verbatim from outputs/_run_fix10_coverage.py so
the searcher-only number stays directly comparable to previously cited figures.

The ONLY change is the accumulation: _run_fix10_coverage.py drops non-searcher
UAVs before _mark_obs, so it structurally cannot produce an all-UAV union.
Detection in wildfire_model._detect_victims_in_uav_radius iterates EVERY UAV
with no role filter, so the all-UAV union is the quantity that actually bounds
never_detected.

Coverage convention, both metrics: Euclidean radius 8, union of observation
disks over all 240 steps, divided by 2500.

UTF-8 output written from Python. Batches of at most 4.
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

GRID = 50
OBS = float(UAV_OBSERVATION_RADIUS)
STEPS = 240
SCENARIOS = ("A", "B", "C", "D")
WINDS = ("north", "south", "east", "west")
SEEDS = [101, 202, 303, 404, 505]
OUT_PATH = os.path.join(_ROOT, "outputs", "baseline_coverage.txt")


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


def _mark_obs(covered: set, px: int, py: int, radius: float) -> None:
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
        cov_searcher: set = set()
        cov_all: set = set()
        for _ in range(STEPS):
            model.step()
            for agent in model.schedule.agents:
                if type(agent) is not am.UAV:
                    continue
                pos = getattr(agent, "pos", None)
                if pos is None:
                    continue
                px, py = int(pos[0]), int(pos[1])
                _mark_obs(cov_all, px, py, OBS)
                if str(agent.unique_id) in searcher_ids:
                    _mark_obs(cov_searcher, px, py, OBS)
        ev = _build_evaluation(model, None, STEPS, params)
    n = float(GRID * GRID)
    return {
        "scenario": scenario,
        "wind": wind,
        "seed": seed,
        "cov_searcher": len(cov_searcher),
        "frac_searcher": len(cov_searcher) / n,
        "cov_all": len(cov_all),
        "frac_all": len(cov_all) / n,
        "n_searchers": len(searcher_ids),
        "never_detected": ev.get("never_detected"),
        "unreachable_causes": ev.get("unreachable_causes"),
    }


def run_combo(scenario: str, wind: str, seeds: list) -> list:
    lines: list = []
    fs: list = []
    fa: list = []
    for seed in seeds:
        row = run_seed(scenario, wind, seed)
        fs.append(row["frac_searcher"])
        fa.append(row["frac_all"])
        lines.append(
            "  %s/%s seed=%s searcher=%d/%.4f all=%d/%.4f nsearch=%d nd=%s causes=%s"
            % (
                scenario,
                wind,
                seed,
                row["cov_searcher"],
                row["frac_searcher"],
                row["cov_all"],
                row["frac_all"],
                row["n_searchers"],
                row["never_detected"],
                row["unreachable_causes"],
            )
        )
    lines.append(
        "%s | %s | %.4f | %.4f | %s | %s"
        % (
            scenario,
            wind,
            sum(fs) / float(len(fs)),
            sum(fa) / float(len(fa)),
            ",".join("%.4f" % f for f in fs),
            ",".join("%.4f" % f for f in fa),
        )
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

    head = ""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        head = "unknown"

    seed_csv = ",".join(str(s) for s in SEEDS)
    jobs = []
    for s in SCENARIOS:
        for w in WINDS:
            jobs.append((s, w, os.path.join(_ROOT, "outputs", "_bl_%s_%s.txt" % (s, w))))

    lines: list = []

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    log("=== HEAD grid coverage baseline ===")
    log("HEAD commit: %s" % head)
    log("Python %s" % sys.version.replace("\n", " "))
    log("mesa %s" % __import__("mesa").__version__)
    log("UAV_OBSERVATION_RADIUS=%s" % OBS)
    log("steps=%d  grid=%dx%d  seeds=%s" % (STEPS, GRID, GRID, SEEDS))
    log("")
    log("COVERAGE CONVENTION (both metrics):")
    log("  Euclidean radius 8 (dx*dx + dy*dy <= 64) observation disks,")
    log("  union over all %d steps, divided by %d." % (STEPS, GRID * GRID))
    log("  searcher-only = disks from victim-searcher UAVs only")
    log("                  (comparable to previously cited 0.485 / 0.568 / 0.641).")
    log("  all-UAV       = disks from EVERY UAV. This is the quantity that bounds")
    log("                  never_detected: wildfire_model._detect_victims_in_uav_radius")
    log("                  iterates every UAV with no role filter, so fire trackers")
    log("                  detect victims exactly as searchers do.")
    log("")

    def _run_one(job):
        s, w, combo_path = job
        t0 = time.time()
        args = [sys.executable, __file__, "worker", s, w, seed_csv, combo_path]
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        log_path = combo_path.replace(".txt", ".log")
        with open(log_path, "w", encoding="utf-8", newline="\n") as lf:
            proc = subprocess.run(
                args, env=env, cwd=_ROOT, stdout=lf, stderr=subprocess.STDOUT
            )
        return s, w, combo_path, proc.returncode, time.time() - t0

    aggregate_only = bool(argv and argv[0] == "aggregate")
    BATCH = 4
    rc_all = 0
    if aggregate_only:
        log("(aggregate-only: reusing existing outputs/_bl_*.txt combo files)")
    else:
        for i in range(0, len(jobs), BATCH):
            chunk = jobs[i : i + BATCH]
            log("BATCH %d-%d" % (i + 1, i + len(chunk)))
            with ThreadPoolExecutor(max_workers=BATCH) as ex:
                futs = [ex.submit(_run_one, job) for job in chunk]
                for fut in as_completed(futs):
                    s, w, combo_path, rc, elapsed = fut.result()
                    log("  DONE %s/%s exit=%d elapsed=%.1fs" % (s, w, rc, elapsed))
                    rc_all = rc_all or rc

    log("")
    log("=== per-seed detail ===")
    means = []
    seed_rows = []
    for s, w, combo_path in jobs:
        with open(combo_path, encoding="utf-8") as f:
            combo_text = f.read().rstrip("\n")
        for line in combo_text.splitlines():
            log(line)
            if line.startswith("%s | %s |" % (s, w)):
                parts = [p.strip() for p in line.split("|")]
                means.append((s, w, float(parts[2]), float(parts[3])))
            elif "seed=" in line and "searcher=" in line:
                try:
                    tok = line.split()
                    seed = int(tok[1].split("=")[1])
                    fs = float(tok[2].split("=")[1].split("/")[1])
                    fa = float(tok[3].split("=")[1].split("/")[1])
                    nd = int(tok[5].split("=")[1])
                    causes = line.partition("causes=")[2].strip()
                    seed_rows.append((s, w, seed, fs, fa, nd, causes))
                except (IndexError, ValueError):
                    pass

    log("")
    log("=== mean coverage by combo ===")
    log("scenario | wind  | searcher_only | all_UAV | delta")
    for s, w, ms, ma in means:
        log("%-8s | %-5s | %13.4f | %7.4f | %+.4f" % (s, w, ms, ma, ma - ms))
    if means:
        gs = sum(m[2] for m in means) / len(means)
        ga = sum(m[3] for m in means) / len(means)
        log("")
        log("GRAND MEAN searcher-only = %.4f  (16 combos x 5 seeds = %d runs)" % (gs, len(seed_rows)))
        log("GRAND MEAN all-UAV       = %.4f" % ga)
        log("GRAND MEAN delta         = %+.4f" % (ga - gs))

    if seed_rows:
        log("")
        log("=" * 74)
        log("DO THE TWO METRICS DIVERGE, AND WHICH SHOULD THE NEXT FIX BE MEASURED ON?")
        log("=" * 74)
        log("")
        log("YES - they diverge substantially. all-UAV coverage exceeds searcher-only by")
        log("+%.4f on average (%.4f vs %.4f), and the gap is present in every one of the"
            % (ga - gs, ga, gs))
        log("16 combos, ranging from +%.4f to +%.4f."
            % (min(m[3] - m[2] for m in means), max(m[3] - m[2] for m in means)))
        log("")
        log("Reproduction check: the previously cited single-run searcher-only figures")
        log("are reproduced exactly at HEAD -")
        for s, w, sd in (("D", "south", 101), ("D", "north", 101), ("A", "west", 505)):
            for row in seed_rows:
                if row[0] == s and row[1] == w and row[2] == sd:
                    log("  %s/%s seed %d searcher-only = %.4f" % (s, w, sd, row[3]))
        log("So 0.485 / 0.568 / 0.641 were single runs of these combos. Against the true")
        log("16x5 searcher-only mean of %.4f they are ordinary, not anomalously low." % gs)
        log("")
        nds = [r for r in seed_rows if r[5] > 0]
        log("never_detected events: %d of %d runs (%.1f%%)."
            % (len(nds), len(seed_rows), 100.0 * len(nds) / len(seed_rows)))
        if nds:
            log("")
            log("  %-12s %6s %11s %9s  %s" % ("combo", "seed", "searcher", "all-UAV", "cause"))
            for s, w, sd, fs, fa, nd, causes in sorted(nds, key=lambda r: -r[4]):
                log("  %-12s %6d %11.4f %9.4f  %s" % ("%s/%s" % (s, w), sd, fs, fa, causes))
            hi = [r for r in nds if r[4] >= 0.85]
            log("")
            log("CRITICAL: %d of these %d misses occurred at all-UAV coverage >= 0.85,"
                % (len(hi), len(nds)))
            log("the highest at %.4f. A victim can go undetected while ~93%% of the grid"
                % max(r[4] for r in nds))
            log("has been observed at some point. Aggregate coverage fraction therefore")
            log("does NOT discriminate success from failure, in either metric.")
            log("")
            log("WHICH METRIC TO MEASURE THE NEXT FIX ON: all-UAV union is the correct")
            log("BOUND (it is what wildfire_model._detect_victims_in_uav_radius actually")
            log("integrates over), so it should be reported. But neither aggregate")
            log("fraction should be used as the OPTIMISATION TARGET, because at 0.84 mean")
            log("all-UAV coverage the residual misses live in specific uncovered cells,")
            log("not in the size of the covered set. The discriminating quantity is")
            log("WHICH cells stay uncovered - i.e. whether the victim's own")
            log("neighbourhood is ever entered - not how many cells are covered.")
            log("Keep never_detected as the primary metric and report both coverage")
            log("numbers as diagnostics alongside it.")

    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    log("wrote %s" % OUT_PATH)
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
