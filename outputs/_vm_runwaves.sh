#!/usr/bin/env bash
# Feature 2: run the control (kill switch) and feature waves back to back, once
# the baseline wave has landed. ONE 13-run wave at a time - the box's limit is
# commit charge, not physical RAM (see the sas-eval-runtime note).
cd /e/Projects/SAS || exit 1
FEAT_REPO=/e/Projects/SAS

# wait for the baseline wave to finish before starting anything
while [ "$(ls outputs/_ffr_vmbase_*.json 2>/dev/null | wc -l)" -lt 13 ]; do sleep 15; done
sleep 20
echo "BASELINE_SEEN $(date +%H:%M:%S)"

echo "=== CONTROL WAVE (kill switch: VICTIM_FLEE_TRIGGER_DISTANCE=0) ==="
bash outputs/_ffr_runall.sh vmoff "$FEAT_REPO" --set VICTIM_FLEE_TRIGGER_DISTANCE=0
echo "=== FEATURE WAVE (defaults: trigger 3, leash 6) ==="
bash outputs/_ffr_runall.sh vmon "$FEAT_REPO"
echo "ALL_VM_WAVES_COMPLETE $(date +%H:%M:%S)"
