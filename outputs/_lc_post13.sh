#!/bin/sh
# POST-FIX arm: the probe with --arm none, run against the PATCHED source.
# Doubles as the equivalence check - these must match the arm-b monkeypatch
# data (_lc_b_*) exactly, or the source patch is not what was validated.
set -u
PY=./.venv/Scripts/python.exe
run() { # wind roles seed
  tag="post_$1_$2_$3"; out="outputs/_lc_$tag.json"
  if [ -s "$out" ]; then echo "SKIP $tag"; return; fi
  echo "START $tag $(date +%H:%M:%S)"
  $PY outputs/_lc_probe.py --wind "$1" --roles "$2" --seeds "$3" --arm none --tag "$tag" \
      > "outputs/_lc_$tag.log" 2>&1
  if [ -s "$out" ]; then echo "OK   $tag $(date +%H:%M:%S)"; else echo "FAIL $tag"; tail -3 "outputs/_lc_$tag.log"; fi
}
run east half 505
run east default 101
run east default 202
run east default 303
run east half 101
run east half 202
run east half 303
run east half 404
run south half 101
run south half 202
run south half 303
run south half 404
run south half 505
echo "POST13 DONE $(date +%H:%M:%S)"
