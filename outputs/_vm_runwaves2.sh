#!/usr/bin/env bash
# Feature 2, guards round. Runs after the guard-1-only wave (vmon2) lands.
#   vmon3   both guards (dead-end avoidance + leash re-anchoring)
#   vmoff2  kill switch WITH both guards present - re-proves byte identity
# One 13-run wave at a time; the box's limit is commit charge.
cd /e/Projects/SAS || exit 1
while [ "$(ls outputs/_ffr_vmon2_*.json 2>/dev/null | wc -l)" -lt 13 ]; do sleep 20; done
sleep 20
echo "VMON2_SEEN $(date +%H:%M:%S)"

echo "=== FEATURE WAVE, BOTH GUARDS (vmon3) ==="
bash outputs/_ffr_runall.sh vmon3 /e/Projects/SAS
echo "=== KILL-SWITCH CONTROL WITH BOTH GUARDS (vmoff2) ==="
bash outputs/_ffr_runall.sh vmoff2 /e/Projects/SAS --set VICTIM_FLEE_TRIGGER_DISTANCE=0
echo "ALL_GUARD_WAVES_COMPLETE $(date +%H:%M:%S)"
