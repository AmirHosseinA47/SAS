"""Dispatch round, LIMIT 3 - reassignment and the no-flip-flop guarantee (outputs/dispatch_part1.txt section 6,
13.3 T-R1..T-R9, T-FLIP-a, T-FLIP-b; T-R10 from amendment A2, 22.5(3)) - amended by dispatch round 2
(outputs/dispatch2_part1.txt 13 (3)): the history progress rule (R-1), d* (R-1), a clean approach for every
challenger (R-2), nearest-or-incumbent (C1), the latched incumbent (C2); T-R8 / T-R10 (a) / T-FLIP rewritten, T-R10 (b)
retired (step 4 offers W only under Limit 3).

Every test is mutation-checked against the named mutant in its docstring (outputs/_dp_mutants.py records them).
"""

from __future__ import annotations

import io
import random
from contextlib import redirect_stderr

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
    move,
    pinned_model,
    place_units,
    place_victims,
    quiet_fire,
    smoke,
    switches,
    unburn,
    victim,
)
from src_extension.planning import joint_dispatch as jd

S = 10  # ruling D-8
M = 5
P = 3


@pytest.fixture
def model(monkeypatch):
    switches(monkeypatch, joint=1, reassign=1)
    m = pinned_model(monkeypatch)
    quiet_fire(m)
    return m


def _revive(model, ff_id, cell):
    unit = ff(model, ff_id)
    unit.dead = False
    unit.status = "available"
    move(model, ff_id, cell)


# ============================================================================ T-R1 / T-R2: the progress rule (pure)
# Round 2 (outputs/dispatch2_part1.txt 2.8 R-1): progress = beating every cell the unit has stood on since its last
# progress, all distances on the CURRENT board. _run feeds progress_step frame by frame from per-frame distance
# tables over cells (the board as it is at that frame).

def _run(frames, frozen=False, clean=False):
    """frames[t] = (cell, {cell: distance at frame t}); frames[0] is the bind. Returns k after each later frame.
    clean=True feeds the same table as the clean distance too."""
    cell0, _ = frames[0]
    state = jd.new_progress(cell0)
    ks = []
    for cell, table in frames[1:]:
        d_hist = tuple(table.get(h) for h in state.history)
        c_hist = d_hist if clean else tuple(None for _ in state.history)
        c_now = table.get(cell) if clean else None
        state = jd.progress_step(state, True, table.get(cell), c_now, d_hist, c_hist, cell, frozen)
        ks.append(state.k)
    return ks


def _loop_frames(n, base_p, base_q, offset):
    """A unit alternating between cells P and Q (P at even frames, Q at odd); offset(t) is added to both cells'
    distances at frame t (the fire or the victim changing the route for everyone)."""
    P, Q = (0, 0), (1, 0)
    return [((P if t % 2 == 0 else Q), {P: base_p + offset(t), Q: base_q + offset(t)}) for t in range(n)]


@pytest.mark.parametrize(
    "offset",
    [
        lambda t: 0,                      # (a) a plain two-cell loop
        lambda t: 4 * (t // 3),           # (b) a front lengthening every route by 4 each fire tick
        lambda t: -4 * (t // 3),          # (c) burn-out shortening every route by 4 each tick
        lambda t: -(t // 2),              # (d) the victim drifting sideways toward the loop's row
    ],
    ids=["loop", "front", "burnout", "drift"],
)
def test_tr1_a_looping_unit_stalls_whatever_the_fire_and_the_victim_do(offset):
    """T-R1 (pure; round 2 R-1). A two-cell loop never beats the least distance over the cells it has stood on since
    its last progress, all on the current board: k grows by one per frame and reaches S at frame S+1 - with a front
    lengthening routes, with burn-out shortening them, and with a victim drifting toward the unit.
    MUTANT q_prevonly: progress judged against the previous cell only (H kept to the last cell) - a two-cell loop
    then beats its previous cell every second frame and never stalls."""
    ks = _run(_loop_frames(14, 60, 59, offset))
    assert max(ks[:S]) < S          # frames 1..S: never S (k = frame - 1 after the first move's progress)
    assert ks[S] >= S               # frame S + 1: S


def test_tr2_no_false_stall():
    """T-R2 (pure). A unit chasing a victim that flees at equal speed, a unit progressing along a fresh fire-made
    detour, and a unit whose route the fire shortens while it advances never reach k = S: every new cell is closer,
    on the current board, than every cell behind it.
    MUTANT q_by2: progress must beat the history's least distance by 2 - the chase (20 against 21) never does."""
    # chase: the unit closes one cell per frame on a victim fleeing one cell per frame: the current cell is 20 away,
    # the cell left one frame ago 21, two frames ago 22, ...
    frames = []
    for t in range(30):
        table = {(i, 0): 20 + (t - i) for i in range(t + 1)}
        frames.append(((t, 0), table))
    assert max(_run(frames)) < S
    # detour: at frame 5 the route jumps by 15 for every cell, then the unit advances one cell per frame
    frames = []
    for t in range(30):
        jump = 15 if t >= 5 else 0
        frames.append(((t, 0), {(i, 0): 20 - i + jump for i in range(t + 1)}))
    assert max(_run(frames)) < S
    # shortening: the fire opens a shortcut (route -6 at frame 8) while the unit advances
    frames = []
    for t in range(25):
        cut = -6 if t >= 8 else 0
        frames.append(((t, 0), {(i, 0): 30 - i + cut for i in range(t + 1)}))
    assert max(_run(frames)) < S


# ============================================================================ T-R1 / T-R2: the model's progress feed

def test_tr2_model_a_chase_never_stalls(model):
    """T-R2 (model). A unit closing one cell per frame on a victim that flees one cell per frame: the route stays
    20 while every cell it left is farther on the current board, so k never reaches S and the spare (a stall
    challenger - 18 + t away, never 5 closer) is never sent.
    MUTANT q_feed: the model feeds progress_step the CURRENT cell's distance for every history cell (no cell is ever
    beaten)."""
    place_units(model, {FF_A: (20, 5)})
    place_victims(model, {V0: (20, 25)})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    _revive(model, FF_B, (38, 25))
    for t in range(1, 2 * S + 2):
        move(model, FF_A, (20, 5 + t))
        model.grid.move_agent(victim(model, V0), (20, 25 + t))
        j_post(model)
    assert events(model, "replace") == []
    assert model._dispatch_progress[(FF_A, V0)].k < S


def _burnout_case(model):
    """A loops at (20, 20) / (20, 21) behind a burning wall (row 30, x 5..30; fire-free route 42 around the east
    end, clean route d* 44 - round 2 R-1 binds and records d*) that burns out one column every 3 frames from the east
    (the detour shortens by 2); B (corner: never 5 closer, a stall challenger at k = S) has a clean approach."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    burn(model, [(x, 30) for x in range(5, 31)])
    j_post(model)
    assert bound_to(model, FF_A) == V0 and events(model, "fill")[-1]["distance"] == 44
    _revive(model, FF_B, (49, 49))


def test_tr1_model_burnout_still_stalls(model):
    """T-R1 (model, burn-out). The burn-out shortens the route from both loop cells alike, so neither ever beats the
    other on the current board: k grows by one per frame and the stall replacement comes at frame S + 1, not before.
    MUTANT q_prevonly: H kept to the last cell - the loop beats its previous cell every second frame and k restarts,
    so no stall replacement comes."""
    _burnout_case(model)
    for frame in range(1, S + 2):
        if frame % 3 == 0:
            unburn(model, [(31 - frame // 3, 30)])
        move(model, FF_A, (20, 21) if frame % 2 else (20, 20))
        j_post(model)
        if frame <= S:
            assert events(model, "replace") == [], frame
    reps = events(model, "replace")
    assert len(reps) == 1 and reps[0]["reason"] == "reassign_stall" and reps[0]["unit"] == FF_B


def test_tr1_model_a_spare_with_a_clean_approach_unfreezes_the_count(model):
    """T-R1 (model, 6.3 FROZEN). The looping incumbent has NO clean approach (every cell around its loop is smoky)
    but the spare has one: k counts ("A's position is the problem") and the stall replacement comes at S + 1.
    MUTANT tfreeze: FROZEN decided by the incumbent alone (the spare leg of 6.3 dropped)."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    _revive(model, FF_B, (22, 18))
    smoke(model, [(19, 20), (21, 20), (20, 19), (19, 21), (21, 21), (20, 22)])
    for frame in range(1, S + 2):
        move(model, FF_A, (20, 21) if frame % 2 else (20, 20))
        j_post(model)
    reps = events(model, "replace")
    assert len(reps) == 1 and reps[0]["reason"] == "reassign_stall" and reps[0]["unit"] == FF_B


def test_tr4_model_a_spare_without_a_clean_approach_is_never_sent(model):
    """T-R4/6.4 (model). A stalled incumbent (it has a clean approach, so k counts) whose only spare is ringed by
    smoke - no clean approach - is not replaced, however long it stalls.
    MUTANT tclean3: the challenger's clean-approach verdict taken as True."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    _revive(model, FF_B, (22, 18))
    smoke(model, [(21, 18), (23, 18), (22, 17), (22, 19)])
    _loop_a(model, 2 * S + 2)
    assert model._dispatch_progress[(FF_A, V0)].k >= S
    assert events(model, "replace") == []
    assert bound_to(model, FF_A) == V0


def test_tr_x_an_enclosed_history_cell_does_not_freeze_the_binding(model):
    """Round 2 (R-1, 2.8; round 1's 6.3 "not evaluated" rule and its P2-3 known limitation are superseded). The
    incumbent's bind cell (20, 20) is enclosed by fire after A moved to (20, 22): a history cell with no finite
    distance is skipped (amendment A2) and the binding is still evaluated every frame, so a spare 8 closer by route
    (d* 10 against 18) replaces A by margin after P evaluations.
    MUTANT q_freeze: a binding with a history cell at no finite distance is left unevaluated (round 1's freeze)."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    move(model, FF_A, (20, 22))
    burn(model, [(19, 20), (21, 20), (20, 19), (20, 21)])
    _revive(model, FF_B, (20, 30))
    j_post(model, 2 * P)
    reps = events(model, "replace")
    assert len(reps) == 1 and reps[0]["reason"] == "reassign_margin" and reps[0]["unit"] == FF_B, events(model)
    assert bound_to(model, FF_B) == V0


# ============================================================================ T-R3 / T-R4: the rules (pure)

def _contest(delta, k, persist=None, *, route_open=True, k_closed=0, latched=False):
    return jd.Contest(victim="victim_0", incumbent="ff_unit_0", delta=delta, route_open=route_open, k=k,
                      k_closed=k_closed, persist=dict(persist or {}), latched=latched)


def test_tr3_stall_charge_boundary():
    """T-R3. A stalled incumbent (k = S, delta 20) is replaced by a fresh spare with a clean approach iff
    d*(B) < 20 + k: 29 yes, 30 no; never without a clean approach; never on a used pair (the nearest is then barred:
    a Barred record, no replacement); never before k = S.
    MUTANT tr3: the lost-time charge removed (d*(B) < delta)."""
    def detail(d_b, clean=True, ledger=None, k=S):
        return jd.plan_replacements_detail(
            [_contest(20, k)], ["ff_unit_1"], {("ff_unit_1", "victim_0"): d_b}, ledger or {},
            {("ff_unit_1", "victim_0"): clean}, stall_steps=S, margin_persist=P,
        )
    assert [r.cause for r in detail(29)[0]] == ["stall"]
    assert detail(30) == ([], [])
    assert detail(29, clean=False) == ([], [])
    reps, barred = detail(29, ledger={("ff_unit_1", "victim_0"): 1})
    assert reps == [] and [(b.victim, b.cause, b.units) for b in barred] == [("victim_0", "stall", ("ff_unit_1",))]
    assert detail(21, k=S - 1) == ([], [])


def _margin_frames(gaps, d_a=20, present=None, clean=True):
    """Evaluate the margin rule over frames; gaps[t] = delta(A) - d*(B) at frame t; present[t] False = B not a
    spare."""
    state = jd.new_progress((0, 0))
    replaced_at = None
    for t, gap in enumerate(gaps):
        is_spare = True if present is None else present[t]
        spare_d = {"ff_unit_1": d_a - gap} if is_spare else {}
        state = jd.update_persistence(state, spare_d, d_a, M)
        plan = jd.plan_replacements(
            [_contest(d_a, 0, state.persist_map())], list(spare_d), {("ff_unit_1", "victim_0"): d_a - gap},
            {}, {("ff_unit_1", "victim_0"): clean}, stall_steps=S, margin_persist=P,
        )
        if plan and replaced_at is None:
            replaced_at = t
    return replaced_at


def test_tr4_margin_needs_m_steps_for_p_evaluations():
    """T-R4. Gap 5 held for 3 evaluations replaces (at the 3rd); gap 4 never; 5, 5, 4 never; a binding younger
    than P cannot be replaced; a spare that was not free at one evaluation restarts its count; a spare without a clean
    approach never replaces (R-2 (a)).
    MUTANT tr4: P = 1. MUTANT r2_margin: the margin challenger's clean-approach test removed."""
    assert _margin_frames([5, 5, 5]) == 2
    assert _margin_frames([4, 4, 4, 4, 4, 4]) is None
    assert _margin_frames([5, 5, 4]) is None
    assert _margin_frames([5, 5]) is None
    assert _margin_frames([5, 5, 5, 5], present=[True, False, True, True]) is None
    assert _margin_frames([5, 5, 5, 5, 5], present=[True, False, True, True, True]) == 4
    assert _margin_frames([5, 5, 5, 5], clean=False) is None


# ============================================================================ T-R5..T-R9: model level

def _bind_a_then_spare_b(model, a_cell, b_cell, v_cell):
    """A bound to victim_0 by J while B is out of the pool; then B revived as a spare."""
    place_units(model, {FF_A: a_cell})
    place_victims(model, {V0: v_cell})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    _revive(model, FF_B, b_cell)


@pytest.mark.parametrize("shape", ["exiting", "rescue_completed", "colocated_latched"])
def test_tr5_a_carrier_or_finisher_is_never_touched(model, shape):
    """T-R5. A unit carrying its victim (exiting), a finisher (rescue_completed) or one standing on the victim's
    cell is never contested, even with a much closer spare for many frames. The co-located case is LATCHED
    (route_blocked while standing on its victim): a plain co-located incumbent has d = 0, which the stall and
    margin rules can never beat (the mutant is equivalent there), so co-location custody matters exactly where a
    latched unit would otherwise be latch-filled away from a pickup it is standing on.
    MUTANT tr5: the custody / finisher / co-location exclusions removed."""
    _bind_a_then_spare_b(model, (20, 5), (20, 33), (20, 35))
    unit = ff(model, FF_A)
    if shape == "exiting":
        unit.exiting = True
    elif shape == "rescue_completed":
        unit.rescue_completed = True
    else:
        move(model, FF_A, (20, 35))
        unit.status = "route_blocked"
    j_post(model, 2 * S)
    # not even an attempt: the unit is outside the contestable and latched sets, not merely refused at apply time
    assert [e for e in events(model) if e["kind"].startswith(("replace", "latch_fill"))] == []
    assert bound_to(model, FF_A) == V0 and bound_to(model, FF_B) is None


def test_tr5_an_off_grid_unit_is_never_a_challenger(model):
    """T-R5. An off-grid unit (pos None) is never a spare: a far incumbent keeps its victim.
    MUTANT tr5."""
    _bind_a_then_spare_b(model, (20, 5), (20, 33), (20, 35))
    unit = ff(model, FF_B)
    model.grid.remove_agent(unit)
    unit.off_grid = True
    unit.status = "off_grid"
    j_post(model, 2 * S)
    assert events(model, "replace") == []
    assert bound_to(model, FF_A) == V0


def test_tr6_a_margin_replacement_uses_the_release_path_cleanly(model, monkeypatch):
    """T-R6. After P evaluations with a spare 25 closer, a margin replacement: the release goes through
    _release_other_claimants(only_ff_id=A); A is unbound and "available"; firefighter_id is B; exactly one active
    binder; the invariant checker is silent; the release counter rises.
    MUTANT tr6: only_ff_id ignored (every binder released)."""
    _bind_a_then_spare_b(model, (20, 5), (20, 33), (20, 35))
    calls = []
    original = model._release_other_claimants

    def spy(*args, **kwargs):
        calls.append((args, dict(kwargs)))
        return original(*args, **kwargs)

    monkeypatch.setattr(model, "_release_other_claimants", spy)
    released_before = int(getattr(model, "ff_claims_released_total", 0) or 0)
    j_post(model, P)
    reps = events(model, "replace")
    assert len(reps) == 1 and reps[0]["reason"] == "reassign_margin"
    assert calls and calls[-1][1].get("only_ff_id") == FF_A
    assert bound_to(model, FF_B) == V0 and bound_to(model, FF_A) is None
    assert str(ff(model, FF_A).status).lower() == "available"
    assert model.managed_victims[V0].firefighter_id == FF_B
    assert binders(model, V0, active_only=True) == [FF_B]
    assert int(model.ff_claims_released_total) == released_before + 1
    from src_extension.adaptation_manager import _check_rescue_assignment_invariant

    err = io.StringIO()
    with redirect_stderr(err):
        _check_rescue_assignment_invariant(model)
    assert "RescueInvariant" not in err.getvalue()


def test_tr7_a_refused_assign_changes_nothing(model, monkeypatch):
    """T-R7. If the new unit's assign is refused, the replacement aborts and every field is as before: A still
    bound, the victim still A's, B free.
    MUTANT tr7: release-then-assign."""
    _bind_a_then_spare_b(model, (20, 5), (20, 33), (20, 35))
    original = model.apply_physical_rescue_command

    def refuse_b(cmd):
        if str(cmd.action).lower() == "assign" and str(cmd.firefighter_id) == FF_B:
            return False
        return original(cmd)

    monkeypatch.setattr(model, "apply_physical_rescue_command", refuse_b)
    j_post(model, P)
    assert [e["kind"] for e in events(model) if e["kind"].startswith("replace")] == ["replace_aborted"]
    assert bound_to(model, FF_A) == V0 and bound_to(model, FF_B) is None
    assert model.managed_victims[V0].firefighter_id == FF_A
    assert str(ff(model, FF_A).status).lower() == "en_route"


def _latched_closed_scene(model, b_ledger=None):
    """Round 2 C2 (outputs/dispatch2_part1.txt 5.2). A bound to v and latched (route_blocked, still bound) inside a
    ring of fire - its route CLOSED; v at (13, 10) on a clean cell, G(A, v) = 3; a spare B at (13, 25) with a clean
    approach, d*(B, v) = 15. The closed stall needs k_L >= S and 15 < 3 + k_L, i.e. k_L = 13: the LATCH-FILL comes at
    the 14th J-post (the first one creates the binding's state)."""
    place_units(model, {FF_A: (10, 10), FF_B: (13, 25)})
    place_victims(model, {V0: (13, 10)})
    assert assign(model, V0, FF_A)
    ff(model, FF_A).status = "route_blocked"
    burn(model, [(11, 10), (9, 10), (10, 11), (10, 9)])
    if b_ledger is not None:
        model._dispatch_ledger[(FF_B, V0)] = b_ledger


def test_tr8_latched_incumbent_is_replaced_by_a_latch_fill_only_after_the_charge(model):
    """T-R8 (round 2 C2). A latched binder whose route is closed is an incumbent credited with its grid distance
    G = 3: no LATCH-FILL while k_L < 13 (the far spare, d* 15, is never 5 closer than 3, and the stall charge needs
    15 < 3 + k_L); at the 14th J-post a stall LATCH-FILL (joint_replace_latched, stage 3) leaves ONE binder (B); the
    released unit is an unassigned route_blocked unit that the revalidation clears once a route opens.
    MUTANT c2_immediate: latched-held victims re-enter the step-2 fill under the cap (round 1's immediate LATCH-FILL).
    MUTANT c2_inf: a closed incumbent's delta read as infinite (round 1's worthless latched unit) - a margin
    LATCH-FILL at the 3rd evaluation. MUTANT tr8: the latched binder is not released by the latch-fill."""
    _latched_closed_scene(model)
    for frame in range(1, 14):
        j_post(model)
        assert events(model, "latch_fill") == [], frame
    j_post(model)
    fills = events(model, "latch_fill")
    assert len(fills) == 1 and fills[0]["reason"] == "joint_replace_latched" and fills[0]["stage"] == 3, fills
    assert fills[0]["unit"] == FF_B and fills[0]["old_units"] == [FF_A]
    assert binders(model, V0) == [FF_B]
    assert bound_to(model, FF_A) is None and str(ff(model, FF_A).status).lower() == "route_blocked"
    unburn(model, [(11, 10), (9, 10), (10, 11), (10, 9)])
    model._revalidate_route_blocked_firefighters()
    assert str(ff(model, FF_A).status).lower() == "available"


def test_tr8_no_allowed_unit_keeps_the_latched_binder(model):
    """T-R8 (C1 + C2). When the charge is met but the only qualifying spare's pair is already bound twice
    (b(B, v) = 2, beyond the LATCH-FILL cap), the latched binder is kept and the frame records a nearest-barred
    decision. MUTANT tr8capm: the LATCH-FILL cap removed (b <= 1 read as any b)."""
    _latched_closed_scene(model, b_ledger=2)
    j_post(model, 14)
    assert events(model, "latch_fill") == []
    barred = events(model, "nearest_barred")
    assert barred and barred[0]["barred"] == [FF_B] and barred[0]["reason"] == "nearest_barred_stall", barred
    assert binders(model, V0) == [FF_A]


def test_tr8_a_latched_unit_whose_route_is_open_is_judged_like_an_active_incumbent(model):
    """T-R8 (C2, label lag). A unit labelled route_blocked whose route is in fact open (quiet fire) is judged on d*
    and its open-route count k: standing still for S frames it stalls like any incumbent and only then is replaced
    (a stall LATCH-FILL at frame S + 1); round 1 latch-filled it at the first J-post.
    MUTANT c2_immediate."""
    place_units(model, {FF_A: (10, 10), FF_B: (16, 10)})
    place_victims(model, {V0: (12, 10)})
    assert assign(model, V0, FF_A)
    ff(model, FF_A).status = "route_blocked"
    for frame in range(1, S + 1):
        j_post(model)
        assert events(model, "latch_fill") == [], frame
    j_post(model)
    fills = events(model, "latch_fill")
    assert len(fills) == 1 and fills[0]["reason"] == "joint_replace_latched" and fills[0]["stage"] == 3, fills


def _loop_a(model, frames, cells=((20, 20), (20, 21))):
    for frame in range(frames):
        move(model, FF_A, cells[(frame + 1) % 2])
        j_post(model)


@pytest.mark.parametrize("shape", ["ring", "band"])
def test_tr9_no_clean_approach_freezes_the_stall(model, shape):
    """T-R9. (a) The victim's cell is clean but all four neighbours are smoky; (b) an unclean band (Manhattan 2-4)
    surrounds the victim. No unit could pick it up, so the looping incumbent's k does not advance and nothing is
    replaced; the spare's ledger is untouched.
    MUTANT tr9: the clean-approach test removed (every unit treated as having a clean approach)."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    _revive(model, FF_B, (22, 18))  # 24 from the victim: a stall challenger, never a margin one
    vx, vy = 20, 40
    if shape == "ring":
        cells = [(vx + 1, vy), (vx - 1, vy), (vx, vy + 1), (vx, vy - 1)]
    else:
        cells = [
            (vx + dx, vy + dy) for dx in range(-4, 5) for dy in range(-4, 5)
            if 2 <= abs(dx) + abs(dy) <= 4 and 0 <= vx + dx < 50 and 0 <= vy + dy < 50
        ]
    smoke(model, cells)
    _loop_a(model, 2 * S + 2)
    assert events(model, "replace") == []
    assert model._dispatch_progress[(FF_A, V0)].k < S
    assert (FF_B, V0) not in model._dispatch_ledger


def test_tr9_a_stall_with_no_spare_releases_nothing(model):
    """T-R9. A stalled incumbent with no spare keeps its victim. MUTANT tr9 (control)."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    _loop_a(model, 2 * S + 2)
    assert model._dispatch_progress[(FF_A, V0)].k >= S
    assert events(model, "replace") == []
    assert bound_to(model, FF_A) == V0


# ============================================================================ T-R10: the second fill (A2)

def _i4_violations(model):
    """I4 as restated by round 2 (outputs/dispatch2_part1.txt 7.3, C2): under Limit 3 no free unit with a finite route
    to a WAITING victim (W) at the end of a J call; a latched-held victim is a contest, not a fill target."""
    view = model._dispatch_view()
    burning = model._active_burning_cells()
    out = []
    for vid in list(view["waiting"]):
        dmap = jd.bfs_distances(view["victims"][vid]["cell"], model.grid.width, model.grid.height, burning)
        for uid in view["free"]:
            if jd.route_distance(dmap, tuple(view["units"][uid].pos), burning) is not None:
                out.append((vid, uid))
    return out


def _tr10_scene(model, b_a_w):
    """The scene the A2 proof review ran on the real model (22.5(3)): A bound to v = victim_0 (route 30); a fresh
    spare B 2 from v; X bound to w = victim_1 and latched (route_blocked, still bound); b(B, w) = 2; d(A, w) = 25
    and b(A, w) = b_a_w. Returns the ledger."""
    place_units(model, {FF_A: (20, 5), FF_B: (20, 33), FF_C: (40, 20)})
    place_victims(model, {V0: (20, 35), V1: (40, 10)})
    assert assign(model, V0, FF_A) and assign(model, V1, FF_C)
    ff(model, FF_C).status = "route_blocked"
    ledger = model._dispatch_ledger
    ledger[(FF_B, V1)] = 2
    ledger[(FF_A, V1)] = b_a_w
    view = model._dispatch_view()
    assert view["contest"] == {V0: FF_A} and view["latched"] == [V1] and view["free"] == [FF_B]
    assert view["latched_binder"] == {V1: FF_C}
    return ledger


def test_tr10_a_the_second_fill_offers_only_w_under_limit3(model):
    """T-R10 (a), round 2 C2 (5.2, 7.1 step 4; A2's W_L leg of step 4 superseded). With b(A, w) = 1: at the 3rd J-post
    B REPLACEs A on v (reassign_margin, stage 3); the released unit A is NOT offered the latched-held victim w - w is a
    contest of its own (its latched binder X, whose route is open, is judged like any incumbent) - so A stays free,
    X keeps w, b(A, w) stays 1, and I4 (W only) holds.
    MUTANT c2_step4: step 4 offers W_L under the LATCH-FILL cap again (A2's step 4) - A latch-fills w at stage 4."""
    ledger = _tr10_scene(model, 1)
    j_post(model, P - 1)
    assert [e for e in events(model) if e["kind"] in ("replace", "latch_fill")] == []
    n_before = len(events(model))
    j_post(model)
    frame = events(model)[n_before:]
    assert [(e["kind"], e["stage"], e["unit"], e["victim_id"]) for e in frame] == [("replace", 3, FF_B, V0)], frame
    assert frame[0]["reason"] == "reassign_margin" and frame[0]["old_units"] == [FF_A]
    assert binders(model, V1) == [FF_C] and binders(model, V0) == [FF_B]
    assert bound_to(model, FF_A) is None and str(ff(model, FF_A).status).lower() == "available"
    assert ledger[(FF_A, V1)] == 1
    assert _i4_violations(model) == []


def test_tr10_c_the_w_leg_binds_a_released_unit_across_an_artificial_bridge(model):
    """T-R10 (c). The second fill's W leg, on an artificial bridge (22.1 WHICH LEG IS LIVE: in normal play no unit
    stands on a burning cell at J-post): a burning wall (row 20, every column) cuts w = victim_1 off from B's side;
    A stands ON the wall - exempt as a route source - with a route to both sides. w is unbound and waiting; B has no
    route to it, so step 2 binds nothing. At the 3rd J-post B REPLACEs A on v and A is bound to w by a second fill
    (stage 4) in the same J-post - although b(A, w) = 2: a W victim's bind is uncapped at step 4 as at step 2.
    MUTANT tr10c: step 4 offers nothing. MUTANT tr10wcap: step 4 caps W."""
    place_units(model, {FF_A: (20, 20), FF_B: (20, 33)})
    place_victims(model, {V0: (20, 35), V1: (40, 10)})
    burn(model, [(x, 20) for x in range(50)])
    assert assign(model, V0, FF_A)
    model._dispatch_ledger[(FF_A, V1)] = 2
    view = model._dispatch_view()
    assert view["contest"] == {V0: FF_A} and view["waiting"] == [V1] and view["free"] == [FF_B]
    j_post(model, P - 1)
    assert [e for e in events(model) if e["kind"] in ("replace", "second_fill", "fill")] == []
    n_before = len(events(model))
    j_post(model)
    frame = events(model)[n_before:]
    assert [(e["kind"], e["stage"], e["unit"], e["victim_id"]) for e in frame] == [
        ("replace", 3, FF_B, V0), ("second_fill", 4, FF_A, V1)
    ], frame
    assert frame[1]["distance"] == 30
    assert bound_to(model, FF_A) == V1 and bound_to(model, FF_B) == V0
    assert _i4_violations(model) == []


def test_tr10_d_a_victim_bound_in_step_2_is_not_offered_again_at_step_4(model):
    """T-R10 (d), 22.5(3)'s pool definition: step 4 offers only the victims NOT bound in step 2. In the J-post of the
    margin REPLACE (B takes v from A), a newly detected W victim u is FILLed in step 2 by a third unit C beside it;
    the released unit A has a finite route to u, but u is bound, so step 4 offers A nothing: no refused or aborted
    event, u keeps its one binder C, A is free. Stages: the fill 2, the replace 3.
    MUTANT tr10bound: step 4 offers every W victim, bound in step 2 or not."""
    place_units(model, {FF_A: (20, 5), FF_B: (20, 33), FF_C: (45, 8)})
    place_victims(model, {V0: (20, 35), V2: (40, 8)}, detected={V0})
    assert assign(model, V0, FF_A)
    j_post(model, P - 1)
    assert events(model) == []
    state = model.managed_victims[V2]
    state.confirmed = True
    state.status = "confirmed"
    victim(model, V2).status = "confirmed"
    n_before = len(events(model))
    j_post(model)
    frame = events(model)[n_before:]
    assert [(e["kind"], e["stage"], e["unit"], e["victim_id"]) for e in frame] == [
        ("fill", 2, FF_C, V2), ("replace", 3, FF_B, V0)
    ], frame
    assert binders(model, V2) == [FF_C] and bound_to(model, FF_A) is None
    assert _i4_violations(model) == []


def test_stage_field_on_j_pre_refused_and_latch_fill_events(model, monkeypatch):
    """The stage field (22.5(3)) on the events the M4 split and the "which leg is live" record read: a J-pre FILL and
    a refused one carry stage 2 (phase pre), an aborted REPLACE stage 3. (Round 2: a LATCH-FILL is a step-3 decision;
    T-R8 asserts its stage 3, so round 1's step-2 LATCH-FILL leg is retired.)
    MUTANT tstage: step-2 binds tagged stage 4. MUTANT tstage_rec: the stage dropped from refused / aborted records."""
    place_units(model, {FF_A: (10, 10)})
    place_victims(model, {V0: (12, 10)})
    original = model.apply_physical_rescue_command
    monkeypatch.setattr(model, "apply_physical_rescue_command", lambda cmd: False)
    model._joint_dispatch_point("pre")
    monkeypatch.setattr(model, "apply_physical_rescue_command", original)
    model._joint_dispatch_point("pre")
    assert [(e["kind"], e["phase"], e.get("stage")) for e in events(model)] == [
        ("fill_refused", "pre", 2), ("fill", "pre", 2)
    ], events(model)
    # an aborted REPLACE (T-R7's scene)
    model2_events = len(events(model))
    place_units(model, {FF_A: (20, 5)})
    place_victims(model, {V2: (20, 35)})
    j_post(model)
    _revive(model, FF_B, (20, 33))

    def refuse_b(cmd):
        if str(cmd.action).lower() == "assign" and str(cmd.firefighter_id) == FF_B:
            return False
        return original(cmd)

    monkeypatch.setattr(model, "apply_physical_rescue_command", refuse_b)
    j_post(model, P)
    aborted = [e for e in events(model)[model2_events:] if e["kind"] == "replace_aborted"]
    assert aborted and all(e.get("stage") == 3 for e in aborted), events(model)[model2_events:]


# ============================================================================ T-FLIP-a: the theorem, simulated

def _simulate(seed: int, steps: int = 400, n_units: int = 3, n_victims: int = 3):
    """A state simulator in the CORRECTED J order (outputs/dispatch2_part1.txt 7.1, round 2). Each frame:
      J-pre   FILL over free units x WAITING victims (W only: under Limit 3 a latched-held victim is a contest);
      advance OUTSIDE events on bound units - a closed route or a random raise: the pair's first raise unbinds it
              (the unit is then route_blocked), a repeated raise latches it (bound, flagged); deaths - and the
              routes change: every pair by an exogenous part (fire / victim motion) and the unit's own step;
      post    blocked units recover (revalidation), latched units may recover onto their victim, victims turn
              terminal (their latched units are released);
      J-post  PROGRESS on every contest - an active single binder and a latched single binder - by the history rule
              on abstract cells (a cell's distance moves with the exogenous part only; the unit's own step takes it
              to a new cell); FROZEN from a random clean-approach predicate over the incumbent and the free units;
              FILL (W); persistence on the spares left; REPLACE / LATCH-FILL by plan_replacements_detail (delta = the
              route if open, else a grid-distance stand-in below it); SECOND FILL (units released by a REPLACE x W).
    Returns every bind (with b before and the J step that made it: 2, 3 or 4), the per-victim histories (with how
    each binding ended: "outside" for o1-o3, "J" for a REPLACE, "terminal"), the per-unit bind sequences, the units
    and the number of nearest-barred decisions. Every set is iterated sorted, so a seed fixes the run whatever
    PYTHONHASHSEED is."""
    rng = random.Random(seed)
    units = [f"ff_unit_{i}" for i in range(n_units)]
    victims = [f"victim_{i}" for i in range(n_victims)]
    dist = {(u, v): rng.randint(3, 40) for u in units for v in victims}
    closed: set[tuple[str, str]] = set()
    dead, blocked, terminal = set(), set(), set()
    active: dict[str, str] = {}             # victim -> active binder
    latched: dict[str, set[str]] = {v: set() for v in victims}
    raised: set[tuple[str, str]] = set()
    ledger: dict[tuple[str, str], int] = {}
    progress: dict[tuple[str, str], jd.Progress] = {}
    cells: dict[tuple[str, str], dict[tuple[int, int], int]] = {}   # bound pair -> {abstract cell: distance}
    here: dict[tuple[str, str], tuple[int, int]] = {}
    history: dict[str, list[dict]] = {v: [] for v in victims}
    unit_hist: dict[str, list[tuple[str, int, str]]] = {u: [] for u in units}
    binds: list[dict] = []
    seq = [0]
    barred_n = [0]

    def route(u, v):
        return None if (u, v) in closed else dist[(u, v)]

    def new_cell(key):
        seq[0] += 1
        cell = (seq[0], 0)
        cells.setdefault(key, {})[cell] = dist[key]
        here[key] = cell
        return cell

    def end(v, u, cause):
        for entry in reversed(history[v]):
            if entry["unit"] == u and entry["end"] is None:
                entry["end"] = cause
                return

    def bind(v, u, kind, cause=None, stage=2):
        before = ledger.get((u, v), 0)
        ledger[(u, v)] = before + 1
        active[v] = u
        cells.pop((u, v), None)
        progress[(u, v)] = jd.new_progress(new_cell((u, v)))
        seq[0] += 1
        history[v].append({"unit": u, "kind": kind, "end": None, "seq": seq[0]})
        unit_hist[u].append((v, seq[0], kind))
        binds.append({"victim": v, "unit": u, "kind": kind, "b_before": before, "cause": cause, "stage": stage})

    def free_units():
        bound = set(active.values()) | {x for s in latched.values() for x in s}
        return [u for u in units if u not in dead and u not in blocked and u not in bound]

    def fill(pool_units, kind="fill", stage=2):
        waiting = [v for v in victims if v not in terminal and v not in active and not latched[v]]
        if not pool_units or not waiting:
            return []
        pairs = jd.solve_fill(
            pool_units, waiting, {(u, v): route(u, v) for u in pool_units for v in waiting}, ledger,
            clean={(u, v): route(u, v) is not None and rng.random() < 0.8 for u in pool_units for v in waiting},
        )
        used = []
        for pair in pairs:
            bind(pair.victim, pair.unit, kind, stage=stage)
            used.append(pair.unit)
        return used

    for _ in range(steps):
        fill(free_units())                                   # J-pre
        for key in sorted(dist):                             # advance: routes change
            if rng.random() < 0.02:
                closed.add(key)
            elif key in closed and rng.random() < 0.2:
                closed.discard(key)
            e = rng.choice((-2, -1, 1, 2)) if rng.random() < 0.4 else 0
            if not 1 <= dist[key] + e <= 60:
                e = -e
            own = rng.choice((-1, 0, 1))
            if not 1 <= dist[key] + e + own <= 60:
                own = 0
            dist[key] += e + own
            if key in cells:
                for c in cells[key]:
                    cells[key][c] = max(1, cells[key][c] + e)   # every cell moves with the exogenous part only
                if own:
                    new_cell(key)                            # the unit's own step: a new cell
                else:
                    cells[key][here[key]] = dist[key]
        for v, u in list(active.items()):                    # advance: outside events
            r = rng.random()
            if (u, v) in closed or r < 0.03:
                del active[v]
                end(v, u, "outside")
                if (u, v) in raised:
                    latched[v].add(u)                        # o2: repeated raise - bound, flagged
                else:
                    raised.add((u, v))                       # o1: first raise - unbound, route_blocked
                    blocked.add(u)
                    progress.pop((u, v), None)
            elif r < 0.035:
                del active[v]
                dead.add(u)                                  # o3: death
                end(v, u, "outside")
                progress.pop((u, v), None)
        for v in victims:                                    # post-move cycle
            for u in sorted(latched[v]):
                if rng.random() < 0.005:
                    latched[v].discard(u)
                    dead.add(u)
                    progress.pop((u, v), None)
            if v not in terminal and rng.random() < 0.004:
                terminal.add(v)
                if v in active:
                    end(v, active.pop(v), "terminal")
                for u in latched[v]:
                    progress.pop((u, v), None)
                latched[v].clear()
        for u in sorted(blocked):
            if rng.random() < 0.2:
                blocked.discard(u)
        for v in victims:
            for u in sorted(latched[v]):
                if (u, v) not in closed and rng.random() < 0.3 and v not in active and v not in terminal:
                    latched[v].discard(u)
                    active[v] = u                            # its own move found a path: active again
                    seq[0] += 1
                    history[v].append({"unit": u, "kind": "recover", "end": None, "seq": seq[0]})
                    unit_hist[u].append((v, seq[0], "recover"))
        # J-post
        contest = {v: (u, False) for v, u in active.items()}
        for v in victims:
            if len(latched[v]) == 1 and v not in active and v not in terminal:
                contest[v] = (next(iter(latched[v])), True)
        free_start = free_units()
        clean = {(u, v): rng.random() < 0.8 for u in units for v in victims}
        delta: dict[str, int] = {}
        for v, (u, is_latched) in sorted(contest.items()):
            key = (u, v)
            is_open = route(u, v) is not None
            delta[v] = dist[key] if is_open else max(1, dist[key] // 3)
            state = progress.get(key)
            if state is None:
                progress[key] = jd.new_progress(new_cell(key))
                continue
            table = cells.get(key, {})
            d_hist = tuple(table.get(h) for h in state.history)
            frozen = not ((is_open and clean[key]) or any(clean[(f, v)] and route(f, v) is not None
                                                             for f in free_start))
            progress[key] = jd.progress_step(state, is_open, route(u, v), None, d_hist,
                                             tuple(None for _ in state.history), here[key], frozen)
        used = fill(free_start)
        spares = [u for u in free_start if u not in used]
        contests = []
        for v, (u, is_latched) in sorted(contest.items()):
            if (active.get(v) != u) and not (is_latched and u in latched[v]):
                continue
            spare_d = {b: route(b, v) for b in spares}
            state = jd.update_persistence(progress[(u, v)], spare_d, delta[v], M)
            progress[(u, v)] = state
            contests.append(jd.Contest(victim=v, incumbent=u, delta=delta[v], route_open=route(u, v) is not None,
                                       k=state.k, k_closed=state.k_closed, persist=state.persist_map(),
                                       latched=is_latched))
        released = []
        if spares and contests:
            matrix = {(b, v): route(b, v) for b in spares for v in victims}
            clean3 = {(b, v): clean[(b, v)] and route(b, v) is not None for b in spares for v in victims}
            plan, barred = jd.plan_replacements_detail(contests, spares, matrix, ledger, clean3,
                                                       stall_steps=S, margin_persist=P)
            barred_n[0] += len(barred)
            for rep in plan:
                progress.pop((rep.old_unit, rep.victim), None)
                if rep.latched:
                    latched[rep.victim].discard(rep.old_unit)
                    blocked.add(rep.old_unit)            # released: an unassigned route_blocked unit
                    bind(rep.victim, rep.new_unit, "latch_fill", rep.cause, stage=3)
                else:
                    end(rep.victim, rep.old_unit, "J")
                    bind(rep.victim, rep.new_unit, "replace", rep.cause, stage=3)
                    released.append(rep.old_unit)
        if released:
            fill([u for u in released if u in free_units()], kind="second_fill", stage=4)
    return binds, history, unit_hist, units, barred_n[0]


@pytest.mark.parametrize("seed", range(500))
def test_tflip_a_no_reversal_by_a_cost_decision(seed):
    """T-FLIP-a. Over random distances, route closures and outside events, in the corrected J order: no REPLACE binds
    a pair with b >= 1; no LATCH-FILL brings in a pair with b >= 2; every RETURN - A..X..A on a victim and v..w..v on
    a unit - follows an OUTSIDE event (the binding just before the return on that victim ended by o1-o3, never by
    J) and is never a REPLACE; REPLACEs per victim <= N_ff - 1; binds per victim <= 5 N_ff.
    MUTANT tflip: the b = 0 rule for REPLACE removed."""
    binds, history, unit_hist, units, _ = _simulate(seed)
    n_ff = len(units)
    for b in binds:
        if b["kind"] == "replace":
            assert b["b_before"] == 0, b
        if b["kind"] == "latch_fill":
            assert b["b_before"] <= 1, b
    by_seq = {}
    for v, entries in history.items():
        assert sum(1 for e in entries if e["kind"] == "replace") <= n_ff - 1
        assert sum(1 for e in entries if e["kind"] != "recover") <= 5 * n_ff
        for j, entry in enumerate(entries):
            by_seq[entry["seq"]] = (v, j)
        for j in range(1, len(entries)):
            unit = entries[j]["unit"]
            earlier = [e["unit"] for e in entries[:j - 1]]
            if unit in earlier and entries[j - 1]["unit"] != unit and entries[j]["kind"] != "recover":
                assert entries[j]["kind"] != "replace", (v, entries)
                assert entries[j - 1]["end"] == "outside", (v, j, entries)
    for u, seqs in unit_hist.items():                        # the unit side: v..w..v
        real = [(v, s, k) for v, s, k in seqs if k != "recover"]
        for i in range(1, len(real)):
            v, s, kind = real[i]
            if v in [x for x, _, _ in real[:i - 1]] and real[i - 1][0] != v:
                vv, j = by_seq[s]
                assert kind != "replace", (u, real)
                assert j > 0 and history[vv][j - 1]["end"] == "outside", (u, v, history[vv])


def test_tflip_a_simulator_is_not_vacuous():
    """The simulator reaches every rule the theorem speaks about in the corrected order: REPLACEs (stall and
    margin), LATCH-FILLs (step 3), second fills, nearest-barred decisions (C1), returns on victims and on units. A
    guard on T-FLIP-a itself, not a separate property. (Round 1's "LATCH-FILL made by the second fill" is retired: under
    Limit 3 step 4 serves W only, C2.)
    MUTANT tflip_vac: plan_replacements_detail returns nothing."""
    kinds: dict[str, int] = {}
    returns = 0
    barred = 0
    for seed in range(100):
        binds, history, unit_hist, _, n_barred = _simulate(seed)
        barred += n_barred
        for b in binds:
            kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
            if b["kind"] in ("replace", "latch_fill"):
                kinds[b["kind"] + "_" + str(b["cause"])] = kinds.get(b["kind"] + "_" + str(b["cause"]), 0) + 1
                assert b["stage"] == 3, b
        for seqs in unit_hist.values():
            real = [v for v, _, k in seqs if k != "recover"]
            returns += sum(1 for i in range(2, len(real)) if real[i] in real[: i - 1] and real[i - 1] != real[i])
    assert kinds.get("replace", 0) > 20 and kinds.get("second_fill", 0) > 0, kinds
    assert kinds.get("latch_fill", 0) > 5, kinds
    assert kinds.get("replace_stall", 0) > 5 and kinds.get("replace_margin", 0) > 5, kinds
    assert barred > 0 and returns > 20, (barred, returns)


# ============================================================================ T-FLIP-b: scripted, model level

def test_tflip_b_alternating_advantage_replaces_at_most_once(model):
    """T-FLIP-b. A and B alternate being 20 steps closer to the victim, 10 consecutive frames each, for 200
    frames: exactly one replacement - the ledger forbids every replacement back, and C1 then keeps the incumbent
    (nearest-barred frames) rather than send anyone else. Then the holder is forced to raise route_blocked (an
    outside event): the other returns by a FILL. Then that one raises too and both recover: with a fresh unit C
    available but FARTHER than both, the NEARER re-used unit is bound (C1: history never ranks a fill; round 1 bound
    C here).
    MUTANT tflip: the b = 0 rule for REPLACE removed (the mutant shows >= 2 replacements in the first phase).
    MUTANT c1_l2: round 1's L2 (fewest re-used pairs) restored ahead of the route keys - C is bound."""
    near, far = (25, 30), (25, 10)       # 5 and 25 from the victim
    place_units(model, {FF_A: near})
    place_victims(model, {V0: (25, 35)})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    _revive(model, FF_B, far)
    for frame in range(200):
        a_far = (frame // 10) % 2 == 0
        move(model, FF_A, far if a_far else near)
        move(model, FF_B, near if a_far else far)
        j_post(model)
    reps = events(model, "replace")
    assert len(reps) == 1, [(e["step"], e["unit"]) for e in reps]
    assert events(model, "nearest_barred"), "C1: the barred nearer spare is recorded, the incumbent kept"
    holder = bound_to(model, FF_A) and FF_A or FF_B
    other = FF_B if holder == FF_A else FF_A
    unit = ff(model, holder)
    unit.status = "route_blocked"
    model._on_firefighter_route_blocked(unit)
    assert binders(model, V0) == []
    j_post(model)
    assert bound_to(model, other) == V0
    assert events(model)[-1]["kind"] == "fill"
    # the other raises too; both recover; a fresh unit C, farther than both, is available
    unit2 = ff(model, other)
    unit2.status = "route_blocked"
    model._on_firefighter_route_blocked(unit2)
    model._revalidate_route_blocked_firefighters()
    assert set(model._dispatch_view()["free"]) == {FF_A, FF_B}
    _revive(model, FF_C, (5, 49))        # route 34: farther than A and B
    nearer = FF_A if tuple(ff(model, FF_A).pos) == near else FF_B
    j_post(model)
    assert binders(model, V0) == [nearer] and bound_to(model, FF_C) is None
    assert model._dispatch_ledger[(nearer, V0)] >= 2
