"""Managing system, PLAN: the joint searcher-target allocation post-pass (fix3b, session 3b).

outputs/fix3b_part1.txt sections 3, 4, 5, 6 and 15. Runs once per step, after the per-UAV local path
planners, for SEARCHER_TARGETING 1 (least-observed tile), 2 (Bayes-diffusion) and 3 (Bayes-flee). For each
victim searcher it keeps or chooses ONE target and delivers it in PathDecision.waypoints_by_uav, with the
step marker uncertainty_context['searcher_targeting_step'] that the executor's hook requires. next_action and
selected_option_id are left unchanged, so the dispatcher's yield / hold / return rules apply exactly as today.

HARD CONSTRAINTS (filters, not penalties):
  reachability  the target has an admissible path - the executor's own _targeting_bfs on the same pre-move
                snapshot (one owner for the check and the steps). SEARCHER_TARGETING_REACHABILITY 0 is the
                ablation (choice blind to reachability; never shipped).
  battery       b - 0.3 * L(t) > agents.rtb_trigger_level_at(uav, t) - the live return trigger evaluated at
                the target; L = the admissible path length.
SCORE (Bayes): expected detection gain along the path and at the target, per unit path length, on
  lambda = N_unf * p; two stages (pre-rank by the target disc's mass, exact along-path gain for the top M).
COMMITMENT: a target is held and re-planned only when reached, unreachable (give-up + cooldown), battery-
  infeasible, or swept (its disc mass < rho * at issue). No score-based switching (fix3b_part1.txt 3.5).
COORDINATION: greedy sequential with fictitious non-detection (held targets first, then the free searchers in
  order of their best stand-alone score); SEARCHER_TARGETING_COORDINATION 0 = each on the unconditioned map.
FALLBACK: no feasible target -> no delivery (the current chain steers) and a hold of R steps.
Draws no random numbers. Writes only its own planning state (model._searcher_targeting_state, ..._stats).

BAYESIAN PREPARATION ROUND (outputs/bayesprep_part1.txt; SEARCHER_TARGETING_FIX ships 1, an exact 0 = fix3b):
  F1-b a Bayes leg ends ON its target when the target is admissible (_targeting_route exact); the gain and the
       coordination claims credit only the discs actually flown (never the target's disc from 2 cells short);
  F1-c the swept rule ignores what the holder itself observed since issue ("another UAV or the fire took its mass");
  F1-d the Bayes target pool is mirror-symmetric (edge distance 4 on every side);
  F1-f no strategy steers a searcher whose recall holds this step (it is treated as on a return leg);
  F1-g under P_d < 1 the gain and the claims use the belief's own P_d; F1-h the boxed test uses the candidate filter.
  Ruling R-4 (bayesprep report section 10): the least-observed baseline gets the same edge geometry - the outer tiles'
  anchors at edge distance 4 (the Bayes pool's edge) and the leg ending ON the anchor (tile_layout edge_anchor).
  SEARCHER_TARGETING 5 (front priority): Bayes-flee with lambda weighted, in target preference ONLY, by the urgency
  weight of planning/fire_arrival_estimate.py; the swept rule keeps the unweighted p.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Any

import numpy as np

from ..knowledge.victim_search_belief import dilate, disc_convolve, disc_mask

PER_MOVE = 0.3   # battery per moving step (agents: battery_drain_per_step 0.1 + battery_drain_per_move 0.2)


def _stats(model: Any, uid: str) -> dict:
    stats = getattr(model, "_searcher_targeting_stats", None)
    if not isinstance(stats, dict):
        stats = {}
        model._searcher_targeting_stats = stats
    return stats.setdefault(uid, {})


def _bump(model: Any, uid: str, key: str, n: int = 1) -> None:
    per = _stats(model, uid)
    per[key] = int(per.get(key, 0)) + n


def _issued_log(model: Any) -> list:
    log = getattr(model, "_searcher_targeting_issued", None)
    if not isinstance(log, list):
        log = []
        model._searcher_targeting_issued = log
    return log


def draw_random_walk(model: Any) -> None:
    """SEARCHER_TARGETING 4: one uniform direction per UAV per step from the dedicated stream, consumed
    EVERY step whatever the UAV's state (the stream stays aligned across steps)."""
    rng = getattr(model, "_searcher_rw_rng", None)
    if rng is None:
        return
    step = int(getattr(model, "evaluation_timesteps_counter", 0))
    draws = getattr(model, "_searcher_rw_draws", None)
    if isinstance(draws, dict) and draws.get("step") == step:
        return                                            # at most one draw set per step
    ids = sorted((a.unique_id for a in model.schedule.agents if type(a).__name__ == "UAV"), key=lambda v: int(v))
    model._searcher_rw_draws = {"step": step, "dirs": {str(uid): rng.randrange(4) for uid in ids}}


# ---- least-observed tiles (baseline, fix3b_part1.txt 6.1) -----------------------------------------------
def tile_layout(height: int, width: int, band: int, tile: int, edge_anchor: bool = False) -> list[dict]:
    """The fixed partition: the interior span [band, N-1-band] per axis split into k = max(1, round(span /
    tile)) equal tiles; the outer tiles extend to the grid edge. Anchor = the centre of the interior part.
    edge_anchor (bayesprep R-4, with SEARCHER_TARGETING_FIX): an outer tile's anchor is at edge distance `band`, the
    Bayes pool's edge. The centre anchors leave every grid corner outside the detection disc (50 / 4 / 7: anchors 7
    and 42, the corner (49, 49) is 9.9 from (42, 42)); at 4 / 45 the corner is 5.7 away."""
    def axis(n: int) -> list[tuple[int, int, int]]:
        lo, hi = band, n - 1 - band
        span = hi - lo + 1
        k = max(1, int(round(span / float(tile))))
        edges = [lo + (span * i) // k for i in range(k)] + [hi + 1]
        out = []
        for i in range(k):
            a, b = edges[i], edges[i + 1] - 1
            anchor = (a + b) // 2
            if edge_anchor and k > 1 and i in (0, k - 1):
                anchor = lo if i == 0 else hi
            full_a = 0 if i == 0 else a
            full_b = n - 1 if i == k - 1 else b
            out.append((full_a, full_b, anchor))
        return out

    tiles = []
    for ix, (xa, xb, ax) in enumerate(axis(height)):
        for iy, (ya, yb, ay) in enumerate(axis(width)):
            tiles.append({"index": len(tiles), "x": (xa, xb), "y": (ya, yb), "anchor": (ax, ay)})
    return tiles


def _tile_ages(belief: Any, tiles: list[dict], burning: set, smoke: set, now: int) -> dict[int, float | None]:
    age = np.where(belief.last_cover >= 0, now - belief.last_cover, now + 1).astype(np.float64)
    searchable = np.ones_like(age, dtype=bool)
    for x, y in burning | smoke:
        if 0 <= x < age.shape[0] and 0 <= y < age.shape[1]:
            searchable[x, y] = False
    out: dict[int, float | None] = {}
    for t in tiles:
        (xa, xb), (ya, yb) = t["x"], t["y"]
        block = age[xa:xb + 1, ya:yb + 1][searchable[xa:xb + 1, ya:yb + 1]]
        out[t["index"]] = float(block.mean()) if block.size else None
    return out


def _mirror_axis(n: int, band: int, stride: int) -> list[int]:
    """bayesprep F1-d: the stride lattice from the low edge band up to the middle, plus its mirror image - the
    edge distance is `band` on BOTH sides (the fix3b lattice range(band, n - band, stride) reaches 4 on the low side
    but 5 on the high side when the interior span is even). 50 / 4 / 2: {4, 6, ..., 24} + {25, 27, ..., 45}."""
    half = list(range(band, (n + 1) // 2, stride))
    return sorted(set(half) | {n - 1 - v for v in half})


def _searcher_recalled(agent: Any) -> bool:
    """bayesprep F1-f: the agent's own one-owner predicate UAV._searcher_recall_will_act - the recall holds AND
    _apply_return_to_base acts on it this step (review R1-2)."""
    fn = getattr(agent, "_searcher_recall_will_act", None)
    return bool(fn()) if callable(fn) else False


# ---- the post-pass -----------------------------------------------------------------------------------
def apply_searcher_targeting(path_decisions: dict, runtime_models: Any) -> dict:
    """Return path_decisions with a target delivered to each searcher that has a feasible one. Inert (the
    same dict, untouched) unless SEARCHER_TARGETING is 1, 2, 3 or 5 and the belief exists."""
    import agents as agents_module                                       # lazy: a root module
    from ..adaptation.local_adaptation_generator import resolve_victim_searcher_uav_ids
    from ..execution.uav_executor import UAVExecutor

    mode = agents_module.searcher_targeting()
    bayes = agents_module.SEARCHER_TARGETING_BAYES
    if mode not in (1,) + bayes or not isinstance(runtime_models, dict):
        return path_decisions
    model = runtime_models.get("simulation_model")
    belief = getattr(model, "victim_search_belief", None)
    if model is None or belief is None:
        return path_decisions
    t0 = time.perf_counter()
    step = int(getattr(model, "evaluation_timesteps_counter", 0))
    f = agents_module.fix3b_param
    G = max(0, int(f("SEARCHER_TARGETING_GIVEUP_COOLDOWN", 15)))
    R = max(0, int(f("SEARCHER_TARGETING_FALLBACK_HOLD", 10)))
    M = max(1, int(f("SEARCHER_TARGETING_TOP_M", 12)))
    L0 = max(1.0, f("SEARCHER_TARGETING_L0", 4))
    rho = f("SEARCHER_TARGETING_SWEPT_RHO", 0.25)
    stride = max(1, int(f("SEARCHER_BELIEF_STRIDE", 2)))
    tile_size = max(1, int(f("SEARCHER_TARGETING_TILE", 7)))
    age_bucket = max(1.0, f("SEARCHER_TARGETING_AGE_BUCKET", 10))
    # a lower bound of every value rtb_trigger_level_at can return (max(reserve >= 0, 0.3 d + margin), or
    # CRITICAL without a berth / below BASE_STATION_MODE 2): a budget at or under it is infeasible, no call needed
    margin = min(float(agents_module.base_station_return_margin()), float(agents_module.battery_critical_threshold()))
    band = int(agents_module.SEARCHER_EDGE_BAND)
    coordination = agents_module.searcher_targeting_coordination()
    reach_on = agents_module.searcher_targeting_reachability()
    battery_on = agents_module.searcher_targeting_battery()
    fix = agents_module.searcher_targeting_fix()                          # bayesprep item 1
    H, W = belief.height, belief.width
    offsets = belief.offsets

    states = getattr(model, "_searcher_targeting_state", None)
    if not isinstance(states, dict):
        states = {}
        model._searcher_targeting_state = states
    agents_by_id = {str(a.unique_id): a for a in model.schedule.agents if type(a).__name__ == "UAV"}
    burning, smoke = model._fix3b_true_fire()

    # ---- eligible searchers and their admissible BFS (the executor's own) -------------------------------
    elig: dict[str, dict] = {}
    for uid in sorted(resolve_victim_searcher_uav_ids(model), key=lambda v: int(v)):
        uid = str(uid)
        pd = path_decisions.get(uid)
        agent = agents_by_id.get(uid)
        st = states.setdefault(uid, {"target": None, "s_issue": 0.0, "tile": None, "cooldown": [],
                                     "fallback_until": -1})
        if pd is None or agent is None or agent.pos is None:
            continue
        if fix and st.get("own") is not None:
            # F1-c: the holder's own footprint since issue (its disc at the cell the belief last measured it in)
            st["own"] |= disc_mask(H, W, [(int(agent.pos[0]), int(agent.pos[1]))], offsets)
        on_return = (getattr(agent, "rtb_active", False) or getattr(agent, "rtb_docked", False)
                     or str(getattr(pd, "selected_option_id", "") or "").startswith("local_path_return_to_base"))
        # F1-f: a searcher whose recall holds this step returns now (UAV.advance) - no strategy steers it, exactly
        # as one already on a return leg, so the current chain runs on that step as in every other arm.
        recalled = (not on_return) and fix and _searcher_recalled(agent)
        if on_return or recalled:
            if st["target"] is not None:
                _bump(model, uid, "drop_recall" if recalled else "drop_return_leg")
                st["target"], st["tile"] = None, None
                if fix:
                    st["own"], st["p_issue"] = None, None
            if recalled:
                _bump(model, uid, "skip_recall")
            continue
        ex = UAVExecutor(uid, model, agent)
        here = (int(agent.pos[0]), int(agent.pos[1]))
        if not ex._route_fire_field_active():
            _bump(model, uid, "skip_route_field_inactive")      # the hook would not steer (review LOW-5)
            continue
        if ex._strict_victim_hazard_level(here) > 0:
            _bump(model, uid, "skip_onhazard")
            continue
        st["cooldown"] = [c for c in st["cooldown"] if c[2] > step]      # issued at s, excluded s+1 .. s+G
        elig[uid] = {"agent": agent, "ex": ex, "here": here, "bfs": ex._targeting_bfs(agent, model), "st": st}

    # RULING R-1 - ONE OWNER TO THE END: once every victim is detected (N_unf = 0) a Bayes arm continues with
    # the least-observed rule (the mode-1 rule, unchanged) instead of handing the searcher back to the current
    # chain. eff is the rule in force this step.
    eff = 1 if (mode == 1 or belief.n_unfound == 0) else mode
    d_min = max(1, int(f("SEARCHER_TARGETING_MIN_DIST", 5)))
    lam = belief.intensity() if eff in bayes else None
    fp_ms = None
    if lam is not None and eff == 5:
        # FRONT PRIORITY (bayesprep item 2): lambda weighted by the urgency of the estimated fire arrival - in the
        # pre-rank, the gain and the claims only (the belief and the swept rule never see the weight). The wind is
        # the managing system's own reading (A4), the fire the pre-move snapshot (A3).
        from .fire_arrival_estimate import front_priority_params, urgency_weight
        t_fp = time.perf_counter()
        ex0 = next(iter(elig.values()))["ex"] if elig else None
        if ex0 is not None:
            wind = UAVExecutor._wind_vector_from_direction(ex0._get_wind_direction(model))
            lam = lam * urgency_weight(H, W, burning, wind, front_priority_params())
        fp_ms = round((time.perf_counter() - t_fp) * 1000.0, 3)
    # F1-g: under P_d < 1 (the PD_SMOKE sensitivity) the planner credits the leg with the belief's OWN detection model:
    # the belief applies P_d once per step a cell lies inside the moving disc, so a cell seen k times along the leg is
    # detected with 1 - (1 - P_d)^k (review R1-1: one credit per path under-counted a cell flown past 7 times).
    # The coordination claims keep the matching non-detection product. P_d = 1 everywhere: the fix3b arithmetic.
    pd_v = f("SEARCHER_BELIEF_PD", 1.0)
    pd_s = f("SEARCHER_BELIEF_PD_SMOKE", 1.0)
    pd_on = fix and lam is not None and (pd_v != 1.0 or pd_s != pd_v)
    pd_grid = None
    if pd_on:
        pd_grid = np.full((H, W), float(pd_v))
        if pd_s != pd_v:
            for x, y in smoke:
                if 0 <= x < H and 0 <= y < W:
                    pd_grid[x, y] = float(pd_s)

    nd = np.ones((H, W)) if pd_on else None        # F1-g: the claims' non-detection product (P_d < 1 only)

    def gain_field(field_: np.ndarray) -> np.ndarray:
        """The pre-rank's field: one look at the target (P_d-weighted under F1-g)."""
        return field_ * pd_grid if pd_on else field_

    def unclaimed(field_: np.ndarray, claimed_: np.ndarray) -> np.ndarray:
        return field_ * nd if pd_on else field_ * ~claimed_

    def looks(path: np.ndarray, start: tuple[int, int]) -> np.ndarray:
        """F1-g: per cell, how many steps of the leg it lies inside the disc (the start's look is already made)."""
        moves = path.copy()
        moves[start] = False
        return disc_convolve(moves.astype(np.float64), offsets)

    def detected(k: np.ndarray) -> np.ndarray:
        return 1.0 - np.power(1.0 - pd_grid, k)

    # The swept rule compares the held target's disc mass of p (one victim's posterior), so a detection
    # elsewhere (N_unf falls) does not 'sweep' it (review LOW-3).
    Sp = disc_convolve(belief.p, offsets) if lam is not None else None
    tiles = tile_layout(H, W, band, tile_size, edge_anchor=fix) if eff == 1 else []       # R-4: edge anchors
    ages = _tile_ages(belief, tiles, burning, smoke, step) if eff == 1 else {}

    if fix and mode in bayes:                                        # F1-d: mirror-symmetric
        pool_cells = [(x, y) for x in _mirror_axis(H, band, stride) for y in _mirror_axis(W, band, stride)]
    else:
        pool_cells = [(x, y) for x in range(band, H - band) for y in range(band, W - band)
                      if x % stride == 0 and y % stride == 0]      # non-band stride lattice (both arms)

    def path_mask(e: dict, cell: tuple[int, int]) -> np.ndarray:
        mask = np.zeros((H, W), dtype=bool)
        parent = e["bfs"]["parent"] if e["bfs"] else {}
        cur = cell
        if cur not in parent:
            mask[cell] = True
            return mask
        while cur is not None:
            mask[cur] = True
            cur = parent.get(cur)
        return mask

    def length(e: dict, goal: tuple[int, int], exact: bool = False) -> tuple[int | None, tuple[int, int] | None]:
        """(L, route cell) by the admissible BFS; with the reachability ablation, Manhattan (no cell). exact (F1-b):
        the leg ends ON the goal when the goal is admissible."""
        route = UAVExecutor._targeting_route(e["bfs"], goal, exact=exact)
        if route is not None:
            return route[1], route[0]
        if not reach_on:
            return abs(goal[0] - e["here"][0]) + abs(goal[1] - e["here"][1]), None
        return None, None

    def battery_ok(e: dict, goal: tuple[int, int], L: int) -> bool:
        if not battery_on:
            return True
        agent = e["agent"]
        budget = float(agent.battery_level) - PER_MOVE * float(L + 2)    # + the goal radius (review LOW-2)
        if budget <= margin:                       # the trigger is >= the margin: infeasible, no call needed
            return False
        return budget > agents_module.rtb_trigger_level_at(agent, goal)

    def swept(st: dict, goal: tuple[int, int]) -> str | None:
        """The swept rule (3.5 d). F1-c (fix on): on the target disc MINUS what the holder's own discs covered since
        issue, compared with the single-victim posterior at issue - so only another UAV, the fire or motion sweeps
        it; with nothing left uncovered by the holder the target is reached by cover. Fix off: the fix3b rule."""
        if fix and st.get("p_issue") is not None and st.get("own") is not None:
            rem = disc_mask(H, W, [goal], offsets) & ~st["own"]
            if not rem.any():
                return "drop_covered"
            ref = float(st["p_issue"][rem].sum())
            if ref > 0.0 and float(belief.p[rem].sum()) < rho * ref:
                return "drop_swept"
            return None
        return "drop_swept" if float(Sp[goal]) < rho * float(st["s_issue"]) else None

    def cooled(e: dict, cell: tuple[int, int]) -> bool:
        return any(abs(cell[0] - c[0]) + abs(cell[1] - c[1]) <= 3 for c in e["st"]["cooldown"])

    # ---- 1. held targets: keep, or drop by (a)-(d) -------------------------------------------------------
    claimed = np.zeros((H, W), dtype=bool)        # union of discs along the assigned paths (coordination)
    claimed_tiles: set = set()
    for uid, e in elig.items():
        st = e["st"]
        if st["target"] is None:
            continue
        goal = tuple(st["target"])
        # Re-checked EVERY step on the admissible BFS (also under the reachability ablation: the steer
        # cannot follow a target without an admissible path, so it is given up - which is the ablation's
        # failure mode, measured).
        exact = bool(fix and st.get("exact"))
        route = UAVExecutor._targeting_route(e["bfs"], goal, exact=exact)
        cell = route[0] if route is not None else None
        reason = None
        if route is None:
            reason = "giveup_unreachable"
        elif route[1] == 0:
            reason = "drop_reached"
        elif not battery_ok(e, goal, route[1]):
            reason = "drop_battery"
        elif eff == 1 and mode in bayes and st["tile"] is None:
            reason = "drop_all_detected"     # a Bayes point target when the search is complete (R-1)
        elif eff in bayes:
            reason = swept(st, goal)
        if reason is not None:
            _bump(model, uid, reason)
            if reason == "giveup_unreachable":
                st["cooldown"].append((goal[0], goal[1], step + G))
            st["target"], st["tile"] = None, None
            if fix:
                st["own"], st["p_issue"] = None, None
            continue
        e["route_cell"] = cell
        if coordination:
            if exact:     # F1-b: claim the discs the leg flies, not the target's disc from 2 cells short
                flown = path_mask(e, cell) if cell is not None else _point(H, W, goal)
                claimed |= dilate(flown, offsets)
                if pd_on:
                    nd *= np.power(1.0 - pd_grid, looks(flown, e["here"]))
            else:
                claimed |= dilate(path_mask(e, cell if cell is not None else goal) | _point(H, W, goal), offsets)
            if st["tile"] is not None:
                claimed_tiles.add(st["tile"])

    # ---- 2. free searchers choose (greedy sequential) ------------------------------------------------------
    def choose(e: dict, lam_cond: np.ndarray | None, taken_tiles: set) -> dict | None:
        here = e["here"]
        if eff == 1:
            best = None
            for t in tiles:
                if t["index"] in taken_tiles or ages.get(t["index"]) is None:
                    continue
                a = t["anchor"]
                if abs(a[0] - here[0]) + abs(a[1] - here[1]) <= 2 or cooled(e, a):
                    continue
                L, cell = length(e, a, exact=fix)                    # R-4: the leg ends ON the anchor
                if L is None or L == 0 or not battery_ok(e, a, L):
                    continue
                key = (int(ages[t["index"]] // age_bucket), -L, -t["index"])
                if best is None or key > best[0]:
                    best = (key, a, L, t["index"], cell)
            if best is None:
                return None
            return {"target": best[1], "L": best[2], "tile": best[3], "G": None, "S": None,
                    "score": float(best[0][0]), "cell": best[4]}
        S_c = disc_convolve(gain_field(lam_cond), offsets)
        cands = []
        for c in pool_cells:
            if abs(c[0] - here[0]) + abs(c[1] - here[1]) <= 2 or cooled(e, c):
                continue
            s = float(S_c[c])
            if s <= 0.0:
                continue
            L, cell = length(e, c, exact=fix)
            if L is None or L < d_min:          # the minimum target distance (R-1; >= 1 also excludes 'reached')
                continue
            cands.append((s / max(float(L), L0), s, L, c, cell))
        cands.sort(key=lambda r: (-r[0], r[2], r[3]))
        top = []
        for r in cands:
            if battery_ok(e, r[3], r[2]):
                top.append(r)
                if len(top) >= M:
                    break
        best = None
        for pre, s, L, c, cell in top:
            k = None
            if fix:       # F1-b: the gain is what the leg flies - the path to the cell it ends at (c when admissible)
                flown = path_mask(e, cell) if cell is not None else _point(H, W, c)
                mask = dilate(flown, offsets)
                if pd_on:
                    k = looks(flown, here)
            else:
                mask = dilate(path_mask(e, cell if cell is not None else c) | _point(H, W, c), offsets)
            g = float((lam_cond * detected(k)).sum()) if k is not None else float(lam_cond[mask].sum())
            score = g / max(float(L), L0)
            key = (score, -L, (-c[0], -c[1]))
            if best is None or key > best[0]:
                best = (key, c, L, g, s, cell, mask, k)
        if best is None:
            return None
        return {"target": best[1], "L": best[2], "G": best[3], "S": float(Sp[best[1]]), "tile": None,
                "score": best[0][0], "cell": best[5], "mask": best[6], "looks": best[7]}

    free = [uid for uid, e in elig.items() if e["st"]["target"] is None]
    in_hold = [uid for uid in free if elig[uid]["st"]["fallback_until"] > step]
    for uid in in_hold:
        _bump(model, uid, "fallback_steps")
    free = [uid for uid in free if uid not in in_hold]
    if eff in bayes:
        base = unclaimed(lam, claimed) if coordination else lam
        alone = {uid: choose(elig[uid], base, set()) for uid in free}
        order = sorted(free, key=lambda u: (-(alone[u]["score"] if alone[u] else -1.0), int(u)))
    else:
        alone = {uid: None for uid in free}
        order = list(free)
    lam_cur = unclaimed(lam, claimed) if (lam is not None and coordination) else lam
    for uid in order:
        e = elig[uid]
        pick = choose(e, lam_cur if coordination else lam, claimed_tiles if coordination else set())
        if pick is None:
            # Review MEDIUM-1: a searcher boxed in only by other UAVs (a crowded depot at launch) is not
            # held off for R steps - the current chain moves it this step and the strategy retries next step.
            # "Boxed by UAVs" = the admissible BFS reaches NO candidate cell at all, while the same search
            # without the other-UAV cells does (not merely "nothing worth targeting", which still holds).
            def any_candidate(bfs):
                cands = pool_cells
                if fix and mode in bayes:     # F1-h: the candidate filter's own rule (Manhattan > 2 from here)
                    here_ = e["here"]
                    cands = [c for c in pool_cells if abs(c[0] - here_[0]) + abs(c[1] - here_[1]) > 2]
                return bfs is not None and any(UAVExecutor._targeting_route(bfs, c) for c in cands)

            free_bfs = e["ex"]._targeting_bfs(e["agent"], model, ignore_uavs=True) if e["bfs"] else None
            if not any_candidate(e["bfs"]) and any_candidate(free_bfs):
                _bump(model, uid, "fallback_boxed_by_uavs")
                continue
            e["st"]["fallback_until"] = step + R
            _bump(model, uid, "fallback_entries")
            _bump(model, uid, "fallback_steps")
            continue
        e["st"]["target"] = [int(pick["target"][0]), int(pick["target"][1])]
        e["st"]["tile"] = pick["tile"]
        e["st"]["s_issue"] = float(pick["S"]) if pick["S"] is not None else 0.0
        if fix and eff in bayes:
            # F1-b / F1-c: an exact-goal Bayes target; the posterior at issue and the holder's own footprint
            e["st"]["exact"] = True
            e["st"]["p_issue"] = belief.p.copy()
            e["st"]["own"] = disc_mask(H, W, [e["here"]], offsets)
        elif fix:     # a least-observed anchor (eff 1): R-4, its leg ends ON the anchor as a Bayes leg does
            e["st"]["exact"], e["st"]["p_issue"], e["st"]["own"] = True, None, None
        e["route_cell"] = pick["cell"]
        _bump(model, uid, "selections")
        reachable_at_issue = UAVExecutor._targeting_route(e["bfs"], tuple(pick["target"])) is not None
        _issued_log(model).append([step, uid, e["st"]["target"], int(pick["L"]),
                                   None if pick["G"] is None else round(pick["G"], 5),
                                   None if pick["S"] is None else round(pick["S"], 5), bool(reachable_at_issue)])
        if coordination:
            if eff == 1:
                claimed_tiles.add(pick["tile"])
            else:
                claimed |= pick["mask"]
                if pd_on and pick.get("looks") is not None:
                    nd *= np.power(1.0 - pd_grid, pick["looks"])
                lam_cur = unclaimed(lam, claimed)

    # ---- 3. delivery -------------------------------------------------------------------------------------
    out = dict(path_decisions)
    for uid, e in elig.items():
        st = e["st"]
        if st["target"] is None:
            continue
        pd = out[uid]
        target = (float(st["target"][0]), float(st["target"][1]))
        ctx = dict(getattr(pd, "uncertainty_context", None) or {})
        ctx["searcher_targeting_target"] = [int(st["target"][0]), int(st["target"][1])]
        ctx["searcher_targeting_step"] = step
        if fix and st.get("exact"):
            ctx["searcher_targeting_exact"] = True        # F1-b: the hook routes to the goal itself
        out[uid] = dataclasses.replace(pd, waypoints_by_uav={uid: (target,)}, uncertainty_context=ctx)
        _bump(model, uid, "delivered_steps")
        if eff == 1 and mode in bayes:
            _bump(model, uid, "lo_continuation_steps")
    timing = getattr(model, "_searcher_targeting_timing", None)
    if not isinstance(timing, dict):
        timing = {"belief_ms": [], "plan_ms": []}
        model._searcher_targeting_timing = timing
    timing["plan_ms"].append(round((time.perf_counter() - t0) * 1000.0, 3))
    if fp_ms is not None:
        timing.setdefault("fp_ms", []).append(fp_ms)
    return out


def _point(h: int, w: int, cell: tuple[int, int]) -> np.ndarray:
    mask = np.zeros((h, w), dtype=bool)
    if 0 <= cell[0] < h and 0 <= cell[1] < w:
        mask[cell] = True
    return mask
