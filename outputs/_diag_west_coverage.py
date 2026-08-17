"""Part 1 diagnostics for west-wind never_detected (read-only; no production edits)."""
from __future__ import annotations

import contextlib
import io
import math
import os
import random
import statistics
import sys

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
    _downwind_edge_blocked,
    apply_scenario_config,
    resolve_victim_searcher_uav_ids,
)
from wildfire_model import WildFireModel

PY = sys.executable
SEEDS = [101, 202, 303, 404, 505]
STEPS = 240
GRID = 50
OBS = float(UAV_OBSERVATION_RADIUS)
OUT_PATH = os.path.join(_ROOT, "outputs", "fix7_part1.txt")

lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg, flush=True)
    lines.append(msg)


def _params(scenario: str, wind: str, *, ft=None, vs=None) -> dict:
    preset = BUILTIN_SCENARIOS[scenario]
    p = {
        "NUM_AGENTS": int(preset.get("NUM_AGENTS", 3)),
        "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
        "WIND_DIRECTION": str(wind),
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
    }
    if ft is not None:
        p["NUM_AGENTS"] = int(ft) + int(vs)
        p["NUM_FIRE_TRACKERS"] = int(ft)
        p["NUM_VICTIM_SEARCHERS"] = int(vs)
    return p


def _make_model(seed: int, params: dict) -> WildFireModel:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
    return model


def _uav_agents(model: WildFireModel):
    return [a for a in model.schedule.agents if type(a) is am.UAV]


def _pos(agent) -> tuple[int, int] | None:
    p = getattr(agent, "pos", None)
    if p is None:
        return None
    return int(p[0]), int(p[1])


def _victim_spawns(model: WildFireModel) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for vid, marker in (getattr(model, "victim_marker_agents", {}) or {}).items():
        p = _pos(marker)
        if p is not None:
            out[str(vid)] = p
    return dict(sorted(out.items()))


def _nd_ids(evaluation: dict) -> set[str]:
    raw = str(evaluation.get("unreachable_causes") or "")
    ids = set()
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        vid, _, cause = part.partition(":")
        if cause.strip() == "never_detected":
            ids.add(vid.strip())
    return ids


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


def _active_fire_cells(model: WildFireModel) -> set[tuple[int, int]]:
    cells = set()
    for a in model.schedule.agents:
        if type(a).__name__ != "Fire":
            continue
        if not getattr(a, "is_burning", lambda: False)():
            continue
        p = _pos(a)
        if p is not None:
            cells.add(p)
    return cells


def run_instrumented(
    seed: int,
    params: dict,
    *,
    coverage: bool = False,
    targets: bool = False,
    fire_blocked_wind: str | None = None,
    blocked_cells: set[tuple[int, int]] | None = None,
) -> dict:
    model = _make_model(seed, params)
    spawns = _victim_spawns(model)
    searcher_ids = resolve_victim_searcher_uav_ids(model)
    covered: set[tuple[int, int]] = set()
    xs: list[int] = []
    ys: list[int] = []
    min_searcher: dict[str, float] = {vid: float("inf") for vid in spawns}
    min_any: dict[str, float] = {vid: float("inf") for vid in spawns}
    ever_in_searcher_obs: dict[str, bool] = {vid: False for vid in spawns}
    target_log: list[tuple[int, dict[str, tuple[float, float] | None]]] = []
    fire_blocked_samples: list[tuple[int, int, int]] = []
    with contextlib.redirect_stdout(io.StringIO()):
        for step in range(1, STEPS + 1):
            model.step()
            uavs = {str(a.unique_id): a for a in _uav_agents(model)}
            searchers = []
            for uid in searcher_ids:
                agent = uavs.get(uid)
                if agent is None:
                    continue
                p = _pos(agent)
                if p is None:
                    continue
                searchers.append((uid, p))
                xs.append(p[0])
                ys.append(p[1])
                if coverage:
                    _mark_obs(covered, p[0], p[1], OBS)
            for vid, (vx, vy) in spawns.items():
                for _, (sx, sy) in searchers:
                    d = math.hypot(sx - vx, sy - vy)
                    if d < min_searcher[vid]:
                        min_searcher[vid] = d
                    if d <= OBS:
                        ever_in_searcher_obs[vid] = True
                for agent in uavs.values():
                    p = _pos(agent)
                    if p is None:
                        continue
                    d = math.hypot(p[0] - vx, p[1] - vy)
                    if d < min_any[vid]:
                        min_any[vid] = d
            if targets:
                store = getattr(model, "_wind_search_target_state", {}) or {}
                step_targets: dict[str, tuple[float, float] | None] = {}
                for uid in searcher_ids:
                    st = store.get(str(uid)) or {}
                    t = st.get("current_target")
                    if isinstance(t, (list, tuple)) and len(t) >= 2:
                        step_targets[uid] = (float(t[0]), float(t[1]))
                    else:
                        step_targets[uid] = None
                target_log.append((step, step_targets))
            if fire_blocked_wind and blocked_cells and step in (1, 60, 120, 180, 240):
                fire = _active_fire_cells(model)
                n_blocked_fire = len(blocked_cells & fire)
                fire_blocked_samples.append((step, n_blocked_fire, len(fire)))
    ev = _build_evaluation(model, None, STEPS, params)
    ev["seed"] = seed
    return {
        "eval": ev,
        "spawns": spawns,
        "searcher_ids": searcher_ids,
        "covered": covered,
        "xs": xs,
        "ys": ys,
        "min_searcher": min_searcher,
        "min_any": min_any,
        "ever_in_searcher_obs": ever_in_searcher_obs,
        "target_log": target_log,
        "fire_blocked_samples": fire_blocked_samples,
        "nd": _nd_ids(ev),
    }


def q3_blocked() -> dict[str, set[tuple[int, int]]]:
    x_min, x_max, y_min, y_max = 0, GRID - 1, 0, GRID - 1
    by_wind: dict[str, set[tuple[int, int]]] = {}
    log("Q3  _downwind_edge_blocked cells on grid 0..49 x 0..49")
    for wind in ("north", "south", "east", "west"):
        cells = set()
        xs, ys = set(), set()
        for cx in range(x_min, x_max + 1):
            for cy in range(y_min, y_max + 1):
                if _downwind_edge_blocked(wind, cx, cy, x_min, x_max, y_min, y_max):
                    cells.add((cx, cy))
                    xs.add(cx)
                    ys.add(cy)
        by_wind[wind] = cells
        if wind in ("west", "east"):
            band = "x in [%d, %d] (all y)" % (min(xs), max(xs)) if xs else "none"
        else:
            band = "y in [%d, %d] (all x)" % (min(ys), max(ys)) if ys else "none"
        log(
            "  wind=%-5s  n_cells=%d  band=%s  x_set=%s  y_set=%s"
            % (
                wind,
                len(cells),
                band,
                sorted(xs) if len(xs) <= 12 else "%s..." % sorted(xs)[:8],
                sorted(ys) if len(ys) <= 12 else "%s..." % sorted(ys)[:8],
            )
        )
    log(
        "  west blocks cx <= x_min+3 => x=0..3 (4 columns, %d cells)"
        % len(by_wind["west"])
    )
    log(
        "  east blocks cx >= x_max-4 => x=45..49 (5 columns, %d cells)"
        % len(by_wind["east"])
    )
    log(
        "  north blocks cy >= y_max-3 => y=46..49 (4 rows, %d cells)"
        % len(by_wind["north"])
    )
    log(
        "  south blocks cy <= y_min+2 => y=0..2 (3 rows, %d cells)"
        % len(by_wind["south"])
    )
    return by_wind


def _coverage_stats(result: dict, label: str) -> None:
    xs = result["xs"]
    ys = result["ys"]
    covered = result["covered"]
    n = GRID * GRID
    log("  [%s]" % label)
    log("    searcher_ids=%s" % result["searcher_ids"])
    if xs:
        log(
            "    trajectory x: min=%d median=%.1f max=%d"
            % (min(xs), statistics.median(xs), max(xs))
        )
        log(
            "    trajectory y: min=%d median=%.1f max=%d"
            % (min(ys), statistics.median(ys), max(ys))
        )
        frac_lo = sum(1 for x in xs if x <= 12) / len(xs)
        frac_hi = sum(1 for x in xs if x >= 30) / len(xs)
        log(
            "    fraction steps x<=12: %.3f   x>=30: %.3f  (n_pos=%d)"
            % (frac_lo, frac_hi, len(xs))
        )
    if covered:
        cxs = [c[0] for c in covered]
        cys = [c[1] for c in covered]
        log(
            "    observed cells: %d / %d = %.3f"
            % (len(covered), n, len(covered) / n)
        )
        log("    covered x-range: [%d, %d]" % (min(cxs), max(cxs)))
        log("    covered y-range: [%d, %d]" % (min(cys), max(cys)))
        west_band = sum(1 for x, y in covered if x <= 3)
        east_band = sum(1 for x, y in covered if x >= 30)
        log(
            "    observed cells with x<=3: %d   x>=30: %d"
            % (west_band, east_band)
        )
    else:
        log("    no coverage recorded")


def _q5_stats(result: dict) -> None:
    log_items = result["target_log"]
    ids = result["searcher_ids"]
    if len(ids) < 2:
        log("  fewer than 2 searchers: %s" % ids)
        return
    a, b = ids[0], ids[1]
    n = 0
    n_both = 0
    n_ident = 0
    n_near = 0
    n_none = 0
    for _step, tmap in log_items:
        n += 1
        ta, tb = tmap.get(a), tmap.get(b)
        if ta is None or tb is None:
            n_none += 1
            continue
        n_both += 1
        dx = abs(ta[0] - tb[0])
        dy = abs(ta[1] - tb[1])
        if dx < 1e-9 and dy < 1e-9:
            n_ident += 1
        if max(dx, dy) <= 2.0:
            n_near += 1
    log("  searchers=%s steps=%d" % (ids, n))
    log("  both-have-target=%d  one-or-both-None=%d" % (n_both, n_none))
    if n_both:
        log(
            "  identical: %d / %d = %.3f"
            % (n_ident, n_both, n_ident / n_both)
        )
        log(
            "  chebyshev<=2: %d / %d = %.3f"
            % (n_near, n_both, n_near / n_both)
        )
        log(
            "  identical-or-near of all steps: ident %.3f  near %.3f"
            % (n_ident / n, n_near / n)
        )


def main() -> None:
    log("Python %s" % sys.version.replace("\n", " "))
    log("mesa %s" % __import__("mesa").__version__)
    log("UAV_OBSERVATION_RADIUS=%s" % OBS)
    log("")

    blocked = q3_blocked()
    log("")

    log("Q1  victim spawn coordinates at t=0 (all 5 seeds) + fix6 never_detected marks")
    FIX6_ND = {
        ("A", 101): set(),
        ("A", 202): set(),
        ("A", 303): {"victim_0", "victim_1"},
        ("A", 404): {"victim_0", "victim_4"},
        ("A", 505): {"victim_0", "victim_1", "victim_4"},
        ("D", 101): set(),
        ("D", 202): set(),
        ("D", 303): {"victim_0", "victim_1"},
        ("D", 404): {"victim_3"},
        ("D", 505): {"victim_0"},
    }
    spawns_by: dict[tuple[str, int], dict[str, tuple[int, int]]] = {}
    for scenario in ("A", "D"):
        params = _params(scenario, "west")
        for seed in SEEDS:
            model = _make_model(seed, params)
            spawns = _victim_spawns(model)
            spawns_by[(scenario, seed)] = spawns
            nd = FIX6_ND[(scenario, seed)]
            log("  %s/west seed=%d (t=0)" % (scenario, seed))
            for vid, pos in spawns.items():
                mark = " NEVER_DETECTED(fix6)" if vid in nd else ""
                log("    %s spawn=(%d,%d)%s" % (vid, pos[0], pos[1], mark))
            del model
    log("")

    log("Q2  searcher observation coverage  A/west 505 vs A/east 505")
    log("  running A/west seed=505 coverage ...")
    coverage_west = run_instrumented(
        505,
        _params("A", "west"),
        coverage=True,
        fire_blocked_wind="west",
        blocked_cells=blocked["west"],
    )
    log(
        "    eval rescued=%s dead=%s nd=%s causes=%s"
        % (
            coverage_west["eval"]["rescued"],
            coverage_west["eval"]["dead"],
            coverage_west["eval"]["never_detected"],
            coverage_west["eval"].get("unreachable_causes"),
        )
    )
    _coverage_stats(coverage_west, "A/west seed=505")
    log("  running A/east seed=505 coverage ...")
    coverage_east = run_instrumented(
        505, _params("A", "east"), coverage=True
    )
    _coverage_stats(coverage_east, "A/east seed=505")
    log(
        "    A/east 505 eval rescued=%s never_detected=%s causes=%s"
        % (
            coverage_east["eval"]["rescued"],
            coverage_east["eval"]["never_detected"],
            coverage_east["eval"].get("unreachable_causes"),
        )
    )
    log("")

    if coverage_west and coverage_west.get("fire_blocked_samples"):
        log("Q3b fire cells inside west blocked band during A/west 505:")
        for step, n_bf, n_fire in coverage_west["fire_blocked_samples"]:
            log(
                "  step=%d  blocked_on_fire=%d  total_burning=%d  blocked_band_size=%d"
                % (step, n_bf, n_fire, len(blocked["west"]))
            )
        log("")

    log("Q4  cross-ref never_detected vs blocked vs uncovered")
    west_blocked = blocked["west"]
    covered_w = coverage_west["covered"]
    log("  A/west 505 (live) all victims:")
    for vid, pos in coverage_west["spawns"].items():
        log(
            "    %s pos=%s nd=%s in_blocked=%s in_covered=%s ever_r8=%s "
            "min_s=%.2f min_any=%.2f"
            % (
                vid,
                pos,
                vid in coverage_west["nd"],
                pos in west_blocked,
                pos in covered_w,
                coverage_west["ever_in_searcher_obs"][vid],
                coverage_west["min_searcher"][vid],
                coverage_west["min_any"][vid],
            )
        )
    log("  running D/west seed=505 (obs distances) ...")
    d_west = run_instrumented(505, _params("D", "west"), coverage=False)
    log(
        "    eval rescued=%s nd=%s causes=%s"
        % (
            d_west["eval"]["rescued"],
            d_west["eval"]["never_detected"],
            d_west["eval"].get("unreachable_causes"),
        )
    )
    for vid, pos in d_west["spawns"].items():
        log(
            "    %s pos=%s nd=%s in_blocked=%s ever_r8=%s min_s=%.2f min_any=%.2f"
            % (
                vid,
                pos,
                vid in d_west["nd"],
                pos in west_blocked,
                d_west["ever_in_searcher_obs"][vid],
                d_west["min_searcher"][vid],
                d_west["min_any"][vid],
            )
        )
    log("  other fix6 ND victims vs blocked band (spawn only):")
    for scenario in ("A", "D"):
        for seed in SEEDS:
            nd = FIX6_ND[(scenario, seed)]
            if not nd or (scenario, seed) in (("A", 505), ("D", 505)):
                continue
            log("  %s/west seed=%d" % (scenario, seed))
            for vid in sorted(nd):
                pos = spawns_by[(scenario, seed)][vid]
                log("    %s pos=%s in_west_blocked=%s" % (vid, pos, pos in west_blocked))
    log("")

    log("Q5  two-searcher target identity  D west  2 trackers + 2 searchers")
    ident_fracs = []
    near_fracs = []
    for seed in (505, 303):
        log("  running D/west ms seed=%d ..." % seed)
        res = run_instrumented(
            seed,
            _params("D", "west", ft=2, vs=2),
            targets=True,
        )
        log(
            "    eval never_detected=%s causes=%s"
            % (res["eval"]["never_detected"], res["eval"].get("unreachable_causes"))
        )
        _q5_stats(res)
        ids = res["searcher_ids"]
        if len(ids) >= 2:
            a, b = ids[0], ids[1]
            n_both = ident = near = 0
            for _s, tmap in res["target_log"]:
                ta, tb = tmap.get(a), tmap.get(b)
                if ta is None or tb is None:
                    continue
                n_both += 1
                dx = abs(ta[0] - tb[0])
                dy = abs(ta[1] - tb[1])
                if dx < 1e-9 and dy < 1e-9:
                    ident += 1
                if max(dx, dy) <= 2.0:
                    near += 1
            if n_both:
                ident_fracs.append(ident / n_both)
                near_fracs.append(near / n_both)
    if ident_fracs:
        log(
            "  MEAN identical fraction=%.3f  chebyshev<=2 fraction=%.3f  (over %d seeds)"
            % (
                statistics.mean(ident_fracs),
                statistics.mean(near_fracs),
                len(ident_fracs),
            )
        )
    log("")
    log("DONE")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
