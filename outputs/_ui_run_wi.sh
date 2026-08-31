#!/usr/bin/env bash
# Part 2 what-if. Sequential (parallel batches exhaust the paging file).
# Only the 8 seeds that actually produce a route_blocked release can differ
# between arms - the other 5 never execute the arm code path at all.
set -u
cd "$(dirname "$0")/.."
PY=./.venv/Scripts/python.exe

run() {
  arm="$1"; tag="$2"; wind="$3"; roles="$4"; seeds="$5"
  out="outputs/_ui_wi_${arm}_${tag}.json"
  if [ -s "$out" ]; then echo "SKIP $arm/$tag"; return; fi
  echo "=== START $arm/$tag $(date -u +%H:%M:%S) ==="
  $PY outputs/_ui_whatif.py --arm "$arm" --wind "$wind" --roles "$roles" \
      --seeds "$seeds" --steps 240 --tag "$tag" \
      >"outputs/_ui_wi_${arm}_${tag}.log" 2>"outputs/_ui_wi_${arm}_${tag}.err"
  rc=$?
  if [ -s "$out" ]; then echo "=== OK $arm/$tag rc=$rc $(date -u +%H:%M:%S) ==="
  else echo "=== FAIL $arm/$tag rc=$rc (empty)"; tail -5 "outputs/_ui_wi_${arm}_${tag}.err"; fi
}

# harness-neutrality control: must reproduce the Part 1 stock sample exactly
run none    Eh404 east  half    404
run none    Ed101 east  default 101

for arm in abort retreat; do
  run "$arm" Eh east  half    101,202,303,404,505
  run "$arm" Ed east  default 101,303
  run "$arm" Sh south half    404
done
echo "ALL DONE $(date -u +%H:%M:%S)"
