#!/usr/bin/env bash
# Runs after the feature wave frees the box: the post-feature test suite (gate:
# no NEW failures vs the 8 recorded at 9c3eac6) and the route_blocked gate.
cd /e/Projects/SAS || exit 1
while [ "$(ls outputs/_ffr_vmon_*.json 2>/dev/null | wc -l)" -lt 13 ]; do sleep 30; done
sleep 30
echo "=== POST-FEATURE PYTEST (feature ON, working tree) ==="
./.venv/Scripts/python.exe -m pytest tests -q > outputs/_vm_pytest_feature.txt 2>&1
tail -14 outputs/_vm_pytest_feature.txt
echo "=== ROUTE_BLOCKED GATE (feature source at defaults) ==="
bash outputs/_ffr_rbgate.sh vmon
./.venv/Scripts/python.exe outputs/_ir_rbmerge.py --prefix vmon > outputs/_vm_gate_rb.txt 2>&1
tail -30 outputs/_vm_gate_rb.txt
echo "VM_POSTWAVE_COMPLETE $(date +%H:%M:%S)"
