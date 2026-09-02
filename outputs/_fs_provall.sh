#!/usr/bin/env bash
# Defect #7 Part 2b: reason-provenance over the same canonical 13-run sample.
# Answers: is the fail-safe mode sustained by INDEPENDENT evidence (analysis /
# execution), or is it self-confirming (the planner's own decision read back)?
set -u
PY=.venv/Scripts/python.exe
mkdir -p outputs/_fs_plogs

launch() {  # seed wind ft vs tag
  local s=$1 w=$2 ft=$3 vs=$4 tag=$5
  if [ "$ft" = "-" ]; then
    $PY outputs/_fs_prov.py --seed "$s" --scenario D --wind "$w" \
        --steps 240 --out "outputs/_fsp_${tag}_$s.json" \
        > "outputs/_fs_plogs/${tag}_$s.log" 2>&1 &
  else
    $PY outputs/_fs_prov.py --seed "$s" --scenario D --wind "$w" \
        --fire-trackers "$ft" --victim-searchers "$vs" --steps 240 \
        --out "outputs/_fsp_${tag}_$s.json" \
        > "outputs/_fs_plogs/${tag}_$s.log" 2>&1 &
  fi
}

for s in 101 202 303 404 505; do launch $s east  2 2 east_half;  done
for s in 101 202 303 404 505; do launch $s south 2 2 south_half; done
for s in 101 202 303;         do launch $s east  - - east_def;   done

wait

echo "=== PROVENANCE LOGS ==="
cat outputs/_fs_plogs/*.log
echo "=== EMPTY-OUTPUT CHECK (must list nothing) ==="
for f in outputs/_fsp_east_half_*.json outputs/_fsp_south_half_*.json outputs/_fsp_east_def_*.json; do
  [ -s "$f" ] || echo "EMPTY-OR-MISSING: $f"
done
echo "ALL 13 PROVENANCE RUNS DONE"
