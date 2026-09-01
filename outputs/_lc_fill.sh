#!/bin/sh
# Re-run the 6 campaign cells that died at import (paging file too small).
# STRICTLY SEQUENTIAL - see memory note on parallel batches exhausting RAM.
set -u
PY=./.venv/Scripts/python.exe
run() { # arm wind roles seed
  tag="$1_$2_$3_$4"
  out="outputs/_lc_$tag.json"
  if [ -s "$out" ]; then echo "SKIP $tag (already present)"; return; fi
  echo "START $tag $(date +%H:%M:%S)"
  $PY outputs/_lc_probe.py --wind "$2" --roles "$3" --seeds "$4" --arm "$1" --tag "$tag" \
      > "outputs/_lc_$tag.log" 2>&1
  if [ -s "$out" ]; then echo "OK   $tag $(date +%H:%M:%S)"; else echo "FAIL $tag $(date +%H:%M:%S)"; tail -3 "outputs/_lc_$tag.log"; fi
}
run none east half 505
run none south half 404
run a east default 101
run a east default 202
run a east half 404
run a south half 404
echo "FILL DONE $(date +%H:%M:%S)"
