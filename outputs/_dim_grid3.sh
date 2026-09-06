#!/usr/bin/env bash
# The three tests the grid-scale diagnosis found failing at 100x100, run at 50x50
# BEFORE (8520706 worktree) and AFTER (patched tree), one process at a time.
BASE="C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/9f290476-6a7b-42cc-bad2-0d6d2ccb4449/scratchpad/base8520706"
PY=/e/Projects/SAS/.venv/Scripts/python.exe
T="tests/test_executor_routing_and_burnt.py::test_fire_self_limits_does_not_burn_whole_map tests/test_unresolved_victim_coverage.py::test_victim_searcher_does_not_stay_in_single_corridor_when_unresolved tests/test_unresolved_victim_coverage.py::test_remaining_victim_coverage_after_two_rescues"
cd "$BASE" && MPLBACKEND=Agg $PY -m pytest $T -p no:cacheprovider -q 2>&1 | tail -15 > /e/Projects/SAS/outputs/_dim_pytest_grid3_before.txt
# The AFTER run lives in _dim_grid3_after.sh (it must cd to the patched tree;
# the first version of this script forgot to and its after-output was discarded).
