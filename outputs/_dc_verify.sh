#!/usr/bin/env bash
# Depot-cost round: the four runs that must be right before the wave is worth
# starting. Written to the wave's own output names, so _dim_pool.sh skips them
# later and nothing is repeated.
#   dcref/dcoff seed 101  -> the kill-switch byte-identity gate
#   dcC/dcD     seed 101  -> the two new geometries actually run and return
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
SCR="C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/aabd7c4c-06e6-4ca4-b6be-e62841bf5ae7/scratchpad"
mkdir -p outputs/_ffr_logs
grep -E '^(dcref|dcoff|dcC|dcD)\|' outputs/_dc_queue.txt \
  | grep -E '\|east\|half\|101\|' \
  > outputs/_dc_verify_queue.txt
wc -l < outputs/_dc_verify_queue.txt
while IFS='|' read -r tag repo w r s extra; do
  tag=${tag//$'\r'/}; repo=${repo//$'\r'/}; w=${w//$'\r'/}
  r=${r//$'\r'/}; s=${s//$'\r'/}; extra=${extra//$'\r'/}
  rr=$r; [ "$r" = "default" ] && rr=def
  name="${tag}_${w}_${rr}_${s}"
  # shellcheck disable=SC2086
  ( $PY outputs/_ffr_harness.py --repo "$repo" --wind "$w" --roles "$r" --seed "$s" \
        --steps 240 --out "outputs/_ffr_${name}.json" --tag "$tag" $extra \
        > "outputs/_ffr_logs/${name}.out" 2> "outputs/_ffr_logs/${name}.err"
    echo "DONE $name rc=$? size=$(stat -c%s "outputs/_ffr_${name}.json" 2>/dev/null || echo 0)" ) &
done < outputs/_dc_verify_queue.txt
wait
echo "DC_VERIFY_COMPLETE $(date '+%H:%M:%S')"
