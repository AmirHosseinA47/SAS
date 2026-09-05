#!/usr/bin/env bash
# Feature 1: the campaign's canonical 13-run sample, 240 steps, scenario D,
# one seed per PROCESS (module-level RNG + apply_scenario_config globals make
# in-process combos non-independent; separate interpreters are fine).
#   D/east  half-roles (2 trackers / 2 searchers) seeds 101,202,303,404,505
#   D/south half-roles                            seeds 101,202,303,404,505
#   D/east  default-roles (legacy n-1,1)          seeds 101,202,303
# usage: _ffr_runall.sh <tag> <repo-checkout> [extra harness args, e.g. --set K=V]
# Per sas-eval-runtime: check FILE SIZE per run, not only the exit code.
cd /e/Projects/SAS || exit 1
TAG=$1; REPO=$2; shift 2
EXTRA=("$@")
PY=./.venv/Scripts/python.exe
mkdir -p outputs/_ffr_logs

go () { # wind roles seed
  local w=$1 r=$2 s=$3
  local rr=$r; [ "$r" = "default" ] && rr=def
  local name="${TAG}_${w}_${rr}_${s}"
  local out="outputs/_ffr_${name}.json"
  $PY outputs/_ffr_harness.py --repo "$REPO" --wind "$w" --roles "$r" --seed "$s" \
      --steps 240 --out "$out" --tag "$TAG" "${EXTRA[@]}" \
      > "outputs/_ffr_logs/${name}.out" 2> "outputs/_ffr_logs/${name}.err"
  local rc=$? sz
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ "$rc" -ne 0 ] || [ ! -s "$out" ]; then
    echo "FAIL $name rc=$rc size=$sz --- $(tail -3 "outputs/_ffr_logs/${name}.err" 2>/dev/null | tr '\n' ' ')"
  else
    echo "DONE $name rc=$rc size=$sz $(cat "outputs/_ffr_logs/${name}.out")"
  fi
}

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
echo "START $TAG repo=$REPO extra=${EXTRA[*]} $(date +%H:%M:%S)"
# here-string, not a pipe: the jobs must be THIS shell's children for `wait`
while read -r w r s; do
  [ -z "$w" ] && continue
  go "$w" "$r" "$s" &
done <<< "$RUNS"
wait
echo "ALL_FFR_${TAG}_COMPLETE $(date +%H:%M:%S)"
