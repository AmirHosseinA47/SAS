"""Feature 2: a victim steps away from approaching fire.

Drives the real WildFireModel, in the style of tests/test_firefighter_rescue_absence.py,
so every assertion holds against the production path rather than a stub: the
flee rule itself, the leash, the custody suppression that stops the victim and
its carrier fighting, the live re-target that stops a rescue completing without
contact, and the kill switch.
"""

from __future__ import annotations

import contextlib
import io
import os
import random

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel

V0 = "victim_0"
FF_A = "ff_unit_0"

_CONFIG_NAMES = (
    "VICTIM_FLEE_TRIGGER_DISTANCE",
    "VICTIM_FLEE_MAX_DISPLACEMENT",
    "SYSTEM_RANDOM",
)


@pytest.fixture(autouse=True)
def _restore_module_config():
    """apply_scenario_config mutates module globals; put them back for other tests."""
    saved = {}
    for mod in (cfv, wf):
        saved[mod] = {name: getattr(mod, name, None) for name in _CONFIG_NAMES}
    saved_agents_random = agents.random
    yield
    for mod, values in saved.items():
        for name, value in values.items():
            setattr(mod, name, value)
    agents.random = saved_agents_random


def _model(seed: int = 101, trigger: int = 3, leash: int = 6) -> WildFireModel:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        VICTIM_FLEE_TRIGGER_DISTANCE=trigger,
        VICTIM_FLEE_MAX_DISPLACEMENT=leash,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        model = WildFireModel()
    model.debug_log = False
    return model


def _clear_fire(model: WildFireModel) -> None:
    """Quiet the whole map so a test controls exactly which cells burn."""
    for agent in model.schedule.agents:
        if type(agent) is agents.Fire:
            agent.burning = False
            agent.next_burning_state = False


def _ignite(model: WildFireModel, cell: tuple[int, int]) -> agents.Fire:
    for agent in model.grid.get_cell_list_contents([cell]):
        if type(agent) is agents.Fire:
            agent.burning = True
            agent.has_burned = True
            return agent
    raise AssertionError("no Fire agent at %s" % (cell,))


def _victim(model: WildFireModel, vid: str = V0) -> agents.Victim:
    return model.victim_marker_agents[vid]


def _cell(agent) -> tuple[int, int]:
    return (int(agent.pos[0]), int(agent.pos[1]))


def _manhattan(a, b) -> int:
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


def _relocate(model: WildFireModel, victim: agents.Victim, cell: tuple[int, int]) -> None:
    """Move a victim for a test AND re-base both anchors.

    Guard 2 measures the leash against `leash_anchor`, not `spawn_cell`. A test
    that relocated a victim without re-basing the anchor left every candidate
    cell outside the leash, so the victim held and the test passed for the wrong
    reason.
    """
    model.grid.move_agent(victim, cell)
    victim.spawn_cell = cell
    victim.leash_anchor = cell
    victim.leash_reanchors = 0


# ----------------------------------------------------------------------
# the flee rule
# ----------------------------------------------------------------------


def test_victim_holds_when_fire_is_beyond_the_trigger() -> None:
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] - 10, start[1]))

    victim.advance()

    assert _cell(victim) == start
    assert getattr(model, "_victim_flee_log", []) == []


def test_victim_steps_away_when_fire_is_within_the_trigger() -> None:
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    fire = (start[0] + 1, start[1])
    _ignite(model, fire)

    victim.advance()

    after = _cell(victim)
    assert after != start
    assert _manhattan(after, fire) > _manhattan(start, fire)


def test_victim_never_steps_onto_a_burning_cell() -> None:
    """Every neighbour but one burns; the victim must take the one that does not."""
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    safe = (start[0], start[1] - 1)
    for offset in ((1, 0), (-1, 0), (0, 1)):
        _ignite(model, (start[0] + offset[0], start[1] + offset[1]))

    victim.advance()

    assert _cell(victim) == safe


def test_victim_holds_when_every_neighbour_burns() -> None:
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    for offset in agents.ORTHOGONAL_OFFSETS:
        _ignite(model, (start[0] + offset[0], start[1] + offset[1]))

    victim.advance()

    assert _cell(victim) == start


def test_victim_escapes_a_cell_that_ignites_under_it() -> None:
    """The scheduler order makes this possible and section 1.2.4 relies on it.

    Victims advance after fire commits and before `_check_fire_casualties`, so
    stepping off one's own burning cell is a survivable move.
    """
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, start)

    victim.advance()

    assert _cell(victim) != start
    entry = model._victim_flee_log[-1]
    assert entry["fire_dist_before"] == 0
    assert entry["escaped_own_cell"] is True

    # and the move is what saves it: the casualty sweep now finds it elsewhere
    model._check_fire_casualties()
    assert victim.status != "dead"


def test_victim_on_a_burning_cell_still_dies_when_boxed_in() -> None:
    """Escaping is not immortality - a surrounded victim has nowhere to go."""
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, start)
    for offset in agents.ORTHOGONAL_OFFSETS:
        _ignite(model, (start[0] + offset[0], start[1] + offset[1]))

    victim.advance()
    assert _cell(victim) == start

    model._check_fire_casualties()
    assert victim.status == "dead"


def test_leash_bounds_displacement_from_the_spawn_cell() -> None:
    model = _model(leash=2)
    victim = _victim(model)
    spawn = victim.spawn_cell
    _clear_fire(model)
    _ignite(model, (spawn[0] + 1, spawn[1]))

    for _ in range(12):
        victim.advance()

    assert _manhattan(_cell(victim), spawn) <= 2


def test_spawn_cell_is_recorded_and_matches_the_placed_cell() -> None:
    model = _model()
    for vid, marker in model.victim_marker_agents.items():
        assert marker.spawn_cell == _cell(marker), vid


def test_movement_is_deterministic() -> None:
    """Same state, same move - the rule draws from no RNG and breaks ties totally."""
    destinations = set()
    for _ in range(3):
        model = _model()
        victim = _victim(model)
        _clear_fire(model)
        start = _cell(victim)
        _ignite(model, start)
        victim.advance()
        destinations.add(_cell(victim))
    assert len(destinations) == 1


def test_flee_draws_nothing_from_the_shared_rng() -> None:
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))

    state_before = cfv.SYSTEM_RANDOM.getstate()
    victim.advance()

    assert _cell(victim) != start
    assert cfv.SYSTEM_RANDOM.getstate() == state_before


# ----------------------------------------------------------------------
# guards
# ----------------------------------------------------------------------


def test_dead_victim_does_not_move() -> None:
    """A dead victim keeps its grid cell and scheduler slot, so advance() runs."""
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, start)
    model._check_fire_casualties()
    assert victim.status == "dead"
    assert victim.unique_id in model.schedule._agents

    victim.advance()

    assert _cell(victim) == start


def test_unreachable_victim_still_flees() -> None:
    """The move set matches the casualty sweep's: still alive means still flees."""
    model = _model()
    victim = _victim(model)
    victim.status = "unreachable"
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))

    victim.advance()

    assert _cell(victim) != start


# ----------------------------------------------------------------------
# custody: the victim and its carrier must never fight over the position
# ----------------------------------------------------------------------


def test_carried_victim_does_not_move_itself() -> None:
    model = _model()
    victim = _victim(model)
    firefighter = model.firefighter_marker_agents[FF_A]
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))
    firefighter.rescued_victim = victim
    firefighter.exiting = True

    victim.advance()

    assert _cell(victim) == start


def test_colocated_firefighter_stops_the_victim_before_exiting_is_set() -> None:
    """The one-step hole on the arrival step: exiting is still False here."""
    model = _model()
    victim = _victim(model)
    firefighter = model.firefighter_marker_agents[FF_A]
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))
    firefighter.rescued_victim = victim
    firefighter.exiting = False
    model.grid.move_agent(firefighter, start)

    victim.advance()

    assert _cell(victim) == start


def test_offgrid_firefighter_does_not_hold_a_victim() -> None:
    """Feature 1 units have pos None; that must not read as custody."""
    model = _model()
    victim = _victim(model)
    firefighter = model.firefighter_marker_agents[FF_A]
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))
    firefighter.rescued_victim = victim
    firefighter.exiting = False
    model.grid.remove_agent(firefighter)
    assert firefighter.pos is None

    victim.advance()

    assert _cell(victim) != start


def test_a_firefighter_bound_to_another_victim_does_not_hold_this_one() -> None:
    model = _model()
    victim = _victim(model)
    other = model.victim_marker_agents["victim_1"]
    firefighter = model.firefighter_marker_agents[FF_A]
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))
    firefighter.rescued_victim = other
    firefighter.exiting = True
    model.grid.move_agent(firefighter, start)

    victim.advance()

    assert _cell(victim) != start


# ----------------------------------------------------------------------
# the stale target_pos, and the fabricated rescue it caused
# ----------------------------------------------------------------------


def test_target_pos_follows_a_moving_victim() -> None:
    model = _model()
    victim = _victim(model)
    firefighter = model.firefighter_marker_agents[FF_A]
    firefighter.assigned = True
    firefighter.exiting = False
    firefighter.rescued_victim = victim
    firefighter.target_pos = _cell(victim)

    model.grid.move_agent(victim, (20, 20))
    firefighter._refresh_target_from_victim()

    assert firefighter.target_pos == (20, 20)


def test_firefighter_never_starts_exiting_without_contact() -> None:
    """The failure mode the re-target exists to prevent, asserted directly.

    Without the refresh the unit reaches the cell recorded at assign, finds
    `pos == target_pos` against empty ground, flips to exiting, and teleports
    the victim to itself on the first carry step.
    """
    model = _model()
    victim = _victim(model)
    firefighter = model.firefighter_marker_agents[FF_A]
    _clear_fire(model)

    start = (20, 20)
    _relocate(model, victim, start)
    model.grid.move_agent(firefighter, (20, 18))
    firefighter.assigned = True
    firefighter.exiting = False
    firefighter.rescued_victim = victim
    firefighter.target_pos = start

    # fire on the far side of the victim, close enough to push it one cell
    _ignite(model, (20, 22))

    for _ in range(6):
        victim.advance()
        firefighter.advance()
        if firefighter.exiting:
            break

    assert firefighter.exiting, "firefighter never reached the victim"
    assert _cell(firefighter) == _cell(victim), "exiting began without contact"


def test_terminal_victim_is_not_chased_to_a_new_cell() -> None:
    model = _model()
    victim = _victim(model)
    firefighter = model.firefighter_marker_agents[FF_A]
    firefighter.assigned = True
    firefighter.exiting = False
    firefighter.rescued_victim = victim
    firefighter.target_pos = _cell(victim)
    original = firefighter.target_pos

    victim.status = "dead"
    model.grid.move_agent(victim, (20, 20))
    firefighter._refresh_target_from_victim()

    assert firefighter.target_pos == original


# ----------------------------------------------------------------------
# kill switch
# ----------------------------------------------------------------------


def test_kill_switch_makes_advance_a_no_op() -> None:
    model = _model(trigger=0)
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, start)

    victim.advance()

    assert _cell(victim) == start
    assert getattr(model, "_victim_flee_log", []) == []
    assert model.managed_victims[V0].last_known_position == pytest.approx(
        (40.0, 25.0)
    )


def test_kill_switch_disables_the_retarget() -> None:
    model = _model(trigger=0)
    victim = _victim(model)
    firefighter = model.firefighter_marker_agents[FF_A]
    firefighter.assigned = True
    firefighter.exiting = False
    firefighter.rescued_victim = victim
    firefighter.target_pos = _cell(victim)
    original = firefighter.target_pos

    model.grid.move_agent(victim, (20, 20))
    firefighter._refresh_target_from_victim()

    assert firefighter.target_pos == original


# ----------------------------------------------------------------------
# model-side bookkeeping
# ----------------------------------------------------------------------


def test_flee_log_and_last_known_position_track_the_move() -> None:
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))

    victim.advance()

    entry = model._victim_flee_log[-1]
    after = _cell(victim)
    assert entry["victim_id"] == V0
    assert entry["from"] == list(start)
    assert entry["to"] == list(after)
    assert entry["spawn"] == list(victim.spawn_cell)
    assert entry["displacement"] == _manhattan(after, victim.spawn_cell)
    assert entry["fire_dist_after"] > entry["fire_dist_before"]
    assert model.managed_victims[V0].last_known_position == pytest.approx(
        (float(after[0]), float(after[1]))
    )
    assert model.victim_flee_moves_total == 1


def test_dead_firefighter_does_not_hold_a_victim() -> None:
    """A casualty keeps its binding until an unassign clears it; a corpse must
    not pin a live victim in the path of the fire."""
    model = _model()
    victim = _victim(model)
    firefighter = model.firefighter_marker_agents[FF_A]
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))
    firefighter.rescued_victim = victim
    firefighter.exiting = True
    firefighter.dead = True

    victim.advance()

    assert _cell(victim) != start


# ----------------------------------------------------------------------
# dead-end avoidance (guard 1)
# ----------------------------------------------------------------------


def test_victim_prefers_a_cell_that_still_has_an_exit() -> None:
    """Greedy distance alone walks into pockets; the lookahead must outrank it.

    GEOMETRY NOTE, verified exhaustively on a small grid: a cell is a dead end
    only when its non-origin neighbours all burn or are out of bounds, and on a
    grid whose corners still have two in-bounds neighbours that forces at least
    one burning neighbour. So a dead end ALWAYS sits at fire distance 1, it can
    never be strictly further from fire than an open cell, and the guard is
    therefore a TIE-BREAK among distance-1 cells. Combined with the strict
    improvement rule that makes it live exactly when the victim is standing IN
    fire and choosing an escape cell - which is the enclosure-shaped case.

    Layout: the victim burns, the sealed pocket (21, 20) is FIRST in the fixed
    offset order so it wins the tie-break without the guard, and (19, 20) is
    open. The guard must flip the choice.
    """
    model = _model(leash=20)
    victim = _victim(model)
    _clear_fire(model)
    start = (20, 20)
    _relocate(model, victim, start)

    _ignite(model, start)                    # the victim is standing in fire
    for pocket_wall in ((22, 20), (21, 19), (21, 21)):
        _ignite(model, pocket_wall)          # seals (21, 20)

    fire = victim._burning_cells()
    pocket, open_cell = (21, 20), (19, 20)
    # the tie is real: both escape cells are the same distance from fire
    assert victim._min_fire_distance(pocket, fire) == victim._min_fire_distance(
        open_cell, fire
    )
    # and without the guard the pocket would win, being offset order 0
    assert agents.ORTHOGONAL_OFFSETS[0] == (1, 0)
    assert not victim._cell_has_onward_exit(pocket, start, fire)
    assert victim._cell_has_onward_exit(open_cell, start, fire)

    victim.advance()

    assert _cell(victim) != pocket, "victim walked into the sealed pocket"
    assert _cell(victim) == open_cell


def test_dead_end_preference_falls_back_when_every_option_is_a_pocket() -> None:
    """A preference, not a filter: with no exit anywhere the victim still moves."""
    model = _model(leash=20)
    victim = _victim(model)
    _clear_fire(model)
    start = (20, 20)
    _relocate(model, victim, start)

    # stand the victim in fire so any non-burning step is an improvement, and
    # seal every second-ring cell so no candidate has an onward exit
    _ignite(model, start)
    for ring2 in ((22, 20), (18, 20), (20, 22), (20, 18),
                  (21, 21), (21, 19), (19, 21), (19, 19)):
        _ignite(model, ring2)

    fire_cells = victim._burning_cells()
    for off in agents.ORTHOGONAL_OFFSETS:
        n = (start[0] + off[0], start[1] + off[1])
        assert not victim._cell_has_onward_exit(n, start, fire_cells)

    victim.advance()

    assert _cell(victim) != start, "victim froze instead of taking the least-bad step"


def test_onward_exit_excludes_the_cell_being_vacated() -> None:
    """Counting the vacated cell would make the guard vacuous."""
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = (20, 20)
    _relocate(model, victim, start)
    target = (19, 20)
    for wall in ((18, 20), (19, 19), (19, 21)):
        _ignite(model, wall)
    fire = victim._burning_cells()

    # the only non-burning neighbour of `target` is `start` itself
    assert victim._cell_has_onward_exit(target, from_cell=None, fire_cells=fire) is True
    assert victim._cell_has_onward_exit(target, from_cell=start, fire_cells=fire) is False


def test_grid_edge_counts_as_a_dead_end_side() -> None:
    """Out-of-bounds is not an exit, so a corner is correctly seen as sealed."""
    model = _model(leash=20)
    victim = _victim(model)
    _clear_fire(model)
    corner = (0, 0)
    model.grid.move_agent(victim, corner)
    fire = victim._burning_cells()
    # (0,0) has only (1,0) and (0,1) in bounds; block one and vacate the other
    _ignite(model, (1, 0))
    fire = victim._burning_cells()
    assert victim._cell_has_onward_exit(corner, from_cell=(0, 1), fire_cells=fire) is False


# ----------------------------------------------------------------------
# leash re-anchoring (guard 2)
# ----------------------------------------------------------------------


def test_leash_anchor_starts_at_spawn() -> None:
    model = _model()
    for vid, marker in model.victim_marker_agents.items():
        assert marker.leash_anchor == marker.spawn_cell, vid
        assert marker.leash_reanchors == 0, vid


def test_leash_reanchors_when_the_victim_reaches_safety() -> None:
    """Fire beyond the trigger is the victim equivalent of a safe standoff."""
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    # move the victim well away from spawn, then put fire out of trigger range
    model.grid.move_agent(victim, (start[0] - 4, start[1]))
    _ignite(model, (0, 0))

    assert victim.leash_anchor == start
    victim.advance()

    assert victim.leash_anchor == _cell(victim)
    assert victim.leash_anchor != start
    assert victim.leash_reanchors == 1
    # the true spawn is untouched, so displacement reporting still means spawn
    assert victim.spawn_cell == start


def test_leash_reanchors_when_nothing_is_burning() -> None:
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    model.grid.move_agent(victim, (start[0] - 3, start[1]))

    victim.advance()

    assert victim.leash_anchor == _cell(victim)
    assert victim.leash_reanchors == 1


def test_reanchoring_does_not_fire_while_the_victim_is_in_danger() -> None:
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    start = _cell(victim)
    _ignite(model, (start[0] + 1, start[1]))

    victim.advance()

    assert victim.leash_anchor == start, "anchor moved while fire was inside the trigger"
    assert victim.leash_reanchors == 0


def test_reanchor_is_idempotent_on_the_same_cell() -> None:
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    _ignite(model, (0, 0))

    for _ in range(5):
        victim.advance()

    assert victim.leash_reanchors == 0, "re-anchoring to the same cell counted as a change"


def _sweep_front(model, victim, steps, cadence=3):
    """Drive a wall of fire across the map from the spawn side, at FIRE_SPREAD_SPEED.

    Cadence matters. The real front advances about one cell per FIRE_SPREAD_SPEED
    (3) steps, so a victim moving one cell per step can break contact and reach
    safety. A wall advancing every step is three times too fast: the victim can
    never get outside the trigger radius, never re-anchors, and the test would
    measure the cadence rather than the guard.
    """
    origin = _cell(victim)
    for step in range(steps):
        wall_x = origin[0] - 2 + (step // cadence)
        _clear_fire(model)
        for y in range(50):
            try:
                _ignite(model, (wall_x, y))
            except AssertionError:
                pass
        victim.advance()


def test_renewable_leash_lets_a_victim_travel_beyond_the_raw_leash() -> None:
    """The whole point of guard 2: the budget renews on reaching safety.

    Spawn-anchored, this victim could never exceed displacement 6 no matter how
    long the front pushed. With re-anchoring it keeps ahead of a front arriving
    from the spawn side.
    """
    model = _model(leash=6)
    victim = _victim(model)
    _clear_fire(model)
    start = (25, 25)
    _relocate(model, victim, start)

    _sweep_front(model, victim, steps=36)

    displacement = _manhattan(_cell(victim), start)
    assert displacement > 6, (
        "victim never escaped the spawn-anchored diamond: displacement %d" % displacement
    )
    assert victim.leash_reanchors > 0
    assert victim.spawn_cell == start, "the true spawn must stay immutable"


def test_without_reanchoring_the_same_front_pins_the_victim_at_the_leash() -> None:
    """The control for the test above: guard 2 is what makes the difference.

    Identical scenario with re-anchoring disabled. The victim is held inside the
    Manhattan-6 diamond around its spawn while the front keeps coming, which is
    the failure the guard exists to remove.
    """
    model = _model(leash=6)
    victim = _victim(model)
    _clear_fire(model)
    start = (25, 25)
    _relocate(model, victim, start)
    victim._reanchor_leash = lambda: None  # disable guard 2 for this victim only

    _sweep_front(model, victim, steps=36)

    displacement = _manhattan(_cell(victim), start)
    assert displacement <= 6, (
        "spawn-anchored leash should cap displacement at 6, got %d" % displacement
    )
    assert victim.leash_reanchors == 0


def test_reanchor_touches_only_the_anchor() -> None:
    """The 93f23b7 reset hole must not be inherited: no other state is cleared."""
    model = _model()
    victim = _victim(model)
    _clear_fire(model)
    model.grid.move_agent(victim, (5, 5))
    victim.status = "confirmed"
    sentinel = object()
    victim._oscillation_memory = sentinel  # stand-in for future anti-oscillation state

    victim._reanchor_leash()

    assert victim.leash_anchor == (5, 5)
    assert victim.status == "confirmed"
    assert victim.spawn_cell == (40, 25)
    assert victim._oscillation_memory is sentinel
