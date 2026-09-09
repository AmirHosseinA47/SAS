#!/usr/bin/env bash
# Depot-cost round: arms C and D of the route_blocked gate, plus the full test
# suite alongside. Third attempt; the first two both stalled and this file
# records why so the next person does not re-derive it.
#
# CHAIN 1 died during stage 2 with no diagnostic. CAUSE STILL UNKNOWN, and it is
# NOT the bug fixed below: chain 1 had the same bare `wait` but no heartbeat, so
# its `wait` would have returned correctly. Two failures, two different causes,
# one of them still open.
#
# CHAIN 2 stalled at stage 4a, and that one IS understood - it was the heartbeat
# I added to chain 2 to make a silent death detectable:
#
#     heartbeat &                 # never exits
#     bash _dc_rbgate.sh A & bash _dc_rbgate.sh B &
#     wait                        # <-- waits for A, B *and the heartbeat*
#
# Bare `wait` waits for EVERY background job of the shell. Arms A and B finished
# at 11:59:17 and 12:01:07; `wait` blocked on the heartbeat forever, so stage 4b
# never started. Reproduced in miniature: bare wait hangs, `wait "$A" "$B"`
# proceeds. EVERY WAIT IN THIS FILE IS TARGETED AT EXPLICIT PIDS. Do not
# reintroduce a bare `wait` while a heartbeat is running.
#
# pytest runs ALONGSIDE the gate rather than after it. It is one light process
# against 8 shards at ~0.9 GB each, and free commit is ~14 GB, so the two fit -
# and it turns 77 + 35 minutes of wall clock into about 80.
cd /e/Projects/SAS || exit 1
LOG=outputs/_dc_chain3.log
STAGE="starting"
say() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
sims() { echo $(( $(tasklist //FI "IMAGENAME eq python.exe" //NH 2>/dev/null | grep -c python) / 2 )); }

heartbeat() {
  while :; do
    sleep 60
    echo "[$(date '+%H:%M:%S')] .. alive [$(cat outputs/_dc_stage3.txt 2>/dev/null)] sims=$(sims) shards=$(ls outputs/_rblatch_camp2_dcrb[CD]*_D_*.json 2>/dev/null | wc -l)/8" >> "$LOG"
  done
}
stage() { STAGE="$1"; echo "$1" > outputs/_dc_stage3.txt; say "STAGE: $1"; }

heartbeat & HB=$!
trap 'kill $HB 2>/dev/null; rm -f outputs/_dc_stage3.txt' EXIT

say "CHAIN3 START (sims already running: $(sims) - expected 0)"

stage "gate arms C and D + full test suite, concurrent"
MPLBACKEND=Agg ./.venv/Scripts/python.exe -m pytest tests -p no:cacheprovider -q \
  > outputs/_dc_pytest_part2.log 2>&1 &
PYT=$!
say "pytest launched pid=$PYT"

bash outputs/_dc_rbgate.sh C >> outputs/_dc_rbgate.log 2>&1 & CPID=$!
bash outputs/_dc_rbgate.sh D >> outputs/_dc_rbgate.log 2>&1 & DPID=$!
say "gate arms launched: C pid=$CPID  D pid=$DPID"

wait "$CPID" "$DPID"
say "GATE DONE: C=$(ls outputs/_rblatch_camp2_dcrbC*_D_*.json 2>/dev/null | wc -l)/4 D=$(ls outputs/_rblatch_camp2_dcrbD*_D_*.json 2>/dev/null | wc -l)/4"

stage "waiting on pytest"
wait "$PYT"
echo "DC_PYTEST_PART2_COMPLETE" >> outputs/_dc_pytest_part2.log
say "PYTEST DONE: $(grep -E '^[0-9]+ (failed|passed)' outputs/_dc_pytest_part2.log | tail -1)"

say "DC_CHAIN3_COMPLETE"
kill $HB 2>/dev/null
