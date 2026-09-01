#!/bin/sh
# Arm b on the 10 fresh seeds, to widen the evidence base beyond the single
# cur_dist==0 event the baseline 13-run sample contains. STRICTLY SEQUENTIAL.
set -u
PY=./.venv/Scripts/python.exe
run() { # arm wind roles seed
  tag="$1_$2_$3_$4"; out="outputs/_lc_$tag.json"
  if [ -s "$out" ]; then echo "SKIP $tag"; return; fi
  echo "START $tag $(date +%H:%M:%S)"
  $PY outputs/_lc_probe.py --wind "$2" --roles "$3" --seeds "$4" --arm "$1" --tag "$tag" \
      > "outputs/_lc_$tag.log" 2>&1
  if [ -s "$out" ]; then echo "OK   $tag $(date +%H:%M:%S)"; else echo "FAIL $tag"; tail -3 "outputs/_lc_$tag.log"; fi
}
for s in 606 707 808 909 1010; do run b east half $s; done
for s in 606 707 808 909 1010; do run b south half $s; done
echo "FRESH-B DONE $(date +%H:%M:%S)"
