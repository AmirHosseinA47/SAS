#!/usr/bin/env bash
# isTrue round Part 1, census wave 1: five independent 360-step runs (one process each), record-only probe.
# Arms: S = shipped defaults (scenario D); B5 = --set SEARCHER_TARGETING=5 (front priority, the numpy-heavy
# Bayesian belief); G1 = --set GLOBAL_PLANNER_MODE=1 (role options valued from world quantities).
cd /e/Projects/SAS_wt/istrue || exit 1
PY=/e/Projects/SAS_wt/istrue/.venv/Scripts/python.exe
REPO=E:/Projects/SAS_wt/istrue
run() {  # arm wind seed [--set K=V]
  local arm=$1 wind=$2 seed=$3; shift 3
  local stem=outputs/_ist_${arm}_${wind}_${seed}
  "$PY" outputs/_ist_probe.py --census-out ${stem}_census.json -- --repo "$REPO" --wind "$wind" --seed "$seed" \
    --steps 360 --out ${stem}.json --tag ist${arm} "$@" > ${stem}.log 2> ${stem}.err
  echo "DONE $arm $wind $seed exit=$? $(tail -1 ${stem}.log)"
}
run S east 101 &
run S west 103 &
run S south 102 &
run B5 east 101 --set SEARCHER_TARGETING=5 &
run G1 east 101 --set GLOBAL_PLANNER_MODE=1 &
wait
echo "WAVE1 COMPLETE"
