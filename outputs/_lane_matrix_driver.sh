#!/usr/bin/env bash
# Sequential driver for the instrumented multi-searcher lane matrix.
set -u
cd /e/Projects/SAS
PY=./.venv/Scripts/python.exe
export PYTHONPATH=/e/Projects/SAS
SEEDS=101,202,303,404,505
STEPS=240
OUT=outputs/lane_matrix

mkdir -p "$OUT"

run() {
  sc="$1"; wind="$2"; uavs="$3"; ft="$4"; vs="$5"
  tag="${sc}_${wind}"
  echo "=== START $tag  ($uavs UAV: ${ft}T+${vs}S)  $(date +%H:%M:%S) ==="
  $PY outputs/_lane_matrix.py --scenario "$sc" --wind "$wind" --seeds "$SEEDS" \
      --steps "$STEPS" --uavs "$uavs" --fire-trackers "$ft" --victim-searchers "$vs" \
      --out "$OUT/${tag}.json"
  echo "=== DONE  $tag  $(date +%H:%M:%S) ==="
}

for w in east west north south; do
  run C "$w" 5 3 2
done
for w in east west north south; do
  run D "$w" 4 2 2
done
echo "ALL DONE $(date +%H:%M:%S)"
