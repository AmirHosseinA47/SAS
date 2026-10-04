"""Bayesian preparation round (outputs/bayesprep_part1.txt; rulings in its section 10). One test per change; each
FAILS with that change removed (verified red in Part 2). Every test sets its own configuration through monkeypatch.

  item 1  SEARCHER_TARGETING_FIX (ships 1): F1-a reflecting walk, F1-b the leg ends on its target and the gain is
          what is flown, F1-c the holder never sweeps its own target, F1-d mirror-symmetric pool, F1-f no steer for a
          recalled / returning / docked searcher, F1-g the gain uses the belief's P_d, F1-h the boxed test
  item 2  SEARCHER_TARGETING 5 (front priority): the arrival-time estimate, the weight, preference only
  item 5  UAV_DOCKED_NOT_OBSTACLE (ships 1): the move rule, no co-docking, no release under another UAV, the global
          collision check counts airborne UAVs only
"""
from __future__ import annotations

import math

import numpy as np
import pytest

import agents
import common_fixed_variables as cfv
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.knowledge.victim_search_belief import MotionParams, VictimSearchBelief, disc_convolve, dilate
from src_extension.planning import fire_arrival_estimate as fae
from src_extension.planning import searcher_targeting as stg
from test_searcher_targeting import STEP, _plan, _shipped, _target, _uav, _world  # noqa: F401 (fixture)

H = W = 50
MX, MY = (1, 0, -1, 0), (0, -1, 0, 1)


# ============================================================================ switches
def test_the_new_switches_ship_on():
    src = open(cfv.__file__, encoding="utf-8").read()
    assert "\nSEARCHER_TARGETING_FIX = 1\n" in src
    assert "\nUAV_DOCKED_NOT_OBSTACLE = 1\n" in src
    assert "\nSEARCHER_TARGETING = 0\n" in src                      # front priority (5) ships OFF


@pytest.mark.parametrize("name,fn", [("SEARCHER_TARGETING_FIX", agents.searcher_targeting_fix),
                                     ("UAV_DOCKED_NOT_OBSTACLE", agents.uav_docked_not_obstacle)])
@pytest.mark.parametrize("raw,on", [(1, True), (0, False), (0.0, False), ("0", False), (False, False),
                                    (0.5, True), ("junk", True), (None, True)])
def test_the_new_switches_turn_off_only_on_an_exact_zero(monkeypatch, name, fn, raw, on):
    monkeypatch.setattr(cfv, name, raw, raising=False)
    assert fn() is on


def test_front_priority_is_a_bayes_strategy_with_the_flee_belief(monkeypatch):
    import wildfire_model as wf

    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", 5, raising=False)
    assert agents.searcher_targeting() == 5 and agents.searcher_targeting_uses_belief()
    assert 5 in agents.SEARCHER_TARGETING_BAYES
    m5 = wf.WildFireModel._fix3b_motion_params(None)
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", 3, raising=False)
    m3 = wf.WildFireModel._fix3b_motion_params(None)
    assert m5 == m3 and m5.mode == "flee"                           # the weight is in the plan only


# ============================================================================ F1-a reflecting walk
@pytest.mark.parametrize("mode", ["diffusion", "flee"])
def test_the_lazy_walk_reflects_so_a_uniform_belief_stays_uniform(mode):
    """No fire, no measurement: a reflecting lazy walk is doubly stochastic, so the uniform belief is stationary.
    The fix3b rule (q / k per available neighbour) drains the edge rows and the corners."""
    for reflect in (True, False):
        b = VictimSearchBelief.with_uniform_prior(H, W, 1, excluded=())
        q = dict(q=0.3) if mode == "diffusion" else dict(q_calm=0.3)
        for _ in range(200):
            b.predict(set(), MotionParams(mode=mode, reflect=reflect, **q))
        u = 1.0 / (H * W)
        if reflect:
            assert np.max(np.abs(b.p - u)) < 1e-12
        else:
            assert b.p[0, 0] < 0.8 * u and b.p[0, 25] < 0.95 * u


def test_the_reflecting_walk_does_not_push_mass_off_a_burning_neighbour():
    """'Fire-agnostic in direction' (design 2.4): next to a burning cell, the reflecting diffusion keeps the blocked
    move's share on the cell; the fix3b rule re-routes it to the other neighbours (a fire repulsion)."""
    for reflect, expect_stay in ((True, 1.0 - 0.1 + 0.1 / 4.0), (False, 0.9)):
        b = VictimSearchBelief.with_uniform_prior(H, W, 1, excluded=())
        b.p[:, :] = 0.0
        b.p[25, 25] = 1.0
        b.predict({(26, 25)}, MotionParams(mode="diffusion", q=0.1, reflect=reflect))
        assert abs(b.p[25, 25] - expect_stay) < 1e-12


@pytest.mark.parametrize("fix,reflect", [(1, True), (0, False)])
def test_the_model_reflects_with_the_fix(monkeypatch, fix, reflect):
    import wildfire_model as wf

    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", 3, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", fix, raising=False)
    assert wf.WildFireModel._fix3b_motion_params(None).reflect is reflect


# ============================================================================ F1-b the leg ends on its target
def test_the_route_ends_on_an_admissible_goal_and_falls_back_to_the_ball():
    bfs = {"dist": {(10, 10): 0, (11, 10): 1, (12, 10): 2, (13, 10): 3, (14, 10): 4}}
    assert UAVExecutor._targeting_route(bfs, (14, 10), exact=True) == ((14, 10), 4)
    assert UAVExecutor._targeting_route(bfs, (14, 10)) == ((12, 10), 2)                  # fix3b: 2 short
    assert UAVExecutor._targeting_route(bfs, (15, 10), exact=True) == ((13, 10), 3)      # goal blocked: the ball


def _path_mask(bfs, cell):
    mask = np.zeros((H, W), dtype=bool)
    cur = cell
    while cur is not None:
        mask[cur] = True
        cur = bfs["parent"].get(cur)
    return mask


@pytest.mark.parametrize("fix", [1, 0])
def test_an_edge_leg_ends_on_its_target_and_its_gain_is_what_is_flown(_shipped, monkeypatch, fix):
    """Three equal masses on the west edge column (0, 18), (0, 24), (0, 30): the best target is the band-boundary
    cell (4, 24), whose disc holds all three. With the fix the leg ends ON (4, 24) and the issued gain equals the
    mass under the discs actually flown. fix3b (0): the leg ends 2 short at (6, 24), whose disc misses (0, 18) and
    (0, 30), while the gain still credits them (the over-credit)."""
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", fix, raising=False)
    mass = {(0, 18): 1.0, (0, 24): 1.0, (0, 30): 1.0}
    model, (u,), dec = _world([(2502, (20, 24), 100.0)], mass, monkeypatch=monkeypatch)
    out = _plan(model, dec)
    t = _target(out, 2502)
    assert t == (4, 24)
    ex = UAVExecutor("2502", model, u)
    bfs = ex._targeting_bfs(u, model)
    route = UAVExecutor._targeting_route(bfs, t, exact=bool(fix))
    issued_g = model._searcher_targeting_issued[-1][4]
    flown = float((model.victim_search_belief.intensity())[dilate(_path_mask(bfs, route[0]), model.victim_search_belief.offsets)].sum())
    if fix:
        assert route[0] == t and out["2502"].uncertainty_context.get("searcher_targeting_exact") is True
        assert abs(issued_g - round(flown, 5)) < 1e-9
    else:
        assert route[0] == (6, 24) and "searcher_targeting_exact" not in out["2502"].uncertainty_context
        assert issued_g > flown + 0.5                                  # credits a disc never flown
    # the hook steers along the same rule (one owner): it passes the planner's exact flag to the route rule
    ex._read_uav_role = lambda: "victim_searcher"  # type: ignore[method-assign]
    seen = []
    orig = UAVExecutor._targeting_route
    monkeypatch.setattr(UAVExecutor, "_targeting_route",
                        staticmethod(lambda b, g, exact=False: seen.append(exact) or orig(b, g, exact=exact)))
    d, label = ex._searcher_targeting_direction(u, out["2502"], model)
    assert label == UAVExecutor.TARGETING_LABEL and bfs["first"][route[0]] == d
    assert seen == [bool(fix)]


# ============================================================================ F1-c the holder never sweeps its own target
def _fly(model, u, dec, steps):
    """Step the stand-in world: plan, take the hook's step, measure the holder's new disc (the only UAV)."""
    ex = UAVExecutor("2502", model, u)
    ex._read_uav_role = lambda: "victim_searcher"  # type: ignore[method-assign]
    for _ in range(steps):
        out = _plan(model, dec)
        stats = model._searcher_targeting_stats.setdefault("2502", {})
        drops = {k: v for k, v in stats.items() if k.startswith(("drop_", "giveup_"))}
        if drops:
            return drops, u.pos
        step = ex._searcher_targeting_direction(u, out["2502"], model)
        if step is None:
            return {"no_steer": 1}, u.pos
        u.pos = (u.pos[0] + MX[step[0]], u.pos[1] + MY[step[0]])
        model.evaluation_timesteps_counter += 1
        model.victim_search_belief.measure([u.pos], set(), model.evaluation_timesteps_counter)
    return {}, u.pos


@pytest.mark.parametrize("fix", [1, 0])
def test_the_holders_own_approach_never_sweeps_its_target(_shipped, monkeypatch, fix):
    """A fresh (uniform) belief, the searcher in the SW quadrant: on its way to a corner-ward target its own discs
    cover most of the target disc. With the fix the swept rule ignores the holder's own looks - the leg ends ON the
    target (drop_reached there). fix3b (0): the holder's own approach 'sweeps' the target before it arrives."""
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", fix, raising=False)
    mass = {(x, y): 1.0 for x in range(H) for y in range(W)}
    for x in range(0, 9):
        for y in range(0, 9):
            mass[(x, y)] = 6.0                                         # a rich SW corner
    model, (u,), dec = _world([(2502, (20, 20), 100.0)], mass, monkeypatch=monkeypatch)
    model.victim_search_belief.measure([u.pos], set(), STEP)
    drops, pos = _fly(model, u, dec, 40)
    target = tuple(model._searcher_targeting_issued[0][2])
    if fix:
        assert drops == {"drop_reached": 1} and pos == target, (drops, pos, target)
    else:
        assert drops.get("drop_swept") == 1, (drops, pos, target)


def test_another_uavs_disc_still_sweeps_the_target(_shipped, monkeypatch):
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", 1, raising=False)
    model, (u,), dec = _world([(2502, (25, 10), 100.0)], {(25, 30): 1.0, (5, 45): 1.0}, monkeypatch=monkeypatch)
    t = _target(_plan(model, dec), 2502)
    assert t is not None and (t[0] - 25) ** 2 + (t[1] - 30) ** 2 <= 64
    model.victim_search_belief.measure([(25, 31)], set(), STEP + 1)    # ANOTHER UAV's disc over the target's mass
    model.evaluation_timesteps_counter += 1
    _plan(model, dec)
    assert model._searcher_targeting_stats["2502"].get("drop_swept") == 1


# ============================================================================ F1-d mirror-symmetric pool
def test_the_pool_axis_is_mirror_symmetric():
    axis = stg._mirror_axis(50, 4, 2)
    assert axis == list(range(4, 25, 2)) + list(range(25, 46, 2))
    assert sorted(49 - v for v in axis) == axis and min(axis) == 4 and max(axis) == 45


@pytest.mark.parametrize("fix", [1, 0])
def test_the_planner_uses_the_symmetric_pool_with_the_fix(_shipped, monkeypatch, fix):
    """Mass only on the far east corner cell (49, 49): with the fix a target on x = 45 / y = 45 (edge distance 4,
    as on the west side) is available; the fix3b pool stops at 44 (edge distance 5)."""
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", fix, raising=False)
    model, (u,), dec = _world([(2502, (35, 35), 100.0)], {(49, 49): 1.0}, monkeypatch=monkeypatch)
    t = _target(_plan(model, dec), 2502)
    assert t is not None
    assert (max(t) == 45) is bool(fix), t


# ============================================================================ F1-f recall / return legs
@pytest.mark.parametrize("fix", [1, 0])
def test_a_recalled_searcher_is_not_steered_on_the_recall_step(_shipped, monkeypatch, fix):
    """Every victim detected (n_unfound 0) and the recall holds for this searcher: with the fix the post-pass
    treats it as on a return leg - no target, no delivery; fix3b: one R-1 least-observed delivery."""
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", fix, raising=False)
    model, (u,), dec = _world([(2502, (25, 10), 100.0)], {(25, 22): 1.0}, monkeypatch=monkeypatch)
    model.victim_search_belief.detected_ids.add("victim_0")
    u.rtb_berth = (46, 3)
    u._searcher_recall_active = lambda: True                           # the agent's own predicate
    out = _plan(model, dec)
    stats = model._searcher_targeting_stats.get("2502", {})
    if fix:
        assert _target(out, 2502) is None and stats.get("skip_recall") == 1 and not stats.get("lo_continuation_steps")
    else:
        assert _target(out, 2502) is not None and stats.get("lo_continuation_steps") == 1


def test_on_a_real_model_the_recall_step_gets_no_targeting_delivery(monkeypatch):
    """A real WildFireModel at SEARCHER_TARGETING 3 with the fix: every victim is marked detected after step 3; on
    step 4 every searcher's post-pass skips it (skip_recall), nothing is delivered, and UAV.advance starts the recall
    on that same step (the trip marked recall, triggered at step 4). review R1-4."""
    import random
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import resolve_victim_searcher_uav_ids

    rng = random.Random(9613)
    for mod in (cfv, wf):
        monkeypatch.setattr(mod, "SYSTEM_RANDOM", rng, raising=False)
    monkeypatch.setattr(agents, "random", rng, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", 3, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", 1, raising=False)
    monkeypatch.setattr(cfv, "VICTIM_SPAWN_MODE", 0, raising=False)
    model = wf.WildFireModel()
    for _ in range(3):
        model.step()
    ids = set(map(str, resolve_victim_searcher_uav_ids(model)))
    searchers = [a for a in model.schedule.agents if type(a) is agents.UAV and str(a.unique_id) in ids]
    assert searchers and not any(s.rtb_active or s.rtb_docked for s in searchers)
    before = {k: dict(v) for k, v in (model._searcher_targeting_stats or {}).items()}
    for vid, st in model.managed_victims.items():
        st.confirmed = True
        model.victim_search_belief.detected_ids.add(str(vid))
    model.step()
    step = model.evaluation_timesteps_counter
    for s in searchers:
        uid = str(s.unique_id)
        now, was = model._searcher_targeting_stats.get(uid, {}), before.get(uid, {})
        delta = {k: now.get(k, 0) - was.get(k, 0) for k in set(now) | set(was)}
        assert delta.get("skip_recall") == 1 and not delta.get("delivered_steps"), delta
        assert not delta.get("lo_continuation_steps")
        assert s.rtb_log and s.rtb_log[-1].get("recall") and s.rtb_log[-1].get("trigger_step") == step


def test_where_the_recall_cannot_act_the_strategy_keeps_steering(_shipped, monkeypatch):
    """review R1-2: BASE_STATION_MODE < 2 (no return at all) - the recall predicate holds but advance() never acts on
    it, so the post-pass must not skip the searcher (R-1's continuation survives there)."""
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", 1, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 1, raising=False)
    model, (u,), dec = _world([(2502, (25, 10), 100.0)], {(25, 22): 1.0}, monkeypatch=monkeypatch)
    model.victim_search_belief.detected_ids.add("victim_0")
    u.rtb_berth = (46, 3)
    u._searcher_recall_active = lambda: True
    out = _plan(model, dec)
    assert _target(out, 2502) is not None
    assert not model._searcher_targeting_stats["2502"].get("skip_recall")


@pytest.mark.parametrize("state", ["recalled", "rtb_active", "rtb_docked"])
@pytest.mark.parametrize("fix", [1, 0])
def test_the_random_walk_does_not_steer_a_returning_searcher(_shipped, monkeypatch, state, fix):
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", fix, raising=False)
    model, (u,), dec = _world([(2502, (25, 10), 100.0)], {(25, 22): 1.0}, mode=4, monkeypatch=monkeypatch)
    model._searcher_rw_draws = {"step": STEP, "dirs": {"2502": 3}}
    if state == "recalled":
        u.rtb_berth = (46, 3)
        u._searcher_recall_active = lambda: True
    else:
        setattr(u, state, True)
    ex = UAVExecutor("2502", model, u)
    got = ex._searcher_targeting_direction(u, dec["2502"], model)
    assert (got is None) is bool(fix)


# ============================================================================ F1-g the planner's P_d
@pytest.mark.parametrize("fix", [1, 0])
def test_the_gain_uses_the_beliefs_own_detection_model(_shipped, monkeypatch, fix):
    """PD_SMOKE 0.5 (the misspecification sensitivity) and the only mass under smoke. With the fix the issued gain is
    the belief's own expected detection along the leg: each cell seen k times (k = steps of the leg it lies inside the
    disc, the start excluded) is detected with 1 - 0.5^k. fix3b credits every covered cell fully (P_d = 1)."""
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", fix, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_BELIEF_PD_SMOKE", 0.5, raising=False)
    cells = {(25, 30), (26, 30), (25, 31)}
    model, (u,), dec = _world([(2502, (25, 15), 100.0)], {c: 1.0 for c in cells}, monkeypatch=monkeypatch)
    model._fix3b_true_fire = lambda: (set(), set(cells))
    out = _plan(model, dec)
    g = model._searcher_targeting_issued[-1][4]
    lam = model.victim_search_belief.intensity()
    full = float(lam.sum())
    if fix:
        ex = UAVExecutor("2502", model, u)
        bfs = ex._targeting_bfs(u, model)
        t = _target(out, 2502)
        path = _path_mask(bfs, UAVExecutor._targeting_route(bfs, t, exact=True)[0])
        path[u.pos] = False
        k = disc_convolve(path.astype(float), model.victim_search_belief.offsets)
        expect = sum(float(lam[c]) * (1.0 - 0.5 ** k[c]) for c in cells)
        assert abs(g - round(expect, 5)) < 1e-9 and 0.5 * full < g < full, (g, expect)
    else:
        assert abs(g - full) < 1e-4, g


# ============================================================================ F1-h the boxed test
@pytest.mark.parametrize("fix", [1, 0])
def test_a_searcher_boxed_by_uavs_next_to_a_pool_cell_is_not_held_off(_shipped, monkeypatch, fix):
    """The searcher stands ON a pool cell, walled in by UAVs: the only cell its BFS reaches is a pool cell within
    Manhattan 2 - never a candidate. With the fix that is 'boxed by UAVs' (retry next step); fix3b counted it as a
    reachable candidate and held the searcher off for R steps."""
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_FIX", fix, raising=False)
    model, (u,), dec = _world([(2502, (10, 10), 100.0)], {(30, 30): 1.0}, monkeypatch=monkeypatch)
    for i, cell in enumerate(((11, 10), (9, 10), (10, 11), (10, 9))):
        model.schedule.agents.append(_uav(9000 + i, cell))
    _plan(model, dec)
    st = model._searcher_targeting_state["2502"]
    if fix:
        assert st["fallback_until"] == -1 and model._searcher_targeting_stats["2502"].get("fallback_boxed_by_uavs") == 1
    else:
        assert st["fallback_until"] == STEP + 10


# ============================================================================ item 2: the arrival-time estimate
def test_the_shipped_front_priority_parameters():
    p = fae.front_priority_params()
    assert abs(p.head_rate - 0.1 * 20 / 3.6 / 1.34) < 1e-12              # 0.415 cells / step
    assert abs(p.length_to_width - (1 + 0.25 * 0.4 * 20 / 1.15 / 1.609344)) < 1e-12
    assert abs(p.eccentricity - 0.877) < 5e-4 and p.kappa == 1.0 and p.tau == 16.0


def test_the_elliptical_arrival_time_head_flank_back():
    p = fae.FrontPriorityParams()
    r, e = p.head_rate, p.eccentricity
    t = fae.arrival_time(H, W, {(25, 25)}, (1.0, 0.0), p)               # wind east: fire travels to +x
    for d in (1, 4, 9):
        assert abs(t[25 + d, 25] - d / r) < 1e-9                                       # head
        assert abs(t[25 - d, 25] - d * (1 + e) / (r * (1 - e))) < 1e-9                 # back
        assert abs(t[25, 25 + d] - d / (r * (1 - e))) < 1e-9                           # flank
    assert t[25, 25] == 0.0
    assert np.isinf(fae.arrival_time(H, W, set(), (1.0, 0.0), p)).all()


def test_the_arrival_time_is_the_envelope_over_the_front():
    p = fae.FrontPriorityParams()
    front = {(10, 10), (30, 30)}
    t = fae.arrival_time(H, W, front, (0.0, -1.0), p)                  # wind south: fire travels to -y
    single = [fae.arrival_time(H, W, {c}, (0.0, -1.0), p) for c in front]
    assert np.array_equal(t, np.minimum(*single))


def test_the_urgency_weight():
    p = fae.FrontPriorityParams()
    w = fae.urgency_weight(H, W, {(25, 25)}, (1.0, 0.0), p)
    t = fae.arrival_time(H, W, {(25, 25)}, (1.0, 0.0), p)
    assert w[25, 25] == 1.0
    assert abs(w[29, 25] - (1.0 + math.exp(-t[29, 25] / 16.0))) < 1e-12
    assert w[29, 25] > w[21, 25] > 1.0 and w[29, 25] <= 2.0              # ahead of the head counts most
    assert np.array_equal(fae.urgency_weight(H, W, set(), (1.0, 0.0), p), np.ones((H, W)))


def test_front_priority_prefers_the_mass_ahead_of_the_head(_shipped, monkeypatch):
    """Two spots of mass, equally far from the searcher: the slightly richer one UPWIND of a burning cell, the other
    DOWNWIND of it. Bayes-flee (3) takes the richer one; front priority (5) takes the one the fire reaches first."""
    fire = {(25, 25)}
    mass = {(25, 13): 1.10, (25, 37): 1.0}                             # wind north: fire travels to +y
    picks = {}
    for mode in (3, 5):
        model, (u,), dec = _world([(2502, (10, 25), 100.0)], mass, fire=fire, mode=mode, monkeypatch=monkeypatch)
        ex_wind = "north"
        monkeypatch.setattr(UAVExecutor, "_get_wind_direction", lambda self, model=None: ex_wind)
        picks[mode] = _target(_plan(model, dec), 2502)
    assert picks[3][1] < 25 and picks[5][1] > 25, picks


def test_front_priority_without_fire_is_bayes_flee(_shipped, monkeypatch):
    mass = {(25, 8): 1.0, (30, 40): 0.7, (12, 33): 0.4}
    picks = {}
    for mode in (3, 5):
        model, (u,), dec = _world([(2502, (10, 25), 100.0)], mass, mode=mode, monkeypatch=monkeypatch)
        out = _plan(model, dec)
        picks[mode] = (_target(out, 2502), model._searcher_targeting_issued[-1][3:6])
    assert picks[3] == picks[5]


def test_the_weight_never_reaches_the_swept_rule(_shipped, monkeypatch):
    """A held front-priority target whose weight collapses (the fire moves away) is NOT dropped: the swept rule
    reads the unweighted p. kappa 50, so a swept rule on the weighted mass WOULD drop it (review R1-3); and the
    posterior stored at issue is the unweighted belief p."""
    monkeypatch.setattr(cfv, "SEARCHER_FP_KAPPA", 50.0, raising=False)
    monkeypatch.setattr(UAVExecutor, "_get_wind_direction", lambda self, model=None: "north")
    fire = [{(25, 25)}]
    model, (u,), dec = _world([(2502, (10, 25), 100.0)], {(25, 37): 1.0, (25, 13): 1.10}, fire=fire[0], mode=5,
                              monkeypatch=monkeypatch)
    model._fix3b_true_fire = lambda: (set(fire[0]), set())
    t = _target(_plan(model, dec), 2502)
    assert t[1] > 25
    assert np.array_equal(model._searcher_targeting_state["2502"]["p_issue"], model.victim_search_belief.p)
    fire[0] = {(45, 2)}
    model.evaluation_timesteps_counter += 1
    out = _plan(model, dec)
    assert _target(out, 2502) == t
    assert not any(k.startswith("drop_") for k in model._searcher_targeting_stats["2502"])


# ============================================================================ item 5: docked UAVs
class _MGrid:
    """A multi-occupancy grid stand-in (mesa MultiGrid semantics for the calls the move rule makes)."""

    def __init__(self):
        self.cells = {}

    def out_of_bounds(self, pos):
        return not (0 <= int(pos[0]) < H and 0 <= int(pos[1]) < W)

    def get_cell_list_contents(self, cells):
        out = []
        for c in cells:
            out += self.cells.get(tuple(c), [])
        return out

    def place(self, agent, pos):
        self.cells.setdefault(tuple(pos), []).append(agent)
        agent.pos = tuple(pos)

    def move_agent(self, agent, pos):
        self.cells[tuple(agent.pos)].remove(agent)
        self.place(agent, pos)


class _World5:
    def __init__(self):
        self.grid = _MGrid()
        self.evaluation_timesteps_counter = 100
        cells = frozenset((45 + i, j) for i in range(5) for j in range(5))
        self.base_station = {"depots": ({"origin": (45, 0), "size": 5, "cells": cells},), "cells": cells, "size": 5}
        self.schedule = type("Sch", (), {"agents": []})()
        self.managed_uav_states = {}

    def base_station_contains(self, pos, depot_index=None):
        return (int(pos[0]), int(pos[1])) in self.base_station["cells"]


def _uav5(world, pos, uid, docked=False, active=False, battery=80.0):
    u = agents.UAV.__new__(agents.UAV)
    u.unique_id, u.model = uid, world
    world.managed_uav_states[str(uid)] = type("S", (), {"role": "fire_tracker"})()
    u.selected_dir = 0
    u.battery_level, u.battery_status = battery, "normal"
    u.battery_drain_per_step, u.battery_drain_per_move = 0.1, 0.2
    u.rtb_berth, u.rtb_berths, u.rtb_home_depot = (46, 3), ((46, 3),), 0
    u.rtb_target_berth = u.rtb_target_depot = None
    u.rtb_active, u.rtb_docked = active, docked
    u.rtb_last_pos = u.rtb_recovery_cell = u.rtb_recovery_steered = None
    u.rtb_stall_steps = u.rtb_trips = u.rtb_cycles = u.rtb_return_steps = u.rtb_charge_steps = 0
    u.rtb_log = [{"trigger_step": 0, "arrival_step": 1, "released_step": None}] if docked else []
    u.rtb_delay_steps, u.rtb_delay_log, u.rtb_boxed_steps = 0, [], 0
    u.execution_direction_applied, u.execution_action, u.execution_stay = False, None, False
    world.grid.place(u, pos)
    world.schedule.agents.append(u)
    return u


@pytest.fixture
def _depots(monkeypatch):
    monkeypatch.setattr(cfv, "BASE_STATION_MODE", 3, raising=False)
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 1, raising=False)
    monkeypatch.setattr(cfv, "BASE_STATION_RETURN_MECHANISM", 2, raising=False)


@pytest.mark.parametrize("switch", [1, 0])
def test_a_docked_uav_does_not_block_a_tracker(_depots, monkeypatch, switch):
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", switch, raising=False)
    w = _World5()
    _uav5(w, (46, 3), 1, docked=True)
    _uav5(w, (40, 10), 3)                                               # an airborne UAV
    tracker = _uav5(w, (47, 3), 2)
    assert tracker._move_target_free((46, 3)) is bool(switch)
    assert tracker._move_target_free((40, 10)) is False                # airborne: always an obstacle
    assert tracker._move_target_free((47, 4)) is True


@pytest.mark.parametrize("switch", [1, 0])
def test_move_lets_a_tracker_over_a_docked_uav(_depots, monkeypatch, switch):
    """The call site: UAV.move itself enters (switch on) or is refused (off) the docked UAV's cell."""
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", switch, raising=False)
    w = _World5()
    _uav5(w, (46, 3), 1, docked=True)
    tracker = _uav5(w, (47, 3), 2)
    tracker.selected_dir = 2                                            # west: (47, 3) -> (46, 3)
    moved = tracker.move()
    assert moved is bool(switch) and tracker.pos == ((46, 3) if switch else (47, 3))


def test_the_switch_is_inert_without_free_cell_docking(monkeypatch):
    """review R2-F2: the berth path's stall-limit dock-in-place cannot coexist with 'never dock on a docked UAV', so
    the switch acts only with FREE_CELL_DOCKING (the shipped docking)."""
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", 1, raising=False)
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 0, raising=False)
    assert agents.uav_docked_not_obstacle() is False
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 1, raising=False)
    assert agents.uav_docked_not_obstacle() is True


def test_a_returning_uav_keeps_todays_rule(_depots, monkeypatch):
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", 1, raising=False)
    w = _World5()
    _uav5(w, (46, 3), 1, docked=True)
    returning = _uav5(w, (47, 3), 2, active=True)
    assert returning._move_target_free((46, 3)) is False


def test_a_stand_in_without_a_dock_flag_stays_an_obstacle(_depots, monkeypatch):
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", 1, raising=False)
    w = _World5()
    blocker = agents.UAV.__new__(agents.UAV)                           # like test_base_station._blocker
    w.grid.place(blocker, (46, 3))
    tracker = _uav5(w, (47, 3), 2)
    assert tracker._move_target_free((46, 3)) is False


@pytest.mark.parametrize("switch", [1, 0])
def test_no_uav_docks_on_a_docked_uav(_depots, monkeypatch, switch):
    """A tracker stands over a docked UAV (possible with the switch on) and its return starts there: it does not
    dock on that cell, it heads for a free one. (Switch off it would dock on the spot - unreachable there, since the
    move rule never lets it stand over a docked UAV.)"""
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", switch, raising=False)
    w = _World5()
    _uav5(w, (46, 3), 1, docked=True)
    over = _uav5(w, (46, 3), 2, battery=5.0)                           # low battery: the return triggers now
    pick = over._nearest_free_dock_cell(over._free_cell_depots(), over._other_uav_cells())
    assert (pick[0] != (46, 3)) is bool(switch)                         # its own cell is not free over a docked UAV
    over._apply_return_to_base()
    assert over.rtb_active
    if switch:
        assert not over.rtb_docked and tuple(over.rtb_target_berth) != (46, 3)
        assert over.execution_direction_applied and over.rtb_log[-1]["repicks"] == 0
    else:
        assert over.rtb_docked


@pytest.mark.parametrize("switch", [1, 0])
def test_a_docked_uav_is_not_released_under_another_uav(_depots, monkeypatch, switch):
    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", switch, raising=False)
    w = _World5()
    docked = _uav5(w, (46, 3), 1, docked=True, battery=100.0)
    _uav5(w, (46, 3), 2)                                               # an airborne tracker over it
    docked._apply_return_to_base()
    if switch:
        assert docked.rtb_docked and docked.rtb_log[-1].get("release_deferred") == 1
    else:
        assert not docked.rtb_docked
    w.grid.cells[(46, 3)] = [docked]                                   # the tracker has left
    docked._apply_return_to_base()
    assert not docked.rtb_docked                                       # relaunches the step after


@pytest.mark.parametrize("real_alarms", [1, 0])
@pytest.mark.parametrize("switch", [1, 0])
def test_a_uav_over_a_docked_one_raises_no_global_collision(monkeypatch, switch, real_alarms):
    """Guard (d) wired end to end: the UAVs' monitor observations -> the post-move resource update -> the global
    analyzer's safety analysis. Two UAVs on one cell, one docked: no COLLISION_RISK with the switch, whatever
    FAILSAFE_REAL_ALARMS (review R2-F1); a CRITICAL one without it."""
    import types
    import wildfire_model as wf
    from src_extension.analysis.global_analyzer import GlobalAnalyzer
    from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
    from src_extension.knowledge.uav_resource_model import UAVResourceModel
    from src_extension.monitoring.monitoring_buffer import MonitoringBuffer
    from src_extension.monitoring.monitoring_interfaces import LocalObservation

    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", switch, raising=False)
    monkeypatch.setattr(cfv, "FREE_CELL_DOCKING", 1, raising=False)
    monkeypatch.setattr(cfv, "FAILSAFE_REAL_ALARMS", real_alarms, raising=False)
    w = _World5()
    docked = _uav5(w, (46, 3), 1, docked=True)
    over = _uav5(w, (46, 3), 2)
    buf = MonitoringBuffer()
    for u in (docked, over):
        tc = {"role": "fire_tracker"}
        if agents.failsafe_real_alarms() or agents.uav_docked_not_obstacle():   # the monitor's rule
            tc["docked"] = bool(u.rtb_docked)
        buf.add_local_observation(str(u.unique_id), LocalObservation(
            uav_id=str(u.unique_id), timestamp=5.0, visible_fire_cells=[], visible_smoke_cells=[],
            visible_victim_candidates=[], current_position=u.pos, intended_move=u.pos, actual_move=u.pos,
            drift_error=0.0, battery_level=80.0, battery_status="normal", communication_status="ok", nearby_uavs=[],
            task_context=tc, negative_observations=[], raw_information_gain=0.0, normalized_information_gain=0.0,
            local_uncertainty_patch=[], observation_confidence=1.0, belief_confirmation_flags=[]))
    host = types.SimpleNamespace(uav_resource_model=UAVResourceModel())
    wf.WildFireModel._apply_uav_resource_updates(host, buf, 5.0)
    triggers = GlobalAnalyzer()._analyze_safety(SharedOperationalPicture(), {},
                                                {"uav_resource_model": host.uav_resource_model}, 5.0)
    collisions = [t for t in triggers if getattr(t, "trigger_type", "") == "COLLISION_RISK"]
    assert (len(collisions) == 0) is bool(switch), collisions


def test_the_monitor_reports_the_dock_state_when_the_switch_needs_it():
    import inspect
    from src_extension.monitoring import local_uav_monitor

    src = inspect.getsource(local_uav_monitor)
    assert "failsafe_real_alarms() or agents_module.uav_docked_not_obstacle()" in src


@pytest.mark.parametrize("switch", [1, 0])
def test_the_global_collision_check_counts_only_airborne_uavs(monkeypatch, switch):
    from src_extension.analysis.global_analyzer import GlobalAnalyzer
    from src_extension.knowledge.uav_resource_model import UAVResourceModel

    monkeypatch.setattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", switch, raising=False)
    urm = UAVResourceModel()
    urm.set_docked("1", True)
    urm.set_docked("3", True)
    urm.set_docked("3", False)
    positions = {"1": (46.0, 3.0), "2": (46.0, 3.0), "3": (10.0, 10.0)}
    got = GlobalAnalyzer._airborne_positions(positions, urm)
    assert ("1" in got) is (not switch) and "2" in got and "3" in got
    assert urm.snapshot().keys() == {"step_index", "by_uav_id"}       # not part of any snapshot
