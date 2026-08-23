"""Q1-Q8 target-following diagnostics (read-only; no production edits).

Measures whether the victim searcher's executed move follows the target that
LocalAdaptationSpaceGenerator._compute_wind_aware_search_target produces, and
whether _uncovered_region_bonus differentiates candidate cells.

Q8 adds a per-term score decomposition: on every 10th step the whole candidate
grid of _pick_global_coverage_escape_target is re-scored with the UNPATCHED
production helpers, mirroring the loop filter-for-filter and term-for-term, so
that "which term outvoted the observation post?" is a direct readout. The
mirror validates itself against the best_point production passed into
_finalize_coverage_target.

ALL instrumentation is CLASS-LEVEL or MODULE-LEVEL monkeypatching applied from
this probe. Nothing under src_extension/ is modified. The executor builds a
fresh LocalAdaptationSpaceGenerator() on every call
(uav_executor.py:3737), so instance-level patching would capture nothing.

Units: detection / observation-post / observed-set membership are EUCLIDEAN r=8
(dx*dx + dy*dy <= 64), matching wildfire_model._detect_victims_in_uav_radius.
Manhattan is used only for progress-toward-target.

Logging budget: aggregates every step; per-candidate detail every 10th step.

Usage:
    python outputs/_diag_target_following.py                 # run all 4 combos
    python outputs/_diag_target_following.py worker D north 101 240 <out_json>
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import random
import subprocess
import sys
import time
from collections import Counter
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
from src_extension.adaptation import local_adaptation_generator as GEN
from src_extension.adaptation.local_adaptation_generator import (
    WIND_INTERIOR_MARGIN,
    LocalAdaptationSpaceGenerator as LAG,
    _cell_on_edge,
    _downwind_edge_blocked,
    _wind_search_state,
    apply_scenario_config,
    resolve_victim_searcher_uav_ids,
)
from src_extension.execution.uav_executor import UAVExecutor
from wildfire_model import WildFireModel

# --------------------------------------------------------------------------
# UNPATCHED snapshot, taken at import before install_patches() ever runs.
# The score decomposition re-evaluates candidate cells; if it went through the
# instrumentation wrappers it would double-count every Q7 aggregate. Calling
# these originals keeps the re-scoring pass invisible to the measurement.
# --------------------------------------------------------------------------
_RAW_NAMES = (
    "_uncovered_region_bonus",
    "_observation_coverage_penalty",
    "_never_seen_proximity_bonus",
    "_interior_margin_score",
    "_victim_likelihood_score",
    "_pocket_penalty",
    "_visit_count_for_cell",
    "_recent_target_penalty",
    "_cell_on_edge",
    "_min_smoke_distance",
    "_coverage_priority",
    "_coverage_mode_active",
    "_coverage_safe_x_min",
    "_coverage_safe_x_max",
    "_corridor_diversity_failure",
    "_grid_y_half_split",
    "_corridor_target_x_cap",
    "_coverage_y_commit_target_y",
    "_searcher_crosswind_lane",
    "_lane_allows_cell",
    "_is_saturated_cell",
    "_west_sweep_pending",
    "_east_sweep_pending",
    "_wind_label_from_vector",
    "_allow_east_force",
)
_RAW = {}
for _n in _RAW_NAMES:
    _f = getattr(GEN, _n, None)
    if _f is None:
        raise SystemExit("probe abort: generator symbol not found: " + _n)
    _RAW[_n] = _f

# Scoring constants read from production, never restated.
K_WIND = float(GEN.HYBRID_WIND_WEIGHT)
K_COV = float(GEN.HYBRID_COVERAGE_WEIGHT)
K_HAZ = float(GEN.HYBRID_HAZARD_WEIGHT)
K_DOWNWIND_CAP = float(GEN.WIND_DOWNWIND_CAP)
K_EDGE_PEN = float(GEN.WIND_EDGE_PENALTY)
K_VISIT = float(GEN.WIND_VISIT_PENALTY_SCALE)
K_REACHED = float(GEN.WIND_REACHED_PENALTY)
K_YPEN = int(GEN.COVERAGE_Y_COMMIT_PENETRATE_MARGIN)
K_YSTEP = float(GEN.COVERAGE_Y_COMMIT_GRADUAL_STEP)
K_UNVIS_X = float(GEN.COVERAGE_UNVISITED_X_BONUS)

# Additive terms of the call-site-1 score, in source order. Terms suffixed
# _in come from _score_hybrid_search_cell; _out are added by
# _pick_global_coverage_escape_target after the scorer returns.
TERM_KEYS = (
    "downwind",
    "hazard_clear",
    "interior",
    "victim_like",
    "obs_penalty",
    "never_seen_in",
    "cov_bonus_gated",
    "pocket_penalty",
    "edge_penalty",
    "visit_penalty",
    "recent_target_penalty",
    "dist_agent_inner",
    "reached_penalty",
    "pocket_center_in",
    "never_seen_out",
    "cov_bonus_ungated",
    "dist_agent_outer",
    "x_force",
    "y_force",
    "commit_north",
    "commit_south",
    "pocket_center_out",
)

GRID = 50
OBS = float(UAV_OBSERVATION_RADIUS)
OBS2 = OBS * OBS
STEPS = 240
DETAIL_EVERY = 10

# Q6 / Q7 disk offsets, Euclidean r=8.
_DISK = [
    (dx, dy)
    for dx in range(-int(math.ceil(OBS)), int(math.ceil(OBS)) + 1)
    for dy in range(-int(math.ceil(OBS)), int(math.ceil(OBS)) + 1)
    if dx * dx + dy * dy <= OBS2
]

RUNS = [
    ("D", "north", 101),
    ("D", "south", 101),
    ("A", "west", 505),
    ("A", "north", 101),
]


# --------------------------------------------------------------------------
# helpers copied verbatim in convention from outputs/_run_fix10_coverage.py
# --------------------------------------------------------------------------
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


def _mark_obs(covered: set, px: int, py: int) -> None:
    for dx, dy in _DISK:
        cx = px + dx
        cy = py + dy
        if 0 <= cx < GRID and 0 <= cy < GRID:
            covered.add((cx, cy))


def _cell(t) -> tuple[int, int] | None:
    if t is None:
        return None
    if isinstance(t, (list, tuple)) and len(t) >= 2:
        try:
            return (int(round(float(t[0]))), int(round(float(t[1]))))
        except (TypeError, ValueError):
            return None
    return None


def _uav_agents(model):
    return [a for a in model.schedule.agents if type(a) is am.UAV]


def _active_fire_cells(model) -> set:
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
        p = getattr(a, "pos", None)
        if p is not None:
            cells.add((int(p[0]), int(p[1])))
    return cells


def _smoke_cells(model) -> set:
    vis = getattr(model, "visibility_model", None)
    if vis is None:
        return set()
    raw = getattr(vis, "smoke_obscured_cells", None)
    if raw is None:
        state = getattr(vis, "state", None)
        if state is not None:
            raw = getattr(state, "smoke_obscured_cells", None)
    cells = set()
    if isinstance(raw, (set, frozenset, list, tuple)):
        for position in raw:
            if not isinstance(position, (list, tuple)) or len(position) < 2:
                continue
            try:
                cells.add((int(position[0]), int(position[1])))
            except (TypeError, ValueError):
                continue
    return cells


def _victim_spawns(model) -> dict:
    out = {}
    for vid, marker in (getattr(model, "victim_marker_agents", {}) or {}).items():
        p = getattr(marker, "pos", None)
        if p is not None:
            out[str(vid)] = (int(p[0]), int(p[1]))
    return dict(sorted(out.items()))


def _nd_ids(evaluation: dict) -> set:
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


def _pearson(xs: list, ys: list) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-12 or syy <= 1e-12:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def _ranks(vals: list) -> list:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def _spearman(xs: list, ys: list) -> float | None:
    if len(xs) < 3:
        return None
    return _pearson(_ranks(xs), _ranks(ys))


def _legal_posts(wind_dir: str, vx: int, vy: int) -> list:
    """Cells from which a searcher would detect the victim at (vx, vy) and not
    be pushed away by the downwind-edge or interior-margin rules. Euclidean r=8.
    """
    legal = []
    for dx, dy in _DISK:
        cx, cy = vx + dx, vy + dy
        if not (0 <= cx < GRID and 0 <= cy < GRID):
            continue
        if _downwind_edge_blocked(wind_dir, cx, cy, 0, GRID - 1, 0, GRID - 1):
            continue
        if _cell_on_edge(cx, cy, 0, GRID - 1, 0, GRID - 1, margin=WIND_INTERIOR_MARGIN):
            continue
        legal.append((cx, cy))
    return legal


# --------------------------------------------------------------------------
# score decomposition: exact mirror of call site 1
# --------------------------------------------------------------------------
def _decomp_site1(gen, kw: dict, prefinal) -> dict:
    """Re-derive the per-term score of every candidate in
    _pick_global_coverage_escape_target's loop, using the unpatched production
    helpers and the same filters in the same order.

    Answers "which term outvoted the observation post?" directly, and
    distinguishes being outscored from never being a candidate at all. The
    mirror is self-validating: its argmax is compared against the pre-finalize
    best_point production actually picked.
    """
    R = _RAW
    ws_real = kw["wind_state"]
    ws = dict(ws_real)
    _sat = ws.get("saturated_until")
    if isinstance(_sat, dict):
        # _is_saturated_cell pops expired keys; keep that off the live state.
        ws["saturated_until"] = dict(_sat)
    rm = kw["runtime_models"]
    uav_id = kw["uav_id"]
    wv = kw["wind_vector"]
    fire = kw["fire_cells"]
    smoke = kw["smoke_cells"]
    fx, fy = float(kw["fx"]), float(kw["fy"])
    ax, ay = float(kw["ax"]), float(kw["ay"])
    x_min, x_max = int(kw["x_min"]), int(kw["x_max"])
    y_min, y_max = int(kw["y_min"]), int(kw["y_max"])
    sim = kw["simulation"]
    step_index = int(kw["step_index"])
    wvx, wvy = float(wv[0]), float(wv[1])

    coverage_w = float(R["_coverage_priority"](ws))
    coverage_active = bool(R["_coverage_mode_active"](ws))
    force_esc = bool(ws.get("force_coverage_escape"))
    unresolved = int(ws.get("unresolved_victim_count", 0) or 0)
    ft_boost = float(ws.get("fire_tracker_detection_boost", 0.0) or 0.0)

    min_escape = 14.0 if force_esc else 6.0
    if coverage_w >= 0.9:
        min_escape = max(min_escape, 20.0)
    safe_x_min = int(R["_coverage_safe_x_min"](x_min))
    safe_x_max = int(R["_coverage_safe_x_max"](x_max))
    if coverage_active and ax < safe_x_min + 4:
        min_escape = max(4.0, min(min_escape, 8.0))
    corridor_fail = bool(R["_corridor_diversity_failure"](ws))
    lower_y_max, upper_y_min = R["_grid_y_half_split"](y_min, y_max)
    corridor_x_cap = R["_corridor_target_x_cap"](
        ws, x_min, x_max, coverage_active=coverage_active,
    )
    # _update_coverage_y_commit and _mark_x_strip_progress already ran inside the
    # real call and both precede the loop, so their results are read here rather
    # than recomputed.
    commit = ws.get("coverage_y_commit")
    y_force_min = (
        R["_coverage_y_commit_target_y"](ws, y_min, y_max) if commit == "north" else None
    )
    y_force_max = (
        R["_coverage_y_commit_target_y"](ws, y_min, y_max) if commit == "south" else None
    )
    if commit == "north" and ay < y_max - K_YPEN:
        min_escape = min(min_escape, 5.0)
    elif commit == "south" and ay > y_min + K_YPEN:
        min_escape = min(min_escape, 5.0)
    center = ws.get("pocket_center")
    has_center = isinstance(center, (list, tuple)) and len(center) >= 2
    ctr_x = int(center[0]) if has_center else 0
    ctr_y = int(center[1]) if has_center else 0
    wlabel = R["_wind_label_from_vector"](wv)
    lane = R["_searcher_crosswind_lane"](sim, uav_id, wlabel, x_min, x_max, y_min, y_max)
    west_pending = bool(R["_west_sweep_pending"](ws, safe_x_min))
    east_pending = bool(R["_east_sweep_pending"](ws, safe_x_max))
    allow_east = bool(R["_allow_east_force"](ws))

    if coverage_w >= 0.9 or unresolved > 0:
        wind_w = K_WIND * 0.15
    else:
        wind_w = K_WIND * max(0.15, 1.0 - coverage_w * 0.65)
    if unresolved > 0:
        wind_w *= 0.35

    memo: dict = {}

    def terms(cx: int, cy: int):
        """(total, term_dict) for a candidate, or (None, filter_name)."""
        hit = memo.get((cx, cy))
        if hit is not None:
            return hit
        out = _terms_uncached(cx, cy)
        memo[(cx, cy)] = out
        return out

    def _terms_uncached(cx: int, cy: int):
        if not (x_min + 1 <= cx < x_max and y_min + 1 <= cy < y_max):
            return None, "outside_loop_range"
        if not R["_lane_allows_cell"](lane, cx, cy):
            return None, "crosswind_lane"
        if corridor_fail and cx > corridor_x_cap:
            return None, "corridor_x_cap"
        if coverage_active:
            if cx < safe_x_min or cx > safe_x_max:
                return None, "coverage_x_bounds"
            if commit == "north" and cy < upper_y_min:
                return None, "commit_north_half"
            if commit == "south" and cy > lower_y_max:
                return None, "commit_south_half"
            if y_force_min is not None and cy < y_force_min:
                return None, "y_force_min"
            if y_force_max is not None and cy > y_force_max:
                return None, "y_force_max"
        if (cx - x_min) % 2 != 0 and (cy - y_min) % 2 != 0 and not force_esc:
            return None, "parity_lattice"
        if (cx, cy) in fire or (cx, cy) in smoke:
            return None, "fire_or_smoke_cell"
        if R["_is_saturated_cell"](ws, cx, cy, step_index):
            return None, "saturated"
        dist_agent = abs(cx - ax) + abs(cy - ay)
        if dist_agent < min_escape:
            return None, "min_escape_dist"

        downwind = (float(cx) - fx) * wvx + (float(cy) - fy) * wvy
        hazard_dist = gen._min_fire_distance((cx, cy), fire)
        smoke_dist = R["_min_smoke_distance"]((cx, cy), smoke)
        capped = min(max(0.0, float(downwind)), K_DOWNWIND_CAP)
        ns = float(R["_never_seen_proximity_bonus"](rm, cx, cy)) * (1.0 + coverage_w)
        urb = float(
            R["_uncovered_region_bonus"](cx, cy, ws, x_min, x_max, y_min, y_max)
        )
        t = {k: 0.0 for k in TERM_KEYS}
        # ---- inside _score_hybrid_search_cell ----
        t["downwind"] = capped * 3.0 * wind_w
        t["hazard_clear"] = min(hazard_dist, smoke_dist) * K_HAZ
        t["interior"] = float(
            R["_interior_margin_score"](cx, cy, x_min, x_max, y_min, y_max)
        )
        t["victim_like"] = float(R["_victim_likelihood_score"](rm, cx, cy))
        t["obs_penalty"] = (
            -float(R["_observation_coverage_penalty"](rm, cx, cy))
            * K_COV
            * (1.0 + coverage_w)
        )
        if coverage_w >= 0.55 or unresolved > 0:
            t["never_seen_in"] = ns
        if unresolved > 0:
            t["cov_bonus_gated"] = urb
        t["pocket_penalty"] = -float(R["_pocket_penalty"](ws, cx, cy))
        if R["_cell_on_edge"](
            cx, cy, x_min, x_max, y_min, y_max, margin=WIND_INTERIOR_MARGIN
        ):
            t["edge_penalty"] = -K_EDGE_PEN
        t["visit_penalty"] = (
            -float(R["_visit_count_for_cell"](sim, uav_id, cx, cy)) * K_VISIT
        )
        t["recent_target_penalty"] = -float(R["_recent_target_penalty"](ws, cx, cy))
        t["dist_agent_inner"] = -dist_agent * 0.1
        if dist_agent <= 2.0:
            t["reached_penalty"] = -K_REACHED
        elif dist_agent <= 4.0:
            t["reached_penalty"] = -K_REACHED * 0.45
        if force_esc and has_center:
            t["pocket_center_in"] = (abs(cx - ctr_x) + abs(cy - ctr_y)) * 0.35
        # ---- added by the call site, after the scorer returns ----
        t["never_seen_out"] = ns
        t["cov_bonus_ungated"] = urb
        t["dist_agent_outer"] = dist_agent * 0.35
        if coverage_active:
            if wlabel == "west":
                if west_pending and ax > safe_x_min + 4 and cx < ax:
                    t["x_force"] = (ax - cx) * 0.75
                elif east_pending and allow_east and ax < safe_x_max - 4 and cx > ax:
                    t["x_force"] = (cx - ax) * 0.75
            elif ax > safe_x_min + 4 and cx < ax:
                t["x_force"] = (ax - cx) * 0.75
        if coverage_active and y_force_min is not None and cy >= y_force_min:
            t["y_force"] = (cy - y_force_min) * 0.45
        if coverage_active and commit == "north" and y_force_min is not None:
            if ay < y_max - K_YPEN:
                north_band = float(ay) + K_YSTEP
                if float(cy) <= north_band:
                    t["commit_north"] += (float(cy) - float(ay)) * 0.55
            t["commit_north"] += max(0.0, float(cy) - float(ay)) * 0.35
        if coverage_active and commit == "south" and y_force_max is not None:
            t["commit_south"] = max(0.0, float(ay) - float(cy)) * 0.35
        if has_center:
            t["pocket_center_out"] = (abs(cx - ctr_x) + abs(cy - ctr_y)) * 0.45
        return sum(t.values()), t

    best_total = -float("inf")
    best_cell = None
    best_terms = None
    n_cand = 0
    reject = Counter()
    # A term's magnitude is not its influence: one that takes the same value on
    # every candidate cannot change the argmax. Range across the candidate set
    # is the decision-relevant statistic.
    tmin = {k: float("inf") for k in TERM_KEYS}
    tmax = {k: -float("inf") for k in TERM_KEYS}
    for cx in range(x_min + 1, x_max):
        for cy in range(y_min + 1, y_max):
            tot, info = terms(cx, cy)
            if tot is None:
                reject[info] += 1
                continue
            n_cand += 1
            for k in TERM_KEYS:
                v = info[k]
                if v < tmin[k]:
                    tmin[k] = v
                if v > tmax[k]:
                    tmax[k] = v
            if tot > best_total:
                best_total, best_cell, best_terms = tot, (cx, cy), info

    # Best cell inside each victim's observation-post set, plus the reason any
    # post cell never entered the running.
    posts: dict = {}
    for vid, cells in (P.posts_by_victim or {}).items():
        p_total = -float("inf")
        p_cell = None
        p_terms = None
        p_reject = Counter()
        n_ok = 0
        for cx, cy in cells:
            tot, info = terms(cx, cy)
            if tot is None:
                p_reject[info] += 1
                continue
            n_ok += 1
            if tot > p_total:
                p_total, p_cell, p_terms = tot, (cx, cy), info
        entry = {
            "n_post_cells": len(cells),
            "n_candidate": n_ok,
            "excluded": dict(p_reject),
            "best_cell": list(p_cell) if p_cell else None,
            "best_total": round(p_total, 3) if p_cell else None,
            "terms": {k: round(p_terms[k], 3) for k in TERM_KEYS} if p_terms else None,
        }
        if p_cell and best_terms:
            entry["deficit"] = round(best_total - p_total, 3)
            entry["term_gap"] = {
                k: round(best_terms[k] - p_terms[k], 3)
                for k in TERM_KEYS
                if abs(best_terms[k] - p_terms[k]) > 1e-9
            }
        posts[vid] = entry

    return {
        "n_candidates": n_cand,
        "rejected": dict(reject),
        "posts": posts,
        "term_range": (
            {k: round(tmax[k] - tmin[k], 3) for k in TERM_KEYS} if n_cand else None
        ),
        "term_min": {k: round(tmin[k], 3) for k in TERM_KEYS} if n_cand else None,
        "term_max": {k: round(tmax[k], 3) for k in TERM_KEYS} if n_cand else None,
        "mirror_best": list(best_cell) if best_cell else None,
        "mirror_total": round(best_total, 3) if best_cell else None,
        "prefinal": list(prefinal) if prefinal else None,
        "mirror_matches_prefinal": (
            bool(best_cell) and bool(prefinal) and tuple(best_cell) == tuple(prefinal)
        ),
        "winner_terms": (
            {k: round(best_terms[k], 3) for k in TERM_KEYS} if best_terms else None
        ),
        "coverage_w": round(coverage_w, 4),
        "coverage_active": coverage_active,
        "force_coverage_escape": force_esc,
        "unresolved": unresolved,
        "ft_boost": round(ft_boost, 4),
        "commit": commit,
        "min_escape_dist": min_escape,
        "wind_w": round(wind_w, 5),
        "agent": [ax, ay],
    }


# --------------------------------------------------------------------------
# probe state
# --------------------------------------------------------------------------
class Probe:
    """Holds all captured state for one run. Reset per process."""

    def __init__(self) -> None:
        self.searcher_ids: set = set()
        self.step = 0
        self.detail = False
        self.counters: Counter = Counter()
        self.patch_kinds: dict = {}
        self.cur: dict = {}
        self.steps: list = []
        self.obs_searcher: set = set()
        self.obs_all: set = set()
        self.snap_searcher: frozenset = frozenset()
        self.snap_all: frozenset = frozenset()
        self.in_gen = 0  # >0 while inside _compute_wind_aware_search_target
        self.gen_for_searcher = False
        self.posts_by_victim: dict = {}

    def begin_step(self, step: int) -> None:
        self.step = step
        self.detail = step % DETAIL_EVERY == 0
        if self.detail:
            self.snap_searcher = frozenset(self.obs_searcher)
            self.snap_all = frozenset(self.obs_all)
        self.cur = {
            "step": step,
            "gen_calls": [],          # (caller_name, result_cell)
            "gen_inner": [],          # ordered inner-fn events
            "gen_target_exec": None,
            "gen_target_planner": None,
            "gen_returned_none": False,
            "legacy_called": False,
            "legacy_target": None,
            "planner_target": None,
            "acted_targets": [],      # (cell, kind, via)
            "pathfind": [],           # (cell, label, routed)
            "retarget_fallback": [],  # (cell, label)
            "gate_calls": [],         # (in_dir, in_label, out_dir, out_label)
            "near_edge": None,
            "live_victims": None,
            "commit": [],             # (dir, label)
            "advance": [],            # (before, after, moved, action)
            "ws_entry": None,
            "execute_calls": 0,
            # Q7 aggregates, per call-kind
            "bonus_gated": [],
            "bonus_ungated": [],
            "pen_vals": [],
            "cand_detail": [],        # (cx, cy, bonus, kind)
            "pen_detail": [],         # (cx, cy, pen)
            "bonus_eff": {},          # (cx, cy) -> [gated_sum, ungated_sum]
            "decomp": None,           # per-term score attribution, detail steps
            "prefinal_target": None,  # best_point before _finalize_coverage_target
            "ft_boost": None,
        }

    def rec_bonus(self, cx: int, cy: int, val: float, caller: str) -> None:
        if not self.gen_for_searcher:
            return
        gated = caller == "_score_hybrid_search_cell"
        key = "bonus_gated" if gated else "bonus_ungated"
        self.cur[key].append(val)
        if self.detail:
            self.cur["cand_detail"].append((cx, cy, val, "gated" if gated else "ungated"))
            # The decision-relevant quantity is the total added to a candidate's
            # score across both call sites, not either call's return value.
            slot = self.cur["bonus_eff"].get((cx, cy))
            if slot is None:
                slot = [0.0, 0.0]
                self.cur["bonus_eff"][(cx, cy)] = slot
            slot[0 if gated else 1] += val

    def rec_pen(self, cx: int, cy: int, val: float) -> None:
        if not self.gen_for_searcher:
            return
        self.cur["pen_vals"].append(val)
        if self.detail:
            self.cur["pen_detail"].append((cx, cy, val))


P = Probe()


# --------------------------------------------------------------------------
# CLASS-LEVEL and MODULE-LEVEL patches
# --------------------------------------------------------------------------
def install_patches() -> dict:
    """Patch generator + executor + agent at class/module scope. Never instance."""
    kinds: dict = {}

    # ---- generator: CLASS-level methods on LocalAdaptationSpaceGenerator ----
    _orig_cwast = LAG._compute_wind_aware_search_target

    def cwast(self, runtime_models, uav_id, wind_direction, wind_vector):
        is_searcher = str(uav_id) in P.searcher_ids
        prev_flag = P.gen_for_searcher
        P.gen_for_searcher = is_searcher
        P.in_gen += 1
        caller = sys._getframe(1).f_code.co_name
        try:
            out = _orig_cwast(self, runtime_models, uav_id, wind_direction, wind_vector)
        finally:
            P.in_gen -= 1
            P.gen_for_searcher = prev_flag
        P.counters["gen_calls_total"] += 1
        if not is_searcher:
            P.counters["gen_calls_nonsearcher"] += 1
            return out
        P.counters["gen_calls_searcher"] += 1
        P.counters["gen_caller_" + caller] += 1
        cell = _cell(out)
        if P.cur:
            P.cur["gen_calls"].append((caller, cell))
            if caller == "_wind_aware_victim_search_target":
                P.cur["gen_target_exec"] = cell
            else:
                P.cur["gen_target_planner"] = cell
            if cell is None:
                P.cur["gen_returned_none"] = True
        if cell is None:
            P.counters["gen_returned_none"] += 1
        return out

    LAG._compute_wind_aware_search_target = cwast
    kinds["_compute_wind_aware_search_target"] = "class:LocalAdaptationSpaceGenerator"

    _orig_pick = LAG._pick_global_coverage_escape_target

    def pick(self, **kw):
        out = _orig_pick(self, **kw)
        P.counters["pick_global_escape_calls"] += 1
        if P.gen_for_searcher and P.cur:
            P.cur["gen_inner"].append(("pick_global_escape", _cell(out)))
            if P.detail and P.cur.get("decomp") is None:
                try:
                    P.cur["decomp"] = _decomp_site1(
                        self, kw, P.cur.get("prefinal_target"),
                    )
                    P.counters["decomp_ok"] += 1
                except Exception as exc:  # instrumentation must never kill a run
                    P.counters["decomp_fail"] += 1
                    P.cur["decomp"] = {"error": repr(exc)[:300]}
        return out

    LAG._pick_global_coverage_escape_target = pick
    kinds["_pick_global_coverage_escape_target"] = "class:LocalAdaptationSpaceGenerator"

    _orig_corr = LAG._generate_corridor_waypoints

    def corr(self, **kw):
        out = _orig_corr(self, **kw)
        P.counters["corridor_waypoint_calls"] += 1
        if P.gen_for_searcher and P.cur:
            P.cur["gen_inner"].append(("corridor", len(out or [])))
        return out

    LAG._generate_corridor_waypoints = corr
    kinds["_generate_corridor_waypoints"] = "class:LocalAdaptationSpaceGenerator"

    # ---- generator: MODULE-level functions (bare-global call sites) ----
    _orig_fin = GEN._finalize_coverage_target

    def fin(target, wind_state, **kw):
        caller = sys._getframe(1).f_code.co_name
        out = _orig_fin(target, wind_state, **kw)
        P.counters["finalize_coverage_calls"] += 1
        if P.gen_for_searcher and P.cur:
            P.cur["gen_inner"].append(("finalize", _cell(out)))
            if caller == "_pick_global_coverage_escape_target":
                # argmax before clamping, for validating the score mirror
                P.cur["prefinal_target"] = _cell(target)
        return out

    GEN._finalize_coverage_target = fin
    kinds["_finalize_coverage_target"] = "module:local_adaptation_generator"

    _orig_bonus = GEN._uncovered_region_bonus

    def bonus(cx, cy, wind_state, x_min, x_max, y_min, y_max):
        out = _orig_bonus(cx, cy, wind_state, x_min, x_max, y_min, y_max)
        caller = sys._getframe(1).f_code.co_name
        P.counters["bonus_calls_total"] += 1
        P.counters["bonus_from_" + caller] += 1
        P.rec_bonus(int(cx), int(cy), float(out), caller)
        return out

    GEN._uncovered_region_bonus = bonus
    kinds["_uncovered_region_bonus"] = "module:local_adaptation_generator"

    _orig_pen = GEN._observation_coverage_penalty

    def pen(runtime_models, cx, cy):
        out = _orig_pen(runtime_models, cx, cy)
        P.counters["obs_penalty_calls"] += 1
        P.rec_pen(int(cx), int(cy), float(out))
        return out

    GEN._observation_coverage_penalty = pen
    kinds["_observation_coverage_penalty"] = "module:local_adaptation_generator"

    _orig_score = GEN._score_hybrid_search_cell

    def score(**kw):
        out = _orig_score(**kw)
        P.counters["score_hybrid_calls"] += 1
        if P.gen_for_searcher and P.cur:
            ws = kw.get("wind_state") or {}
            P.cur["unresolved_at_score"] = int(ws.get("unresolved_victim_count", 0) or 0)
        return out

    GEN._score_hybrid_search_cell = score
    kinds["_score_hybrid_search_cell"] = "module:local_adaptation_generator"

    # ---- executor: CLASS-level methods on UAVExecutor ----
    _orig_exec = UAVExecutor.execute

    def execute(self, decision, timestamp=0.0, fail_safe_decision=None):
        mine = str(self.uav_id) in P.searcher_ids
        if mine and P.cur:
            P.cur["execute_calls"] += 1
            model = getattr(self, "_model", None)
            if model is not None:
                ws = _wind_search_state(model, self.uav_id)
                P.cur["ws_entry"] = {
                    "escape_target": _cell(ws.get("escape_target")),
                    "force_coverage_escape": bool(ws.get("force_coverage_escape")),
                    "force_interior_retarget": bool(ws.get("force_interior_retarget")),
                    "force_sweep": bool(ws.get("force_sweep")),
                    "pocket_streak": int(ws.get("pocket_streak", 0) or 0),
                    "sweep_no_move_streak": int(ws.get("sweep_no_move_streak", 0) or 0),
                    "steps_since_detection": int(ws.get("steps_since_detection", 0) or 0),
                    "unresolved": int(ws.get("unresolved_victim_count", 0) or 0),
                    "x_span": list(GEN._coverage_x_span(ws)),
                    "west_strip_done": bool(ws.get("west_strip_done")),
                    "east_strip_done": bool(ws.get("east_strip_done")),
                    "y_span": list(GEN._coverage_y_span(ws)),
                    # written into every searcher's state by the fire_tracker
                    # branch at wildfire_model.py:1017-1024, then read back by
                    # _coverage_mode_active/_coverage_priority: an external
                    # input to the scores being decomposed.
                    "ft_boost": float(
                        ws.get("fire_tracker_detection_boost", 0.0) or 0.0
                    ),
                }
        out = _orig_exec(self, decision, timestamp, fail_safe_decision)
        if mine:
            P.counters["execute_calls_searcher"] += 1
        return out

    UAVExecutor.execute = execute
    kinds["execute"] = "class:UAVExecutor"

    _orig_wavst = UAVExecutor._wind_aware_victim_search_target

    def wavst(self, agent, model=None):
        out = _orig_wavst(self, agent, model)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["exec_wind_target_calls"] += 1
        return out

    UAVExecutor._wind_aware_victim_search_target = wavst
    kinds["_wind_aware_victim_search_target"] = "class:UAVExecutor"

    _orig_leg = UAVExecutor._wind_aware_victim_search_target_legacy

    def legacy(self, agent, resolved):
        out = _orig_leg(self, agent, resolved)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["legacy_calls"] += 1
            if out is not None:
                P.counters["legacy_nonnull"] += 1
            if P.cur:
                P.cur["legacy_called"] = True
                P.cur["legacy_target"] = _cell(out)
        return out

    UAVExecutor._wind_aware_victim_search_target_legacy = legacy
    kinds["_wind_aware_victim_search_target_legacy"] = "class:UAVExecutor"

    _orig_plan = UAVExecutor._planner_wind_aware_target_from_decision

    def planner(self, decision):
        out = _orig_plan(self, decision)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["planner_target_calls"] += 1
            if out is not None:
                P.counters["planner_target_nonnull"] += 1
                if P.cur:
                    P.cur["planner_target"] = _cell(out[0])
        return out

    UAVExecutor._planner_wind_aware_target_from_decision = planner
    kinds["_planner_wind_aware_target_from_decision"] = "class:UAVExecutor"

    _orig_choose = UAVExecutor._choose_best_direction

    def choose(self, agent, target, target_kind="general"):
        out = _orig_choose(self, agent, target, target_kind)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["choose_best_direction_calls"] += 1
            if P.cur:
                P.cur["acted_targets"].append((_cell(target), str(target_kind), "choose"))
        return out

    UAVExecutor._choose_best_direction = choose
    kinds["_choose_best_direction"] = "class:UAVExecutor"

    _orig_pf = UAVExecutor._attempt_pathfinding_toward_target

    def pathfind(self, agent, target, *, action_label, prefer_bfs_action_label=False):
        out = _orig_pf(
            self,
            agent,
            target,
            action_label=action_label,
            prefer_bfs_action_label=prefer_bfs_action_label,
        )
        if str(self.uav_id) in P.searcher_ids:
            P.counters["pathfind_calls"] += 1
            if P.cur:
                P.cur["pathfind"].append((_cell(target), str(action_label), out is not None))
                if out is not None:
                    P.cur["acted_targets"].append((_cell(target), "victim", "pathfind"))
        return out

    UAVExecutor._attempt_pathfinding_toward_target = pathfind
    kinds["_attempt_pathfinding_toward_target"] = "class:UAVExecutor"

    _orig_rf = UAVExecutor._apply_retarget_with_pathfinding_fallback

    def retarget(self, agent, target, action_label):
        out = _orig_rf(self, agent, target, action_label)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["retarget_fallback_calls"] += 1
            if P.cur:
                P.cur["retarget_fallback"].append((_cell(target), str(action_label)))
        return out

    UAVExecutor._apply_retarget_with_pathfinding_fallback = retarget
    kinds["_apply_retarget_with_pathfinding_fallback"] = "class:UAVExecutor"

    _orig_gate = UAVExecutor._apply_victim_searcher_hazard_gate

    def gate(self, agent, chosen_dir, action):
        out = _orig_gate(self, agent, chosen_dir, action)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["hazard_gate_calls"] += 1
            try:
                od, ol = int(out[0]), str(out[1])
            except Exception:
                od, ol = None, None
            if od != int(chosen_dir) or ol != str(action):
                P.counters["hazard_gate_changed"] += 1
            if P.cur:
                P.cur["gate_calls"].append((int(chosen_dir), str(action), od, ol))
        return out

    UAVExecutor._apply_victim_searcher_hazard_gate = gate
    kinds["_apply_victim_searcher_hazard_gate"] = "class:UAVExecutor"

    _orig_ne = UAVExecutor._victim_near_edge_escape_required

    def near_edge(self, agent, model):
        out = _orig_ne(self, agent, model)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["near_edge_calls"] += 1
            if P.cur:
                P.cur["near_edge"] = bool(out)
        return out

    UAVExecutor._victim_near_edge_escape_required = near_edge
    kinds["_victim_near_edge_escape_required"] = "class:UAVExecutor"

    _orig_vp = UAVExecutor._victim_positions_from_runtime

    def vpos(self):
        out = _orig_vp(self)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["victim_positions_calls"] += 1
            if P.cur:
                P.cur["live_victims"] = len(out or [])
        return out

    UAVExecutor._victim_positions_from_runtime = vpos
    kinds["_victim_positions_from_runtime"] = "class:UAVExecutor"

    _orig_commit = UAVExecutor._commit_execution_direction

    def commit(self, agent, chosen_dir, action):
        out = _orig_commit(self, agent, chosen_dir, action)
        if str(self.uav_id) in P.searcher_ids:
            P.counters["commit_calls"] += 1
            if P.cur:
                P.cur["commit"].append((int(chosen_dir), str(action or "")))
        return out

    UAVExecutor._commit_execution_direction = commit
    kinds["_commit_execution_direction"] = "class:UAVExecutor"

    # ---- agent: CLASS-level method on agents.UAV (where pos actually mutates) ----
    _orig_advance = am.UAV.advance

    def advance(self):
        mine = str(self.unique_id) in P.searcher_ids
        before = getattr(self, "pos", None)
        before_c = (int(before[0]), int(before[1])) if before is not None else None
        _orig_advance(self)
        after = getattr(self, "pos", None)
        after_c = (int(after[0]), int(after[1])) if after is not None else None
        if mine:
            P.counters["advance_calls"] += 1
            if P.cur:
                P.cur["advance"].append(
                    (
                        before_c,
                        after_c,
                        before_c != after_c,
                        str(getattr(self, "execution_action", "") or ""),
                    )
                )

    am.UAV.advance = advance
    kinds["advance"] = "class:agents.UAV"

    return kinds


# --------------------------------------------------------------------------
# per-step classification
# --------------------------------------------------------------------------
def _gen_branch(rec: dict) -> str:
    """Attribute which generator code path produced the target (MEASURED events)."""
    inner = rec.get("gen_inner") or []
    tgt = rec.get("gen_target_exec") or rec.get("gen_target_planner")
    if not rec.get("gen_calls"):
        return "generator_not_called"
    if tgt is None:
        return "returned_none"
    names = [e[0] for e in inner]
    picks = [e[1] for e in inner if e[0] == "pick_global_escape" and e[1] is not None]
    if tgt in picks:
        return "pick_global_coverage_escape"
    if "corridor" in names:
        return "corridor_waypoints"
    if "finalize" in names:
        return "finalize_only_escape"
    return "other_branch"


def _acted_target(rec: dict):
    """Target the executor actually acted on = last routed target before commit."""
    acts = rec.get("acted_targets") or []
    for cell, kind, via in reversed(acts):
        if cell is not None:
            return cell, via
    return None, None


def _classify(rec: dict) -> tuple[str, list]:
    """Return (exclusive_cause, non_exclusive_flags). Cause is 'agree' if honoured."""
    flags = []
    ws = rec.get("ws_entry") or {}
    gen = rec.get("gen_target_exec") or rec.get("gen_target_planner")
    acted, via = _acted_target(rec)
    label = rec["commit"][-1][1] if rec.get("commit") else ""

    if ws.get("escape_target") is not None:
        flags.append("escape_target_set")
    if ws.get("force_coverage_escape"):
        flags.append("force_coverage")
    if ws.get("force_interior_retarget") or rec.get("near_edge"):
        flags.append("force_interior")
    if rec.get("retarget_fallback"):
        flags.append("retarget_fallback_fired")
    if rec.get("legacy_called"):
        flags.append("legacy_called")
    if rec.get("legacy_target") is not None:
        flags.append("legacy_nonnull")
    if (rec.get("live_victims") or 0) > 0:
        flags.append("live_victim_present")
    if label in ("victim_escape_committed", "victim_stuck_escape"):
        flags.append("live_victim_pursuit_label")
    if any(g[2] != g[0] or g[3] != g[1] for g in (rec.get("gate_calls") or [])):
        flags.append("hazard_gate_changed")
    if rec.get("gen_returned_none"):
        flags.append("generator_returned_none")
    if rec.get("planner_target") is not None:
        flags.append("planner_target_used")

    if gen is not None and acted is not None and gen == acted:
        return "agree", flags

    # disagreement: assign one exclusive cause, highest precedence first
    if label in ("victim_escape_committed", "victim_stuck_escape"):
        return "live_victim_pursuit", flags
    if label in ("hold", "no_managed_direction_hold") or label.startswith("hold"):
        return "hold", flags
    if rec.get("legacy_target") is not None:
        return "legacy_target_source", flags
    if gen is None and not rec.get("gen_calls"):
        if ws.get("escape_target") is not None:
            return "escape_target_routing", flags
        if rec.get("planner_target") is not None:
            return "planner_target_source", flags
        return "generator_not_called_other", flags
    if rec.get("gen_returned_none"):
        return "generator_returned_none", flags
    if ws.get("escape_target") is not None:
        return "escape_target_routing", flags
    if ws.get("force_coverage_escape"):
        return "force_coverage_retarget", flags
    if ws.get("force_interior_retarget") or rec.get("near_edge"):
        return "force_interior_retarget", flags
    if "hazard_gate_changed" in flags:
        return "hazard_gate", flags
    if rec.get("planner_target") is not None and rec.get("planner_target") == acted:
        return "planner_target_source", flags
    return "other", flags


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------
def run_one(scenario: str, wind: str, seed: int, steps: int) -> dict:
    global P
    P = Probe()
    kinds = install_patches()
    P.patch_kinds = kinds

    params = _params(scenario, wind)
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        P.searcher_ids = set(str(x) for x in resolve_victim_searcher_uav_ids(model))
        spawns = _victim_spawns(model)
        wind_dir = str(params["WIND_DIRECTION"])
        # Victims never move, so post-sets are fixed at t=0. The decomposition
        # needs them mid-run, which rules out waiting for never_detected.
        P.posts_by_victim = {
            vid: _legal_posts(wind_dir, vx, vy) for vid, (vx, vy) in spawns.items()
        }

        ever_searcher = {vid: False for vid in spawns}
        ever_any = {vid: False for vid in spawns}
        min_searcher = {vid: float("inf") for vid in spawns}
        min_any = {vid: float("inf") for vid in spawns}

        for step in range(1, steps + 1):
            P.begin_step(step)
            model.step()

            uavs = _uav_agents(model)
            searcher_pos = []
            for a in uavs:
                p = getattr(a, "pos", None)
                if p is None:
                    continue
                pc = (int(p[0]), int(p[1]))
                _mark_obs(P.obs_all, pc[0], pc[1])
                if str(a.unique_id) in P.searcher_ids:
                    searcher_pos.append(pc)
                    _mark_obs(P.obs_searcher, pc[0], pc[1])

            for vid, (vx, vy) in spawns.items():
                for a in uavs:
                    p = getattr(a, "pos", None)
                    if p is None:
                        continue
                    d = math.hypot(float(p[0]) - vx, float(p[1]) - vy)
                    if d < min_any[vid]:
                        min_any[vid] = d
                    if d <= OBS:
                        ever_any[vid] = True
                    if str(a.unique_id) in P.searcher_ids:
                        if d < min_searcher[vid]:
                            min_searcher[vid] = d
                        if d <= OBS:
                            ever_searcher[vid] = True

            fire = _active_fire_cells(model)
            smoke = _smoke_cells(model)
            rec = P.cur
            rec["fire_n"] = len(fire)
            rec["smoke_n"] = len(smoke)
            if P.searcher_ids:
                sws = _wind_search_state(model, sorted(P.searcher_ids)[0])
                rec["ft_boost"] = float(
                    sws.get("fire_tracker_detection_boost", 0.0) or 0.0
                )
                rec["coverage_w"] = round(float(_RAW["_coverage_priority"](sws)), 4)
                rec["coverage_active"] = bool(_RAW["_coverage_mode_active"](sws))
                rec["detections"] = int(
                    sws.get("searcher_victim_detections", 0) or 0
                )
            rec["obs_frac_searcher"] = len(P.obs_searcher) / float(GRID * GRID)
            rec["obs_frac_all"] = len(P.obs_all) / float(GRID * GRID)
            rec["searcher_pos"] = searcher_pos[0] if searcher_pos else None
            rec["branch"] = _gen_branch(rec)
            acted, via = _acted_target(rec)
            rec["acted_target"] = acted
            rec["acted_via"] = via
            cause, flags = _classify(rec)
            rec["cause"] = cause
            rec["flags"] = flags

            # Q7 aggregates every step
            for key in ("bonus_gated", "bonus_ungated", "pen_vals"):
                vals = rec[key]
                if vals:
                    rec[key + "_n"] = len(vals)
                    rec[key + "_min"] = min(vals)
                    rec[key + "_max"] = max(vals)
                    rec[key + "_spread"] = max(vals) - min(vals)
                else:
                    rec[key + "_n"] = 0
                rec[key] = None  # drop raw list, keep memory bounded

            # Q7B per-candidate correlation, only on detail steps.
            # Unobserved counts are cached per unique cell (the same candidate is
            # scored once gated and once ungated, so this halves the disk scans).
            if P.detail and (rec["cand_detail"] or rec["pen_detail"]):
                cache: dict = {}

                def _unobs(cx: int, cy: int):
                    hit = cache.get((cx, cy))
                    if hit is not None:
                        return hit
                    us = ua = 0
                    for dx, dy in _DISK:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < GRID and 0 <= ny < GRID:
                            if (nx, ny) not in P.snap_searcher:
                                us += 1
                            if (nx, ny) not in P.snap_all:
                                ua += 1
                    cache[(cx, cy)] = (us, ua)
                    return us, ua

                by_kind: dict = {"gated": [], "ungated": []}
                for cx, cy, val, kindq in rec["cand_detail"] or []:
                    us, ua = _unobs(cx, cy)
                    by_kind[kindq].append((val, us, ua))
                stats = {}
                for kindq, pairs in by_kind.items():
                    if len(pairs) < 3:
                        continue
                    bv = [p[0] for p in pairs]
                    us = [p[1] for p in pairs]
                    ua = [p[2] for p in pairs]
                    stats[kindq] = {
                        "n": len(pairs),
                        "pearson_searcher": _pearson(bv, us),
                        "spearman_searcher": _spearman(bv, us),
                        "pearson_all": _pearson(bv, ua),
                        "spearman_all": _spearman(bv, ua),
                        "bonus_min": min(bv),
                        "bonus_max": max(bv),
                        "unobs_min": min(us),
                        "unobs_max": max(us),
                        "sample": pairs[:: max(1, len(pairs) // 60)][:60],
                    }

                # Q7B correlates the EFFECTIVE bonus: the total added to one
                # candidate's score across both call sites. Either call's
                # return value alone understates what the term actually does.
                eff = rec["bonus_eff"] or {}
                if len(eff) >= 3:
                    ev, eus, eua, gs, ugs = [], [], [], [], []
                    for (cx, cy), (g, u) in eff.items():
                        a, b = _unobs(cx, cy)
                        ev.append(g + u)
                        eus.append(a)
                        eua.append(b)
                        gs.append(g)
                        ugs.append(u)
                    stats["effective"] = {
                        "n": len(ev),
                        "pearson_searcher": _pearson(ev, eus),
                        "spearman_searcher": _spearman(ev, eus),
                        "pearson_all": _pearson(ev, eua),
                        "spearman_all": _spearman(ev, eua),
                        "bonus_min": min(ev),
                        "bonus_max": max(ev),
                        "unobs_min": min(eus),
                        "unobs_max": max(eus),
                        "gated_mean": sum(gs) / len(gs),
                        "ungated_mean": sum(ugs) / len(ugs),
                        "gated_max": max(gs),
                        "ungated_max": max(ugs),
                        "n_double_counted": sum(
                            1 for g, u in zip(gs, ugs) if g > 0.0 and u > 0.0
                        ),
                        "sample": list(zip(ev, eus, eua))[
                            :: max(1, len(ev) // 60)
                        ][:60],
                    }
                rec["corr_bonus"] = stats

                ppairs = []
                for cx, cy, val in rec["pen_detail"] or []:
                    us, _ua = _unobs(cx, cy)
                    ppairs.append((val, us))
                if len(ppairs) >= 3:
                    pv = [p[0] for p in ppairs]
                    pu = [p[1] for p in ppairs]
                    rec["corr_pen"] = {
                        "n": len(ppairs),
                        "pearson_searcher": _pearson(pv, pu),
                        "spearman_searcher": _spearman(pv, pu),
                        "pen_min": min(pv),
                        "pen_max": max(pv),
                        "sample": ppairs[:: max(1, len(ppairs) // 60)][:60],
                    }
            rec["bonus_eff_n"] = len(rec["bonus_eff"] or {})
            rec["cand_detail"] = None
            rec["pen_detail"] = None
            rec["bonus_eff"] = None

            P.steps.append(rec)

        ev = _build_evaluation(model, None, steps, params)

    elapsed = time.time() - t0
    nd = _nd_ids(ev)

    # ---- Q6 legal observation-post sets, EUCLIDEAN r=8 ----
    posts = {
        vid: P.posts_by_victim.get(vid, [])
        for vid in (sorted(nd) or sorted(spawns))
        if vid in spawns
    }

    return {
        "scenario": scenario,
        "wind": wind,
        "seed": seed,
        "steps": steps,
        "elapsed_s": elapsed,
        "searcher_ids": sorted(P.searcher_ids),
        "patch_kinds": P.patch_kinds,
        "counters": dict(P.counters),
        "spawns": {k: list(v) for k, v in spawns.items()},
        "nd": sorted(nd),
        "eval": {
            "never_detected": ev.get("never_detected"),
            "unreachable_causes": ev.get("unreachable_causes"),
            "rescued": ev.get("rescued"),
        },
        "ever_searcher": ever_searcher,
        "ever_any": ever_any,
        "min_searcher": {k: (None if v == float("inf") else round(v, 2)) for k, v in min_searcher.items()},
        "min_any": {k: (None if v == float("inf") else round(v, 2)) for k, v in min_any.items()},
        "obs_frac_searcher": len(P.obs_searcher) / float(GRID * GRID),
        "obs_frac_all": len(P.obs_all) / float(GRID * GRID),
        "posts": {k: [list(c) for c in v] for k, v in posts.items()},
        "step_records": P.steps,
    }


# --------------------------------------------------------------------------
# worker / main
# --------------------------------------------------------------------------
def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "worker":
        scenario, wind, seed, steps, out_json = (
            argv[1], argv[2], int(argv[3]), int(argv[4]), argv[5]
        )
        res = run_one(scenario, wind, seed, steps)
        c = res["counters"]
        print("PATCH KINDS:", flush=True)
        for k, v in sorted(res["patch_kinds"].items()):
            print("  %-46s %s" % (k, v), flush=True)
        print("RAW COUNTERS:", flush=True)
        for k, v in sorted(c.items()):
            print("  %-40s %d" % (k, v), flush=True)
        fail = []
        if c.get("gen_calls_searcher", 0) <= 0:
            fail.append("gen_calls_searcher == 0")
        if c.get("advance_calls", 0) <= 0:
            fail.append("advance_calls == 0")
        if c.get("commit_calls", 0) <= 0:
            fail.append("commit_calls == 0")
        if c.get("bonus_calls_total", 0) <= 0:
            fail.append("bonus_calls_total == 0")
        if c.get("decomp_ok", 0) <= 0:
            fail.append("decomp_ok == 0 (score decomposition never ran)")
        if c.get("decomp_fail", 0) > 0:
            fail.append("decomp_fail == %d" % c["decomp_fail"])
        # The mirror is only trustworthy if its argmax reproduces the target
        # production actually chose before clamping.
        dec = [
            r["decomp"]
            for r in res["step_records"]
            if isinstance(r.get("decomp"), dict) and "error" not in r["decomp"]
        ]
        agree = sum(1 for d in dec if d.get("mirror_matches_prefinal"))
        with_pre = sum(1 for d in dec if d.get("prefinal"))
        print(
            "MIRROR VALIDATION: %d/%d decompositions reproduce the pre-finalize "
            "argmax (%d had a pre-finalize target)"
            % (agree, len(dec), with_pre),
            flush=True,
        )
        if with_pre and agree == 0:
            fail.append("score mirror never reproduced production's argmax")
        if fail:
            print("PATCH VERIFICATION FAILED: " + "; ".join(fail), flush=True)
            return 3
        print("PATCH VERIFICATION OK", flush=True)
        with open(out_json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f)
        print("wrote %s (%.1fs)" % (out_json, res["elapsed_s"]), flush=True)
        return 0

    steps = int(argv[0]) if argv else STEPS
    jobs = []
    for scenario, wind, seed in RUNS:
        out_json = os.path.join(
            _ROOT, "outputs", "_tf_%s_%s_%d.json" % (scenario, wind, seed)
        )
        jobs.append((scenario, wind, seed, out_json))

    def _run_one(job):
        scenario, wind, seed, out_json = job
        t0 = time.time()
        args = [
            sys.executable, __file__, "worker",
            scenario, wind, str(seed), str(steps), out_json,
        ]
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        log_path = out_json.replace(".json", ".log")
        with open(log_path, "w", encoding="utf-8", newline="\n") as lf:
            proc = subprocess.run(args, env=env, cwd=_ROOT, stdout=lf, stderr=subprocess.STDOUT)
        return scenario, wind, seed, out_json, proc.returncode, time.time() - t0

    print("Python %s" % sys.version.replace("\n", " "), flush=True)
    print("mesa %s" % __import__("mesa").__version__, flush=True)
    print("steps=%d runs=%d" % (steps, len(jobs)), flush=True)
    rc_all = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(_run_one, job) for job in jobs]
        for fut in as_completed(futs):
            s, w, sd, oj, rc, el = fut.result()
            print("  DONE %s/%s seed=%d exit=%d elapsed=%.1fs" % (s, w, sd, rc, el), flush=True)
            rc_all = rc_all or rc
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
