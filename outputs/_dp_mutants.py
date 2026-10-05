"""Dispatch round Part 2 - the mutation check of section 13.3 (outputs/dispatch_part1.txt).

Every new test names a MUTANT: the smallest source change that removes what the test guards. For each mutant this
script copies the source (root *.py, src_extension/, tests/) of the given checkout into a scratch directory,
applies the mutant as exact text replacements (each must match exactly once), runs ALL the tests listed with it in
one pytest call WITHOUT -x, and reads each test's own outcome from the JUnit XML - so the record is PER TEST, as
13.3 requires. A listed node naming one parametrized case must fail itself; a listed node naming a whole
parametrized function is killed when at least one of its cases fails (the record gives k/n). A mutant is KILLED
only when EVERY listed node is killed. A control copy (no mutant) must pass every listed node. Results go to stdout
and, with --out, to a record file.

    python outputs/_dp_mutants.py --repo E:\\Projects\\SAS_wt\\dispatch --work E:\\Projects\\SAS_wt\\_dpmut
        [--only tj1,tr6] [--jobs 6] [--out outputs/_dp_mutants_result.txt]

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
TINV = f"{TI}::test_tinv_invariants_hold_at_every_frame_of_a_real_run"

_SKIP_TAIL = "        if agents.dispatch_joint():\n            # Dispatch round (design 5.7): no pairing here"


def _skip_except(itype: str) -> str:
    return _SKIP_TAIL.replace("if agents.dispatch_joint():", f"if agents.dispatch_joint() and itype != \"{itype}\":")


# id -> (description, [(file, old, new), ...], [pytest node ids])
MUTANTS: dict[str, tuple[str, list[tuple[str, str, str]], list[str]]] = {
    # ------------------------------------------------------------------ LIMIT 2
    "tj1": (
        "solve_fill replaced by per-victim greedy in victim-index order",
        [(JD,
          "    walk(0, frozenset(), [])\n    return sorted(best_pairs, key=lambda p: id_index(p.victim))",
          "    taken: set[str] = set()\n    greedy: list[FillPair] = []\n    for victim in victim_list:\n"
          "        cands = sorted((d, id_index(u), u, r) for u in unit_list if u not in taken\n"
          "                       for (vv, d, r) in options[u] if vv == victim)\n"
          "        if cands:\n            d, _, u, r = cands[0]\n            taken.add(u)\n"
          "            greedy.append(FillPair(victim=victim, unit=u, distance=d, reused=r))\n    return greedy")],
        [f"{TJ}::test_tj1_crossing_pairs_are_uncrossed"],
    ),
    "tj2": (
        "route distance replaced by Manhattan distance",
        [(WM,
          "        def d_of(uid: str, vid: str) -> int | None:\n            return _jd.route_distance(maps[vid], unit_cell(uid), burning)",
          "        def d_of(uid: str, vid: str) -> int | None:\n            c, v = unit_cell(uid), victims[vid][\"cell\"]\n"
          "            return abs(c[0] - v[0]) + abs(c[1] - v[1])")],
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
        [(JD, "        return (-n, reused, total, worst, ids)", "        return (-n, reused, ids, total, worst)")],
        [f"{TJ}::test_tj3_scarcity_serves_the_nearest_by_route"],
    ),
    "tj4": (
        "J iterates units and victims in insertion order with a first-found fit (inputs unsorted, L5 key removed, "
        "the view's victims in registry order)",
        [(JD, "    unit_list = sorted({str(u) for u in units}, key=id_index)\n"
              "    victim_list = sorted({str(v) for v in victims}, key=id_index)",
              "    unit_list = list(dict.fromkeys(str(u) for u in units))\n"
              "    victim_list = list(dict.fromkeys(str(v) for v in victims))"),
         (JD, "        return (-n, reused, total, worst, ids)", "        return (-n, reused, total, worst)"),
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
        "latched-held victims excluded from the fill",
        [(WM, "        fill_victims = list(waiting) + list(latched)", "        fill_victims = list(waiting)")],
        [f"{TJ}::test_tj10_latched_held_victim_gets_a_second_claimant_under_limit2_alone"],
    ),
    "tj11": (
        "the L2 (fewest re-used pairs) key removed",
        [(JD, "        return (-n, reused, total, worst, ids)", "        return (-n, 0, total, worst, ids)")],
        [f"{TJ}::test_tj11_coverage_before_reuse_and_fresh_before_reused"],
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
    # ------------------------------------------------------------------ LIMIT 3
    "tr1": (
        "progress_step without the exogenous shift e_t (the named T-R1 / T-R2 mutant)",
        [(JD, "    best = state.best + (int(x_now) - state.d_prev)", "    best = state.best")],
        [f"{TR}::test_tr1_a_looping_unit_stalls_whatever_the_fire_and_the_victim_do[burnout]",
         f"{TR}::test_tr1_a_looping_unit_stalls_whatever_the_fire_and_the_victim_do[drift]",
         f"{TR}::test_tr2_no_false_stall"],
    ),
    "tr1cmp": (
        "progress judged against the previous distance (d < d_prev - the rejected 'approaching' flag of 6.3)",
        [(JD, "    elif d_now < best:\n        best, k = int(d_now), 0",
              "    elif d_now < state.d_prev:\n        best, k = int(d_now), 0")],
        [f"{TR}::test_tr1_a_looping_unit_stalls_whatever_the_fire_and_the_victim_do[loop]",
         f"{TR}::test_tr1_a_looping_unit_stalls_whatever_the_fire_and_the_victim_do[front]"],
    ),
    "tr1x": (
        "the model feeds progress_step x := d_prev (the exogenous shift dropped at the model's call)",
        [(WM, "            progress[key] = _jd.progress_step(state, d_now, x_now, cell, frozen)",
              "            progress[key] = _jd.progress_step(state, d_now, state.d_prev, cell, frozen)")],
        [f"{TR}::test_tr2_model_a_chase_never_stalls", f"{TR}::test_tr1_model_burnout_still_stalls"],
    ),
    "tr1m": (
        "the stall rule disabled (no stall replacement at all)",
        [(JD, "    stalled = [c for c in contests if c.k >= stall_steps]", "    stalled = []")],
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
        [(WM, "                    clean3[(b, vid)] = clean_ok(b, vid)", "                    clean3[(b, vid)] = True")],
        [f"{TR}::test_tr4_model_a_spare_without_a_clean_approach_is_never_sent"],
    ),
    "txnone": (
        "6.3's not-evaluated rule for an infinite x removed (the binding evaluated with its state unchanged)",
        [(WM, "            if d_now is None or x_now is None:\n                # 6.3",
              "            if False:\n                # 6.3")],
        [f"{TR}::test_tr_x_infinite_binding_is_not_evaluated"],
    ),
    "tr3": (
        "the lost-time charge removed (d(B) < d(A))",
        [(JD, "            if d is None or not int(d) < c.d + c.k:", "            if d is None or not int(d) < c.d:")],
        [f"{TR}::test_tr3_stall_charge_boundary"],
    ),
    "tr4": (
        "P = 1",
        [(JD, "            if int(c.persist.get(unit, 0) or 0) < margin_persist:",
              "            if int(c.persist.get(unit, 0) or 0) < 1:")],
        [f"{TR}::test_tr4_margin_needs_m_steps_for_p_evaluations"],
    ),
    "tr5": (
        "the custody / finisher / co-location exclusions removed",
        [(WM, "            if custody:\n                continue\n            if not binders:",
              "            if False:\n                continue\n            if not binders:")],
        [f"{TR}::test_tr5_a_carrier_or_finisher_is_never_touched[exiting]",
         f"{TR}::test_tr5_a_carrier_or_finisher_is_never_touched[rescue_completed]",
         f"{TR}::test_tr5_a_carrier_or_finisher_is_never_touched[colocated_latched]"],
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
        "the latched binder is not released by the latch-fill (second claim kept under Limit 3)",
        [(WM, "view, pair.victim, list(victims[pair.victim][\"binders\"]), pair.unit,",
              "view, pair.victim, [], pair.unit,")],
        [f"{TR}::test_tr8_latched_incumbent_is_replaced_by_a_latch_fill", TINV],
    ),
    "tr8capm": (
        "the LATCH-FILL cap not passed by the model (capped = [])",
        [(WM, "            capped = latched if reassign else []", "            capped = []")],
        [f"{TR}::test_tr8_no_allowed_unit_keeps_the_latched_binder"],
    ),
    "tr8capp": (
        "the LATCH-FILL cap removed from the pure solver (b >= 2 allowed)",
        [(JD, "            if victim in capped_set and b >= 2:\n                continue",
              "            if False:\n                continue")],
        [f"{TR}::test_tr8_no_allowed_unit_keeps_the_latched_binder",
         f"{TJ}::test_tj11_coverage_before_reuse_and_fresh_before_reused"],
    ),
    "tr9": (
        "the clean-approach test removed (every unit has a clean approach)",
        [(WM, "            return cmap is not None and _jd.route_distance(cmap, unit_cell(uid), unclean) is not None",
              "            return True")],
        [f"{TR}::test_tr9_no_clean_approach_freezes_the_stall[ring]",
         f"{TR}::test_tr9_no_clean_approach_freezes_the_stall[band]"],
    ),
    "tr9rel": (
        "a stalled incumbent released before checking for a qualifying spare",
        [(WM, "        if spares and contests:\n",
              "        for c in contests:\n            if c.k >= stall_steps:\n"
              "                self._release_other_claimants(c.victim, view[\"victims\"][c.victim][\"marker\"], \"\",\n"
              "                                              \"reassign_stall\", only_ff_id=c.incumbent)\n"
              "        if spares and contests:\n")],
        [f"{TR}::test_tr9_a_stall_with_no_spare_releases_nothing"],
    ),
    "tflip": (
        "the b = 0 rule for REPLACE removed (persistence and plan)",
        [(JD, "    def fresh(unit: str, victim: str) -> bool:\n        return int(ledger.get((unit, victim), 0) or 0) == 0",
              "    def fresh(unit: str, victim: str) -> bool:\n        return True"),
         (JD, "        if d is None or d_incumbent is None or not fresh.get(unit, False):",
              "        if d is None or d_incumbent is None:")],
        [f"{TR}::test_tflip_a_no_reversal_by_a_cost_decision",
         f"{TR}::test_tflip_b_alternating_advantage_replaces_at_most_once"],
    ),
    "tflip_vac": (
        "plan_replacements returns nothing (the simulator would test no REPLACE)",
        [(JD, "    spare_list = sorted({str(s) for s in spares}, key=id_index)\n    used: set[str] = set()",
              "    return []\n    spare_list = sorted({str(s) for s in spares}, key=id_index)\n    used: set[str] = set()")],
        [f"{TR}::test_tflip_a_simulator_is_not_vacuous"],
    ),
    # ------------------------------------------------------------------ INFORMATION
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
    # ------------------------------------------------------------------ SWITCHES
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
        "DISPATCH_JOINT shipped 1",
        [(CFV, "\nDISPATCH_JOINT = 0\nDISPATCH_REASSIGN = 0", "\nDISPATCH_JOINT = 1\nDISPATCH_REASSIGN = 0")],
        [f"{TI}::test_tsw_shipped_defaults", f"{TB}::test_shipped_defaults"],
    ),
    "tsw_gate": (
        "the gate at the top of _joint_dispatch_point removed",
        [(WM, "        if not agents.dispatch_joint():\n            return\n        reassign = agents.dispatch_reassign()",
              "        reassign = agents.dispatch_reassign()")],
        [f"{TI}::test_tsw_with_joint_off_j_is_never_entered_and_nothing_changes"],
    ),
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
        return (mid or "CONTROL", rc, cases, secs, nodes)

    lines = [f"dispatch Part 2 mutation check - repo {repo}",
             "one pytest call per mutant, no -x, per-test outcomes from the JUnit XML", ""]
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
