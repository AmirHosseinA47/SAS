#!/usr/bin/env bash
# Isolation runs for the seed-808 latch: separate the UAV-spawn relocation from
# the FIREFIGHTER-spawn relocation. Both move at BASE_STATION_MODE>=1, so
# BASE_STATION_SPAWN_FIREFIGHTERS=0 is the only lever that splits them.
#
#   m1_ffs0  mode 1, firefighters back on the pre-feature centre cluster,
#            UAVs still on depot berths.
#            latch persists  -> UAV spawn (detection delay) is the operative change
#            latch disappears-> firefighter spawn is necessary
#   m3_ffs0  same at mode 3, to confirm the return leg/recharge stay irrelevant.
#
# Waits for commit-charge headroom before each launch (see memory: sas-eval-runtime).
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
MINFREE_KB=${MINFREE_KB:-2600000}
mkdir -p outputs/_l808_logs2

free_kb () { powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory" | tr -d '\r '; }

run_iso () { # mode ffspawn name
  local m=$1 fs=$2 name=$3
  local out="outputs/_l808iso_${name}.json"
  [ -s "$out" ] && { echo "SKIP $name"; return; }
  while :; do
    f=$(free_kb)
    [ "${f:-0}" -gt "$MINFREE_KB" ] && break
    sleep 20
  done
  echo "LAUNCH $name $(date +%H:%M:%S) free=${f}"
  local t0=$(date +%s)
  MPLBACKEND=Agg $PY outputs/_l808_sweep.py --seed 808 --mode "$m" --wind east \
      --ffspawn "$fs" --out "$out" \
      > "outputs/_l808_logs2/${name}.out" 2> "outputs/_l808_logs2/${name}.err"
  local rc=$?
  if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $name rc=$rc $(($(date +%s)-t0))s --- $(tail -3 "outputs/_l808_logs2/${name}.err" | tr -d '\r' | tr '\n' ' ')"
  else
    echo "DONE $name $(($(date +%s)-t0))s $(tail -1 "outputs/_l808_logs2/${name}.err" | tr -d '\r')"
  fi
}

run_iso 1 0 m1_ffs0
run_iso 3 0 m3_ffs0
echo "L808 ISO DONE $(date +%H:%M:%S)"
