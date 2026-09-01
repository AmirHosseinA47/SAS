#!/bin/sh
# Only these fresh seeds can diverge under arm b: they are the three runs whose
# stock trace contains a cur_dist==0 scan that the last_cell guard emptied
# (east/half 606 s27, south/half 606 s96, south/half 1010 s45).  The other
# seven fresh seeds never trigger the condition and are being run anyway by
# _lc_freshb.sh as a null check.  Sequential.
set -u
PY=./.venv/Scripts/python.exe
run() {
  tag="$1_$2_$3_$4"; out="outputs/_lc_$tag.json"
  if [ -s "$out" ]; then echo "SKIP $tag"; return; fi
  echo "START $tag $(date +%H:%M:%S)"
  $PY outputs/_lc_probe.py --wind "$2" --roles "$3" --seeds "$4" --arm "$1" --tag "$tag" \
      > "outputs/_lc_$tag.log" 2>&1
  if [ -s "$out" ]; then echo "OK   $tag $(date +%H:%M:%S)"; else echo "FAIL $tag"; tail -3 "outputs/_lc_$tag.log"; fi
}
run b south half 606
run b south half 1010
echo "PRIO DONE $(date +%H:%M:%S)"
