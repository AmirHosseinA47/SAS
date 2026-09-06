#!/usr/bin/env bash
# AFTER arm of the three grid-sensitive tests, on the PATCHED tree (cwd matters:
# the suite has no conftest, modules resolve from the current directory).
PY=/e/Projects/SAS/.venv/Scripts/python.exe
T="tests/test_executor_routing_and_burnt.py::test_fire_self_limits_does_not_burn_whole_map tests/test_unresolved_victim_coverage.py::test_victim_searcher_does_not_stay_in_single_corridor_when_unresolved tests/test_unresolved_victim_coverage.py::test_remaining_victim_coverage_after_two_rescues"
cd /e/Projects/SAS || exit 1
sleep 240
MPLBACKEND=Agg $PY -m pytest $T -p no:cacheprovider -q 2>&1 | tail -15 > /e/Projects/SAS/outputs/_dim_pytest_grid3_after_fix.txt
echo "GRID3 AFTER DONE $(date +%H:%M:%S) cwd=$(pwd)" >> /e/Projects/SAS/outputs/_dim_pytest_grid3_after_fix.txt
