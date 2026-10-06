"""Urgency round - U1, the urgency re-dispatch order (outputs/urgency_part1.txt sections 6-14; the Part 2 tests of
15.3: T-U1..T-U11, T-CAS, T-DRN, T-FLIP-U, T-SRC, T-INFO-a..c, T-SW, T-ID).

THE BUILT RULE. At a QUALIFYING kick of _try_dispatch_unresolved_confirmed_victims - DISPATCH_URGENCY on an exact 1,
exactly ONE free unit f (|F| = 1, F by _firefighter_available_for_dispatch), two or more waiting victims (|W| >= 2, W
by today's three predicates) and at least one burning cell - W is visited in the order of
    key(v) = (0, T(v), c(f, v), idx(v))   if v is PROMOTABLE (c finite and c + 1 <= T(v))
             (1, idx(v))                  otherwise (DEFERRED, today's index order),
T = FAE.arrival_time with FrontPriorityParams() defaults at v's live cell, c = the safe-in-time route of 8.2 (clean
cells - not burning, not smoky, not 4-adjacent to fire - the unit's own cell exempt, the victim's cell not; a cell is
entered at hop k only if T* > k). The loop body (one _dispatch_firefighter_to_victim(vid, marker, "initial") per
victim) is today's. Every other kick runs today's loop verbatim.

Every test names its MUTANT(S) in its docstring; outputs/_ud_mutants_u1.py holds each mutant as exact-text edits and
the tests it must kill. Most tests drive the REAL model directly (park units and victims, set the fire, call the
kick); T-ID and one T-INFO-b form run short pinned real-model runs in which the searcher's never-seen proximity bonus
is stubbed to 0.0 IN EVERY ARM (it costs about 10 s per step in the searcher's coverage target and is not read by
dispatch), so the identity comparisons stay exact.
"""

from __future__ import annotations

import ast
import inspect
import io
import random
import re
import textwrap
import types
from contextlib import redirect_stdout

import numpy as np
import pytest

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation import local_adaptation_generator as lag
from src_extension.planning import urgency_dispatch as ud
from src_extension.planning.fire_arrival_estimate import FrontPriorityParams, arrival_time, front_priority_params
from urgency_test_support import (
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
    ff,
    fire_agents,
    fire_at as fire_at_cell,
    pinned_model,
    place_units,
    place_victims,
    quiet_fire,
    restore_config,
    set_step,
    smoke,
    switches,
    unburn,
    victim,
)
from wildfire_model import PhysicalRescueCommand

FIRE = (25, 10)          # the usual single burning cell; wind "north" pushes the fire toward +y
VICTIMS = (V0, V1, V2, V3, V4)
UNITS = (FF_A, FF_B, FF_C)
_TRIAGE_RE = re.compile(r"^\[UrgencyTriage\] step=(\S+) unit=(\S*) order=\[(.*)\] served=(\S*)$")
_TOKEN_RE = re.compile(r"(victim_\d+)\(T=([^,]+),c=([^,]+),([PD])\)")


@pytest.fixture(autouse=True)
def _pristine_config(monkeypatch):
    """Every test starts from the import-time configuration: the full suite's other files leave scenario settings
    behind, and the real-model tests here (T-ID, T-INFO-b) depend on them. A test's own switches are set afterwards
    and win; monkeypatch undoes all of it."""
    restore_config(monkeypatch)


# ================================================================================================ helpers

def _scene(monkeypatch, units, victims, *, burning=(FIRE,), smoky=(), wind="north", detected=None, urgency=1,
           step=100, numpy_bool=True):
    """A pinned real model with the fire cleared and re-set: `units` free on their cells (every other unit dead),
    `victims` parked and detected (or only `detected`), `burning` / `smoky` set on the Fire agents."""
    switches(monkeypatch, urgency=urgency)
    model = pinned_model(monkeypatch)
    quiet_fire(model)
    model.wind.wind_direction = wind
    place_units(model, units)
    place_victims(model, victims, detected=detected)
    burn(model, burning, numpy_bool=numpy_bool)
    smoke(model, smoky)
    set_step(model, step)
    return model


def _kick(model):
    """One kick of the re-dispatch loop: (stdout, the executor audit entries it added)."""
    n = len(model._physical_rescue_command_audit)
    out = io.StringIO()
    with redirect_stdout(out):
        model._try_dispatch_unresolved_confirmed_victims()
    log = [(e["action"], e["victim_id"], e["firefighter_id"], e["reason"], bool(e["success"]))
           for e in model._physical_rescue_command_audit[n:]]
    return out.getvalue(), log


def _triage(out):
    """[(unit, [(vid, T, c, P|D)], served)] for every [UrgencyTriage] line in `out`."""
    rows = []
    for line in out.splitlines():
        if not line.startswith("[UrgencyTriage]"):
            continue
        match = _TRIAGE_RE.match(line)
        assert match, line
        tokens = [(v, t, c, pd) for v, t, c, pd in _TOKEN_RE.findall(match.group(3))]
        rows.append((match.group(2), tokens, match.group(4)))
    return rows


class _OrderSpy:
    """Records every urgency_order call made through the module attribute WM reads at call time."""

    def __init__(self, monkeypatch):
        self.calls = []
        original = ud.urgency_order

        def spy(*args, **kwargs):
            ordered, records = original(*args, **kwargs)
            self.calls.append({"unit_cell": tuple(args[1]), "waiting": list(args[0]), "ordered": list(ordered),
                               "records": records, "x_size": args[5], "y_size": args[6]})
            return ordered, records

        monkeypatch.setattr(ud, "urgency_order", spy)


class _CommandSpy:
    """Every physical command reaching the model's sink, and every _release_other_claimants call."""

    def __init__(self, monkeypatch, model):
        self.commands = []
        self.releases = []
        apply_original = model.apply_physical_rescue_command
        release_original = model._release_other_claimants

        def apply(cmd):
            self.commands.append((str(cmd.action), str(cmd.victim_id or ""), str(cmd.firefighter_id or ""),
                                  str(cmd.reason or "")))
            return apply_original(cmd)

        def release(*args, **kwargs):
            self.releases.append(args)
            return release_original(*args, **kwargs)

        monkeypatch.setattr(model, "apply_physical_rescue_command", apply)
        monkeypatch.setattr(model, "_release_other_claimants", release)


def _crafted_t(monkeypatch, values, default=1000.0):
    """Replace U1's estimator call with a crafted T grid (T-U2 / T-U3(iii) / T-U7)."""
    def fake(height, width, burning, wind, params):
        grid = np.full((height, width), float(default))
        for cell, value in values.items():
            grid[cell] = float(value)
        return grid

    monkeypatch.setattr(ud, "arrival_time", fake)


def _unbind(model, ff_id, reason, *, reset=True):
    """An OUTSIDE unbind made by the test (a route_blocked handler, a death or a rescue), never by U1."""
    unit = ff(model, ff_id)
    vid = bound_to(model, ff_id)
    model.apply_physical_rescue_command(PhysicalRescueCommand(
        action="unassign", victim_id=vid or "", firefighter_id=ff_id, reason=reason,
        metadata={"reset_victim_pending": True} if reset else {}))
    return unit, vid


def _rescue_done(model, vid, ff_id):
    """Outside event o4/o5: the binder carried `vid` out and is back, available."""
    _unbind(model, ff_id, "test_outside_rescued", reset=False)
    state = model.managed_victims[vid]
    state.rescued = True
    state.status = "rescued"
    victim(model, vid).status = "rescued"
    ff(model, ff_id).status = "available"


def _waiting_today(model):
    """W by today's three predicates, computed by the test (independent of U1's builder)."""
    out = []
    for vid, state in model.managed_victims.items():
        marker = model.victim_marker_agents.get(vid)
        if not model._victim_needs_rescue(vid, marker):
            continue
        confirmed = bool(getattr(state, "confirmed", False))
        status = str(getattr(marker, "status", "") or "").strip().lower() if marker is not None else ""
        if not confirmed and status != "confirmed":
            continue
        if model._find_active_firefighter_for_victim(vid, marker):
            continue
        out.append(vid)
    return out


def _free_today(model):
    return [uid for uid, unit in model.firefighter_marker_agents.items()
            if model._firefighter_available_for_dispatch(unit)]


def _any_burning(model):
    return any(bool(a.burning) for a in fire_agents(model))


# ================================================================================================ T-U1

def test_tu1_scarcity_serves_the_smaller_t_even_at_the_higher_index(monkeypatch):
    """T-U1. One free unit, two promotable victims: victim_2 (T 146) is served before victim_0 (T 262), although
    today's index order serves victim_0 - which the same state with the switch off does.
    MUTANTS: tu1_noorder (the urgency order computed but not applied); tu4_never (no kick ever qualifies)."""
    units, victims = {FF_A: (30, 20)}, {V0: (10, 12), V2: (40, 30)}
    model = _scene(monkeypatch, units, victims)
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    assert len(spy.calls) == 1, "the kick did not qualify"
    (call,) = spy.calls
    rec = call["records"]
    assert rec[V0]["promotable"] and rec[V2]["promotable"]
    assert rec[V2]["T"] < rec[V0]["T"]
    assert call["ordered"] == [V2, V0] and call["unit_cell"] == (30, 20)
    assert log == [("assign", V2, FF_A, "initial", True)]
    assert bound_to(model, FF_A) == V2 and binders(model, V0) == []
    ((unit, tokens, served),) = _triage(out)
    assert unit == FF_A and served == V2 and [t[0] for t in tokens] == [V2, V0]
    assert [t[3] for t in tokens] == ["P", "P"]
    off = _scene(monkeypatch, units, victims, urgency=0)
    out_off, log_off = _kick(off)
    assert log_off == [("assign", V0, FF_A, "initial", True)] and "[UrgencyTriage]" not in out_off


def test_tu1_the_triage_line_follows_the_bind_and_names_the_victim_bound(monkeypatch):
    """T-U1 / 13.3 (R1-1). The order's head victim_2 carries state.cancelled - a written-off victim relabelled
    "confirmed" by reset_victim_pending (WM:3243-3253) - so she is in W but select_rescue_assignment refuses her,
    and the loop binds the next victim of U1's order, victim_0. The [UrgencyTriage] line comes AFTER that bind's
    [Dispatch] line and names served=victim_0, the victim actually bound. With both victims refused, nothing binds
    and the line says served=none.
    MUTANTS: tu13_served_head (served = the order's head); tu13_print_before (the line printed before the binds)."""
    units, victims = {FF_A: (30, 20)}, {V0: (10, 12), V2: (40, 30)}
    model = _scene(monkeypatch, units, victims)
    model.managed_victims[V2].cancelled = True
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    assert len(spy.calls) == 1 and spy.calls[0]["ordered"] == [V2, V0]
    assert log == [("assign", V0, FF_A, "initial", True)] and bound_to(model, FF_A) == V0
    ((unit, tokens, served),) = _triage(out)
    assert unit == FF_A and served == V0 and [t[0] for t in tokens] == [V2, V0]
    lines = out.splitlines()
    i_dispatch = next(i for i, ln in enumerate(lines) if ln.startswith("[Dispatch]") and V0 in ln)
    i_triage = next(i for i, ln in enumerate(lines) if ln.startswith("[UrgencyTriage]"))
    assert i_dispatch < i_triage
    both = _scene(monkeypatch, units, victims)
    both.managed_victims[V0].cancelled = True
    both.managed_victims[V2].cancelled = True
    out2, log2 = _kick(both)
    ((_, tokens2, served2),) = _triage(out2)
    assert log2 == [] and served2 == "none" and [t[0] for t in tokens2] == [V2, V0]


# ================================================================================================ T-U2

@pytest.mark.parametrize(
    "t_v,promotable,c",
    [(11.0, True, 10),      # c + 1 = T: promotable (the boundary)
     (10.5, False, 10),     # c finite, c + 1 > T: deferred by the in-time cut ALONE
     (10.0, False, None)],  # c + 1 = T + 1: refused already by the entry test T*(v) > c (T* <= T at v's own cell)
    ids=["c+1=T", "c<T<c+1", "c+1=T+1"])
def test_tu2_in_time_cut_boundary(monkeypatch, t_v, promotable, c):
    """T-U2 (pure, crafted T). The unit at (10,10), the victim at (10,20) on a clean straight route (Manhattan 10):
    promotable iff c + 1 <= T. Because T*(v) <= T(v), the route's entry test already refuses T(v) <= c, so the cut
    itself bites only for T in (c, c + 1) - the [c<T<c+1] case - and c + 1 = T + 1 is guarded twice.
    MUTANTS: tu2_cut (the cut removed) on [c<T<c+1]; tu2_no_pickup (c <= T) on [c<T<c+1]; tu2_strict (c + 1 < T)
    on [c+1=T]; tu2_cut_and_static (the cut AND the T* entry test removed) on [c+1=T+1]."""
    _crafted_t(monkeypatch, {(10, 20): t_v})
    ordered, rec = ud.urgency_order([(V0, (10, 20))], (10, 10), [(45, 45)], [], (0.0, 1.0), 50, 50)
    assert rec[V0]["c"] == c
    assert rec[V0]["promotable"] is promotable
    assert rec[V0]["key"] == ((0, t_v, c, 0) if promotable else (1, 0))


def test_tu2_urgent_but_too_late_is_deferred_and_the_reachable_one_served(monkeypatch):
    """T-U2 (model). victim_0 is the most urgent (T 10.5) but the free unit needs c = 10, so c + 1 > T: she is
    deferred and the promotable, less urgent victim_2 (T 500) is served; today's index order would serve victim_0.
    MUTANTS: tu2_cut; tu2_no_pickup; tu2_cut_and_static."""
    model = _scene(monkeypatch, {FF_A: (10, 10)}, {V0: (10, 20), V2: (20, 10)}, burning=[(45, 45)])
    _crafted_t(monkeypatch, {(10, 20): 10.5, (20, 10): 500.0})
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    rec = spy.calls[0]["records"]
    assert (rec[V0]["c"], rec[V0]["promotable"]) == (10, False)
    assert (rec[V2]["c"], rec[V2]["promotable"]) == (10, True)
    assert log == [("assign", V2, FF_A, "initial", True)]
    ((_, tokens, served),) = _triage(out)
    assert served == V2 and tokens[1][0] == V0 and tokens[1][3] == "D"


# ================================================================================================ T-U3

def _wall(kind):
    """A barrier across the whole grid width at y = 25 (the unit at (10,10) is south of it, victim_0 at (10,40)
    north of it): burning, fire-adjacent only (burning cells at y 24 / 26, alternating, so row 25 is ALL
    fire-adjacent and none of it burns), or smoky (with one far burning cell so a fire exists)."""
    if kind == "burning":
        return [(x, 25) for x in range(50)], []
    if kind == "fire_adjacent":
        return [(x, 24) for x in range(0, 50, 2)] + [(x, 26) for x in range(1, 50, 2)], []
    return [(10, 45)], [(x, 25) for x in range(50)]


@pytest.mark.parametrize("kind", ["burning", "fire_adjacent", "smoky"])
def test_tu3_i_reachable_only_through_unclean_cells_is_deferred(monkeypatch, kind):
    """T-U3 (i). victim_0 is reachable only across an unclean wall (burning / fire-adjacent / smoky): no safe route,
    deferred; victim_2 on the unit's side is promotable and served (the index order would serve victim_0). Each
    wall leaves victim_0 the more urgent, so a mutant that opens the wall serves her.
    MUTANTS: tu3_smoke_ignored and tu3_burning_only on [smoky]; tu3_fire_blind_route on all three."""
    burning, smoky = _wall(kind)
    model = _scene(monkeypatch, {FF_A: (10, 10)}, {V0: (10, 40), V2: (40, 12)}, burning=burning, smoky=smoky)
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    rec = spy.calls[0]["records"]
    assert rec[V0]["T"] < rec[V2]["T"]
    assert rec[V0]["c"] is None and rec[V0]["promotable"] is False
    assert rec[V2]["promotable"] is True
    assert log == [("assign", V2, FF_A, "initial", True)]


@pytest.mark.parametrize("kind", ["smoky", "fire_adjacent", "own_cell_smoky", "own_cell_fire_adjacent"])
def test_tu3_ii_victim_on_an_unclean_cell_is_deferred(monkeypatch, kind):
    """T-U3 (ii). victim_0 stands on an unclean cell - smoky or fire-adjacent, away from the unit or on the free
    unit's own cell (the unit's cell is exempt for the UNIT, never for the victim): deferred; the promotable
    victim_2 is served, although victim_0 is the more urgent.
    MUTANTS: tu3_victim_exempt on all four; tu3_smoke_ignored on [smoky] and [own_cell_smoky]; tu3_burning_only on
    [smoky], [own_cell_smoky] and [own_cell_fire_adjacent]."""
    if kind == "smoky":
        unit, v0, burning, smoky = (10, 10), (10, 40), [(10, 45)], [(10, 40)]
    elif kind == "fire_adjacent":
        unit, v0, burning, smoky = (10, 10), (10, 40), [(10, 41)], []
    elif kind == "own_cell_smoky":
        unit, v0, burning, smoky = (10, 10), (10, 10), [(10, 15)], [(10, 10)]
    else:
        unit, v0, burning, smoky = (10, 10), (10, 10), [(10, 11)], []
    model = _scene(monkeypatch, {FF_A: unit}, {V0: v0, V2: (40, 12)}, burning=burning, smoky=smoky)
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    rec = spy.calls[0]["records"]
    assert rec[V0]["T"] < rec[V2]["T"]
    assert rec[V0]["c"] is None and rec[V0]["promotable"] is False
    assert rec[V2]["promotable"] is True
    assert log == [("assign", V2, FF_A, "initial", True)]


def test_tu3_iii_a_cell_the_fire_reaches_first_is_refused_and_the_slower_route_used(monkeypatch):
    """T-U3 (iii) (crafted T). The straight 4-hop route to victim_0 passes (10,12), clean NOW but with T = 2, so
    T*(10,11..13) = 2 and it cannot be entered at hop 2 or 3: the BFS takes the 8-hop detour that avoids the cell's
    4-neighbourhood. victim_2 (c 4) and victim_0 tie on T, so c decides: victim_2 is served. A static clean route
    gives victim_0 c 4, the tie falls to the index and victim_0 is served.
    MUTANT: tu3_static_route (the T* test removed)."""
    model = _scene(monkeypatch, {FF_A: (10, 10)}, {V0: (10, 14), V2: (14, 10)}, burning=[(45, 45)])
    _crafted_t(monkeypatch, {(10, 12): 2.0, (10, 14): 500.0, (14, 10): 500.0})
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    rec = spy.calls[0]["records"]
    assert rec[V0]["c"] == 8 and rec[V2]["c"] == 4
    assert spy.calls[0]["ordered"] == [V2, V0]
    assert log == [("assign", V2, FF_A, "initial", True)]


@pytest.mark.parametrize("kind", ["smoky", "fire_adjacent"])
def test_tu3_iv_the_units_own_unclean_cell_is_exempt(monkeypatch, kind):
    """T-U3 (iv). The free unit stands on an unclean cell (smoky, or 4-adjacent to fire): its own cell is hop 0 and
    exempt, so both victims keep their routes and the more urgent victim_2 is served.
    MUTANT: tu3_unit_not_exempt (the BFS refuses to start from an unclean unit cell: everyone deferred, index
    order)."""
    if kind == "smoky":
        burning, smoky = [FIRE], [(10, 10)]
    else:
        burning, smoky = [(9, 10)], []
    model = _scene(monkeypatch, {FF_A: (10, 10)}, {V0: (40, 40), V2: (12, 30)}, burning=burning, smoky=smoky)
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    rec = spy.calls[0]["records"]
    assert rec[V0]["promotable"] and rec[V2]["promotable"]
    assert rec[V2]["T"] < rec[V0]["T"]
    assert log == [("assign", V2, FF_A, "initial", True)]


# ================================================================================================ T-U4

@pytest.mark.parametrize(
    "n_waiting,n_free,any_burning,expected",
    [(2, 1, True, True), (5, 1, True, True), (1, 1, True, False), (0, 1, True, False), (2, 0, True, False),
     (2, 2, True, False), (3, 2, True, False), (2, 1, False, False)],
    ids=["W2F1fire", "W5F1fire", "W1F1fire", "W0F1fire", "W2F0fire", "W2F2fire", "W3F2fire", "W2F1nofire"])
def test_tu4_qualifies_table(n_waiting, n_free, any_burning, expected):
    """T-U4 (pure). qualifies is exactly: one free unit, two or more waiting, a fire.
    MUTANTS: tu4_nfree (|F| = 1 relaxed to |F| >= 1), tu4_nwait (|W| >= 2 relaxed to >= 1), tu4_qualifies_true
    (qualifies always True), tu11_no_burning (the burning condition removed), tu4_never (qualifies always False -
    the positive rows); 15.3's forms tu4_w_gt_f (|F| = 1 replaced by |W| > |F| >= 1) and tu4_gate_removed."""
    assert ud.qualifies(n_waiting, n_free, any_burning) is expected


@pytest.mark.parametrize("case", ["F2_W2", "F2_W3", "F1_W1"])
def test_tu4_not_qualifying_kicks_run_today_verbatim(monkeypatch, case):
    """T-U4 (model). |W| <= |F| (2 free, 2 waiting; 1 free, 1 waiting) and |F| = 2 with |W| = 3: no ordering, no
    [UrgencyTriage] line, and stdout and the assign log equal the same state's with the switch off - although
    U1's order (victim_2 most urgent) would differ from the index order.
    MUTANTS: tu4_nfree on [F2_W2] and [F2_W3]; tu4_nwait on [F1_W1]; tu4_gate_removed (15.3) on [F1_W1]."""
    if case == "F2_W2":
        units, victims = {FF_A: (30, 20), FF_B: (35, 25)}, {V0: (10, 12), V2: (40, 30)}
    elif case == "F2_W3":
        units, victims = {FF_A: (30, 20), FF_B: (35, 25)}, {V0: (10, 12), V1: (12, 14), V2: (40, 30)}
    else:
        units, victims = {FF_A: (30, 20)}, {V2: (40, 30)}
    model = _scene(monkeypatch, units, victims)
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    assert spy.calls == [] and "[UrgencyTriage]" not in out
    off = _scene(monkeypatch, units, victims, urgency=0)
    out_off, log_off = _kick(off)
    assert (out, log) == (out_off, log_off)
    assert log and all(e[0] == "assign" and e[3] == "initial" for e in log)


# ================================================================================================ T-U5

def test_tu5_deferred_is_not_abandoned(monkeypatch):
    """T-U5. Kick 1 (one free unit A): victim_0 and victim_3 stand on smoky cells (deferred), victim_2 is promotable
    and served; victim_0 stays waiting and needy - no unassign, no release, no mark_unreachable, no state change -
    and the [UrgencyTriage] line marks her D. Kick 2 (B freed by an outside event): only deferred victims wait, so
    the index order holds and victim_0, who now comes first, is served.
    MUTANTS: tu5_drop_deferred (deferred victims dropped from the iteration); tu5_reason (the reason changed from
    "initial" in _urgency_dispatch_pass - an empty pool then writes the deferred victim off)."""
    model = _scene(monkeypatch, {FF_A: (12, 12), FF_B: (40, 5)},
                   {V0: (5, 40), V2: (20, 15), V3: (45, 45), V4: (45, 5)}, smoky=[(5, 40), (45, 45)])
    assert assign(model, V4, FF_B)
    cmds = _CommandSpy(monkeypatch, model)
    out1, log1 = _kick(model)
    assert log1 == [("assign", V2, FF_A, "initial", True)]
    ((unit, tokens, served),) = _triage(out1)
    assert unit == FF_A and served == V2
    marks = {v: pd for v, _t, _c, pd in tokens}
    assert marks == {V2: "P", V0: "D", V3: "D"}
    assert [c[0] for c in cmds.commands] == ["assign"] and cmds.releases == []
    for vid in (V0, V3):
        state = model.managed_victims[vid]
        assert victim(model, vid).status == "confirmed" and state.status == "confirmed"
        assert not state.unreachable and not state.cancelled and binders(model, vid) == []
    assert _waiting_today(model) == [V0, V3]
    # an outside event frees B (its victim carried out); the next kick serves victim_0, who now comes first
    _rescue_done(model, V4, FF_B)
    n_cmd = len(cmds.commands)
    out2, log2 = _kick(model)
    assert log2 == [("assign", V0, FF_B, "initial", True)]
    ((_, tokens2, served2),) = _triage(out2)
    assert served2 == V0 and [(t[0], t[3]) for t in tokens2] == [(V0, "D"), (V3, "D")]
    assert [c[0] for c in cmds.commands[n_cmd:]] == ["assign"] and cmds.releases == []
    assert binders(model, V2) == [FF_A] and binders(model, V0) == [FF_B]


# ================================================================================================ T-U6

def test_tu6_flight_changes_t_c_and_the_order_and_a_bound_victim_stays_bound(monkeypatch):
    """T-U6. Two kicks with the loop body recording instead of binding: victim_2 flees from (40,30) to (45,5)
    between them, so her T and c - read at her LIVE cell - change and the order flips. Then real kicks: A binds
    victim_0; victim_0 moves beside the fire (her T drops below everyone's) and B is freed by an outside event;
    the next kick sends B to a waiting victim and victim_0 stays bound to A. Each victim's detection is recorded
    at her first cell, so a view that reads the detection position instead of the live cell is caught.
    MUTANTS: tu6_spawn_cell (the view reads the victim's spawn cell instead of her live cell); tu6_detection_cell
    (15.3's form: T cached at the detection cell)."""
    model = _scene(monkeypatch, {FF_A: (30, 20), FF_B: (40, 5)},
                   {V0: (10, 12), V2: (40, 30), V3: (2, 2), V4: (44, 5)})
    for vid, cell in ((V0, (10, 12)), (V2, (40, 30)), (V3, (2, 2)), (V4, (44, 5))):
        model.victim_runtime_model.update_detection(victim_id=vid, position=(float(cell[0]), float(cell[1])),
                                                    timestamp=100.0, source="uav_proximity", confidence=0.75)
    assert assign(model, V4, FF_B)
    spy = _OrderSpy(monkeypatch)
    visited = []
    real_body = model._dispatch_firefighter_to_victim
    monkeypatch.setattr(model, "_dispatch_firefighter_to_victim",
                        lambda vid, marker, reason: visited.append(vid) or False)
    _kick(model)
    first = spy.calls[-1]
    model.grid.move_agent(victim(model, V2), (45, 5))
    _kick(model)
    second = spy.calls[-1]
    assert first["records"][V2]["cell"] == (40, 30) and second["records"][V2]["cell"] == (45, 5)
    assert first["records"][V2]["T"] != second["records"][V2]["T"]
    assert first["records"][V2]["c"] != second["records"][V2]["c"]
    assert first["ordered"][0] == V2 and second["ordered"][0] == V0
    assert visited[:3] == first["ordered"] and visited[3:] == second["ordered"]
    # real binds: A takes victim_0; her T then drops; a freed B never pulls her from A
    monkeypatch.setattr(model, "_dispatch_firefighter_to_victim", real_body)
    cmds = _CommandSpy(monkeypatch, model)
    out3, log3 = _kick(model)
    assert log3 == [("assign", V0, FF_A, "initial", True)]
    t_before = spy.calls[-1]["records"][V0]["T"]
    model.grid.move_agent(victim(model, V0), (25, 13))
    _rescue_done(model, V4, FF_B)
    n_cmd = len(cmds.commands)
    out4, log4 = _kick(model)
    t_now = arrival_time(50, 50, [FIRE], cfv.wind_vector_from_direction("north"), FrontPriorityParams())[25, 13]
    assert t_now < t_before and t_now < min(r["T"] for r in spy.calls[-1]["records"].values())
    assert V0 not in spy.calls[-1]["ordered"]
    assert [c[0] for c in cmds.commands[n_cmd:]] == ["assign"] and cmds.releases == []
    assert binders(model, V0) == [FF_A] and bound_to(model, FF_A) == V0
    assert bound_to(model, FF_B) in (V2, V3)


# ================================================================================================ T-U7

def test_tu7_equal_t_falls_to_the_smaller_c(monkeypatch):
    """T-U7 (model). victim_0 (20,20) and victim_2 (30,20) stand symmetric about the fire's downwind axis: equal T
    to the last bit. The unit at (32,22) is 4 from victim_2 and 14 from victim_0, so victim_2 - the higher index -
    is served.
    MUTANT: tu7_no_c (c dropped from the key)."""
    model = _scene(monkeypatch, {FF_A: (32, 22)}, {V0: (20, 20), V2: (30, 20)})
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    rec = spy.calls[0]["records"]
    assert rec[V0]["T"] == rec[V2]["T"] and rec[V0]["promotable"] and rec[V2]["promotable"]
    assert rec[V2]["c"] < rec[V0]["c"]
    assert log == [("assign", V2, FF_A, "initial", True)]


@pytest.mark.parametrize("group", ["promotable", "deferred"])
def test_tu7_then_the_integer_index_victim_10_after_victim_2(monkeypatch, group):
    """T-U7 (pure). Equal T and equal c (promotable), or both deferred: the INTEGER index decides - victim_2 before
    victim_10, whatever order they arrive in (a string comparison puts victim_10 first).
    MUTANT: tu7_string_ids."""
    v10, v2 = "victim_10", "victim_2"
    if group == "promotable":
        _crafted_t(monkeypatch, {(10, 15): 100.0, (15, 10): 100.0})
        smoky = []
    else:
        smoky = [(10, 15), (15, 10)]
    waiting = [(v10, (10, 15)), (v2, (15, 10))]
    ordered, rec = ud.urgency_order(waiting, (10, 10), [(45, 45)], smoky, (0.0, 1.0), 50, 50)
    assert ordered == [v2, v10]
    assert rec[v2]["promotable"] is rec[v10]["promotable"] is (group == "promotable")
    assert ud.victim_index(v10) == 10 and ud.victim_index(v2) == 2


# ================================================================================================ T-U8

def test_tu8_t_is_fae_arrival_time_with_the_published_defaults(monkeypatch):
    """T-U8. Every T in U1's records equals FAE.arrival_time(HEIGHT, WIDTH, the burning set, the wind, the
    FrontPriorityParams() defaults) at the victim's cell, with the burning set stored as numpy.bool_.
    MUTANTS: tu8_fp_params (the parameters read through front_priority_params()); tu8_numpy_identity (burning read
    by identity with True: the numpy.bool_ fire is invisible and the kick does not qualify). The square board
    cannot see a height / width swap - test_tu8_non_square_grid_indexes_x_by_the_first_extent does."""
    fire = [FIRE, (26, 10), (25, 11)]
    model = _scene(monkeypatch, {FF_A: (22, 11)}, {V0: (28, 10), V2: (25, 27), V3: (40, 40)}, burning=fire,
                   wind="east")
    monkeypatch.setattr(cfv, "SEARCHER_FP_U10_KMH", 40.0, raising=False)
    spy = _OrderSpy(monkeypatch)
    _kick(model)
    grid = arrival_time(50, 50, fire, cfv.wind_vector_from_direction("east"), FrontPriorityParams())
    assert len(spy.calls) == 1 and len(spy.calls[0]["records"]) == 3
    for vid, rec in spy.calls[0]["records"].items():
        assert rec["T"] == float(grid[rec["cell"]]), vid
    assert all(type(a.burning) is np.bool_ for a in fire_agents(model) if a.burning)


def test_tu8_numpy_bool_burning_is_read_by_truthiness(monkeypatch):
    """T-U8. The simulator stores burning as numpy.bool_ after its first tick: the kick qualifies and orders exactly
    as with Python bools.
    MUTANT: tu8_numpy_identity (fire_board_sets reads burning by identity with True)."""
    runs = []
    for numpy_bool in (True, False):
        model = _scene(monkeypatch, {FF_A: (30, 20)}, {V0: (10, 12), V2: (40, 30)}, numpy_bool=numpy_bool)
        assert type(fire_at_cell(model, FIRE).burning) is (np.bool_ if numpy_bool else bool)
        out, log = _kick(model)
        runs.append((out, log))
    assert runs[0] == runs[1]
    assert runs[0][1] == [("assign", V2, FF_A, "initial", True)] and "[UrgencyTriage]" in runs[0][0]


def test_tu8_searcher_fp_knob_moves_the_searcher_estimate_but_not_u1(monkeypatch):
    """T-U8. With SEARCHER_FP_U10_KMH = 40 set on cfv (the --set route), the searcher's front_priority_params()
    changes and would REORDER these two victims (victim_2 first), but U1's records and order are those of the
    published defaults (victim_0 first, as with the knob unset).
    MUTANT: tu8_fp_params."""
    units, victims = {FF_A: (22, 11)}, {V0: (27, 10), V2: (25, 27)}
    base = _scene(monkeypatch, units, victims)
    spy = _OrderSpy(monkeypatch)
    _kick(base)
    monkeypatch.setattr(cfv, "SEARCHER_FP_U10_KMH", 40.0, raising=False)
    knob = _scene(monkeypatch, units, victims)
    monkeypatch.setattr(cfv, "SEARCHER_FP_U10_KMH", 40.0, raising=False)
    out, log = _kick(knob)
    assert front_priority_params().u10_kmh == 40.0 and front_priority_params() != FrontPriorityParams()
    searcher_order, _ = ud.urgency_order(
        [(V0, (27, 10)), (V2, (25, 27))], (22, 11), [FIRE], [], cfv.wind_vector_from_direction("north"), 50, 50,
        params=front_priority_params())
    assert searcher_order == [V2, V0]
    assert spy.calls[0]["ordered"] == spy.calls[1]["ordered"] == [V0, V2]
    assert {v: r["T"] for v, r in spy.calls[0]["records"].items()} == {v: r["T"] for v, r in
                                                                       spy.calls[1]["records"].items()}
    assert log == [("assign", V0, FF_A, "initial", True)]


def test_tu8_non_square_grid_indexes_x_by_the_first_extent(monkeypatch):
    """T-U8. On a NON-SQUARE 30 x 50 board (x_size = HEIGHT = grid.width = 30, y_size = 50) T is
    arrival_time(30, 50, ...) indexed [x, y]; a fire at (20, 40) and a victim at (25, 40) exist only with x as the
    first extent. The model's view passes grid.width as x_size and grid.height as y_size.
    MUTANTS: tu8_xy_swap; tu8_view_swap (the view swaps grid.width and grid.height)."""
    fire = [(20, 40)]
    wind = cfv.wind_vector_from_direction("east")
    ordered, rec = ud.urgency_order([(V0, (25, 40)), (V2, (5, 5))], (10, 40), fire, [], wind, 30, 50)
    grid = arrival_time(30, 50, fire, wind, FrontPriorityParams())
    assert grid.shape == (30, 50)
    assert rec[V0]["T"] == float(grid[25, 40]) and np.isfinite(rec[V0]["T"])
    assert rec[V2]["T"] == float(grid[5, 5])
    model = _scene(monkeypatch, {FF_A: (10, 10)}, {V0: (12, 12), V2: (14, 14)})
    monkeypatch.setattr(model, "grid", types.SimpleNamespace(width=30, height=50))
    view = model._urgency_dispatch_view([(V0, victim(model, V0)), (V2, victim(model, V2))], ff(model, FF_A))
    assert (view["x_size"], view["y_size"]) == (30, 50)


# ================================================================================================ T-U9

_UNIT_STATES = ("free", "free", "en_route", "exiting", "exiting_unassigned", "rescue_completed",
                "rescue_completed_unassigned", "route_blocked", "route_blocked_unassigned", "off_grid", "dead")


def _random_state(monkeypatch, rng):
    cells = rng.sample([(x, y) for x in range(2, 48, 3) for y in range(2, 48, 3)], 8)
    detected = rng.sample(VICTIMS, rng.randint(2, 5))
    burning = [] if rng.random() < 0.1 else rng.sample([(x, y) for x in range(50) for y in range(50)
                                                          if (x, y) not in cells], rng.randint(1, 5))
    smoky = rng.sample([(x, y) for x in range(50) for y in range(50) if (x, y) not in cells], rng.randint(0, 3))
    model = _scene(monkeypatch, dict(zip(UNITS, cells[:3])), dict(zip(VICTIMS, cells[3:])), burning=burning,
                   smoky=smoky, detected=detected, wind=rng.choice(["north", "south", "east", "west"]))
    for uid in UNITS:
        state = rng.choice(_UNIT_STATES)
        unit = ff(model, uid)
        target = rng.choice(VICTIMS)
        if state in ("en_route", "exiting", "rescue_completed"):
            assign(model, target, uid)
            unit.exiting = state == "exiting"
            unit.rescue_completed = state == "rescue_completed"
        elif state in ("exiting_unassigned", "rescue_completed_unassigned"):
            unit.exiting = state == "exiting_unassigned"
            unit.rescue_completed = state == "rescue_completed_unassigned"
            unit.status = "en_route"
        elif state == "route_blocked":
            assign(model, target, uid)
            unit.status = "route_blocked"
        elif state == "route_blocked_unassigned":
            unit.status = "route_blocked"
        elif state == "off_grid":
            model.grid.remove_agent(unit)
            unit.status, unit.off_grid, unit.absent_until_step = "off_grid", True, 105
        elif state == "dead":
            unit.dead, unit.status = True, "dead"
    return model


def test_tu9_the_judged_unit_is_the_unit_sent(monkeypatch):
    """T-U9. 300 random states (unit status mixes: free, en_route, exiting, rescue_completed, route_blocked - each
    also with the flags set on an unassigned unit - off-grid and dead; random detections, fire, smoke and wind).
    U1 orders a kick IFF exactly one unit passes _firefighter_available_for_dispatch, two or more victims wait by
    today's predicates and something burns; when it does, it judges that unit's cell, and the kick binds exactly
    that unit to the first victim of the order.
    MUTANT: tu9_loose_f (F built without the exiting / rescue_completed filters)."""
    rng = random.Random(15309)
    spy = _OrderSpy(monkeypatch)
    qualifying = 0
    for trial in range(300):
        model = _random_state(monkeypatch, rng)
        free, waiting, fire = _free_today(model), _waiting_today(model), _any_burning(model)
        expect = len(free) == 1 and len(waiting) >= 2 and fire
        n_calls = len(spy.calls)
        out, log = _kick(model)
        made = spy.calls[n_calls:]
        assert len(made) == (1 if expect else 0), (trial, free, waiting, fire)
        if not expect:
            continue
        qualifying += 1
        (call,) = made
        unit = ff(model, free[0])
        assert call["unit_cell"] == (int(unit.pos[0]), int(unit.pos[1])), trial
        assert sorted(call["ordered"]) == sorted(waiting), trial
        assert log == [("assign", call["ordered"][0], free[0], "initial", True)], (trial, log)
        assert _triage(out)[0][0] == free[0]
    assert qualifying >= 40, qualifying


# ================================================================================================ T-U10 / T-U11

def test_tu10_all_deferred_keep_todays_index_order(monkeypatch):
    """T-U10. victim_0 (upwind-adjacent, T 36.8) and victim_2 (downwind-adjacent, T 2.4) both stand on unclean
    cells: both deferred, and the index order holds although T orders them the other way.
    MUTANT: tu10_deferred_by_t (deferred victims keyed by T)."""
    model = _scene(monkeypatch, {FF_A: (40, 40)}, {V0: (25, 9), V2: (25, 11)})
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    rec = spy.calls[0]["records"]
    assert not rec[V0]["promotable"] and not rec[V2]["promotable"] and rec[V2]["T"] < rec[V0]["T"]
    assert spy.calls[0]["ordered"] == [V0, V2]
    assert log == [("assign", V0, FF_A, "initial", True)]
    ((_, tokens, served),) = _triage(out)
    assert served == V0 and [t[3] for t in tokens] == ["D", "D"]


def test_tu11_nothing_burns_runs_verbatim(monkeypatch):
    """T-U11. Nothing burns: no ordering, no line, and today's index order (victim_0) although victim_2 is far
    closer.
    MUTANTS: tu11_no_burning (the burning condition removed: T = inf, ordered by c); tu4_qualifies_true."""
    model = _scene(monkeypatch, {FF_A: (32, 32)}, {V0: (5, 5), V2: (30, 30)}, burning=[])
    spy = _OrderSpy(monkeypatch)
    out, log = _kick(model)
    assert spy.calls == [] and "[UrgencyTriage]" not in out
    assert log == [("assign", V0, FF_A, "initial", True)]


# ================================================================================================ T-CAS / T-DRN

def _cas_scene(monkeypatch):
    """A (bound to victim_0, who stands on a smoky cell - U1 would DEFER her) and B free; victim_2 waits and is
    promotable for B. U1 applied to {victim_0, victim_2} with B would send B to victim_2."""
    model = _scene(monkeypatch, {FF_A: (20, 20), FF_B: (30, 15)}, {V0: (25, 40), V2: (35, 20)}, smoky=[(25, 40)])
    assert assign(model, V0, FF_A)
    view = model._urgency_dispatch_view([(V0, victim(model, V0)), (V2, victim(model, V2))], ff(model, FF_B))
    would, _ = ud.urgency_order(view["waiting"], view["unit_cell"], view["burning"], view["smoky"], view["wind"],
                                view["x_size"], view["y_size"])
    assert would == [V2, V0]
    return model


@pytest.mark.parametrize("incident", ["casualty", "route_blocked"])
def test_tcas_replacements_still_serve_their_own_victim(monkeypatch, incident):
    """T-CAS. With U1 on and victim_2 waiting (U1 would prefer her), the casualty replacement (A dies on a burning
    cell; the real casualty sweep) and the route_blocked replacement (A raises; the real handler) send the free
    unit B to A's own victim_0; victim_2 keeps waiting; nothing is written off; no [UrgencyTriage] line.
    MUTANT: tcas_tail (U1's pass run at the incident handler's tail for casualty / route_blocked incidents)."""
    model = _cas_scene(monkeypatch)
    spy = _OrderSpy(monkeypatch)
    cmds = _CommandSpy(monkeypatch, model)
    out = io.StringIO()
    with redirect_stdout(out):
        if incident == "casualty":
            burn(model, [(20, 20)])
            model._check_fire_casualties()
            assert ff(model, FF_A).dead
        else:
            ff(model, FF_A).status = "route_blocked"
            model._on_firefighter_route_blocked(ff(model, FF_A))
    assert bound_to(model, FF_B) == V0 and binders(model, V0) == [FF_B]
    assert _waiting_today(model) == [V2]
    assert not any(c[0] == "mark_unreachable" for c in cmds.commands)
    assert all(str(victim(model, v).status) != "unreachable" for v in (V0, V2))
    assert "[Rescue Failed]" not in out.getvalue() and "[UrgencyTriage]" not in out.getvalue()
    assert spy.calls == []
    assign_cmds = [c for c in cmds.commands if c[0] == "assign"]
    expected = "replacement_after_casualty" if incident == "casualty" else "replacement_after_blocked"
    assert assign_cmds == [("assign", V0, FF_B, expected)]


def test_tdrn_detection_drain_order_is_unchanged(monkeypatch):
    """T-DRN. Two victim_confirmed incidents drained in queue order (victim_0 first) with U1 on: victim_0 gets the
    unit nearest to both (A), victim_2 the other (B) - although victim_2 is the more urgent. No ordering, no line.
    MUTANT: tdrn_sort (the drain sorted by urgency)."""
    model = _scene(monkeypatch, {FF_A: (20, 20), FF_B: (45, 45)}, {V0: (20, 25), V2: (25, 20)})
    grid = arrival_time(50, 50, [FIRE], cfv.wind_vector_from_direction("north"), FrontPriorityParams())
    assert grid[25, 20] < grid[20, 25]
    spy = _OrderSpy(monkeypatch)
    for vid in (V0, V2):
        model._enqueue_rescue_incident({"type": "victim_confirmed", "victim_id": vid, "reason": "initial"})
    n = len(model._physical_rescue_command_audit)
    out = io.StringIO()
    with redirect_stdout(out):
        model._process_rescue_incidents()
    log = [(e["action"], e["victim_id"], e["firefighter_id"]) for e in model._physical_rescue_command_audit[n:]]
    assert log == [("assign", V0, FF_A), ("assign", V2, FF_B)]
    assert spy.calls == [] and "[UrgencyTriage]" not in out.getvalue()


# ================================================================================================ T-FLIP-U

def _flip_events(model, rng, outside):
    """Outside events between kicks: fire changes, victim flight, detections, o1 (route_blocked raise + the handler's
    unassign), o2 (a repeated raise: latched, still bound), recoveries, o3 (death) and o4 (rescue: every binder of
    the victim released, the carrier back). Every unbind and latch here is the TEST's, recorded in `outside`."""
    for _ in range(rng.randint(0, 2)):
        burn(model, [(rng.randrange(50), rng.randrange(50))])
    lit = [tuple(a.pos) for a in fire_agents(model) if a.burning]
    if len(lit) > 1 and rng.random() < 0.4:
        unburn(model, [rng.choice(lit)])
    if rng.random() < 0.3:
        smoke(model, [(rng.randrange(50), rng.randrange(50))])
    for vid in VICTIMS:
        marker = victim(model, vid)
        if marker.pos is None or str(marker.status) in ("rescued", "dead") or rng.random() > 0.3:
            continue
        dx, dy = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        cell = (min(49, max(0, marker.pos[0] + dx)), min(49, max(0, marker.pos[1] + dy)))
        model.grid.move_agent(marker, cell)
    for vid in VICTIMS:
        state = model.managed_victims[vid]
        if not state.confirmed and rng.random() < 0.2:
            state.confirmed, state.status = True, "confirmed"
            victim(model, vid).status = "confirmed"
    for uid in UNITS:
        unit = ff(model, uid)
        if unit.dead:
            continue
        roll = rng.random()
        latched = str(unit.status) == "route_blocked"
        if latched and roll < 0.5:                                    # recovery (the route reopens)
            unit.status = "en_route" if bound_to(model, uid) is not None else "available"
        elif bound_to(model, uid) is not None and not latched:
            if roll < 0.15:                                           # o1
                _, vid = _unbind(model, uid, "test_o1_route_blocked")
                unit.status = "route_blocked"
                outside.append(("o1", uid, vid))
            elif roll < 0.27:                                         # o2: latched, still bound
                unit.status = "route_blocked"
                outside.append(("o2", uid, bound_to(model, uid)))
            elif roll < 0.4:                                          # o4: rescued; every binder released
                vid = bound_to(model, uid)
                for other in binders(model, vid):
                    if other != uid:
                        _unbind(model, other, "test_o4_release", reset=False)
                        if str(ff(model, other).status) != "route_blocked":
                            ff(model, other).status = "available"
                        outside.append(("o4", other, vid))
                _rescue_done(model, vid, uid)
                outside.append(("o4", uid, vid))
            elif roll < 0.43 and sum(not ff(model, u).dead for u in UNITS) > 1:   # o3
                _, vid = _unbind(model, uid, "test_o3_death")
                unit.dead, unit.status = True, "dead"
                outside.append(("o3", uid, vid))


def _flip_sequence(monkeypatch, seed, urgency, spy, n_kicks=10):
    rng = random.Random(seed)
    cells = rng.sample([(x, y) for x in range(3, 47, 2) for y in range(3, 47, 2)], 8)
    model = _scene(monkeypatch, dict(zip(UNITS, cells[:3])), dict(zip(VICTIMS, cells[3:])),
                   burning=[(rng.randrange(50), rng.randrange(50)) for _ in range(3)],
                   detected=rng.sample(VICTIMS, 3), wind=rng.choice(["north", "south", "east", "west"]),
                   urgency=urgency)
    binds = []                                   # (t, unit, victim): every bind, in order (setup and kicks)
    for uid, vid in zip(UNITS[:2], rng.sample([v for v in VICTIMS if model.managed_victims[v].confirmed], 2)):
        assign(model, vid, uid)
        binds.append((len(binds), uid, vid))
    cmds = _CommandSpy(monkeypatch, model)
    outside, qualifying, kicks, clock = [], 0, 0, [len(binds)]
    for k in range(n_kicks):
        events = []
        _flip_events(model, rng, events)
        for kind, uid, vid in events:
            outside.append((clock[0], kind, uid, vid))
            clock[0] += 1
        free, waiting = _free_today(model), _waiting_today(model)
        before = {u: bound_to(model, u) for u in UNITS}
        n_cmd, n_rel, n_calls = len(cmds.commands), len(cmds.releases), len(spy.calls)
        out, log = _kick(model)
        kicks += 1
        qualifying += len(spy.calls) - n_calls
        issued = cmds.commands[n_cmd:]
        assert [c[0] for c in issued] == ["assign"] * len(issued), (seed, k, issued)
        assert len(cmds.releases) == n_rel, (seed, k)
        assert sum(1 for e in log if e[0] == "assign" and e[4]) == min(len(free), len(waiting)), (seed, k, log)
        for uid, vid in before.items():
            if vid is not None:
                assert bound_to(model, uid) == vid, (seed, k, uid, vid)
        for action, vid, uid, _reason, success in log:
            if action == "assign" and success:
                binds.append((clock[0], uid, vid))
                clock[0] += 1

    def has_outside(unit, lo, hi):
        return any(e[2] == unit and lo < e[0] < hi for e in outside)

    # RETURNS. On a victim, A .. X .. A: an outside event on the intermediate binder X between X's bind and A's
    # return. On a unit, v .. w .. v: an outside event on the unit while it served w.
    for key_index, other_index in ((2, 1), (1, 2)):
        groups = {}
        for b in binds:
            groups.setdefault(b[key_index], []).append(b)
        for seq in groups.values():
            for i in range(len(seq)):
                for j in range(i + 2, len(seq)):
                    if seq[j][other_index] != seq[i][other_index]:
                        continue
                    for mid in seq[i + 1:j]:
                        holder = mid[1] if key_index == 2 else seq[i][1]
                        assert has_outside(holder, mid[0], seq[j][0]), (seed, seq, outside)
    return kicks, qualifying


def test_tflip_u_never_unbinds_and_binds_as_many_as_the_index_loop(monkeypatch):
    """T-FLIP-U. 500 seeded random sequences (15.3) of 10 kicks each, with fire changes, victim flight, detections
    and the outside events o1 / o3 / o4 and recoveries between kicks. At every kick: U1 issues only assigns (no unassign,
    no mark_unreachable, no release); every unit bound before the kick is still bound to the same victim after it;
    the kick binds exactly min(|F|, |W|) victims - the index-order loop's count, which the same sequences with the
    switch off confirm; a binder RETURN needs an outside event on the intermediate binder.
    MUTANT: tflip_rerank (a re-rank in _urgency_dispatch_pass that releases a bound unit when the most urgent
    waiting victim is promotable - pre-emption)."""
    spy = _OrderSpy(monkeypatch)
    totals = {0: [0, 0], 1: [0, 0]}
    for urgency in (1, 0):
        for seed in range(500):
            kicks, qualifying = _flip_sequence(monkeypatch, 7100 + seed, urgency, spy)
            totals[urgency][0] += kicks
            totals[urgency][1] += qualifying
    assert totals[0][1] == 0
    assert totals[1][1] >= 800, totals


# ================================================================================================ T-SRC

_FORBIDDEN_CALLS = {
    "apply_physical_rescue_command", "execute_physical_command", "apply_physical_pairing_decision",
    "_release_other_claimants", "_handle_rescue_incident", "_enqueue_rescue_incident", "_process_rescue_incidents",
    "select_rescue_assignment", "PhysicalRescueCommand", "_execute_physical_rescue_via_executor",
    "_update_unreachable_victims", "_record_rescue_event", "setattr", "delattr",
}
_FORBIDDEN_WORDS = ("unassign", "mark_unreachable", "release", "unreachable", "cancel")
_U1_METHODS = ("_urgency_waiting", "_urgency_dispatch_view", "_urgency_dispatch_pass")


def _func_tree(fn):
    return ast.parse(textwrap.dedent(inspect.getsource(fn)))


def _called_names(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            out.append(func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", ""))
    return out


def _strings_without_docstrings(tree):
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def test_tsrc_u1_code_has_no_path_to_unbind_release_or_write_off():
    """T-SRC (AST). urgency_dispatch.py and the WM U1 methods call nothing that unbinds, releases, writes off or
    issues a command (the executor, the sink, select, the incident queue, setattr), assign to no attribute, and
    name no such action; the one dispatch call is the unchanged loop body _dispatch_firefighter_to_victim(vid,
    marker, "initial"), in _urgency_dispatch_pass; the kick's switch branch only delegates to the pass.
    MUTANTS: tsrc_unassign (an unassign command added to the pass); tu5_reason."""
    trees = {"urgency_dispatch": ast.parse(inspect.getsource(ud))}
    trees.update({name: _func_tree(getattr(wf.WildFireModel, name)) for name in _U1_METHODS})
    dispatch_calls = []
    for name, tree in trees.items():
        called = set(_called_names(tree))
        assert not (called & _FORBIDDEN_CALLS), (name, called & _FORBIDDEN_CALLS)
        for text in _strings_without_docstrings(tree):
            assert not any(word in text.lower() for word in _FORBIDDEN_WORDS), (name, text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    # no state change on any object: no attribute store, no store into anything but a local name
                    assert not isinstance(target, ast.Attribute), (name, ast.dump(target))
                    if isinstance(target, ast.Subscript):
                        assert isinstance(target.value, ast.Name), (name, ast.dump(target))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "_dispatch_firefighter_to_victim":
                dispatch_calls.append((name, node))
    assert len(dispatch_calls) == 1 and dispatch_calls[0][0] == "_urgency_dispatch_pass"
    args = dispatch_calls[0][1].args
    assert len(args) == 3 and isinstance(args[2], ast.Constant) and args[2].value == "initial"
    kick = _func_tree(wf.WildFireModel._try_dispatch_unresolved_confirmed_victims)
    branches = [n for n in ast.walk(kick) if isinstance(n, ast.If) and isinstance(n.test, ast.Call)
                and isinstance(n.test.func, ast.Attribute) and n.test.func.attr == "dispatch_urgency"]
    assert len(branches) == 1
    body = branches[0].body
    assert len(body) == 2 and isinstance(body[1], ast.Return) and body[1].value is None
    assert isinstance(body[0], ast.Expr) and _called_names(body[0]) == ["_urgency_dispatch_pass"]


# ================================================================================================ T-INFO

class _TrapError(AssertionError):
    pass


def _trap_class(base, allowed):
    def __getattribute__(self, name):
        if name == "__class__" or name in allowed:
            return object.__getattribute__(self, name)
        raise _TrapError(f"an undetected victim's {base.__name__}.{name} was read inside U1")

    return type("Trap" + base.__name__, (base,), {"__getattribute__": __getattribute__})


class _ReadTrap:
    """Inside the context, every UNDETECTED victim's marker raises on any attribute access and her managed state
    allows only `confirmed` (the classes are swapped in place, so every route to the object is covered)."""

    def __init__(self, model, hits):
        self.model, self.hits, self.swapped = model, hits, []

    def __enter__(self):
        for vid, state in self.model.managed_victims.items():
            if bool(state.confirmed):
                continue
            marker = self.model.victim_marker_agents[vid]
            for obj, allowed in ((marker, ()), (state, ("confirmed",))):
                base = type(obj)
                obj.__class__ = _trap_class(base, allowed)
                self.swapped.append((obj, base))
        return self

    def __exit__(self, exc_type, exc, tb):
        for obj, base in self.swapped:
            obj.__class__ = base
        if exc_type is not None and issubclass(exc_type, _TrapError):
            self.hits.append(str(exc))
        return False


def _arm_trap(monkeypatch, model, hits):
    """Arm the read trap around _urgency_dispatch_view and urgency_order only (after W is built)."""
    view = model._urgency_dispatch_view
    order = ud.urgency_order

    def trapped_view(*args, **kwargs):
        with _ReadTrap(model, hits):
            return view(*args, **kwargs)

    def trapped_order(*args, **kwargs):
        with _ReadTrap(model, hits):
            return order(*args, **kwargs)

    monkeypatch.setattr(model, "_urgency_dispatch_view", trapped_view)
    monkeypatch.setattr(ud, "urgency_order", trapped_order)


def test_tinfo_a_no_undetected_victim_is_read_by_the_view_or_the_order(monkeypatch):
    """T-INFO-a. Two detected victims wait, three undetected ones stand right beside the free unit and on its route.
    With the trap armed around _urgency_dispatch_view and urgency_order, the qualifying kick orders and binds
    without touching any undetected victim (the trap itself is shown to bite).
    MUTANTS: tinfo_read (the view reads the undetected victims' cells); tinfo_read_one (15.3's form: the view
    reads one undetected marker's cell); tinfo_snapshot (the view calls get_rescue_operational_snapshot)."""
    model = _scene(monkeypatch, {FF_A: (30, 20)},
                   {V0: (10, 12), V1: (40, 30), V2: (30, 21), V3: (31, 20), V4: (35, 25)}, detected=[V0, V1])
    hits = []
    with pytest.raises(_TrapError):
        with _ReadTrap(model, hits):
            victim(model, V2).pos
    assert hits and model.victim_marker_agents[V2].pos == (30, 21)
    hits.clear()
    _arm_trap(monkeypatch, model, hits)
    out, log = _kick(model)
    assert hits == []
    assert log == [("assign", V1, FF_A, "initial", True)]
    ((_, tokens, served),) = _triage(out)
    assert served == V1 and {t[0] for t in tokens} == {V0, V1}


def _info_sequence(monkeypatch, perturb):
    """Three kicks with fire changes and victim flight between them; returns (detected ids per kick, U1 orders,
    the assign log)."""
    model = _scene(monkeypatch, {FF_A: (30, 20), FF_B: (5, 45)},
                   {V0: (10, 12), V1: (5, 47), V2: (40, 30), V3: (0, 49), V4: (49, 49)}, detected=[V0, V1, V2])
    assert assign(model, V1, FF_B)
    if perturb:
        # every undetected victim's truth changes: cells (onto / beside the detected victims and the unit's
        # route), marker statuses, fates
        for vid, cell, status in ((V3, (40, 30), "unreachable"), (V4, (10, 12), "dead")):
            model.grid.move_agent(victim(model, vid), cell)
            victim(model, vid).status = status
            state = model.managed_victims[vid]
            state.status, state.rescued, state.cancelled, state.unreachable = "rescued", True, True, True
    spy = _OrderSpy(monkeypatch)
    detected, logs = [], []
    for k in range(3):
        if k == 1:
            _unbind(model, FF_B, "test_o1_route_blocked")      # B freed, victim_1 waits again
            burn(model, [(25, 11), (25, 12)])
            model.grid.move_agent(victim(model, V0), (11, 12))
        if k == 2:
            _rescue_done(model, bound_to(model, FF_A), FF_A)
            model.grid.move_agent(victim(model, V0), (12, 12))
        detected.append(tuple(sorted(v for v, s in model.managed_victims.items() if s.confirmed)))
        out, log = _kick(model)
        logs.extend(log)
    orders = [(c["unit_cell"], c["ordered"], {v: (r["T"], r["c"]) for v, r in c["records"].items()})
              for c in spy.calls]
    return detected, orders, logs


def test_tinfo_b_metamorphic_undetected_truth_changes_nothing(monkeypatch):
    """T-INFO-b (direct kicks). Perturbing every undetected victim's cell (onto the detected victims' cells),
    marker status and fate - with the detected-id sequence asserted identical first - leaves every U1 order (ids,
    T, c) and the assign log identical over three qualifying kicks with fire changes and flight between them.
    MUTANT: tinfo_read."""
    base = _info_sequence(monkeypatch, False)
    pert = _info_sequence(monkeypatch, True)
    assert base[0] == pert[0]
    assert len(base[1]) >= 2, "too few qualifying kicks - the test would be vacuous"
    assert base[1] == pert[1]
    assert base[2] == pert[2]


def _stub_searcher_cost(monkeypatch):
    monkeypatch.setattr(lag, "_never_seen_proximity_bonus", lambda runtime_models, cx, cy, obs_radius=8: 0.0)


def _info_real_run(monkeypatch, perturb, steps=4):
    """A short pinned REAL run, U1 on: victims 0, 1 and 4 detected at the start, 2 and 3 not; the other units dead
    and ff_unit_0 put in route_blocked, so step 1's revalidation (K2) makes a qualifying kick."""
    switches(monkeypatch, urgency=1)
    _stub_searcher_cost(monkeypatch)
    model = pinned_model(monkeypatch)
    for vid in (V0, V1, V4):
        state = model.managed_victims[vid]
        state.confirmed, state.status = True, "confirmed"
        victim(model, vid).status = "confirmed"
    for uid in (FF_B, FF_C):
        ff(model, uid).dead, ff(model, uid).status = True, "dead"
    ff(model, FF_A).status = "route_blocked"
    if perturb is not None:
        perturb(model)
    spy = _OrderSpy(monkeypatch)
    detected, fire = [], []
    with redirect_stdout(io.StringIO()):
        for _ in range(steps):
            model.step()
            detected.append(tuple(sorted(v for v, s in model.managed_victims.items() if s.confirmed)))
            fire.append(tuple(sorted(tuple(a.pos) for a in fire_agents(model) if a.burning)))
    orders = [(c["unit_cell"], c["ordered"]) for c in spy.calls]
    audit = [(e["action"], e["victim_id"], e["firefighter_id"], e["reason"], e["success"])
             for e in model._physical_rescue_command_audit]
    return detected, fire, orders, audit


def _perturb_cells(model):
    """Undetected victims moved onto the cells of the victims U1 ranks first and second (victim_4, victim_0)."""
    model.grid.move_agent(victim(model, V3), tuple(victim(model, V4).pos))
    model.grid.move_agent(victim(model, V2), tuple(victim(model, V0).pos))


def _perturb_fates(model):
    for vid in (V2, V3):
        state = model.managed_victims[vid]
        state.status, state.rescued, state.cancelled, state.unreachable = "rescued", True, True, True


def _perturb_markers(model):
    for vid in (V2, V3):
        victim(model, vid).status = "unreachable"


def test_tinfo_b_metamorphic_over_a_short_real_run(monkeypatch):
    """T-INFO-b (pre-registered form: a short pinned real-model run). Variants perturb the undetected victims'
    cells, fates and marker statuses; a variant is ACCEPTED only if its per-step detected-id sequence (asserted
    first) and burning sets equal the base run's. Every accepted variant leaves U1's orders and the assign /
    unassign log identical; the cells variant must be accepted, and U1 must have ordered a kick.
    MUTANT: tinfo_read."""
    base = _info_real_run(monkeypatch, None)
    assert base[2], "no qualifying kick in the real run - the test would be vacuous"
    assert base[2][0][1][0] == V4
    accepted = []
    for perturb in (_perturb_cells, _perturb_fates, _perturb_markers):
        variant = _info_real_run(monkeypatch, perturb)
        if variant[0] != base[0] or variant[1] != base[1]:
            continue
        accepted.append(perturb.__name__)
        assert variant[2] == base[2], perturb.__name__
        assert variant[3] == base[3], perturb.__name__
    assert "_perturb_cells" in accepted, accepted


def test_tinfo_c_source_reads_only_what_11_1_allows():
    """T-INFO-c (source). urgency_dispatch.py names no victim registry, snapshot, RNG or simulator constant. The view
    and the pass never touch victim_marker_agents / managed_victims and never call get_rescue_operational_snapshot
    or _any_victim_needs_rescue. The W builder calls only today's predicates (_victim_needs_rescue,
    _find_active_firefighter_for_victim) and reads only state.confirmed and marker.status. The existing exactly-2
    AST test of _any_victim_needs_rescue (tests/test_searcher_untuned.py) still passes.
    MUTANT: tinfo_snapshot."""
    module_tree = ast.parse(inspect.getsource(ud))
    names = set()
    for node in ast.walk(module_tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(a.name for a in node.names)
            names.add(getattr(node, "module", None) or "")
    code_text = " ".join(sorted(names) + _strings_without_docstrings(module_tree))
    for word in ("victim_marker_agents", "managed_victims", "get_rescue_operational_snapshot",
                 "_any_victim_needs_rescue", "random", "FIRE_SPREAD", "SEARCHER_FP", "front_priority_params",
                 "schedule", "cfv", "common_fixed_variables", "agents", "wildfire_model"):
        assert word not in code_text, word
    for name in ("_urgency_dispatch_view", "_urgency_dispatch_pass"):
        tree = _func_tree(getattr(wf.WildFireModel, name))
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        consts = set(_strings_without_docstrings(tree))
        for word in ("victim_marker_agents", "managed_victims", "get_rescue_operational_snapshot",
                     "_any_victim_needs_rescue", "_detected_victim_ids", "victim_runtime_model"):
            assert word not in attrs and word not in consts, (name, word)
    tree = _func_tree(wf.WildFireModel._urgency_waiting)
    self_calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                  and n.func.value.id == "self"}
    assert self_calls == {"_victim_needs_rescue", "_find_active_firefighter_for_victim"}
    read = {n.args[1].value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") ==
            "getattr" and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)}
    assert read == {"confirmed", "status"}
    import test_searcher_untuned

    test_searcher_untuned.test_the_release_relabel_passes_the_detected_only_rule()


# ================================================================================================ T-SW

ON = [1, True, 1.0, "1", " 1 "]
ON_IDS = ["int1", "True", "float1.0", "str1", "str1_padded"]
OFF = [0, 2, 0.5, "2.0", "on", "", None, "missing"]
OFF_IDS = ["int0", "int2", "float0.5", "str2.0", "str_on", "str_empty", "None", "missing"]


@pytest.mark.parametrize("value", ON, ids=ON_IDS)
def test_tsw_on_only_on_an_exact_one(monkeypatch, value):
    """T-SW. DISPATCH_URGENCY is ON for what denotes the integer 1, read at call time from the cfv module.
    MUTANTS: tsw_import_time (the switch read once at import, not at call time) on every case; tsw_raw_eq (a raw
    `== 1` instead of the exact-integer reading: the strings "1" and " 1 " stay off) on [str1] and [str1_padded].
    (The truthiness mutant is killed by the OFF table below.)"""
    switches(monkeypatch, urgency=0)
    assert agents.dispatch_urgency() is False
    monkeypatch.setattr(cfv, "DISPATCH_URGENCY", value, raising=False)
    assert agents.dispatch_urgency() is True


@pytest.mark.parametrize("value", OFF, ids=OFF_IDS)
def test_tsw_off_for_everything_else(monkeypatch, value):
    """T-SW. Everything else is OFF, a missing name included; read at call time.
    MUTANTS: tsw_truthy (truthiness instead of an exact 1: 2, 0.5, "2.0" and "on" turn it on); tsw_default_on (a
    missing name read as 1) on [missing]; tsw_import_time on every case."""
    monkeypatch.setattr(cfv, "DISPATCH_URGENCY", 1, raising=False)
    assert agents.dispatch_urgency() is True
    if value == "missing":
        monkeypatch.delattr(cfv, "DISPATCH_URGENCY", raising=False)
    else:
        monkeypatch.setattr(cfv, "DISPATCH_URGENCY", value, raising=False)
    assert agents.dispatch_urgency() is False


def _base_try_dispatch(self) -> None:
    """Re-dispatch confirmed victims that still need rescue when firefighters become available."""
    managed = getattr(self, "managed_victims", None)
    markers = getattr(self, "victim_marker_agents", None)
    if not isinstance(managed, dict) or not isinstance(markers, dict):
        return
    for vid, state in managed.items():
        marker = markers.get(vid)
        if not self._victim_needs_rescue(vid, marker):
            continue
        confirmed = bool(getattr(state, "confirmed", False) if state is not None else False)
        marker_status = (
            str(getattr(marker, "status", "") or "").strip().lower()
            if marker is not None
            else ""
        )
        if not confirmed and marker_status != "confirmed":
            continue
        if self._find_active_firefighter_for_victim(vid, marker):
            continue
        self._dispatch_firefighter_to_victim(vid, marker, "initial")


@pytest.mark.parametrize("value", [0, 2, "on", "missing"], ids=["0", "2", "on", "missing"])
def test_tsw_off_never_enters_the_urgency_code(monkeypatch, value):
    """T-SW. With the switch OFF at a state that WOULD qualify: _urgency_waiting, _urgency_dispatch_view,
    _urgency_dispatch_pass, qualifies and urgency_order are never entered (each raises if called), nothing is
    printed, the bind is today's (victim_0) and the kick adds exactly the model attributes the base loop adds.
    MUTANTS: tsw_gate (the gate in _try_dispatch replaced by True); tsw_truthy on [2] and [on]."""
    units, victims = {FF_A: (30, 20)}, {V0: (10, 12), V2: (40, 30)}

    def boom(*args, **kwargs):
        raise AssertionError("urgency code entered with DISPATCH_URGENCY off")

    def make(base_loop):
        model = _scene(monkeypatch, units, victims, urgency=value)
        if value == "missing":
            monkeypatch.delattr(cfv, "DISPATCH_URGENCY", raising=False)
        if base_loop:
            model._try_dispatch_unresolved_confirmed_victims = types.MethodType(_base_try_dispatch, model)
        return model

    reference = make(True)
    keys_ref = set(vars(reference))
    out_ref, log_ref = _kick(reference)
    added_ref = set(vars(reference)) - keys_ref
    model = make(False)
    for name in _U1_METHODS:
        monkeypatch.setattr(model, name, boom)
    monkeypatch.setattr(ud, "urgency_order", boom)
    monkeypatch.setattr(ud, "qualifies", boom)
    keys = set(vars(model))
    out, log = _kick(model)
    assert out == out_ref and "[UrgencyTriage]" not in out
    assert log == log_ref == [("assign", V0, FF_A, "initial", True)]
    assert set(vars(model)) - keys == added_ref


# ================================================================================================ T-ID

def _id_run(monkeypatch, mode, steps=24):
    """A short pinned REAL run. mode: "absent" (DISPATCH_URGENCY deleted), "zero", or "base" (the kick replaced by
    the base 27744a28 loop). victim_0 and victim_1 are detected at the start (waiting); a free unit is put in
    route_blocked before steps 3 and 12, so the revalidation (K2) kicks inside model.step."""
    switches(monkeypatch, urgency=0)
    if mode == "absent":
        monkeypatch.delattr(cfv, "DISPATCH_URGENCY", raising=False)
    _stub_searcher_cost(monkeypatch)
    model = pinned_model(monkeypatch)
    if mode == "base":
        model._try_dispatch_unresolved_confirmed_victims = types.MethodType(_base_try_dispatch, model)
    kicks = []
    inner = model._try_dispatch_unresolved_confirmed_victims

    def counted():
        kicks.append(model.evaluation_timesteps_counter)
        return inner()

    model._try_dispatch_unresolved_confirmed_victims = counted
    for vid in (V0, V1):
        state = model.managed_victims[vid]
        state.confirmed, state.status = True, "confirmed"
        victim(model, vid).status = "confirmed"
    out = io.StringIO()
    with redirect_stdout(out):
        for step in range(steps):
            if step in (3, 12):
                for uid in UNITS:
                    unit = ff(model, uid)
                    if not unit.dead and not unit.assigned and unit.pos is not None and unit.status == "available":
                        unit.status = "route_blocked"
                        break
            model.step()
    audit = [(e["action"], e["victim_id"], e["firefighter_id"], e["reason"], e["success"])
             for e in model._physical_rescue_command_audit]
    return out.getvalue(), audit, kicks


def test_tid_off_is_identical_absent_zero_and_base(monkeypatch):
    """T-ID. A 24-step pinned real run with DISPATCH_URGENCY absent and at 0 gives identical stdout and assign /
    unassign log, both equal to the run whose kick is the base (27744a28) loop; the kicks did run (K2, forced), no
    [UrgencyTriage] line appears; the OFF path of the kick is the base loop's text with only the switch branch
    added.
    MUTANT: tid_print (an unconditional [UrgencyTriage] print in the kick)."""
    runs = {mode: _id_run(monkeypatch, mode) for mode in ("absent", "zero", "base")}
    assert len(runs["base"][2]) >= 2, runs["base"][2]
    assert "[UrgencyTriage]" not in runs["zero"][0] and "[UrgencyTriage]" not in runs["absent"][0]
    assert runs["absent"] == runs["zero"] == runs["base"]
    assert any(e[0] == "assign" and e[3] == "initial" for e in runs["zero"][1])
    current = textwrap.dedent(inspect.getsource(wf.WildFireModel._try_dispatch_unresolved_confirmed_victims))
    block = "    if agents.dispatch_urgency():\n        self._urgency_dispatch_pass(managed, markers)\n        return\n"
    assert current.count(block) == 1
    base_src = textwrap.dedent(inspect.getsource(_base_try_dispatch)).replace(
        "def _base_try_dispatch(", "def _try_dispatch_unresolved_confirmed_victims(")
    assert current.replace(block, "") == base_src
