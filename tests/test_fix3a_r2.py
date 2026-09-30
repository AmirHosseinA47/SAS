"""fix3a round 2 (outputs/fix3a_r2_prereg.txt): (a) ONE OWNER FOR NEAR-FIRE STEERING
(SEARCHER_FIRE_ROUTE_OWNER) and (b) A BOUNDED WAIT (SEARCHER_ROUTE_BOUNDED_WAIT, SEARCHER_ROUTE_WAIT_LIMIT W).

Every rule's tests FAIL when its switch is forced to 0 (revert-checked: outputs/_fx3_revert_check.py).
"""
from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import pytest

import agents
import common_fixed_variables as cfv
from src_extension.adaptation.local_adaptation_generator import _wind_search_state
from src_extension.execution.uav_executor import UAVExecutor

from test_fix3a import EAST, MX, MY, NORTH, SOUTH, WEST, W, _near_field_setting, _searcher

LEGACY_RETREAT_LABELS = ("victim_search_hazard_retreat",)


def _ws(ex):
    return _wind_search_state(ex._model, ex.uav_id)


def _at_step(ex, step):
    ex._model.evaluation_timesteps_counter = step


def _oscillation_windows(trail):
    """The pre-registered (O) window measure: 10 consecutive positions on <= 2 cells with >= 4 changes (a
    single probe-and-retreat, A-B-A, is not an episode)."""
    hits = 0
    for i in range(0, len(trail) - 9):
        w = trail[i:i + 10]
        if len(set(w)) <= 2 and sum(1 for k in range(1, 10) if w[k] != w[k - 1]) >= 4:
            hits += 1
    return hits


# ============================================================================ switches and W
@pytest.mark.parametrize("name,accessor", [("SEARCHER_FIRE_ROUTE_OWNER", agents.searcher_fire_route_owner),
                                           ("SEARCHER_ROUTE_BOUNDED_WAIT", agents.searcher_route_bounded_wait)])
def test_both_switches_ship_on_and_turn_off_only_on_an_exact_zero(monkeypatch, name, accessor):
    assert getattr(cfv, name) == 1 and accessor()
    for junk in (0.5, "off", None, 2):
        monkeypatch.setattr(cfv, name, junk, raising=False)
        assert accessor(), junk
    for zero in (0, 0.0, "0", False):
        monkeypatch.setattr(cfv, name, zero, raising=False)
        assert not accessor(), zero


def test_the_wait_limit_is_the_preregistered_20_and_refuses_junk(monkeypatch):
    assert cfv.SEARCHER_ROUTE_WAIT_LIMIT == 20 and agents.searcher_route_wait_limit() == 20
    for good, value in ((39, 39), ("20", 20), (1, 1), (5.0, 5)):
        monkeypatch.setattr(cfv, "SEARCHER_ROUTE_WAIT_LIMIT", good, raising=False)
        assert agents.searcher_route_wait_limit() == value
    for bad in (0, -1, 1.5, "x", None, True):
        monkeypatch.setattr(cfv, "SEARCHER_ROUTE_WAIT_LIMIT", bad, raising=False)
        with pytest.raises(ValueError):
            agents.searcher_route_wait_limit()


# ============================================================================ (a5) the edge predicate
@pytest.mark.parametrize("corner", [1, 0])
def test_the_edge_predicate_is_exactly_the_edge_filter(monkeypatch, corner):
    """_edge_step_allowed(cell, next) == not _victim_edge_blocked_direction for a searcher on cell - every cell,
    every direction, both filter rules."""
    monkeypatch.setattr(cfv, "SEARCHER_CORNER_ESCAPE", corner, raising=False)
    ex, agent = _searcher((25, 25))
    for x in range(W):
        for y in range(W):
            agent.pos = (x, y)
            for d in range(4):
                nxt = (x + MX[d], y + MY[d])
                assert ex._edge_step_allowed(ex._model, (x, y), nxt) == (not ex._victim_edge_blocked_direction(agent, d)), (x, y, d)


# ============================================================================ (a2) the hand-off
def test_a_gate_veto_goes_to_the_route_not_the_retreat(monkeypatch):
    """A burning cell 3 north of the searcher, the step's target north beyond it: the gate vetoes the
    northward step (near field) - the step is the latched route's, labelled <origin>_fire_route or a FIRE
    label, never the memoryless retreat's; the route is latched on the target."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 20), fire_cells={(25, 23)})
    ex._step_target = (25.0, 40.0)
    direction, label = ex._apply_victim_searcher_hazard_gate(agent, NORTH, "victim_search_wind_aware_sweep")
    assert label in ("victim_search_wind_aware_sweep_fire_route", UAVExecutor.FIRE_RETREAT_LABEL,
                     UAVExecutor.FIRE_WAIT_LABEL)
    assert ex._latched_on(agent, (25.0, 40.0)) or label != "victim_search_wind_aware_sweep_fire_route"
    assert getattr(ex, "_route_owned_step", False)


def test_with_the_switch_off_the_gate_returns_its_own_retreat(monkeypatch):
    _near_field_setting(monkeypatch)
    monkeypatch.setattr(cfv, "SEARCHER_FIRE_ROUTE_OWNER", 0, raising=False)
    ex, agent = _searcher((25, 20), fire_cells={(25, 23)})
    ex._step_target = (25.0, 40.0)
    direction, label = ex._apply_victim_searcher_hazard_gate(agent, NORTH, "victim_search_wind_aware_sweep")
    assert not label.endswith("_fire_route") and label not in (UAVExecutor.FIRE_RETREAT_LABEL,
                                                               UAVExecutor.FIRE_WAIT_LABEL)


def test_once_latched_the_route_owns_the_step_even_when_the_gate_would_pass(monkeypatch):
    """Far from any hazard the gate passes the planner's step - but the searcher is latched on this target,
    so the route plans it (one owner, no alternation between the planner and the route)."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 10))
    _ws(ex)["fire_route_target"] = [25, 40]
    ex._step_target = (25.0, 41.0)                      # within Manhattan 2 of the latched goal
    _direction, label = ex._apply_victim_searcher_hazard_gate(agent, EAST, "victim_search_wind_aware")
    assert label == "victim_search_wind_aware_fire_route"
    ex2, agent2 = _searcher((25, 10))
    ex2._step_target = (25.0, 41.0)                     # not latched: the gate's pass-through stands
    assert ex2._apply_victim_searcher_hazard_gate(agent2, EAST, "victim_search_wind_aware") == (
        EAST, "victim_search_wind_aware")


def test_the_b_west_9608_alternation_is_gone(monkeypatch):
    """Part 3's (O) episode B/W 9608 (33 steps, (45, 11) <-> (46, 11)): the planner keeps pointing north at a
    target beyond a fire, the gate's retreat stepped into the edge band and the edge filter sent it back.
    Driven with a constant northward planner (it keeps the target even after the give-up, so the
    refusal is exercised): no oscillation window, no edge-blocked move, no legacy
    retreat label."""
    _near_field_setting(monkeypatch)
    # A fire west-north of the searcher: the legacy retreat's best cell is EAST, (46, 11), inside the band
    # (the 9608 mechanism) - from there the edge filter only lets it back west, and the planner turns north.
    fire = {(x, y) for x in range(39, 42) for y in range(12, 17)}
    ex, agent = _searcher((45, 11), fire_cells=fire)
    trail, labels = [agent.pos], []
    for step in range(31, 71):
        _at_step(ex, step)
        ex._step_target = (45.0, 20.0)
        ex._route_owned_step = False
        before = agent.pos
        direction, label = ex._apply_victim_searcher_hazard_gate(agent, NORTH, "victim_search_wind_aware_sweep")
        labels.append(label)
        if label != UAVExecutor.FIRE_WAIT_LABEL:
            nxt = (before[0] + MX[direction], before[1] + MY[direction])
            assert ex._edge_step_allowed(ex._model, before, nxt), (before, direction, label)
            agent.pos = nxt
        trail.append(agent.pos)
    assert _oscillation_windows(trail) == 0, trail
    assert not any(label in LEGACY_RETREAT_LABELS for label in labels)


def test_a_vetoed_step_without_a_target_is_the_no_goal_step(monkeypatch):
    """A hold escape (no target) vetoed next to a fire, nothing latched: the fire retreat / wait, never the
    legacy retreat."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 20), fire_cells={(25, 22)})
    ex._step_target = None
    _direction, label = ex._apply_victim_searcher_hazard_gate(agent, NORTH, "hold_escape")
    assert label in (UAVExecutor.FIRE_RETREAT_LABEL, UAVExecutor.FIRE_WAIT_LABEL)


# ============================================================================ (a3) (a4) (a6) the route
def test_smoke_within_the_near_field_puts_the_route_in_fire_mode(monkeypatch):
    """Smoke 4 west, no fire (the Part 2 test's case): one "near" - the route plans by the fire-mode BFS
    (a shortest path around the smoke, never into it), not the unlatched greedy step."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((20, 20), smoke_cells={(16, 20)})
    direction, _label = ex._attempt_pathfinding_toward_target(agent, (5.0, 20.0), action_label="lbl")
    assert str(ex._last_escape_method).startswith("bfs_fire_field")
    assert _ws(ex)["fire_route_target"] == [5, 20]
    assert getattr(ex, "_route_owned_step", False)            # a fire-mode step is route-owned
    # the route, followed step by step, never enters the smoke cell and arrives
    trail = [agent.pos]
    for step in range(31, 60):
        _at_step(ex, step)
        routed = ex._attempt_pathfinding_toward_target(agent, (5.0, 20.0), action_label="lbl")
        if routed is None or routed[1] in (UAVExecutor.FIRE_WAIT_LABEL,):
            break
        agent.pos = (agent.pos[0] + MX[routed[0]], agent.pos[1] + MY[routed[0]])
        trail.append(agent.pos)
        if abs(agent.pos[0] - 5) + abs(agent.pos[1] - 20) <= 2:
            break
    assert (16, 20) not in trail and abs(trail[-1][0] - 5) + abs(trail[-1][1] - 20) <= 2, trail


def test_a_first_step_hazard_the_plan_did_not_see_is_replanned_not_waited(monkeypatch):
    """True smoke on the path's first cell that the belief map (the plan) does not hold: the route replans
    around it instead of breaking to a wait."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((20, 20), fire_cells={(20, 14)})
    real = ex._strict_victim_hazard_level
    unseen = (20, 21)                                   # the straight path's first cell toward (20, 35)
    monkeypatch.setattr(ex, "_strict_victim_hazard_level",
                        lambda cell: 1 if tuple(cell) == unseen else real(cell))
    direction, label = ex._attempt_pathfinding_toward_target(agent, (20.0, 35.0), action_label="lbl")
    assert label == "lbl" and (20 + MX[direction], 20 + MY[direction]) != unseen


def test_on_a_hazard_cell_the_no_path_step_leaves_it(monkeypatch):
    """Smoke drifted onto the searcher, no goal: out of it to the legal neighbour farthest from the fire,
    whatever the gain (Part 2 would have waited IN the smoke: no strictly farther cell from a distant fire)."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 25), smoke_cells={(25, 25)})
    direction, label = ex._attempt_pathfinding_toward_target(agent, None, action_label="lbl",
                                                            force_fire_mode=True)
    assert label == UAVExecutor.FIRE_RETREAT_LABEL
    assert ex._strict_victim_hazard_level((25 + MX[direction], 25 + MY[direction])) == 0


def test_the_latch_survives_a_one_cell_shift_of_its_target(monkeypatch):
    """C/S 9610: the escape target moved (45, 45) -> (44, 45) mid-wait. Within Manhattan 2 it is the same route:
    the latch and its no-path count are kept, the stored goal follows."""
    _near_field_setting(monkeypatch)
    wall = {(10, y) for y in range(W)}
    ex, agent = _searcher((20, 25), fire_cells=wall)
    _at_step(ex, 40)
    ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    assert _ws(ex)["fire_route_nopath"] == 1
    _at_step(ex, 41)
    ex._attempt_pathfinding_toward_target(agent, (5.0, 26.0), action_label="lbl", force_fire_mode=True)
    assert _ws(ex)["fire_route_target"] == [5, 26] and _ws(ex)["fire_route_nopath"] == 2
    _at_step(ex, 42)
    ex._attempt_pathfinding_toward_target(agent, (5.0, 30.0), action_label="lbl", force_fire_mode=True)
    assert _ws(ex)["fire_route_target"] == [5, 30] and _ws(ex)["fire_route_nopath"] == 1   # a new route


# ============================================================================ (b) the bounded wait
def _walled(monkeypatch, limit=3):
    _near_field_setting(monkeypatch)
    monkeypatch.setattr(cfv, "SEARCHER_ROUTE_WAIT_LIMIT", limit, raising=False)
    wall = {(10, y) for y in range(W)}
    ex, agent = _searcher((20, 25), fire_cells=wall)
    return ex, agent


def test_the_no_path_count_is_once_per_model_step_and_skips_return_legs(monkeypatch):
    ex, agent = _walled(monkeypatch, limit=20)
    for step, calls in ((50, 2), (51, 1), (52, 3)):
        _at_step(ex, step)
        for _ in range(calls):
            ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    assert _ws(ex)["fire_route_nopath"] == 3
    agent.rtb_active = True
    _at_step(ex, 53)
    ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    assert _ws(ex)["fire_route_nopath"] == 3


def test_the_count_is_cumulative_over_the_latch(monkeypatch):
    """A routed step does not reset the count (C/S 9610: runs of 15, 30, 50 waits split by 1-2 moves)."""
    ex, agent = _walled(monkeypatch, limit=20)
    _at_step(ex, 60)
    ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    fire = ex._model.schedule.agents
    ex._model.schedule.agents = []                       # the fire burns out: a path exists
    _at_step(ex, 61)
    direction, label = ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl",
                                                            force_fire_mode=True)
    assert label == "lbl" and _ws(ex)["fire_route_nopath"] == 1
    ex._model.schedule.agents = fire
    _at_step(ex, 62)
    ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    assert _ws(ex)["fire_route_nopath"] == 2


def test_at_w_the_route_gives_its_target_up(monkeypatch):
    ex, agent = _walled(monkeypatch, limit=3)
    ws = _ws(ex)
    ws["escape_target"] = [5.0, 25.0]
    ws["commit_target"] = (5.0, 25.0)
    for step in (70, 71, 72):
        _at_step(ex, step)
        ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    assert ws["route_give_ups"] == 1
    assert ws["route_given_up"] == [{"cell": [5, 25], "until": 72 + 15}]
    assert ws["fire_route_target"] is None and ws["fire_route_nopath"] == 0
    assert ws["escape_target"] is None and ws["commit_target"] is None
    assert ws["commit_breaks"]["route_give_up"] == 1
    assert ws["saturated_until"][(5, 25)] == 72 + 15 and ws["saturated_until"][(7, 27)] == 72 + 15
    assert ws["force_coverage_escape"] is True and ws["force_interior_retarget"] is True


def test_a_given_up_target_is_refused_until_its_cooldown_ends(monkeypatch):
    ex, agent = _walled(monkeypatch, limit=3)
    for step in (70, 71, 72):
        _at_step(ex, step)
        ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    _at_step(ex, 80)
    assert ex._target_refused(ex._model, (6.0, 26.0))                 # within Manhattan 2
    assert not ex._target_refused(ex._model, (5.0, 28.0))             # 3 away
    _direction, label = ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl",
                                                             force_fire_mode=True)
    assert label in (UAVExecutor.FIRE_RETREAT_LABEL, UAVExecutor.FIRE_WAIT_LABEL)
    assert _ws(ex)["fire_route_target"] is None and _ws(ex)["route_refusals"] >= 2
    _at_step(ex, 87)
    assert not ex._target_refused(ex._model, (5.0, 25.0))              # the cooldown is over


def test_with_the_bound_off_the_wait_is_unbounded(monkeypatch):
    ex, agent = _walled(monkeypatch, limit=3)
    monkeypatch.setattr(cfv, "SEARCHER_ROUTE_BOUNDED_WAIT", 0, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_FIRE_ROUTE_OWNER", 1, raising=False)   # (b) alone off, (a) on
    for step in range(70, 80):
        _at_step(ex, step)
        ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    assert not _ws(ex).get("route_give_ups") and _ws(ex)["fire_route_target"] == [5, 25]


# ============================================================================ review fixes (before any run)
from src_extension.planning.decision_objects import FailSafeDecision, PathDecision  # noqa: E402


def _decision(ex):
    return PathDecision(decision_id="d", uav_id=ex.uav_id, selected_option_id="wind_aware_victim_search",
                        next_action="victim_search_wind_aware", uncertainty_context={})


def test_a_reached_goal_at_the_near_field_boundary_does_not_alternate(monkeypatch):
    """The review's geometry: a burning front on x = 16, the sweep target S = (20, 20) (burning distance 4),
    the searcher at B = (23, 20) (7) outside the near field. The planner steps west to A = (22, 20) (6), the
    only cell within 2 of S that keeps the clearance; there the step is handed to the route with the goal
    reached. Releasing it (the first version) ran the no-goal retreat east, and the planner walked back:
    B -> A -> B. The route now keeps the reached goal and waits (counted toward W)."""
    _near_field_setting(monkeypatch)
    front = {(16, y) for y in range(W)}
    ex, agent = _searcher((23, 20), fire_cells=front)
    trail = [agent.pos]
    for step in range(31, 56):
        _at_step(ex, step)
        ex._step_target = (20.0, 20.0)
        ex._route_owned_step = False
        before = agent.pos
        direction, label = ex._apply_victim_searcher_hazard_gate(agent, WEST, "victim_search_wind_aware_sweep")
        if label != UAVExecutor.FIRE_WAIT_LABEL:
            agent.pos = (before[0] + MX[direction], before[1] + MY[direction])
        trail.append(agent.pos)
    assert _oscillation_windows(trail) == 0, trail
    assert (22, 20) in trail and min(x for x, _y in trail) >= 22     # never inside the clearance


def test_only_a_fire_mode_step_is_route_owned(monkeypatch):
    """(a7, review) far from any hazard and unlatched, the route's forced-progress step (whose BFS fallback does
    not plan within the edge filter) is NOT route-owned - execute() gates it; a fire-mode step is."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 25))
    ex._route_owned_step = False
    routed = ex._attempt_pathfinding_toward_target(agent, (25.0, 40.0), action_label="lbl")
    assert routed is not None and not ex._route_owned_step
    ex2, agent2 = _searcher((25, 25), fire_cells={(25, 29)})
    ex2._route_owned_step = False
    assert ex2._attempt_pathfinding_toward_target(agent2, (25.0, 40.0), action_label="lbl") is not None
    assert ex2._route_owned_step


def test_a_step_toward_another_target_releases_a_stale_latch(monkeypatch):
    """(review) latched on X with a no-path count, the searcher's step now steers to Y (more than 2 away):
    the latch and its count are released at that step, so X re-issued later starts a fresh count."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 10))
    ws = _ws(ex)
    ws["fire_route_target"], ws["fire_route_nopath"] = [25, 40], 19
    ex._step_target = (40.0, 10.0)
    ex._apply_victim_searcher_hazard_gate(agent, EAST, "victim_search_wind_aware")
    assert ws["fire_route_target"] is None and ws["fire_route_nopath"] == 0


def test_execute_gates_an_ordinary_step_once_and_never_regates_a_route_step(monkeypatch):
    """(a1, a7) execute(): a known-victim step next to a fire is gated ONCE and handed to the route; a step
    the route already owns is not gated at all; a stale ownership flag from the previous call is reset."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 20), fire_cells={(25, 23)})
    calls = []
    real_gate = ex._apply_victim_searcher_hazard_gate

    def spy(a, d, lab):
        calls.append(lab)
        return real_gate(a, d, lab)

    monkeypatch.setattr(ex, "_apply_victim_searcher_hazard_gate", spy)

    def known_victim(a, dec, rk, act):
        ex._step_target = (25.0, 40.0)
        return NORTH, "computed_from_target"

    monkeypatch.setattr(ex, "_resolve_direction_intent", known_victim)
    ex._route_owned_step = True                                 # stale, from a previous call
    result = ex.execute(_decision(ex), 30.0)
    assert calls == ["computed_from_target"]
    assert result["action"] in ("computed_from_target_fire_route", UAVExecutor.FIRE_RETREAT_LABEL,
                                UAVExecutor.FIRE_WAIT_LABEL)

    def routed(a, dec, rk, act):
        ex._route_owned_step = True
        return EAST, "victim_search_wind_aware_retarget_to_interior"

    calls.clear()
    monkeypatch.setattr(ex, "_resolve_direction_intent", routed)
    ex.execute(_decision(ex), 31.0)
    assert calls == []


def test_the_fail_safe_search_path_uses_the_searcher_gate(monkeypatch):
    """(a8) the dormant fail-safe search path: the searcher gate (with its hand-off), not
    _apply_final_direction_safety."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 20), fire_cells={(25, 23)})

    def forbidden(*_a, **_k):
        raise AssertionError("_apply_final_direction_safety used for a searcher")

    monkeypatch.setattr(ex, "_apply_final_direction_safety", forbidden)

    def known_victim(a, dec, rk, act):
        ex._step_target = (25.0, 40.0)
        return NORTH, "computed_from_target"

    monkeypatch.setattr(ex, "_resolve_direction_intent", known_victim)
    fs = FailSafeDecision(decision_id="fs", selected_option_id="x", fail_safe_action="safe_hold",
                          mission_mode="safety_first", search_mode_active=True, uncertainty_context={})
    result = ex.execute(_decision(ex), 30.0, fail_safe_decision=fs)
    assert result["action"].endswith("_fire_route") or result["action"] in (
        UAVExecutor.FIRE_RETREAT_LABEL, UAVExecutor.FIRE_WAIT_LABEL)


def test_a_route_owned_sweep_step_clears_force_sweep(monkeypatch):
    """(a9) a handed-off sweep step is a sweep step for the sweep flag."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 25))
    _ws(ex)["force_sweep"] = True
    ex._sync_wind_search_execution_state(agent, _decision(ex), "victim_search_wind_aware_sweep_fire_route")
    assert _ws(ex)["force_sweep"] is False


def test_a_given_up_escape_target_is_refused_at_its_source(monkeypatch):
    """(b3) the escape target: cleared at the source, the step goes on without it; one refusal step counted."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((20, 25), fire_cells={(10, y) for y in range(W)})
    ws = _ws(ex)
    ws["escape_target"] = [5.0, 25.0]
    ws["route_given_up"] = [{"cell": [5, 25], "until": 99}]
    ex._resolve_direction_intent(agent, _decision(ex), "victim", "victim_search_wind_aware")
    assert ws["escape_target"] is None and ws["route_refusal_steps"] == 1


def test_the_no_goal_step_leaves_the_edge_band(monkeypatch):
    """(a4, review) no goal, no fire, in the band: the step leaves it inward (the penetration strictly
    falls), labelled a fire retreat - never a wait in the band (no latch, no W: it would never end)."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((20, 1))
    direction, label = ex._attempt_pathfinding_toward_target(agent, None, action_label="lbl",
                                                            force_fire_mode=True)
    assert (direction, label) == (NORTH, UAVExecutor.FIRE_RETREAT_LABEL)


def test_a_wait_keeps_its_direction_on_the_grid(monkeypatch):
    """(a4, review) a wait with a stale heading that points off the grid returns an on-grid direction."""
    _near_field_setting(monkeypatch)
    ex, agent = _searcher((25, 25))
    agent.selected_dir = WEST
    direction, label = ex._fire_no_path_step(agent, (0, 25), 99, 6, lambda cell: 99, set(), True,
                                             band_exit=False)
    assert label == UAVExecutor.FIRE_WAIT_LABEL and direction != WEST


def test_a_junk_wait_limit_raises_at_the_first_execute(monkeypatch):
    _near_field_setting(monkeypatch)
    monkeypatch.setattr(cfv, "SEARCHER_ROUTE_WAIT_LIMIT", 39.5, raising=False)
    ex, agent = _searcher((25, 25))
    with pytest.raises(ValueError):
        ex.execute(_decision(ex), 1.0)


def test_the_give_up_is_logged_for_repeat_analysis(monkeypatch):
    ex, agent = _walled(monkeypatch, limit=3)
    for step in (70, 71, 72):
        _at_step(ex, step)
        ex._attempt_pathfinding_toward_target(agent, (5.0, 25.0), action_label="lbl", force_fire_mode=True)
    assert _ws(ex)["route_give_up_log"] == [[72, 5, 25]]
