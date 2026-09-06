"""Grid-scale diagnosis probe (read-only observers + RUNTIME monkeypatches only).

Mirrors evaluate_scenarios._run_seed statement for statement (seeding order,
apply_scenario_config, model.debug_log = False, stdout redirected, per-step
get_dashboard_state() polling until the terminal step) and layers observers on
top. Nothing here edits source: the grid size is set on common_fixed_variables
BEFORE any simulation module is imported (which is exactly what a source edit of
WIDTH/HEIGHT would do for every `from common_fixed_variables import ...`), and
every other override is an attribute rebinding at run time.

Options that matter for the grid-scale round:
  --grid N            HEIGHT = WIDTH = N, applied before the first simulation import
  --expose-dims       set WildFireModel.HEIGHT / .WIDTH class attributes so the many
                      `getattr(model, "HEIGHT", 50)` fallbacks in agents.py and
                      src_extension resolve to the real grid instead of 50
  --const NAME=VALUE  rebind a module constant in EVERY loaded repo module that has
                      it (import-time copies included); UNDETECTED_STREAK_STEPS /
                      UNREACHABLE_STREAK_STEPS also patch the __defaults__ of
                      rescue_planner.unreachable_escape_victims, which is where the
                      model actually reads them
  --checkpoints a,b,c evaluate (serve_dashboard._build_evaluation, pure) at these
                      steps inside ONE run; the model has no knowledge of the step
                      budget (BATCH_SIZE is only an exit guard), so the state at
                      step S of a long run is the state of a run with budget S
  --set KEY=VALUE     extra apply_scenario_config parameter, like _ffr_harness

BATCH_SIZE is passed as max(300, steps): WildFireModel.step() calls sys.exit(0)
once evaluation_timesteps_counter - 1 == BATCH_SIZE, i.e. on the 302nd step of a
BATCH_SIZE=300 run, so any budget above 301 needs BATCH_SIZE raised with it.

Coverage definition (recorded per step from UAV positions, initial position
included): a cell is "covered" once it has been inside a UAV's observation square
(Chebyshev radius UAV_OBSERVATION_RADIUS, clipped to the grid). "searcher" =
UAVs whose current_role is victim_searcher/victim_search; "all" = every UAV.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import io as _io
import json
import os
import random
import sys
import time


def _parse_value(raw: str):
    text = str(raw).strip()
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _mem_mb() -> dict:
    """Working set / commit of this process in MB (Windows psapi, no psutil)."""
    try:
        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_uint32),
                ("PageFaultCount", ctypes.c_uint32),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        h = ctypes.windll.kernel32.GetCurrentProcess()
        fn = ctypes.windll.psapi.GetProcessMemoryInfo
        fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_uint32]
        fn.restype = ctypes.c_int
        ok = fn(h, ctypes.byref(pmc), pmc.cb)
        if not ok:
            return {}
        mb = 1024.0 * 1024.0
        return {
            "working_set_mb": round(pmc.WorkingSetSize / mb, 1),
            "peak_working_set_mb": round(pmc.PeakWorkingSetSize / mb, 1),
            "commit_mb": round(pmc.PagefileUsage / mb, 1),
            "peak_commit_mb": round(pmc.PeakPagefileUsage / mb, 1),
        }
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--grid", type=int, default=50)
    ap.add_argument("--wind", default="east", choices=["north", "south", "east", "west"])
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--checkpoints", default="")
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--expose-dims", action="store_true")
    ap.add_argument("--const", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--fast-nsb", action="store_true",
                    help="exact, order-preserving reimplementation of _never_seen_proximity_bonus (measurement-time speedup)")
    ap.add_argument("--verify-nsb", type=int, default=0,
                    help="with --fast-nsb: every Nth call also runs the original and compares bit-for-bit")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")

    # ---- grid size BEFORE the first simulation import (== a source edit) -------
    import common_fixed_variables as cfv  # noqa: E402
    cfv.HEIGHT = int(args.grid)
    cfv.WIDTH = int(args.grid)

    import numpy as np  # noqa: E402
    import agents as am  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    from src_extension.adaptation.local_adaptation_generator import (  # noqa: E402
        LocalAdaptationSpaceGenerator,
        apply_scenario_config,
    )
    from src_extension.planning import rescue_planner as rp  # noqa: E402
    from wildfire_model import WildFireModel  # noqa: E402
    from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params  # noqa: E402

    for mod in (am, cfv, wf):
        path = os.path.abspath(getattr(mod, "__file__", ""))
        if not path.lower().startswith(repo.lower()):
            print("IMPORT MISMATCH: %s from %s" % (mod.__name__, path), file=sys.stderr)
            return 3
    assert wf.HEIGHT == args.grid and wf.WIDTH == args.grid, "star-import did not pick up the grid"

    H = int(cfv.HEIGHT)
    W = int(cfv.WIDTH)
    R = int(cfv.UAV_OBSERVATION_RADIUS)

    # ---- runtime monkeypatches -------------------------------------------------
    if args.expose_dims:
        WildFireModel.HEIGHT = H
        WildFireModel.WIDTH = W

    def _repo_modules():
        out = []
        for name, mod in list(sys.modules.items()):
            path = getattr(mod, "__file__", None)
            if not path:
                continue
            try:
                if os.path.abspath(path).lower().startswith(repo.lower()):
                    out.append((name, mod))
            except Exception:
                continue
        return out

    applied_consts: dict = {}
    for item in args.const:
        if "=" not in item:
            print("bad --const %r" % item, file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        k = k.strip()
        val = _parse_value(v)
        sites = []
        for name, mod in _repo_modules():
            if k in getattr(mod, "__dict__", {}):
                setattr(mod, k, val)
                sites.append(name)
        if k in ("UNDETECTED_STREAK_STEPS", "UNREACHABLE_STREAK_STEPS"):
            fn = rp.unreachable_escape_victims
            # signature (..., *, geo_threshold=UNREACHABLE_STREAK_STEPS, undetected_threshold=UNDETECTED_STREAK_STEPS)
            kw = dict(fn.__kwdefaults__ or {})
            kw["geo_threshold" if k == "UNREACHABLE_STREAK_STEPS" else "undetected_threshold"] = val
            fn.__kwdefaults__ = kw
            sites.append("rescue_planner.unreachable_escape_victims.__kwdefaults__")
        applied_consts[k] = {"value": val, "sites": sites}
        if not sites:
            print("WARNING: --const %s matched no module" % k, file=sys.stderr)

    # ---- measurement-time speedup: exact reimplementation of the O(cells) scan ----
    # _never_seen_proximity_bonus walks the WHOLE observation_status_map for every
    # candidate cell (10k candidates x 10k cells per retarget at 100x100). The
    # replacement caches, once per (map, step), the dict POSITION of every
    # never_seen/stale cell in a grid array; per candidate it gathers the cells
    # inside the Manhattan radius, sorts them by that original position and
    # accumulates the identical terms in the identical order, so every float
    # addition happens in the same sequence as the original and the result is
    # bit-identical. Cells that contribute nothing are skipped (they never touch
    # `bonus` in the original either). --verify-nsb N re-runs the original on
    # every Nth call and counts mismatches.
    import math  # noqa: E402
    lag_mod = sys.modules["src_extension.adaptation.local_adaptation_generator"]
    NSB_STATS = {"calls": 0, "builds": 0, "verified": 0, "mismatch": 0, "fallback": 0, "enabled": bool(args.fast_nsb)}
    if args.fast_nsb:
        _orig_nsb = lag_mod._never_seen_proximity_bonus
        _nsb_cache: dict = {"key": None, "order": None}

        def _fast_nsb(runtime_models, cx, cy, *, obs_radius: int = 8):
            NSB_STATS["calls"] += 1
            if isinstance(runtime_models, dict):
                visibility = runtime_models.get("visibility_model")
                sim = runtime_models.get("simulation_model")
            else:
                visibility = getattr(runtime_models, "visibility_model", None)
                sim = getattr(runtime_models, "simulation_model", None)
            status_map = getattr(getattr(visibility, "state", None), "observation_status_map", None)
            if visibility is None or not isinstance(status_map, dict) or sim is None:
                NSB_STATS["fallback"] += 1
                return _orig_nsb(runtime_models, cx, cy, obs_radius=obs_radius)
            key = (id(status_map), int(getattr(sim, "evaluation_timesteps_counter", -1) or 0), len(status_map))
            if _nsb_cache["key"] != key:
                order = np.full((H, W), -1, dtype=np.int64)
                bad = False
                for idx, (cell_pos, status) in enumerate(status_map.items()):
                    label = str(getattr(status, "value", status) or "").lower()
                    if "never_seen" not in label and label != "stale_information":
                        continue
                    if isinstance(cell_pos, (list, tuple)) and len(cell_pos) >= 2:
                        nx, ny = int(cell_pos[0]), int(cell_pos[1])
                    else:
                        continue
                    if 0 <= nx < H and 0 <= ny < W:
                        order[nx, ny] = idx
                    else:
                        bad = True
                        break
                if bad:
                    NSB_STATS["fallback"] += 1
                    return _orig_nsb(runtime_models, cx, cy, obs_radius=obs_radius)
                _nsb_cache["key"] = key
                _nsb_cache["order"] = order
                NSB_STATS["builds"] += 1
            order = _nsb_cache["order"]
            r2 = obs_radius + 8
            x0 = max(0, int(math.floor(cx - r2)))
            x1 = min(H, int(math.ceil(cx + r2)) + 1)
            y0 = max(0, int(math.floor(cy - r2)))
            y1 = min(W, int(math.ceil(cy + r2)) + 1)
            bonus = 0.0
            if x0 < x1 and y0 < y1:
                sub = order[x0:x1, y0:y1]
                xs, ys = np.nonzero(sub >= 0)
                if xs.size:
                    idxs = sub[xs, ys]
                    for j in np.argsort(idxs, kind="stable"):
                        nx = int(xs[j]) + x0
                        ny = int(ys[j]) + y0
                        dist = abs(cx - nx) + abs(cy - ny)
                        if dist <= obs_radius:
                            bonus += 4.0
                        elif dist <= r2:
                            bonus += max(0.0, 2.5 - (dist - obs_radius) * 0.3)
            if args.verify_nsb and NSB_STATS["calls"] % int(args.verify_nsb) == 0:
                ref = _orig_nsb(runtime_models, cx, cy, obs_radius=obs_radius)
                NSB_STATS["verified"] += 1
                if ref != bonus:
                    NSB_STATS["mismatch"] += 1
            return bonus

        lag_mod._never_seen_proximity_bonus = _fast_nsb
        # import-time copies of the NAME in other repo modules (none expected, but exact)
        for name, mod in _repo_modules():
            if mod is not lag_mod and getattr(mod, "_never_seen_proximity_bonus", None) is _orig_nsb:
                setattr(mod, "_never_seen_proximity_bonus", _fast_nsb)

    # ---- params: identical to evaluate_scenarios._scenario_params at CLI defaults
    preset = BUILTIN_SCENARIOS.get(args.scenario, {})
    num_agents = int(preset.get("NUM_AGENTS", 3))
    if args.roles == "half":
        ft, vs = _resolve_role_count_params(num_agents, 2, 2)
    else:
        ft, vs = _resolve_role_count_params(num_agents, None, None)
    batch_size = int(args.batch_size) if args.batch_size is not None else max(300, int(args.steps))
    params = {
        "NUM_AGENTS": num_agents,
        "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
        "WIND_DIRECTION": str(args.wind),
        "BATCH_SIZE": batch_size,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": ft,
        "NUM_VICTIM_SEARCHERS": vs,
    }
    extra: dict = {}
    for item in args.set:
        if "=" not in item:
            print("bad --set %r" % item, file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        extra[k.strip()] = _parse_value(v)
    params.update(extra)

    checkpoints = sorted({int(c) for c in args.checkpoints.split(",") if c.strip()} | {int(args.steps)})

    def _cell(pos):
        return None if pos is None else [int(pos[0]), int(pos[1])]

    def _on_boundary(pos) -> bool:
        if pos is None:
            return False
        x, y = int(pos[0]), int(pos[1])
        return x == 0 or x == H - 1 or y == 0 or y == W - 1

    def _step_of(model) -> int:
        return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)

    def _vid(model, agent) -> str:
        if agent is None:
            return ""
        try:
            return str(model._victim_id_from_agent(agent) or "")
        except Exception:
            return str(getattr(agent, "victim_id", "") or "")

    REC: dict = {"exit_starts": [], "completions": [], "unreachable_marks": [], "assigns": []}

    # ---- observers (call original, return unchanged) --------------------------
    _orig_advance = am.Firefighter.advance

    def _obs_advance(self):
        before_exiting = bool(getattr(self, "exiting", False))
        before_completed = bool(getattr(self, "rescue_completed", False))
        result = _orig_advance(self)
        if bool(getattr(self, "exiting", False)) and not before_exiting:
            et = getattr(self, "exit_target", None)
            REC["exit_starts"].append({
                "step": _step_of(self.model),
                "ff": str(getattr(self, "unit_id", "") or ""),
                "victim": _vid(self.model, getattr(self, "rescued_victim", None)),
                "ff_pos": _cell(getattr(self, "pos", None)),
                "exit_target": _cell(et),
                "exit_target_on_boundary": _on_boundary(et),
            })
        if bool(getattr(self, "rescue_completed", False)) and not before_completed:
            REC["completions"].append({
                "step": _step_of(self.model),
                "ff": str(getattr(self, "unit_id", "") or ""),
                "victim": _vid(self.model, getattr(self, "rescued_victim", None)),
                "pos": _cell(getattr(self, "pos", None)),
                "pos_on_boundary": _on_boundary(getattr(self, "pos", None)),
            })
        return result

    am.Firefighter.advance = _obs_advance

    _orig_apply = WildFireModel.apply_physical_rescue_command

    def _obs_apply(self, cmd):
        ok = _orig_apply(self, cmd)
        action = str(getattr(cmd, "action", "") or "").strip().lower()
        rec = {
            "step": _step_of(self),
            "ff": str(getattr(cmd, "firefighter_id", "") or ""),
            "vid": str(getattr(cmd, "victim_id", "") or ""),
            "reason": str(getattr(cmd, "reason", "") or ""),
            "ok": bool(ok),
        }
        if action == "mark_unreachable":
            REC["unreachable_marks"].append(rec)
        elif action == "assign":
            REC["assigns"].append(rec)
        return ok

    WildFireModel.apply_physical_rescue_command = _obs_apply

    # ---- run: byte-for-byte the evaluate_scenarios._run_seed sequence ----------
    rng = random.Random(args.seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    cov_searcher = np.zeros((H, W), dtype=bool)
    cov_all = np.zeros((H, W), dtype=bool)
    cov_tracker = np.zeros((H, W), dtype=bool)
    uav_steps: list = []          # per step: [[id, x, y, role], ...]
    victim_transitions: list = []  # [step, vid, status]
    victim_last: dict = {}
    fire_counts: list = []        # per step: [burning, burnt, has_burned]
    step_wall: list = []
    checkpoint_records: list = []
    uav_extent: dict = {}         # id -> [min_x, max_x, min_y, max_y]
    terminal_step = None
    step = 0

    def _fire_digest(model) -> str:
        parts = []
        for a in model.schedule.agents:
            if type(a).__name__ == "Fire":
                parts.append("%s:%d%d%s" % (a.unique_id, int(bool(a.burning)), int(bool(a.burnt)), a.fuel))
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    def _mark_cov(arr, x, y):
        arr[max(0, x - R):min(H, x + R + 1), max(0, y - R):min(W, y + R + 1)] = True

    def _observe_uavs(model, step_idx):
        row = []
        for a in model.schedule.agents:
            if type(a).__name__ != "UAV":
                continue
            pos = getattr(a, "pos", None)
            if pos is None:
                continue
            x, y = int(pos[0]), int(pos[1])
            role = str(getattr(a, "current_role", "") or "")
            uid = str(a.unique_id)
            row.append([uid, x, y, role])
            _mark_cov(cov_all, x, y)
            if role in ("victim_searcher", "victim_search"):
                _mark_cov(cov_searcher, x, y)
            elif role == "fire_tracker":
                _mark_cov(cov_tracker, x, y)
            ext = uav_extent.setdefault(uid, [x, x, y, y])
            ext[0] = min(ext[0], x); ext[1] = max(ext[1], x); ext[2] = min(ext[2], y); ext[3] = max(ext[3], y)
        uav_steps.append(row)

    def _observe_victims(model, step_idx):
        for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items():
            st = str(getattr(m, "status", "") or "")
            if victim_last.get(vid) != st:
                victim_last[vid] = st
                victim_transitions.append([step_idx, str(vid), st, _cell(getattr(m, "pos", None))])

    def _fire_stats(model):
        burning = burnt = has_burned = 0
        for a in model.schedule.agents:
            if type(a).__name__ == "Fire":
                if a.burning:
                    burning += 1
                if a.burnt:
                    burnt += 1
                if getattr(a, "has_burned", False):
                    has_burned += 1
        return [burning, burnt, has_burned]

    def _checkpoint(model, step_idx, t0):
        ev = _build_evaluation(model, terminal_step, step_idx, params)
        vis = getattr(model, "visibility_model", None)
        vis_state = getattr(vis, "state", None) if vis is not None else None
        visible = getattr(vis_state, "visible_cells", None) if vis_state is not None else None
        victims = {}
        for vid, m in (getattr(model, "victim_marker_agents", {}) or {}).items():
            victims[str(vid)] = {"status": str(getattr(m, "status", "") or ""), "pos": _cell(getattr(m, "pos", None))}
        ffs = {}
        for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
            ffs[str(fid)] = {
                "pos": _cell(getattr(m, "pos", None)),
                "status": str(getattr(m, "status", "") or ""),
                "dead": bool(getattr(m, "dead", False)),
                "off_grid": bool(getattr(m, "off_grid", False)),
            }
        uavs = {}
        for a in model.schedule.agents:
            if type(a).__name__ == "UAV":
                uavs[str(a.unique_id)] = {
                    "pos": _cell(getattr(a, "pos", None)),
                    "role": str(getattr(a, "current_role", "") or ""),
                    "battery": round(float(getattr(a, "battery_level", 0.0)), 1),
                    "battery_status": str(getattr(a, "battery_status", "") or ""),
                }
        fs = _fire_stats(model)
        rec = {
            "step": step_idx,
            "eval": ev,
            "terminal_step": terminal_step,
            "coverage_searcher": round(float(cov_searcher.sum()) / float(H * W), 4),
            "coverage_all": round(float(cov_all.sum()) / float(H * W), 4),
            "coverage_tracker": round(float(cov_tracker.sum()) / float(H * W), 4),
            "visibility_visible_fraction": (round(len(visible) / float(H * W), 4) if isinstance(visible, (set, dict, list)) else None),
            "burning": fs[0], "burnt": fs[1], "has_burned": fs[2],
            "burnt_fraction": round(fs[1] / float(H * W), 4),
            "has_burned_fraction": round(fs[2] / float(H * W), 4),
            "victims": victims,
            "firefighters": ffs,
            "uavs": uavs,
            "fire_digest": _fire_digest(model),
            "wall_s": round(time.perf_counter() - t0, 1),
            "mem": _mem_mb(),
            "n_unreachable_marks": len(REC["unreachable_marks"]),
            "n_completions": len(REC["completions"]),
        }
        checkpoint_records.append(rec)

    t0 = time.perf_counter()
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        t_init = time.perf_counter() - t0
        # geometry the managing system actually sees (diagnostic, read-only)
        try:
            gb = LocalAdaptationSpaceGenerator._grid_bounds({"simulation_model": model})
        except Exception as exc:
            gb = repr(exc)
        geometry = {
            "grid_h_w": [H, W],
            "model_has_HEIGHT_attr": hasattr(model, "HEIGHT"),
            "getattr_model_HEIGHT_default50": getattr(model, "HEIGHT", 50),
            "mesa_grid_w_h": [int(model.grid.width), int(model.grid.height)],
            "lag_grid_bounds": list(gb) if isinstance(gb, tuple) else gb,
            "sector_assignments": {str(k): dict(v) for k, v in (getattr(model, "_uav_sector_assignments", {}) or {}).items()},
            "victim_spawns": {str(v): _cell(getattr(m, "pos", None)) for v, m in (getattr(model, "victim_marker_agents", {}) or {}).items()},
            "ff_spawns": {str(f): _cell(getattr(m, "pos", None)) for f, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items()},
            "ignition": [_cell(a.pos) for a in model.schedule.agents if type(a).__name__ == "Fire" and a.burning],
            "uav_spawns": {str(a.unique_id): _cell(a.pos) for a in model.schedule.agents if type(a).__name__ == "UAV"},
            "batch_size": batch_size,
        }
        _observe_uavs(model, 0)
        _observe_victims(model, 0)
        for _ in range(args.steps):
            ts = time.perf_counter()
            model.step()
            step += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                mission = panel.get("mission_status", {}) or {}
                if mission.get("all_victims_terminal"):
                    terminal_step = step
            step_wall.append(round(time.perf_counter() - ts, 3))
            # --- observers only below this line
            _observe_uavs(model, step)
            _observe_victims(model, step)
            fire_counts.append(_fire_stats(model))
            if step in checkpoints:
                _checkpoint(model, step, t0)
        evaluation = _build_evaluation(model, terminal_step, step, params)
    wall = time.perf_counter() - t0
    stdout_text = buf.getvalue()

    # detection = the victim reached a status that implies a UAV saw it; a write-off
    # (candidate -> unreachable) or a death while still a candidate is NOT a detection
    first_detection = {}
    for s, vid, st, pos in victim_transitions:
        if vid not in first_detection and st in ("confirmed", "assigned", "rescued"):
            first_detection[vid] = {"step": s, "status": st}

    out = {
        "tag": args.tag,
        "repo": repo,
        "grid": [H, W],
        "expose_dims": bool(args.expose_dims),
        "consts": applied_consts,
        "scenario": args.scenario,
        "wind": args.wind,
        "roles": args.roles,
        "seed": args.seed,
        "steps": args.steps,
        "checkpoints": checkpoints,
        "params": params,
        "extra_params": extra,
        "geometry": geometry,
        "eval": evaluation,
        "terminal_step": terminal_step,
        "wall_s": round(wall, 1),
        "init_s": round(t_init, 1),
        "step_wall": step_wall,
        "mem_final": _mem_mb(),
        "checkpoint_records": checkpoint_records,
        "first_detection": first_detection,
        "victim_transitions": victim_transitions,
        "fire_counts": fire_counts,
        "uav_steps": uav_steps,
        "uav_extent": uav_extent,
        "exit_starts": REC["exit_starts"],
        "completions": REC["completions"],
        "unreachable_marks": REC["unreachable_marks"],
        "assigns": REC["assigns"],
        "absence_counters": {
            "removals_total": getattr(model, "ff_absence_removals_total", None),
            "returns_total": getattr(model, "ff_absence_returns_total", None),
        },
        "victim_flee_moves_total": int(getattr(model, "victim_flee_moves_total", 0) or 0),
        "nsb_stats": NSB_STATS,
        "stdout_sha256": hashlib.sha256(stdout_text.encode("utf-8", "replace")).hexdigest(),
        "stdout_lines": stdout_text.count("\n"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f)
    os.replace(tmp, args.out)
    ev = evaluation
    cps = " ".join("cp%d[cov_s=%.2f cov_all=%.2f resc=%d dead=%d nd=%d burnt=%.2f]" % (
        c["step"], c["coverage_searcher"], c["coverage_all"], c["eval"]["rescued"], c["eval"]["dead"],
        c["eval"].get("never_detected", 0), c["burnt_fraction"]) for c in checkpoint_records)
    print("%s grid=%d %s/%s seed=%d steps=%d rescued=%d dead=%d unreachable=%d nd=%d ff_deaths=%d terminal=%s wall=%.0fs init=%.1fs mem=%s nsb=%s %s"
          % (args.tag, H, args.wind, args.roles, args.seed, args.steps, ev["rescued"], ev["dead"], ev["unreachable"],
             ev.get("never_detected", 0), ev["firefighter_deaths"], ev["terminal_step"], wall, t_init,
             out["mem_final"].get("peak_commit_mb"), NSB_STATS, cps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
