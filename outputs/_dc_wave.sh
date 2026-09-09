#!/usr/bin/env bash
# Depot-cost round: the 128-run wave, through the memory-aware pool.
#
# MINFREE_KB is the real throttle on this box - the ceiling is COMMIT CHARGE, not
# RAM or cores, and a batch that exhausts it fails SILENTLY into zero-byte outputs
# (the traceback goes to the .err file). The pool checks free commit before every
# launch and _dim_pool.sh already refuses to start a run below the floor, so the
# wave self-throttles rather than dying.
#
# Restartable: the pool skips any run whose output JSON already exists and is
# non-empty, so the four verification runs are not repeated and an interrupted
# wave can simply be re-run.
cd /e/Projects/SAS || exit 1
MAXPAR=${MAXPAR:-10} MINFREE_KB=${MINFREE_KB:-2500000} \
  bash outputs/_dim_pool.sh outputs/_dc_queue.txt
echo "DC_WAVE_COMPLETE $(date '+%Y-%m-%d %H:%M:%S')"
