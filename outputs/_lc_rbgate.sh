#!/bin/sh
# The 70e1b33 route_blocked gate, re-run on the patched source.
# Same 18 runs, same shard split as the idle-retreat round (irfix*), so the
# merge and seed-set verification in _ir_rbmerge.py apply unchanged.
set -u
PY=./.venv/Scripts/python.exe
run() { # tag wind seeds
  out="outputs/_rblatch_camp2_$1_D_$2.json"
  if [ -s "$out" ]; then echo "SKIP $1"; return; fi
  echo "START rb $1 $2 $(date +%H:%M:%S)"
  $PY outputs/_rblatch_campaign2.py --wind "$2" --seeds "$3" --tag "$1" \
      > "outputs/_lc_rb_$1.log" 2>&1
  if [ -s "$out" ]; then echo "OK   rb $1 $(date +%H:%M:%S)"; else echo "FAIL rb $1"; tail -3 "outputs/_lc_rb_$1.log"; fi
}
run lcfixa east 101,202,303,404,505
run lcfixb east 606,707,808,909
run lcfixc east 111,222,333,444
run lcfixs south 101,202,303,404,505
echo "RBGATE DONE $(date +%H:%M:%S)"
