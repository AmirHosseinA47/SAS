#!/usr/bin/env bash
# Stage 2: waits for the multi-searcher matrix, then runs the DEFAULT n<=1
# matrix (16 combos, no role overrides) and the post-fix east-wind probes.
set -u
cd /e/Projects/SAS
PY=./.venv/Scripts/python.exe
export PYTHONPATH=/e/Projects/SAS
export MPLBACKEND=Agg

while ! grep -q "ALL DONE" outputs/_lane_clamp_ms_driver.log 2>/dev/null; do
  sleep 20
done
echo "=== MS MATRIX DONE, starting default matrix $(date +%H:%M:%S) ==="

for sc in A B C D; do
  for w in east west north south; do
    echo "--- default $sc $w $(date +%H:%M:%S) ---"
    $PY evaluate_scenarios.py --scenario "$sc" --wind "$w" --n 5 \
        --seeds 101,202,303,404,505 --steps 240 \
        > "outputs/lane_clamp_default_${sc}_${w}.txt" 2>"outputs/_lane_clamp_default_${sc}_${w}.log"
  done
done
echo "=== DEFAULT MATRIX DONE $(date +%H:%M:%S) ==="

echo "--- post-fix violation probe east $(date +%H:%M:%S) ---"
$PY outputs/_lane_probe_violation.py east 101 120 2 \
    > outputs/_lane_clamp_probe_violation_east_POST.txt 2>&1
echo "ALL STAGE2 DONE $(date +%H:%M:%S)"
