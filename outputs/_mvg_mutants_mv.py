"""MVG round Part 2d - the MUTANTS of the movement block: fixes (a) and (b) and their stranding guard
(outputs/urgency_part1d.txt 1d.8 (4): "the urgency round's (a) / (b) mutants plus the guard mutants above. All must
be killed"; the convention and the check are the urgency round's, outputs/urgency_part1.txt 15.3 / 15.4 / 22.6.2).

MUTANTS_MV = {id: (description, [(file, old, new), ...], [pytest node ids])}. Every test in
tests/test_movement_fixes.py and tests/test_stranding_guard.py names its mutant(s) ("MUTANT: <id>"); a mutant is the
smallest exact-text source change that removes what the test guards. `old` must match the CURRENT source exactly
once. The test must FAIL on the mutant and PASS on the unmutated source. outputs/_mvg_mutants.py (the round's check,
a port of urgency:outputs/_ud_mutants.py) imports MUTANTS_MV lazily; this file also runs the check on its own:

    python outputs/_mvg_mutants_mv.py --repo E:/Projects/SAS_wt/mvg --work <scratch dir> [--only ma1_pass,g_plus1]
        [--jobs 3] [--out <record file>]
    python outputs/_mvg_mutants_mv.py --repo ... --pins            # T-NT pins from `git show a20a2ef5`
    python outputs/_mvg_mutants_mv.py --repo ... --work ... --golden   # T-ID-M's base digest (a20a2ef5 code)

WHERE THE MUTANTS COME FROM (a port of urgency:outputs/_ud_mutants_mv.py at 0d5358e3, 48 mutants):
  - KEPT, 32: every (a), (b), ALL, switch, identity and T-NT mutant. Texts and node lists are the urgency round's
    with three kinds of change, each for this branch only:
      * RE-ANCHORED: the (a) call site is now `path_step = self._guarded(<urgency's expression>)` (the guard wraps
        the fix's choice, Part 1d 1d.8 (3)); ma6_greedy, sw_enter_a and id_a_off edit that line and keep their
        meaning inside the wrapper. The (b) call site keeps urgency's three lines inside `self._guarded(...)`, so
        the (b) edits match unchanged.
      * NODES RE-POINTED: T-ID-M is renamed (it checks a third setting, "shipped"); T-Ma8, T-Mb4 and T-SAFE-M are
        now parametrized over the guard (guard0 / guard1). Each urgency node is mapped to its guard0 case - the fix
        as screened, which is what the urgency test was - AND to its guard1 case, except the one case the guard
        masks (GUARD-MASKED below). Every case is named on its own, so each must fail itself (not "one of the
        function's cases"): ma8_raise [guard0] [guard1]; safe_clean [guard0] [guard1]; mb4_pickup [on_her_cell-
        guard0] [on_her_cell-guard1]; mb4_exempt [next_to_her-guard0].
      * DESCRIPTIONS: "three fix blocks" -> "two" (nt_advance); the call-site mutants say what the guard sees.
  - DROPPED, 16: fix (c) (mc1_len, mc1_comb, mc_greedy, mc2_greedy, mc2_order_only, mc2_burning_hold, mc2_smoky,
    mc3_hold, mc4_removed, mc4_approach, mc5_hold, mc6_dep, mc7_c1, mc8_relabel, sw_truthy_c, sw_enter_c): fix (c)
    and U1 are not carried into this round (ruling, urgency report 11; W-9 (a)) and their tests are not ported.
  - NEW, 29: the guard's 28 (1d.8 (4)), each paired with the T-G case that kills it (tests/test_stranding_guard.py,
    whose module docstring holds the MUTANT KEY), plus nt_toplevel for T-NT's new top-level-statement pin.
  61 in all. Every edit is the one builder T pre-checked (scratch tmut.py / tmut_ported.py), byte for byte.

GUARD-MASKED CASE (measured 2026-10-07 with every case of the four guard-parametrized nodes listed on its own):
mb4_exempt SURVIVES T-Mb4 [next_to_her-guard1]. The mutant roots the fix's clean field at her unclean (smoky) cell,
so (a) wants to step onto it; with the guard on, the guard's OWN unclean set (unclean_cells: burning, smoky,
fire-adjacent) vetoes that step (n unclean -> veto), today's step runs and the unit never enters her cell - the
property the test checks then holds through the guard, not through the fix. That case is not listed; the guard's
unclean test at n is itself pinned by T-G1 [n_smoky] (g_n_exempt) and [victim_smoky] (g_victim_exempt). The other
three were killed in both guard cases: ma8_raise (raise != today's predicate) and mb4_pickup (the unit picks her up)
by the property assertion in both; safe_clean [guard0] by the clean-landing assertion, but safe_clean [guard1] by
T-SAFE-M's ACTIVITY FLOOR (measured {7: 1, 10: 31} against floors {7: 25, 10: 20}): with the guard on, the fix's
steps onto unclean cells are vetoed, so the safety assertion holds through the guard and fix (a) almost stops
acting - the guarded case detects the mutant only through the collapse of (a)'s activity.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

AG = "agents.py"
WM = "wildfire_model.py"
MP = "src_extension/planning/movement_paths.py"
CFV = "common_fixed_variables.py"
T = "tests/test_movement_fixes.py"
TG = "tests/test_stranding_guard.py"
BASE_COMMIT = "a20a2ef5"

# ---- frequently edited source lines (each must match the current source exactly once) ------------------------------
# (a) call site: urgency's `path_step = self._approach_path_choice() if ff_approach_path() else None`, guarded here
_A_CHOICE = "self._approach_path_choice() if ff_approach_path() else None"
_A_CALL = "                path_step = self._guarded(" + _A_CHOICE + ")"
_A_STEP = "                if path_step is not None:\n                    self._fix_move(path_step, APPROACH_PATH_TIER)"
_A_ELSE = ("                if path_step is not None:\n                    self._fix_move(path_step, APPROACH_PATH_TIER)\n"
           "                else:\n                    self._move_toward(self.target_pos)")
# (b) call site: urgency's three lines, now inside `on_route = self._guarded(...)`
_B_CALL = ("                self._retreat_on_route_choice()\n"
           "                if ff_retreat_keep_approach() and self.target_pos and not self.exiting\n"
           "                else None")
_B_STEP = "            if on_route is not None:\n                self._fix_move(on_route, RETREAT_ON_ROUTE_TIER)"
_FIELD = "        field = movement_paths.clean_distance_field(target, is_clean, in_bounds)\n        has_exit"
_ACC_A = "    return _exact_integer(getattr(cfv, \"FF_APPROACH_PATH\", 0)) == 1"
_ACC_B = "    return _exact_integer(getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 0)) == 1"
# the guard (movement_paths.stranding_guard and the model side, Firefighter._stranding_guard_verdict / _guarded)
_ACC_G = "    return _fix2_switch(\"FF_FIX_STRANDING_GUARD\")"
_G_FIRST = "    if n in unclean or not t_star(t_grid, n, x_size, y_size) > 1:"
_G_HOPS = ("    hops = safe_route_hops(n, x_size, y_size, unclean | {u}, "
           "lambda x: t_star(t_grid, x, x_size, y_size) - 1)")
_G_FAE = ("    t_grid = arrival_time(x_size, y_size, burning, wind, "
          "params if params is not None else FrontPriorityParams())")
_G_VERDICT = "        return step_cell if self._stranding_guard_verdict(step_cell)[0] else None"
_G_SWITCH = "        if step_cell is None or not ff_fix_stranding_guard():\n            return step_cell"
_G_VIEW = "            int(grid.width),\n            int(grid.height),"


def _t(name: str) -> str:
    return f"{T}::{name}"


def _g(name: str) -> str:
    return f"{TG}::{name}"


_TG1 = "test_tg1_known_answer_boards_crafted_t"


def _tg1(*cases: str) -> list[str]:
    return [_g(f"{_TG1}[{c}]") for c in cases]


_TG1_PROP = _g("test_tg1_property_the_guard_equals_the_oracle")
_TG7 = _g("test_tg7_the_built_guard_equals_the_frozen_guard_on_1019_recorded_decisions")
_TG4 = _g("test_tg4_the_ported_bfs_helpers_equal_u1s_on_a_property_corpus")
_TG5_ON = "test_tg5_the_guard_is_on_for_everything_but_an_exact_zero"
_TG5_OFF = "test_tg5_the_guard_is_off_only_on_an_exact_zero"
_TG5_SHIP = _g("test_tg5_shipped_one_and_read_at_call_time")
_TG6 = _g("test_tg6_with_both_fixes_at_0_the_guard_is_never_evaluated")
_TG8 = _g("test_tg8_searcher_fp_knobs_do_not_change_any_verdict")
_MA8 = "test_ma8_z_rb_the_raise_is_todays_predicate_and_never_on_an_a_step"
_MB4 = "test_mb4_an_unclean_victim_cell_is_never_entered_nor_a_pickup_made"
_TSAFEM = "test_tsafem_property_no_fix_enters_fire_and_a_b_land_clean_in_a_gesc_region"


# id -> (description, [(file, old, new), ...], [pytest node ids])
MUTANTS_MV: dict[str, tuple[str, list[tuple[str, str, str]], list[str]]] = {
    # ------------------------------------------------------------------ (a) FF_APPROACH_PATH (urgency, kept)
    "ma1_switch": (
        "(a)'s switch ignored: ff_approach_path() never reads FF_APPROACH_PATH (always off)",
        [(AG, _ACC_A, "    return False")],
        [_t("test_ma1_barrier_board_reaches_the_victim_in_d_steps")],
    ),
    "ma1_pass": (
        "(a)/(b)'s passable = non-burning: the victim's field built over every non-burning cell",
        [(AG, _FIELD, "        field = movement_paths.clean_distance_field(target, lambda c: in_bounds(c) and c not in "
                      "burning, in_bounds)\n        has_exit")],
        [_t("test_ma1_barrier_board_reaches_the_victim_in_d_steps")],
    ),
    "ma2_burning": (
        "(a) without a clean path follows a shortest burning-only (fire-free) path instead of today's mover",
        [(AG, "        if unit not in field:\n            return None\n        today = self._greedy_choice(",
          "        if unit not in field:\n"
          "            field = movement_paths.clean_distance_field((int(self.target_pos[0]), int(self.target_pos[1])), "
          "lambda c: in_bounds(c) and c not in burning, in_bounds)\n"
          "            has_exit = True\n        today = self._greedy_choice(")],
        [_t("test_ma2_without_a_qualifying_clean_path_todays_mover_runs[no_clean_path]"),
         _t("test_ma2_without_a_qualifying_clean_path_todays_mover_runs[unclean_victim]")],
    ),
    "ma2_gesc": (
        "G-ESC removed from (a)'s choice",
        [(MP, "    if d is None or d == 0 or not has_exit:", "    if d is None or d == 0:")],
        [_t("test_ma2_without_a_qualifying_clean_path_todays_mover_runs[gesc_false]")],
    ),
    "ma3_tiebreak": (
        "TODAY-FIRST removed: the fire-distance tie-break applied to every step",
        [(MP, "    if not on_path or today_cell in on_path:", "    if not on_path:")],
        [_t("test_ma3_today_first_on_open_ground")],
    ),
    "ma3_replica": (
        "the greedy replica's axis rule |dx| >= |dy| changed to > (today's shadow wrong on ties)",
        [(AG, "        cx, cy = self.pos\n        dx, dy = tx - cx, ty - cy\n        if abs(dx) >= abs(dy):\n"
              "            preferred = (",
          "        cx, cy = self.pos\n        dx, dy = tx - cx, ty - cy\n        if abs(dx) > abs(dy):\n"
          "            preferred = (")],
        [_t("test_ma3_greedy_choice_is_move_towards_destination")],
    ),
    "ma4_order": (
        "(a)'s tie-break order-only: the first shortest-path neighbour in search order",
        [(MP, "    return _best(unit_cell, on_path, fire_dist)", "    return on_path[0]")],
        [_t("test_ma4_off_path_today_takes_the_larger_fire_distance")],
    ),
    "ma5_relabel": (
        "the relabel tail removed from the (a) step (tier and risk still written)",
        [(AG, _A_STEP, "                if path_step is not None:\n"
                       "                    self._last_move_tier = APPROACH_PATH_TIER\n"
                       "                    self._last_move_risk = 0\n"
                       "                    self.model.grid.move_agent(self, path_step)")],
        [_t("test_ma5_an_a_step_relabels_a_route_blocked_unit_tier_7_risk_0")],
    ),
    "ma6_greedy": (
        "today's greedy only: the (a) branch is never taken at the call site (the guard is handed no step)",
        [(AG, _A_CALL, "                path_step = self._guarded(None)")],
        [_t("test_ma6_property_the_clean_distance_falls_by_one_per_step")],
    ),
    "ma7_cache": (
        "the clean field cached on the unit at the first call for the victim's cell (not recomputed)",
        [(AG, _FIELD,
          "        cache = getattr(self, \"_mv_field_cache\", None)\n"
          "        if cache is None or cache[0] != target:\n"
          "            cache = (target, movement_paths.clean_distance_field(target, is_clean, in_bounds))\n"
          "            self._mv_field_cache = cache\n"
          "        field = cache[1]\n        has_exit")],
        [_t("test_ma7_the_field_is_recomputed_every_step")],
    ),
    "ma8_raise": (
        "with (a) on and no fire-free route, the unit holds instead of calling _move_toward (the raise suppressed)",
        [(AG, _A_ELSE,
          "                if path_step is not None:\n                    self._fix_move(path_step, APPROACH_PATH_TIER)\n"
          "                elif ff_approach_path() and not self._path_exists_avoiding_fire(\n"
          "                    (int(self.pos[0]), int(self.pos[1])), tuple(self.target_pos), self._fire_cells()\n"
          "                ):\n                    pass\n"
          "                else:\n                    self._move_toward(self.target_pos)")],
        [_t(f"{_MA8}[guard0]"), _t(f"{_MA8}[guard1]")],
    ),
    # ------------------------------------------------------------------ (b) FF_RETREAT_KEEP_APPROACH (urgency, kept)
    "mb1_today": (
        "today's retreat always: the (b) choice is never consulted at the call site (the guard is handed no step)",
        [(AG, _B_CALL, _B_CALL.replace("self._retreat_on_route_choice()", "None"))],
        [_t("test_mb1_an_off_route_retreat_takes_the_on_route_clean_cell")],
    ),
    "mb2_always": (
        "(b) used even when today's retreat cell is already on the route",
        [(MP, "    if today_cell in best:\n        return None\n", "")],
        [_t("test_mb2_an_on_route_retreat_is_todays_survival_move_verbatim")],
    ),
    "mb3_unclean": (
        "unclean cells admitted: (b)'s on-route set built over every non-burning cell",
        [(AG, "        field, has_exit, is_clean, in_bounds = self._victim_clean_field(burning, smoky)\n"
              "        if not field:\n            return None\n        today = self._survival_choice()",
          "        field, has_exit, is_clean, in_bounds = self._victim_clean_field(burning, smoky)\n"
          "        is_clean = lambda c: in_bounds(c) and c not in burning  # noqa: E731\n"
          "        field = movement_paths.clean_distance_field((int(self.target_pos[0]), int(self.target_pos[1])), "
          "is_clean, in_bounds)\n"
          "        if not field:\n            return None\n        today = self._survival_choice()")],
        [_t("test_mb3_without_a_clean_on_route_cell_todays_retreat_runs[no_clean_neighbour]"),
         _t("test_mb3_without_a_clean_on_route_cell_todays_retreat_runs[no_clean_route]")],
    ),
    "mb3_gesc": (
        "G-ESC removed from (b)'s choice",
        [(MP, "    if not field or not has_exit:\n        return None\n    finite",
          "    if not field:\n        return None\n    finite")],
        [_t("test_mb3_without_a_clean_on_route_cell_todays_retreat_runs[gesc_false]")],
    ),
    "mb4_pickup": (
        "pickup on an unclean, non-burning victim cell: a unit standing on its victim's non-burning cell skips the "
        "survival retreat and reaches the pickup branch (ruling V-4's rejected option)",
        [(AG, "        if self._needs_immediate_survival_retreat(idle_buffer):",
          "        if self._needs_immediate_survival_retreat(idle_buffer) and not (\n"
          "            self.target_pos and not self.exiting and tuple(self.pos) == tuple(self.target_pos)\n"
          "            and not self._cell_contains_active_fire((int(self.pos[0]), int(self.pos[1])))\n"
          "        ):")],
        [_t(f"{_MB4}[on_her_cell-guard0]"), _t(f"{_MB4}[on_her_cell-guard1]")],
    ),
    "mb4_exempt": (
        "the victim's own cell exempt from the clean test: the clean field is rooted at an unclean victim cell",
        [(MP, "    if not in_bounds(target) or not is_clean(target):\n        return {}",
          "    if not in_bounds(target):\n        return {}")],
        [_t(f"{_MB4}[next_to_her-guard0]")],
    ),
    "mb5_both": (
        "the (b) step's relabel tail and its \"survival_retreat_on_route\" record both removed",
        [(AG, "                self._fix_move(on_route, RETREAT_ON_ROUTE_TIER)\n                self._record_movement_reason(\n"
              "                    \"survival_retreat_on_route\",",
          "                self._last_move_tier = RETREAT_ON_ROUTE_TIER\n"
          "                self._last_move_risk = 0\n"
          "                self.model.grid.move_agent(self, on_route)\n                self._record_movement_reason(\n"
          "                    \"survival_retreat\",")],
        [_t("test_mb5_a_b_step_relabels_and_records_survival_retreat_on_route")],
    ),
    "mb6_write": (
        "(b) writes _idle_retreat_last_cell",
        [(AG, _B_STEP, "            if on_route is not None:\n                self._idle_retreat_last_cell = cell\n"
                       "                self._fix_move(on_route, RETREAT_ON_ROUTE_TIER)")],
        [_t("test_mb6_hidden_state_a_today_retreat_after_b_steps_reads_the_stored_state")],
    ),
    "mb6_replica": (
        "the _survival_choice replica ignores the stored last cell (anti-oscillation memory)",
        [(AG, "        last_cell = getattr(self, \"_idle_retreat_last_cell\", None)\n        if origin is None or (",
          "        last_cell = None\n        if origin is None or (")],
        [_t("test_mb6_survival_choice_is_survival_moves_destination")],
    ),
    # ------------------------------------------------------------------ ALL (urgency, kept)
    "safe_clean": (
        "the clean filter dropped from the shared predicate: CLEAN = in bounds and not burning",
        [(AG, "            if grid.out_of_bounds(cell) or cell in burning or cell in smoky:\n                return False\n"
              "            cx, cy = cell\n            for ox, oy in EXIT_LEG_SEARCH_ORDER:\n"
              "                if (cx + ox, cy + oy) in burning:\n                    return False\n            return True",
          "            if grid.out_of_bounds(cell) or cell in burning:\n                return False\n            return True")],
        [_t(f"{_TSAFEM}[guard0]"), _t(f"{_TSAFEM}[guard1]")],
    ),
    "sw_strict_a": (
        "FF_APPROACH_PATH compared with 1 without the exact-integer parsing (\"1\" and \" 1 \" read off)",
        [(AG, _ACC_A, "    return getattr(cfv, \"FF_APPROACH_PATH\", 0) == 1")],
        [_t("test_tswm_on_only_on_an_exact_one")],
    ),
    "sw_import_a": (
        "FF_APPROACH_PATH read once at import time (an import-time copy, not a call-time read)",
        [(AG, "def ff_approach_path() -> bool:",
          "_FF_APPROACH_PATH_AT_IMPORT = getattr(cfv, \"FF_APPROACH_PATH\", 0)\n\n\ndef ff_approach_path() -> bool:"),
         (AG, _ACC_A, "    return _exact_integer(_FF_APPROACH_PATH_AT_IMPORT) == 1")],
        [_t("test_tswm_read_at_call_time_and_shipped_zero")],
    ),
    "sw_shipped_a": (
        "FF_APPROACH_PATH shipped 1",
        [(CFV, "\nFF_APPROACH_PATH = 0\n", "\nFF_APPROACH_PATH = 1\n")],
        [_t("test_tswm_read_at_call_time_and_shipped_zero")],
    ),
    "sw_truthy_a": (
        "FF_APPROACH_PATH read by truthiness instead of an exact 1",
        [(AG, _ACC_A, "    return bool(getattr(cfv, \"FF_APPROACH_PATH\", 0))")],
        [_t("test_tswm_off_approach_path")],
    ),
    "sw_truthy_b": (
        "FF_RETREAT_KEEP_APPROACH read by truthiness instead of an exact 1",
        [(AG, _ACC_B, "    return bool(getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 0))")],
        [_t("test_tswm_off_retreat_keep_approach")],
    ),
    "sw_enter_a": (
        "(a)'s pure choice evaluated while FF_APPROACH_PATH is off (the result discarded before the guard)",
        [(AG, _A_CALL, _A_CALL.replace("else None)", "else (self._approach_path_choice() and None))"))],
        [_t("test_tswm_off_never_enters_new_code")],
    ),
    "sw_enter_b": (
        "(b)'s pure choice evaluated while FF_RETREAT_KEEP_APPROACH is off (the result discarded before the guard)",
        [(AG, _B_CALL, _B_CALL.replace("                else None",
                                       "                else (self._retreat_on_route_choice() and None)"))],
        [_t("test_tswm_off_never_enters_new_code")],
    ),
    "id_a_off": (
        "the (a) branch taken when its switch is off (its step still passes through the guard)",
        [(AG, _A_CALL, "                path_step = self._guarded(self._approach_path_choice())")],
        [_t("test_tidm_switches_absent_zero_and_shipped_are_identical_and_equal_the_base")],
    ),
    "nt_survival": (
        "one line changed in _survival_move (the leash cap test >= -> >)",
        [(AG, "        at_cap = steps >= IDLE_RETREAT_MAX_CELLS\n        current_dist = self._min_fire_distance(cell, fire_cells)\n"
              "        current_risk = self._firefighter_cell_risk(cell)\n"
              "        last_cell = getattr(self, \"_idle_retreat_last_cell\", None)",
          "        at_cap = steps > IDLE_RETREAT_MAX_CELLS\n        current_dist = self._min_fire_distance(cell, fire_cells)\n"
          "        current_risk = self._firefighter_cell_risk(cell)\n"
          "        last_cell = getattr(self, \"_idle_retreat_last_cell\", None)")],
        [_t("test_tnt_the_not_touched_list_hashes_equal_the_base")],
    ),
    "nt_release": (
        "15.3's T-NT mutant: one line changed in _release_other_claimants (value-equivalent text change)",
        [(WM, "        keep = str(keep_ff_id or \"\").strip()\n", "        keep = str(keep_ff_id or \"\").strip() or \"\"\n")],
        [_t("test_tnt_the_not_touched_list_hashes_equal_the_base")],
    ),
    "nt_advance": (
        "one line changed in Firefighter.advance outside the two fix blocks (the standby record's text)",
        [(AG, "                f\"standby at edge {self.pos}\",", "                f\"standby at the edge {self.pos}\",")],
        [_t("test_tnt_touched_functions_differ_from_the_base_only_by_the_registered_edits")],
    ),
    # ------------------------------------------------------------------ T-NT (new in this round)
    "nt_toplevel": (
        "an import added at the top of agents.py next to the registered movement_paths import (a top-level "
        "statement outside every def / class / assignment)",
        [(AG, "from src_extension.planning import movement_paths\n",
          "from src_extension.planning import movement_paths\nimport math as _nt_math  # noqa: F401\n")],
        [_t("test_tnt_touched_functions_differ_from_the_base_only_by_the_registered_edits")],
    ),
    # ------------------------------------------------------------------ THE GUARD SG-T: stranding_guard (1d.2.2)
    "g_plus1": (
        "drop \"+1\": stranding_guard admits on c_n <= T(v) (the pickup step dropped)",
        [(MP, "    return (c_n + 1) <= t_v, c_n, t_v", "    return c_n <= t_v, c_n, t_v")],
        _tg1("plus_one_cut", "n_is_v_cut") + [_TG1_PROP],
    ),
    "g_tstar": (
        "T instead of T*: the first-hop test and the route's t_star_of read T at the cell itself, "
        "float(t_grid[x]), not t_star(t_grid, x, ...)",
        [(MP, _G_FIRST, "    if n in unclean or not float(t_grid[n[0], n[1]]) > 1:"),
         (MP, _G_HOPS, _G_HOPS.replace("t_star(t_grid, x, x_size, y_size) - 1", "float(t_grid[x[0], x[1]]) - 1"))],
        _tg1("closes_by_neighbour_t", "closes_at_hop_k") + [_TG1_PROP, _TG7],
    ),
    "g_ge_k": (
        "\">= k\" for \"> k\": the ported safe_route_hops enters a cell at hop k when t_star_of(cell) >= k",
        [(MP, "            if not t_star_of(n) > k:", "            if not t_star_of(n) >= k:")],
        _tg1("c_equals_t", "closes_at_hop_k") + [_TG4],
    ),
    "g_ge_1": (
        "\">= k\" for \"> k\" at the first hop: stranding_guard's test at n is t_star(t_grid, n, ...) >= 1",
        [(MP, _G_FIRST, _G_FIRST.replace("> 1:", ">= 1:"))],
        _tg1("n_is_v_closes"),
    ),
    "g_first_hop": (
        "no forced first hop: the route BFS starts at u (c = hops from u to v, any first step), not at n",
        [(MP, _G_HOPS + "\n    if v not in hops:\n        return False, None, t_v\n    c_n = 1 + hops[v]",
          "    hops = safe_route_hops(u, x_size, y_size, unclean, lambda x: t_star(t_grid, x, x_size, y_size))"
          "\n    if v not in hops:\n        return False, None, t_v\n    c_n = hops[v]")],
        _tg1("only_via_another_neighbour") + [_TG1_PROP, _TG7],
    ),
    "g_reenter_u": (
        "u re-entered: u is not added to the route BFS's blocked set",
        [(MP, _G_HOPS, _G_HOPS.replace("unclean | {u}", "unclean"))],
        _tg1("only_through_u", "only_via_another_neighbour") + [_TG1_PROP],
    ),
    "g_admit_inf": (
        "admit when c infinite: stranding_guard's \"v not in hops\" return is (True, None, T(v))",
        [(MP, "    if v not in hops:\n        return False, None, t_v", "    if v not in hops:\n        return True, None, t_v")],
        _tg1("victim_smoky", "victim_fire_adjacent", "c_equals_t", "closes_by_neighbour_t", "closes_at_hop_k",
             "only_through_u", "only_via_another_neighbour") + [_TG1_PROP, _TG7],
    ),
    "g_n_exempt": (
        "n's own unclean test dropped: only T*(n) > 1 is tested at n",
        [(MP, _G_FIRST, "    if not t_star(t_grid, n, x_size, y_size) > 1:")],
        _tg1("n_smoky"),
    ),
    "g_victim_exempt": (
        "the victim's cell removed from the unclean set",
        [(MP, "    unclean = unclean_cells(burning, smoky, x_size, y_size)\n    t_v",
          "    unclean = unclean_cells(burning, smoky, x_size, y_size) - {v}\n    t_v")],
        _tg1("victim_smoky"),
    ),
    "g_nofire_veto": (
        "with nothing burning the guard vetoes (an early (False, None, inf) when the burning set is empty)",
        [(MP, "    burning = [(int(x), int(y)) for x, y in burning]\n",
          "    burning = [(int(x), int(y)) for x, y in burning]\n    if not burning:\n"
          "        return False, None, float(\"inf\")\n")],
        [_g("test_tg1_no_fire_admits_with_t_infinite")],
    ),
    "g_wind_none_mp": (
        "wind None inside movement_paths: stranding_guard calls arrival_time with wind None",
        [(MP, _G_FAE, _G_FAE.replace("burning, wind,", "burning, None,"))],
        [_g("test_tg1_the_wind_vector_decides_the_barrier_board"), _TG1_PROP, _TG7],
    ),
    "g_xy_swap": (
        "the extents swapped inside movement_paths: stranding_guard calls arrival_time(y_size, x_size, ...)",
        [(MP, _G_FAE, _G_FAE.replace("arrival_time(x_size, y_size,", "arrival_time(y_size, x_size,"))],
        [_g("test_tg1_non_square_grid_x_is_the_first_extent")],
    ),
    "g_fae_params": (
        "FAE params from SEARCHER_FP_*: stranding_guard's default params are front_priority_params()",
        [(MP, "from src_extension.planning.fire_arrival_estimate import FrontPriorityParams, arrival_time",
          "from src_extension.planning.fire_arrival_estimate import FrontPriorityParams, arrival_time, "
          "front_priority_params"),
         (MP, _G_FAE, _G_FAE.replace("else FrontPriorityParams()", "else front_priority_params()"))],
        [_TG8],
    ),
    # ------------------------------------------------------------------ the ported U1 helpers (T-G4)
    "hp_t_star_cell": (
        "T instead of T* in the ported helper: t_star ignores the neighbours (returns T at the cell)",
        [(MP, "    best = float(t_grid[cell[0], cell[1]])\n    for ox, oy in SEARCH_ORDER:",
          "    best = float(t_grid[cell[0], cell[1]])\n    return best\n    for ox, oy in SEARCH_ORDER:")],
        _tg1("closes_by_neighbour_t", "closes_at_hop_k") + [_TG4],
    ),
    "hp_no_adjacent": (
        "the ported helper unclean_cells drops the 4-neighbours of burning cells (equivalent inside the guard, where "
        "FAE's T = 0 on burning cells closes every fire-adjacent cell through T*; killed by T-G4's direct comparison)",
        [(MP, "        out.add(cell)\n        for ox, oy in SEARCH_ORDER:\n            n = (cell[0] + ox, cell[1] + oy)\n"
              "            if _in_bounds(n, x_size, y_size):\n                out.add(n)",
          "        out.add(cell)")],
        [_TG4],
    ),
    # ------------------------------------------------------------------ the guard's model side (agents.py)
    "g_wind_none": (
        "wind None: _stranding_guard_verdict passes wind None (the model's wind label is not read)",
        [(AG, "            cfv.wind_vector_from_direction(wind_label),", "            None,")],
        [_g("test_tg1_the_wind_vector_decides_the_barrier_board")],
    ),
    "g_view_swap": (
        "_stranding_guard_verdict passes grid.height as x_size and grid.width as y_size",
        [(AG, _G_VIEW, "            int(grid.height),\n            int(grid.width),")],
        [_g("test_tg1_non_square_grid_x_is_the_first_extent")],
    ),
    "g_numpy_identity": (
        "fire_board_sets reads burning by identity with True (a numpy.bool_ fire is invisible to the guard)",
        [(AG, "        if agent.is_burning():\n            burning.add(cell)\n        smoke = getattr(agent, \"smoke\", None)",
          "        if agent.is_burning() is True:\n            burning.add(cell)\n        smoke = getattr(agent, \"smoke\", None)")],
        [_g("test_tg1_numpy_bool_burning_flags_are_read_by_truthiness")],
    ),
    "g_fae_params_view": (
        "FAE params from SEARCHER_FP_* on the model side: _stranding_guard_verdict passes "
        "params=front_priority_params()",
        [(AG, _G_VIEW + "\n        )",
          _G_VIEW + "\n            params=__import__(\"src_extension.planning.fire_arrival_estimate\", "
          "fromlist=[\"x\"]).front_priority_params(),\n        )")],
        [_TG8],
    ),
    "g_veto_acts": (
        "veto acts: the fix's step is taken although the guard vetoes (_guarded returns the cell whatever the "
        "verdict; the verdict is still computed)",
        [(AG, _G_VERDICT, "        self._stranding_guard_verdict(step_cell)\n        return step_cell")],
        [_g("test_tg2_an_a_veto_is_todays_step"), _g("test_tg2_a_b_veto_is_todays_retreat_with_its_writes"),
         _g("test_tg2_property_every_veto_is_todays_step")],
    ),
    "g_switch_first": (
        "_guarded reads ff_fix_stranding_guard() before it tests for a missing step (the switch read with both "
        "fixes off)",
        [(AG, "        if step_cell is None or not ff_fix_stranding_guard():",
          "        if not ff_fix_stranding_guard() or step_cell is None:")],
        [_TG6],
    ),
    "g_eval_off": (
        "the (a) site evaluates the guard on (a)'s pure choice whatever FF_APPROACH_PATH says (the result discarded "
        "when the switch is off)",
        [(AG, _A_CALL, "                path_step = (self._guarded(self._approach_path_choice()) if ff_approach_path() "
                       "else (self._guarded(self._approach_path_choice()) and None))")],
        [_TG6],
    ),
    # ------------------------------------------------------------------ the guard's switch FF_FIX_STRANDING_GUARD
    "sw_guard_ignored": (
        "the guard applied whatever FF_FIX_STRANDING_GUARD says: _guarded's switch test removed",
        [(AG, _G_SWITCH, "        if step_cell is None:\n            return step_cell")],
        [_g("test_tg3_guard_at_exact_0_is_the_urgency_rounds_fixes")],
    ),
    "sw_guard_default": (
        "accessor default: ff_fix_stranding_guard reads a MISSING switch as 0 (getattr default 0)",
        [(AG, _ACC_G, "    return _exact_integer(getattr(cfv, \"FF_FIX_STRANDING_GUARD\", 0)) != 0")],
        [_g(f"{_TG5_ON}[missing]")],
    ),
    "sw_guard_truthy": (
        "exact-0 semantics lost: ff_fix_stranding_guard reads truthiness, bool(getattr(cfv, "
        "\"FF_FIX_STRANDING_GUARD\", 1))",
        [(AG, _ACC_G, "    return bool(getattr(cfv, \"FF_FIX_STRANDING_GUARD\", 1))")],
        [_g(f"{_TG5_ON}[None]"), _g(f"{_TG5_ON}[empty]"), _g(f"{_TG5_OFF}[str0]"), _g(f"{_TG5_OFF}[str_0_]")],
    ),
    "sw_guard_exact1": (
        "exact-0 semantics lost the other way: ff_fix_stranding_guard is on only on an exact 1",
        [(AG, _ACC_G, "    return _exact_integer(getattr(cfv, \"FF_FIX_STRANDING_GUARD\", 1)) == 1")],
        [_g(f"{_TG5_ON}[{c}]") for c in ("None", "2", "0.5", "on", "empty")],
    ),
    "sw_guard_import": (
        "FF_FIX_STRANDING_GUARD read once at import time (an import-time copy, not a call-time read)",
        [(AG, "def ff_fix_stranding_guard() -> bool:",
          "_FF_FIX_STRANDING_GUARD_AT_IMPORT = getattr(cfv, \"FF_FIX_STRANDING_GUARD\", 1)\n\n\n"
          "def ff_fix_stranding_guard() -> bool:"),
         (AG, _ACC_G, "    return _exact_integer(_FF_FIX_STRANDING_GUARD_AT_IMPORT) != 0")],
        [_TG5_SHIP],
    ),
    "sw_guard_shipped0": (
        "FF_FIX_STRANDING_GUARD shipped 0",
        [(CFV, "\nFF_FIX_STRANDING_GUARD = 1\n", "\nFF_FIX_STRANDING_GUARD = 0\n")],
        [_TG5_SHIP],
    ),
}


# ============================================================================ the runner (as _ud_mutants_mv.py)

def _copy_tree(repo: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in repo.glob("*.py"):
        shutil.copy2(path, dest / path.name)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    shutil.copytree(repo / "src_extension", dest / "src_extension", ignore=ignore)
    shutil.copytree(repo / "tests", dest / "tests", ignore=ignore)


def _apply(dest: Path, edits: list[tuple[str, str, str]]) -> None:
    for rel, old, new in edits:
        path = dest / rel
        raw = path.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in raw else "\n"
        o, n = old.replace("\n", nl), new.replace("\n", nl)
        count = raw.count(o)
        if count != 1:
            raise SystemExit(f"MUTANT EDIT does not match exactly once ({count}) in {rel}: {old[:80]!r}")
        path.write_bytes(raw.replace(o, n).encode("utf-8"))


def _cases(xml_path: Path) -> dict[tuple[str, str], tuple[str, str]]:
    """(module stem, test name with its [case]) -> (passed | failed | error | skipped, first line of the message).
    Only "failed" (the test body raised - an assertion or an exception from the code under test) is a kill; an
    "error" (collection, import or fixture) is NOT: a mutant that does not import proves nothing."""
    out: dict[tuple[str, str], tuple[str, str]] = {}
    if not xml_path.exists():
        return out
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        stem = str(case.get("classname", "")).split(".")[-1]
        name = str(case.get("name", ""))
        status, message = "passed", ""
        for child in case:
            if child.tag in ("failure", "error", "skipped"):
                status = {"failure": "failed"}.get(child.tag, child.tag)
                message = " ".join(str(child.get("message", "")).split())[:150]
        out[(stem, name)] = (status, message)
    return out


def _node_result(node: str, cases) -> tuple[int, int, int, int, str]:
    """(cases collected, failed, errored, skipped, the first failure message) for one listed node."""
    path, name = node.split("::", 1)
    stem = Path(path).stem
    if "[" in name:
        hits = [s for (st, n), s in cases.items() if st == stem and n == name]
    else:
        hits = [s for (st, n), s in cases.items() if st == stem and (n == name or n.startswith(name + "["))]
    failed = [m for s, m in hits if s == "failed"]
    return (len(hits), len(failed), sum(1 for s, _ in hits if s == "error"), sum(1 for s, _ in hits if s == "skipped"),
            failed[0] if failed else "")


def _run(dest: Path, py: str, nodes: list[str]) -> tuple[int, dict, float]:
    env = dict(os.environ, PYTHONHASHSEED="0", MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1")
    xml_path = dest / "_junit.xml"
    t0 = time.time()
    proc = subprocess.run(
        [py, "-m", "pytest", *nodes, "-q", "-p", "no:cacheprovider", f"--junitxml={xml_path}",
         "-o", "junit_family=xunit2"],
        cwd=str(dest), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, _cases(xml_path), time.time() - t0


def check(repo: Path, work: Path, only: list[str], jobs: int, out: str) -> int:
    py = str(Path(sys.executable))
    chosen = [m for m in MUTANTS_MV if not only or m in only]
    work.mkdir(parents=True, exist_ok=True)
    base = work / "_base"
    _copy_tree(repo, base)
    for mid in chosen:                                   # every edit must match exactly once BEFORE anything runs
        probe = work / "_probe"
        if probe.exists():
            shutil.rmtree(probe)
        probe.mkdir()
        for rel in {e[0] for e in MUTANTS_MV[mid][1]}:
            (probe / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base / rel, probe / rel)
        _apply(probe, MUTANTS_MV[mid][1])
        shutil.rmtree(probe)

    def one(mid: str | None):
        dest = work / (mid or "_control")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(base, dest)
        if mid is None:
            nodes = sorted({n for m in chosen for n in MUTANTS_MV[m][2]})
        else:
            _apply(dest, MUTANTS_MV[mid][1])
            nodes = MUTANTS_MV[mid][2]
        rc, cases, secs = _run(dest, py, nodes)
        shutil.rmtree(dest, ignore_errors=True)
        return (mid or "CONTROL", rc, cases, secs, nodes)

    lines = [f"MVG Part 2d movement + guard mutation check (standalone runner) - repo {repo}",
             "one pytest call per mutant, no -x, per-test outcomes from the JUnit XML, PYTHONHASHSEED=0", ""]
    results = []
    with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [pool.submit(one, None)] + [pool.submit(one, m) for m in chosen]
        for fut in futures:
            results.append(fut.result())
    ok = True
    records = 0
    for mid, rc, cases, secs, nodes in results:
        rows = []
        killed_all = clean_all = True
        for node in nodes:
            n, failed, errored, skipped, message = _node_result(node, cases)
            name = node.split("::", 1)[1]
            if n == 0:
                rows.append(f"    MISSING  {name} (no case collected)")
                killed_all = clean_all = False
                continue
            if mid == "CONTROL":
                good = failed == 0 and errored == 0 and skipped == 0
                clean_all &= good
                if not good:
                    rows.append(f"    FAIL     {name} ({failed}/{n} fail, {errored} error, {skipped} skipped)")
                continue
            records += 1
            killed = failed > 0 and errored == 0
            killed_all &= killed
            frac = f" ({failed}/{n} cases fail)" if n > 1 else ""
            label = "KILLED  " if killed else ("ERROR   " if errored else "SURVIVED")
            rows.append(f"    {label} {name}{frac}")
            if message:
                rows.append(f"             first failure: {message}")
        if mid == "CONTROL":
            verdict = f"PASS (all {len(nodes)} listed nodes pass)" if clean_all else "FAIL (control does not pass!)"
            ok &= clean_all
            lines.append(f"{mid:17s} rc={rc} {verdict}  {secs:6.1f}s")
        else:
            verdict = ("KILLED (every listed test fails)" if killed_all
                       else "NOT KILLED (a listed test passes or only errors!)")
            ok &= killed_all
            lines.append(f"{mid:17s} rc={rc} {verdict}  {secs:6.1f}s")
            lines.append(f"    mutant: {MUTANTS_MV[mid][0]}")
        lines.extend(rows)
    lines.append("")
    lines.append(f"{len(chosen)} mutants, {records} (mutant, test) records")
    lines.append("ALL MUTANTS KILLED ON EVERY LISTED TEST, CONTROL PASSES" if ok else "MUTATION CHECK NOT CLEAN")
    text = "\n".join(lines)
    print(text)
    if out:
        Path(out).write_bytes((text + "\n").encode("utf-8"))
    shutil.rmtree(base, ignore_errors=True)
    return 0 if ok else 1


# ============================================================================ pins and the golden digest

def _import_test_module(root: Path):
    sys.path[:0] = [str(root), str(root / "tests")]
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.dont_write_bytecode = True
    import importlib
    return importlib.import_module("test_movement_fixes")


def pins(repo: Path) -> int:
    """Print T-NT's TNT_PINS / TOUCHED_PINS / REST_PINS / OTHER_PINS from `git show a20a2ef5:<file>` (the test's own
    helper _base_pins)."""
    mod = _import_test_module(repo)

    def git_text(rel: str) -> str:
        proc = subprocess.run(["git", "-C", str(repo), "show", f"{BASE_COMMIT}:{rel}"], capture_output=True,
                              check=True)
        return proc.stdout.decode("utf-8")

    for name, values in mod._base_pins(git_text).items():
        print(f"{name} = {{")
        for key in sorted(values):
            print(f"    {key!r}: {values[key]!r},")
        print("}")
    return 0


_GOLDEN_DRIVER = """
import os, sys
sys.dont_write_bytecode = True
sys.path[:0] = [os.getcwd(), os.path.join(os.getcwd(), "tests")]
os.environ.setdefault("MPLBACKEND", "Agg")
from _pytest.monkeypatch import MonkeyPatch
import test_movement_fixes as t
mp = MonkeyPatch()
digest = t._identity_run(mp, sys.argv[1])
mp.undo()
print("DIGEST", digest)
"""


def golden(repo: Path, work: Path) -> int:
    """T-ID-M's base digest: _identity_run in a copy of the checkout whose three changed source files are the base
    commit's (`git show a20a2ef5:<file>`; movement_paths.py stays - the base code never imports it, the test module
    does), under two hash seeds (the run must not depend on PYTHONHASHSEED)."""
    dest = work / "_golden_base"
    _copy_tree(repo, dest)
    for rel in ("agents.py", "wildfire_model.py", "common_fixed_variables.py"):
        proc = subprocess.run(["git", "-C", str(repo), "show", f"{BASE_COMMIT}:{rel}"], capture_output=True, check=True)
        (dest / rel).write_bytes(proc.stdout)
    (dest / "_golden_driver.py").write_text(_GOLDEN_DRIVER, encoding="utf-8")
    digests = []
    for seed in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "_golden_driver.py", "absent"], cwd=str(dest), env=env,
                              capture_output=True, text=True)
        found = [line.split()[1] for line in proc.stdout.splitlines() if line.startswith("DIGEST ")]
        if proc.returncode != 0 or not found:
            print(proc.stdout[-2000:], proc.stderr[-4000:])
            return 1
        digests.append(found[0])
        print(f"PYTHONHASHSEED={seed}: {found[0]}")
    shutil.rmtree(dest, ignore_errors=True)
    if len(set(digests)) != 1:
        print("THE BASE RUN DEPENDS ON PYTHONHASHSEED")
        return 1
    print(f"ID_GOLDEN_BASE = {digests[0]!r}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--work", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--out", default="")
    ap.add_argument("--pins", action="store_true")
    ap.add_argument("--golden", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    if args.pins:
        return pins(repo)
    if not args.work:
        raise SystemExit("--work is required")
    work = Path(args.work).resolve()
    if args.golden:
        return golden(repo, work)
    return check(repo, work, [m for m in args.only.split(",") if m], args.jobs, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
