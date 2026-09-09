#!/usr/bin/env bash
# Depot-cost round: the remaining measurement, restarted after the first chain
# died mid-stage-2.
#
# WHAT HAPPENED. outputs/_dc_chain.sh reached "STAGE 2 dcAref", launched 8 of its
# 13 runs, and its parent bash then vanished at about 09:42. The 8 launched runs
# survived as orphans and kept writing; the remaining 5 never launched, and stages
# 3-5 (the --set inertness check, the four-arm route_blocked gate, the full test
# suite) never started at all. Cause not established. No output was lost or
# corrupted - the pool skips any run whose JSON already exists and is non-empty,
# so this is a clean resume rather than a re-run.
#
# WHAT IS DIFFERENT HERE.
#   1. A HEARTBEAT every 60s. The first chain emitted a line only at stage
#      boundaries, so "working" and "dead" looked identical for 50 minutes. Now
#      silence for more than ~2 minutes means dead, and that is checkable without
#      inspecting the process table.
#   2. It waits for the ORPHANS to drain before starting the pool. Relaunching
#      while they are alive would double-run the two in-flight seeds, with two
#      processes writing one output path.
#   3. Each stage records what it produced, so a partial stage is visible in the
#      log rather than having to be reconstructed from disk.
cd /e/Projects/SAS || exit 1
LOG=outputs/_dc_chain2.log
say() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

heartbeat() {
  while :; do
    sleep 60
    echo "[$(date '+%H:%M:%S')] .. alive; sims=$(( $(tasklist //FI "IMAGENAME eq python.exe" //NH 2>/dev/null | grep -c python) / 2 ))" >> "$LOG"
  done
}
heartbeat & HB=$!
trap 'kill $HB 2>/dev/null' EXIT

sims() { echo $(( $(tasklist //FI "IMAGENAME eq python.exe" //NH 2>/dev/null | grep -c python) / 2 )); }

say "CHAIN2 START - draining $(sims) orphaned run(s) from the dead chain"
while [ "$(sims)" -gt 0 ]; do sleep 20; done
say "orphans drained; dcAref now $(find outputs -name '_ffr_dcAref_*.json' -size +0 | wc -l)/13"

say "STAGE 2 dcAref - resume the armed refactor-inertness control"
MAXPAR=8 MINFREE_KB=2500000 bash outputs/_dim_pool.sh outputs/_dc_refactor_queue.txt \
  >> outputs/_dc_refactor.log 2>&1
say "STAGE 2 done: dcAref $(find outputs -name '_ffr_dcAref_*.json' -size +0 | wc -l)/13"

say "STAGE 3 dcinert - proving the --set passthrough is inert"
bash outputs/_dc_rbgate.sh verify >> outputs/_dc_rbgate.log 2>&1
say "STAGE 3 done: $(ls outputs/_rblatch_camp2_dcinert*_D_*.json 2>/dev/null | wc -l) shard(s)"

say "STAGE 4a route_blocked gate, arms A and B (8 concurrent shards)"
bash outputs/_dc_rbgate.sh A >> outputs/_dc_rbgate.log 2>&1 &
bash outputs/_dc_rbgate.sh B >> outputs/_dc_rbgate.log 2>&1 &
wait
say "STAGE 4a done: A=$(ls outputs/_rblatch_camp2_dcrbA*_D_*.json 2>/dev/null | wc -l)/4 B=$(ls outputs/_rblatch_camp2_dcrbB*_D_*.json 2>/dev/null | wc -l)/4"

say "STAGE 4b route_blocked gate, arms C and D"
bash outputs/_dc_rbgate.sh C >> outputs/_dc_rbgate.log 2>&1 &
bash outputs/_dc_rbgate.sh D >> outputs/_dc_rbgate.log 2>&1 &
wait
say "STAGE 4b done: C=$(ls outputs/_rblatch_camp2_dcrbC*_D_*.json 2>/dev/null | wc -l)/4 D=$(ls outputs/_rblatch_camp2_dcrbD*_D_*.json 2>/dev/null | wc -l)/4"

say "STAGE 5 full test suite at the Part 2 tree"
MPLBACKEND=Agg ./.venv/Scripts/python.exe -m pytest tests -p no:cacheprovider -q \
  > outputs/_dc_pytest_part2.log 2>&1
echo "DC_PYTEST_PART2_COMPLETE rc=$?" >> outputs/_dc_pytest_part2.log
say "STAGE 5 done: $(tail -2 outputs/_dc_pytest_part2.log | head -1)"

say "DC_CHAIN2_COMPLETE"
kill $HB 2>/dev/null
