#!/usr/bin/env bash
# belief_gap_regions Part 2: the campaign's canonical 13-run sample, 240 steps,
# scenario D, x3 modes (nopatch / observe / arm) = 39 processes.
#   D/east  half-roles (2 trackers / 2 searchers) seeds 101,202,303,404,505
#   D/south half-roles                            seeds 101,202,303,404,505
#   D/east  default-roles (legacy n-1,1)          seeds 101,202,303
#
# Each run is its own PROCESS, so the "run combos sequentially" rule (which
# exists because apply_scenario_config mutates module-level globals and the
# RNG is module-scoped) is satisfied without serialising wall-clock.
set -u
PY=.venv/Scripts/python.exe
mkdir -p outputs/_bg_logs

launch() {  # mode seed wind roles tag
  local m=$1 s=$2 w=$3 r=$4 tag=$5
  $PY outputs/_bg_probe.py --mode "$m" --seed "$s" --wind "$w" --roles "$r" \
      --steps 240 --out "outputs/_bg_run_${m}_${tag}_$s.json" \
      > "outputs/_bg_logs/${m}_${tag}_$s.log" 2>&1 &
}

for m in nopatch observe arm; do
  for s in 101 202 303 404 505; do launch $m $s east  half    east_half;  done
  for s in 101 202 303 404 505; do launch $m $s south half    south_half; done
  for s in 101 202 303;         do launch $m $s east  default east_def;   done
done

wait
echo "ALL 39 RUNS DONE"
cat outputs/_bg_logs/*.log
