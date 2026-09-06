#!/bin/bash
# Battery diagnosis: seed-matched arms over the canonical 13-run sample.
#   wave 1: stock   x13   (D/east half 101-505, D/south half 101-505, D/east default 101/202/303)
#   wave 2: nodrain x13   (same seeds; drain constants zeroed -> battery pinned at 100)
#   wave 3: low25 x3 + crit12 x3 (east/half 101, south/half 101, east/default 101)
# One wave at a time (commit-charge limit on this box), plain & + wait so the
# children outlive nothing; every run is checked for a NON-EMPTY json.
cd /e/Projects/SAS || exit 1
PY=.venv/Scripts/python.exe
mkdir -p outputs/_bat_logs
LOG=outputs/_bat_runall.log
: > "$LOG"

run() {
  local arm=$1 wind=$2 roles=$3 seed=$4
  local tag="${arm}_${wind}_${roles}_${seed}"
  "$PY" outputs/_bat_probe.py --repo . --wind "$wind" --roles "$roles" --seed "$seed" \
      --steps 240 --arm "$arm" --out "outputs/_bat_${tag}.json" \
      > "outputs/_bat_logs/${tag}.log" 2>&1
  if [ -s "outputs/_bat_${tag}.json" ]; then
    echo "OK    $tag $(date +%H:%M:%S)" >> "$LOG"
  else
    echo "EMPTY $tag $(date +%H:%M:%S)" >> "$LOG"
  fi
}

CANON=(
  "east half 101" "east half 202" "east half 303" "east half 404" "east half 505"
  "south half 101" "south half 202" "south half 303" "south half 404" "south half 505"
  "east default 101" "east default 202" "east default 303"
)
FORCED=("east half 101" "south half 101" "east default 101")

for arm in stock nodrain; do
  echo "WAVE $arm start $(date +%H:%M:%S)" >> "$LOG"
  for combo in "${CANON[@]}"; do
    set -- $combo
    run "$arm" "$1" "$2" "$3" &
  done
  wait
  echo "WAVE $arm done $(date +%H:%M:%S)" >> "$LOG"
done

echo "WAVE forced start $(date +%H:%M:%S)" >> "$LOG"
for arm in low25 crit12; do
  for combo in "${FORCED[@]}"; do
    set -- $combo
    run "$arm" "$1" "$2" "$3" &
  done
done
wait
echo "WAVE forced done $(date +%H:%M:%S)" >> "$LOG"
echo "ALLDONE $(date +%H:%M:%S)" >> "$LOG"
