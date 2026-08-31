#!/bin/sh
# Lane 6: separability check. Same seed, same params, one half of the fix at
# a time, so "two separable pieces" is demonstrated rather than asserted.
cd /e/Projects/SAS
PY=.venv/Scripts/python.exe
for p in latch leash none; do
  echo "=== pieces=$p  S/half 101  $(date +%H:%M:%S)"
  $PY outputs/_ir_whatif.py --mode apply --wind south --roles half --seeds 101 \
      --steps 240 --pieces "$p" --tag "sep_${p}_S101" 2>>outputs/_ir/lane6.err
done
echo "LANE6 DONE $(date +%H:%M:%S)"
