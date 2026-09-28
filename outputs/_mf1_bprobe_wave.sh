#!/bin/bash
# mf1 Part 1 design probe wave: scenario B, reduced launch battery candidates.
# 8 single-seed 360-step runs, one process each (cross-process parallel is safe).
cd /e/Projects/SAS
PY=.venv/Scripts/python.exe
for spec in "east 9411" "south 9412"; do
  set -- $spec; wind=$1; seed=$2
  for frac in 1.0 0.5 0.25 0.12; do
    tag="mf1_bp_B_${wind:0:1}_f${frac/./}"
    $PY outputs/_mf1_bprobe.py $frac --scenario B --wind $wind --seed $seed --steps 360 \
      --set BATCH_SIZE=360 --out outputs/_${tag}.json --tag $tag > outputs/_${tag}.log 2>&1 &
  done
done
wait
echo MF1_BPROBE_WAVE_DONE
