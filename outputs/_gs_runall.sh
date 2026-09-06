#!/usr/bin/env bash
# Grid-scale round: run the campaign's canonical 13-run scenario-D sample through
# outputs/_gs_probe.py, one seed per PROCESS, at most MAXPAR concurrent.
#   D/east  half-roles (2 trackers / 2 searchers) seeds 101,202,303,404,505
#   D/south half-roles                            seeds 101,202,303,404,505
#   D/east  default-roles (legacy n-1,1)          seeds 101,202,303
# usage: _gs_runall.sh <tag> <maxpar> [probe args...]   e.g. --grid 100 --steps 960 --checkpoints 240,500 --expose-dims --fast-nsb
# env GS_RUNS="east half 101;south half 202" overrides the run list.
# Per sas-eval-runtime: check FILE SIZE per run, not only the exit code.
cd /e/Projects/SAS || exit 1
TAG=$1; MAXPAR=$2; shift 2
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
echo "START $TAG maxpar=$MAXPAR extra=${EXTRA[*]} $(date +%H:%M:%S)"
while read -r w r s; do
  [ -z "$w" ] && continue
  while [ "$(jobs -rp | wc -l)" -ge "$MAXPAR" ]; do sleep 10; done
  go "$w" "$r" "$s" &
  sleep 2
done <<< "$RUNS"
wait
echo "ALL_GS_${TAG}_COMPLETE $(date +%H:%M:%S)"
