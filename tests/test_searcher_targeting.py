"""fix3b (session 3b): searcher targeting - outputs/fix3b_part1.txt section 8 (T-R, T-B, T-C, T-U, T-D, T-S,
T-W, T-V). Every test sets its own configuration through monkeypatch (no test depends on suite order)."""
from __future__ import annotations

import collections
import random

import numpy as np
import pytest

import agents
import common_fixed_variables as cfv
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.knowledge.victim_search_belief import (
    MotionParams,
    VictimSearchBelief,
    disc_mask,
    disc_offsets,
)
from src_extension.planning.decision_objects import PathDecision
from src_extension.planning import searcher_targeting as stg
from test_uav_executor import _FakeAgent, _bfs_test_model

H = W = 50
STEP = 30
# a full-width fire wall at y = 30: everything at y >= 24 is inside the clearance (6) or beyond the wall
WALL = {(x, 30) for x in range(H)}


@pytest.fixture
def _shipped(monkeypatch):
    """The shipped searcher settings the targeting route depends on, set here (not inherited)."""
    monkeypatch.setattr(cfv, "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE", 99, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_GATE_NEAR_FIELD", 1, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_ROUTE_FIRE_FIELD", 1, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_CORNER_ESCAPE", 1, raising=False)
    for name, value in (("SEARCHER_TARGETING_COORDINATION", 1), ("SEARCHER_TARGETING_REACHABILITY", 1),
                        ("SEARCHER_TARGETING_BATTERY", 1), ("SEARCHER_BELIEF_MOTION", 1),
                        ("SEARCHER_BELIEF_STRIDE", 2), ("SEARCHER_TARGETING_TOP_M", 12),
                        ("SEARCHER_TARGETING_L0", 4), ("SEARCHER_TARGETING_TILE", 7),
                        ("SEARCHER_TARGETING_AGE_BUCKET", 10)):
        monkeypatch.setattr(cfv, name, value, raising=False)
    # battery: a generous fixed trigger unless a test sets its own
    monkeypatch.setattr(agents, "rtb_trigger_level_at", lambda uav, cell: 0.0)


def _uav(uid: int, pos, battery: float = 100.0):
    u = agents.UAV.__new__(agents.UAV)
    u.unique_id = uid
    u.pos = tuple(pos)
    u.battery_level = float(battery)
    u.battery_drain_per_step = 0.1
    u.battery_drain_per_move = 0.2
    u.rtb_active = False
    u.rtb_docked = False
    return u


def _world(searchers, mass, fire=(), smoke=(), mode=3, monkeypatch=None):
    """A fake model with real UAV agents, a real belief whose p is `mass` (dict cell -> weight), and the
    true-fire accessor the planner reads."""
    model = _bfs_test_model(fire_cells=set(fire), smoke_cells=set(smoke))
    uavs = [_uav(uid, pos, battery) for uid, pos, battery in searchers]
    model.schedule.agents.extend(uavs)
    model.managed_uav_states = {str(u.unique_id): type("S", (), {"role": "victim_searcher"})() for u in uavs}
    model._wind_search_target_state = {}
    model.evaluation_timesteps_counter = STEP
    model._fix3b_true_fire = lambda: (set(fire), set(smoke))
    belief = VictimSearchBelief.with_uniform_prior(H, W, 1, excluded=())
    p = np.zeros((H, W))
    for cell, weight in mass.items():
        p[cell] = weight
    belief.p = p / p.sum()
    model.victim_search_belief = belief
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", mode, raising=False)
    decisions = {str(u.unique_id): PathDecision(decision_id="d%s" % u.unique_id, uav_id=str(u.unique_id),
                                               selected_option_id="wind_aware_victim_search",
                                               next_action="victim_search_wind_aware") for u in uavs}
    return model, uavs, decisions


def _plan(model, decisions):
    return stg.apply_searcher_targeting(decisions, {"simulation_model": model})


def _target(out, uid):
    pts = out[str(uid)].waypoints_by_uav.get(str(uid))
    return (int(pts[0][0]), int(pts[0][1])) if pts else None


# ============================================================================ T-R reachability
def test_bayes_target_is_the_reachable_one_not_the_richer_one_behind_the_fire(_shipped, monkeypatch):
    """The richer mass lies behind a full fire wall; a poorer one is reachable. The issued target is the
    reachable one, and the executor's first step is on its admissible path. FAILS if the reachability
    filter is removed (verified red in Part 2 with the filter patched out)."""
    mass = {(25, 40): 0.9, (25, 18): 0.1}
    model, (u,), dec = _world([(2502, (25, 10), 100.0)], mass, fire=WALL, monkeypatch=monkeypatch)
    out = _plan(model, dec)
    t = _target(out, 2502)
    assert t is not None
    assert t[1] < 24, "a target behind the fire wall was issued: %r" % (t,)
    assert out["2502"].uncertainty_context["searcher_targeting_step"] == STEP
    ex = UAVExecutor("2502", model, u)
    ex._read_uav_role = lambda: "victim_searcher"  # type: ignore[method-assign]
    step = ex._searcher_targeting_direction(u, out["2502"], model)
    assert step is not None and step[1] == UAVExecutor.TARGETING_LABEL
    nxt = (u.pos[0] + [1, 0, -1, 0][step[0]], u.pos[1] + [0, -1, 0, 1][step[0]])
    assert nxt in ex._targeting_bfs(u, model)["dist"]


def test_least_observed_tile_is_the_reachable_stale_one(_shipped, monkeypatch):
    """The never-covered tiles lie behind the wall; one reachable tile is stale (covered at step 15), every
    other reachable tile was just covered. The issued anchor is the reachable stale tile's."""
    model, (u,), dec = _world([(2502, (25, 10), 100.0)], {(1, 1): 1.0}, fire=WALL, mode=1,
                              monkeypatch=monkeypatch)
    b = model.victim_search_belief
    b.last_cover[:, :] = STEP
    b.last_cover[:, 31:] = -1                     # behind the wall: never covered
    stale = [t for t in stg.tile_layout(H, W, 4, 7) if t["anchor"] == (42, 14)]
    assert stale, "tile layout changed"
    (xa, xb), (ya, yb) = stale[0]["x"], stale[0]["y"]
    b.last_cover[xa:xb + 1, ya:yb + 1] = 15
    out = _plan(model, dec)
    assert _target(out, 2502) == (42, 14)


# ============================================================================ T-B battery
def test_a_target_whose_round_trip_breaks_the_trigger_is_never_issued(_shipped, monkeypatch):
    """Depot at the origin: trigger(t) = 39.23 + 0.3 * |t|_1. The rich far target is battery-infeasible at 55;
    the poor near one is feasible. With the battery ablation the far one is issued."""
    monkeypatch.setattr(agents, "rtb_trigger_level_at", lambda uav, cell: 39.23 + 0.3 * (abs(cell[0]) + abs(cell[1])))
    mass = {(40, 40): 0.95, (14, 14): 0.05}
    model, _, dec = _world([(2502, (10, 10), 55.0)], mass, monkeypatch=monkeypatch)
    near = _target(_plan(model, dec), 2502)
    assert near is not None and (near[0] - 14) ** 2 + (near[1] - 14) ** 2 <= 64      # its disc covers the near mass
    model2, _, dec2 = _world([(2502, (10, 10), 55.0)], mass, monkeypatch=monkeypatch)
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_BATTERY", 0, raising=False)
    far = _target(_plan(model2, dec2), 2502)
    assert far is not None and (far[0] - 40) ** 2 + (far[1] - 40) ** 2 <= 64        # its disc covers the far mass


# ============================================================================ T-C coordination
def _hotspot_cover(target, centre=(21, 32), radius=8.0):
    return (target[0] - centre[0]) ** 2 + (target[1] - centre[1]) ** 2 <= radius * radius


def test_two_searchers_do_not_both_take_the_one_hotspot(_shipped, monkeypatch):
    mass = {(21, 32): 0.9}
    mass.update({(x, y): 0.1 / 25 for x in range(5, 46, 10) for y in range(5, 46, 10)})
    model, _, dec = _world([(2502, (20, 10), 100.0), (2503, (22, 10), 100.0)], mass, monkeypatch=monkeypatch)
    out = _plan(model, dec)
    covers = [_hotspot_cover(_target(out, uid)) for uid in (2502, 2503)]
    assert covers.count(True) == 1, "coordination: exactly one searcher takes the hotspot"
    model2, _, dec2 = _world([(2502, (20, 10), 100.0), (2503, (22, 10), 100.0)], mass, monkeypatch=monkeypatch)
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_COORDINATION", 0, raising=False)
    out2 = _plan(model2, dec2)
    assert all(_hotspot_cover(_target(out2, uid)) for uid in (2502, 2503))


# ============================================================================ T-U belief
def test_the_negative_update_zeroes_exactly_the_euclidean_disc():
    b = VictimSearchBelief.with_uniform_prior(H, W, 3, excluded=())
    b.measure([(25, 25)], set(), step=1)
    zero = {(int(x), int(y)) for x, y in zip(*np.where(b.p == 0.0))}
    assert len(disc_offsets(8)) == 197
    assert zero == {(25 + dx, 25 + dy) for dx, dy in disc_offsets(8)}
    assert abs(b.p.sum() - 1.0) < 1e-12 and b.dead == 0.0


@pytest.mark.parametrize("mode", ["diffusion", "flee", "off"])
def test_predict_and_burn_over_conserve_mass(mode):
    b = VictimSearchBelief.with_uniform_prior(H, W, 2, excluded=())
    burning = {(x, 20) for x in range(10, 30)}
    before = float(b.p.sum()) + b.dead
    b.predict(burning, MotionParams(mode=mode))
    assert abs(float(b.p.sum()) + b.dead - before) < 1e-9
    alive_on_fire = sum(float(b.p[c]) for c in burning)
    b.burn_over(burning, 0.5)
    assert abs(float(b.p.sum()) + b.dead - before) < 1e-9
    assert abs(b.dead - 0.5 * alive_on_fire) < 1e-12


def test_flee_moves_mass_away_from_the_fire():
    b = VictimSearchBelief.with_uniform_prior(H, W, 1, excluded=())
    b.p[:, :] = 0.0
    b.p[25, 22] = 1.0
    b.predict({(25, 20)}, MotionParams(mode="flee"))
    assert b.p[25, 23] > b.p[25, 21] and b.p[25, 23] > b.p[24, 22]


def test_a_detection_decrements_the_unfound_count_and_leaves_p_unchanged():
    b = VictimSearchBelief.with_uniform_prior(H, W, 3, excluded=())
    p0 = b.p.copy()
    b.detected_ids.add("victim_1")
    assert b.n_unfound == 2 and np.array_equal(b.p, p0)
    assert abs(b.expected_unfound_alive() - 2.0) < 1e-9


def test_the_belief_draws_no_random_numbers():
    s1, s2 = random.getstate(), agents.random.getstate()
    b = VictimSearchBelief.with_uniform_prior(H, W, 2, excluded=())
    for _ in range(5):
        b.predict({(10, 10), (11, 10)}, MotionParams(mode="flee"))
        b.measure([(5, 5), (40, 40)], {(6, 6)}, step=1, pd_smoke=0.5)
        b.burn_over({(10, 10)}, 0.5)
    assert random.getstate() == s1 and agents.random.getstate() == s2


# ============================================================================ T-D delivery
def _delivered(monkeypatch, step=STEP, pos=(25, 10), smoke=()):
    model, (u,), dec = _world([(2502, pos, 100.0)], {(25, 18): 1.0}, smoke=smoke, monkeypatch=monkeypatch)
    out = _plan(model, dec)
    ex = UAVExecutor("2502", model, u)
    ex._read_uav_role = lambda: "victim_searcher"  # type: ignore[method-assign]
    pd = out["2502"]
    ctx = dict(pd.uncertainty_context)
    ctx["searcher_targeting_step"] = step
    return ex, u, model, PathDecision(**{**pd.__dict__, "uncertainty_context": ctx})


def test_a_stale_marker_never_steers(_shipped, monkeypatch):
    ex, u, model, pd = _delivered(monkeypatch, step=STEP - 1)
    assert ex._searcher_targeting_direction(u, pd, model) is None


def test_an_on_cell_hazard_falls_through_to_the_current_chain(_shipped, monkeypatch):
    ex, u, model, pd = _delivered(monkeypatch)
    assert ex._searcher_targeting_direction(u, pd, model) is not None
    model.visibility_model.smoke_obscured_cells.add(u.pos)
    assert ex._searcher_targeting_direction(u, pd, model) is None


def test_the_gate_exemption_needs_the_label_and_the_method(_shipped, monkeypatch):
    ex, u, model, pd = _delivered(monkeypatch)
    ex._last_escape_method = None
    assert not ex._fix3b_gate_exempt(UAVExecutor.TARGETING_LABEL)
    ex._last_escape_method = UAVExecutor.TARGETING_METHOD
    assert ex._fix3b_gate_exempt(UAVExecutor.TARGETING_LABEL)
    assert not ex._fix3b_gate_exempt("victim_search_wind_aware")
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", 0, raising=False)
    assert not ex._fix3b_gate_exempt(UAVExecutor.TARGETING_LABEL)


def test_the_post_pass_is_inert_at_the_shipped_zero(_shipped, monkeypatch):
    model, _, dec = _world([(2502, (25, 10), 100.0)], {(25, 18): 1.0}, mode=0, monkeypatch=monkeypatch)
    assert _plan(model, dec) is dec


# ============================================================================ T-S switches
def test_shipped_values():
    import importlib

    fresh = importlib.import_module("common_fixed_variables")
    src = open(fresh.__file__, encoding="utf-8").read()
    assert "\nSEARCHER_TARGETING = 0\n" in src
    assert "\nSEARCHER_TARGETING_REACHABILITY = 1\n" in src      # never shipped at 0
    assert "\nVICTIM_SPAWN_MODE = 0\n" in src
    assert "\nSEARCHER_TARGETING_RW_GATED = 0\n" in src


@pytest.mark.parametrize("raw,expected", [(0, 0), (1, 1), (3, 3), (4, 4), (2.0, 2), ("3", 3), (5, 0), (-1, 0),
                                          (0.5, 0), ("x", 0), (None, 0)])
def test_searcher_targeting_parses_exact_integers(monkeypatch, raw, expected):
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", raw, raising=False)
    assert agents.searcher_targeting() == expected


@pytest.mark.parametrize("raw,on", [(1, True), (0, False), (0.0, False), ("0", False), (0.5, True), ("junk", True)])
def test_ablation_switches_turn_off_only_on_an_exact_zero(monkeypatch, raw, on):
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING_REACHABILITY", raw, raising=False)
    assert agents.searcher_targeting_reachability() is on


@pytest.mark.parametrize("raw,mode", [(1, 1), (0, 0), (0.5, 0), (2, 0), ("1", 1)])
def test_victim_spawn_mode_is_one_only_on_an_exact_one(monkeypatch, raw, mode):
    monkeypatch.setattr(cfv, "VICTIM_SPAWN_MODE", raw, raising=False)
    assert agents.victim_spawn_mode() == mode


# ============================================================================ T-W random walk
def test_the_random_walk_uses_only_its_own_stream_and_is_uniform():
    class _M:
        pass

    m = _M()
    m.schedule = type("Sc", (), {"agents": [_uav(2502, (10, 10)), _uav(2503, (12, 10))]})()
    m._searcher_rw_rng = random.Random(1234)
    s1, s2 = random.getstate(), agents.random.getstate()
    counts = collections.Counter()
    for step in range(2000):
        m.evaluation_timesteps_counter = step
        stg.draw_random_walk(m)
        counts.update(m._searcher_rw_draws["dirs"].values())
    assert random.getstate() == s1 and agents.random.getstate() == s2
    n = sum(counts.values())
    chi2 = sum((counts[d] - n / 4.0) ** 2 / (n / 4.0) for d in range(4))
    assert set(counts) == {0, 1, 2, 3} and chi2 < 16.27          # df 3, p = 0.001


def test_the_salted_streams_consume_nothing_and_differ(monkeypatch):
    import wildfire_model as wf

    rng = random.Random(77)
    monkeypatch.setattr(wf, "SYSTEM_RANDOM", rng, raising=False)
    state = rng.getstate()
    a = wf.WildFireModel._make_salted_rng("fix3b-victim-spawn")
    b = wf.WildFireModel._make_salted_rng("fix3b-searcher-random-walk")
    c = wf.WildFireModel._make_ff_absence_rng()
    assert rng.getstate() == state
    assert len({a.random(), b.random(), c.random()}) == 3


# ============================================================================ T-V uniform spawn (a real model)
def _seeded_model(monkeypatch, seed, spawn_mode):
    import wildfire_model as wf

    rng = random.Random(seed)
    monkeypatch.setattr(cfv, "SYSTEM_RANDOM", rng, raising=False)
    monkeypatch.setattr(wf, "SYSTEM_RANDOM", rng, raising=False)
    monkeypatch.setattr(agents, "random", rng, raising=False)
    monkeypatch.setattr(cfv, "VICTIM_SPAWN_MODE", spawn_mode, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", 0, raising=False)
    model = wf.WildFireModel()
    burning = {tuple(a.pos) for a in model.schedule.agents if type(a) is agents.Fire and a.is_burning()}
    spawn = {vid: tuple(m.pos) for vid, m in model.victim_marker_agents.items()}
    return model, burning, spawn, rng.getstate()


def test_uniform_spawn_is_on_the_prior_support_reproducible_and_leaves_the_fire_unchanged(monkeypatch):
    model, burn1, spawn1, state1 = _seeded_model(monkeypatch, 4242, 1)
    excluded = model.victim_search_prior_excluded()
    assert all(cell not in excluded for cell in spawn1.values())
    _, burn1b, spawn1b, _ = _seeded_model(monkeypatch, 4242, 1)
    assert spawn1 == spawn1b
    _, burn0, spawn0, state0 = _seeded_model(monkeypatch, 4242, 0)
    assert burn1 == burn0 and state1 == state0          # the fire stream is untouched by the spawn
    assert spawn1 != spawn0                              # and the victims are not on the ring
    assert model.victim_search_belief is None            # no belief at SEARCHER_TARGETING 0
