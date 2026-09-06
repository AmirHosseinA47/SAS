#!/usr/bin/env bash
# Dimension round: memory-aware job pool over ONE queue of every run of the round.
# Runs are independent processes (each seeds its own RNG; arms differ only in
# --repo and --dim-* args), so there is no reason to serialise them by wave. A
# run is launched only while fewer than MAXPAR are running AND the box has more
# than MINFREE_KB of free commit (FreeVirtualMemory) - the ceiling on this box
# is commit charge, not RAM or cores (see memory: sas-eval-runtime).
#
# queue line: tag|repo|wind|roles|seed|extra harness args (may be empty)
# usage: MAXPAR=13 MINFREE_KB=3000000 bash outputs/_dim_pool.sh outputs/_dim_queue.txt
# Skips any run whose output JSON already exists and is non-empty (restartable).
cd /e/Projects/SAS || exit 1
QUEUE=${1:-outputs/_dim_queue.txt}
MAXPAR=${MAXPAR:-13}
MINFREE_KB=${MINFREE_KB:-3000000}
LAUNCH_GAP=${LAUNCH_GAP:-25}
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_ffr_logs

free_kb () { powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory" | tr -d '\r '; }
running () { jobs -rp | wc -l; }

run_one () { # tag repo wind roles seed extra...
  local tag=$1 repo=$2 w=$3 r=$4 s=$5; shift 5
  local rr=$r; [ "$r" = "default" ] && rr=def
  local name="${tag}_${w}_${rr}_${s}"
  local out="outputs/_ffr_${name}.json"
  local t0=$(date +%s)
  $PY outputs/_ffr_harness.py --repo "$repo" --wind "$w" --roles "$r" --seed "$s" \
      --steps 240 --out "$out" --tag "$tag" "$@" \
      > "outputs/_ffr_logs/${name}.out" 2> "outputs/_ffr_logs/${name}.err"
  local rc=$? sz
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $name rc=$rc size=$sz $(($(date +%s)-t0))s --- $(tail -3 "outputs/_ffr_logs/${name}.err" 2>/dev/null | tr '\n' ' ')"
  else
    echo "DONE $name rc=$rc size=$sz $(($(date +%s)-t0))s $(cat "outputs/_ffr_logs/${name}.out")"
  fi
}

echo "POOL START $(date '+%Y-%m-%d %H:%M:%S') queue=$QUEUE maxpar=$MAXPAR minfree_kb=$MINFREE_KB free_kb_now=$(free_kb)"
n_launched=0; n_skipped=0
while IFS='|' read -r tag repo w r s extra; do
  # a CRLF queue file would leave a CR on the last field, which argparse then
  # sees as a stray argument - strip it from every field
  tag=${tag//$'\r'/}; repo=${repo//$'\r'/}; w=${w//$'\r'/}; r=${r//$'\r'/}; s=${s//$'\r'/}; extra=${extra//$'\r'/}
  [ -z "$tag" ] && continue
  case "$tag" in \#*) continue;; esac
  rr=$r; [ "$r" = "default" ] && rr=def
  name="${tag}_${w}_${rr}_${s}"
  if [ -s "outputs/_ffr_${name}.json" ]; then echo "SKIP $name (exists)"; n_skipped=$((n_skipped+1)); continue; fi
  while :; do
    n=$(running); f=$(free_kb)
    if [ "$n" -lt "$MAXPAR" ] && [ "${f:-0}" -gt "$MINFREE_KB" ]; then break; fi
    sleep 15
  done
  # shellcheck disable=SC2086
  run_one "$tag" "$repo" "$w" "$r" "$s" $extra &
  n_launched=$((n_launched+1))
  echo "LAUNCH $name running=$((n+1)) free_kb=$f $(date +%H:%M:%S)"
  sleep "$LAUNCH_GAP"
done < "$QUEUE"
wait
echo "ALL_DIM_POOL_COMPLETE launched=$n_launched skipped=$n_skipped $(date '+%Y-%m-%d %H:%M:%S')"
