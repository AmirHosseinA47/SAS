#!/usr/bin/env bash
cd /e/Projects/SAS || exit 1
MAXPAR=13 MINFREE_KB=3000000 LAUNCH_GAP=25 bash outputs/_dim_pool.sh outputs/_dim_queue.txt > outputs/_dim_pool.log 2>&1
