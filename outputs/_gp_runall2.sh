#!/usr/bin/env bash
# Continuation of _gp_runall.sh: the remaining six modes, TWO MODES PER WAVE
# (26 concurrent single-seed processes on the 32-core box, ~145 MB each, so
# ~3.8 GB - well inside the RAM budget that OOMed only on 5-seed-per-process
# runs). Halves wall time versus one mode per wave.
# Per sas-eval-runtime: check FILE SIZE per run, not just exit code.
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_gp_logs

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

# each line is one wave: the modes on it run concurrently
WAVES="${GP_WAVES:-observe,arm_hi arm_lo,arm_role_dict arm_role_str,arm_role_dict_gen}"
STEPS="${GP_STEPS:-240}"

go () { # mode wind roles seed
  local m=$1 w=$2 r=$3 s=$4
  local rr=$r; [ "$r" = "default" ] && rr=def
  local tag="${m}_${w}_${rr}_${s}"
  local out="outputs/_gp_run_${tag}.json"
  $PY outputs/_gp_probe.py --mode "$m" --wind "$w" --roles "$r" --seed "$s" \
      --steps "$STEPS" --out "$out" \
      > "outputs/_gp_logs/${tag}.out" 2> "outputs/_gp_logs/${tag}.err"
  local rc=$? sz
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $tag rc=$rc size=$sz --- $(tail -3 outputs/_gp_logs/${tag}.err 2>/dev/null | tr '\n' ' ')"
  else
    echo "DONE $tag rc=$rc size=$sz"
  fi
}

for wave in $WAVES; do
  echo "=== WAVE: $wave ==="
  for mode in $(echo "$wave" | tr ',' ' '); do
    while read -r w r s; do
      [ -z "$w" ] && continue
      go "$mode" "$w" "$r" "$s" &
    done <<< "$RUNS"
  done
  wait
  echo "=== WAVE $wave COMPLETE ==="
done
echo "ALL_GP2_COMPLETE"
