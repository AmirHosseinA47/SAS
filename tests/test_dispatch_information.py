"""Dispatch round - the information rule, the switches and the binding invariants (outputs/dispatch_part1.txt
sections 9, 10, 7.4; 13.3 T-INFO-a..c, T-SW, T-INV).

Every test is mutation-checked against the named mutant in its docstring (outputs/_dp_mutants.py records them).
"""

from __future__ import annotations

import inspect
import io
from contextlib import redirect_stdout

import pytest

import agents
import common_fixed_variables as cfv
from dispatch_test_support import (
    FF_A,
    FF_B,
    FF_C,
    V0,
    V1,
    V2,
    V3,
    V4,
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
import wildfire_model as wf


# ============================================================================ T-INFO-a: the read trap

class _TrapError(AssertionError):
    pass


class _TrapState:
    """An undetected victim's managed state: only the detection flag may be read."""

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattribute__(self, name):
        if name == "confirmed":
            return bool(object.__getattribute__(self, "_real").confirmed)
        if name in ("__class__",):
            return object.__getattribute__(self, name)
        raise _TrapError(f"undetected victim state read: {name}")


class _TrapMarker:
    """An undetected victim's marker: nothing may be read."""

    def __getattribute__(self, name):
        if name in ("__class__",):
            return object.__getattribute__(self, name)
        raise _TrapError(f"undetected victim marker read: {name}")

    def __eq__(self, other):
        raise _TrapError("undetected victim marker compared")

    __hash__ = object.__hash__


def _setup_info(model):
    """Two detected victims, three undetected ones placed right beside the free units (the most tempting)."""
    place_units(model, {FF_A: (10, 10), FF_B: (30, 30)})
    place_victims(
        model,
        {V0: (10, 30), V1: (30, 12), V2: (10, 11), V3: (30, 31), V4: (11, 10)},
        detected=[V0, V1],
    )


def _decide(model, monkeypatch):
    """Run J with its APPLY layer recording instead of binding, so only the builder, the BFS, the solver and
    the progress code run (the scope of design 9.3)."""
    decisions = []

    def record_fill(view, vid, uid, distance, phase, *, kind, stage):
        decisions.append((kind, vid, uid, int(distance)))
        return True

    def record_replace(view, vid, old_units, new_uid, reason, distance, phase, *, kind, stage):
        decisions.append((kind, vid, new_uid, int(distance)))
        return True

    monkeypatch.setattr(model, "_dispatch_fill_bind", record_fill)
    monkeypatch.setattr(model, "_dispatch_replace", record_replace)
    model._joint_dispatch_point("post")
    return sorted(decisions)


def _decide_frames(model, monkeypatch, frames, loop):
    """J-post over several frames with the apply layer recording (nothing is bound), the incumbent moving along
    `loop` - so the progress, clean-approach, persistence and replacement code all run."""
    decisions = []

    def record_fill(view, vid, uid, distance, phase, *, kind, stage):
        decisions.append((model.evaluation_timesteps_counter, kind, vid, uid))
        return True

    def record_replace(view, vid, old_units, new_uid, reason, distance, phase, *, kind, stage):
        decisions.append((model.evaluation_timesteps_counter, kind, vid, new_uid))
        return True

    monkeypatch.setattr(model, "_dispatch_fill_bind", record_fill)
    monkeypatch.setattr(model, "_dispatch_replace", record_replace)
    for frame in range(frames):
        if loop:
            ff_id, cells = loop
            model.grid.move_agent(ff(model, ff_id), cells[frame % len(cells)])
        j_post(model)
    return decisions


@pytest.mark.parametrize("reassign", [0, 1])
def test_tinfo_a_no_attribute_of_an_undetected_victim_is_read(monkeypatch, reassign):
    """T-INFO-a. Undetected victims' managed states allow ONLY `confirmed`; their markers allow nothing. J's
    builder, BFS, solver and (reassign = 1) progress, clean-approach, persistence and replacement code run over
    several frames without touching them: victim_0 is bound to a far incumbent A that loops, victim_1 waits, B
    fills victim_1 and C - a spare 21 closer to victim_0 - is chosen as a margin replacement at the third frame.
    The undetected victims stand beside every unit.
    MUTANT tinfo: the builder reads the undetected victims (their state and marker)."""
    switches(monkeypatch, joint=1, reassign=reassign)
    model = pinned_model(monkeypatch)
    quiet_fire(model)
    place_units(model, {FF_A: (10, 5), FF_B: (30, 30), FF_C: (12, 28)})
    place_victims(
        model, {V0: (10, 30), V1: (30, 12), V2: (10, 6), V3: (30, 31), V4: (12, 27)}, detected=[V0, V1]
    )
    assert assign(model, V0, FF_A)
    for vid in (V2, V3, V4):
        monkeypatch.setitem(model.managed_victims, vid, _TrapState(model.managed_victims[vid]))
        monkeypatch.setitem(model.victim_marker_agents, vid, _TrapMarker())
    decisions = _decide_frames(model, monkeypatch, 4, (FF_A, [(11, 5), (10, 5)]))
    assert {(kind, vid, uid) for _, kind, vid, uid in decisions if kind == "fill"} == {("fill", V1, FF_B)}
    replaces = [(kind, vid, uid) for _, kind, vid, uid in decisions if kind == "replace"]
    if reassign:
        assert replaces and replaces[0] == ("replace", V0, FF_C)
        assert model._dispatch_progress[(FF_A, V0)].k >= 1   # the progress code ran under the trap
    else:
        assert replaces == []


def _perturb_undetected(model):
    """The truth of every undetected victim changes: fate, status, flags, position (beside the units)."""
    for vid, cell in ((V2, (10, 12)), (V3, (29, 30)), (V4, (12, 10))):
        marker = victim(model, vid)
        state = model.managed_victims[vid]
        model.grid.move_agent(marker, cell)
        marker.status = "dead"
        state.status = "rescued"
        state.rescued, state.cancelled, state.unreachable = True, True, True


def test_tinfo_b_metamorphic_undetected_truth_changes_nothing(monkeypatch):
    """T-INFO-b (one frame). Perturbing every undetected victim's truth (cells, statuses, fates) - with the
    detected-id set asserted identical first - leaves J's decisions identical.
    MUTANT tinfo."""
    switches(monkeypatch, joint=1, reassign=1)
    model = pinned_model(monkeypatch)
    quiet_fire(model)
    _setup_info(model)
    detected_before = set(wf._detected_victim_ids(model))
    before = _decide(model, monkeypatch)
    _perturb_undetected(model)
    assert set(wf._detected_victim_ids(model)) == detected_before
    after = _decide(model, monkeypatch)
    assert before == after and before


def test_tinfo_b_metamorphic_applied_binds(monkeypatch):
    """T-INFO-b (one frame, applied). The same with the binds applied: the assign / unassign audit is identical.
    MUTANT tinfo."""
    switches(monkeypatch, joint=1, reassign=1)
    logs = []
    for perturb in (False, True):
        model = pinned_model(monkeypatch)
        quiet_fire(model)
        _setup_info(model)
        if perturb:
            _perturb_undetected(model)
        j_post(model)
        logs.append([
            (e["action"], e["victim_id"], e["firefighter_id"], e["success"])
            for e in model._physical_rescue_command_audit
        ])
    assert logs[0] == logs[1] and logs[0]


def _perturb_fates(model):
    """Undetected victims' managed fates and flags change (rescued / cancelled / unreachable, statuses)."""
    for vid in (V2, V3, V4):
        state = model.managed_victims[vid]
        state.status = "rescued"
        state.rescued, state.cancelled, state.unreachable = True, True, True


def _perturb_cells(model):
    """Undetected victims moved onto the cells right beside the detected ones (the most tempting cells)."""
    for vid, near in ((V2, V0), (V3, V1), (V4, V0)):
        cell = victim(model, near).pos
        target = (min(49, int(cell[0]) + 1), int(cell[1]))
        model.grid.move_agent(victim(model, vid), target)


def _perturb_markers(model):
    """Undetected victims' marker statuses changed (the planner's needy test reads them)."""
    for vid in (V2, V3, V4):
        victim(model, vid).status = "unreachable"


def _real_run(monkeypatch, perturb, steps):
    switches(monkeypatch, joint=1, reassign=1)
    model = pinned_model(monkeypatch)
    for vid in (V0, V1):
        state = model.managed_victims[vid]
        state.confirmed = True
        state.status = "confirmed"
        victim(model, vid).status = "confirmed"
    if perturb is not None:
        perturb(model)
    detected, fire = [], []
    with redirect_stdout(io.StringIO()):
        for _ in range(steps):
            model.step()
            detected.append(tuple(sorted(wf._detected_victim_ids(model))))
            fire.append(tuple(sorted(model._active_burning_cells())))
    decisions = [(e["step"], e["phase"], e["kind"], e["victim_id"], e["unit"]) for e in events(model)]
    audit = [
        (e["action"], e["victim_id"], e["firefighter_id"], e["success"])
        for e in model._physical_rescue_command_audit
    ]
    return detected, fire, decisions, audit


def test_tinfo_b_metamorphic_over_a_short_real_run(monkeypatch):
    """T-INFO-b (pre-registered form, design 9.3). Over a short pinned real-model run with both switches on and
    victims 0 and 1 detected at the start, variants that perturb the undetected victims' fates, cells and marker
    statuses are compared with the unperturbed run. A variant is ACCEPTED only if its per-step detected-id sequence
    (asserted first) and its per-step burning set are identical (J reads the fire legitimately; a variant that
    changes detections or the fire through shared randomness is rejected). Every accepted variant must leave J's
    decisions and the assign / unassign log identical, and at least one variant must be accepted.
    MUTANT tinfo."""
    steps = 4
    base = _real_run(monkeypatch, None, steps)
    assert base[2], "J made no decision - the test would be vacuous"
    accepted = []
    for perturb in (_perturb_fates, _perturb_cells, _perturb_markers):
        variant = _real_run(monkeypatch, perturb, steps)
        if variant[0] != base[0] or variant[1] != base[1]:
            continue                                   # rejected: detections or the fire changed
        accepted.append(perturb.__name__)
        assert variant[2] == base[2], perturb.__name__
        assert variant[3] == base[3], perturb.__name__
    assert accepted, "every variant was rejected"


def test_tinfo_c_source_never_iterates_victims_nor_calls_the_snapshot():
    """T-INFO-c. joint_dispatch.py never names the victim registry; J's model functions never iterate it and never
    call get_rescue_operational_snapshot or _any_victim_needs_rescue (the exactly-2 AST test stays green). The one
    new snapshot read - the record-only would-have-been write-off counter (D-6) - is never read by J."""
    assert "victim_marker_agents" not in inspect.getsource(jd)
    assert "writeoff" not in inspect.getsource(jd)
    for name in ("_dispatch_view", "_joint_dispatch_point", "_dispatch_fill_bind", "_dispatch_replace",
                 "_dispatch_fire_sets", "_dispatch_victim_needy"):
        src = inspect.getsource(getattr(wf.WildFireModel, name))
        assert "get_rescue_operational_snapshot" not in src, name
        assert "_any_victim_needs_rescue" not in src, name
        assert "v_markers.items()" not in src and "victim_marker_agents.items()" not in src, name
        assert "v_markers.values()" not in src and "victim_marker_agents.values()" not in src, name
        assert "writeoff" not in src and "_dispatch_cf_taken" not in src, name


# ============================================================================ T-SW: the switches

ON = [1, True, 1.0, "1", " 1 "]
OFF = [0, 2, 0.5, "2.0", "1.0", "on", "", None, -1]


@pytest.mark.parametrize("value", ON)
def test_tsw_on_only_on_an_exact_one(monkeypatch, value):
    """T-SW. DISPATCH_JOINT / DISPATCH_REASSIGN are ON for what denotes the integer 1. Read at call time."""
    switches(monkeypatch, joint=value, reassign=value)
    assert agents.dispatch_joint() is True
    assert agents.dispatch_reassign() is True


@pytest.mark.parametrize("value", OFF)
def test_tsw_off_for_everything_else(monkeypatch, value):
    """T-SW. Everything else is OFF, missing included."""
    switches(monkeypatch, joint=value, reassign=1)
    assert agents.dispatch_joint() is False
    assert agents.dispatch_reassign() is False


@pytest.mark.parametrize("value", OFF)
def test_tsw_reassign_needs_its_own_exact_one_while_joint_is_on(monkeypatch, value):
    """T-SW. With DISPATCH_JOINT on, DISPATCH_REASSIGN is still ON only on an exact 1.
    MUTANT tsw_reassign: DISPATCH_REASSIGN read by truthiness (kills the truthy cases; 0, "" and None are off
    either way)."""
    switches(monkeypatch, joint=1, reassign=value)
    assert agents.dispatch_joint() is True
    assert agents.dispatch_reassign() is False


def test_tsw_missing_is_off_and_reassign_needs_joint(monkeypatch):
    """T-SW (ruling D-4). REASSIGN acts only while JOINT is on; a missing JOINT is off.
    MUTANT tsw_dep: the dependency removed."""
    monkeypatch.delattr(cfv, "DISPATCH_JOINT", raising=False)
    monkeypatch.setattr(cfv, "DISPATCH_REASSIGN", 1, raising=False)
    assert agents.dispatch_joint() is False
    assert agents.dispatch_reassign() is False
    monkeypatch.setattr(cfv, "DISPATCH_JOINT", 0, raising=False)
    assert agents.dispatch_reassign() is False


@pytest.mark.parametrize(
    "name,accessor,default",
    [
        ("DISPATCH_STALL_STEPS", agents.dispatch_stall_steps, 10),
        ("DISPATCH_MARGIN_STEPS", agents.dispatch_margin_steps, 5),
        ("DISPATCH_MARGIN_PERSIST", agents.dispatch_margin_persist, 3),
    ],
)
def test_tsw_step_parameters(monkeypatch, name, accessor, default):
    """T-SW. The step parameters: shipped values (ruling D-8); an exact positive integer, otherwise the default."""
    assert getattr(cfv, name) == default
    assert accessor() == default
    monkeypatch.setattr(cfv, name, 7, raising=False)
    assert accessor() == 7
    for junk in (0, -3, 2.5, "x", None):
        monkeypatch.setattr(cfv, name, junk, raising=False)
        assert accessor() == default


def test_tsw_shipped_defaults():
    """T-SW. Both limits ship OFF."""
    assert cfv.DISPATCH_JOINT == 0 and cfv.DISPATCH_REASSIGN == 0


def test_tsw_with_joint_off_j_is_never_entered_and_nothing_changes(monkeypatch):
    """T-SW. With DISPATCH_JOINT = 0: J's builder is never entered, nothing is printed by J, today's legacy
    pairing still runs (a victim_confirmed incident through the handler's select binds the nearest unit with
    reason "initial"), and the sink keeps no ledger, no J event and no counterfactual state.
    MUTANT tsw_gate: the gate at the top of _joint_dispatch_point removed."""
    switches(monkeypatch, joint=0, reassign=1)
    model = pinned_model(monkeypatch)
    quiet_fire(model)
    place_units(model, {FF_A: (10, 10), FF_B: (30, 30)})
    place_victims(model, {V0: (12, 10)})

    def boom(*args, **kwargs):
        raise AssertionError("J entered with DISPATCH_JOINT = 0")

    monkeypatch.setattr(model, "_dispatch_view", boom)
    out = io.StringIO()
    with redirect_stdout(out):
        model._joint_dispatch_point("pre")
        model._joint_dispatch_point("post")
    assert out.getvalue() == ""
    with redirect_stdout(io.StringIO()):
        model._handle_rescue_incident({"type": "victim_confirmed", "victim_id": V0, "reason": "initial"})
    assert bound_to(model, FF_A) == V0
    last = [e for e in model._physical_rescue_command_audit if e["action"] == "assign"][-1]
    assert (last["victim_id"], last["firefighter_id"], last["success"], last["reason"]) == (V0, FF_A, True, "initial")
    for name in ("_dispatch_ledger", "_dispatch_events", "_dispatch_pending_cause", "_dispatch_cf_taken",
                 "_dispatch_progress", "dispatch_writeoffs_avoided"):
        assert getattr(model, name, None) is None, name


# ============================================================================ T-INV: the invariants, stepped

def _check_frame(model, failures):
    """I1, I4, I5, I7 at a frame boundary. I4 as restated by round 2 (outputs/dispatch2_part1.txt 7.3): under Limit 3
    no free unit and WAITING victim (W) with a finite route; a latched-held victim is a contest, not a fill target."""
    view = model._dispatch_view()
    victims, units = view["victims"], view["units"]
    for vid, info in victims.items():
        active = [u for u in info["binders"] if str(units[u].status).lower() != "route_blocked"]
        latched = [u for u in info["binders"] if str(units[u].status).lower() == "route_blocked"]
        if len(active) > 1:
            failures.append(("I1", vid, active))
        if active and latched:
            failures.append(("I7", vid, active, latched))
    # I4 (W leg only under Limit 3): no free unit and waiting victim with a finite route (a fill is uncapped)
    burning = model._active_burning_cells()
    ledger = getattr(model, "_dispatch_ledger", {}) or {}
    for vid in list(view["waiting"]):
        dmap = jd.bfs_distances(victims[vid]["cell"], model.grid.width, model.grid.height, burning)
        for uid in view["free"]:
            if jd.route_distance(dmap, tuple(units[uid].pos), burning) is not None:
                failures.append(("I4", vid, uid))
    # I5: every REPLACE bound a never-bound pair; every LATCH-FILL a pair bound at most once before
    seen = {}
    for e in events(model):
        key = (e.get("unit"), e.get("victim_id"))
        if e["kind"] in ("fill", "second_fill", "latch_fill", "replace"):
            seen[key] = seen.get(key, 0) + 1
            if e["kind"] == "replace" and seen[key] != 1:
                failures.append(("I5", e))
            if e["kind"] == "latch_fill" and seen[key] > 2:
                failures.append(("I5", e))
    for key, count in seen.items():
        if ledger.get(key, 0) < count:
            failures.append(("ledger", key, ledger.get(key), count))


def _custody_units(model) -> dict:
    """Units in custody of their victim (design 5.2 / I6): exiting, rescue_completed or standing on its cell."""
    out = {}
    for uid, unit in model.firefighter_marker_agents.items():
        rv = getattr(unit, "rescued_victim", None)
        if getattr(unit, "dead", False) or rv is None:
            continue
        colocated = unit.pos is not None and getattr(rv, "pos", None) is not None and tuple(unit.pos) == tuple(rv.pos)
        if getattr(unit, "exiting", False) or getattr(unit, "rescue_completed", False) or colocated:
            out[uid] = rv
    return out


def _clean_cell(model, origin, lo, hi):
    """A deterministic cell at Manhattan distance lo..hi from origin, not burning, smoky or beside fire, with a
    fire-free route to origin."""
    burning = model._active_burning_cells()
    smoky = model._dispatch_fire_sets(need_smoke=True)[1]
    unclean = jd.unclean_cells(burning, smoky)
    dmap = jd.bfs_distances(tuple(origin), model.grid.width, model.grid.height, burning)
    for d in range(lo, hi + 1):
        for x in range(model.grid.width):
            for y in range(model.grid.height):
                cell = (x, y)
                if abs(x - origin[0]) + abs(y - origin[1]) != d or cell in unclean:
                    continue
                if dmap.get(cell) is not None:
                    return cell
    raise AssertionError(f"no clean cell {lo}..{hi} from {origin}")


def test_tinv_invariants_hold_at_every_frame_of_a_real_run(monkeypatch):
    """T-INV. A short pinned real run (scenario A's team) with both switches on and TWO victims detected at the start
    (three units: a spare exists). After EVERY J call: I1 (at most one active binder), I4 (full fill, latch-cap leg
    included), I5 (ledger), I7 (no latched + active pair), I6 (no carrier, finisher or co-located unit was a J
    donor or target, its binding untouched) and I3 (no J action stripped a victim of its unit). Limit 3 is made to
    act inside the real run: one binder is put in the repeated-raise state (latched) between steps - round 2 (C2):
    its route is open, so it is NOT latch-filled at once (it recovers in its own advance) and the latch leaves I7
    intact - and then a free unit with a fresh pair is parked beside a bound victim whose incumbent was moved far
    away - a margin REPLACE must follow. The REPLACE is asserted to have happened, so the invariants are not checked
    vacuously."""
    switches(monkeypatch, joint=1, reassign=1)
    model = pinned_model(monkeypatch)
    for vid in (V0, V1):
        state = model.managed_victims[vid]
        state.confirmed = True
        state.status = "confirmed"
        victim(model, vid).status = "confirmed"
    failures: list = []
    original = model._joint_dispatch_point

    def checked(phase):
        custody = _custody_units(model)
        bound_before = {vid: binders(model, vid) for vid in (V0, V1, V2, V3, V4)}
        n_before = len(events(model))
        original(phase)
        for uid, rv in custody.items():
            if model.firefighter_marker_agents[uid].rescued_victim is not rv:
                failures.append(("I6", uid))
        for e in events(model)[n_before:]:
            vid = e.get("victim_id")
            touched = {e.get("unit")} | set(e.get("old_units") or [])
            if touched & set(custody):
                failures.append(("I6", e))
            if bound_before.get(vid) and not binders(model, vid):
                failures.append(("I3", e))
        _check_frame(model, failures)

    monkeypatch.setattr(model, "_joint_dispatch_point", checked)

    def step():
        with redirect_stdout(io.StringIO()):
            model.step()

    step()
    step()
    # LATCH: a bound, contestable unit is put in the repeated-raise state (route_blocked, still bound)
    view = model._dispatch_view()
    vid_l, uid_l = sorted(view["contest"].items())[0]
    ff(model, uid_l).status = "route_blocked"
    step()
    assert not [e for e in events(model, "latch_fill") if e["victim_id"] == vid_l], events(model)
    assert uid_l in binders(model, vid_l)
    # MARGIN: the other bound victim's incumbent is moved far away; a free unit with a fresh pair is parked
    # beside the victim before each step until the margin replacement happens (P evaluations)
    moved = False
    for _ in range(6):
        if events(model, "replace"):
            break
        view = model._dispatch_view()
        ledger = model._dispatch_ledger
        pairs = [
            (vid, inc, spare)
            for vid, inc in sorted(view["contest"].items())
            for spare in view["free"]
            if int(ledger.get((spare, vid), 0) or 0) == 0
        ]
        assert pairs, ("no contest with a fresh spare", view["contest"], view["free"])
        vid_m, inc, spare = pairs[0]
        cell = tuple(view["victims"][vid_m]["cell"])
        if not moved:
            model.grid.move_agent(ff(model, inc), _clean_cell(model, cell, 16, 24))
            moved = True
        model.grid.move_agent(ff(model, spare), _clean_cell(model, cell, 1, 2))
        step()
    reps = events(model, "replace")
    assert reps and reps[0]["reason"] == "reassign_margin", events(model)
    for _ in range(3):
        step()
    assert failures == []
