#!/usr/bin/env bash
# Fill the 5 arm runs the fork-storm batch lost. No pipes -> `wait` actually waits.
set -u
cd /e/Projects/SAS
PY=./.venv/Scripts/python.exe
OUT=outputs
LOG=$OUT/_bgc_logs
mkdir -p "$LOG"
echo "=== FILL start $(date +%H:%M:%S) ==="
for spec in "south half 101" "south half 505" "east default 101" "east default 202" "east default 303"; do
  set -- $spec
  w=$1; r=$2; s=$3
  tag="arm_${w}_${r}_${s}"
  "$PY" "$OUT/_bgc_probe.py" --mode arm --wind "$w" --roles "$r" \
      --seed "$s" --steps 240 --out "$OUT/_bgc_run_${tag}.json" \
      > "$LOG/${tag}.log" 2> "$LOG/${tag}.err" &
done
wait
echo "=== FILL done $(date +%H:%M:%S) ==="
for spec in "south half 101" "south half 505" "east default 101" "east default 202" "east default 303"; do
  set -- $spec
  tag="arm_${1}_${2}_${3}"
  if [ -s "$OUT/_bgc_run_${tag}.json" ]; then echo "OK   $tag $(stat -c%s "$OUT/_bgc_run_${tag}.json")"
  else echo "FAIL $tag :: $(tail -3 "$LOG/${tag}.err" | tr '\n' ' ')"; fi
done
echo "BGC_FILL_COMPLETE"
