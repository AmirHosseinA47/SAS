"""Dispatch round 2 - the corrected dispatcher (outputs/dispatch2_part1.txt sections 2.8, 4-7 and 13 (3); rulings
section 19: every option (a)).

C1  history never ranks a choice between units: the fill key (L1, L1b, L2' total d*, L3' worst d*, L4' re-use as an
    exact-tie tie-break, L5 ids); a replacement takes the lowest-id ledger-ALLOWED spare among the nearest qualifying
    ones, else the incumbent is kept (a nearest_barred record).
C2  a bound unit whose route is closed is an incumbent credited with its grid distance G, its closed steps counted
    apart (k_L, reset when the route opens); latched-held victims are contests, not fill targets, under Limit 3.
R-1 d* (the clean distance when finite, else d) and progress against every cell the unit has stood on since its last
    progress, on the current board (a metric with no finite value over the history is not compared - amendment A2).
R-2 a clean approach for every challenger, and L1b in the fill.
C3  no new behaviour: a regression check that J leaves a free unit it cannot use untouched.

Every test names the MUTANT it kills (outputs/_dq_mutants.py records them).
"""

from __future__ import annotations

import pytest

from dispatch_test_support import (
    FF_A,
    FF_B,
    FF_C,
    V0,
    V1,
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
)
from src_extension.planning import joint_dispatch as jd

S = 10  # ruling D-8; unchanged (outputs/dispatch2_part1.txt section 0 / 19)
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


# ============================================================================ C1: nearest wins

def test_c1_a_nearer_reused_unit_beats_a_farther_fresh_one(model):
    """C1 (unit side; round 1's ring set 1 B_S step 84 shape). The victim waits; A (route 10) has bound it once
    before (b = 1), B (route 25) is fresh: A is bound.
    MUTANT c1_l2: round 1's L2 (fewest re-used pairs) restored ahead of the route keys."""
    place_units(model, {FF_A: (20, 30), FF_B: (20, 15)})
    place_victims(model, {V0: (20, 40)})
    model._dispatch_state("_dispatch_ledger", dict)[(FF_A, V0)] = 1
    j_post(model)
    assert bound_to(model, FF_A) == V0 and bound_to(model, FF_B) is None
    assert events(model, "fill")[-1]["distance"] == 10


def test_c1_a_nearer_victim_on_a_reused_pair_beats_a_farther_fresh_one(model):
    """C1 (victim side; round 1's uniform set 2 B_W step 63 shape). One free unit, two waiting victims: v at route 9
    on a re-used pair, w at route 18 fresh: the unit serves v.
    MUTANT c1_l2."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 29), V1: (20, 2)})
    model._dispatch_state("_dispatch_ledger", dict)[(FF_A, V0)] = 1
    j_post(model)
    assert bound_to(model, FF_A) == V0


def test_c1_l1b_a_clean_approach_beats_a_nearer_unit_without_one(model):
    """R-2 (b) in the fill (key L1b). A stands in a smoke pocket (its cell and its four neighbours smoky: no clean
    approach; d* = d = 10); B has a clean approach at 20: B is bound.
    MUTANT r2_fill: L1b removed from the fill key."""
    place_units(model, {FF_A: (20, 30), FF_B: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    smoke(model, [(20, 30), (19, 30), (21, 30), (20, 29), (20, 31)])
    j_post(model)
    assert bound_to(model, FF_B) == V0 and bound_to(model, FF_A) is None


def _stall_scene_with_barred_nearest(model):
    """A bound to v (route 20) loops between (20, 20) and (20, 21); spare B (route 12, b(B, v) = 1: barred) and
    spare C (route 20, fresh) both qualify for the stall charge at k = S; B also margin-qualifies (12 + 5 <= 20)."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    _revive(model, FF_B, (22, 30))
    _revive(model, FF_C, (25, 25))
    model._dispatch_ledger[(FF_B, V0)] = 1


def test_c1_the_incumbent_is_kept_when_the_nearest_qualifying_spare_is_barred(model):
    """C1 in a replacement (4.3, ruling X-1 (a)). The nearest qualifying spare B is ledger-barred (a REPLACE needs
    b = 0); the farther fresh spare C also qualifies at k = S - but J keeps the stalled incumbent rather than send a
    farther unit, and records nearest_barred decisions (margin, then stall).
    MUTANT c1_allowed: the replacement takes the nearest ALLOWED spare (ruling X-1 (b)) - C replaces A."""
    _stall_scene_with_barred_nearest(model)
    for frame in range(2 * S + 2):
        move(model, FF_A, (20, 21) if frame % 2 == 0 else (20, 20))
        j_post(model)
    assert events(model, "replace") == []
    assert bound_to(model, FF_A) == V0 and bound_to(model, FF_C) is None
    reasons = {e["reason"] for e in events(model, "nearest_barred")}
    assert reasons == {"nearest_barred_margin", "nearest_barred_stall"}, reasons
    assert all(e["barred"] == [FF_B] for e in events(model, "nearest_barred"))


def test_c1_a_tie_at_the_least_distance_goes_to_the_allowed_spare():
    """C1 tie rule (4.3; review finding design M3). Two qualifying spares at the same least d* 15: ff_unit_1 is
    barred (b = 1), ff_unit_2 is fresh - ff_unit_2 replaces; the lower id does not decide before the ledger.
    MUTANT c1_tieorder: the lowest-id spare among the nearest is taken before the ledger is read (then barred -> none)."""
    contest = jd.Contest(victim="victim_0", incumbent="ff_unit_0", delta=20, route_open=True, k=S, k_closed=0,
                         persist={})
    reps, barred = jd.plan_replacements_detail(
        [contest], ["ff_unit_1", "ff_unit_2"],
        {("ff_unit_1", "victim_0"): 15, ("ff_unit_2", "victim_0"): 15},
        {("ff_unit_1", "victim_0"): 1},
        {("ff_unit_1", "victim_0"): True, ("ff_unit_2", "victim_0"): True},
        stall_steps=S, margin_persist=P,
    )
    assert [(r.new_unit, r.cause, r.distance) for r in reps] == [("ff_unit_2", "stall", 15)] and barred == []


def test_c1_the_margin_leg_counts_a_barred_spares_persistence(model):
    """C1, margin leg (4.3: persistence is kept for every spare, fresh or not). A bound and still (route 30); spare
    B1 at route 10 (b = 1, barred) and spare B2 at route 20 (fresh) both hold the margin (10 + 5, 20 + 5 <= 30)
    for P evaluations. B1 is the nearest qualifying spare and is barred, so nothing is replaced at the margin - nor
    at the stall charge later.
    MUTANT c1_freshpersist: the model counts persistence (and offers spares) only for fresh pairs - B2 replaces A at
    the 3rd evaluation."""
    place_units(model, {FF_A: (20, 10)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    _revive(model, FF_B, (20, 30))
    _revive(model, FF_C, (20, 20))
    model._dispatch_ledger[(FF_B, V0)] = 1
    j_post(model, 2 * S)
    assert events(model, "replace") == []
    assert bound_to(model, FF_A) == V0
    assert events(model, "nearest_barred")


# ============================================================================ C2: a closed-route binder is an incumbent

def test_c2_an_active_unit_whose_route_is_closed_is_judged_on_g_and_k_closed(model):
    """C2 (5.2): an ACTIVE binder (en_route) whose route is closed - a ring of fire around it, its raise postponed -
    is evaluated with delta = G = 3 and its closed count k_L: a stall REPLACE (b = 0; reason reassign_stall) by the
    spare at d* 15 comes at the 14th J-post (15 < 3 + 13), not before. Round 1 left such a binding unevaluated.
    MUTANT c2_activeclosed: an active binder whose route is closed is not evaluated (round 1's 6.3)."""
    place_units(model, {FF_A: (10, 10), FF_B: (13, 25)})
    place_victims(model, {V0: (13, 10)})
    assert assign(model, V0, FF_A)
    assert str(ff(model, FF_A).status).lower() == "en_route"
    burn(model, [(11, 10), (9, 10), (10, 11), (10, 9)])
    for frame in range(1, 14):
        j_post(model)
        assert events(model, "replace") == [], frame
    j_post(model)
    reps = events(model, "replace")
    assert len(reps) == 1 and reps[0]["reason"] == "reassign_stall" and reps[0]["unit"] == FF_B, reps
    assert binders(model, V0) == [FF_B]


def test_c2_the_closed_count_resets_when_the_route_opens():
    """C2 (5.2; review finding design B1). A binding closed for 30 counted J-posts whose route then reopens at
    d* 21 is judged on its OPEN-route count (0, then 1): a fresh spare at d* 50 does not stall-replace it, although
    50 < 21 + 30. During the closed spell it was not replaced either (50 >= G 15 + 30).
    MUTANT c2_onecount: the closed steps also add to the open-route count k."""
    state = jd.new_progress((0, 0))
    for t in range(30):
        state = jd.progress_step(state, False, None, None, (None,) * len(state.history),
                                 (None,) * len(state.history), (0, 0), False)
    assert (state.k, state.k_closed, state.closed) == (0, 30, True)

    def plan(st, delta, route_open):
        return jd.plan_replacements(
            [jd.Contest(victim="victim_0", incumbent="ff_unit_0", delta=delta, route_open=route_open, k=st.k,
                        k_closed=st.k_closed, persist={})],
            ["ff_unit_1"], {("ff_unit_1", "victim_0"): 50}, {}, {("ff_unit_1", "victim_0"): True},
            stall_steps=S, margin_persist=P,
        )
    assert plan(state, 15, False) == []
    state = jd.progress_step(state, True, 21, 21, (21,), (21,), (0, 0), False)
    assert (state.k, state.k_closed, state.closed) == (1, 0, False)
    assert plan(state, 21, True) == []


def test_c2_frozen_steps_count_in_neither_count():
    """C2 / 6.3 FROZEN (nobody could pick the victim up): neither k (open, no progress) nor k_L (closed) advances.
    MUTANT c2_frozenL: the closed branch counts FROZEN steps."""
    state = jd.new_progress((0, 0))
    state = jd.progress_step(state, False, None, None, (None,), (None,), (0, 0), True)
    assert (state.k, state.k_closed) == (0, 0)
    state = jd.progress_step(state, True, 5, None, (5,), (None,), (0, 0), True)
    assert (state.k, state.k_closed) == (0, 0)
    state = jd.progress_step(state, False, None, None, (None,), (None,), (0, 0), False)
    assert (state.k, state.k_closed) == (0, 1)


# ============================================================================ R-1: d* and the history rule

def _clean_step(model, cell, vcell):
    """The next cell of a shortest clean path from `cell` to the victim (the clean field from the victim; ties by the
    movers' neighbour order)."""
    burning = model._active_burning_cells()
    unclean = jd.unclean_cells(burning, set())
    field = jd.bfs_distances(vcell, model.grid.width, model.grid.height, unclean)
    here = field[cell]
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nxt = (cell[0] + ox, cell[1] + oy)
        if field.get(nxt) == here - 1:
            return nxt
    raise AssertionError(("no clean step", cell))


def test_r1_a_unit_walking_a_clean_detour_never_stalls(model):
    """R-1 (2.2's worked example on the real model). A burning wall x = 10, y = 10..20 with a gap at (10, 15); the
    victim at (20, 15); A bound at (8, 15): d = 12 through the gap, but the clean route goes round the wall's end
    (D_c 26). A walks the clean route one cell per frame: its fire-free d first rises, yet every step beats every
    earlier cell on the clean distance, so k stays 0 and the spare B (d 15 through the gap, a clean approach)
    is never sent.
    MUTANT r1_donly: progress judged on the fire-free d only (round 1's metric) - A stalls at frame S + 1 and B
    replaces it."""
    burn(model, [(10, y) for y in range(10, 21) if y != 15])
    place_units(model, {FF_A: (8, 15)})
    place_victims(model, {V0: (20, 15)})
    j_post(model)
    assert bound_to(model, FF_A) == V0
    _revive(model, FF_B, (5, 15))
    cell = (8, 15)
    for frame in range(16):
        cell = _clean_step(model, cell, (20, 15))
        move(model, FF_A, cell)
        j_post(model)
        assert model._dispatch_progress[(FF_A, V0)].k == 0, (frame, cell)
    assert events(model, "replace") == [] and bound_to(model, FF_A) == V0


def test_r1_a_two_cell_loop_on_the_clean_field_boundary_still_stalls(model):
    """R-1 with amendment A2 (a metric with no finite value over the history is not compared). The victim at
    (20, 0). A loops between q = (20, 20) - smoky, but with a clean neighbour (20, 21) in the field, so its clean
    distance is finite - and p = (20, 19), smoky with no clean neighbour (its clean distance is none), p one step
    nearer by d. The loop never beats its own history: k reaches S and the spare B replaces A by stall.
    MUTANT q_emptyinf: an empty history minimum read as infinite (2.8's draft text) - at q the clean distance
    'beats' p's none, at p the fire-free d beats q's: progress every frame, no stall."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 0)})
    smoke(model, [(20, 20), (20, 19), (19, 19), (21, 19), (20, 18), (19, 20), (21, 20)])
    j_post(model)
    assert bound_to(model, FF_A) == V0
    _revive(model, FF_B, (35, 5))       # route 20, a clean approach: a stall challenger, never 5 closer
    for frame in range(2 * S + 2):
        move(model, FF_A, (20, 19) if frame % 2 == 0 else (20, 20))
        j_post(model)
        if events(model, "replace"):
            break
    reps = events(model, "replace")
    assert len(reps) == 1 and reps[0]["reason"] == "reassign_stall" and reps[0]["unit"] == FF_B, reps


def test_r1_dstar_is_d_when_no_clean_path_exists(model):
    """R-1. The victim's own cell is smoky, so no unit has a clean distance: d* falls back to d (10), the unit is
    bound with that distance (feasibility unchanged).
    MUTANT r1_cnone: d* = the clean distance only (None when there is no clean path) - nobody is bound."""
    place_units(model, {FF_A: (20, 30)})
    place_victims(model, {V0: (20, 40)})
    smoke(model, [(20, 40)])
    j_post(model)
    assert bound_to(model, FF_A) == V0 and events(model, "fill")[-1]["distance"] == 10


def test_r1_the_history_is_the_bind_cell_at_the_bind(model):
    """R-1 (review finding design m1): a bind initialises H to the bind cell and both counts to 0.
    MUTANT q_initempty: new_progress starts with an empty history."""
    assert jd.new_progress((3, 4)) == jd.Progress(history=((3, 4),))
    place_units(model, {FF_A: (20, 30)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    state = model._dispatch_progress[(FF_A, V0)]
    assert (state.history, state.k, state.k_closed) == (((20, 30),), 0, 0)


# ============================================================================ R-2: a clean approach for every challenger

def test_r2_a_margin_challenger_without_a_clean_approach_is_refused(model):
    """R-2 (a). A bound and still at route 20; spare B at route 10 (5 closer: a margin challenger) stands in a smoke
    pocket (no clean approach): no margin replacement at the P-th evaluation, nor later.
    MUTANT r2_margin: the margin challenger's clean-approach test removed."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (20, 40)})
    j_post(model)
    _revive(model, FF_B, (20, 30))
    smoke(model, [(20, 30), (19, 30), (21, 30), (20, 29), (20, 31)])
    j_post(model, 2 * S)
    assert events(model, "replace") == [] and bound_to(model, FF_A) == V0


# ============================================================================ C3: no unit is held (regression check)

def test_c3_a_free_unit_no_victim_can_use_is_left_untouched(model):
    """C3 (6.3; X-4 (a): no new behaviour). The waiting victim is enclosed by fire; the free unit has no route to
    her. J issues nothing and leaves the unit exactly as it was (no target, not assigned, status available), so the
    unit runs the shipped free-unit policy; I4 (W leg) holds. Once the ring burns out, the same J point binds it.
    A REGRESSION CHECK (C3 adds no code; Z-C3 is a code-structure check) - no mutant."""
    place_units(model, {FF_A: (20, 20)})
    place_victims(model, {V0: (30, 30)})
    ring = [(31, 30), (29, 30), (30, 31), (30, 29)]
    burn(model, ring)
    j_post(model, 3)
    unit = ff(model, FF_A)
    assert events(model) == []
    assert unit.target_pos is None and not unit.assigned and str(unit.status).lower() == "available"
    assert unit.rescued_victim is None
    unburn(model, ring)
    j_post(model)
    assert bound_to(model, FF_A) == V0
