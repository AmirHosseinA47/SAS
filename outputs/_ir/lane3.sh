#!/bin/sh
# Lane 3: what-if OBSERVE mode - stock trajectory, plus a non-applied read of
# what the proposed logic would decide at every latched idle call.
cd /e/Projects/SAS
PY=.venv/Scripts/python.exe
echo "=== START observe S/half 101 $(date +%H:%M:%S)"
$PY outputs/_ir_whatif.py --mode observe --wind south --roles half \
    --seeds 101 --steps 240 --tag obs_S101 2>>outputs/_ir/lane3.err
echo "=== START observe E/half 101 $(date +%H:%M:%S)"
$PY outputs/_ir_whatif.py --mode observe --wind east --roles half \
    --seeds 101 --steps 240 --tag obs_E101 2>>outputs/_ir/lane3.err
echo "LANE3 DONE $(date +%H:%M:%S)"
