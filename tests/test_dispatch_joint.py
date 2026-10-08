"""Dispatch round, LIMIT 2 - joint route-aware assignment (outputs/dispatch_part1.txt sections 5, 13.3 T-J1..T-J13).

Every test is mutation-checked against the named mutant in its docstring (outputs/_dp_mutants.py records them):
it must FAIL on the mutant. Model-level tests drive the real WildFireModel and call J at its solve points.
"""

from __future__ import annotations

import pytest

import agents
from dispatch_test_support import (
    FF_A,
    FF_B,
    FF_C,
    V0,
    V1,
    V2,
    assign,
    binders,
    bound_to,
    burn,
    events,
    ff,
    j_post,
    pinned_model,
    place_units,
    place_victims,
    quiet_fire,
    switches,
    victim,
)
from src_extension.planning import joint_dispatch as jd
from wildfire_model import PhysicalRescueCommand, WildFireModel


@pytest.fixture
def model(monkeypatch):
    switches(monkeypatch, joint=1, reassign=0)
    m = pinned_model(monkeypatch)
    quiet_fire(m)
    return m


def test_tj1_crossing_pairs_are_uncrossed(model):
    """T-J1. Per-victim greedy in victim-index order binds victim_0 to its nearest unit A (4) and leaves
    victim_1 the far one B (18): total 22. J binds A->victim_1 (8), B->victim_0 (6): total 14.
    MUTANT tj1: solve_fill replaced by per-victim greedy in victim-index order."""
    place_units(model, {FF_A: (10, 10), FF_B: (10, 20)})
    place_victims(model, {V0: (10, 14), V1: (10, 2)})
    j_post(model)
    assert bound_to(model, FF_A) == V1
    assert bound_to(model, FF_B) == V0


def test_tj2_route_aware_choice_through_a_numpy_bool_fire_wall(model):
    """T-J2. A is Manhattan 3 from the victim but behind a burning wall (route 35); B is 10 away in the open.
    The wall is burning as numpy.bool_(True): a builder testing burning by identity with True sees no fire.
    MUTANT tj2: route distance replaced by Manhattan distance."""
    place_units(model, {FF_A: (20, 23), FF_B: (20, 10)})
    place_victims(model, {V0: (20, 20)})
    burn(model, [(x, 21) for x in range(0, 36)], numpy_bool=True)
    j_post(model)
    assert bound_to(model, FF_B) == V0
    assert bound_to(model, FF_A) is None
    event = events(model, "fill")[-1]
    assert event["unit"] == FF_B and event["distance"] == 10


def test_tj3_scarcity_serves_the_nearest_by_route(model):
    """T-J3 (ruling D-1 (a)). One free unit, two waiting victims: J serves the nearer by ROUTE (victim_1, 5),
    not the lower index (victim_0, 20) as today's re-dispatch order would.
    MUTANT tj3: the key puts victim index before route time (victim-index order)."""
    place_units(model, {FF_A: (25, 25)})
    place_victims(model, {V0: (25, 45), V1: (25, 30)})
    j_post(model)
    assert bound_to(model, FF_A) == V1
    assert binders(model, V0) == []


def _tie_case(model):
    place_units(model, {FF_A: (20, 20), FF_B: (30, 20)})
    place_victims(model, {V0: (25, 25), V1: (25, 15)})


def test_tj4_order_independence_pure():
    """T-J4 (pure). An exact tie (every pair 10): the result is the L5 choice whatever the input order.
    MUTANT tj4: inputs left unsorted and the L5 integer-id key removed (first found wins)."""
    dist = {(u, v): 10 for u in ("ff_unit_0", "ff_unit_1") for v in ("victim_0", "victim_1")}
    a = jd.solve_fill(["ff_unit_0", "ff_unit_1"], ["victim_0", "victim_1"], dist, {})
    b = jd.solve_fill(["ff_unit_1", "ff_unit_0"], ["victim_0", "victim_1"], dist, {})
    c = jd.solve_fill(["ff_unit_0", "ff_unit_1"], ["victim_1", "victim_0"], dist, {})
    assert a == b == c
    assert [(p.unit, p.victim) for p in a] == [("ff_unit_0", "victim_0"), ("ff_unit_1", "victim_1")]


@pytest.mark.parametrize("order", ["units", "victims", "incidents"])
def test_tj4_order_independence_model(model, order):
    """T-J4 (model). An exact tie (every pair 10): reversing the insertion order of the unit registry, of the victim
    registries, or the order in which the victim_confirmed incidents are drained does not change J's binds (the L5
    choice ff_unit_0 -> victim_0, ff_unit_1 -> victim_1).
    MUTANT tj4 (units, victims): J iterates units and victims in insertion order with a first-found fit.
    MUTANT tj4i (incidents): the generic pairing tail runs for victim_confirmed (per-incident greedy in drain
    order, today's behaviour)."""
    _tie_case(model)
    if order == "units":
        model.firefighter_marker_agents = dict(reversed(list(model.firefighter_marker_agents.items())))
    elif order == "victims":
        model.victim_marker_agents = dict(reversed(list(model.victim_marker_agents.items())))
        model.managed_victims = dict(reversed(list(model.managed_victims.items())))
    else:
        for vid in (V1, V0):
            model._handle_rescue_incident({"type": "victim_confirmed", "victim_id": vid, "reason": "initial"})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    assert bound_to(model, FF_B) == V1


def test_tj5_closed_route_is_never_bound(model):
    """T-J5. A victim enclosed by fire on all four sides (numpy bools): no bind, not written off, and the unit
    is not sent toward it (so it cannot raise route_blocked on it).
    MUTANT tj5: an infinite route distance replaced by a large finite cost."""
    place_units(model, {FF_A: (30, 30)})
    place_victims(model, {V0: (20, 20)})
    burn(model, [(21, 20), (19, 20), (20, 21), (20, 19)])
    j_post(model)
    assert bound_to(model, FF_A) is None
    state = model.managed_victims[V0]
    assert not state.unreachable and not state.cancelled
    assert str(victim(model, V0).status).lower() == "confirmed"
    assert str(ff(model, FF_A).status).lower() == "available"
    assert events(model) == []


def test_tj6_a_unit_freed_by_a_death_release_is_bound_the_same_step(model):
    """T-J6. A unit freed by a victim_dead release is offered the waiting victim at the same J-post (today: only
    at the next recycle / return / recovery kick); one freed by an unassign without any incident (the escape
    sweep's shape) at the next J-pre.
    MUTANT tj6: J skips a solve point unless a victim_confirmed / replacement incident was drained."""
    place_units(model, {FF_A: (10, 10)})
    place_victims(model, {V0: (12, 10), V1: (30, 30)})
    model._handle_rescue_incident({"type": "victim_confirmed", "victim_id": V0, "reason": "initial"})
    model._handle_rescue_incident({"type": "victim_confirmed", "victim_id": V1, "reason": "initial"})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    # victim_0 dies: the terminal release frees A; no incident about victim_1 is drained
    state = model.managed_victims[V0]
    state.status = "dead"
    state.cancelled = True
    victim(model, V0).status = "dead"
    model._handle_rescue_incident({"type": "victim_dead", "victim_id": V0, "reason": "fire_casualty"})
    assert bound_to(model, FF_A) is None
    j_post(model)
    assert bound_to(model, FF_A) == V1
    # an unassign with no incident at all (the escape sweep's shape), then J-pre
    model._execute_physical_rescue_via_executor(
        PhysicalRescueCommand(action="unassign", victim_id=V1, firefighter_id=FF_A, reason="test", metadata={})
    )
    ff(model, FF_A).status = "available"
    model._joint_dispatch_point("pre")
    assert bound_to(model, FF_A) == V1


def test_tj6_a_unit_free_between_steps_is_paired_at_j_pre_before_moving(model):
    """T-J6 (real step). A free unit and a waiting victim between two steps - the escape sweep's shape (freed after
    the post-move cycle, no incident): the next model step binds them at J-pre, the call at the end of
    _run_execution, before any unit moves (design 5.7).
    MUTANT tjpre: the J-pre call removed from _run_execution (the bind then waits for J-post, after the advance)."""
    import contextlib
    import io

    place_units(model, {FF_A: (10, 10)})
    place_victims(model, {V0: (14, 10)})
    with contextlib.redirect_stdout(io.StringIO()):
        model.step()
    fills = [e for e in events(model, "fill") if e["victim_id"] == V0]
    assert fills and (fills[0]["phase"], fills[0]["unit"]) == ("pre", FF_A)


def _audit(model) -> list[dict]:
    return list(getattr(model, "_physical_rescue_command_audit", []) or [])


def test_tj7_no_pairing_mid_advance_and_a_same_step_detection_is_seen(model):
    """T-J7. A route_blocked raise inside a unit's own move unassigns it (the 808 mechanism, kept) but pairs
    nothing; the replacement is chosen at J-post of the same step, which also sees a victim detected in that
    step's post-move cycle (case 2's step 46).
    The rebind carries the victim's pending cause: joint_replacement_after_blocked, event type
    dispatch_replacement_after_blocked (design 5.10); the same-step detection's bind carries joint_initial.
    MUTANT tj7: the generic pairing tail is not skipped for route_blocked incidents.
    MUTANT reason_const: every fill carries joint_initial (the pending cause dropped)."""
    place_units(model, {FF_A: (10, 10), FF_B: (30, 10), FF_C: (15, 10)})
    place_victims(model, {V0: (12, 10), V1: (32, 12)}, detected=[V0])
    j_post(model)
    assert bound_to(model, FF_A) == V0      # 2 < 3 (C) < 18 (B)
    assert bound_to(model, FF_B) is None and bound_to(model, FF_C) is None  # victim_1 not yet detected
    before = len(_audit(model))
    unit = ff(model, FF_A)
    unit.status = "route_blocked"
    model._on_firefighter_route_blocked(unit)
    new = _audit(model)[before:]
    assert [e["action"] for e in new] == ["unassign"]  # the raise's own unassign, and NO assign mid-advance
    assert binders(model, V0) == []
    # a same-step post-move detection, then J-post
    state = model.managed_victims[V1]
    state.confirmed = True
    j_post(model)
    assert bound_to(model, FF_C) == V0      # C -> V0 (3) + B -> V1 (4) beats C -> V1 (19) + B -> V0 (18)
    assert bound_to(model, FF_B) == V1
    reasons = {e["victim_id"]: e["reason"] for e in events(model, "fill")[1:]}
    assert reasons == {V0: "joint_replacement_after_blocked", V1: "joint_initial"}
    types = {e["victim_id"]: e["event_type"] for e in model._rescue_event_log if e["event_type"].startswith("dispatch")}
    assert types[V0] == "dispatch_replacement_after_blocked" and types[V1] == "dispatch_initial"


def test_tj7_real_step_no_assign_inside_the_advance(model, monkeypatch):
    """T-J7 (real step, phase spy). A burning row closes A's route to victim_0 before a real model step: A's own
    move raises route_blocked and is unassigned inside the advance; no assign command is issued while
    schedule.step() runs; J-post of the same step binds C (on the victim's side of the row) with the blocked
    cause's reason.
    MUTANT tj7."""
    place_units(model, {FF_A: (10, 5), FF_C: (20, 18)})
    place_victims(model, {V0: (10, 16)})
    j_post(model)
    assert bound_to(model, FF_A) == V0      # 11 < 12
    burn(model, [(x, 12) for x in range(50)])
    log: list[tuple[bool, str, str, str]] = []
    inside = [False]
    sink = model.apply_physical_rescue_command

    def spy_sink(cmd):
        log.append((inside[0], str(cmd.action).lower(), str(cmd.victim_id), str(cmd.firefighter_id)))
        return sink(cmd)

    advance = model.schedule.step

    def spy_advance(*args, **kwargs):
        inside[0] = True
        try:
            return advance(*args, **kwargs)
        finally:
            inside[0] = False

    monkeypatch.setattr(model, "apply_physical_rescue_command", spy_sink)
    monkeypatch.setattr(model.schedule, "step", spy_advance)
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        model.step()
    in_advance = [entry[1:] for entry in log if entry[0]]
    assert ("unassign", V0, FF_A) in in_advance        # the raise happened inside the advance
    assert [e for e in in_advance if e[0] == "assign"] == []
    assert bound_to(model, FF_C) == V0
    fill = [e for e in events(model, "fill") if e["victim_id"] == V0][-1]
    assert fill["unit"] == FF_C and fill["reason"] == "joint_replacement_after_blocked" and fill["phase"] == "post"


def test_tj8_casualty_with_an_empty_pool_waits_and_is_counted(model):
    """T-J8 (ruling D-6). A unit dies with every other unit busy and none off-grid: today's planner writes the
    victim off at once; under Limit 2 it waits (not unreachable) and the would-have-been write-off is counted.
    MUTANT tj8: J hands casualty victims to select_rescue_assignment (the legacy tail runs)."""
    place_units(model, {FF_A: (10, 10), FF_B: (30, 30)})
    place_victims(model, {V0: (12, 10), V1: (32, 30)})
    j_post(model)
    assert bound_to(model, FF_A) == V0 and bound_to(model, FF_B) == V1
    model._execute_physical_rescue_via_executor(
        PhysicalRescueCommand(
            action="unassign", victim_id=V0, firefighter_id=FF_A, reason="fire_casualty",
            metadata={"reset_victim_pending": True},
        )
    )
    unit = ff(model, FF_A)
    unit.dead = True
    unit.status = "dead"
    model._handle_rescue_incident(
        {"type": "firefighter_casualty", "victim_id": V0, "firefighter_id": FF_A, "reason": "replacement_after_casualty"}
    )
    j_post(model)
    state = model.managed_victims[V0]
    assert not state.unreachable and not state.cancelled
    assert str(victim(model, V0).status).lower() != "unreachable"
    assert int(getattr(model, "dispatch_writeoffs_avoided_total", 0)) == 1
    assert binders(model, V0) == []


def _kill_bound_unit(model, vid, ff_id):
    """A bound unit dies (the casualty sweep's shape): unassign with reset, marked dead, casualty incident."""
    model._execute_physical_rescue_via_executor(
        PhysicalRescueCommand(
            action="unassign", victim_id=vid, firefighter_id=ff_id, reason="fire_casualty",
            metadata={"reset_victim_pending": True},
        )
    )
    unit = ff(model, ff_id)
    unit.dead = True
    unit.status = "dead"
    model._handle_rescue_incident(
        {"type": "firefighter_casualty", "victim_id": vid, "firefighter_id": ff_id,
         "reason": "replacement_after_casualty"}
    )


def test_tj8_a_casualty_victim_is_rebound_with_the_casualty_reason(model):
    """T-J8 (reason). When a unit frees up, the casualty's victim is bound with joint_replacement_after_casualty,
    event type dispatch_replacement_after_casualty (design 5.10).
    MUTANT reason_const: every fill carries joint_initial."""
    place_units(model, {FF_A: (10, 10), FF_B: (30, 30)})
    place_victims(model, {V0: (12, 10), V1: (32, 30)})
    j_post(model)
    _kill_bound_unit(model, V0, FF_A)
    j_post(model)
    assert binders(model, V0) == []
    unit = ff(model, FF_C)          # a unit frees up (here: revived as a free unit)
    unit.dead = False
    unit.status = "available"
    model.grid.move_agent(unit, (14, 10))
    j_post(model)
    fill = events(model, "fill")[-1]
    assert (fill["victim_id"], fill["unit"], fill["reason"]) == (V0, FF_C, "joint_replacement_after_casualty")
    last = [e for e in model._rescue_event_log if e["victim_id"] == V0][-1]
    assert last["event_type"] == "dispatch_replacement_after_casualty"


def test_tj8_a_returning_unit_means_no_would_have_been_writeoff(model):
    """T-J8 (negative). With an off-grid unit returning, today's planner delays instead of writing off: the
    counter stays 0. MUTANT tj8cnt: the counter counts every casualty incident."""
    place_units(model, {FF_A: (10, 10), FF_B: (30, 30), FF_C: (40, 40)})
    place_victims(model, {V0: (12, 10), V1: (32, 30), V2: (5, 45)})
    j_post(model)
    assert bound_to(model, FF_C) == V2
    unit = ff(model, FF_C)
    model.grid.remove_agent(unit)
    unit.off_grid = True
    _kill_bound_unit(model, V0, FF_A)
    assert int(getattr(model, "dispatch_writeoffs_avoided_total", 0) or 0) == 0


def test_tj8_counterfactual_takes_units_in_drain_order(model):
    """T-J8 (drain order). Two units die in the same step with one free unit: today's planner gives the free unit
    to the first casualty and writes the second off - one would-have-been write-off, not zero.
    MUTANT tj8cf: the counterfactual ignores the units it already took this step."""
    place_units(model, {FF_A: (10, 10), FF_B: (30, 30)})
    place_victims(model, {V0: (12, 10), V1: (32, 30)})
    j_post(model)
    unit = ff(model, FF_C)
    unit.dead = False
    unit.status = "available"
    model.grid.move_agent(unit, (20, 20))
    model.evaluation_timesteps_counter = int(model.evaluation_timesteps_counter or 0) + 1
    _kill_bound_unit(model, V0, FF_A)
    _kill_bound_unit(model, V1, FF_B)
    assert int(getattr(model, "dispatch_writeoffs_avoided_total", 0) or 0) == 1
    assert [e["victim_id"] for e in model.dispatch_writeoffs_avoided] == [V1]
    model._joint_dispatch_point("post")
    assert not model.managed_victims[V0].unreachable and not model.managed_victims[V1].unreachable


def test_tj9_integer_tie_break():
    """T-J9. ff_unit_10 vs ff_unit_2 at equal route: the integer id decides (2 < 10), not the string.
    MUTANT tj9: ids compared as strings."""
    pairs = jd.solve_fill(
        ["ff_unit_10", "ff_unit_2"], ["victim_0"], {("ff_unit_10", "victim_0"): 5, ("ff_unit_2", "victim_0"): 5}, {}
    )
    assert [(p.unit, p.victim) for p in pairs] == [("ff_unit_2", "victim_0")]


def test_tj10_latched_held_victim_gets_a_second_claimant_under_limit2_alone(model):
    """T-J10 (D-7). Limit 2 alone: a victim whose only binder is latched (route_blocked, still bound) is bound to
    a free unit at J-post of the repeated-raise step, with no recycle / return / recovery kick in the scenario;
    the latched unit keeps its claim (today's dd0a1b9 hedge, made prompt).
    MUTANT tj10: latched-held victims excluded from the fill."""
    place_units(model, {FF_A: (10, 10), FF_B: (16, 10)})
    place_victims(model, {V0: (12, 10)})
    assert assign(model, V0, FF_A)
    ff(model, FF_A).status = "route_blocked"   # the repeated-raise state: bound, flagged
    j_post(model)
    assert binders(model, V0) == [FF_A, FF_B]
    assert bound_to(model, FF_A) == V0


def test_tj11_coverage_before_reuse_and_nearest_over_fresh():
    """T-J11 (round 2 C1, outputs/dispatch2_part1.txt 4.2). (i) Coverage first: with (B, v) re-used and B unable to
    reach w, the only maximum matching {A->w, B->v} is chosen although (A, v) is fresh. (ii) History never ranks a
    fill: among maximum matchings the SHORTER one wins although it re-uses a pair (round 1 chose the fresh one).
    (iii) On an exact tie of total and worst route the fresh pair wins (L4'). (iv) The LATCH-FILL cap still holds
    for a capped victim (the parameter stays; the round-2 model passes none).
    MUTANT c1_l2: round 1's L2 (fewest re-used pairs) restored ahead of the route keys. MUTANT c1_tie: the re-use
    tie-break dropped (ids decide an exact tie)."""
    A, B, v, w = "ff_unit_0", "ff_unit_1", "victim_0", "victim_1"
    dist = {(A, v): 5, (A, w): 5, (B, v): 5, (B, w): None}
    pairs = jd.solve_fill([A, B], [v, w], dist, {(B, v): 1})
    assert {(p.unit, p.victim) for p in pairs} == {(A, w), (B, v)}
    dist2 = {(A, v): 5, (A, w): 5, (B, v): 5, (B, w): 7}
    pairs2 = jd.solve_fill([A, B], [v, w], dist2, {(B, v): 1})
    assert {(p.unit, p.victim) for p in pairs2} == {(A, w), (B, v)}      # total 10 (re-used) beats 12 (fresh)
    dist3 = {(A, v): 5, (B, v): 5}
    assert [p.unit for p in jd.solve_fill([A, B], [v], dist3, {(A, v): 1})] == [B]
    assert jd.solve_fill([B], [v], {(B, v): 3}, {(B, v): 2}, capped=[v]) == []
    assert len(jd.solve_fill([B], [v], {(B, v): 3}, {(B, v): 1}, capped=[v])) == 1


def test_tj12_reason_strings_and_event_types():
    """T-J12. joint_* fill reasons map to the existing event types; reassign_* and joint_replace_latched to the one
    new type dispatch_reassignment, which prints like the other dispatch types; existing reasons unchanged.
    MUTANT tj12: the dispatch_reassignment branch removed."""
    f = WildFireModel._physical_rescue_event_type_from_reason
    assert f("joint_initial") == "dispatch_initial"
    assert f("joint_replacement_after_blocked") == "dispatch_replacement_after_blocked"
    assert f("joint_replacement_after_casualty") == "dispatch_replacement_after_casualty"
    for reason in ("reassign_stall", "reassign_margin", "joint_replace_latched"):
        assert f(reason) == "dispatch_reassignment"
    assert "dispatch_reassignment" in WildFireModel._RESCUE_EVENT_CONSOLE_TYPES
    for reason, expected in (
        ("initial", "dispatch_initial"),
        ("test_initial", "dispatch_initial"),
        ("replacement_after_blocked", "dispatch_replacement_after_blocked"),
        ("replacement_after_casualty", "dispatch_replacement_after_casualty"),
        ("victim_confirmed", "dispatch_initial"),
        ("", "dispatch_initial"),
    ):
        assert f(reason) == expected


def test_tj13_the_ledger_counts_every_bind_at_the_single_sink(model):
    """T-J13 (design 5.6). A bind issued outside J (straight through the command sink) is counted; a second bind
    of the same pair counts 2.
    MUTANT tj13: the ledger is counted inside J's own apply paths only (the sink line removed)."""
    place_units(model, {FF_A: (10, 10)})
    place_victims(model, {V0: (12, 10)})
    assert assign(model, V0, FF_A)
    assert model._dispatch_ledger[(FF_A, V0)] == 1
    model._execute_physical_rescue_via_executor(
        PhysicalRescueCommand(action="unassign", victim_id=V0, firefighter_id=FF_A, reason="t",
                              metadata={"reset_victim_pending": True})
    )
    ff(model, FF_A).status = "available"
    assert assign(model, V0, FF_A)
    assert model._dispatch_ledger[(FF_A, V0)] == 2
