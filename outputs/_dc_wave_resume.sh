#!/usr/bin/env bash
# Depot-cost round: resume the 128-run wave after the interruption.
# The pool skips any run whose output JSON already exists and is non-empty, so
# this re-runs only what is missing (64 of 128 at the time of writing). Output is
# APPENDED to the original wave log so the round has one continuous record.
cd /e/Projects/SAS || exit 1
{
  echo "=== WAVE RESUMED $(date '+%Y-%m-%d %H:%M:%S') ==="
  MAXPAR=${MAXPAR:-10} MINFREE_KB=${MINFREE_KB:-2500000} \
    bash outputs/_dim_pool.sh outputs/_dc_queue.txt
  echo "DC_WAVE_COMPLETE $(date '+%Y-%m-%d %H:%M:%S')"
} >> outputs/_dc_wave.log 2>&1
