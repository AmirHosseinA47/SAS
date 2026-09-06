#!/usr/bin/env bash
# Repeat the four tests that flipped between the baseline suite run and the patched
# run, on BOTH trees, one process at a time. Unseeded tests (scenario matrix) get 5
# repeats; the seeded trajectory tests get 2 (they should be deterministic).
BASE="C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/9f290476-6a7b-42cc-bad2-0d6d2ccb4449/scratchpad/base8520706"
PY=/e/Projects/SAS/.venv/Scripts/python.exe
OUT=/e/Projects/SAS/outputs/_dim_flips.txt
run () { # tree label test reps
  local tree=$1 label=$2 t=$3 reps=$4 i
  for i in $(seq 1 "$reps"); do
    cd "$tree" || exit 1
    r=$(MPLBACKEND=Agg $PY -m pytest "$t" -p no:cacheprovider -q 2>&1 | grep -a -E '^E +Assert|^E +assert|passed|failed' | tr '\n' ' ' | cut -c1-200)
    echo "$label rep$i $t :: $r" >> "$OUT"
  done
}
: > "$OUT"
for tree_label in "$BASE base" "/e/Projects/SAS fix"; do
  set -- $tree_label
  run "$1" "$2" tests/test_victim_searcher_scenario_matrix.py::test_no_crash_zero_victims 5
  run "$1" "$2" tests/test_wind_aware_trajectory_regression.py::test_east_vs_west_trajectories_diverge_over_40_steps 2
  run "$1" "$2" tests/test_wind_aware_trajectory_regression.py::test_north_vs_south_trajectories_diverge_over_40_steps 2
  run "$1" "$2" tests/test_wind_aware_victim_search.py::test_victim_search_wind_aware_action_when_downwind_exists 2
done
echo "FLIPS DONE $(date +%H:%M:%S)" >> "$OUT"
