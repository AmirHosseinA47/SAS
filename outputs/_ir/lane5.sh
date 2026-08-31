#!/bin/sh
# Lane 5: what-if APPLY with the refined revalidation tail (clear stall flag
# only, keep the anti-oscillation memory). Two seeds: the clearest latch case
# (S/half 101) and the extreme stale-origin case (E/half 101, d=40).
cd /e/Projects/SAS
PY=.venv/Scripts/python.exe
echo "=== apply2 S/half 101 $(date +%H:%M:%S)"
$PY outputs/_ir_whatif.py --mode apply --wind south --roles half \
    --seeds 101 --steps 240 --tag app2_S101 2>>outputs/_ir/lane5.err
echo "=== apply2 E/half 101 $(date +%H:%M:%S)"
$PY outputs/_ir_whatif.py --mode apply --wind east --roles half \
    --seeds 101 --steps 240 --tag app2_E101 2>>outputs/_ir/lane5.err
echo "LANE5 DONE $(date +%H:%M:%S)"
