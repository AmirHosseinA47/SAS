#!/usr/bin/env bash
# Probe 2 (planner gate) over the canonical 13-run scenario-D sample, both modes.
# Two waves of 13 to stay inside the tested 12-16 concurrent limit (RAM-bound box).
# Per sas-eval-runtime: check FILE SIZE per combo, not just exit code - OOM at
# import fails silently into a zero-byte output.
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_bg_logs

# label list: wind roles seed
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

go () { # mode wind roles seed
  local m=$1 w=$2 r=$3 s=$4
  local rr=$r; [ "$r" = "default" ] && rr=def
  local tag="${m}_${w}_${rr}_${s}"
  local out="outputs/_bg2_run_${tag}.json"
  $PY outputs/_bg_probe2.py --mode "$m" --wind "$w" --roles "$r" --seed "$s" \
      --steps 240 --out "$out" \
      > "outputs/_bg_logs/bg2_${tag}.out" 2> "outputs/_bg_logs/bg2_${tag}.err"
  local rc=$? sz
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $tag rc=$rc size=$sz  --- $(tail -3 outputs/_bg_logs/bg2_${tag}.err 2>/dev/null | tr '\n' ' ')"
  else
    echo "DONE $tag rc=$rc size=$sz"
  fi
}

# NOTE: do NOT pipe RUNS into `while read` - the loop body would run in a
# subshell, the backgrounded jobs would be that subshell's children, and the
# `wait` below (parent shell) would return immediately with the wave still
# running. Feed the loop from a here-string so the jobs are OUR children.
for mode in observe arm; do
  echo "=== WAVE: $mode ==="
  while read -r w r s; do
    [ -z "$w" ] && continue
    go "$mode" "$w" "$r" "$s" &
  done <<< "$RUNS"
  wait
  echo "=== WAVE $mode COMPLETE ==="
done
echo "ALL_BG2_COMPLETE"
