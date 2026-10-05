"""Dispatch round, LIMIT 3 - reassignment and the no-flip-flop guarantee (outputs/dispatch_part1.txt section 6,
13.3 T-R1..T-R9, T-FLIP-a, T-FLIP-b).

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

def _run(d_seq, x_seq, frozen=False):
    """Drive progress_step from a bind at d_seq[0]; d_seq[t] = distance from the current cell at frame t,
    x_seq[t] = distance from the previous frame's cell, on the same frame's fire and victim cell."""
    state = jd.new_progress(d_seq[0], (0, 0))
    ks = []
    for t in range(1, len(d_seq)):
        state = jd.progress_step(state, d_seq[t], x_seq[t], (t, 0), frozen)
        ks.append(state.k)
    return ks


def _loop_tables(n, base_p, base_q, offset):
    """A unit alternating between cells P and Q (P at even frames, Q at odd); offset(t) is added to both cells'
    distances at frame t (the fire or the victim changing the route for everyone)."""
    dist_p = [base_p + offset(t) for t in range(n)]
    dist_q = [base_q + offset(t) for t in range(n)]
    cur = [dist_p[t] if t % 2 == 0 else dist_q[t] for t in range(n)]
    prev = [None] + [dist_q[t] if t % 2 == 0 else dist_p[t] for t in range(1, n)]
    return cur, prev


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
    """T-R1 (pure). A two-cell loop never beats `best` once the exogenous change is factored out: k grows by one
    per frame and reaches S at frame S+1 - with a front lengthening routes, with burn-out shortening them, and with
    a victim drifting toward the unit.
    MUTANT tr1 (burnout, drift): progress_step without the exogenous shift e_t - on these inputs the change
    shortens the route, which the mutant reads as progress.
    MUTANT tr1cmp (loop, front): progress judged against the previous distance (d < d_prev, the model's rejected
    "approaching" flag, 6.3) - the named mutant tr1 is EQUIVALENT on these two inputs (e = 0, or e > 0, which can
    only add to k), so no test of them can fail on it (Part 2 notes)."""
    cur, prev = _loop_tables(14, 60, 59, offset)
    ks = _run(cur, prev)
    assert max(ks[:S]) < S          # frames 1..S: never S (k = frame - 1 after the first move's progress)
    assert ks[S] >= S               # frame S + 1: S


def test_tr1_model_level_stall_replacement_at_exactly_s(model):
    """T-R1 (model). A bound unit looping between two cells (route 20 / 19) with a spare 24 away that has a clean
    approach: no replacement before k reaches S, a stall replacement (reassign_stall) at the frame it does.
    MUTANT tr1m: the stall rule disabled (tr1 is equivalent here: no fire, a still victim, e = 0)."""
    place_units(model, {FF_A: (20, 20), FF_B: (22, 18)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    assert bound_to(model, FF_A) == V0  # 20 < 24
    for frame in range(1, S + 1):
        move(model, FF_A, (20, 21) if frame % 2 else (20, 20))
        j_post(model)
        assert events(model, "replace") == [], frame
    move(model, FF_A, (20, 21))
    j_post(model)
    reps = events(model, "replace")
    assert len(reps) == 1 and reps[0]["reason"] == "reassign_stall" and reps[0]["unit"] == FF_B
    assert bound_to(model, FF_B) == V0 and bound_to(model, FF_A) is None


def test_tr2_no_false_stall():
    """T-R2 (pure). A unit chasing a victim that flees at equal speed, a unit progressing along a fresh fire-made
    detour, and a unit whose route the fire shortens while it advances never reach k = S.
    MUTANT tr1 (no exogenous shift): the chase reaches S."""
    # chase: the victim moves one cell away each frame; the unit closes one: distance stays 20
    cur = [20] * 30
    prev = [None] + [21] * 29
    assert max(_run(cur, prev)) < S
    # detour: at frame 5 the route jumps by 15 for every cell, then the unit advances one cell per frame
    cur, prev = [20], [None]
    for t in range(1, 30):
        jump = 15 if t >= 5 else 0
        cur.append(20 - t + jump)
        prev.append(20 - (t - 1) + jump)
    assert max(_run(cur, prev)) < S
    # shortening: the fire opens a shortcut (route -6 at frame 8) while the unit advances
    cur, prev = [30], [None]
    for t in range(1, 25):
        cut = -6 if t >= 8 else 0
        cur.append(30 - t + cut)
        prev.append(30 - (t - 1) + cut)
    assert max(_run(cur, prev)) < S


# ============================================================================ T-R1 / T-R2: the model's progress feed

def test_tr2_model_a_chase_never_stalls(model):
    """T-R2 (model). A unit closing one cell per frame on a victim that flees one cell per frame: the route stays
    20, the victim's flight is the exogenous change (x - d_prev = +1 each frame), so k never reaches S and the spare
    (a stall challenger - 18 + t away, never 5 closer) is never sent.
    MUTANT tr1x: the model feeds progress_step x := d_prev (the exogenous shift dropped at the call)."""
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
    """A loops at (20, 20) / (20, 21) behind a burning wall (row 30, x 5..30; route 42 around the east end) that
    burns out one column every 3 frames from the east (the detour shortens by 2); B (corner, route 38: never 5
    closer, a stall challenger at k = S) has a clean approach."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    burn(model, [(x, 30) for x in range(5, 31)])
    j_post(model)
    assert bound_to(model, FF_A) == V0 and events(model, "fill")[-1]["distance"] == 42
    _revive(model, FF_B, (49, 49))


def test_tr1_model_burnout_still_stalls(model):
    """T-R1 (model, burn-out). The burn-out shortening is factored out (e = -2 at each burn-out frame): k grows by
    one per frame and the stall replacement comes at frame S + 1, not before.
    MUTANT tr1x: the model feeds progress_step x := d_prev - every burn-out frame then reads as progress and k
    restarts, so no stall replacement comes."""
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


def test_tr_x_infinite_binding_is_not_evaluated(model):
    """6.3. When x is infinite (the incumbent's previous evaluated cell is enclosed on this fire) while d is finite,
    the state is frozen and the binding is NOT evaluated this frame: no persistence count, no replacement - even
    with a spare 8 closer by route for many frames. (Literal 6.3: the state, cell_prev included, is left unchanged,
    so the binding stays unevaluated while that cell stays enclosed - Part 2 notes, known limitation.)
    MUTANT txnone: the not-evaluated rule removed (the binding evaluated with its state unchanged)."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    move(model, FF_A, (20, 22))
    burn(model, [(19, 20), (21, 20), (20, 19), (20, 21)])
    _revive(model, FF_B, (20, 30))
    j_post(model, 2 * P)
    assert events(model, "replace") == []
    assert model._dispatch_progress[(FF_A, V0)].cell_prev == (20, 20)


# ============================================================================ T-R3 / T-R4: the rules (pure)

def _contest(d, k, persist=None):
    return jd.Contest(victim="victim_0", incumbent="ff_unit_0", d=d, k=k, persist=dict(persist or {}))


def test_tr3_stall_charge_boundary():
    """T-R3. A stalled incumbent (k = S, route 20) is replaced by a fresh spare with a clean approach iff
    d(B) < 20 + k: 29 yes, 30 no; never without a clean approach, never on a used pair.
    MUTANT tr3: the lost-time charge removed (d(B) < d(A))."""
    def plan(d_b, clean=True, ledger=None):
        return jd.plan_replacements(
            [_contest(20, S)], ["ff_unit_1"], {("ff_unit_1", "victim_0"): d_b}, ledger or {},
            {("ff_unit_1", "victim_0"): clean}, stall_steps=S, margin_persist=P,
        )
    assert [r.cause for r in plan(29)] == ["stall"]
    assert plan(30) == []
    assert plan(29, clean=False) == []
    assert plan(29, ledger={("ff_unit_1", "victim_0"): 1}) == []
    assert jd.plan_replacements(
        [_contest(20, S - 1)], ["ff_unit_1"], {("ff_unit_1", "victim_0"): 21}, {},
        {("ff_unit_1", "victim_0"): True}, stall_steps=S, margin_persist=P,
    ) == []


def _margin_frames(gaps, d_a=20, present=None):
    """Evaluate the margin rule over frames; gaps[t] = d(A) - d(B) at frame t; present[t] False = B not a spare."""
    state = jd.new_progress(d_a, (0, 0))
    replaced_at = None
    for t, gap in enumerate(gaps):
        is_spare = True if present is None else present[t]
        spare_d = {"ff_unit_1": d_a - gap} if is_spare else {}
        state = jd.update_persistence(state, spare_d, d_a, M, {"ff_unit_1": True})
        plan = jd.plan_replacements(
            [_contest(d_a, 0, state.persist_map())], list(spare_d), {("ff_unit_1", "victim_0"): d_a - gap},
            {}, {}, stall_steps=S, margin_persist=P,
        )
        if plan and replaced_at is None:
            replaced_at = t
    return replaced_at


def test_tr4_margin_needs_m_steps_for_p_evaluations():
    """T-R4. Gap 5 held for 3 evaluations replaces (at the 3rd); gap 4 never; 5, 5, 4 never; a binding younger
    than P cannot be replaced; a spare that was not free at one evaluation restarts its count.
    MUTANT tr4: P = 1."""
    assert _margin_frames([5, 5, 5]) == 2
    assert _margin_frames([4, 4, 4, 4, 4, 4]) is None
    assert _margin_frames([5, 5, 4]) is None
    assert _margin_frames([5, 5]) is None
    assert _margin_frames([5, 5, 5, 5], present=[True, False, True, True]) is None
    assert _margin_frames([5, 5, 5, 5, 5], present=[True, False, True, True, True]) == 4


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


def test_tr8_latched_incumbent_is_replaced_by_a_latch_fill(model):
    """T-R8. A latched binder (route_blocked, still bound) is replaced by a free unit with ONE binder after; the
    released unit is an unassigned route_blocked unit that the revalidation later clears; with no allowed free
    unit (the pair already bound twice) the latched unit is kept.
    MUTANT tr8: the latched binder is not released by the latch-fill."""
    place_units(model, {FF_A: (10, 10), FF_B: (16, 10)})
    place_victims(model, {V0: (12, 10)})
    assert assign(model, V0, FF_A)
    ff(model, FF_A).status = "route_blocked"
    j_post(model)
    fills = events(model, "latch_fill")
    assert len(fills) == 1 and fills[0]["reason"] == "joint_replace_latched"
    assert binders(model, V0) == [FF_B]
    assert bound_to(model, FF_A) is None and str(ff(model, FF_A).status).lower() == "route_blocked"
    model._revalidate_route_blocked_firefighters()
    assert str(ff(model, FF_A).status).lower() == "available"


def test_tr8_no_allowed_unit_keeps_the_latched_binder(model):
    """T-R8. A pair already bound twice may not latch-fill: the latched binder is kept. MUTANT tr8 (control)."""
    place_units(model, {FF_A: (10, 10), FF_B: (16, 10)})
    place_victims(model, {V0: (12, 10)})
    assert assign(model, V0, FF_A)
    ff(model, FF_A).status = "route_blocked"
    model._dispatch_ledger[(FF_B, V0)] = 2
    j_post(model)
    assert events(model, "latch_fill") == []
    assert binders(model, V0) == [FF_A]


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


# ============================================================================ T-FLIP-a: the theorem, simulated

def _simulate(seed: int, steps: int = 400, n_units: int = 3, n_victims: int = 3):
    """A state simulator in the model's J order (design 5.7, 6.7). Each frame:
      J-pre   FILL over free units x (waiting + latched-held) victims, LATCH-FILLs capped (b <= 1 before);
      advance OUTSIDE events on bound units - a closed route or a random raise: the pair's first raise unbinds it
              (the unit is then route_blocked), a repeated raise latches it (bound, flagged); deaths - and the
              routes change: every pair by an exogenous part (fire / victim motion) and the unit's own step;
      post    blocked units recover (revalidation), latched units may recover onto their victim, victims turn
              terminal (their latched units are released);
      J-post  PROGRESS on the bindings contestable at its start (x = the anchor distance moved by the exogenous
              part only; FROZEN from a random clean-approach predicate over the incumbent and the free units),
              FILL / LATCH-FILL, persistence on the spares left, REPLACE, SECOND FILL (units released by REPLACE x
              victims still waiting, uncapped).
    Returns every bind (with b before), the per-victim histories (with how each binding ended: "outside" for o1-o3,
    "J" for a REPLACE, "terminal") and the per-unit bind sequences."""
    rng = random.Random(seed)
    units = [f"ff_unit_{i}" for i in range(n_units)]
    victims = [f"victim_{i}" for i in range(n_victims)]
    dist = {(u, v): rng.randint(3, 40) for u in units for v in victims}
    closed: set[tuple[str, str]] = set()
    anchor: dict[tuple[str, str], int] = {}
    dead, blocked, terminal = set(), set(), set()
    active: dict[str, str] = {}             # victim -> active binder
    latched: dict[str, set[str]] = {v: set() for v in victims}
    raised: set[tuple[str, str]] = set()
    ledger: dict[tuple[str, str], int] = {}
    progress: dict[tuple[str, str], jd.Progress] = {}
    history: dict[str, list[dict]] = {v: [] for v in victims}
    unit_hist: dict[str, list[tuple[str, int, str]]] = {u: [] for u in units}
    binds: list[dict] = []
    seq = [0]

    def route(u, v):
        return None if (u, v) in closed else dist[(u, v)]

    def end(v, u, cause):
        for entry in reversed(history[v]):
            if entry["unit"] == u and entry["end"] is None:
                entry["end"] = cause
                return

    def bind(v, u, kind, cause=None):
        before = ledger.get((u, v), 0)
        ledger[(u, v)] = before + 1
        active[v] = u
        progress[(u, v)] = jd.new_progress(dist[(u, v)], (0, 0))
        anchor[(u, v)] = dist[(u, v)]
        seq[0] += 1
        history[v].append({"unit": u, "kind": kind, "end": None, "seq": seq[0]})
        unit_hist[u].append((v, seq[0], kind))
        binds.append({"victim": v, "unit": u, "kind": kind, "b_before": before, "cause": cause})

    def free_units():
        bound = set(active.values()) | {x for s in latched.values() for x in s}
        return [u for u in units if u not in dead and u not in blocked and u not in bound]

    def fill(pool_units, kind="fill", allow_latched=True):
        waiting = [v for v in victims if v not in terminal and v not in active and not latched[v]]
        held = [v for v in victims if v not in terminal and v not in active and latched[v]] if allow_latched else []
        if not pool_units or not (waiting or held):
            return []
        pairs = jd.solve_fill(pool_units, waiting + held,
                              {(u, v): route(u, v) for u in pool_units for v in waiting + held}, ledger, capped=held)
        used = []
        for pair in pairs:
            if pair.victim in held:
                for x in sorted(latched[pair.victim]):
                    blocked.add(x)           # released: an unassigned route_blocked unit
                latched[pair.victim].clear()
                bind(pair.victim, pair.unit, "latch_fill")
            else:
                bind(pair.victim, pair.unit, kind)
            used.append(pair.unit)
        return used

    for _ in range(steps):
        fill(free_units())                                   # J-pre
        for key in dist:                                     # advance: routes change
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
            if key in anchor:
                anchor[key] += e                             # the previous cell's distance moves with the fire only
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
            elif r < 0.035:
                del active[v]
                dead.add(u)                                  # o3: death
                end(v, u, "outside")
        for v in victims:                                    # post-move cycle
            for u in list(latched[v]):
                if rng.random() < 0.005:
                    latched[v].discard(u)
                    dead.add(u)
            if v not in terminal and rng.random() < 0.004:
                terminal.add(v)
                if v in active:
                    end(v, active.pop(v), "terminal")
                latched[v].clear()
        for u in list(blocked):
            if rng.random() < 0.2:
                blocked.discard(u)
        for v in victims:
            for u in sorted(latched[v]):
                if rng.random() < 0.05 and v not in active and v not in terminal:
                    latched[v].discard(u)
                    active[v] = u                            # its own move found a path: active again
                    seq[0] += 1
                    history[v].append({"unit": u, "kind": "recover", "end": None, "seq": seq[0]})
                    unit_hist[u].append((v, seq[0], "recover"))
        # J-post
        contest = dict(active)
        free_start = free_units()
        clean = {(u, v): rng.random() < 0.8 for u in units for v in victims}
        unevaluated = set()
        for v, u in contest.items():
            state = progress.get((u, v))
            d_now = route(u, v)
            if state is None or d_now is None:
                unevaluated.add(v)
                continue
            frozen = not (clean[(u, v)] or any(clean[(f, v)] for f in free_start))
            progress[(u, v)] = jd.progress_step(state, d_now, anchor[(u, v)], (0, 0), frozen)
            anchor[(u, v)] = d_now
        used = fill(free_start)
        spares = [u for u in free_start if u not in used]
        contests = []
        for v, u in contest.items():
            if v in unevaluated or active.get(v) != u:
                continue
            spare_d = {b: route(b, v) for b in spares}
            fresh = {b: ledger.get((b, v), 0) == 0 for b in spares}
            state = jd.update_persistence(progress[(u, v)], spare_d, route(u, v), M, fresh)
            progress[(u, v)] = state
            contests.append(jd.Contest(victim=v, incumbent=u, d=route(u, v), k=state.k, persist=state.persist_map()))
        released = []
        if spares and contests:
            matrix = {(b, v): route(b, v) for b in spares for v in victims}
            plan = jd.plan_replacements(contests, spares, matrix, ledger, clean, stall_steps=S, margin_persist=P)
            for rep in plan:
                end(rep.victim, rep.old_unit, "J")
                progress.pop((rep.old_unit, rep.victim), None)
                bind(rep.victim, rep.new_unit, "replace", rep.cause)
                released.append(rep.old_unit)
        if released:
            fill([u for u in released if u in free_units()], kind="second_fill", allow_latched=False)
    return binds, history, unit_hist, units


@pytest.mark.parametrize("seed", range(500))
def test_tflip_a_no_reversal_by_a_cost_decision(seed):
    """T-FLIP-a. Over random distances, route closures and outside events, in the model's J order: no REPLACE binds a
    pair with b >= 1; no LATCH-FILL brings in a pair with b >= 2; every RETURN - A..X..A on a victim and v..w..v on
    a unit - follows an OUTSIDE event (the binding just before the return on that victim ended by o1-o3, never by
    J) and is never a REPLACE; REPLACEs per victim <= N_ff - 1; binds per victim <= 5 N_ff.
    MUTANT tflip: the b = 0 rule for REPLACE removed."""
    binds, history, unit_hist, units = _simulate(seed)
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
    """The simulator reaches every rule the theorem speaks about: REPLACEs (stall and margin), LATCH-FILLs, second
    fills, returns on victims and on units. A guard on T-FLIP-a itself, not a separate property."""
    kinds: dict[str, int] = {}
    returns = 0
    for seed in range(100):
        binds, history, unit_hist, _ = _simulate(seed)
        for b in binds:
            kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
            if b["kind"] == "replace":
                kinds["replace_" + str(b["cause"])] = kinds.get("replace_" + str(b["cause"]), 0) + 1
        for seqs in unit_hist.values():
            real = [v for v, _, k in seqs if k != "recover"]
            returns += sum(1 for i in range(2, len(real)) if real[i] in real[: i - 1] and real[i - 1] != real[i])
    assert kinds.get("replace", 0) > 20 and kinds.get("latch_fill", 0) > 20 and kinds.get("second_fill", 0) > 0
    assert kinds.get("replace_stall", 0) > 5 and kinds.get("replace_margin", 0) > 5, kinds
    assert returns > 20


# ============================================================================ T-FLIP-b: scripted, model level

def test_tflip_b_alternating_advantage_replaces_at_most_once(model):
    """T-FLIP-b. A and B alternate being 20 steps closer to the victim, 10 consecutive frames each, for 200
    frames: exactly one replacement - the ledger forbids every replacement back. Then the holder is forced to raise
    route_blocked (an outside event): the other returns by a FILL. Then that one raises too: with a fresh unit C
    available (farther than both), C is bound - a re-used pair returns only if no fresh pair covers the victim;
    and once C raises as well, no fresh pair is left and a re-used pair serves the victim (it does not wait).
    MUTANT tflip: the b = 0 rule for REPLACE removed (the mutant shows >= 2 replacements in the first phase)."""
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
    j_post(model)
    assert bound_to(model, FF_C) == V0
    assert model._dispatch_ledger[(FF_C, V0)] == 1
    # C raises: every pair is re-used now; the victim is still served
    unit3 = ff(model, FF_C)
    unit3.status = "route_blocked"
    model._on_firefighter_route_blocked(unit3)
    model._revalidate_route_blocked_firefighters()
    j_post(model)
    assert len(binders(model, V0)) == 1 and binders(model, V0)[0] in (FF_A, FF_B)
