"""untune round: the UNTUNED CURRENT SEARCH behind SEARCHER_UNTUNED - outputs/untune_part1.txt sections 2, 3,
6.2 and 11 (rulings). Two kinds of test:
  (a) SWITCH-EFFECT tests: each asserts the switch-on behaviour AND that switch-off is the shipped behaviour,
      so removing the switch's effect (or breaking the shipped path) fails a test;
  (b) PRIVILEGED-READ GUARDS: with the switch on, no searcher / mission-phase output depends on - or reads -
      the truth of a victim nobody has detected; with it off the same perturbation changes them (the guard
      bites).
Every test sets its own configuration through monkeypatch (no test depends on suite order)."""
from __future__ import annotations

import ast
import pathlib
import random

import pytest

import agents
import common_fixed_variables as cfv
import src_extension.adaptation.local_adaptation_generator as gen
from src_extension.execution.uav_executor import UAVExecutor
from src_extension.knowledge.mission_goal_model import MissionGoalModel
from src_extension.planning import local_uav_path_planner as planner

REPO = pathlib.Path(__file__).resolve().parents[1]
X_MIN, X_MAX, Y_MIN, Y_MAX = 0, 49, 0, 49


def _on(monkeypatch, value=1):
    monkeypatch.setattr(cfv, "SEARCHER_UNTUNED", value, raising=False)


def _ws(**overrides):
    ws = gen._default_wind_search_state()
    ws.update(overrides)
    return ws


# ============================================================================ the switch
def test_the_switch_ships_off():
    assert cfv.SEARCHER_UNTUNED == 0


@pytest.mark.parametrize("raw, on", [
    (0, False), (1, True), (2, False), (-1, False), ("1", True), (" 1 ", True), ("1.0", False),
    (0.5, False), (1.0, True), (True, True), (False, False), (None, False), ("on", False), ("", False),
])
def test_the_switch_is_on_only_on_an_exact_one(monkeypatch, raw, on):
    _on(monkeypatch, raw)
    assert agents.searcher_untuned() is on
    assert gen._searcher_untuned() is on


# ============================================================================ item 1 - T1 / T8
def test_t1_the_failure_test_reads_no_absolute_band(monkeypatch):
    tail_wide = list(range(10, 50, 2))  # 20 samples, span 38: not a camp anywhere
    monkeypatch.setattr(gen, "CORRIDOR_DIVERSITY_X_BAND", 0)  # an absurd band every x satisfies
    _on(monkeypatch, 0)
    assert gen._corridor_diversity_failure(_ws(recent_x_positions=tail_wide)) is True   # shipped reads it
    _on(monkeypatch, 1)
    assert gen._corridor_diversity_failure(_ws(recent_x_positions=tail_wide)) is False  # untuned does not


def test_t1_with_the_shipped_constants_the_result_is_unchanged_for_every_tail(monkeypatch):
    rng = random.Random(3)
    for _ in range(3000):
        lo = rng.randrange(0, 50)
        tail = [min(49, max(0, lo + rng.randrange(-3, 25))) for _ in range(rng.choice((19, 20, 25)))]
        for wind in ("west", "east", "north", "south"):
            ws = _ws(recent_x_positions=tail, last_wind_direction=wind)
            _on(monkeypatch, 0)
            off = gen._corridor_diversity_failure(ws)
            _on(monkeypatch, 1)
            assert gen._corridor_diversity_failure(ws) == off


def test_t8_the_strips_are_the_latch_thresholds():
    assert gen._x_strip_edges(X_MIN, X_MAX) == (12, 37)
    safe_lo, safe_hi = gen._coverage_safe_x_min(X_MIN), gen._coverage_safe_x_max(X_MAX)
    assert gen._west_strip_reached(_ws(recent_x_positions=[12]), safe_lo)
    assert not gen._west_strip_reached(_ws(recent_x_positions=[13]), safe_lo)
    assert gen._east_strip_reached(_ws(recent_x_positions=[37]), safe_hi)
    assert not gen._east_strip_reached(_ws(recent_x_positions=[36]), safe_hi)
    # = x_min + WIND_INTERIOR_MARGIN + COVERAGE_SWEEP_BAND_MARGIN (the derivation in the docstring)
    assert gen._x_strip_edges(X_MIN, X_MAX)[0] == X_MIN + gen.WIND_INTERIOR_MARGIN + gen.COVERAGE_SWEEP_BAND_MARGIN


# ============================================================================ item 1 - T2 / T4 / T5
def test_t2_the_camp_escape_is_symmetric_on_and_east_only_off(monkeypatch):
    west, east = _ws(recent_x_positions=[5] * 20), _ws(recent_x_positions=[45] * 20)
    for ws in (west, east):
        ws["last_wind_direction"] = "west"
    _on(monkeypatch, 1)
    assert gen._corridor_target_x_bounds_untuned(west, X_MIN, X_MAX) == (13, 47)   # floor 5 + 8
    assert gen._corridor_target_x_bounds_untuned(east, X_MIN, X_MAX) == (None, 37)  # cap 45 - 8
    assert gen._corridor_target_x_bounds_untuned(_ws(recent_x_positions=[25] * 20), X_MIN, X_MAX) == (None, 47)
    # shipped: the east cap only; a west camp (even under west wind, 66dc728c) gets no floor
    assert gen._corridor_target_x_cap(east, X_MIN, X_MAX, coverage_active=True) == 37
    assert gen._corridor_target_x_cap(west, X_MIN, X_MAX, coverage_active=True) == 47


def test_t5_no_west_half_cap_when_coverage_is_inactive(monkeypatch):
    monkeypatch.setattr(gen, "CORRIDOR_WEST_TARGET_X_MAX", 3)
    ws = _ws(recent_x_positions=[25] * 20)
    assert gen._corridor_target_x_cap(ws, X_MIN, X_MAX, coverage_active=False) == 3   # shipped reads it
    _on(monkeypatch, 1)
    assert gen._corridor_target_x_bounds_untuned(ws, X_MIN, X_MAX) == (None, 47)


def _escape(monkeypatch, *, ax, ay, recent_x, wind_vector=(-1.0, 0.0), wind="west"):
    """Run _pick_global_coverage_escape_target with the hybrid score stubbed to 0 and the finalize step stubbed
    out, recording every candidate scored. Coverage mode on (one undetected victim)."""
    seen = []

    def score(**kw):
        seen.append((kw["cx"], kw["cy"], kw["dist_agent"]))
        return 0.0

    monkeypatch.setattr(gen, "_score_hybrid_search_cell", score)
    monkeypatch.setattr(gen, "_finalize_coverage_target", lambda target, ws, **kw: target)
    ws = _ws(recent_x_positions=list(recent_x), unresolved_victim_count=1, last_wind_direction=wind)
    best = gen.LocalAdaptationSpaceGenerator()._pick_global_coverage_escape_target(
        runtime_models={}, uav_id="1", wind_vector=wind_vector, fire_cells=set(), smoke_cells=set(),
        fx=25.0, fy=25.0, ax=float(ax), ay=float(ay), x_min=X_MIN, x_max=X_MAX, y_min=Y_MIN, y_max=Y_MAX,
        simulation=None, wind_state=ws, step_index=50,
    )
    return best, seen


def test_t2_the_west_camp_floor_is_wired_into_the_escape_loop(monkeypatch):
    _on(monkeypatch, 0)
    _, seen_off = _escape(monkeypatch, ax=5, ay=25, recent_x=[5] * 20)
    _on(monkeypatch, 1)
    best_on, seen_on = _escape(monkeypatch, ax=5, ay=25, recent_x=[5] * 20)
    assert min(c[0] for c in seen_off) < 13          # shipped: no floor for a west camp
    assert seen_on and min(c[0] for c in seen_on) >= 13
    assert best_on[0] >= 13


def test_t15_the_escape_distance_relaxes_at_both_x_bounds(monkeypatch):
    for value, east_min in ((0, 20), (1, 8)):
        _on(monkeypatch, value)
        _, seen_west = _escape(monkeypatch, ax=3, ay=25, recent_x=[3, 20])
        _, seen_east = _escape(monkeypatch, ax=46, ay=25, recent_x=[29, 46])
        assert min(c[2] for c in seen_west) == 8      # the shipped west relaxation, both settings
        assert min(c[2] for c in seen_east) == east_min


# ============================================================================ item 1 - T6
def test_t6_the_absolute_fallbacks_are_not_read(monkeypatch):
    monkeypatch.setattr(gen, "COVERAGE_INTERIOR_X_MIN", 20)
    monkeypatch.setattr(gen, "COVERAGE_INTERIOR_X_MAX", 21)

    def final(x_min, x_max):
        ws = _ws(recent_x_positions=[40], unresolved_victim_count=1, last_wind_direction="west")
        return gen._finalize_coverage_target((40.0, 25.0), ws, x_min=x_min, x_max=x_max, y_min=Y_MIN,
                                             y_max=Y_MAX, ax=40.0, ay=25.0, fire_cells=set(),
                                             smoke_cells=set(), step_index=10)
    _on(monkeypatch, 0)
    assert final(None, None) != final(X_MIN, X_MAX)    # shipped falls back to 20 / 21
    _on(monkeypatch, 1)
    assert final(None, None) == final(X_MIN, X_MAX)    # grid-relative fallback


# ============================================================================ item 1 - T7 / F2
@pytest.mark.parametrize("wind, ax, off_x, on_x", [
    ("west", 25.0, 8.0, 8.0),     # downwind (west) first: unchanged
    ("east", 25.0, 8.0, 41.0),    # downwind is EAST: east first (shipped: west first)
    ("north", 30.0, 8.0, 41.0),   # across the wind: the NEARER strip (east)
    ("north", 20.0, 8.0, 8.0),    # nearer strip west
    ("south", 30.0, 8.0, 41.0),
])
def test_t7_the_sweep_order_is_wind_uniform(monkeypatch, wind, ax, off_x, on_x):
    for value, expected in ((0, off_x), (1, on_x)):
        _on(monkeypatch, value)
        ws = _ws(recent_x_positions=[int(ax)], unresolved_victim_count=1, last_wind_direction=wind)
        out = gen._finalize_coverage_target((float(ax), 25.0), ws, x_min=X_MIN, x_max=X_MAX, y_min=Y_MIN,
                                           y_max=Y_MAX, ax=ax, ay=25.0, fire_cells=set(), smoke_cells=set(),
                                           step_index=10)
        assert out[0] == expected, (wind, ax, value)


def test_t7_the_cross_wind_choice_is_latched(monkeypatch):
    _on(monkeypatch, 1)
    ws = _ws()
    assert gen._untuned_x_sweep_first(ws, "north", 30.0, 2, 47) == "east"
    assert gen._untuned_x_sweep_first(ws, "north", 5.0, 2, 47) == "east"      # latched
    assert gen._untuned_x_sweep_first(ws, "south", 5.0, 2, 47) == "west"      # a new wind decides anew
    assert gen._untuned_x_sweep_first(_ws(), "north", None, 2, 47) is None   # unknown position: no pull
    tie = _ws()
    assert gen._untuned_x_sweep_first(tie, "north", 24.5, 2, 47) is None     # exact tie: no compass default
    assert "untuned_x_sweep_first" not in tie                                # ... and nothing latched
    assert gen._untuned_x_sweep_first(tie, "north", 30.0, 2, 47) == "east"   # a real position decides
    assert gen._untuned_x_sweep_first(_ws(), "west", 40.0, 2, 47) == "west"
    assert gen._untuned_x_sweep_first(_ws(), "east", 5.0, 2, 47) == "east"


def _pull(untuned, wind, cx, ax, west_pending, east_pending):
    return gen._add_escape_x_pull(0.0, untuned=untuned, wind_label=wind, west_pending=west_pending,
                                  east_pending=east_pending, ax=float(ax), cx=cx, safe_x_min=2, safe_x_max=47,
                                  wind_state=_ws(last_wind_direction=wind))


def test_f2_the_unlatched_westward_escape_pull_is_removed(monkeypatch):
    # shipped, north wind: a west pull with BOTH strips done (no release) and no east pull at all
    assert _pull(False, "north", 10, 25, False, False) == pytest.approx(11.25)
    assert _pull(False, "north", 40, 25, True, True) == 0.0
    # untuned: latched (nothing once both strips are done) and symmetric
    assert _pull(True, "north", 10, 25, False, False) == 0.0
    assert _pull(True, "north", 40, 25, False, True) == pytest.approx(11.25)
    rng = random.Random(5)
    for _ in range(2000):
        cx, ax = rng.randrange(0, 50), rng.randrange(0, 50)
        wp, ep = rng.random() < 0.5, rng.random() < 0.5
        for wind in ("west", "east", "north", "south"):
            assert _pull(True, wind, cx, ax, wp, ep) == _pull(True, wind, 49 - cx, 49 - ax, ep, wp)
    # under west wind the untuned rule IS the shipped rule
    for _ in range(2000):
        cx, ax = rng.randrange(0, 50), rng.randrange(0, 50)
        wp, ep = rng.random() < 0.5, rng.random() < 0.5
        assert _pull(True, "west", cx, ax, wp, ep) == _pull(False, "west", cx, ax, wp, ep)


def test_t7_the_corridor_second_strip_pull_is_wind_uniform():
    assert gen._untuned_second_strip_pull("west", False, True) == "east"
    assert gen._untuned_second_strip_pull("east", True, False) == "west"
    assert gen._untuned_second_strip_pull("west", True, True) is None     # first strip still pending
    assert gen._untuned_second_strip_pull("east", False, False) is None
    assert gen._untuned_second_strip_pull(None, False, True) is None


# ============================================================================ item 1 - T9, T16, T17, T18
def test_t9_every_downwind_edge_blocks_four_cells(monkeypatch):
    def widths():
        out = {}
        for w in ("north", "south", "east", "west"):
            if w in ("north", "south"):
                cells = [y for y in range(50) if gen._downwind_edge_blocked(w, 25, y, X_MIN, X_MAX, Y_MIN, Y_MAX)]
            else:
                cells = [x for x in range(50) if gen._downwind_edge_blocked(w, x, 25, X_MIN, X_MAX, Y_MIN, Y_MAX)]
            out[w] = len(cells)
        return out
    _on(monkeypatch, 0)
    assert widths() == {"north": 4, "south": 3, "east": 5, "west": 4}
    _on(monkeypatch, 1)
    assert widths() == {"north": 4, "south": 4, "east": 4, "west": 4}


def _y_terms(untuned, commit, cy, ay):
    y_force_min = Y_MAX - gen.COVERAGE_Y_COMMIT_TARGET_MARGIN if commit == "north" else None
    y_force_max = Y_MIN + gen.COVERAGE_Y_COMMIT_TARGET_MARGIN if commit == "south" else None
    return gen._add_y_commit_terms(0.0, untuned=untuned, coverage_active=True, commit=commit, cy=cy,
                                   ay=float(ay), y_min=Y_MIN, y_max=Y_MAX, y_force_min=y_force_min,
                                   y_force_max=y_force_max)


def test_t16_the_y_commit_terms_mirror_north_and_south():
    asym = 0
    for cy in range(50):
        for ay in range(50):
            north, south = _y_terms(True, "north", cy, ay), _y_terms(True, "south", 49 - cy, 49 - ay)
            assert north == south, (cy, ay)
            asym += _y_terms(False, "north", cy, ay) != _y_terms(False, "south", 49 - cy, 49 - ay)
            assert _y_terms(True, "north", cy, ay) == _y_terms(False, "north", cy, ay)  # north unchanged
    assert asym > 0   # the shipped terms are not mirrored


def test_t17_the_south_interior_pick_mirrors_the_north_pick(monkeypatch):
    rng = random.Random(11)
    for _ in range(300):
        pts = [(float(rng.randrange(6, 44)), float(rng.randrange(6, 44))) for _ in range(rng.randrange(1, 8))]
        ax, ay = float(rng.randrange(6, 44)), float(rng.randrange(6, 44))
        north = max(pts, key=lambda p: (float(p[1]), abs(p[0] - ax) + abs(p[1] - ay)))  # the shipped north pick
        mirrored = [(p[0], 49.0 - p[1]) for p in pts]
        _on(monkeypatch, 1)
        south = gen._south_commit_interior_pick(mirrored, ax, 49.0 - ay)
        assert (south[1], abs(south[0] - ax) + abs(south[1] - (49.0 - ay))) == \
            (49.0 - north[1], abs(north[0] - ax) + abs(north[1] - ay))
    _on(monkeypatch, 0)
    pts = [(20.0, 10.0), (20.0, 30.0)]
    assert gen._south_commit_interior_pick(pts, 20.0, 35.0) == (20.0, 30.0)   # shipped: the shallowest
    _on(monkeypatch, 1)
    assert gen._south_commit_interior_pick(pts, 20.0, 35.0) == (20.0, 10.0)   # untuned: the deepest


def test_t18_the_edge_sweep_bonus_is_equal_at_both_x_edges(monkeypatch):
    ws = _ws(recent_x_positions=[24, 25], recent_y_positions=[25])
    def pair():
        return (gen._uncovered_region_bonus(3, 25, ws, X_MIN, X_MAX, Y_MIN, Y_MAX),
                gen._uncovered_region_bonus(46, 25, ws, X_MIN, X_MAX, Y_MIN, Y_MAX))
    _on(monkeypatch, 0)
    west, east = pair()
    assert west - east == pytest.approx(gen.COVERAGE_EDGE_SWEEP_BONUS * 0.15)
    _on(monkeypatch, 1)
    west, east = pair()
    assert west == east


# ============================================================================ item 1 - T3 (planner)
def test_t3_the_planner_flag_is_the_symmetric_strip_camp(monkeypatch):
    cases = {"west camp": [5] * 20, "east camp": [40] * 20, "x=37": [37] * 20, "interior": [25] * 20,
             "short": [45] * 19}
    expect_off = {"west camp": False, "east camp": True, "x=37": False, "interior": False, "short": False}
    expect_on = {"west camp": True, "east camp": True, "x=37": True, "interior": False, "short": False}
    for value, expect in ((0, expect_off), (1, expect_on)):
        _on(monkeypatch, value)
        for name, tail in cases.items():
            assert planner._planner_corridor_diversity_failure(tail, None) is expect[name], (value, name)


# ============================================================================ item 1 - dead helpers stay dead
DEAD = ("_south_edge_extra_penalty", "_east_edge_extra_penalty", "_opposite_quadrant_escape_target",
        "_corridor_front_distance_penalty", "_score_wind_aware_cell")


def test_the_compass_specific_dead_helpers_have_no_caller():
    files = [p for p in REPO.glob("*.py")] + list((REPO / "src_extension").rglob("*.py"))
    used = {name: [] for name in DEAD}
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
            if name in used:
                used[name].append(str(path))
    assert used == {name: [] for name in DEAD}


# ============================================================================ item 2 - a real model
def _model(monkeypatch, *, untuned, targeting=0, seed=9613):
    import wildfire_model as wf

    rng = random.Random(seed)
    for mod in (cfv, wf):
        monkeypatch.setattr(mod, "SYSTEM_RANDOM", rng, raising=False)
        # scenario A's team, pinned: other tests call apply_scenario_config (e.g. NUM_VICTIMS=3) and leave it set
        for name, value in (("NUM_AGENTS", 3), ("NUM_VICTIMS", 5), ("NUM_FIREFIGHTERS", 3)):
            monkeypatch.setattr(mod, name, value, raising=False)
    monkeypatch.setattr(agents, "random", rng, raising=False)
    monkeypatch.setattr(cfv, "SEARCHER_TARGETING", targeting, raising=False)
    monkeypatch.setattr(cfv, "VICTIM_SPAWN_MODE", 0, raising=False)
    _on(monkeypatch, untuned)
    return wf.WildFireModel()


def _detect(model, vid):
    marker = model.victim_marker_agents[vid]
    model.victim_runtime_model.update_detection(victim_id=vid, position=tuple(map(float, marker.pos)),
                                                timestamp=0.0, source="test", confidence=0.75)
    model.managed_victims[vid].confirmed = True
    marker.status = "confirmed"


def _kill(model, vid):
    """What _check_fire_casualties writes."""
    model.victim_marker_agents[vid].status = "dead"
    state = model.managed_victims[vid]
    state.status, state.rescued, state.cancelled, state.rescue_assigned, state.unreachable = (
        "dead", False, True, False, False)
    model.victim_runtime_model.victims.pop(vid, None)


def _rescue(model, vid):
    state = model.managed_victims[vid]
    state.rescued, state.status = True, "rescued"
    model.victim_marker_agents[vid].status = "rescued"


def _unreachable(model, vid):
    state = model.managed_victims[vid]
    state.cancelled, state.unreachable, state.status, state.rescue_assigned = True, True, "unreachable", False
    model.victim_marker_agents[vid].status = "unreachable"


def test_the_briefing_count_is_the_models_num_victims(monkeypatch):
    import wildfire_model as wf

    model = _model(monkeypatch, untuned=1)
    assert gen._victim_briefing_count(model) == wf.NUM_VICTIMS == len(model.managed_victims)
    monkeypatch.setattr(wf, "NUM_VICTIMS", 7)
    assert gen._victim_briefing_count(model) == 7    # the briefing, not the managed dict


def test_two_counts_two_questions(monkeypatch):
    model = _model(monkeypatch, untuned=1)
    v = sorted(model.managed_victims)
    n = len(v)
    find, mission, shipped = (gen._count_known_undetected_victims, gen._count_known_mission_unresolved,
                              gen._count_unresolved_victims)
    assert (find(model), mission(model), shipped(model)) == (n, n, n)
    _detect(model, v[0])                       # found, awaiting rescue: no more searching (case A)
    assert (find(model), mission(model), shipped(model)) == (n - 1, n, n)
    _kill(model, v[1])                         # dies UNSEEN: still to be found, mission not finished
    assert (find(model), mission(model), shipped(model)) == (n - 1, n, n - 1)
    _unreachable(model, v[0])                  # detected and unreachable: mission count keeps it
    assert (find(model), mission(model), shipped(model)) == (n - 1, n, n - 2)
    _detect(model, v[2])
    _rescue(model, v[2])                       # rescued: off both
    assert (find(model), mission(model), shipped(model)) == (n - 2, n - 1, n - 3)
    _detect(model, v[3])
    _kill(model, v[3])                         # detected, then dead: observed dead
    assert (find(model), mission(model), shipped(model)) == (n - 3, n - 2, n - 4)
    for vid in v:                              # every victim detected (case A): nothing left to FIND
        if not model.managed_victims[vid].confirmed and vid != v[1]:
            _detect(model, vid)
    assert find(model) == 1                    # only the unseen-dead victim (case B)
    assert mission(model) > 0


def _searcher_ws(model):
    ids = gen.resolve_victim_searcher_uav_ids(model)
    assert ids
    return {uid: gen._wind_search_state(model, uid) for uid in ids}


def test_the_searcher_path_uses_the_found_count(monkeypatch):
    for value in (0, 1):
        model = _model(monkeypatch, untuned=value)
        for vid in model.managed_victims:      # case A: all found, none resolved
            _detect(model, vid)
        for uid, ws in _searcher_ws(model).items():
            gen._update_unresolved_coverage_state(model, ws)
            assert ws["unresolved_victim_count"] == (0 if value else len(model.managed_victims))
            assert gen._coverage_mode_active(ws) is (not value)


def test_the_post_rescue_burst_needs_a_victim_still_to_find(monkeypatch):
    for value, armed in ((0, True), (1, False)):
        model = _model(monkeypatch, untuned=value)
        for vid in model.managed_victims:      # case A
            _detect(model, vid)
        model._activate_post_rescue_coverage_for_searchers()
        assert all((ws["post_rescue_coverage_steps_remaining"] > 0) is armed for ws in _searcher_ws(model).values())


def _mission(model, severity=0.9):
    model._estimate_fire_severity = lambda: severity
    ctx = model._build_mission_goal_runtime_context(0.0)
    goals = MissionGoalModel()
    goals.refresh_from_runtime(ctx)
    return ctx, goals


def test_the_mission_phase_uses_the_mission_count(monkeypatch):
    for value, phase in ((0, "exploration"), (1, "evacuation")):
        model = _model(monkeypatch, untuned=value)
        for vid in model.managed_victims:      # every victim dies unseen: the shipped count knows
            _kill(model, vid)
        ctx, goals = _mission(model)
        assert goals.mission_phase == phase
        assert ctx["alive_victims_remaining"] == (len(model.managed_victims) if value else 0)


def _outputs(model):
    out = {}
    for uid, ws in _searcher_ws(model).items():
        gen._update_unresolved_coverage_state(model, ws)
        out["count", uid] = ws["unresolved_victim_count"]
        ws["post_rescue_coverage_steps_remaining"] = 0
    model._activate_post_rescue_coverage_for_searchers()
    for uid, ws in _searcher_ws(model).items():
        out["burst", uid] = ws["post_rescue_coverage_steps_remaining"]
    ctx, goals = _mission(model)
    out["alive"], out["active"] = ctx["alive_victims_remaining"], ctx["active_rescues"]
    out["phase"], out["priorities"] = goals.mission_phase, dict(goals.goal_priorities)
    out["find"], out["mission"] = gen._count_known_undetected_victims(model), gen._count_known_mission_unresolved(model)
    return out


def _perturb_undetected_truth(model):
    """Change the TRUTH of every victim nobody has detected - their fate, status, flags and position. The
    detection record (confirmed, runtime records) is the team's own knowledge and is left alone."""
    undetected = [vid for vid, s in model.managed_victims.items() if not s.confirmed]
    assert len(undetected) >= 2
    _kill(model, undetected[0])
    state = model.managed_victims[undetected[1]]
    state.unreachable, state.cancelled, state.rescued, state.status = True, True, True, "rescued"
    for vid in undetected:
        marker = model.victim_marker_agents[vid]
        marker.status = "dead"
        model.grid.move_agent(marker, (1, 1))
        model.managed_victims[vid].dead = True
    return undetected


@pytest.mark.parametrize("targeting", [0, 2, 3])
def test_guard_no_searcher_or_mission_output_depends_on_undetected_truth(monkeypatch, targeting):
    for value in (1, 0):
        model = _model(monkeypatch, untuned=value, targeting=targeting)
        v = sorted(model.managed_victims)
        _detect(model, v[0])
        _detect(model, v[1])
        model.managed_victims[v[1]].rescue_assigned = True   # an active rescue (detected victims only)
        before = _outputs(model)
        _perturb_undetected_truth(model)
        after = _outputs(model)
        if value:
            assert after == before                         # untuned: blind to undetected truth
        else:
            assert after["count", next(iter(_searcher_ws(model)))] != before["count", next(iter(_searcher_ws(model)))]
            assert after["alive"] != before["alive"]       # shipped: the guard bites


class _Recorder:
    """A managed-victim state that records every attribute read."""

    def __init__(self, inner, log):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_log", log)

    def __getattr__(self, name):
        self._log.append(name)
        return getattr(self._inner, name)


class _NoTouch(dict):
    """victim_marker_agents that fails on any access (the markers are ground truth)."""

    def _no(self, *a, **k):
        raise AssertionError("victim_marker_agents read")

    __getitem__ = get = items = values = keys = __iter__ = __contains__ = _no


def test_guard_the_untuned_counts_read_only_the_detection_flag_of_an_undetected_victim(monkeypatch):
    model = _model(monkeypatch, untuned=1)
    v = sorted(model.managed_victims)
    _detect(model, v[0])
    log: list[str] = []
    for vid in v[1:]:
        model.managed_victims[vid] = _Recorder(model.managed_victims[vid], log)
    real_markers = model.victim_marker_agents
    model.victim_marker_agents = _NoTouch()
    for ws in _searcher_ws(model).values():
        gen._update_unresolved_coverage_state(model, ws)
    model._activate_post_rescue_coverage_for_searchers()
    gen._count_known_mission_unresolved(model)
    assert set(log) == {"confirmed"}
    # the guard bites: the privileged count touches the markers and the undetected victims' fate
    with pytest.raises(AssertionError, match="victim_marker_agents read"):
        gen._count_unresolved_victims(model)
    model.victim_marker_agents = real_markers


def test_guard_the_executor_handled_check_skips_the_marker(monkeypatch):
    class _State:
        status, dead, cancelled, rescued, unreachable, rescue_assigned, confirmed, assigned = (
            "candidate", False, False, False, False, False, False, False)

    model = type("M", (), {})()
    model.managed_victims = {"victim_0": _State()}
    model.victim_marker_agents = _NoTouch()
    executor = UAVExecutor.__new__(UAVExecutor)
    _on(monkeypatch, 0)
    with pytest.raises(AssertionError, match="victim_marker_agents read"):
        executor._victim_handled_for_uav_target("victim_0", {}, model)
    _on(monkeypatch, 1)
    assert executor._victim_handled_for_uav_target("victim_0", {}, model) is False


@pytest.mark.parametrize("targeting", [0, 2, 3])
def test_guard_stepping_a_model_never_calls_the_privileged_count(monkeypatch, targeting):
    """Two real steps (the searcher chain, the mission goals, and at 3 the Bayes post-pass with its hand-back
    to the chain): with the switch on, _count_unresolved_victims is called only by the observer dashboards;
    the searcher's count equals briefing - detected after every step. Off: the chain calls it (bites)."""
    import traceback

    for value in (1, 0):
        model = _model(monkeypatch, untuned=value, targeting=targeting)
        callers: list[str] = []
        real = gen._count_unresolved_victims

        def recording(sim, _real=real):
            callers.append(pathlib.Path(traceback.extract_stack(limit=3)[-2].filename).parts[-2])
            return _real(sim)

        import wildfire_model as wf
        monkeypatch.setattr(gen, "_count_unresolved_victims", recording)
        monkeypatch.setattr(wf, "_count_unresolved_victims", recording)
        for _ in range(2):
            model.step()
        if value:   # the chain first writes the count on step 1 (step 0 leaves the default 0)
            expected = gen._victim_briefing_count(model) - len(gen._detected_victim_ids(model))
            assert expected > 0
            assert all(ws["unresolved_victim_count"] == expected for ws in _searcher_ws(model).values())
        outside = [c for c in callers if c != "dashboard"]
        if value:
            assert outside == []
        else:
            assert outside


# ============================================================================ review fixes (Part 2)
def test_no_untuned_x_pull_inside_an_x_lane(monkeypatch):
    """Inside an x-lane (north / south wind, 2 searchers) the other strip is out of reach: no escape pull and no
    corridor second-strip pull, as _finalize_coverage_target already suppresses its clamp."""
    ws = _ws(last_wind_direction="north", lane_axis="x")
    assert gen._add_escape_x_pull(0.0, untuned=True, wind_label="north", west_pending=False, east_pending=True,
                                  ax=10.0, cx=20, safe_x_min=2, safe_x_max=47, wind_state=ws) == 0.0
    ws["lane_axis"] = None
    assert gen._add_escape_x_pull(0.0, untuned=True, wind_label="north", west_pending=False, east_pending=True,
                                  ax=10.0, cx=20, safe_x_min=2, safe_x_max=47, wind_state=ws) == pytest.approx(7.5)


def _corridor_pull_calls(monkeypatch, lane_axis):
    """Run the corridor waypoint generator (north wind, coverage on) and record whether the untuned second-strip
    pull is consulted."""
    calls = []
    real = gen._untuned_second_strip_pull
    monkeypatch.setattr(gen, "_untuned_second_strip_pull", lambda *a: calls.append(a) or real(*a))
    monkeypatch.setattr(gen, "_searcher_crosswind_lane",
                        lambda *a, **k: ("x", 0, 24) if lane_axis == "x" else None)
    ws = _ws(recent_x_positions=[5, 10], unresolved_victim_count=1, last_wind_direction="north")
    gen.LocalAdaptationSpaceGenerator()._generate_corridor_waypoints(
        runtime_models={}, uav_id="1", wind_direction="north", wind_vector=(0.0, 1.0), fire_cells=set(),
        smoke_cells=set(), fx=25.0, fy=25.0, ax=10.0, ay=25.0, x_min=X_MIN, x_max=X_MAX, y_min=Y_MIN,
        y_max=Y_MAX, simulation=None, wind_state=ws, step_index=50, force_interior=False)
    return calls


def test_no_corridor_second_strip_pull_inside_an_x_lane(monkeypatch):
    _on(monkeypatch, 1)
    free = _corridor_pull_calls(monkeypatch, None)
    assert free and free[0][0] == "west" and free[0][1:] == (False, True)   # west done, east pending -> pull
    assert _corridor_pull_calls(monkeypatch, "x") == []


def _tails15():
    for lo in range(50):
        for hi in range(lo, min(50, lo + 20)):
            yield [lo] * 8 + [hi] * 7


def test_t19_the_y_camping_gate_mirrors_north_and_south(monkeypatch):
    def commit(tail, wind):
        ws = _ws(recent_y_positions=list(tail), last_wind_direction=wind)
        return gen._wind_aware_y_commit(ws, Y_MIN, Y_MAX)
    flip = {"north": "south", "south": "north", None: None}
    for value in (1, 0):
        _on(monkeypatch, value)
        asym = sum(1 for t in _tails15() if flip[commit(t, "north")] != commit([49 - y for y in t], "south"))
        assert (asym == 0) if value else (asym > 0)
        # east / west wind: unchanged by T19 (the disjoint-halves rule decides after the gate)
    for t in _tails15():
        for wind in ("east", "west"):
            _on(monkeypatch, 0)
            off = commit(t, wind)
            _on(monkeypatch, 1)
            assert commit(t, wind) == off


def test_the_communication_planner_reads_no_undetected_victim(monkeypatch):
    from src_extension.planning import communication_adaptation_planner as cap

    class _S:
        rescue_assigned, status, confirmed = True, "assigned", False      # impossible for an undetected victim
    sim = type("Sim", (), {"managed_victims": {"victim_0": _S()}})()
    fn = cap._rescue_coordination_active
    import inspect
    params = list(inspect.signature(fn).parameters)
    call = (lambda: fn({}, {"simulation_model": sim})) if len(params) >= 2 else (lambda: fn({"simulation_model": sim}))
    _on(monkeypatch, 0)
    assert call() is True
    _on(monkeypatch, 1)
    assert call() is False
