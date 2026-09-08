#!/usr/bin/env bash
# Latch-fix round: memory-aware job pool for the 17-seed x 2-mode latch sweep,
# re-run through outputs/_lf_assert.py so the corrected latch definition and the
# per-cleared-unit accountability verdict are recorded in the same artifact.
#
# CR-hardened, for the reason outputs/latch808_part1.txt section 10 records: a
# CRLF queue left a literal CR in the last field, which became part of the --out
# filename and destroyed 34 completed runs at the final write.
#
# queue line: seed|mode|wind|switch
# usage: MAXPAR=5 MINFREE_KB=2500000 bash outputs/_lf_sweeppool.sh outputs/_lf_sweepq.txt
# Skips any run whose output JSON already exists and is non-empty (restartable).
cd /e/Projects/SAS || exit 1
QUEUE=${1:-outputs/_lf_sweepq.txt}
MAXPAR=${MAXPAR:-5}
MINFREE_KB=${MINFREE_KB:-2500000}
LAUNCH_GAP=${LAUNCH_GAP:-15}
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_lf_logs

free_kb () { powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory" | tr -d '\r '; }
running () { jobs -rp | wc -l; }

run_one () { # seed mode wind switch
  local s=$1 m=$2 w=$3 sw=$4
  local name="s${s}_m${m}_${w}_sw${sw}"
  local out="outputs/_lfsw_${name}.json"
  local t0=$(date +%s)
  MPLBACKEND=Agg $PY outputs/_lf_assert.py --seed "$s" --mode "$m" --wind "$w" \
      --set "ROUTE_BLOCK_STALE_CLEAR=$sw" --out "$out" \
      > "outputs/_lf_logs/${name}.out" 2> "outputs/_lf_logs/${name}.err"
  local rc=$?
  if [ ! -s "$out" ]; then
    echo "FAIL $name rc=$rc $(($(date +%s)-t0))s --- $(tail -2 "outputs/_lf_logs/${name}.err" 2>/dev/null | tr -d '\r' | tr '\n' ' ')"
  else
    # rc 3 means the gate failed inside the run - the artifact is still valid
    echo "DONE $name rc=$rc $(($(date +%s)-t0))s $(tail -1 "outputs/_lf_logs/${name}.err" | tr -d '\r')"
  fi
}

echo "LF SWEEP START $(date '+%Y-%m-%d %H:%M:%S') queue=$QUEUE maxpar=$MAXPAR free_kb=$(free_kb)"
while IFS='|' read -r s m w sw; do
  s=$(echo "$s" | tr -d '\r\n ')
  m=$(echo "$m" | tr -d '\r\n ')
  w=$(echo "$w" | tr -d '\r\n ')
  sw=$(echo "$sw" | tr -d '\r\n ')
  case "$s" in ''|\#*) continue ;; esac
  out="outputs/_lfsw_s${s}_m${m}_${w}_sw${sw}.json"
  if [ -s "$out" ]; then echo "SKIP s${s}_m${m}_${w}_sw${sw}"; continue; fi
  while :; do
    r=$(running); f=$(free_kb)
    if [ "$r" -lt "$MAXPAR" ] && [ "${f:-0}" -gt "$MINFREE_KB" ]; then break; fi
    sleep 15
  done
  run_one "$s" "$m" "$w" "$sw" &
  echo "LAUNCH s${s}_m${m}_${w}_sw${sw} free_kb=$f $(date +%H:%M:%S)"
  sleep "$LAUNCH_GAP"
done < "$QUEUE"
wait
echo "LF SWEEP DONE $(date '+%Y-%m-%d %H:%M:%S')"
