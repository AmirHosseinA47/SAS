#!/bin/sh
# Lane 4: what-if APPLY mode - proposed logic installed, same two seeds.
# This is the side-effect check: trajectory diverges from baseline.
cd /e/Projects/SAS
PY=.venv/Scripts/python.exe
echo "=== START apply S/half 101 $(date +%H:%M:%S)"
$PY outputs/_ir_whatif.py --mode apply --wind south --roles half \
    --seeds 101 --steps 240 --tag app_S101 2>>outputs/_ir/lane4.err
echo "=== START apply E/half 101 $(date +%H:%M:%S)"
$PY outputs/_ir_whatif.py --mode apply --wind east --roles half \
    --seeds 101 --steps 240 --tag app_E101 2>>outputs/_ir/lane4.err
echo "LANE4 DONE $(date +%H:%M:%S)"
