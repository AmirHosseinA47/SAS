#!/usr/bin/env bash
# Memory-aware job pool for the latch-frequency sweep (CR-hardened).
# The v1 pool lost 34 completed runs because the CRLF queue put a literal CR
# into $w, which became part of the --out filename -> OSError at the final
# json.dump. Every field is now stripped of CR before use.
# queue line: seed|mode|wind
# usage: MAXPAR=8 MINFREE_KB=2000000 bash outputs/_l808_pool2.sh outputs/_l808_queue2.txt
cd /e/Projects/SAS || exit 1
QUEUE=${1:-outputs/_l808_queue2.txt}
MAXPAR=${MAXPAR:-8}
MINFREE_KB=${MINFREE_KB:-2000000}
LAUNCH_GAP=${LAUNCH_GAP:-8}
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_l808_logs2

free_kb () { powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory" | tr -d '\r '; }
running () { jobs -rp | wc -l; }

run_one () { # seed mode wind
  local s=$1 m=$2 w=$3
  local name="s${s}_m${m}_${w}"
  local out="outputs/_l808sw2_${name}.json"
  local t0=$(date +%s)
  MPLBACKEND=Agg $PY outputs/_l808_sweep.py --seed "$s" --mode "$m" --wind "$w" --out "$out" \
      > "outputs/_l808_logs2/${name}.out" 2> "outputs/_l808_logs2/${name}.err"
  local rc=$?
  if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $name rc=$rc $(($(date +%s)-t0))s --- $(tail -2 "outputs/_l808_logs2/${name}.err" 2>/dev/null | tr -d '\r' | tr '\n' ' ')"
  else
    echo "DONE $name $(($(date +%s)-t0))s $(tail -1 "outputs/_l808_logs2/${name}.err" | tr -d '\r')"
  fi
}

while IFS='|' read -r s m w; do
  s=$(echo "$s" | tr -d '\r\n ')
  m=$(echo "$m" | tr -d '\r\n ')
  w=$(echo "$w" | tr -d '\r\n ')
  case "$s" in ''|\#*) continue ;; esac
  out="outputs/_l808sw2_s${s}_m${m}_${w}.json"
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
echo "L808 SWEEP2 DONE $(date +%H:%M:%S)"
