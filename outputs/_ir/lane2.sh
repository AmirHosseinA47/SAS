#!/bin/sh
# Lane 2: FRESH seeds - independent check that the shape is not seed-specific
cd /e/Projects/SAS
PY=.venv/Scripts/python.exe
run() {
  echo "=== START $4  wind=$1 roles=$2 seeds=$3  $(date +%H:%M:%S)"
  $PY outputs/_ir_probe.py --scenario D --wind "$1" --roles "$2" \
      --seeds "$3" --steps 240 --tag "$4" 2>>outputs/_ir/lane2.err
  rc=$?
  f="outputs/_sb_$4.json"
  if [ $rc -ne 0 ] || [ ! -s "$f" ]; then
    echo "!!! FAIL $4 rc=$rc size=$(stat -c%s "$f" 2>/dev/null || echo none)"
  else
    echo "=== OK $4 size=$(stat -c%s "$f")  $(date +%H:%M:%S)"
  fi
}
run east  half 606,707,808,909,111 IR_FRESH_E_half
run south half 606,707,808,909,111 IR_FRESH_S_half
echo "LANE2 DONE $(date +%H:%M:%S)"
