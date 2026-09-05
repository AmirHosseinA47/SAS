"""Phantom rescue: a victim may hold two claimants - the route_blocked
replacement pathway depends on it, and in the only recorded episode the second
claimant was the unit that actually rescued the victim - so when the victim
turns terminal every OTHER claimant must be released, on rescue_complete and on
victim_dead alike, and a released unit must re-enter the dispatch pool: a
route_blocked one through the revalidation pass.

Drives the real WildFireModel through the executor and the incident handler,
the way test_dead_victim_rescue_recall does, plus one end-to-end pass through
the post-move drain.
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
from src_extension.planning.rescue_planner import select_rescue_assignment
from wildfire_model import PhysicalRescueCommand, WildFireModel

V0 = "victim_0"
V1 = "victim_1"
FF_A = "ff_unit_0"
FF_B = "ff_unit_1"
FF_C = "ff_unit_2"
# Ignition is random in [10, 39]^2 (SystemRandom, unseeded in tests) and may land
# near these cells. No assertion below reads a unit position after advance(), and
# a single burning cell can neither enclose a unit nor cut the revalidation BFS.
CELL = (20, 20)
CELL_A = (18, 20)
CELL_B = (22, 20)
OTHER_CELL = (10, 12)
FAR_CORNER = (49, 49)
EXIT_CELL = (0, 20)
# closer to CELL_B than to EXIT_CELL, so the re-dispatch pick does not depend on
# whether the completer is off-grid (Feature 1 on) or recycled at the exit (off)
DRAIN_VICTIM_CELL = (30, 14)
RELEASE_REASON = "released_after_rescue_complete"


def _fresh_model() -> WildFireModel:
    model = WildFireModel()
    model.debug_log = False
    return model


def _ff(model: WildFireModel, ff_id: str) -> agents.Firefighter:
    return model.firefighter_marker_agents[ff_id]


def _reset_all_ff(model: WildFireModel) -> None:
    for ff in model.firefighter_marker_agents.values():
        ff.dead = False
        ff.assigned = False
        ff.target_pos = None
        ff.rescued_victim = None
        ff.exiting = False
        ff.exit_target = None
        ff.rescue_completed = False
        ff.status = "available"


def _park(model: WildFireModel, ff_id: str, cell: tuple[int, int]) -> agents.Firefighter:
    ff = _ff(model, ff_id)
    model.grid.move_agent(ff, cell)
    return ff


def _confirm_victim(model: WildFireModel, vid: str, cell: tuple[int, int]) -> agents.Victim:
    marker = model.victim_marker_agents[vid]
    state = model.managed_victims[vid]
    model.grid.move_agent(marker, cell)
    if hasattr(marker, "spawn_cell"):
        marker.spawn_cell = cell
    if hasattr(marker, "leash_anchor"):
        marker.leash_anchor = cell
    state.confirmed = True
    state.status = "confirmed"
    state.rescue_assigned = False
    state.assigned = False
    marker.status = "confirmed"
    return marker


def _assign(model: WildFireModel, vid: str, ff_id: str) -> bool:
    marker = model.victim_marker_agents[vid]
    return bool(
        model.apply_physical_rescue_command(
            PhysicalRescueCommand(
                action="assign",
                victim_id=vid,
                firefighter_id=ff_id,
                reason="initial",
                metadata={"victim_marker": marker, "target_pos": tuple(marker.pos)},
            )
        )
    )


def _complete(model: WildFireModel, vid: str, ff_id: str) -> None:
    """What the drain does for the completing unit: finalize, then take the victim off the grid."""
    marker = model.victim_marker_agents[vid]
    model._finalize_rescued_victim(vid, marker, firefighter_id=ff_id)
    if getattr(marker, "pos", None) is not None:
        model.grid.remove_agent(marker)
    try:
        model.schedule.remove(marker)
    except Exception:
        pass


def _unassign_audit(model: WildFireModel) -> list[dict]:
    return [
        e
        for e in list(getattr(model, "_physical_rescue_command_audit", []) or [])
        if e.get("action") == "unassign"
    ]


def _events(model: WildFireModel, event_type: str, vid: str) -> list[dict]:
    return [
        e
        for e in list(getattr(model, "_rescue_event_log", []) or [])
        if e.get("event_type") == event_type and e.get("victim_id") == vid
    ]


def _double_claim(model: WildFireModel):
    """Two live claimants on victim_0: A at CELL_A, B at CELL_B, C parked out of the way."""
    _reset_all_ff(model)
    marker = _confirm_victim(model, V0, CELL)
    ff_a = _park(model, FF_A, CELL_A)
    ff_b = _park(model, FF_B, CELL_B)
    _park(model, FF_C, FAR_CORNER)
    # Both accepted: double assignment stays PERMITTED by design (fix (b), not (a)).
    assert _assign(model, V0, FF_A)
    assert _assign(model, V0, FF_B)
    assert ff_a.rescued_victim is marker and ff_b.rescued_victim is marker
    assert ff_a.assigned and ff_b.assigned
    return marker, ff_a, ff_b


def _complete_as_carrier(model: WildFireModel, ff: agents.Firefighter, vid: str) -> None:
    """The state Firefighter.advance leaves the carrier in at its exit cell, then the finalize."""
    ff.exiting = True
    ff.exit_target = tuple(ff.pos)
    ff.rescue_completed = True
    _complete(model, vid, ff.unit_id)


def test_second_claimant_released_when_first_completes(capsys) -> None:
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)

    _complete_as_carrier(model, ff_a, V0)

    assert model.managed_victims[V0].rescued is True
    # the loser is fully released ...
    assert ff_b.assigned is False
    assert ff_b.target_pos is None
    assert ff_b.rescued_victim is None
    assert ff_b.exiting is False
    assert ff_b.exit_target is None
    assert ff_b.rescue_completed is False
    assert ff_b.status == "available"
    # ... in place, and immediately dispatchable
    assert tuple(ff_b.pos) == CELL_B
    assert model._firefighter_available_for_dispatch(ff_b) is True
    assert model.ff_claims_released_total == 1
    out = capsys.readouterr().out
    assert f"[Rescue Released] FF-{FF_B} released from {V0} reason={RELEASE_REASON}" in out
    audit = _unassign_audit(model)
    assert [(e["firefighter_id"], e["reason"], e["success"]) for e in audit] == [
        (FF_B, RELEASE_REASON, True)
    ]


def test_completing_unit_is_not_touched_by_the_release() -> None:
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)

    _complete_as_carrier(model, ff_a, V0)

    # the drain, not the incident handler, finishes the carrier
    assert ff_a.exiting is True
    assert ff_a.rescue_completed is True
    assert ff_a.rescued_victim is marker
    assert ff_a.assigned is True
    assert ff_b.rescued_victim is None


def test_released_unit_no_longer_walks_to_the_stale_target() -> None:
    """The probe's Q2 as a unit test: no phantom exit after the release."""
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    _complete_as_carrier(model, ff_a, V0)

    for _ in range(12):
        ff_b.advance()
        assert ff_b.exiting is False
        assert ff_b.target_pos is None
        assert ff_b.rescued_victim is None
    assert marker.pos is None


def test_released_unit_is_the_planner_pick_for_the_next_victim() -> None:
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    _complete_as_carrier(model, ff_a, V0)
    other = _confirm_victim(model, V1, OTHER_CELL)

    snapshot = model.get_rescue_operational_snapshot()
    assert snapshot["firefighters"][FF_B]["available"] is True
    assert snapshot["firefighters"][FF_B]["assigned"] is False
    assert snapshot["firefighters"][FF_B]["target_victim_id"] is None
    decision = select_rescue_assignment(snapshot, "initial", victim_id=V1)
    assert str(decision.rescue_action).lower() == "assign"
    assert decision.firefighter_id == FF_B

    model._try_dispatch_unresolved_confirmed_victims()
    assert ff_b.assigned is True
    assert ff_b.rescued_victim is other
    assert ff_b.target_pos == OTHER_CELL


def test_release_relabels_the_knowledge_model_as_available() -> None:
    """D2: without the relabel the unit is freed in fact but reported as assigned."""
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    _complete_as_carrier(model, ff_a, V0)

    fields = model._derive_firefighter_operational_fields(ff_b, None)
    assert fields["availability_status"] == "available"
    assert fields["assignment_state"] == "unassigned"
    assert fields["route_state"] == "idle"
    managed = model.managed_firefighters[FF_B]
    assert managed.availability == "available"
    assert managed.assignment_state == "unassigned"
    assert managed.route_state == "idle"
    ff_model = getattr(model, "firefighter_model", None)
    unit = getattr(ff_model, "units", {}).get(FF_B) if ff_model is not None else None
    if unit is not None:
        assert unit.is_assigned is False
        assert unit.availability_status == "available"
        assert (getattr(unit, "target_victim", None) or None) is None


def test_route_blocked_claimant_is_released_and_recovered_by_revalidation() -> None:
    """The 70e1b33 shape: a blocked second claimant must not be left latched."""
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    # the repeat-block state the incident handler leaves behind: still bound, flagged
    ff_b.status = "route_blocked"
    assert model._find_active_firefighter_for_victim(V0, marker) == (FF_A, ff_a)

    _complete_as_carrier(model, ff_a, V0)

    assert ff_b.assigned is False
    assert ff_b.rescued_victim is None
    assert ff_b.target_pos is None
    assert ff_b.exiting is False
    # the flag is left for the revalidation pass, so not dispatchable yet
    assert ff_b.status == "route_blocked"
    assert model._firefighter_available_for_dispatch(ff_b) is False
    assert model.managed_firefighters[FF_B].assignment_state == "unassigned"

    other = _confirm_victim(model, V1, OTHER_CELL)
    model._revalidate_route_blocked_firefighters()
    assert ff_b.status != "route_blocked"
    # the pass re-runs dispatch for waiting victims and the recovered unit is the pick
    assert ff_b.assigned is True
    assert ff_b.rescued_victim is other


def test_single_claimant_completion_emits_no_release(capsys) -> None:
    """Runs without a second claimant must stay byte-identical: no line, no command."""
    model = _fresh_model()
    _reset_all_ff(model)
    marker = _confirm_victim(model, V0, CELL)
    ff_a = _park(model, FF_A, CELL_A)
    _park(model, FF_B, CELL_B)
    _park(model, FF_C, FAR_CORNER)
    assert _assign(model, V0, FF_A)
    before = len(_unassign_audit(model))

    _complete_as_carrier(model, ff_a, V0)

    assert model.managed_victims[V0].rescued is True
    assert len(_unassign_audit(model)) == before
    assert "[Rescue Released]" not in capsys.readouterr().out
    assert model.ff_claims_released_total == 0
    assert _ff(model, FF_B).status == "available" and _ff(model, FF_B).assigned is False


def test_completion_for_an_already_rescued_victim_releases_a_straggler() -> None:
    """D3: the phantom's own signature - rescue_complete arriving for a rescued victim."""
    model = _fresh_model()
    _reset_all_ff(model)
    marker = _confirm_victim(model, V0, CELL)
    ff_a = _park(model, FF_A, CELL_A)
    ff_b = _park(model, FF_B, CELL_B)
    _park(model, FF_C, FAR_CORNER)
    assert _assign(model, V0, FF_A)
    _complete_as_carrier(model, ff_a, V0)
    assert len(_events(model, "rescue_complete", V0)) == 1

    # a straggler bound to the rescued victim, as the pre-fix run left it
    ff_b.assigned = True
    ff_b.rescued_victim = marker
    ff_b.target_pos = CELL
    ff_b.status = "en_route"
    # a later step: _record_rescue_event drops a second rescue_complete for the
    # same victim only when it lands on the SAME step, so the assertions below
    # must not be able to pass on that guard alone
    model.evaluation_timesteps_counter = int(model.evaluation_timesteps_counter or 0) + 47

    model._handle_rescue_incident(
        {"type": "rescue_complete", "victim_id": V0, "firefighter_id": FF_B}
    )

    assert ff_b.assigned is False
    assert ff_b.rescued_victim is None
    assert ff_b.target_pos is None
    assert ff_b.status == "available"
    assert model.managed_victims[V0].rescued is True
    # no second rescue_complete event, no double-count, no second finalize command
    assert len(_events(model, "rescue_complete", V0)) == 1
    finalizes = [
        e for e in model._physical_rescue_command_audit if e.get("action") == "finalize_rescue"
    ]
    assert len(finalizes) == 1


def test_victim_dead_releases_every_claimant_including_route_blocked() -> None:
    """D1: one helper, one behaviour - the recall no longer skips route_blocked units."""
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    ff_b.status = "route_blocked"
    state = model.managed_victims[V0]
    marker.status = "dead"
    state.status = "dead"
    state.dead = True
    state.cancelled = True

    model._handle_rescue_incident(
        {"type": "victim_dead", "victim_id": V0, "firefighter_id": None, "reason": "fire_casualty"}
    )

    for ff in (ff_a, ff_b):
        assert ff.assigned is False
        assert ff.rescued_victim is None
        assert ff.target_pos is None
        assert ff.exiting is False
    assert ff_a.status == "available"
    assert ff_b.status == "route_blocked"
    assert sorted((e["firefighter_id"], e["reason"]) for e in _unassign_audit(model)) == [
        (FF_A, "fire_casualty"),
        (FF_B, "fire_casualty"),
    ]
    assert model.ff_claims_released_total == 2


def test_victim_dead_with_one_visible_claimant_is_the_old_recall_plus_relabel() -> None:
    model = _fresh_model()
    _reset_all_ff(model)
    marker = _confirm_victim(model, V0, CELL)
    ff_a = _park(model, FF_A, CELL_A)
    _park(model, FF_B, CELL_B)
    _park(model, FF_C, FAR_CORNER)
    assert _assign(model, V0, FF_A)
    state = model.managed_victims[V0]
    marker.status = "dead"
    state.status = "dead"
    state.dead = True
    state.cancelled = True

    model._handle_rescue_incident(
        {"type": "victim_dead", "victim_id": V0, "firefighter_id": None, "reason": "fire_casualty"}
    )

    assert ff_a.assigned is False and ff_a.rescued_victim is None and ff_a.target_pos is None
    assert ff_a.status == "available"
    assert [(e["firefighter_id"], e["reason"]) for e in _unassign_audit(model)] == [
        (FF_A, "fire_casualty")
    ]
    assert _ff(model, FF_B).assigned is False


def test_drain_end_to_end_releases_loser_and_redispatches_it() -> None:
    """The production path: advance() completes at the exit cell -> drain -> release -> re-dispatch."""
    model = _fresh_model()
    _reset_all_ff(model)
    marker = _confirm_victim(model, V0, CELL)
    ff_a = _park(model, FF_A, CELL_A)
    ff_b = _park(model, FF_B, CELL_B)
    _park(model, FF_C, FAR_CORNER)
    assert _assign(model, V0, FF_A)
    assert _assign(model, V0, FF_B)
    other = _confirm_victim(model, V1, DRAIN_VICTIM_CELL)

    # A is carrying the victim and stands on its exit cell
    model.grid.move_agent(ff_a, EXIT_CELL)
    model.grid.move_agent(marker, EXIT_CELL)
    ff_a.exiting = True
    ff_a.exit_target = EXIT_CELL
    model._agents_pending_removal = []
    ff_a.advance()
    assert ff_a.rescue_completed is True
    assert ff_a in model._agents_pending_removal and marker in model._agents_pending_removal

    handled = model._process_pending_agent_removals()

    assert handled >= 2
    assert model.managed_victims[V0].rescued is True
    assert marker.pos is None
    # the carrier went through its own hand-over (off-grid absence or recycle), untouched by the release
    assert ff_a.assigned is False and ff_a.rescued_victim is None
    assert ff_a.pos is None or ff_a.status == "available"
    removals = [e for e in model._ff_absence_log if e.get("event") == "removed"]
    assert [e["ff"] for e in removals] in ([], [FF_A])
    # the loser was released and picked up by the re-dispatch pass in the same drain
    assert model.ff_claims_released_total == 1
    assert ff_b.exiting is False
    assert ff_b.assigned is True
    assert ff_b.rescued_victim is other
    assert ff_b.target_pos == DRAIN_VICTIM_CELL
    assert model.pending_removal_failures_last_step == 0


def test_release_when_incident_names_the_loser_still_frees_the_loser() -> None:
    """Review finding: without a firefighter id, _finalize_rescued_victim names
    managed_victims[vid].firefighter_id = the LAST-assigned unit. In a double
    claim that is the loser. Keeping it by id alone would release nobody."""
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    # B was assigned last, so the fallback names B
    assert model.managed_victims[V0].firefighter_id == FF_B
    assert model._firefighter_id_for_victim(V0) == FF_B
    ff_a.exiting = True
    ff_a.exit_target = tuple(ff_a.pos)
    ff_a.rescue_completed = True

    model._finalize_rescued_victim(V0, marker)  # no firefighter id at all

    assert model.managed_victims[V0].rescued is True
    # the loser is released even though the incident named it ...
    assert ff_b.assigned is False and ff_b.rescued_victim is None and ff_b.status == "available"
    # ... and the carrier, protected by its own state, is not
    assert ff_a.exiting is True and ff_a.rescue_completed is True and ff_a.rescued_victim is marker
    assert model.ff_claims_released_total == 1


def test_named_unit_is_kept_only_while_carrying() -> None:
    """A named unit that is exiting with the victim is the carrier and is kept;
    a named unit that is merely bound is a stale claimant and is released."""
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    ff_a.exiting = True
    ff_a.exit_target = tuple(ff_a.pos)
    # not yet rescue_completed: a directly reported completion mid-carry
    model._finalize_rescued_victim(V0, marker, firefighter_id=FF_A)
    assert ff_a.exiting is True and ff_a.rescued_victim is marker
    assert ff_b.assigned is False and ff_b.rescued_victim is None

    model2 = _fresh_model()
    marker2, ff_a2, ff_b2 = _double_claim(model2)
    # name A, but A is not carrying anything: both stale claimants are released
    model2._finalize_rescued_victim(V0, marker2, firefighter_id=FF_A)
    assert ff_a2.assigned is False and ff_a2.rescued_victim is None
    assert ff_b2.assigned is False and ff_b2.rescued_victim is None
    assert model2.ff_claims_released_total == 2


def test_release_counter_is_split_by_reason() -> None:
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    _complete_as_carrier(model, ff_a, V0)
    assert model.ff_claims_released_by_reason == {RELEASE_REASON: 1}

    other = _confirm_victim(model, V1, OTHER_CELL)
    ff_b.status = "available"
    assert _assign(model, V1, FF_B)
    state = model.managed_victims[V1]
    other.status = "dead"
    state.status = "dead"
    state.dead = True
    state.cancelled = True
    model._handle_rescue_incident(
        {"type": "victim_dead", "victim_id": V1, "firefighter_id": None, "reason": "fire_casualty"}
    )
    assert ff_b.assigned is False and ff_b.rescued_victim is None
    assert model.ff_claims_released_by_reason == {RELEASE_REASON: 1, "fire_casualty": 1}
    assert model.ff_claims_released_total == 2


def test_named_exiting_unit_is_released_once_a_completer_exists() -> None:
    """Double carry plus the no-id fallback naming the second carrier: the true
    completer is protected by rescue_completed, so the name must not protect an
    exiting unit that has not completed."""
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    ff_a.exiting = True
    ff_a.exit_target = tuple(ff_a.pos)
    ff_a.rescue_completed = True
    ff_b.exiting = True                # second carrier, still walking
    ff_b.exit_target = (49, 20)
    assert model._firefighter_id_for_victim(V0) == FF_B   # the fallback names the loser

    model._finalize_rescued_victim(V0, marker)             # no firefighter id

    assert ff_a.exiting is True and ff_a.rescue_completed is True and ff_a.rescued_victim is marker
    assert ff_b.assigned is False and ff_b.exiting is False and ff_b.rescued_victim is None
    assert ff_b.status == "available"


def test_dead_claimant_is_skipped_and_the_others_released() -> None:
    model = _fresh_model()
    _reset_all_ff(model)
    marker = _confirm_victim(model, V0, CELL)
    ff_a = _park(model, FF_A, CELL_A)
    ff_b = _park(model, FF_B, CELL_B)
    ff_c = _park(model, FF_C, (20, 22))
    for ff_id in (FF_A, FF_B, FF_C):
        assert _assign(model, V0, ff_id)
    # C died still bound (the casualty sweep would normally unassign it first)
    ff_c.dead = True
    ff_c.status = "dead"
    availability_before = model.managed_firefighters[FF_C].availability

    _complete_as_carrier(model, ff_a, V0)

    assert ff_b.assigned is False and ff_b.rescued_victim is None
    assert ff_c.dead is True and ff_c.rescued_victim is marker     # untouched
    assert model.managed_firefighters[FF_C].availability == availability_before
    assert [e["firefighter_id"] for e in _unassign_audit(model)] == [FF_B]
    assert model.ff_claims_released_total == 1


def test_relabel_failure_does_not_undo_or_hide_the_release(capsys, monkeypatch) -> None:
    model = _fresh_model()
    _reset_all_ff(model)
    marker = _confirm_victim(model, V0, CELL)
    ff_a = _park(model, FF_A, CELL_A)
    ff_b = _park(model, FF_B, CELL_B)
    ff_c = _park(model, FF_C, (20, 22))
    for ff_id in (FF_A, FF_B, FF_C):
        assert _assign(model, V0, ff_id)

    real_sync = model._sync_firefighter_operational_knowledge
    calls = {"n": 0}

    def flaky_sync(ids=None):
        # the unassign action itself syncs (must keep working); fail only the
        # relabel sync of the first released unit
        if ids and ids == [FF_B]:
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("knowledge model unavailable")
        return real_sync(ids)

    monkeypatch.setattr(model, "_sync_firefighter_operational_knowledge", flaky_sync)
    _complete_as_carrier(model, ff_a, V0)
    out = capsys.readouterr().out

    assert ff_b.assigned is False and ff_b.rescued_victim is None      # unassign applied
    assert ff_c.assigned is False and ff_c.rescued_victim is None      # the loop went on
    assert model.ff_claims_released_total == 2
    assert f"[Rescue Released] FF-{FF_B}" in out
    assert f"[Rescue Release] FF-{FF_B} relabel failed: RuntimeError" in out
    assert "[Rescue Release Failed]" not in out


def test_route_blocked_release_with_no_victim_left_clears_the_flag(capsys) -> None:
    """The gate case: released while blocked, and nothing left to be blocked from."""
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    ff_b.status = "route_blocked"
    # every other victim already terminal, so no live victim remains after V0
    for vid, state in model.managed_victims.items():
        if vid == V0:
            continue
        state.status = "rescued"
        state.rescued = True
        model.victim_marker_agents[vid].status = "rescued"

    _complete_as_carrier(model, ff_a, V0)

    assert model._any_victim_needs_rescue() is False
    assert ff_b.assigned is False and ff_b.rescued_victim is None
    assert ff_b.status == "available"
    assert model._firefighter_available_for_dispatch(ff_b) is True
    out = capsys.readouterr().out
    assert f"[Route Cleared] FF-{FF_B} released with no victim left to reach" in out


def test_route_blocked_release_with_a_live_victim_leaves_the_flag_to_the_pass() -> None:
    model = _fresh_model()
    marker, ff_a, ff_b = _double_claim(model)
    ff_b.status = "route_blocked"
    _confirm_victim(model, V1, OTHER_CELL)          # live work exists
    assert model._any_victim_needs_rescue() is True

    _complete_as_carrier(model, ff_a, V0)

    assert ff_b.assigned is False and ff_b.rescued_victim is None
    assert ff_b.status == "route_blocked"           # the revalidation pass owns it
    model._revalidate_route_blocked_firefighters()
    assert ff_b.status != "route_blocked"


def test_same_step_co_completer_is_recycled_without_an_absence() -> None:
    """Two carriers of one victim reaching the exit in the same step: one
    hand-over, one absence at most; the other is recycled in place."""
    model = _fresh_model()
    _reset_all_ff(model)
    marker = _confirm_victim(model, V0, CELL)
    ff_a = _park(model, FF_A, CELL_A)
    ff_b = _park(model, FF_B, CELL_B)
    _park(model, FF_C, FAR_CORNER)
    assert _assign(model, V0, FF_A)
    assert _assign(model, V0, FF_B)
    for ff in (ff_a, ff_b):
        model.grid.move_agent(ff, EXIT_CELL)
        ff.exiting = True
        ff.exit_target = EXIT_CELL
    model.grid.move_agent(marker, EXIT_CELL)
    model._agents_pending_removal = []
    ff_a.advance()
    ff_b.advance()
    assert ff_a.rescue_completed is True and ff_b.rescue_completed is True
    assert [type(x).__name__ for x in model._agents_pending_removal] == [
        "Firefighter", "Victim", "Firefighter", "Victim"
    ]
    removals_before = int(model.ff_absence_removals_total or 0)

    model._process_pending_agent_removals()

    assert model.managed_victims[V0].rescued is True
    assert len(_events(model, "rescue_complete", V0)) == 1
    removals = [e for e in model._ff_absence_log if e.get("event") == "removed"]
    assert [e["ff"] for e in removals] in ([FF_A], [])       # A alone, or nobody with absence off
    assert model.ff_absence_removals_total - removals_before <= 1
    # B had nothing to hand over: recycled in place, on the grid, dispatchable
    assert ff_b.pos is not None
    assert ff_b.status == "available"
    assert ff_b.exiting is False and ff_b.rescue_completed is False and ff_b.rescued_victim is None
    assert model._firefighter_available_for_dispatch(ff_b) is True
    assert model.pending_removal_failures_last_step == 0
