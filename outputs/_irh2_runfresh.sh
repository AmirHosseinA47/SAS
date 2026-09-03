#!/bin/bash
# FRESH SEEDS, never used to tune anything in this chain.
# The canonical 13 are the sample this round measured the hole on, so they are
# also the sample a fix would be over-fitted to.  These ten are the independent
# check.  east/half and south/half, seeds 1111..5555, both arms.
PY=/e/Projects/SAS/.venv/Scripts/python.exe
OUT=/e/Projects/SAS/outputs
N=${N:-9}
STEPS=${STEPS:-240}

if [ "$1" = "--one" ]; then
  IFS=',' read -r wind roles seed arm tag probe pre <<< "$2"
  "$PY" "$OUT/$probe" --wind "$wind" --roles "$roles" --seeds "$seed" \
      --steps "$STEPS" --arm "$arm" --tag "$tag" \
      > "$OUT/${pre}log_${tag}.txt" 2>&1
  rc=$?
  if [ -s "$OUT/${pre}${tag}.json" ]; then
    echo "OK   $tag rc=$rc $(wc -c < "$OUT/${pre}${tag}.json") bytes"
  else
    echo "FAIL $tag rc=$rc NO/EMPTY JSON"
  fi
  exit 0
fi

SELF="$OUT/_irh2_runfresh.sh"
{
  for s in 1111 2222 3333 4444 5555; do
    echo "east,half,$s,none,fh_${s}_none,_irh2_probe.py,_irh2_"
    echo "east,half,$s,hardlc,fh_${s}_hardlc,_irh2_probe_h.py,_irh2h_"
    echo "south,half,$s,none,fs_${s}_none,_irh2_probe.py,_irh2_"
    echo "south,half,$s,hardlc,fs_${s}_hardlc,_irh2_probe_h.py,_irh2h_"
  done
} | STEPS=$STEPS xargs -P "$N" -I{} bash "$SELF" --one {}
echo "ALL_FRESH_JOBS_FINISHED"
