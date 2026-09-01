#!/bin/sh
# One (wind, roles, seed, arm) cell of the dispatch-reachability sample.
# Usage: _dr_run.sh <wind> <roles> <seed> <arm> [margin]
# Idempotent: an existing non-empty output is left alone, so a re-run of the
# whole sheet only fills the gaps.
set -u
PY=./.venv/Scripts/python.exe
w="$1"; r="$2"; s="$3"; arm="$4"; m="${5:-2}"
tag="${arm}_${w}_${r}_${s}"
out="outputs/_dr_${tag}.json"
if [ -s "$out" ]; then echo "SKIP $tag"; exit 0; fi
echo "START $tag $(date +%H:%M:%S)"
$PY outputs/_dr_probe.py --wind "$w" --roles "$r" --seeds "$s" --arm "$arm" \
    --margin "$m" --tag "$tag" > "outputs/_dr_${tag}.log" 2>&1
if [ -s "$out" ]; then echo "OK   $tag $(date +%H:%M:%S)"
else echo "FAIL $tag"; tail -5 "outputs/_dr_${tag}.log"; fi
