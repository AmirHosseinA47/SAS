#!/bin/bash
# Canonical-sample runner for the idle-reset-hole round.
# 13 combos x 2 arms = 26 single-seed 240-step runs, N workers kept busy.
# One seed per process: each process seeds its own random.Random(seed) into
# cfv/wf/agents, so cross-process parallelism cannot perturb results.
# Concurrency is capped because a large simultaneous batch OOMs at import
# (paging file) and fails SILENTLY into zero-byte outputs - so every job is
# checked for a non-empty JSON, not just an exit code.
PY=/e/Projects/SAS/.venv/Scripts/python.exe
OUT=/e/Projects/SAS/outputs
N=${N:-9}
STEPS=${STEPS:-240}

if [ "$1" = "--one" ]; then
  IFS=',' read -r wind roles seed arm tag <<< "$2"
  "$PY" "$OUT/_irh2_probe.py" --wind "$wind" --roles "$roles" --seeds "$seed" \
      --steps "$STEPS" --arm "$arm" --tag "$tag" \
      > "$OUT/_irh2_log_${tag}.txt" 2>&1
  rc=$?
  if [ -s "$OUT/_irh2_${tag}.json" ]; then
    echo "OK   $tag rc=$rc $(wc -c < "$OUT/_irh2_${tag}.json") bytes"
  else
    echo "FAIL $tag rc=$rc NO/EMPTY JSON"
  fi
  exit 0
fi

SELF="$OUT/_irh2_run.sh"
{
  for s in 101 202 303;             do for a in none keeplc; do echo "east,default,$s,$a,ed_${s}_${a}"; done; done
  for s in 101 202 303 404 505;     do for a in none keeplc; do echo "east,half,$s,$a,eh_${s}_${a}";   done; done
  for s in 101 202 303 404 505;     do for a in none keeplc; do echo "south,half,$s,$a,sh_${s}_${a}";  done; done
} | STEPS=$STEPS xargs -P "$N" -I{} bash "$SELF" --one {}
echo "ALL_JOBS_FINISHED"
