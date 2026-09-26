"""Carrying-leg round, Part 3: G6 - the test suite's failing NAME SET and counts, read from
the junit XML that outputs/_cl_pytest.sh writes (carryleg_prereg.txt section 8, "G6
PRE-DECLARED COUNTS"; design carryleg_part1.txt "THE BASELINE").

  base / p0 / post   failed == BASELINE (8 names), passed == 875, errors 0, skipped 0
  sim <NAME>         failed == BASELINE + {PIN}, passed == 874, errors 0, skipped 0,
                     and the log's "CLSIM END CHECK OK"
A failure outside the expected set is listed; the two slow seed-42 tests named in advance
(SEED42) are flagged "named in advance - diagnose from managed_victims at 300, to the
maintainer", never passed automatically. The log's COMPLETE line must be present.

usage: .venv/Scripts/python.exe -B outputs/_cl_g6.py outputs/_cl1_pytest_base.xml [...]
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

BASELINE = frozenset((
    "test_behavior_regression::test_descriptive_next_action_uses_target_position",
    "test_dashboard_panel::test_dashboard_panel_render_returns_string",
    "test_firefighter_dispatch_replacement::test_no_replacement_available_marks_victim_unreachable_once",
    "test_rescue_planner_authority::test_no_firefighter_planner_delay_or_unreachable",
    "test_uav_sector_assignment::test_fire_tracker_uavs_receive_different_target_sets",
    "test_uav_sector_assignment::test_fire_tracker_still_overridden_by_search_mode_fail_safe",
    "test_wind_aware_trajectory_regression::test_north_vs_south_trajectories_diverge_over_40_steps",
    "test_wind_aware_trajectory_regression::test_east_vs_west_trajectories_diverge_over_40_steps",
))
PIN = "test_carry_leg::test_every_switch_ships_zero_and_a_missing_attribute_is_the_shipped_zero"
SEED42 = frozenset((
    "test_firefighter_fire_avoidance::test_scenario_a_east_seed42_firefighter_survival_validation",
    "test_unresolved_victim_coverage::test_seed42_scenario_a_all_victims_accounted_by_300",
))
PASSED_ALL0 = 875


def read(xml):
    root = ET.parse(xml).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    failed, errors, skipped, total = set(), set(), 0, 0
    for ts in suites:
        for c in ts.iter("testcase"):
            total += 1
            name = "%s::%s" % (c.get("classname", "").split(".")[-1], c.get("name"))
            if c.find("failure") is not None:
                failed.add(name)
            if c.find("error") is not None:
                errors.add(name)
            if c.find("skipped") is not None:
                skipped += 1
    return failed, errors, skipped, total


def judge(xml):
    base = os.path.basename(xml)
    m = re.match(r"^_(cl[A-Za-z0-9]*)_pytest_(base|p0|sim|post)(?:_([A-Za-z0-9]+))?\.xml$", base)
    if not m:
        return "FAIL", ["%s is not a _cl_pytest.sh junit file" % base]
    variant = m.group(2)
    log = xml[:-4] + ".log"
    notes, bad = [], []
    text = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""
    if "CL_PYTEST_COMPLETE" not in text:
        bad.append("log %s has no CL_PYTEST_COMPLETE line" % os.path.basename(log))
    failed, errors, skipped, total = read(xml)
    want_failed = set(BASELINE) | ({PIN} if variant == "sim" else set())
    want_passed = PASSED_ALL0 - (1 if variant == "sim" else 0)
    passed = total - len(failed | errors) - skipped
    if variant == "sim" and "CLSIM END CHECK OK" not in text:
        bad.append("sim log without CLSIM END CHECK OK")
    if errors:
        bad.append("%d error(s) (collection/setup): %s" % (len(errors), sorted(errors)))
    if skipped:
        bad.append("%d skipped (none expected)" % skipped)
    new = sorted(failed - want_failed)
    gone = sorted(want_failed - failed)
    for n in new:
        if n in SEED42:
            bad.append("NEW FAILURE (named in advance, seed-42 slow test - diagnose from managed_victims at "
                       "300, to the maintainer): %s" % n)
        else:
            bad.append("NEW FAILURE: %s" % n)
    for n in gone:
        bad.append("expected failure did NOT fail (the name set moved): %s" % n)
    if passed != want_passed:
        bad.append("passed %d != %d" % (passed, want_passed))
    notes.append("variant %s: %d tests, %d failed, %d passed, %d errors, %d skipped" % (
        variant, total, len(failed), passed, len(errors), skipped))
    return ("FAIL" if bad else "PASS"), notes + bad


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    worst = 0
    for xml in argv:
        v, lines = judge(xml)
        print("G6 %s %s" % (v, os.path.basename(xml)))
        for ln in lines:
            print("    " + ln)
        worst = max(worst, 1 if v == "FAIL" else 0)
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
