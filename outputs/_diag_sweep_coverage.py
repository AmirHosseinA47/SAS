"""Part 1 diagnostics for systematic sweep coverage (read-only; no production edits)."""
from __future__ import annotations

import contextlib
import io
import math
import os
import random
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)
os.environ.setdefault("MPLBACKEND", "Agg")

import agents as am
import common_fixed_variables as cfv
import mesa
import wildfire_model as wf
from common_fixed_variables import UAV_OBSERVATION_RADIUS
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation
from src_extension.adaptation.local_adaptation_generator import (
    WIND_FIRE_FRONT_MIN_DISTANCE,
    _downwind_edge_blocked,
    apply_scenario_config,
    resolve_victim_searcher_uav_ids,
)
from wildfire_model import WildFireModel

PY = sys.executable
STEPS = 240
GRID = 50
OBS = float(UAV_OBSERVATION_RADIUS)
TIMEOUT = 210
FRONT_MIN = int(WIND_FIRE_FRONT_MIN_DISTANCE)
TRACKS = (8, 25, 42)
OUT_PATH = os.path.join(_ROOT, "outputs", "fix10_part1.txt")

ND_CASES = (
    ("D", "north", "victim_3", (25, 3)),
    ("D", "south", "victim_1", (25, 48)),
    ("A", "south", "victim_1", (32, 46)),
    ("D", "east", "victim_3", (25, 3)),
    ("D", "west", "victim_3", (25, 3)),
    ("C", "west", "victim_1", (14, 44)),
    ("A", "north", "victim_0", (40, 25)),
    ("B", "north", "victim_0", (40, 25)),
)

lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg, flush=True)
    lines.append(msg)


def _params(scenario: str, wind: str, *, ft=None, vs=None) -> dict:
    preset = BUILTIN_SCENARIOS[scenario]
    n_agents = int(preset.get("NUM_AGENTS", 3))
    p = {
        "NUM_AGENTS": n_agents,
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


def spawn_coords(n: int) -> dict[str, tuple[int, int]]:
    positions: dict[str, tuple[int, int]] = {}
    for i in range(n):
        angle = (2 * math.pi * i) / max(n, 1)
        r_x = 0.3 + 0.15 * (i % 2)
        r_y = 0.3 + 0.15 * (i % 2)
        vx = max(1.0, min(float(GRID) - 1, float(GRID) * (0.5 + r_x * math.cos(angle))))
        vy = max(1.0, min(float(GRID) - 1, float(GRID) * (0.5 + r_y * math.sin(angle))))
        positions["victim_%d" % i] = (int(round(vx)), int(round(vy)))
    return positions


def manhattan_connect(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    ax, ay = a
    bx, by = b
    cells = [(ax, ay)]
    x, y = ax, ay
    while x != bx:
        x += 1 if bx > x else -1
        cells.append((x, y))
    while y != by:
        y += 1 if by > y else -1
        cells.append((x, y))
    return cells


def boustrophedon_path(
    track_xs: list[int],
    *,
    y0: int = 0,
    y1: int = 49,
    first_north: bool = True,
) -> list[tuple[int, int]]:
    path: list[tuple[int, int]] = []
    north = first_north
    for x in track_xs:
        start = (int(x), int(y0 if north else y1))
        end = (int(x), int(y1 if north else y0))
        if not path:
            path.extend(manhattan_connect(start, end))
        else:
            conn = manhattan_connect(path[-1], start)
            path.extend(conn[1:])
            rest = manhattan_connect(start, end)
            path.extend(rest[1:])
        north = not north
    return path


def tracks_for_band(lo: int, hi: int, radius: int = 8) -> list[int]:
    spacing = 2 * radius + 1
    if hi < lo:
        lo, hi = hi, lo
    xs: list[int] = []
    x = lo + radius
    if x > hi:
        return [(lo + hi) // 2]
    while True:
        xs.append(int(min(hi, max(lo, x))))
        if x + radius >= hi:
            break
        x += spacing
        if x > hi:
            last = hi - radius
            if last > xs[-1]:
                xs.append(int(max(lo, last)))
            elif hi not in xs and (hi - xs[-1]) > radius:
                xs.append(int(hi))
            break
    out: list[int] = []
    for v in xs:
        if not out or out[-1] != v:
            out.append(v)
    return out


def lane_bounds(n: int, idx: int, axis_min: int, axis_max: int) -> tuple[int, int]:
    span = axis_max - axis_min + 1
    lo = axis_min + (span * idx) // n
    hi = axis_min + (span * (idx + 1)) // n - 1
    if idx == n - 1:
        hi = axis_max
    return lo, hi


def mark_obs(covered: set[tuple[int, int]], px: int, py: int, radius: float = OBS) -> None:
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


def coverage_along_path(path: list[tuple[int, int]]) -> tuple[list[int], int | None]:
    covered: set[tuple[int, int]] = set()
    counts: list[int] = []
    full_at = None
    n = GRID * GRID
    for i, (px, py) in enumerate(path):
        mark_obs(covered, px, py)
        counts.append(len(covered))
        if full_at is None and len(covered) >= n:
            full_at = i
    return counts, full_at


def first_obs_step(path: list[tuple[int, int]], vx: float, vy: float) -> int | None:
    r2 = OBS * OBS
    for i, (px, py) in enumerate(path):
        dx = px - vx
        dy = py - vy
        if dx * dx + dy * dy <= r2:
            return i
    return None


def _active_fire_cells(model: WildFireModel) -> set[tuple[int, int]]:
    cells = set()
    for a in model.schedule.agents:
        if type(a).__name__ != "Fire":
            continue
        is_burning = getattr(a, "is_burning", None)
        burning = is_burning() if callable(is_burning) else bool(is_burning)
        if not burning:
            status = getattr(a, "burnt_status", None)
            status_val = getattr(status, "value", status) if status is not None else None
            if str(status_val or "").lower() not in ("burning", "on_fire", "fire"):
                continue
        p = _pos(a)
        if p is not None:
            cells.add(p)
    return cells


def _smoke_cells(model: WildFireModel) -> set[tuple[int, int]]:
    vis = getattr(model, "visibility_model", None)
    if vis is None:
        return set()
    raw = getattr(vis, "smoke_obscured_cells", None)
    if raw is None:
        state = getattr(vis, "state", None)
        if state is not None:
            raw = getattr(state, "smoke_obscured_cells", None)
    cells: set[tuple[int, int]] = set()
    if isinstance(raw, (set, frozenset, list, tuple)):
        for position in raw:
            if not isinstance(position, (list, tuple)) or len(position) < 2:
                continue
            try:
                cells.add((int(position[0]), int(position[1])))
            except (TypeError, ValueError):
                continue
    return cells


def min_manh(cell: tuple[int, int], hazards: set[tuple[int, int]]) -> int:
    if not hazards:
        return 10**9
    cx, cy = cell
    return min(abs(cx - hx) + abs(cy - hy) for hx, hy in hazards)


def cell_unsafe(
    cell: tuple[int, int],
    fire: set[tuple[int, int]],
    smoke: set[tuple[int, int]],
    wind: str,
    *,
    use_front: bool,
) -> bool:
    cx, cy = cell
    if cell in fire or cell in smoke:
        return True
    if _downwind_edge_blocked(wind, cx, cy, 0, GRID - 1, 0, GRID - 1):
        return True
    if use_front:
        hazards = fire | smoke
        if hazards and min_manh(cell, hazards) < FRONT_MIN:
            return True
    return False


def snapshot_hazards(model: WildFireModel) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    return _active_fire_cells(model), _smoke_cells(model)


def bfs_next_step(
    start: tuple[int, int],
    goal: tuple[int, int],
    fire: set[tuple[int, int]],
    smoke: set[tuple[int, int]],
    wind: str,
    *,
    use_front: bool,
) -> tuple[int, int] | None:
    if start == goal:
        return start
    from collections import deque

    q: deque[tuple[int, int]] = deque([start])
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    found = False
    while q:
        cur = q.popleft()
        if cur == goal:
            found = True
            break
        x, y = cur
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nx < 0 or ny < 0 or nx >= GRID or ny >= GRID:
                continue
            nxt = (nx, ny)
            if nxt in parent:
                continue
            if nxt != goal and cell_unsafe(nxt, fire, smoke, wind, use_front=use_front):
                continue
            parent[nxt] = cur
            q.append(nxt)
    if not found or goal not in parent:
        return None
    cell = goal
    while parent[cell] is not None and parent[cell] != start:
        cell = parent[cell]
    return cell


def path_block_stats(
    path: list[tuple[int, int]],
    fire: set[tuple[int, int]],
    smoke: set[tuple[int, int]],
    wind: str,
) -> dict:
    n = len(path)
    fire_or_smoke = fire | smoke
    n_fire_smoke_grid = len(fire_or_smoke)
    n_path_fire_smoke = sum(1 for c in path if c in fire_or_smoke)
    n_path_blocked_edge = sum(
        1 for c in path if _downwind_edge_blocked(wind, c[0], c[1], 0, GRID - 1, 0, GRID - 1)
    )
    n_path_front = sum(
        1 for c in path if fire_or_smoke and min_manh(c, fire_or_smoke) < FRONT_MIN
    )
    n_path_unsafe = sum(1 for c in path if cell_unsafe(c, fire, smoke, wind, use_front=True))
    n_path_hard = sum(1 for c in path if cell_unsafe(c, fire, smoke, wind, use_front=False))
    return {
        "grid_fire_smoke": n_fire_smoke_grid,
        "grid_frac": n_fire_smoke_grid / float(GRID * GRID),
        "path_n": n,
        "path_fire_smoke": n_path_fire_smoke,
        "path_edge": n_path_blocked_edge,
        "path_front": n_path_front,
        "path_unsafe": n_path_unsafe,
        "path_hard": n_path_hard,
        "path_unsafe_frac": n_path_unsafe / float(n) if n else 0.0,
        "path_hard_frac": n_path_hard / float(n) if n else 0.0,
    }


def simulate_defer_online(
    path: list[tuple[int, int]],
    fire: set[tuple[int, int]],
    smoke: set[tuple[int, int]],
    wind: str,
    victims: dict[str, tuple[int, int]],
    *,
    use_front: bool,
    pos: tuple[int, int],
    pending: list[tuple[int, int]],
    deferred: list[tuple[int, int]],
    done: set[tuple[int, int]],
    obs_step: dict[str, int | None],
    t: int,
) -> tuple[tuple[int, int], int]:
    """One step of defer-and-continue with BFS around currently blocked cells."""
    r2 = OBS * OBS
    px, py = pos
    for vid, (vx, vy) in victims.items():
        if obs_step[vid] is None and (px - vx) ** 2 + (py - vy) ** 2 <= r2:
            obs_step[vid] = t

    def is_blocked(cell: tuple[int, int]) -> bool:
        return cell_unsafe(cell, fire, smoke, wind, use_front=use_front)

    def pick_next() -> tuple[int, int] | None:
        while pending:
            cell = pending[0]
            if cell in done:
                pending.pop(0)
                continue
            if is_blocked(cell):
                deferred.append(pending.pop(0))
                continue
            return cell
        revived: list[tuple[int, int]] = []
        still: list[tuple[int, int]] = []
        for cell in deferred:
            if cell in done:
                continue
            if is_blocked(cell):
                still.append(cell)
            else:
                revived.append(cell)
        deferred[:] = still
        if not revived:
            return None
        revived.sort(key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1]))
        return revived[0]

    target = pick_next()
    if target is None:
        return pos, 0
    if pos == target:
        done.add(target)
        return pos, 0
    nxt = bfs_next_step(pos, target, fire, smoke, wind, use_front=use_front)
    if nxt is None:
        if target not in deferred:
            deferred.append(target)
        if pending and pending[0] == target:
            pending.pop(0)
        return pos, 0
    moved = 0 if nxt == pos else 1
    pos = nxt
    px, py = pos
    for vid, (vx, vy) in victims.items():
        if obs_step[vid] is None and (px - vx) ** 2 + (py - vy) ** 2 <= r2:
            obs_step[vid] = t
    if pos == target:
        done.add(target)
        if pending and pending[0] == target:
            pending.pop(0)
    return pos, moved


def run_hazard_and_detour(seed: int, scenario: str, wind: str, path: list[tuple[int, int]]) -> dict:
    params = _params(scenario, wind)
    model = _make_model(seed, params)
    spawns = _victim_spawns(model)
    searcher_ids = resolve_victim_searcher_uav_ids(model)
    samples: dict[int, dict] = {}
    states = {
        "hard": {
            "pos": path[0],
            "pending": list(path),
            "deferred": [],
            "done": set(),
            "obs": {vid: None for vid in spawns},
            "moves": 0,
            "t_done": None,
        },
        "front": {
            "pos": path[0],
            "pending": list(path),
            "deferred": [],
            "done": set(),
            "obs": {vid: None for vid in spawns},
            "moves": 0,
            "t_done": None,
        },
    }
    log("    stepping model ...")
    with contextlib.redirect_stdout(io.StringIO()):
        for step in range(1, STEPS + 1):
            model.step()
            fire, smoke = snapshot_hazards(model)
            if step in (60, 120, 180, 240):
                samples[step] = path_block_stats(path, fire, smoke, wind)
                log("      reached step %d" % step)
            for key, use_front in (("hard", False), ("front", True)):
                st = states[key]
                if st["t_done"] is not None:
                    continue
                remaining = [c for c in st["pending"] if c not in st["done"]] + [
                    c for c in st["deferred"] if c not in st["done"]
                ]
                if not remaining:
                    st["t_done"] = step
                    continue
                new_pos, moved = simulate_defer_online(
                    path,
                    fire,
                    smoke,
                    wind,
                    spawns,
                    use_front=use_front,
                    pos=st["pos"],
                    pending=st["pending"],
                    deferred=st["deferred"],
                    done=st["done"],
                    obs_step=st["obs"],
                    t=step,
                )
                st["pos"] = new_pos
                st["moves"] += moved
    ev = _build_evaluation(model, None, STEPS, params)
    del model
    return {
        "spawns": spawns,
        "searcher_ids": searcher_ids,
        "samples": samples,
        "states": states,
        "eval": ev,
        "params": params,
    }


def two_searcher_paths(wind: str) -> list[list[tuple[int, int]]]:
    n = 2
    paths = []
    w = str(wind).strip().lower()
    if w in ("east", "west"):
        for idx in range(n):
            lo, hi = lane_bounds(n, idx, 0, GRID - 1)
            first_north = w != "south"
            paths.append(boustrophedon_path(list(TRACKS), y0=lo, y1=hi, first_north=first_north))
    else:
        for idx in range(n):
            lo, hi = lane_bounds(n, idx, 0, GRID - 1)
            xs = tracks_for_band(lo, hi, int(OBS))
            first_north = w != "south"
            paths.append(boustrophedon_path(xs, y0=0, y1=GRID - 1, first_north=first_north))
    return paths


def write_output() -> None:
    text = "\n".join(lines) + "\n"
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main() -> int:
    log("FIX10 PART 1  systematic sweep coverage ceiling")
    log("Python %s" % sys.version.replace("\n", " "))
    log("mesa %s" % mesa.__version__)
    log("executable %s" % PY)
    log("UAV_OBSERVATION_RADIUS=%s" % OBS)
    log("WIND_FIRE_FRONT_MIN_DISTANCE=%s" % FRONT_MIN)
    log("never_detected timeout UNDETECTED_STREAK_STEPS=%d" % TIMEOUT)
    log("grid=%dx%d  tracks=%s" % (GRID, GRID, list(TRACKS)))
    log("")

    log("================================================================")
    log("Q1  theoretical boustrophedon schedule (no hazards)")
    log("================================================================")
    path = boustrophedon_path(list(TRACKS), y0=0, y1=GRID - 1, first_north=True)
    n_wp = len(path)
    n_moves = max(0, n_wp - 1)
    log("  swath layout:")
    log("    observation radius R=8  swath width=2*R+1=17")
    log("    track x-centers: 8, 25, 42")
    log("    track 8  covers x in [0, 16]")
    log("    track 25 covers x in [17, 33]")
    log("    track 42 covers x in [34, 49]")
    log("    pass 1: (8,0)->(8,49)  then connect x 8->25 at y=49")
    log("    pass 2: (25,49)->(25,0) then connect x 25->42 at y=0")
    log("    pass 3: (42,0)->(42,49)")
    log("  waypoint count (cells occupied, including start): %d" % n_wp)
    log("  move count (one 4-connected step per step): %d" % n_moves)
    log("  start cell=%s  end cell=%s" % (path[0], path[-1]))
    counts, full_at = coverage_along_path(path)
    n_grid = GRID * GRID
    final_cov = counts[-1] if counts else 0
    log("  cells observed at end of path: %d / %d = %.6f" % (final_cov, n_grid, final_cov / float(n_grid)))
    if full_at is None:
        missing = n_grid - final_cov
        log("  100%% coverage: NOT reached  missing=%d" % missing)
        covered: set[tuple[int, int]] = set()
        for px, py in path:
            mark_obs(covered, px, py)
        miss = [(x, y) for x in range(GRID) for y in range(GRID) if (x, y) not in covered]
        log("  missing cells (up to 20): %s" % miss[:20])
    else:
        log("  100%% coverage first reached at path index %d (moves=%d, 0-based occupy step)" % (full_at, full_at))
        log("  within timeout 210: %s   within budget 240: %s" % (full_at <= TIMEOUT, full_at <= STEPS))
    log("")

    log("================================================================")
    log("Q2  offline geometry vs exact victim spawn coordinates")
    log("================================================================")
    log("  spawn formula: wildfire_model._init_managed_victims (deterministic, no RNG)")
    for n in (2, 3, 4, 5):
        spawns = spawn_coords(n)
        log("  NUM_VICTIMS=%d  rounded grid coords=%s" % (n, spawns))
        for vid, (vx, vy) in spawns.items():
            step = first_obs_step(path, float(vx), float(vy))
            if step is None:
                log("    %s (%d,%d)  NEVER observed along theoretical path" % (vid, vx, vy))
            else:
                log(
                    "    %s (%d,%d)  first observed at path index %d  (<=210=%s <=240=%s)"
                    % (vid, vx, vy, step, step <= TIMEOUT, step <= STEPS)
                )
    log("  listed never_detected victims (fix8) vs same path:")
    all_geom_ok = True
    latest_nd = 0
    for scenario, wind, vid, pos in ND_CASES:
        vx, vy = pos
        step = first_obs_step(path, float(vx), float(vy))
        ok = step is not None and step <= TIMEOUT
        all_geom_ok = all_geom_ok and ok
        if step is not None:
            latest_nd = max(latest_nd, step)
        log(
            "    %s/%s %s %s  first_step=%s  <=210=%s"
            % (scenario, wind, vid, pos, step, ok)
        )
    log("  all listed ND victims observed by 210 (no hazard): %s  latest_step=%d" % (all_geom_ok, latest_nd))
    log("")
    write_output()

    log("  verifying spawn coords against live model (D n=4, A n=5, C n=3, B n=2) seed=101")
    for scenario, n_expect in (("B", 2), ("C", 3), ("D", 4), ("A", 5)):
        model = _make_model(101, _params(scenario, "north"))
        live = _victim_spawns(model)
        formula = spawn_coords(n_expect)
        match = live == formula
        log("    %s live=%s formula=%s match=%s" % (scenario, live, formula, match))
        del model
    log("")

    log("================================================================")
    log("Q3  hazards D/north seed=101 and D/south seed=101")
    log("================================================================")
    log("  hard-blocked = fire OR smoke OR _downwind_edge_blocked")
    log("  front-blocked = hard OR Manhattan to fire/smoke < %d" % FRONT_MIN)
    defer_results = {}
    for scenario, wind in (("D", "north"), ("D", "south")):
        path_w = path
        if wind == "south":
            path_w = boustrophedon_path(list(TRACKS), y0=0, y1=GRID - 1, first_north=False)
        log("  running %s/%s seed=101 (%d steps) ..." % (scenario, wind, STEPS))
        data = run_hazard_and_detour(101, scenario, wind, path_w)
        log("    searcher_ids=%s spawns=%s" % (data["searcher_ids"], data["spawns"]))
        ev = data["eval"]
        log(
            "    eval rescued=%s dead=%s unreachable=%s never_detected=%s causes=%s"
            % (
                ev.get("rescued"),
                ev.get("dead"),
                ev.get("unreachable"),
                ev.get("never_detected"),
                ev.get("unreachable_causes"),
            )
        )
        for sample_step in (60, 120, 180, 240):
            st = data["samples"][sample_step]
            log(
                "    step=%d  fire_or_smoke=%d/%d=%.4f  "
                "path_hard=%d/%d=%.4f  path_front<%d=%d/%d=%.4f  "
                "path_on_fire_or_smoke=%d  path_downwind_edge=%d"
                % (
                    sample_step,
                    st["grid_fire_smoke"],
                    GRID * GRID,
                    st["grid_frac"],
                    st["path_hard"],
                    st["path_n"],
                    st["path_hard_frac"],
                    FRONT_MIN,
                    st["path_front"],
                    st["path_n"],
                    st["path_unsafe_frac"],
                    st["path_fire_smoke"],
                    st["path_edge"],
                )
            )
        defer_results[(scenario, wind)] = data
        for label, key in (("hard (fire/smoke/edge)", "hard"), ("hard+front<12", "front")):
            st = data["states"][key]
            leftover_n = sum(1 for c in path_w if c not in st["done"])
            log(
                "    defer BFS %s: t_done=%s moves=%d done=%d/%d leftover=%d"
                % (label, st["t_done"], st["moves"], len(st["done"]), len(path_w), leftover_n)
            )
            for vid, pos in sorted(data["spawns"].items()):
                obs = st["obs"].get(vid)
                log(
                    "      %s %s  observed_at_step=%s  <=210=%s"
                    % (vid, pos, obs, (obs is not None and obs <= TIMEOUT))
                )
            extra = None if st["t_done"] is None else st["t_done"] - n_moves
            log(
                "    extra vs theoretical moves (%d): extra=%s  fits_210=%s fits_240=%s"
                % (
                    n_moves,
                    extra,
                    st["t_done"] is not None and st["t_done"] <= TIMEOUT,
                    st["t_done"] is not None and st["t_done"] <= STEPS,
                )
            )
    log("")

    log("================================================================")
    log("Q4  gate: can systematic sweep reach remaining victims?")
    log("================================================================")
    log("  single-searcher geometry (no hazard): all NUM_VICTIMS in {2,3,4,5} observed?")
    geom_fail = []
    for n in (2, 3, 4, 5):
        for vid, (vx, vy) in spawn_coords(n).items():
            step = first_obs_step(path, float(vx), float(vy))
            if step is None or step > TIMEOUT:
                geom_fail.append((n, vid, (vx, vy), step))
    if geom_fail:
        log("    NO  failures=%s" % geom_fail)
    else:
        log("    YES  every spawn observed by path index <= %d (timeout 210)" % latest_nd)

    log("  listed ND victims, single searcher, no hazard: %s" % all_geom_ok)
    log("  D/north 101 and D/south 101 hazard-aware BFS defer:")
    dn = defer_results[("D", "north")]
    ds = defer_results[("D", "south")]
    v3_n_hard = dn["states"]["hard"]["obs"].get("victim_3")
    v3_n_front = dn["states"]["front"]["obs"].get("victim_3")
    v1_s_hard = ds["states"]["hard"]["obs"].get("victim_1")
    v1_s_front = ds["states"]["front"]["obs"].get("victim_1")
    log("    D/north victim_3 (25,3) hard=%s front=%s leftover_hard=%d leftover_front=%d"
        % (
            v3_n_hard,
            v3_n_front,
            sum(1 for c in boustrophedon_path(list(TRACKS), first_north=True) if c not in dn["states"]["hard"]["done"]),
            sum(1 for c in boustrophedon_path(list(TRACKS), first_north=True) if c not in dn["states"]["front"]["done"]),
        ))
    log("    D/south victim_1 (25,48) hard=%s front=%s leftover_hard=%d leftover_front=%d"
        % (
            v1_s_hard,
            v1_s_front,
            sum(1 for c in boustrophedon_path(list(TRACKS), first_north=False) if c not in ds["states"]["hard"]["done"]),
            sum(1 for c in boustrophedon_path(list(TRACKS), first_north=False) if c not in ds["states"]["front"]["done"]),
        ))

    single_nd_ok = all_geom_ok
    for scenario, wind, vid, pos in ND_CASES:
        step = first_obs_step(path, float(pos[0]), float(pos[1]))
        if step is None or step > TIMEOUT:
            single_nd_ok = False
    # Gate uses hard obstacles (fire/smoke/edge). Front<12 is a preference the
    # production sweep keeps by deferring when a safer continuation exists, but
    # it must not stall the lawnmower (corridor already relaxed 12 -> ~5.4).
    hazard_key_ok = (
        v3_n_hard is not None and v3_n_hard <= TIMEOUT
        and v1_s_hard is not None and v1_s_hard <= TIMEOUT
    )
    single_ok = single_nd_ok and hazard_key_ok
    log("  SINGLE searcher feasible within 210 (geometry all ND + D/north&south HARD-obstacle BFS): %s" % single_ok)
    log("  same key victims with front<12 as HARD too: D/north v3=%s D/south v1=%s"
        % (v3_n_front, v1_s_front))

    log("  TWO searchers using existing lane partitioning (n=2):")
    two_ok = True
    latest_two = 0
    for wind in ("north", "south", "east", "west"):
        paths2 = two_searcher_paths(wind)
        lengths = [len(p) - 1 for p in paths2]
        log("    wind=%s  path_moves=%s  max=%d" % (wind, lengths, max(lengths)))
        for scenario, w, vid, pos in ND_CASES:
            if w != wind:
                continue
            best = None
            for p in paths2:
                st = first_obs_step(p, float(pos[0]), float(pos[1]))
                if st is None:
                    continue
                if best is None or st < best:
                    best = st
            ok = best is not None and best <= TIMEOUT
            two_ok = two_ok and ok
            if best is not None:
                latest_two = max(latest_two, best)
            log("      %s/%s %s %s  first_step=%s  <=210=%s" % (scenario, w, vid, pos, best, ok))
    log("  TWO searchers, no-hazard, all listed ND victims <=210: %s  latest=%d" % (two_ok, latest_two))

    if single_ok:
        decision = (
            "YES: a single searcher systematic sweep can plausibly observe all remaining "
            "never_detected victims within the 210-step timeout. Geometry covers every spawn "
            "on the 3-track lawnmower; D/north and D/south hazard detours still observe the "
            "y-extreme victims. IMPLEMENT Part 2."
        )
    elif two_ok:
        decision = (
            "SINGLE searcher cannot guarantee all victims within 210 under the measured "
            "hazard/geometry constraints, but TWO lane-partitioned searchers can. This is a "
            "resource-provisioning finding about the architecture, not a failure of systematic "
            "coverage. Default searcher count is NOT changed. IMPLEMENT Part 2 for the single "
            "searcher (existing default) so coverage is no longer wasted on corridor scoring."
        )
    else:
        decision = (
            "NO: systematic sweep cannot plausibly reach all remaining victims within 210 "
            "steps for one searcher, and two lane-partitioned searchers also fail. STOP. "
            "Do not implement Part 2."
        )
    log("")
    log("DECISION:")
    log("  %s" % decision)
    log("")
    log("END PART 1")
    write_output()
    log("wrote %s" % OUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
