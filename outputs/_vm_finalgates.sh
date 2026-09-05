#!/usr/bin/env bash
# Final gates on the FINAL code (both guards), once the kill-switch control wave
# and the route_blocked campaign have freed the box.
cd /e/Projects/SAS || exit 1
while [ "$(ls outputs/_ffr_vmoff2_*.json 2>/dev/null | wc -l)" -lt 13 ]; do sleep 30; done
while [ "$(ls outputs/_rblatch_camp2_vmon*.json 2>/dev/null | wc -l)" -lt 4 ]; do sleep 30; done
sleep 30
echo "=== FINAL PYTEST (both guards) ==="
./.venv/Scripts/python.exe -m pytest tests -q > outputs/_vm_pytest_final.txt 2>&1
tail -14 outputs/_vm_pytest_final.txt
echo "VM_FINAL_GATES_COMPLETE $(date +%H:%M:%S)"
