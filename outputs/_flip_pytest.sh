#!/usr/bin/env bash
# Flip round: the full suite, SERIAL, with the campaign's standard command
# (outputs/_dc_pytest.sh). Serial is not optional: tests/test_wind_aware_trajectory_
# regression.py:323-324 records order-dependent siblings, so a sharded run can move
# the failing NAME SET by itself.
#   VARIANT=base  no plugin - identical to _dc_pytest.sh / _fov_pytest_post.log
#   VARIANT=p0    plugin loaded, FLIP_SIM=0 (control for the plugin's early import)
#   VARIANT=sim   plugin loaded, FLIP_SIM=1 (the five constants at dcD's values)
#   VARIANT=post  no plugin, after the source flip (Part 3)
# Launch detached: powershell -File outputs/_dcd4_launch.ps1 -Env "VARIANT=sim" \
#   -Script /e/Projects/SAS/outputs/_flip_pytest.sh
set -u
cd /e/Projects/SAS || exit 1
export MPLBACKEND=Agg
V="${VARIANT:?VARIANT unset}"
TAG="${FLIPTAG:-flip1}"
LOG="outputs/_${TAG}_pytest_${V}.log"
XML="outputs/_${TAG}_pytest_${V}.xml"
PY=./.venv/Scripts/python.exe
P=()
case "$V" in
  base|post) ;;
  p0)  export FLIP_SIM=0; P=(-p outputs._flip_simplugin) ;;
  sim) export FLIP_SIM=1; P=(-p outputs._flip_simplugin) ;;
  *)   echo "unknown VARIANT $V" > "$LOG"; exit 2 ;;
esac
{
  echo "FLIP_PYTEST START variant=$V tag=$TAG head=$(git rev-parse --short HEAD)" \
       "dirty_tracked=$(git status --porcelain --untracked-files=no | wc -l)" \
       "bashpid=$$ start=$(date '+%F %T')"
  "$PY" -c "import sys, mesa; print('python', sys.version); print('mesa', mesa.__version__)"
  git status --porcelain --untracked-files=no
} > "$LOG" 2>&1
"$PY" -m pytest tests -p no:cacheprovider -q ${P[@]+"${P[@]}"} --junitxml="$XML" >> "$LOG" 2>&1
rc=$?
echo "FLIP_PYTEST_COMPLETE variant=$V rc=$rc end=$(date '+%F %T')" >> "$LOG"
