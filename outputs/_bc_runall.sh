#!/usr/bin/env bash
# Defect #9 Part 2: the campaign's canonical 13-run sample, 240 steps, scenario D.
#   D/east  half-roles (2 trackers / 2 searchers) seeds 101,202,303,404,505
#   D/south half-roles                            seeds 101,202,303,404,505
#   D/east  default-roles (legacy n-1,1)          seeds 101,202,303
#
# Each run is its own PROCESS, so the "run combos sequentially" rule (which
# exists because apply_scenario_config mutates module-level globals and the
# RNG is module-scoped) is satisfied without serialising wall-clock: separate
# interpreters do not share those globals. Determinism is per-process seeded.
set -u
PY=.venv/Scripts/python.exe
mkdir -p outputs/_bc_logs

launch() {  # seed wind ft vs tag
  local s=$1 w=$2 ft=$3 vs=$4 tag=$5
  if [ "$ft" = "-" ]; then
    $PY outputs/_bc_probe.py --seed "$s" --scenario D --wind "$w" \
        --steps 240 --out "outputs/_bc_${tag}_$s.json" \
        > "outputs/_bc_logs/${tag}_$s.log" 2>&1 &
  else
    $PY outputs/_bc_probe.py --seed "$s" --scenario D --wind "$w" \
        --fire-trackers "$ft" --victim-searchers "$vs" --steps 240 \
        --out "outputs/_bc_${tag}_$s.json" \
        > "outputs/_bc_logs/${tag}_$s.log" 2>&1 &
  fi
}

for s in 101 202 303 404 505; do launch $s east  2 2 east_half;  done
for s in 101 202 303 404 505; do launch $s south 2 2 south_half; done
for s in 101 202 303;         do launch $s east  - - east_def;   done

wait
echo "ALL 13 RUNS DONE"
cat outputs/_bc_logs/*.log
