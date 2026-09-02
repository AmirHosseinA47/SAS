#!/usr/bin/env bash
# Defect #7 Part 2: canonical 13-run sample, 240 steps, scenario D.
#   D/east  half-roles (2 trackers / 2 searchers) seeds 101,202,303,404,505
#   D/south half-roles                            seeds 101,202,303,404,505
#   D/east  default-roles (legacy n-1,1)          seeds 101,202,303
# One PROCESS per run: apply_scenario_config mutates module-level globals and
# the RNG is module-scoped, so combos must not share an interpreter. Separate
# interpreters satisfy that without serialising wall-clock.
set -u
PY=.venv/Scripts/python.exe
mkdir -p outputs/_fs_logs

launch() {  # seed wind ft vs tag
  local s=$1 w=$2 ft=$3 vs=$4 tag=$5
  if [ "$ft" = "-" ]; then
    $PY outputs/_fs_probe.py --seed "$s" --scenario D --wind "$w" \
        --steps 240 --out "outputs/_fs_${tag}_$s.json" \
        > "outputs/_fs_logs/${tag}_$s.log" 2>&1 &
  else
    $PY outputs/_fs_probe.py --seed "$s" --scenario D --wind "$w" \
        --fire-trackers "$ft" --victim-searchers "$vs" --steps 240 \
        --out "outputs/_fs_${tag}_$s.json" \
        > "outputs/_fs_logs/${tag}_$s.log" 2>&1 &
  fi
}

for s in 101 202 303 404 505; do launch $s east  2 2 east_half;  done
for s in 101 202 303 404 505; do launch $s south 2 2 south_half; done
for s in 101 202 303;         do launch $s east  - - east_def;   done

wait

echo "=== RUN LOGS ==="
cat outputs/_fs_logs/*.log
echo "=== EMPTY-OUTPUT CHECK (must list nothing) ==="
for f in outputs/_fs_east_half_*.json outputs/_fs_south_half_*.json outputs/_fs_east_def_*.json; do
  [ -s "$f" ] || echo "EMPTY-OR-MISSING: $f"
done
echo "ALL 13 RUNS DONE"
