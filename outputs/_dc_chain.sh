#!/usr/bin/env bash
# Depot-cost round: everything that has to happen after the 128-run wave, in one
# unattended chain, so the box is never idle and never oversubscribed.
#
# ORDERING IS A MEMORY DECISION, not a logical one. The ceiling on this box is
# COMMIT CHARGE (~0.85-0.9 GB per simulation process, ~13-15 processes maximum),
# and an over-subscribed batch fails SILENTLY into zero-byte outputs with the
# traceback in the .err file. So:
#   1  wait for the wave (10 concurrent) to finish before starting anything
#   2  dcAref, 13 runs through the memory-aware pool, which self-throttles
#   3  rbcv, ONE process: the inertness check that keeps the e703861 gate
#      reference valid. If this fails nothing downstream is readable, so it runs
#      alone and first.
#   4  rbgate arms, TWO AT A TIME. _ffr_rbgate.sh backgrounds four shards per arm,
#      so two arms is 8 concurrent - the most that fits with headroom.
#
# Every stage writes a completion marker so a watcher can tell where it is, and
# every stage is restartable: the pool skips existing JSONs and _ffr_rbgate.sh
# skips existing shards.
cd /e/Projects/SAS || exit 1
LOG=outputs/_dc_chain.log
say() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

say "CHAIN START - waiting for the wave"
until grep -q "DC_WAVE_COMPLETE" outputs/_dc_wave.log 2>/dev/null; do sleep 30; done
say "wave complete"

say "STAGE 2 dcAref - the armed refactor-inertness control (13 runs)"
MAXPAR=8 MINFREE_KB=2500000 bash outputs/_dim_pool.sh outputs/_dc_refactor_queue.txt \
  >> outputs/_dc_refactor.log 2>&1
say "STAGE 2 done: $(find outputs -name '_ffr_dcAref_*.json' -size +0 | wc -l) of 13 present"

say "STAGE 3 rbcv - proving the --set passthrough is inert"
bash outputs/_dc_rbgate.sh verify >> outputs/_dc_rbgate.log 2>&1
say "STAGE 3 done"

say "STAGE 4a rbgate arms A and B"
bash outputs/_dc_rbgate.sh A >> outputs/_dc_rbgate.log 2>&1 &
bash outputs/_dc_rbgate.sh B >> outputs/_dc_rbgate.log 2>&1 &
wait
say "STAGE 4a done"

say "STAGE 4b rbgate arms C and D"
bash outputs/_dc_rbgate.sh C >> outputs/_dc_rbgate.log 2>&1 &
bash outputs/_dc_rbgate.sh D >> outputs/_dc_rbgate.log 2>&1 &
wait
say "STAGE 4b done"

say "STAGE 5 full test suite at the Part 2 tree"
MPLBACKEND=Agg ./.venv/Scripts/python.exe -m pytest tests -p no:cacheprovider -q \
  > outputs/_dc_pytest_part2.log 2>&1
echo "DC_PYTEST_PART2_COMPLETE rc=$?" >> outputs/_dc_pytest_part2.log
say "STAGE 5 done"

say "DC_CHAIN_COMPLETE"
