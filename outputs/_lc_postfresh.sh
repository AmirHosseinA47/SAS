#!/bin/sh
# POST-FIX arm over the 10 fresh seeds, for the pooled 23-run figure.
set -u
PY=./.venv/Scripts/python.exe
run() {
  tag="post_$1_$2_$3"; out="outputs/_lc_$tag.json"
  if [ -s "$out" ]; then echo "SKIP $tag"; return; fi
  echo "START $tag $(date +%H:%M:%S)"
  $PY outputs/_lc_probe.py --wind "$1" --roles "$2" --seeds "$3" --arm none --tag "$tag" \
      > "outputs/_lc_$tag.log" 2>&1
  if [ -s "$out" ]; then echo "OK   $tag $(date +%H:%M:%S)"; else echo "FAIL $tag"; tail -3 "outputs/_lc_$tag.log"; fi
}
# the three that can diverge first, then the seven null checks
run south half 606
run south half 1010
run east half 606
run east half 707
run east half 808
run east half 909
run east half 1010
run south half 707
run south half 808
run south half 909
echo "POSTFRESH DONE $(date +%H:%M:%S)"
