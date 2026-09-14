#!/usr/bin/env bash
# Interior-hazard round, Part 3 post: the full test suite and the route_blocked
# gate (4 shards, new prefix ihrest) concurrently against the PATCHED working
# tree at its default (VICTIM_SEARCHER_HAZARD_RETREAT_RANGE = 99), then the gate
# merge, then the flipped/hazard-bound tests in isolation.
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
LOG=outputs/_ih_post.log
{
  echo "POST START $(date '+%Y-%m-%d %H:%M:%S')  tree: $(git diff --stat -- '*.py' ':(exclude)outputs' | tail -1)  range=$($PY -c 'import common_fixed_variables as c; print(c.VICTIM_SEARCHER_HAZARD_RETREAT_RANGE)')"
  ( MPLBACKEND=Agg $PY -m pytest tests -p no:cacheprovider -q > outputs/_ih_pytest_rest99.log 2>&1; echo "PYTEST DONE rc=$? $(date +%H:%M:%S) $(tail -1 outputs/_ih_pytest_rest99.log)" ) &
  # dcD flip (2026-09-14): pinned to the mode-0 default ihrest measured. The pytest
  # stage above still runs the SHIPPED default (see outputs/flip_runner_register.txt).
  bash outputs/_ffr_rbgate.sh ihrest --set BASE_STATION_MODE=0
  echo "RBGATE SHARDS DONE $(date +%H:%M:%S)"
  $PY outputs/_ir_rbmerge.py --prefix ihrest > outputs/_ih_rbgate_ihrest.txt 2>&1
  echo "RBMERGE DONE rc=$? $(date +%H:%M:%S)"
  wait
  bash outputs/_ih_flips.sh
  echo "FLIPS DONE $(date +%H:%M:%S)"
  echo "ALL_IH_POST_COMPLETE $(date '+%Y-%m-%d %H:%M:%S')"
} > "$LOG" 2>&1
