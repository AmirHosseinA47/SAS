#!/usr/bin/env bash
# Seed-matched 3-arm batch for the _belief_gap_critical round.
# 13 canonical runs x {nopatch, live, arm} = 39 single-seed processes, 240 steps.
# One seed per process (safe to parallelise: each seeds its own random.Random);
# waves of 13 to stay inside RAM (see memory: paging-file OOM above ~16).
set -u
cd /e/Projects/SAS
PY=./.venv/Scripts/python.exe
OUT=outputs
LOG=$OUT/_bgc_logs
mkdir -p "$LOG"

RUNS="
east half 101
east half 202
east half 303
east half 404
east half 505
south half 101
south half 202
south half 303
south half 404
south half 505
east default 101
east default 202
east default 303
"

wave () {
  local mode=$1
  echo "=== WAVE $mode start $(date +%H:%M:%S) ==="
  echo "$RUNS" | while read -r w r s; do
    [ -z "${w:-}" ] && continue
    tag="${mode}_${w}_${r}_${s}"
    "$PY" "$OUT/_bgc_probe.py" --mode "$mode" --wind "$w" --roles "$r" \
        --seed "$s" --steps 240 --out "$OUT/_bgc_run_${tag}.json" \
        > "$LOG/${tag}.log" 2> "$LOG/${tag}.err" &
  done
  wait
  echo "=== WAVE $mode done $(date +%H:%M:%S) ==="
  echo "$RUNS" | while read -r w r s; do
    [ -z "${w:-}" ] && continue
    tag="${mode}_${w}_${r}_${s}"
    if [ -s "$OUT/_bgc_run_${tag}.json" ]; then
      echo "OK   $tag $(head -c 200 "$LOG/${tag}.log")"
    else
      echo "FAIL $tag :: $(tail -3 "$LOG/${tag}.err" | tr '\n' ' ')"
    fi
  done
}

wave nopatch
wave live
wave arm

echo "=== ALL WAVES DONE $(date +%H:%M:%S) ==="
ls -1 $OUT/_bgc_run_*.json | wc -l
echo "BGC_BATCH_COMPLETE"
