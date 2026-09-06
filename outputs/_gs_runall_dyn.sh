#!/usr/bin/env bash
# Same as _gs_runall.sh but the concurrency gate is GLOBAL and dynamic: a run starts only
# when fewer than MAXPROC real python interpreters (working set > 50 MB) exist on the box
# AND FreeVirtualMemory exceeds MINFREE_KB. Lets a queued wave fill slots as another wave
# drains without exceeding the commit ceiling (sas-eval-runtime).
# usage: _gs_runall_dyn.sh <tag> <maxproc> <minfree_kb> [probe args...]
cd /e/Projects/SAS || exit 1
TAG=$1; MAXPROC=$2; MINFREE=$3; shift 3
EXTRA=("$@")
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_gs_logs

go () { # wind roles seed
  local w=$1 r=$2 s=$3
  local rr=$r; [ "$r" = "default" ] && rr=def
  local name="${TAG}_${w}_${rr}_${s}"
  local out="outputs/_gs_${name}.json"
  $PY outputs/_gs_probe.py --repo /e/Projects/SAS --wind "$w" --roles "$r" --seed "$s" \
      --out "$out" --tag "$TAG" "${EXTRA[@]}" \
      > "outputs/_gs_logs/${name}.out" 2> "outputs/_gs_logs/${name}.err"
  local rc=$? sz
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $name rc=$rc size=$sz $(date +%H:%M:%S) --- $(tail -3 "outputs/_gs_logs/${name}.err" 2>/dev/null | tr '\n' ' ')"
  else
    echo "DONE $name rc=$rc size=$sz $(date +%H:%M:%S) $(cat "outputs/_gs_logs/${name}.out")"
  fi
}

nproc_heavy () {
  # a pytest session grows well past a probe's steady commit, so it counts double
  powershell -NoProfile -Command "\$p = Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { \$_.WorkingSetSize -gt 50MB }; \$n = (\$p | Measure-Object).Count; \$t = (\$p | Where-Object { \$_.CommandLine -match 'pytest' } | Measure-Object).Count; \$n + \$t" 2>/dev/null | tr -d '\r '
}
free_kb () {
  powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory" 2>/dev/null | tr -d '\r '
}

if [ -n "$GS_RUNS" ]; then
  RUNS=$(echo "$GS_RUNS" | tr ';' '\n')
else
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
fi
echo "START $TAG maxproc=$MAXPROC minfree_kb=$MINFREE extra=${EXTRA[*]} $(date +%H:%M:%S)"
while read -r w r s; do
  [ -z "$w" ] && continue
  while :; do
    n=$(nproc_heavy); f=$(free_kb)
    [ -z "$n" ] && n=99; [ -z "$f" ] && f=0
    if [ "$n" -lt "$MAXPROC" ] && [ "$f" -gt "$MINFREE" ]; then break; fi
    sleep 30
  done
  echo "LAUNCH $TAG $w $r $s heavy=$n free_kb=$f $(date +%H:%M:%S)"
  go "$w" "$r" "$s" &
  sleep 120  # let the new interpreter reach its steady commit before re-checking
done <<< "$RUNS"
wait
echo "ALL_GS_${TAG}_COMPLETE $(date +%H:%M:%S)"
