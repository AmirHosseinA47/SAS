#!/bin/bash
# Third arm: `hardlc` - the anti-oscillation memory survives BOTH clears
# (the reset at agents.py:752 and the inline leash re-anchor at agents.py:786).
# This is the only arm that actually blocks the reversal, so it is the arm that
# measures whether the reversal costs anything or buys something.
PY=/e/Projects/SAS/.venv/Scripts/python.exe
OUT=/e/Projects/SAS/outputs
N=${N:-9}
STEPS=${STEPS:-240}

if [ "$1" = "--one" ]; then
  IFS=',' read -r wind roles seed arm tag <<< "$2"
  "$PY" "$OUT/_irh2_probe_h.py" --wind "$wind" --roles "$roles" --seeds "$seed" \
      --steps "$STEPS" --arm "$arm" --tag "$tag" \
      > "$OUT/_irh2h_log_${tag}.txt" 2>&1
  rc=$?
  if [ -s "$OUT/_irh2h_${tag}.json" ]; then
    echo "OK   $tag rc=$rc $(wc -c < "$OUT/_irh2h_${tag}.json") bytes"
  else
    echo "FAIL $tag rc=$rc NO/EMPTY JSON"
  fi
  exit 0
fi

SELF="$OUT/_irh2_runh.sh"
ARM=${ARM:-hardlc}
{
  for s in 101 202 303;         do echo "east,default,$s,$ARM,ed_${s}_${ARM}"; done
  for s in 101 202 303 404 505; do echo "east,half,$s,$ARM,eh_${s}_${ARM}";   done
  for s in 101 202 303 404 505; do echo "south,half,$s,$ARM,sh_${s}_${ARM}";  done
} | STEPS=$STEPS xargs -P "$N" -I{} bash "$SELF" --one {}
echo "ALL_HARDLC_JOBS_FINISHED"
