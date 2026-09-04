#!/usr/bin/env bash
# Negative control: force _belief_gap_critical always-False, seed-matched.
# No pipes -> `wait` actually waits (the earlier batch's fork storm came from
# backgrounding inside a `... | while read` subshell).
set -u
cd /e/Projects/SAS
PY=./.venv/Scripts/python.exe
OUT=outputs
LOG=$OUT/_bgc_logs
mkdir -p "$LOG"
echo "=== NEG start $(date +%H:%M:%S) ==="
for spec in "east half 101" "east half 202" "east half 303" "east half 404" "east half 505" \
            "south half 101" "south half 202" "south half 303" "south half 404" "south half 505" \
            "east default 101" "east default 202" "east default 303"; do
  set -- $spec
  w=$1; r=$2; s=$3
  tag="falsearm_${w}_${r}_${s}"
  "$PY" "$OUT/_bgc_neg.py" --mode falsearm --wind "$w" --roles "$r" \
      --seed "$s" --steps 240 --out "$OUT/_bgc_run_${tag}.json" \
      > "$LOG/${tag}.log" 2> "$LOG/${tag}.err" &
done
wait
echo "=== NEG done $(date +%H:%M:%S) ==="
for spec in "east half 101" "east half 202" "east half 303" "east half 404" "east half 505" \
            "south half 101" "south half 202" "south half 303" "south half 404" "south half 505" \
            "east default 101" "east default 202" "east default 303"; do
  set -- $spec
  tag="falsearm_${1}_${2}_${3}"
  if [ -s "$OUT/_bgc_run_${tag}.json" ]; then echo "OK   $tag $(cat "$LOG/${tag}.log")"
  else echo "FAIL $tag :: $(tail -3 "$LOG/${tag}.err" | tr '\n' ' ')"; fi
done
echo "BGC_NEG_COMPLETE"
