#!/usr/bin/env bash
# The hazard-bound scenario tests and the four tests that flipped in the held
# round, in isolation on the PATCHED tree at its default, one process at a time.
# Unseeded-fixture tests get 5 repeats, seeded trajectory tests 2.
PY=/e/Projects/SAS/.venv/Scripts/python.exe
OUT=/e/Projects/SAS/outputs/_ih_flips.txt
cd /e/Projects/SAS || exit 1
run () { # test reps
  local t=$1 reps=$2 i
  for i in $(seq 1 "$reps"); do
    r=$(MPLBACKEND=Agg $PY -m pytest "$t" -p no:cacheprovider -q 2>&1 | grep -a -E '^E +Assert|^E +assert|passed|failed' | tr '\n' ' ' | cut -c1-200)
    echo "rest99 rep$i $t :: $r" >> "$OUT"
  done
}
: > "$OUT"
run tests/test_victim_searcher_scenario_matrix.py::test_no_crash_zero_victims 5
run tests/test_victim_searcher_scenario_matrix.py::test_scenario_a_no_5x5_camping_east 5
run tests/test_wind_aware_victim_search.py::test_victim_search_wind_aware_action_when_downwind_exists 5
run tests/test_wind_aware_trajectory_regression.py::test_east_vs_west_trajectories_diverge_over_40_steps 2
run tests/test_wind_aware_trajectory_regression.py::test_north_vs_south_trajectories_diverge_over_40_steps 2
run tests/test_victim_searcher_hazard_retreat.py 1
echo "FLIPS DONE $(date +%H:%M:%S)" >> "$OUT"
