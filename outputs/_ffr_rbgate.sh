#!/usr/bin/env bash
# NOTE the interpreter: the depot-cost round added an EXTRA=("$@") array and
# the "${EXTRA[@]+...}" empty-safe expansion below, both of which are bash/ksh
# and a PARSE ERROR in dash. The file declared #!/bin/sh before that. Every
# caller in this repo invokes it as `bash outputs/_ffr_rbgate.sh ...`, so the
# shebang was bypassed and nothing broke - but a direct ./ execution on a box
# where /bin/sh is dash would have failed at parse time, before running a
# single seed. Declared correctly rather than left as a trap.
# The 70e1b33 route_blocked gate, re-run for feature 1 (firefighter rescue
# absence). Identical shard split and seed set to every prior round in this
# chain (irfix* / lcfix* / drfix* / prfix* / rhfix*), so _ir_rbmerge.py's
# seed-set verification applies unchanged. Pass a tag prefix: "ffabs" for the
# feature source at its defaults ([3,5]).
# Depot-cost round: everything after the tag prefix is passed straight through to
# _rblatch_campaign2.py, so an ARMED arm can be gated without touching the shipped
# default. Usage: bash outputs/_ffr_rbgate.sh dcD --set BASE_STATION_MODE=3 ...
# With no extra arguments this is byte-for-byte the command it always ran.
set -u
PY=./.venv/Scripts/python.exe
P="${1:-ffabs}"
shift || true
EXTRA=("$@")
run() { # tag wind seeds
  out="outputs/_rblatch_camp2_$1_D_$2.json"
  if [ -s "$out" ]; then echo "SKIP $1"; return; fi
  echo "START rb $1 $2 $(date +%H:%M:%S)"
  $PY outputs/_rblatch_campaign2.py --wind "$2" --seeds "$3" --tag "$1" \
      "${EXTRA[@]+"${EXTRA[@]}"}" \
      > "outputs/_ffr_rb_$1.log" 2>&1
  if [ -s "$out" ]; then echo "OK   rb $1 $(date +%H:%M:%S)"
  else echo "FAIL rb $1"; tail -3 "outputs/_ffr_rb_$1.log"; fi
}
run "${P}a" east 101,202,303,404,505 &
run "${P}b" east 606,707,808,909 &
run "${P}c" east 111,222,333,444 &
run "${P}s" south 101,202,303,404,505 &
wait
echo "RBGATE DONE $(date +%H:%M:%S)"
