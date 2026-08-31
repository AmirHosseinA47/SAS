#!/bin/sh
# Re-run the 70e1b33 route_blocked gate campaign with the idle-retreat fix
# layered on top. Identical harness, params and seeds to the round that set
# the baseline (outputs/_rblatch_camp2_exact_D_{east,south}.json), so the
# comparison is seed-for-seed on the same instrument.
#
# The 13 east seeds are sharded across processes purely for wall-clock; the
# harness accumulates only per-seed `evals` plus simple global counters, both
# of which merge additively (see _ir_rbmerge.py).
#
# usage: sh rbgate.sh <tag-prefix>
cd /e/Projects/SAS
PRE="${1:-irfix}"
PY=.venv/Scripts/python.exe

run() {  # tag wind seeds
  $PY outputs/_rblatch_campaign2.py --scenario D --wind "$2" --steps 240 \
      --seeds "$3" --tag "$1" >/dev/null 2>>"outputs/_ir/rbgate_$1_$2.err"
  rc=$?
  f="outputs/_rblatch_camp2_$1_D_$2.json"
  if [ $rc -ne 0 ] || [ ! -s "$f" ]; then
    echo "FAIL rb $1/$2 rc=$rc size=$(stat -c%s "$f" 2>/dev/null || echo none)"
  else
    echo "OK   rb $1/$2 $(stat -c%s "$f") $(date +%H:%M:%S)"
  fi
}

echo "=== RBGATE START $(date +%H:%M:%S)"
run "${PRE}a" east  101,202,303,404,505 &
run "${PRE}b" east  606,707,808,909 &
run "${PRE}c" east  111,222,333,444 &
run "${PRE}s" south 101,202,303,404,505 &
wait
echo "RBGATE DONE $(date +%H:%M:%S)"
