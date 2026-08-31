#!/usr/bin/env bash
# Part 1 re-baseline at HEAD 62b4fbe. Combos run SEQUENTIALLY (parallel batches
# exhaust the paging file on this box and fail silently into empty outputs).
set -u
cd "$(dirname "$0")/.."
PY=./.venv/Scripts/python.exe

run() {
  tag="$1"; wind="$2"; roles="$3"; seeds="$4"
  out="outputs/_ui_p1_${tag}.json"
  if [ -s "$out" ]; then echo "SKIP $tag (exists)"; return; fi
  echo "=== START $tag $(date -u +%H:%M:%S) ==="
  $PY outputs/_ui_probe.py --wind "$wind" --roles "$roles" --seeds "$seeds" \
      --steps 240 --prefix _ui_p1 --tag "$tag" \
      >"outputs/_ui_p1_${tag}.log" 2>"outputs/_ui_p1_${tag}.err"
  rc=$?
  if [ -s "$out" ]; then echo "=== OK $tag rc=$rc $(date -u +%H:%M:%S) ==="
  else echo "=== FAIL $tag rc=$rc (empty output) ==="; tail -5 "outputs/_ui_p1_${tag}.err"; fi
}

run east_half    east  half    101,202,303,404,505
run south_half   south half    101,202,303,404,505
run east_default east  default 101,202,303
echo "ALL DONE $(date -u +%H:%M:%S)"
