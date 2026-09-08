#!/usr/bin/env bash
# Memory-aware job pool for the latch-frequency sweep. Same shape and the same
# commit-charge ceiling as outputs/_dim_pool.sh (see memory: sas-eval-runtime).
# queue line: seed|mode|wind
# usage: MAXPAR=8 MINFREE_KB=3000000 bash outputs/_l808_pool.sh outputs/_l808_queue.txt
cd /e/Projects/SAS || exit 1
QUEUE=${1:-outputs/_l808_queue.txt}
MAXPAR=${MAXPAR:-8}
MINFREE_KB=${MINFREE_KB:-3000000}
LAUNCH_GAP=${LAUNCH_GAP:-10}
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_l808_logs

free_kb () { powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory" | tr -d '\r '; }
running () { jobs -rp | wc -l; }

run_one () { # seed mode wind
  local s=$1 m=$2 w=$3
  local name="s${s}_m${m}_${w}"
  local out="outputs/_l808sw_${name}.json"
  local t0=$(date +%s)
  MPLBACKEND=Agg $PY outputs/_l808_sweep.py --seed "$s" --mode "$m" --wind "$w" --out "$out" \
      > "outputs/_l808_logs/${name}.out" 2> "outputs/_l808_logs/${name}.err"
  local rc=$?
  if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $name rc=$rc $(($(date +%s)-t0))s --- $(tail -2 "outputs/_l808_logs/${name}.err" 2>/dev/null | tr '\n' ' ')"
  else
    echo "DONE $name $(($(date +%s)-t0))s $(tail -1 "outputs/_l808_logs/${name}.err")"
  fi
}

while IFS='|' read -r s m w; do
  case "$s" in ''|\#*) continue ;; esac
  out="outputs/_l808sw_s${s}_m${m}_${w}.json"
  if [ -s "$out" ]; then echo "SKIP s${s}_m${m}_${w}"; continue; fi
  while :; do
    r=$(running); f=$(free_kb)
    if [ "$r" -lt "$MAXPAR" ] && [ "${f:-0}" -gt "$MINFREE_KB" ]; then break; fi
    sleep 5
  done
  run_one "$s" "$m" "$w" &
  sleep "$LAUNCH_GAP"
done < "$QUEUE"
wait
echo "L808 SWEEP DONE $(date +%H:%M:%S)"
