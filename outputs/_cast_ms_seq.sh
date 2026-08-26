#!/usr/bin/env bash
# 40-run multi-searcher lane matrix - the SAME matrix both prior lane rounds
# used (Scenario C 3T+2S, Scenario D 2T+2S, 4 winds, seeds 101-505, 240 steps).
#
# SEQUENTIAL, for the same reason as _cast_default_seq.sh: the parallel
# version (_cast_ms.sh) oversubscribes the paging file and the combos die at
# import. Run this one.
#
#   usage: _cast_ms_seq.sh <OUTDIR> [combo ...]
set -u
ROOT="E:/Projects/SAS/.claude/worktrees/c-east-interior-retarget-diagnosis-daa820"
PY="E:/Projects/SAS/.venv/Scripts/python.exe"
OUTDIR="${1:-outputs/lane_matrix_cast}"
shift || true
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT"
mkdir -p "$OUTDIR"

if [ "$#" -gt 0 ]; then
  COMBOS="$*"
else
  COMBOS="C_east C_west C_north C_south D_east D_west D_north D_south"
fi

rc=0
for c in $COMBOS; do
  sc="${c%%_*}"; wind="${c##*_}"
  if [ "$sc" = "C" ]; then uavs=5; trk=3; else uavs=4; trk=2; fi
  echo "RUN ${sc}_${wind} -> ${OUTDIR}/${sc}_${wind}.json  $(date +%H:%M:%S)"
  "$PY" outputs/_lane_matrix.py --scenario "$sc" --wind "$wind" \
        --seeds 101,202,303,404,505 --steps 240 \
        --uavs "$uavs" --fire-trackers "$trk" --victim-searchers 2 \
        --out "${OUTDIR}/${sc}_${wind}.json" \
        > "${OUTDIR}/${sc}_${wind}.log" 2>&1 || rc=1
  if [ ! -s "${OUTDIR}/${sc}_${wind}.json" ]; then
    echo "  !! NO JSON for ${sc}/${wind} - see ${OUTDIR}/${sc}_${wind}.log"
    rc=1
  fi
done
echo "MS MATRIX DONE rc=$rc  $(date +%H:%M:%S)"
exit "$rc"
