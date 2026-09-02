#!/bin/sh
# The 70e1b33 route_blocked gate, re-run for the recovery-hysteresis deletion.
# Identical shard split and seed set to every prior round in this chain
# (irfix* / lcfix* / drfix* / prfix*), so _ir_rbmerge.py's seed-set
# verification applies unchanged. Pass a tag prefix: "rhfix" for patched source.
set -u
PY=./.venv/Scripts/python.exe
P="${1:-rhfix}"
run() { # tag wind seeds
  out="outputs/_rblatch_camp2_$1_D_$2.json"
  if [ -s "$out" ]; then echo "SKIP $1"; return; fi
  echo "START rb $1 $2 $(date +%H:%M:%S)"
  $PY outputs/_rblatch_campaign2.py --wind "$2" --seeds "$3" --tag "$1" \
      > "outputs/_rh_rb_$1.log" 2>&1
  if [ -s "$out" ]; then echo "OK   rb $1 $(date +%H:%M:%S)"
  else echo "FAIL rb $1"; tail -3 "outputs/_rh_rb_$1.log"; fi
}
run "${P}a" east 101,202,303,404,505 &
run "${P}b" east 606,707,808,909 &
run "${P}c" east 111,222,333,444 &
run "${P}s" south 101,202,303,404,505 &
wait
echo "RBGATE DONE $(date +%H:%M:%S)"
