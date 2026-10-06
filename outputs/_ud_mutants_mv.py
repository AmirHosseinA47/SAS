"""Urgency round Part 2 - the MOVEMENT mutants of outputs/urgency_part1.txt 22.6.2 (mutation check as 15.4).

MUTANTS_MV = {id: (description, [(file, old, new), ...], [pytest node ids])}. Every test in
tests/test_movement_fixes.py names its mutant ("MUTANT: <id>"); a mutant is the smallest exact-text source change
that removes what the test guards. `old` must match the CURRENT source exactly once. The test must FAIL on the
mutant and PASS on the unmutated source. outputs/_ud_mutants.py (15.4) may import MUTANTS_MV; this file also runs
the movement check on its own:

    python outputs/_ud_mutants_mv.py --repo E:/Projects/SAS_wt/urgency --work <scratch dir> [--only ma1_pass,mc3_hold]
        [--jobs 3] [--out <record file>]
    python outputs/_ud_mutants_mv.py --repo ... --pins            # T-NT pins from `git show 27744a28`
    python outputs/_ud_mutants_mv.py --repo ... --work ... --golden   # T-ID-M's base digest (27744a28 code)

The check copies the checkout's root *.py, src_extension/ and tests/ into --work (never touching the checkout),
applies one mutant per copy, runs exactly its listed nodes in ONE pytest call without -x (PYTHONHASHSEED=0) and
reads each node's outcome from the JUnit XML. A node naming one parametrized case must fail itself; a node naming a
whole parametrized function is killed when at least one case fails. A control copy must pass every listed node.
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
BASE_COMMIT = "27744a28"

# ---- frequently edited source lines (each must match the current source exactly once) ------------------------------
_A_CALL = "                path_step = self._approach_path_choice() if ff_approach_path() else None"
_A_STEP = "                if path_step is not None:\n                    self._fix_move(path_step, APPROACH_PATH_TIER)"
_A_ELSE = ("                if path_step is not None:\n                    self._fix_move(path_step, APPROACH_PATH_TIER)\n"
           "                else:\n                    self._move_toward(self.target_pos)")
_B_CALL = ("                self._retreat_on_route_choice()\n"
           "                if ff_retreat_keep_approach() and self.target_pos and not self.exiting\n"
           "                else None")
_B_STEP = "            if on_route is not None:\n                self._fix_move(on_route, RETREAT_ON_ROUTE_TIER)"
_C_CALL = "                    if ff_carry_replan():\n                        self._carry_replan_step()"
_FIELD = "        field = movement_paths.clean_distance_field(target, is_clean, in_bounds)\n        has_exit"
_ACC_A = "    return _exact_integer(getattr(cfv, \"FF_APPROACH_PATH\", 0)) == 1"
_ACC_B = "    return _exact_integer(getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 0)) == 1"
_ACC_C = "    return _exact_integer(getattr(cfv, \"FF_CARRY_REPLAN\", 0)) == 1"
_C1_CALL = ("        first = movement_paths.least_exposure_first_step(\n"
            "            start, is_burning, is_fire_adjacent, is_smoky, self._on_grid_boundary, in_bounds\n"
            "        )\n        if first is not None:\n            return \"replan\", first")
_C1_KEY = ("            key = (fa + (1 if is_fire_adjacent(n) else 0), sm + (1 if is_smoky(n) else 0), length + 1)")


def _t(name: str) -> str:
    return f"{T}::{name}"


# id -> (description, [(file, old, new), ...], [pytest node ids])
MUTANTS_MV: dict[str, tuple[str, list[tuple[str, str, str]], list[str]]] = {
    # ------------------------------------------------------------------ (a) FF_APPROACH_PATH
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
        "today's greedy only: the (a) branch is never taken at the call site",
        [(AG, _A_CALL, "                path_step = None")],
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
        [_t("test_ma8_z_rb_the_raise_is_todays_predicate_and_never_on_an_a_step")],
    ),
    # ------------------------------------------------------------------ (b) FF_RETREAT_KEEP_APPROACH
    "mb1_today": (
        "today's retreat always: the (b) choice is never consulted at the call site",
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
        [_t("test_mb4_an_unclean_victim_cell_is_never_entered_nor_a_pickup_made[on_her_cell]")],
    ),
    "mb4_exempt": (
        "the victim's own cell exempt from the clean test: the clean field is rooted at an unclean victim cell",
        [(MP, "    if not in_bounds(target) or not is_clean(target):\n        return {}",
          "    if not in_bounds(target):\n        return {}")],
        [_t("test_mb4_an_unclean_victim_cell_is_never_entered_nor_a_pickup_made[next_to_her]")],
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
    # ------------------------------------------------------------------ (c) FF_CARRY_REPLAN
    "mc1_len": (
        "C-1 cost length-only",
        [(MP, _C1_KEY, "            key = (0, 0, length + 1)")],
        [_t("test_mc1_least_exposure_first_step[A]"), _t("test_mc1_least_exposure_first_step[C]")],
    ),
    "mc1_comb": (
        "C-1 cost: one combined hazard count (fire-adjacent + smoky), then length",
        [(MP, _C1_KEY, "            key = (fa + (1 if is_fire_adjacent(n) else 0) + (1 if is_smoky(n) else 0), 0, "
                       "length + 1)")],
        [_t("test_mc1_least_exposure_first_step[B]")],
    ),
    "mc_greedy": (
        "the greedy fallback: with no clean path the carry takes today's greedy step toward exit_target, not C-1",
        [(AG, _C1_CALL, "        first = self._greedy_choice(self.exit_target, burning, smoky)\n"
                        "        if first is not None:\n            return \"replan\", first")],
        [_t("test_mc1_least_exposure_first_step[A]"), _t("test_mc1_least_exposure_first_step[C]"),
         _t("test_mc9_property_the_carry_plan_cost_falls_strictly")],
    ),
    "mc2_greedy": (
        "C-2's shelter replaced by today's greedy step toward exit_target",
        [(AG, "        step = movement_paths.shelter_step(\n"
              "            start, is_burning, is_fire_adjacent, is_smoky, lambda c: self._min_fire_distance(c, burning), "
              "in_bounds\n"
              "        )",
          "        step = self._greedy_choice(self.exit_target, burning, smoky)")],
        [_t("test_mc2_a_pocket_carry_shelters_at_the_safest_cell_and_stays[plain]")],
    ),
    "mc2_order_only": (
        "the C-2 walk by search order alone: a shortest pocket path ignoring exposure (the Part 2 build before R1-2)",
        [(MP, "            key = (length + 1, fa + (1 if is_fire_adjacent(n) else 0), sm + (1 if is_smoky(n) else 0))",
          "            key = (length + 1, 0, 0)")],
        [_t("test_mc2_the_shelter_walk_takes_the_least_exposed_shortest_path[smoky]"),
         _t("test_mc2_the_shelter_walk_takes_the_least_exposed_shortest_path[fire_adjacent]"),
         _t("test_mc2_property_the_shelter_step_is_a_least_exposed_shortest_step")],
    ),
    "mc2_burning_hold": (
        "a carrier standing on a BURNING cell treated as enclosed: C-2 skipped, it holds on the burning cell",
        [(AG, "        if step is None:\n            return \"hold\", start",
          "        if step is None or start in burning:\n            return \"hold\", start")],
        [_t("test_mc2_a_carrier_on_a_burning_cell_always_moves_off_it")],
    ),
    "mc2_smoky": (
        "the C-2 target's not-smoky key removed",
        [(MP, "    target = max(candidates, key=lambda c: (fire_dist(c), 0 if is_smoky(c) else 1, -depth[c], -rank[c]))",
          "    target = max(candidates, key=lambda c: (fire_dist(c), -depth[c], -rank[c]))")],
        [_t("test_mc2_a_pocket_carry_shelters_at_the_safest_cell_and_stays[smoky_tie]")],
    ),
    "mc3_hold": (
        "C-3's hold skipped: an enclosed carrier runs today's _move_toward (route_blocked, the drop)",
        [(AG, "        else:\n            self._exit_leg_hold()\n        return kind",
          "        else:\n            self._move_toward(self.exit_target)\n        return kind")],
        [_t("test_mc3_an_enclosed_carrier_holds_and_keeps_its_victim")],
    ),
    "mc4_removed": (
        "the C-4 clause removed from _find_active_firefighter_for_victim",
        [(WM, "                if not (\n                    status == \"route_blocked\"\n"
              "                    and getattr(ff_marker, \"exiting\", False)\n"
              "                    and getattr(ff_marker, \"pos\", None) is not None\n"
              "                    and agents.ff_carry_replan()\n                ):\n                    continue",
          "                continue")],
        [_t("test_mc4_a_latched_carriers_victim_is_in_custody")],
    ),
    "mc4_approach": (
        "the C-4 clause applied to approaching units too (the exiting test dropped)",
        [(WM, "                    and getattr(ff_marker, \"exiting\", False)\n"
              "                    and getattr(ff_marker, \"pos\", None) is not None\n"
              "                    and agents.ff_carry_replan()",
          "                    and getattr(ff_marker, \"pos\", None) is not None\n"
          "                    and agents.ff_carry_replan()")],
        [_t("test_mc4_a_latched_approaching_unit_is_still_not_returned")],
    ),
    "mc5_hold": (
        "the corpse guard (C-5) keyed on HOLD only",
        [(WM, "                    and (agents.ff_exit_leg_hold() or agents.ff_carry_replan())  # + urgency round C-5",
          "                    and agents.ff_exit_leg_hold()")],
        [_t("test_mc5_a_carrier_dying_in_custody_leaves_one_dead_victim")],
    ),
    "mc6_dep": (
        "the enforced dependency (MODE 2 and SERVED 1) removed from ff_carry_replan",
        [(AG, "    if ff_exit_leg_mode() != 2 or ff_exit_leg_served() != 1:\n        return False\n" + _ACC_C, _ACC_C)],
        [_t("test_mc6_c_c4_and_c5_are_inert_without_mode_2_and_served_1")],
    ),
    "mc7_c1": (
        "C-0 skipped: C-1 used although a clean path exists",
        [(AG, "        if first is not None:\n            return \"path\", first",
          "        if first is not None and False:\n            return \"path\", first")],
        [_t("test_mc7_c0_is_value_identical_to_mode_2_with_a_clean_path")],
    ),
    "mc8_relabel": (
        "the relabel removed from C-1 and C-2 (moves and the stay)",
        [(AG, "        elif kind == \"replan\":\n            self._fix_move(cell, CARRY_REPLAN_TIER)\n"
              "        elif kind == \"shelter\":\n            self._fix_move(cell, CARRY_SHELTER_TIER)\n"
              "        elif kind == \"shelter_stay\":\n            self._relabel_if_route_blocked()\n",
          "        elif kind == \"replan\":\n            self._last_move_tier = CARRY_REPLAN_TIER\n"
          "            self.model.grid.move_agent(self, cell)\n"
          "        elif kind == \"shelter\":\n            self._last_move_tier = CARRY_SHELTER_TIER\n"
          "            self.model.grid.move_agent(self, cell)\n"
          "        elif kind == \"shelter_stay\":\n")],
        [_t("test_mc8_c1_and_c2_raise_nothing_and_relabel_a_route_blocked_carry")],
    ),
    # ------------------------------------------------------------------ ALL
    "safe_clean": (
        "the clean filter dropped from the shared predicate: CLEAN = in bounds and not burning",
        [(AG, "            if grid.out_of_bounds(cell) or cell in burning or cell in smoky:\n                return False\n"
              "            cx, cy = cell\n            for ox, oy in EXIT_LEG_SEARCH_ORDER:\n"
              "                if (cx + ox, cy + oy) in burning:\n                    return False\n            return True",
          "            if grid.out_of_bounds(cell) or cell in burning:\n                return False\n            return True")],
        [_t("test_tsafem_property_no_fix_enters_fire_and_a_b_land_clean_in_a_gesc_region")],
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
    "sw_truthy_c": (
        "FF_CARRY_REPLAN read by truthiness instead of an exact 1",
        [(AG, _ACC_C, "    return bool(getattr(cfv, \"FF_CARRY_REPLAN\", 0))")],
        [_t("test_tswm_off_carry_replan")],
    ),
    "sw_enter_a": (
        "(a)'s pure choice evaluated while FF_APPROACH_PATH is off (the result discarded)",
        [(AG, _A_CALL, _A_CALL.replace("else None", "else (self._approach_path_choice() and None)"))],
        [_t("test_tswm_off_never_enters_new_code")],
    ),
    "sw_enter_b": (
        "(b)'s pure choice evaluated while FF_RETREAT_KEEP_APPROACH is off (the result discarded)",
        [(AG, _B_CALL, _B_CALL.replace("                else None", "                else (self._retreat_on_route_choice() and None)"))],
        [_t("test_tswm_off_never_enters_new_code")],
    ),
    "sw_enter_c": (
        "(c)'s pure choice evaluated while FF_CARRY_REPLAN is off (the result discarded)",
        [(AG, _C_CALL, "                    if ff_carry_replan() or self._carry_replan_choice() is None:\n"
                       "                        self._carry_replan_step()")],
        [_t("test_tswm_off_never_enters_new_code")],
    ),
    "id_a_off": (
        "the (a) branch taken when its switch is off",
        [(AG, _A_CALL, "                path_step = self._approach_path_choice()")],
        [_t("test_tidm_switches_absent_and_zero_are_identical_and_equal_the_base")],
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
        "one line changed in Firefighter.advance outside the three fix blocks (the standby record's text)",
        [(AG, "                f\"standby at edge {self.pos}\",", "                f\"standby at the edge {self.pos}\",")],
        [_t("test_tnt_touched_functions_differ_from_the_base_only_by_the_registered_edits")],
    ),
}


# ============================================================================ the runner (as _dp_mutants.py)

def _copy_tree(repo: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in repo.glob("*.py"):
        shutil.copy2(path, dest / path.name)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
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
    env = dict(os.environ, PYTHONHASHSEED="0", MPLBACKEND="Agg")
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

    lines = [f"urgency Part 2 movement mutation check - repo {repo}",
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
            lines.append(f"{mid:13s} rc={rc} {verdict}  {secs:6.1f}s")
        else:
            verdict = ("KILLED (every listed test fails)" if killed_all
                       else "NOT KILLED (a listed test passes or only errors!)")
            ok &= killed_all
            lines.append(f"{mid:13s} rc={rc} {verdict}  {secs:6.1f}s")
            lines.append(f"    mutant: {MUTANTS_MV[mid][0]}")
        lines.extend(rows)
    lines.append("")
    lines.append(f"{len(chosen)} mutants, {records} (mutant, test) records")
    lines.append("ALL MUTANTS KILLED ON EVERY LISTED TEST, CONTROL PASSES" if ok else "MUTATION CHECK NOT CLEAN")
    text = "\n".join(lines)
    print(text)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    shutil.rmtree(base, ignore_errors=True)
    return 0 if ok else 1


# ============================================================================ pins and the golden digest

def _import_test_module(root: Path):
    sys.path[:0] = [str(root), str(root / "tests")]
    os.environ.setdefault("MPLBACKEND", "Agg")
    import importlib
    return importlib.import_module("test_movement_fixes")


def pins(repo: Path) -> int:
    """Print T-NT's TNT_PINS / TOUCHED_PINS / REST_PINS from `git show 27744a28:<file>` (the test's own helpers)."""
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
    commit's (`git show 27744a28:<file>`), under two hash seeds (the run must not depend on PYTHONHASHSEED)."""
    dest = work / "_golden_base"
    _copy_tree(repo, dest)
    for rel in ("agents.py", "wildfire_model.py", "common_fixed_variables.py"):
        proc = subprocess.run(["git", "-C", str(repo), "show", f"{BASE_COMMIT}:{rel}"], capture_output=True, check=True)
        (dest / rel).write_bytes(proc.stdout)
    (dest / "_golden_driver.py").write_text(_GOLDEN_DRIVER, encoding="utf-8")
    digests = []
    for seed in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, MPLBACKEND="Agg")
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
