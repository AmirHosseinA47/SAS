"""Part 1 diagnostics for y-axis never_detected (read-only; no production edits)."""
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
    COVERAGE_SWEEP_BAND_MARGIN,
    COVERAGE_Y_COMMIT_PENETRATE_MARGIN,
    COVERAGE_Y_COMMIT_TARGET_MARGIN,
    WIND_INTERIOR_MARGIN,
    _allow_east_force,
    _coverage_safe_x_max,
    _coverage_safe_x_min,
    _coverage_safe_y_max,
    _coverage_safe_y_min,
    _downwind_edge_blocked,
    apply_scenario_config,
    resolve_victim_searcher_uav_ids,
)
from wildfire_model import WildFireModel

SEEDS = [101, 202, 303, 404, 505]
STEPS = 240
GRID = 50
OBS = float(UAV_OBSERVATION_RADIUS)
OUT_PATH = os.path.join(_ROOT, "outputs", "fix9_part1.txt")

lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg, flush=True)
    lines.append(msg)


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


def q2_blocked() -> dict[str, set[tuple[int, int]]]:
    x_min, x_max, y_min, y_max = 0, GRID - 1, 0, GRID - 1
    by_wind: dict[str, set[tuple[int, int]]] = {}
    log("Q2  static y-axis constraints (code + blocked bands)")
    log("  _allow_east_force(west)=%s  _allow_east_force(north)=%s  _allow_east_force(south)=%s  _allow_east_force(east)=%s"
        % (
            _allow_east_force({"last_wind_direction": "west"}),
            _allow_east_force({"last_wind_direction": "north"}),
            _allow_east_force({"last_wind_direction": "south"}),
            _allow_east_force({"last_wind_direction": "east"}),
        ))
    log("  WIND_INTERIOR_MARGIN=%d  COVERAGE_SWEEP_BAND_MARGIN=%d" % (
        WIND_INTERIOR_MARGIN, COVERAGE_SWEEP_BAND_MARGIN,
    ))
    log("  COVERAGE_Y_COMMIT_TARGET_MARGIN=%d  COVERAGE_Y_COMMIT_PENETRATE_MARGIN=%d" % (
        COVERAGE_Y_COMMIT_TARGET_MARGIN, COVERAGE_Y_COMMIT_PENETRATE_MARGIN,
    ))
    safe_y_min = _coverage_safe_y_min(y_min)
    safe_y_max = _coverage_safe_y_max(y_max)
    south_reached = safe_y_min + COVERAGE_SWEEP_BAND_MARGIN + 4
    north_reached = safe_y_max - COVERAGE_SWEEP_BAND_MARGIN - 4
    south_goal = safe_y_min + COVERAGE_SWEEP_BAND_MARGIN
    north_goal = safe_y_max - COVERAGE_SWEEP_BAND_MARGIN
    log("  safe_y_min=%d safe_y_max=%d" % (safe_y_min, safe_y_max))
    log("  analogue south_strip_reached if y_lo<=%d  north_strip_reached if y_hi>=%d" % (
        south_reached, north_reached,
    ))
    log("  analogue south_goal=%d  north_goal=%d" % (south_goal, north_goal))
    log("  y-commit north target y=%d  south target y=%d" % (
        y_max - COVERAGE_Y_COMMIT_TARGET_MARGIN,
        y_min + COVERAGE_Y_COMMIT_TARGET_MARGIN,
    ))
    log("  y-commit north penetrate ay>=%d  south penetrate ay<=%d" % (
        y_max - COVERAGE_Y_COMMIT_PENETRATE_MARGIN,
        y_min + COVERAGE_Y_COMMIT_PENETRATE_MARGIN,
    ))
    log("  interior-edge y: cy<=%d or cy>=%d (margin=%d)" % (
        y_min + WIND_INTERIOR_MARGIN, y_max - WIND_INTERIOR_MARGIN, WIND_INTERIOR_MARGIN,
    ))
    log("  _downwind_edge_blocked cells on grid 0..49 x 0..49")
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
            "  wind=%-5s  n_cells=%d  band=%s"
            % (wind, len(cells), band)
        )
    log("  north blocks cy >= y_max-3 => y=46..49")
    log("  south blocks cy <= y_min+2 => y=0..2")
    log("  east  blocks cx >= x_max-4 => x=45..49")
    log("  west  blocks cx <= x_min+3 => x=0..3")
    log("  CODE QUOTES:")
    log("    _score_hybrid_search_cell downwind: score = capped_downwind * 3.0 * wind_w  (lines 991-992)")
    log("    _finalize_coverage_target: west-only x strip latch + _allow_east_force; y only via coverage_y_commit (829-902)")
    log("    _allow_east_force: return w == 'west'  (182-185)  -- NO y analogue")
    log("    no north_strip_done / south_strip_done in _default_wind_search_state (only west_strip_done, east_strip_done)")
    log("    _downwind_edge_blocked north cy>=y_max-3; south cy<=y_min+2  (1243-1255)")
    log("    _cell_on_edge margin=WIND_INTERIOR_MARGIN=6: cy<=6 or cy>=43  (455-469, 1005)")
    log("    _coverage_y_commit_target_y north=y_max-4=45 south=y_min+4=4  (804-812)")
    log("    corridor/escape DROP cy < y_force_min or cy > y_force_max  (3196-3199, 3366-3369)")
    log("    _coverage_y_commit_penetrated north ay>=y_max-6=43 south ay<=y_min+6=6  (770-781)")
    log("    UNOccupiable trap candidate: north commit wants cy>=45 AND north wind blocks cy>=46")
    log("      AND interior treats cy>=43 as edge. Corridor stride-3 y=47 is blocked.")
    log("    south commit wants cy<=4 AND south wind blocks cy<=2 AND interior cy<=6 is edge.")
    return by_wind


def run_instrumented(
    seed: int,
    params: dict,
    *,
    coverage: bool = False,
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
    ever_in_any_obs: dict[str, bool] = {vid: False for vid in spawns}
    fire_blocked_samples: list[tuple[int, int, int]] = []
    commit_hist: list[str | None] = []
    target_ys: list[float] = []
    n_target_none = 0
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
            store = getattr(model, "_wind_search_target_state", {}) or {}
            step_commit = None
            for uid in searcher_ids:
                st = store.get(str(uid)) or {}
                c = st.get("coverage_y_commit")
                if c in ("north", "south"):
                    step_commit = str(c)
                t = st.get("current_target")
                if isinstance(t, (list, tuple)) and len(t) >= 2:
                    target_ys.append(float(t[1]))
                else:
                    n_target_none += 1
            commit_hist.append(step_commit)
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
                    if d <= OBS:
                        ever_in_any_obs[vid] = True
            if fire_blocked_wind and blocked_cells and step in (1, 60, 120, 180, 240):
                fire = _active_fire_cells(model)
                n_blocked_fire = len(blocked_cells & fire)
                fire_blocked_samples.append((step, n_blocked_fire, len(fire)))
    ev = _build_evaluation(model, None, STEPS, params)
    ev["seed"] = seed
    n_north = sum(1 for c in commit_hist if c == "north")
    n_south = sum(1 for c in commit_hist if c == "south")
    n_none = sum(1 for c in commit_hist if c is None)
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
        "ever_in_any_obs": ever_in_any_obs,
        "fire_blocked_samples": fire_blocked_samples,
        "nd": _nd_ids(ev),
        "commit_north_steps": n_north,
        "commit_south_steps": n_south,
        "commit_none_steps": n_none,
        "n_target_none": n_target_none,
        "target_ys": target_ys,
    }


def _coverage_stats(result: dict, label: str) -> None:
    xs = result["xs"]
    ys = result["ys"]
    covered = result["covered"]
    n = GRID * GRID
    log("  [%s]" % label)
    log("    searcher_ids=%s" % result["searcher_ids"])
    log(
        "    eval rescued=%s dead=%s nd=%s causes=%s all_terminal=%s"
        % (
            result["eval"].get("rescued"),
            result["eval"].get("dead"),
            result["eval"].get("never_detected"),
            result["eval"].get("unreachable_causes"),
            result["eval"].get("all_terminal"),
        )
    )
    if xs:
        log(
            "    trajectory x: min=%d median=%.1f max=%d"
            % (min(xs), statistics.median(xs), max(xs))
        )
        log(
            "    trajectory y: min=%d median=%.1f max=%d"
            % (min(ys), statistics.median(ys), max(ys))
        )
        frac_ylo = sum(1 for y in ys if y <= 12) / len(ys)
        frac_yhi = sum(1 for y in ys if y >= 38) / len(ys)
        frac_xlo = sum(1 for x in xs if x <= 12) / len(xs)
        frac_xhi = sum(1 for x in xs if x >= 30) / len(xs)
        log(
            "    fraction steps y<=12: %.3f   y>=38: %.3f  (n_pos=%d)"
            % (frac_ylo, frac_yhi, len(ys))
        )
        log(
            "    fraction steps x<=12: %.3f   x>=30: %.3f"
            % (frac_xlo, frac_xhi)
        )
        log(
            "    occupy reachable south y<=12: %d  north y>=37: %d"
            % (sum(1 for y in ys if y <= 12), sum(1 for y in ys if y >= 37))
        )
        log(
            "    occupy blocked south y<=2: %d  north y>=46: %d"
            % (sum(1 for y in ys if y <= 2), sum(1 for y in ys if y >= 46))
        )
        log(
            "    occupy interior-edge south y<=6: %d  north y>=43: %d"
            % (sum(1 for y in ys if y <= 6), sum(1 for y in ys if y >= 43))
        )
    log(
        "    coverage_y_commit steps: north=%d south=%d none=%d  target_none=%d"
        % (
            result["commit_north_steps"],
            result["commit_south_steps"],
            result["commit_none_steps"],
            result["n_target_none"],
        )
    )
    tys = result.get("target_ys") or []
    if tys:
        log(
            "    target y: min=%.1f median=%.1f max=%.1f  n=%d"
            % (min(tys), statistics.median(tys), max(tys), len(tys))
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
        log(
            "    observed cells with y<=3: %d   y>=46: %d   y<=11: %d"
            % (
                sum(1 for _, y in covered if y <= 3),
                sum(1 for _, y in covered if y >= 46),
                sum(1 for _, y in covered if y <= 11),
            )
        )
    else:
        log("    no coverage recorded")


def _victim_line(result: dict, vid: str, blocked: set[tuple[int, int]] | None) -> None:
    pos = result["spawns"].get(vid)
    if pos is None:
        log("    %s MISSING from spawns" % vid)
        return
    in_blocked = pos in blocked if blocked is not None else None
    in_covered = pos in result["covered"] if result["covered"] else None
    log(
        "    %s pos=%s nd=%s in_blocked=%s in_covered=%s ever_searcher_r8=%s ever_any_r8=%s "
        "min_s=%.2f min_any=%.2f"
        % (
            vid,
            pos,
            vid in result["nd"],
            in_blocked,
            in_covered,
            result["ever_in_searcher_obs"][vid],
            result["ever_in_any_obs"][vid],
            result["min_searcher"][vid],
            result["min_any"][vid],
        )
    )


def main() -> None:
    log("Python %s" % sys.version.replace("\n", " "))
    log("mesa %s" % __import__("mesa").__version__)
    log("UAV_OBSERVATION_RADIUS=%s" % OBS)
    log("")

    blocked = q2_blocked()
    log("")

    log("Q1  coverage extent  D/north 101  D/south 101  vs A/west 505")
    log("  running D/north seed=101 coverage ...")
    d_north = run_instrumented(
        101,
        _params("D", "north"),
        coverage=True,
        fire_blocked_wind="north",
        blocked_cells=blocked["north"],
    )
    _coverage_stats(d_north, "D/north seed=101")
    if d_north.get("fire_blocked_samples"):
        log("    fire in north blocked band:")
        for step, n_bf, n_fire in d_north["fire_blocked_samples"]:
            log(
                "      step=%d  blocked_on_fire=%d  total_burning=%d  blocked_band_size=%d"
                % (step, n_bf, n_fire, len(blocked["north"]))
            )
    log("  running D/south seed=101 coverage ...")
    d_south = run_instrumented(
        101,
        _params("D", "south"),
        coverage=True,
        fire_blocked_wind="south",
        blocked_cells=blocked["south"],
    )
    _coverage_stats(d_south, "D/south seed=101")
    if d_south.get("fire_blocked_samples"):
        log("    fire in south blocked band:")
        for step, n_bf, n_fire in d_south["fire_blocked_samples"]:
            log(
                "      step=%d  blocked_on_fire=%d  total_burning=%d  blocked_band_size=%d"
                % (step, n_bf, n_fire, len(blocked["south"]))
            )
    log("  running A/west seed=505 coverage ...")
    a_west = run_instrumented(
        505,
        _params("A", "west"),
        coverage=True,
        fire_blocked_wind="west",
        blocked_cells=blocked["west"],
    )
    _coverage_stats(a_west, "A/west seed=505")
    log("")

    log("Q2b  live occupancy vs reachable/blocked/unoccupiable release")
    log("  D/north 101: downwind=+y; miss expected at low y (25,3)")
    log("    if y-commit south fires, target y=4; penetrate ay<=6; blocked y<=2 is SOUTH wind only")
    log("    north commit target y=45 vs blocked y>=46 vs interior y>=43")
    log("  D/south 101: downwind=-y; miss expected at high y (25,48)")
    log("")

    log("Q3  D/east 202 and D/west 404 miss v3 (25,3)")
    log("  running D/east seed=202 coverage ...")
    d_east = run_instrumented(202, _params("D", "east"), coverage=True)
    _coverage_stats(d_east, "D/east seed=202")
    _victim_line(d_east, "victim_3", blocked["east"])
    log("  running D/west seed=404 coverage ...")
    d_west = run_instrumented(404, _params("D", "west"), coverage=True)
    _coverage_stats(d_west, "D/west seed=404")
    _victim_line(d_west, "victim_3", blocked["west"])
    log("")

    log("Q4  A/north 101 and B/north 101 v0 (40,25) — mid-y high-x")
    log("  running A/north seed=101 coverage ...")
    a_north = run_instrumented(101, _params("A", "north"), coverage=True)
    _coverage_stats(a_north, "A/north seed=101")
    _victim_line(a_north, "victim_0", blocked["north"])
    log("  running B/north seed=101 coverage ...")
    b_north = run_instrumented(101, _params("B", "north"), coverage=True)
    _coverage_stats(b_north, "B/north seed=101")
    _victim_line(b_north, "victim_0", blocked["north"])
    log("")

    log("Q5  all 10 never_detected victims vs observation / blocked band")
    cases = [
        ("D", "north", 101, "victim_3", blocked["north"]),
        ("D", "north", 404, "victim_3", blocked["north"]),
        ("D", "north", 505, "victim_3", blocked["north"]),
        ("D", "south", 101, "victim_1", blocked["south"]),
        ("A", "south", 303, "victim_1", blocked["south"]),
        ("D", "east", 202, "victim_3", blocked["east"]),
        ("D", "west", 404, "victim_3", blocked["west"]),
        ("C", "west", 303, "victim_1", blocked["west"]),
        ("A", "north", 101, "victim_0", blocked["north"]),
        ("B", "north", 101, "victim_0", blocked["north"]),
    ]
    already = {
        ("D", "north", 101): d_north,
        ("D", "south", 101): d_south,
        ("D", "east", 202): d_east,
        ("D", "west", 404): d_west,
        ("A", "north", 101): a_north,
        ("B", "north", 101): b_north,
    }
    for scenario, wind, seed, vid, band in cases:
        key = (scenario, wind, seed)
        if key in already:
            res = already[key]
            log("  %s/%s seed=%d (reuse)" % (scenario, wind, seed))
        else:
            log("  running %s/%s seed=%d ..." % (scenario, wind, seed))
            res = run_instrumented(seed, _params(scenario, wind), coverage=True)
            already[key] = res
            log(
                "    eval nd=%s causes=%s"
                % (res["eval"].get("never_detected"), res["eval"].get("unreachable_causes"))
            )
        _victim_line(res, vid, band)
        if res["covered"] and vid in res["spawns"]:
            vx, vy = res["spawns"][vid]
            near = sum(
                1
                for cx, cy in res["covered"]
                if abs(cx - vx) <= 2 and abs(cy - vy) <= 2
            )
            log("    nearby covered cells (chebyshev<=2 of spawn): %d" % near)
    log("")

    log("DECISION GATE")
    y_extreme = [
        ("D", "north", 101, "victim_3"),
        ("D", "north", 404, "victim_3"),
        ("D", "north", 505, "victim_3"),
        ("D", "south", 101, "victim_1"),
        ("A", "south", 303, "victim_1"),
        ("D", "east", 202, "victim_3"),
        ("D", "west", 404, "victim_3"),
        ("C", "west", 303, "victim_1"),
    ]
    n_unobs = 0
    n_obs_but_nd = 0
    for scenario, wind, seed, vid in y_extreme:
        res = already[(scenario, wind, seed)]
        obs = bool(res["ever_in_searcher_obs"].get(vid) or res["ever_in_any_obs"].get(vid))
        nd = vid in res["nd"]
        if nd and not obs:
            n_unobs += 1
        if nd and obs:
            n_obs_but_nd += 1
        log(
            "  %s/%s %d %s nd=%s ever_any_r8=%s min_s=%.2f min_any=%.2f y=%s"
            % (
                scenario, wind, seed, vid, nd,
                res["ever_in_any_obs"].get(vid),
                res["min_searcher"].get(vid, float("nan")),
                res["min_any"].get(vid, float("nan")),
                res["spawns"].get(vid),
            )
        )
    log("  y-extreme never-observed (coverage gap): %d" % n_unobs)
    log("  y-extreme observed-but-nd (NOT coverage): %d" % n_obs_but_nd)
    for scenario, wind, seed, vid in (("A", "north", 101, "victim_0"), ("B", "north", 101, "victim_0")):
        res = already[(scenario, wind, seed)]
        xs = res["xs"]
        log(
            "  %s/%s %d %s x traj min/med/max=%s/%s/%s min_s=%.2f ever_r8=%s"
            % (
                scenario, wind, seed, vid,
                min(xs) if xs else None,
                statistics.median(xs) if xs else None,
                max(xs) if xs else None,
                res["min_searcher"].get(vid, float("nan")),
                res["ever_in_any_obs"].get(vid),
            )
        )
    log("DONE")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
