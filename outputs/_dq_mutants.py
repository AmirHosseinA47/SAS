"""Dispatch round 2, Part 2 - the mutation check of outputs/dispatch2_part1.txt 13 (4): round 1's dispatch mutants
(outputs/_dp_mutants.py) RE-RUN against the corrected dispatcher - each re-targeted at the code that now carries the
same behaviour, or RETIRED with a reason when the behaviour it removed no longer exists (RETIRED below, printed in the
record) - plus the round-2 mutants of C1, C2, R-1 and R-2 (13 (3)).

The engine is round 1's, unchanged: for each mutant it copies the source (root *.py, src_extension/, tests/) of the
given checkout into a scratch directory, applies the mutant as exact text replacements (each must match exactly once),
runs ALL the tests listed with it in one pytest call WITHOUT -x, and reads each test's own outcome from the JUnit XML -
PER TEST. A listed node naming one parametrized case must fail itself; a listed node naming a whole parametrized
function is killed when at least one of its cases fails (the record gives k/n). A mutant is KILLED only when EVERY
listed node is killed. A control copy (no mutant) must pass every listed node.

    python outputs/_dq_mutants.py --repo E:\\Projects\\SAS_wt\\dispatch --work E:\\Projects\\SAS_wt\\_dqmut
        [--only c1_l2,tr6] [--jobs 6] [--out outputs/_dq_mutants_result.txt]

Never touches the checkout itself. PYTHONHASHSEED=0 in every run (set iteration order fixed).
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

JD = "src_extension/planning/joint_dispatch.py"
WM = "wildfire_model.py"
AG = "agents.py"
CFV = "common_fixed_variables.py"
TJ = "tests/test_dispatch_joint.py"
TR = "tests/test_dispatch_reassign.py"
TI = "tests/test_dispatch_information.py"
TB = "tests/test_base_station.py"
TC = "tests/test_dispatch2_corrections.py"
TINV = f"{TI}::test_tinv_invariants_hold_at_every_frame_of_a_real_run"

_SKIP_TAIL = "        if agents.dispatch_joint():\n            # Dispatch round (design 5.7): no pairing here"


def _skip_except(itype: str) -> str:
    return _SKIP_TAIL.replace("if agents.dispatch_joint():", f"if agents.dispatch_joint() and itype != \"{itype}\":")


_KEY = "        return (-n, -n_clean, total, worst, reused, ids)"
_STILL = "            still = [v for v in waiting if v not in bound_victims]"
_STEP4 = (
    "            still = [v for v in waiting if v not in bound_victims]\n"
    "            if again and still:\n"
    "                dist4 = {(u, v): dstar(u, v) for u in again for v in still}\n"
    "                clean4 = {(u, v): clean_ok(u, v) for u in again for v in still}\n"
    "                for pair in _jd.solve_fill(again, still, dist4, ledger, clean=clean4):\n"
    "                    self._dispatch_fill_bind(\n"
    "                        view, pair.victim, pair.unit, pair.distance, phase, kind=\"second_fill\", stage=4\n"
    "                    )\n"
)
_STEP4_A2 = (
    "            still = [v for v in list(waiting) + list(latched) if v not in bound_victims]\n"
    "            if again and still:\n"
    "                still_latched = [v for v in latched if v not in bound_victims]\n"
    "                dist4 = {(u, v): dstar(u, v) for u in again for v in still}\n"
    "                clean4 = {(u, v): clean_ok(u, v) for u in again for v in still}\n"
    "                for pair in _jd.solve_fill(again, still, dist4, ledger, clean=clean4, capped=still_latched):\n"
    "                    if pair.victim in latched:\n"
    "                        self._dispatch_replace(\n"
    "                            view, pair.victim, list(victims[pair.victim][\"binders\"]), pair.unit,\n"
    "                            \"joint_replace_latched\", pair.distance, phase, kind=\"latch_fill\", stage=4,\n"
    "                        )\n"
    "                    else:\n"
    "                        self._dispatch_fill_bind(\n"
    "                            view, pair.victim, pair.unit, pair.distance, phase, kind=\"second_fill\", stage=4\n"
    "                        )\n"
)
_FILL2 = (
    "            for pair in _jd.solve_fill(free, fill_victims, dist, ledger, clean=clean2):\n"
    "                ok = self._dispatch_fill_bind(\n"
    "                    view, pair.victim, pair.unit, pair.distance, phase, kind=\"fill\", stage=2\n"
    "                )\n"
)
_FILL2_R1 = (
    "            for pair in _jd.solve_fill(free, fill_victims, dist, ledger, clean=clean2,\n"
    "                                       capped=latched if reassign else []):\n"
    "                if reassign and pair.victim in latched:\n"
    "                    ok = self._dispatch_replace(\n"
    "                        view, pair.victim, list(victims[pair.victim][\"binders\"]), pair.unit,\n"
    "                        \"joint_replace_latched\", pair.distance, phase, kind=\"latch_fill\", stage=2,\n"
    "                    )\n"
    "                else:\n"
    "                    ok = self._dispatch_fill_bind(\n"
    "                        view, pair.victim, pair.unit, pair.distance, phase, kind=\"fill\", stage=2\n"
    "                    )\n"
)

# id -> (description, [(file, old, new), ...], [pytest node ids])
MUTANTS: dict[str, tuple[str, list[tuple[str, str, str]], list[str]]] = {
    # ------------------------------------------------------------------ LIMIT 2 (round 1, re-targeted)
    "tj1": (
        "solve_fill replaced by per-victim greedy in victim-index order",
        [(JD,
          "    walk(0, frozenset(), [])\n    return sorted(best_pairs, key=lambda p: id_index(p.victim))",
          "    taken: set[str] = set()\n    greedy: list[FillPair] = []\n    for victim in victim_list:\n"
          "        cands = sorted((d, id_index(u), u, r, cl) for u in unit_list if u not in taken\n"
          "                       for (vv, d, r, cl) in options[u] if vv == victim)\n"
          "        if cands:\n            d, _, u, r, cl = cands[0]\n            taken.add(u)\n"
          "            greedy.append(FillPair(victim=victim, unit=u, distance=d, reused=r, clean=cl))\n"
          "    return greedy")],
        [f"{TJ}::test_tj1_crossing_pairs_are_uncrossed"],
    ),
    "tj2": (
        "the fill's route distance replaced by Manhattan distance",
        [(WM, "            dist = {(u, v): dstar(u, v) for u in free for v in fill_victims}",
              "            dist = {(u, v): abs(unit_cell(u)[0] - victims[v][\"cell\"][0])\n"
              "                    + abs(unit_cell(u)[1] - victims[v][\"cell\"][1]) for u in free for v in fill_victims}")],
        [f"{TJ}::test_tj2_route_aware_choice_through_a_numpy_bool_fire_wall"],
    ),
    "tj2b": (
        "the burning set built by identity with True (blind to the simulator's numpy bools)",
        [(WM,
          "        burning = self._active_burning_cells()\n        smoky: set[tuple[int, int]] = set()",
          "        burning = {(int(a.pos[0]), int(a.pos[1])) for a in self.schedule.agents\n"
          "                   if type(a) is agents.Fire and a.pos is not None and a.is_burning() is True}\n"
          "        smoky: set[tuple[int, int]] = set()")],
        [f"{TJ}::test_tj2_route_aware_choice_through_a_numpy_bool_fire_wall"],
    ),
    "tj3": (
        "the key puts victim index before route time (victim-index order)",
        [(JD, _KEY, "        return (-n, -n_clean, ids, total, worst, reused)")],
        [f"{TJ}::test_tj3_scarcity_serves_the_nearest_by_route"],
    ),
    "tj4": (
        "J iterates units and victims in insertion order with a first-found fit (inputs unsorted, L5 key removed, "
        "the view's victims in registry order)",
        [(JD, "    unit_list = sorted({str(u) for u in units}, key=id_index)\n"
              "    victim_list = sorted({str(v) for v in victims}, key=id_index)",
              "    unit_list = list(dict.fromkeys(str(u) for u in units))\n"
              "    victim_list = list(dict.fromkeys(str(v) for v in victims))"),
         (JD, _KEY, "        return (-n, -n_clean, total, worst, reused)"),
         (WM, "        for ff_id, ff_marker in sorted(ff_markers.items(), key=lambda kv: _jd.id_index(str(kv[0]))):",
              "        for ff_id, ff_marker in ff_markers.items():"),
         (WM, "        detected = sorted((str(v) for v in _detected_victim_ids(self)), key=_jd.id_index)",
              "        detected = [str(v) for v in v_markers if str(v) in _detected_victim_ids(self)]")],
        [f"{TJ}::test_tj4_order_independence_pure", f"{TJ}::test_tj4_order_independence_model[units]",
         f"{TJ}::test_tj4_order_independence_model[victims]"],
    ),
    "tj4i": (
        "the generic pairing tail runs for victim_confirmed incidents (per-incident greedy in drain order)",
        [(WM, _SKIP_TAIL, _skip_except("victim_confirmed"))],
        [f"{TJ}::test_tj4_order_independence_model[incidents]"],
    ),
    "tj5": (
        "an infinite route distance replaced by a large finite cost",
        [(JD, "    if here not in blocked_set:\n        return None", "    if here not in blocked_set:\n        return 10_000")],
        [f"{TJ}::test_tj5_closed_route_is_never_bound"],
    ),
    "tj6": (
        "J skips a solve point unless an incident was drained since the last one",
        [(WM, "            self._dispatch_note_pending(vid, itype)\n",
              "            self._dispatch_note_pending(vid, itype)\n            self._dispatch_incident_flag = True\n"),
         (WM, "        reassign = agents.dispatch_reassign()\n        post = phase == \"post\"",
              "        if not getattr(self, \"_dispatch_incident_flag\", False):\n            return\n"
              "        self._dispatch_incident_flag = False\n"
              "        reassign = agents.dispatch_reassign()\n        post = phase == \"post\"")],
        [f"{TJ}::test_tj6_a_unit_freed_by_a_death_release_is_bound_the_same_step"],
    ),
    "tjpre": (
        "the J-pre call removed from _run_execution",
        [(WM, "        self._joint_dispatch_point(\"pre\")\n", "")],
        [f"{TJ}::test_tj6_a_unit_free_between_steps_is_paired_at_j_pre_before_moving"],
    ),
    "tj7": (
        "the generic pairing tail is not skipped for route_blocked incidents",
        [(WM, _SKIP_TAIL, _skip_except("route_blocked"))],
        [f"{TJ}::test_tj7_no_pairing_mid_advance_and_a_same_step_detection_is_seen",
         f"{TJ}::test_tj7_real_step_no_assign_inside_the_advance"],
    ),
    "reason_const": (
        "every fill carries joint_initial (the victim's pending cause dropped from the reason)",
        [(WM, "        reason = self._DISPATCH_FILL_REASONS.get(pending.get(vid, \"initial\"), \"joint_initial\")",
              "        reason = \"joint_initial\"")],
        [f"{TJ}::test_tj7_no_pairing_mid_advance_and_a_same_step_detection_is_seen",
         f"{TJ}::test_tj8_a_casualty_victim_is_rebound_with_the_casualty_reason"],
    ),
    "tj8": (
        "casualty victims handed to select_rescue_assignment (the legacy tail runs)",
        [(WM, _SKIP_TAIL, _skip_except("firefighter_casualty"))],
        [f"{TJ}::test_tj8_casualty_with_an_empty_pool_waits_and_is_counted"],
    ),
    "tj8cnt": (
        "the would-have-been counter counts every casualty incident",
        [(WM, "        if itype != \"firefighter_casualty\" or action != \"mark_unreachable\":",
              "        if itype != \"firefighter_casualty\":")],
        [f"{TJ}::test_tj8_a_returning_unit_means_no_would_have_been_writeoff"],
    ),
    "tj8cf": (
        "the counterfactual ignores the units it already took earlier in the same step",
        [(WM, "                    entry[\"available\"] = False", "                    pass")],
        [f"{TJ}::test_tj8_counterfactual_takes_units_in_drain_order"],
    ),
    "tj9": (
        "ids compared as strings",
        [(JD, "    return (int(match.group(1)) if match else 10**9, text)", "    return (0, text)")],
        [f"{TJ}::test_tj9_integer_tie_break"],
    ),
    "tj10": (
        "latched-held victims excluded from the fill under Limit 2 alone too (ruling D-7 broken)",
        [(WM, "        fill_victims = list(waiting) if reassign else list(waiting) + list(latched)",
              "        fill_victims = list(waiting)")],
        [f"{TJ}::test_tj10_latched_held_victim_gets_a_second_claimant_under_limit2_alone"],
    ),
    "tj12": (
        "the dispatch_reassignment branch removed",
        [(WM, "        if reason_l.startswith(\"reassign_\") or reason_l == \"joint_replace_latched\":",
              "        if False:")],
        [f"{TJ}::test_tj12_reason_strings_and_event_types"],
    ),
    "tj13": (
        "the ledger counted inside J only (the sink line removed)",
        [(WM, "            if agents.dispatch_joint():\n"
              "                # Dispatch round (design 5.6): the ledger counts every bind at this single sink.\n"
              "                self._dispatch_ledger_record(ff_id, vid)\n",
              "")],
        [f"{TJ}::test_tj13_the_ledger_counts_every_bind_at_the_single_sink"],
    ),
    # ------------------------------------------------------------------ LIMIT 3 (round 1, re-targeted)
    "tr1m": (
        "the stall rule disabled (no stall replacement at all)",
        [(JD, "    stalled = [c for c in contests if c.count >= stall_steps]", "    stalled = []")],
        [f"{TR}::test_tr1_model_level_stall_replacement_at_exactly_s"],
    ),
    "tfreeze": (
        "FROZEN decided by the incumbent alone (the spare leg of 6.3 dropped)",
        [(WM, "            frozen = not (clean_ok(uid, vid) or any(clean_ok(f, vid) for f in free))",
              "            frozen = not clean_ok(uid, vid)")],
        [f"{TR}::test_tr1_model_a_spare_with_a_clean_approach_unfreezes_the_count"],
    ),
    "tclean3": (
        "the challenger's clean-approach verdict taken as True",
        [(WM, "                clean3[(b, vid)] = clean_ok(b, vid)", "                clean3[(b, vid)] = True")],
        [f"{TR}::test_tr4_model_a_spare_without_a_clean_approach_is_never_sent",
         f"{TC}::test_r2_a_margin_challenger_without_a_clean_approach_is_refused"],
    ),
    "tr3": (
        "the lost-time charge removed (d*(B) < delta)",
        [(JD, "                if not int(d) < c.delta + c.count:", "                if not int(d) < c.delta:")],
        [f"{TR}::test_tr3_stall_charge_boundary"],
    ),
    "tr4": (
        "P = 1",
        [(JD, "            elif int(c.persist.get(unit, 0) or 0) < margin_persist:",
              "            elif int(c.persist.get(unit, 0) or 0) < 1:")],
        [f"{TR}::test_tr4_margin_needs_m_steps_for_p_evaluations"],
    ),
    "tr5": (
        "the custody / finisher / co-location exclusions removed",
        [(WM, "            if custody:\n                continue\n            if not binders:",
              "            if False:\n                continue\n            if not binders:")],
        [f"{TR}::test_tr5_a_carrier_or_finisher_is_never_touched[exiting]",
         f"{TR}::test_tr5_a_carrier_or_finisher_is_never_touched[rescue_completed]",
         f"{TR}::test_tr5_colocated_latched_is_custody_under_limit2_alone"],
    ),
    "tr5og": (
        "the off-grid exclusion removed from the donor (spare) predicate",
        [(WM, "            if self._firefighter_available_for_dispatch(ff_marker):\n                free.append(uid)",
              "            if self._firefighter_available_for_dispatch(ff_marker) or getattr(ff_marker, \"off_grid\", False):\n"
              "                free.append(uid)")],
        [f"{TR}::test_tr5_an_off_grid_unit_is_never_a_challenger"],
    ),
    "tr6": (
        "only_ff_id ignored (every binder released)",
        [(WM, "            if only and ff_id_s != only:\n                continue", "            if False:\n                continue")],
        [f"{TR}::test_tr6_a_margin_replacement_uses_the_release_path_cleanly", TINV],
    ),
    "tr7": (
        "release-then-assign",
        [(WM, "        if not refused:\n            result = self._physical_rescue_executor().execute_physical_command(",
              "        if not refused:\n            for old in old_units:\n"
              "                self._release_other_claimants(vid, marker, \"\", reason, only_ff_id=old)\n"
              "            result = self._physical_rescue_executor().execute_physical_command(")],
        [f"{TR}::test_tr7_a_refused_assign_changes_nothing"],
    ),
    "tr8": (
        "the latched binder is not released by the (step-3) latch-fill",
        [(WM, "                    view, rep.victim, [rep.old_unit], rep.new_unit, reason, rep.distance, phase,",
              "                    view, rep.victim, [] if rep.latched else [rep.old_unit], rep.new_unit, reason,\n"
              "                    rep.distance, phase,")],
        [f"{TR}::test_tr8_latched_incumbent_is_replaced_by_a_latch_fill_only_after_the_charge"],
    ),
    "tr8capm": (
        "the LATCH-FILL cap removed from the replacement plan (b <= 1 read as any b)",
        [(JD, "        return b <= 1 if c.latched else b == 0", "        return True if c.latched else b == 0")],
        [f"{TR}::test_tr8_no_allowed_unit_keeps_the_latched_binder"],
    ),
    "tr8capp": (
        "the LATCH-FILL cap removed from the pure solver (b >= 2 allowed for a capped victim) - DEAD CODE in the round-2 "
        "model, which never passes `capped` (Limit 3's LATCH-FILL is a step-3 decision; review F9): kept because the "
        "pure function keeps the parameter",
        [(JD, "            if victim in capped_set and b >= 2:\n                continue",
              "            if False:\n                continue")],
        [f"{TJ}::test_tj11_coverage_before_reuse_and_nearest_over_fresh"],
    ),
    "tr9": (
        "the clean-approach test removed (every unit has a clean approach)",
        [(WM, "            return c_at(vid, unit_cell(uid)) is not None", "            return True")],
        [f"{TR}::test_tr9_no_clean_approach_freezes_the_stall[ring]",
         f"{TR}::test_tr9_no_clean_approach_freezes_the_stall[band]"],
    ),
    "tr9rel": (
        "a stalled incumbent released before checking for a qualifying spare",
        [(WM, "        if spares and contests:\n",
              "        for c in contests:\n            if c.count >= stall_steps:\n"
              "                self._release_other_claimants(c.victim, view[\"victims\"][c.victim][\"marker\"], \"\",\n"
              "                                              \"reassign_stall\", only_ff_id=c.incumbent)\n"
              "        if spares and contests:\n")],
        [f"{TR}::test_tr9_a_stall_with_no_spare_releases_nothing"],
    ),
    "tr10wcap": (
        "step 4 caps W victims (capped = every victim offered)",
        [(WM, "                for pair in _jd.solve_fill(again, still, dist4, ledger, clean=clean4):",
              "                for pair in _jd.solve_fill(again, still, dist4, ledger, clean=clean4, capped=still):")],
        [f"{TR}::test_tr10_c_the_w_leg_binds_a_released_unit_across_an_artificial_bridge"],
    ),
    "tr10bound": (
        "step 4 offers every W victim, bound in step 2 or not",
        [(WM, _STILL, "            still = [v for v in waiting]")],
        [f"{TR}::test_tr10_d_a_victim_bound_in_step_2_is_not_offered_again_at_step_4"],
    ),
    "tr10c": (
        "step 4 offers nothing",
        [(WM, _STILL, "            still = []")],
        [f"{TR}::test_tr10_c_the_w_leg_binds_a_released_unit_across_an_artificial_bridge"],
    ),
    "tstage": (
        "step-2 FILL binds tagged stage 4",
        [(WM, "view, pair.victim, pair.unit, pair.distance, phase, kind=\"fill\", stage=2",
              "view, pair.victim, pair.unit, pair.distance, phase, kind=\"fill\", stage=4")],
        [f"{TR}::test_stage_field_on_j_pre_refused_and_latch_fill_events"],
    ),
    "tstage_rec": (
        "the stage dropped from refused and aborted records",
        [(WM, "phase=phase, kind=kind if ok else kind + \"_refused\", stage=int(stage),",
              "phase=phase, kind=kind if ok else kind + \"_refused\", stage=int(stage) if ok else None,"),
         (WM, "phase=phase, kind=kind + \"_aborted\", stage=int(stage),",
              "phase=phase, kind=kind + \"_aborted\","),
         ],
        [f"{TR}::test_stage_field_on_j_pre_refused_and_latch_fill_events"],
    ),
    "tflip": (
        "the b = 0 rule for REPLACE removed",
        [(JD, "        return b <= 1 if c.latched else b == 0", "        return b <= 1 if c.latched else True")],
        [f"{TR}::test_tflip_a_no_reversal_by_a_cost_decision",
         f"{TR}::test_tflip_b_alternating_advantage_replaces_at_most_once"],
    ),
    "tflip_vac": (
        "plan_replacements_detail returns nothing (the simulator would test no REPLACE)",
        [(JD, "    spare_list = sorted({str(s) for s in spares}, key=id_index)\n    used: set[str] = set()\n"
              "    out: list[Replacement] = []",
              "    return [], []\n    spare_list = sorted({str(s) for s in spares}, key=id_index)\n"
              "    used: set[str] = set()\n    out: list[Replacement] = []")],
        [f"{TR}::test_tflip_a_simulator_is_not_vacuous"],
    ),
    # ------------------------------------------------------------------ INFORMATION and SWITCHES (round 1, unchanged)
    "tinfo": (
        "the builder takes every victim (undetected ones read and used)",
        [(WM, "        detected = sorted((str(v) for v in _detected_victim_ids(self)), key=_jd.id_index)",
              "        detected = sorted((str(v) for v in v_markers), key=_jd.id_index)")],
        [f"{TI}::test_tinfo_a_no_attribute_of_an_undetected_victim_is_read[0]",
         f"{TI}::test_tinfo_a_no_attribute_of_an_undetected_victim_is_read[1]",
         f"{TI}::test_tinfo_b_metamorphic_undetected_truth_changes_nothing",
         f"{TI}::test_tinfo_b_metamorphic_applied_binds",
         f"{TI}::test_tinfo_b_metamorphic_over_a_short_real_run"],
    ),
    "tinfo_read": (
        "the builder READS one undetected victim's marker cell (13.3's named T-INFO-a mutant: a read, not a use)",
        [(WM, "        detected = sorted((str(v) for v in _detected_victim_ids(self)), key=_jd.id_index)\n",
              "        detected = sorted((str(v) for v in _detected_victim_ids(self)), key=_jd.id_index)\n"
              "        _peek = [getattr(m, \"pos\", None) for v, m in v_markers.items() if str(v) not in detected][:1]\n")],
        [f"{TI}::test_tinfo_a_no_attribute_of_an_undetected_victim_is_read[0]",
         f"{TI}::test_tinfo_a_no_attribute_of_an_undetected_victim_is_read[1]"],
    ),
    "tinfoc": (
        "J's builder calls get_rescue_operational_snapshot",
        [(WM, "        detected = sorted((str(v) for v in _detected_victim_ids(self)), key=_jd.id_index)",
              "        _snapshot = self.get_rescue_operational_snapshot()\n"
              "        detected = sorted((str(v) for v in _detected_victim_ids(self)), key=_jd.id_index)")],
        [f"{TI}::test_tinfo_c_source_never_iterates_victims_nor_calls_the_snapshot"],
    ),
    "tsw_dep": (
        "the DISPATCH_REASSIGN dependency on DISPATCH_JOINT removed",
        [(AG, "    if not dispatch_joint():\n        return False\n    return _exact_integer(getattr(cfv, \"DISPATCH_REASSIGN\", 0)) == 1",
              "    return _exact_integer(getattr(cfv, \"DISPATCH_REASSIGN\", 0)) == 1")],
        [f"{TI}::test_tsw_missing_is_off_and_reassign_needs_joint", f"{TI}::test_tsw_off_for_everything_else"],
    ),
    "tsw_reassign": (
        "DISPATCH_REASSIGN read by truthiness instead of an exact 1",
        [(AG, "    return _exact_integer(getattr(cfv, \"DISPATCH_REASSIGN\", 0)) == 1",
              "    return bool(getattr(cfv, \"DISPATCH_REASSIGN\", 0))")],
        [f"{TI}::test_tsw_reassign_needs_its_own_exact_one_while_joint_is_on"],
    ),
    "tsw_exact": (
        "DISPATCH_JOINT compared with 1 without the exact-integer reading",
        [(AG, "    return _exact_integer(getattr(cfv, \"DISPATCH_JOINT\", 0)) == 1",
              "    return getattr(cfv, \"DISPATCH_JOINT\", 0) == 1")],
        [f"{TI}::test_tsw_on_only_on_an_exact_one"],
    ),
    "tsw_param": (
        "a non-positive step parameter accepted",
        [(AG, "    if value is None or value <= 0:\n        return default", "    if value is None:\n        return default")],
        [f"{TI}::test_tsw_step_parameters"],
    ),
    "tsw_shipped": (
        "DISPATCH_JOINT shipped 0 (re-anchored at THE DISPATCH FLIP: the shipped default is 1 / 1)",
        [(CFV, "\nDISPATCH_JOINT = 1\nDISPATCH_REASSIGN = 1", "\nDISPATCH_JOINT = 0\nDISPATCH_REASSIGN = 1")],
        [f"{TI}::test_tsw_shipped_defaults", f"{TB}::test_shipped_defaults"],
    ),
    "tsw_gate": (
        "the gate at the top of _joint_dispatch_point removed",
        [(WM, "        if not agents.dispatch_joint():\n            return\n        reassign = agents.dispatch_reassign()",
              "        reassign = agents.dispatch_reassign()")],
        [f"{TI}::test_tsw_with_joint_off_j_is_never_entered_and_nothing_changes"],
    ),
    # ------------------------------------------------------------------ ROUND 2: R-1 (progress and d*)
    "q_prevonly": (
        "R-1: the history kept to the last cell (progress judged against the previous cell only)",
        [(JD, "    return replace(\n        state,\n        history=grown,\n        k=state.k + (0 if frozen else 1),",
              "    return replace(\n        state,\n        history=(cell,),\n        k=state.k + (0 if frozen else 1),")],
        [f"{TR}::test_tr1_a_looping_unit_stalls_whatever_the_fire_and_the_victim_do",
         f"{TR}::test_tr1_model_burnout_still_stalls"],
    ),
    "q_by2": (
        "R-1: progress must beat the history's least distance by 2",
        [(JD, "        or (best_d is not None and int(d_now) < best_d)",
              "        or (best_d is not None and int(d_now) < best_d - 1)")],
        [f"{TR}::test_tr2_no_false_stall"],
    ),
    "q_feed": (
        "R-1: the model feeds the CURRENT cell's distance for every history cell",
        [(WM, "            d_hist = tuple(d_at(vid, h) for h in state.history)\n"
              "            c_hist = tuple(c_at(vid, h) for h in state.history)",
              "            d_hist = tuple(d_at(vid, cell) for h in state.history)\n"
              "            c_hist = tuple(c_at(vid, cell) for h in state.history)")],
        [f"{TR}::test_tr2_model_a_chase_never_stalls"],
    ),
    "q_freeze": (
        "R-1: a binding with a history cell at no finite distance is left unevaluated (round 1's freeze)",
        [(WM, "        delta: dict[str, int] = {}\n        route_open: dict[str, bool] = {}\n",
              "        delta: dict[str, int] = {}\n        route_open: dict[str, bool] = {}\n"
              "        frozen_skip: set[str] = set()\n"),
         (WM, "            c_hist = tuple(c_at(vid, h) for h in state.history)\n",
              "            c_hist = tuple(c_at(vid, h) for h in state.history)\n"
              "            if any(x is None for x in d_hist):\n                frozen_skip.add(vid)\n                continue\n"),
         (WM, "            state = progress.get((uid, vid))\n            if state is None:\n                continue\n"
              "            spare_d",
              "            state = progress.get((uid, vid))\n            if state is None or vid in frozen_skip:\n"
              "                continue\n            spare_d")],
        [f"{TR}::test_tr_x_an_enclosed_history_cell_does_not_freeze_the_binding"],
    ),
    "q_emptyinf": (
        "R-1 / amendment A2: an empty history minimum read as infinite (2.8's draft text)",
        [(JD, "        or (best_d is not None and int(d_now) < best_d)\n"
              "        or (c_now is not None and best_c is not None and int(c_now) < best_c)",
              "        or (best_d is None or int(d_now) < best_d)\n"
              "        or (c_now is not None and (best_c is None or int(c_now) < best_c))")],
        [f"{TC}::test_r1_a_two_cell_loop_on_the_clean_field_boundary_still_stalls"],
    ),
    "q_rebase": (
        "R-1: H re-based to the current cell when the clean distance is undefined (re-base without memory; 2.8 "
        "'Nothing is ever re-based', review B2's exploit)",
        [(JD, "    best_c = _finite_min(c_hist)\n",
              "    best_c = _finite_min(c_hist)\n"
              "    if c_now is None:\n"
              "        return replace(state, history=(cell,), k=state.k + (0 if frozen else 1), k_closed=0, closed=False,\n"
              "                       age=state.age + 1)\n")],
        [f"{TC}::test_r1_a_two_cell_loop_stalls_also_when_the_victims_cell_turns_smoky_every_third_evaluation"],
    ),
    "r1_dstar_d": (
        "R-1: d* replaced by the fire-free d (the fill's length keys and the margin comparisons)",
        [(WM, "            return d if c is None else c", "            return d")],
        [f"{TC}::test_r1_a_margin_challenger_through_a_gap_is_judged_on_its_clean_distance",
         f"{TC}::test_r1_the_fill_ranks_units_by_dstar_not_by_a_gap_distance"],
    ),
    "q_initempty": (
        "R-1: new_progress starts with an empty history",
        [(JD, "    return Progress(history=((int(cell[0]), int(cell[1])),))", "    return Progress(history=())")],
        [f"{TC}::test_r1_the_history_is_the_bind_cell_at_the_bind"],
    ),
    "r1_donly": (
        "R-1: progress judged on the fire-free d only (round 1's metric; the clean comparison removed)",
        [(JD, "        or (c_now is not None and best_c is not None and int(c_now) < best_c)\n", "")],
        [f"{TC}::test_r1_a_unit_walking_a_clean_detour_never_stalls"],
    ),
    "r1_cnone": (
        "R-1: d* = the clean distance only (None when no clean path exists)",
        [(WM, "            return d if c is None else c", "            return c")],
        [f"{TC}::test_r1_dstar_is_d_when_no_clean_path_exists"],
    ),
    # ------------------------------------------------------------------ ROUND 2: R-2 (clean approach first)
    "r2_fill": (
        "R-2 (b): L1b (most clean-approach pairs) removed from the fill key",
        [(JD, _KEY, "        return (-n, 0, total, worst, reused, ids)")],
        [f"{TC}::test_c1_l1b_a_clean_approach_beats_a_nearer_unit_without_one"],
    ),
    "r2_margin": (
        "R-2 (a): the margin challenger's clean-approach test removed (stall keeps it)",
        [(JD, "            if unit in used or not clean.get((unit, c.victim), False):",
              "            if unit in used or (stall and not clean.get((unit, c.victim), False)):")],
        [f"{TR}::test_tr4_margin_needs_m_steps_for_p_evaluations",
         f"{TC}::test_r2_a_margin_challenger_without_a_clean_approach_is_refused"],
    ),
    # ------------------------------------------------------------------ ROUND 2: C1 (nearest wins)
    "c1_l1b_first": (
        "C1: L1b (clean-approach pairs) ranked before L1 (coverage)",
        [(JD, _KEY, "        return (-n_clean, -n, total, worst, reused, ids)")],
        [f"{TC}::test_c1_coverage_comes_before_clean_approach_pairs"],
    ),
    "c1_barred_used": (
        "C1: a barred contest's nearest spares are marked used (not left available to other contests)",
        [(JD, "                                 units=tuple(ties)))\n            return\n",
              "                                 units=tuple(ties)))\n            used.update(ties)\n            return\n")],
        [f"{TC}::test_c1_a_spare_barred_for_one_contest_stays_available_to_another"],
    ),
    "c2_label_open": (
        "C2: the route read as closed whenever the binder is labelled route_blocked (label, not route)",
        [(WM, "            is_open = d_now is not None\n",
              "            is_open = d_now is not None and str(getattr(units[uid], \"status\", \"\") or \"\").strip()"
              ".lower() != \"route_blocked\"\n")],
        [f"{TC}::test_c2_a_latched_label_on_an_open_route_is_read_from_the_route"],
    ),
    "c1_l2": (
        "C1: round 1's L2 (fewest re-used pairs) restored ahead of the route keys",
        [(JD, _KEY, "        return (-n, reused, -n_clean, total, worst, ids)")],
        [f"{TJ}::test_tj11_coverage_before_reuse_and_nearest_over_fresh",
         f"{TC}::test_c1_a_nearer_reused_unit_beats_a_farther_fresh_one",
         f"{TC}::test_c1_a_nearer_victim_on_a_reused_pair_beats_a_farther_fresh_one",
         f"{TR}::test_tflip_b_alternating_advantage_replaces_at_most_once"],
    ),
    "c1_tie": (
        "C1: the re-use tie-break (L4') dropped - ids decide an exact tie",
        [(JD, _KEY, "        return (-n, -n_clean, total, worst, 0, ids)")],
        [f"{TJ}::test_tj11_coverage_before_reuse_and_nearest_over_fresh"],
    ),
    "c1_allowed": (
        "C1 / ruling X-1 (b): a replacement takes the nearest ALLOWED qualifying spare",
        [(JD, "        least = min(d for d, _ in q)\n",
              "        q = [(d, u) for d, u in q if allowed(u, c)] or q\n        least = min(d for d, _ in q)\n")],
        [f"{TC}::test_c1_the_incumbent_is_kept_when_the_nearest_qualifying_spare_is_barred"],
    ),
    "c1_tieorder": (
        "C1: the lowest-id spare among the nearest taken before the ledger is read",
        [(JD, "        ok = [u for u in ties if allowed(u, c)]", "        ok = [u for u in ties[:1] if allowed(u, c)]")],
        [f"{TC}::test_c1_a_tie_at_the_least_distance_goes_to_the_allowed_spare"],
    ),
    "c1_freshpersist": (
        "C1: the model counts persistence (and offers spares) only for fresh pairs",
        [(WM, "            spare_d = {b: dstar(b, vid) for b in spares}\n",
              "            spare_d = {b: dstar(b, vid) for b in spares if int(ledger.get((b, vid), 0) or 0) == 0}\n"),
         (WM, "            for b in spares:\n                dist3[(b, vid)] = spare_d[b]",
              "            for b in spare_d:\n                dist3[(b, vid)] = spare_d[b]")],
        [f"{TC}::test_c1_the_margin_leg_counts_a_barred_spares_persistence"],
    ),
    # ------------------------------------------------------------------ ROUND 2: C2 (a closed-route binder is an incumbent)
    "c2_immediate": (
        "C2: latched-held victims re-enter the step-2 fill as immediate LATCH-FILLs under the cap (round 1)",
        [(WM, "        fill_victims = list(waiting) if reassign else list(waiting) + list(latched)",
              "        fill_victims = list(waiting) + list(latched)"),
         (WM, _FILL2, _FILL2_R1)],
        [f"{TR}::test_tr8_latched_incumbent_is_replaced_by_a_latch_fill_only_after_the_charge",
         f"{TR}::test_tr8_a_latched_unit_whose_route_is_open_is_judged_like_an_active_incumbent"],
    ),
    "c2_inf": (
        "C2: a closed incumbent's delta read as infinite (round 1's worthless latched unit)",
        [(WM, "                delta[vid] = _jd.grid_distance(cell, victims[vid][\"cell\"])",
              "                delta[vid] = 10**6")],
        [f"{TR}::test_tr8_latched_incumbent_is_replaced_by_a_latch_fill_only_after_the_charge"],
    ),
    "c2_activeclosed": (
        "C2: an active binder whose route is closed is not evaluated (round 1's 6.3)",
        [(WM, "        delta: dict[str, int] = {}\n        route_open: dict[str, bool] = {}\n",
              "        delta: dict[str, int] = {}\n        route_open: dict[str, bool] = {}\n"
              "        skip_closed: set[str] = set()\n"),
         (WM, "            route_open[vid] = is_open\n",
              "            route_open[vid] = is_open\n"
              "            if not is_open and str(getattr(units[uid], \"status\", \"\") or \"\").strip().lower() != \"route_blocked\":\n"
              "                skip_closed.add(vid)\n                continue\n"),
         (WM, "            state = progress.get((uid, vid))\n            if state is None:\n                continue\n"
              "            spare_d",
              "            state = progress.get((uid, vid))\n            if state is None or vid in skip_closed:\n"
              "                continue\n            spare_d")],
        [f"{TC}::test_c2_an_active_unit_whose_route_is_closed_is_judged_on_g_and_k_closed"],
    ),
    "c2_onecount": (
        "C2: the closed steps also add to the open-route count k",
        [(JD, "            k_closed=state.k_closed + (0 if frozen else 1),\n            closed=True,",
              "            k=state.k + (0 if frozen else 1),\n            k_closed=state.k_closed + (0 if frozen else 1),\n"
              "            closed=True,")],
        [f"{TC}::test_c2_the_closed_count_resets_when_the_route_opens"],
    ),
    "c2_frozenL": (
        "C2: the closed branch counts FROZEN steps",
        [(JD, "            k_closed=state.k_closed + (0 if frozen else 1),\n            closed=True,",
              "            k_closed=state.k_closed + 1,\n            closed=True,")],
        [f"{TC}::test_c2_frozen_steps_count_in_neither_count"],
    ),
    "c2_step4": (
        "C2: step 4 offers W_L under the LATCH-FILL cap again (A2's step 4)",
        [(WM, _STEP4, _STEP4_A2)],
        [f"{TR}::test_tr10_a_the_second_fill_offers_only_w_under_limit3"],
    ),
}

# Round 1's mutants RETIRED by round 2, each with its reason (printed in the record).
RETIRED: dict[str, str] = {
    "tj11": "round 1's L2 key no longer exists; its two halves are c1_l2 (the key restored ahead of the route keys) "
            "and c1_tie (the re-use tie-break dropped)",
    "tr1": "progress_step has no exogenous shift e_t (R-1's history rule measures every cell on the current board); "
           "its role is taken by q_prevonly / q_by2 / q_feed",
    "tr1cmp": "round 1's best / d_prev reference is gone; the 'previous cell only' mutant is q_prevonly",
    "tr1x": "the model no longer feeds x / d_prev; the feed mutant is q_feed",
    "txnone": "round 1's 'x infinite -> not evaluated' rule is superseded (R-1 / C2); the freeze is q_freeze",
    "tr10a": "A2's step-4 W_L leg is superseded by C2 (step 4 offers W only under Limit 3); its inverse is c2_step4",
    "tr10b": "no W_L victim is offered at step 4 under Limit 3 (C2), so the step-4 cap cannot be reached",
    "tr10rel": "no step-4 LATCH-FILL exists under Limit 3 (C2); the release of a latched binder is tr8 (step 3)",
}


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


def _cases(xml_path: Path) -> dict[tuple[str, str], str]:
    """(module stem, test name with its [case]) -> passed | failed | error | skipped."""
    out: dict[tuple[str, str], str] = {}
    if not xml_path.exists():
        return out
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        stem = str(case.get("classname", "")).split(".")[-1]
        name = str(case.get("name", ""))
        status = "passed"
        for child in case:
            if child.tag in ("failure", "error", "skipped"):
                status = {"failure": "failed"}.get(child.tag, child.tag)
        out[(stem, name)] = status
    return out


def _node_result(node: str, cases: dict[tuple[str, str], str]) -> tuple[int, int, int]:
    """(cases collected, cases failed or errored, cases skipped) for one listed node."""
    path, name = node.split("::", 1)
    stem = Path(path).stem
    if "[" in name:
        hits = [s for (st, n), s in cases.items() if st == stem and n == name]
    else:
        hits = [s for (st, n), s in cases.items() if st == stem and (n == name or n.startswith(name + "["))]
    return len(hits), sum(1 for s in hits if s in ("failed", "error")), sum(1 for s in hits if s == "skipped")


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    work = Path(args.work).resolve()
    py = str(Path(sys.executable))
    chosen = [m for m in MUTANTS if not args.only or m in args.only.split(",")]
    work.mkdir(parents=True, exist_ok=True)
    base = work / "_base"
    _copy_tree(repo, base)

    def one(mid: str | None) -> tuple[str, int, dict, float, list[str]]:
        dest = work / (mid or "_control")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(base, dest)
        if mid is None:
            nodes = sorted({n for m in chosen for n in MUTANTS[m][2]})
        else:
            _apply(dest, MUTANTS[mid][1])
            nodes = MUTANTS[mid][2]
        rc, cases, secs = _run(dest, py, nodes)
        shutil.rmtree(dest, ignore_errors=True)
        if rc in (2, 3, 4, 5):
            # pytest interrupted / internal error / usage error / nothing collected: no listed test ran, so the
            # outcome says nothing about the mutant (round 2: a vacuous "killed" is impossible).
            cases = {}
        return (mid or "CONTROL", rc, cases, secs, nodes)

    lines = [f"dispatch round 2 Part 2 mutation check - repo {repo}",
             "one pytest call per mutant, no -x, per-test outcomes from the JUnit XML", "",
             "RETIRED round-1 mutants (dispatch2_part1.txt 13 (4)):"]
    lines += [f"    {k}: {v}" for k, v in RETIRED.items()]
    lines.append("")
    results = []
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(one, None)] + [pool.submit(one, m) for m in chosen]
        for fut in futures:
            results.append(fut.result())
    ok = True
    per_test = 0
    for mid, rc, cases, secs, nodes in results:
        rows = []
        killed_all = True
        clean_all = True
        for node in nodes:
            n, failed, skipped = _node_result(node, cases)
            name = node.split("::", 1)[1]
            if n == 0:
                rows.append(f"    MISSING  {name} (no case collected)")
                killed_all = clean_all = False
                continue
            if mid == "CONTROL":
                good = failed == 0 and skipped == 0
                clean_all &= good
                if not good:
                    rows.append(f"    FAIL     {name} ({failed}/{n} cases fail, {skipped} skipped)")
                continue
            per_test += 1
            killed = failed > 0
            killed_all &= killed
            frac = f" ({failed}/{n} cases fail)" if n > 1 else ""
            rows.append(f"    {'KILLED  ' if killed else 'SURVIVED'} {name}{frac}")
        if mid == "CONTROL":
            verdict = f"PASS (all {len(nodes)} listed nodes pass)" if clean_all else "FAIL (control does not pass!)"
            ok &= clean_all
            lines.append(f"{mid:13s} rc={rc} {verdict}  {secs:6.1f}s")
        else:
            verdict = "KILLED (every listed test fails)" if killed_all else "NOT KILLED (a listed test passes!)"
            ok &= killed_all
            lines.append(f"{mid:13s} rc={rc} {verdict}  {secs:6.1f}s")
            lines.append(f"    mutant: {MUTANTS[mid][0]}")
        lines.extend(rows)
    lines.append("")
    lines.append(f"{per_test} (mutant, test) records")
    lines.append("ALL MUTANTS KILLED ON EVERY LISTED TEST, CONTROL PASSES" if ok else "MUTATION CHECK NOT CLEAN")
    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    shutil.rmtree(base, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
