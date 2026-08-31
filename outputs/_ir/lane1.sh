#!/bin/sh
# Lane 1: reproduce the investigation's exact 13-run sample (PRE-FIX baseline)
cd /e/Projects/SAS
PY=.venv/Scripts/python.exe
run() {  # wind roles seeds tag
  echo "=== START $4  wind=$1 roles=$2 seeds=$3  $(date +%H:%M:%S)"
  $PY outputs/_ir_probe.py --scenario D --wind "$1" --roles "$2" \
      --seeds "$3" --steps 240 --tag "$4" 2>>outputs/_ir/lane1.err
  rc=$?
  f="outputs/_sb_$4.json"
  if [ $rc -ne 0 ] || [ ! -s "$f" ]; then
    echo "!!! FAIL $4 rc=$rc size=$(stat -c%s "$f" 2>/dev/null || echo none)"
  else
    echo "=== OK $4 size=$(stat -c%s "$f")  $(date +%H:%M:%S)"
  fi
}
run east half    101,202,303,404,505 IR_BASE_E_half
run south half   101,202,303,404,505 IR_BASE_S_half
run east default 101,202,303         IR_BASE_E_def
echo "LANE1 DONE $(date +%H:%M:%S)"
