#!/usr/bin/env bash
# Default n<=1 matrix (no role overrides), 16 combos.
#
# SEQUENTIAL. This replaces _cast_default.sh, which launched all 16 combos
# with "&" into the background at once. That exhausted the Windows paging
# file and every combo died at import time with
#   ImportError: DLL load failed while importing <x>:
#   The paging file is too small for this operation to complete.
# leaving 16 zero-byte .txt outputs. One mesa+pandas+matplotlib interpreter
# is ~0.5-1 GB; 16 at once is not survivable on this box.
#
#   usage: _cast_default_seq.sh <OUTPREFIX> [combos...]
set -u
ROOT="E:/Projects/SAS/.claude/worktrees/c-east-interior-retarget-diagnosis-daa820"
PY="E:/Projects/SAS/.venv/Scripts/python.exe"
PREFIX="${1:-outputs/cast_default}"
shift || true
cd "$ROOT" || exit 1

if [ "$#" -gt 0 ]; then
  COMBOS="$*"
else
  COMBOS="A_east A_west A_north A_south B_east B_west B_north B_south C_east C_west C_north C_south D_east D_west D_north D_south"
fi

rc=0
for c in $COMBOS; do
  sc="${c%%_*}"; wind="${c##*_}"
  echo "RUN ${sc}/${wind} -> ${PREFIX}_${sc}_${wind}.txt  $(date +%H:%M:%S)"
  "$PY" evaluate_scenarios.py --scenario "$sc" --wind "$wind" --n 5 --steps 240 \
        --seeds 101,202,303,404,505 > "${PREFIX}_${sc}_${wind}.txt" \
        2> "${PREFIX}_${sc}_${wind}.err" || rc=1
  # A combo that dies at import leaves an empty file; catch it immediately
  # instead of discovering 16 empty outputs at the end.
  if [ ! -s "${PREFIX}_${sc}_${wind}.txt" ]; then
    echo "  !! EMPTY OUTPUT for ${sc}/${wind} - see ${PREFIX}_${sc}_${wind}.err"
    rc=1
  fi
done
echo "ALL DONE rc=$rc  $(date +%H:%M:%S)"
exit "$rc"
