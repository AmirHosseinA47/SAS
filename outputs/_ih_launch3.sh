#!/usr/bin/env bash
# Interior-hazard round, Part 3 arms through the memory-aware pool.
cd /e/Projects/SAS || exit 1
MAXPAR=8 MINFREE_KB=2800000 LAUNCH_GAP=20 bash outputs/_dim_pool.sh outputs/_ih_queue3.txt > outputs/_ih_pool3.log 2>&1
