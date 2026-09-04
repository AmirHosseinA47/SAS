#!/bin/bash
# Canonical-sample runner for the _move_toward oscillation round.
# 13 combos, single arm (observation only), 240 steps, one seed per process.
# Each process seeds its own random.Random(seed) into cfv/wf/agents, so
# cross-process parallelism cannot perturb results.
# Concurrency is capped because a large simultaneous batch OOMs at import
# (paging file) and fails SILENTLY into zero-byte outputs - so every job is
# checked for a non-empty JSON, not just an exit code.
PY=/e/Projects/SAS/.venv/Scripts/python.exe
OUT=/e/Projects/SAS/outputs
N=${N:-7}
STEPS=${STEPS:-240}

if [ "$1" = "--one" ]; then
  IFS=',' read -r wind roles seed tag <<< "$2"
  "$PY" "$OUT/_mto_probe.py" --wind "$wind" --roles "$roles" --seeds "$seed" \
      --steps "$STEPS" --arm none --tag "$tag" \
      > "$OUT/_mto_log_${tag}.txt" 2>&1
  rc=$?
  if [ -s "$OUT/_mto_${tag}.json" ]; then
    echo "OK   $tag rc=$rc $(wc -c < "$OUT/_mto_${tag}.json") bytes"
  else
    echo "FAIL $tag rc=$rc NO/EMPTY JSON"
  fi
  exit 0
fi

SELF="$OUT/_mto_run.sh"
{
  for s in 101 202 303;         do echo "east,default,$s,ed_${s}"; done
  for s in 101 202 303 404 505; do echo "east,half,$s,eh_${s}";    done
  for s in 101 202 303 404 505; do echo "south,half,$s,sh_${s}";   done
} | STEPS=$STEPS xargs -P "$N" -I{} bash "$SELF" --one {}
echo "ALL_JOBS_FINISHED"
