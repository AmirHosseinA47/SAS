#!/bin/sh
# Fan out the 13 canonical control runs, one seed per process.
# Cross-process parallelism is safe: each process seeds its own random.Random
# into cfv/wf/agents. Only combos INSIDE one process must stay sequential.
# usage: _rh_ctl_drive.sh <tag> [steps]
set -u
PY=./.venv/Scripts/python.exe
TAG="${1:?tag required}"
STEPS="${2:-240}"
LABELS="east_half_101 east_half_202 east_half_303 east_half_404 east_half_505 \
south_half_101 south_half_202 south_half_303 south_half_404 south_half_505 \
east_def_101 east_def_202 east_def_303"

i=0
for lbl in $LABELS; do
  i=$((i+1))
  out="outputs/_rh_ctl_${TAG}_${lbl}.json"
  if [ -s "$out" ]; then echo "SKIP $lbl"; continue; fi
  ( $PY outputs/_rh_control.py "$TAG" "$i" "$STEPS" \
        > "outputs/_rh_ctl_${TAG}_${lbl}.log" 2>&1 ) &
done
wait

echo "---- results ----"
fail=0
for lbl in $LABELS; do
  out="outputs/_rh_ctl_${TAG}_${lbl}.json"
  if [ -s "$out" ]; then
    echo "OK   $lbl  $(cat outputs/_rh_ctl_${TAG}_${lbl}.log)"
  else
    echo "FAIL $lbl"; tail -5 "outputs/_rh_ctl_${TAG}_${lbl}.log"; fail=1
  fi
done
echo "RH_CTL_DONE tag=$TAG fail=$fail"
