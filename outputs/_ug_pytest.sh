#!/usr/bin/env bash
# Ungated-firefighting round: the full suite, SERIAL, with the campaign's standard
# command (copied from outputs/_flip_pytest.sh). Serial is not optional:
# tests/test_wind_aware_trajectory_regression.py records order-dependent siblings,
# so a sharded run can move the failing NAME SET by itself.
#   VARIANT=base  no plugin - the checkout as it is
#   VARIANT=p0    plugin loaded, UG_SIM=0 (control for the plugin's early import)
#   VARIANT=sim   plugin loaded, UG_SIM=1 (the four FF constants at their flipped values)
#   VARIANT=post  no plugin, after the source flip (Part 3)
# Launch detached: powershell -File outputs/_dcd4_launch.ps1 -Env "VARIANT=sim" \
#   -Script /e/Projects/SAS/outputs/_ug_pytest.sh
set -u
cd /e/Projects/SAS || exit 1
export MPLBACKEND=Agg
V="${VARIANT:?VARIANT unset}"
TAG="${UGTAG:-ug1}"
LOG="outputs/_${TAG}_pytest_${V}.log"
XML="outputs/_${TAG}_pytest_${V}.xml"
PY=./.venv/Scripts/python.exe
P=()
case "$V" in
  base|post) ;;
  p0)  export UG_SIM=0; P=(-p outputs._ug_simplugin) ;;
  sim) export UG_SIM=1; P=(-p outputs._ug_simplugin) ;;
  *)   echo "unknown VARIANT $V" > "$LOG"; exit 2 ;;
esac
{
  echo "UG_PYTEST START variant=$V tag=$TAG head=$(git rev-parse --short HEAD)" \
       "branch=$(git branch --show-current)" \
       "dirty_tracked=$(git status --porcelain --untracked-files=no | wc -l)" \
       "bashpid=$$ start=$(date '+%F %T')"
  "$PY" -c "import sys, mesa; print('python', sys.version); print('mesa', mesa.__version__)"
  git status --porcelain --untracked-files=no
} > "$LOG" 2>&1
"$PY" -m pytest tests -p no:cacheprovider -q ${P[@]+"${P[@]}"} --junitxml="$XML" >> "$LOG" 2>&1
rc=$?
echo "UG_PYTEST_COMPLETE variant=$V rc=$rc end=$(date '+%F %T')" >> "$LOG"
