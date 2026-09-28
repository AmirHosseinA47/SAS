#!/usr/bin/env bash
# Planner round: the full suite, SERIAL (outputs/_cl_pytest.sh's standard command, no plugin:
# tests/test_wind_aware_trajectory_regression.py records order-dependent siblings, so a
# sharded run can move the failing NAME SET by itself). PLTAG names the log:
#   outputs/_<PLTAG>_pytest.log / .xml ; PLTAG must start with "pl" and must not exist yet.
set -u
cd /e/Projects/SAS || exit 1
export MPLBACKEND=Agg
for e in PYTEST_ADDOPTS PYTEST_PLUGINS; do
  if [ -n "${!e:-}" ]; then echo "PL_PYTEST REFUSED: $e is set" >&2; exit 2; fi
done
TAG="${PLTAG:?PLTAG unset}"
case "$TAG" in pl*) ;; *) echo "PL_PYTEST REFUSED: PLTAG '$TAG' does not start with pl" >&2; exit 2 ;; esac
case "$TAG" in *[!A-Za-z0-9]*) echo "PL_PYTEST REFUSED: bad PLTAG '$TAG'" >&2; exit 2 ;; esac
PY=/e/Projects/SAS/.venv/Scripts/python.exe
LOG="outputs/_${TAG}_pytest.log"; XML="outputs/_${TAG}_pytest.xml"
for f in "$LOG" "$XML"; do [ -e "$f" ] && { echo "PL_PYTEST REFUSED: $f exists" >&2; exit 2; }; done
set -o noclobber
: > "$LOG" || exit 2
{
  echo "PL_PYTEST START tag=$TAG head=$(git rev-parse HEAD) branch=$(git branch --show-current)" \
       "dirty_tracked=$(git status --porcelain -uno | wc -l) start=$(date '+%F %T')"
  "$PY" -B -c "import sys, mesa, numpy; print('python', sys.version); print('mesa', mesa.__version__, 'numpy', numpy.__version__)"
  "$PY" -B -c "import common_fixed_variables as c, agents as a; print('PL_PYTEST SHIPPED GLOBAL_PLANNER_MODE', c.GLOBAL_PLANNER_MODE, 'accessor', a.global_planner_mode())"
  git status --porcelain -uno
} >> "$LOG" 2>&1
"$PY" -B -m pytest tests -p no:cacheprovider -q --junitxml="$XML" >> "$LOG" 2>&1
rc=$?
echo "PL_PYTEST END rc=$rc end=$(date '+%F %T')" >> "$LOG"
exit $rc
