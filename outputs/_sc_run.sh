#!/usr/bin/env bash
# Defect #9-A1 A/B runner.  One PROCESS per (arm, combo, seed): separate
# interpreters do not share the module-level scenario globals or the module-level
# RNG, so the "combos sequentially" rule is satisfied without serialising wall
# clock.  Concurrency is capped because the limit here is RAM, not determinism -
# a too-large batch dies at import with "paging file is too small" and leaves a
# ZERO-BYTE output, so every job is checked with [ -s ] rather than by exit code.
#
#   arm stock  : BASE13 only  - provenance, HEAD e02377b with no monkeypatch
#   arm none   : ALL23        - the harness at penalty 0 (must equal stock)
#   arm a      : ALL23        - scorched penalty +1
#   arm b      : ALL23        - scorched penalty +10
#   arm c      : ALL23        - scorched penalty +100 (fire-adjacency rung)
set -u
cd "$(dirname "$0")/.."
PY=./.venv/Scripts/python.exe
JOBS=outputs/_sc_jobs.txt
: > "$JOBS"

emit() {  # arm wind roles seed
  local arm="$1" wind="$2" roles="$3" seed="$4"
  local tag="${arm}_${wind}_${roles}_${seed}"
  if [ -s "outputs/_sc_${tag}.json" ]; then return; fi
  echo "$PY outputs/_sc_probe.py --wind $wind --roles $roles --seeds $seed --arm $arm --tag $tag > outputs/_sc_${tag}.log 2>&1" >> "$JOBS"
}

ED="101 202 303"
EH="101 202 303 404 505"
SH="101 202 303 404 505"
FRESH="606 707 808 909 1010"

for s in $ED;    do emit stock east  default "$s"; done
for s in $EH;    do emit stock east  half    "$s"; done
for s in $SH;    do emit stock south half    "$s"; done

for arm in none a b c; do
  for s in $ED;    do emit "$arm" east  default "$s"; done
  for s in $EH;    do emit "$arm" east  half    "$s"; done
  for s in $SH;    do emit "$arm" south half    "$s"; done
  for s in $FRESH; do emit "$arm" east  half    "$s"; done
  for s in $FRESH; do emit "$arm" south half    "$s"; done
done

n=$(wc -l < "$JOBS")
echo "jobs queued: $n  (concurrency ${SCP:-14})"
if [ "$n" -gt 0 ]; then
  xargs -P "${SCP:-14}" -I CMD sh -c CMD < "$JOBS"
fi
echo "PASS DONE"

miss=0
for f in $(sed -n 's/.*--tag \([^ ]*\) .*/\1/p' "$JOBS"); do
  if [ ! -s "outputs/_sc_${f}.json" ]; then
    echo "MISSING outputs/_sc_${f}.json"
    miss=$((miss+1))
  fi
done
echo "missing after pass: $miss"
