#!/usr/bin/env bash
# Sharded runner for the last_cell round. One process per (arm, combo, seed);
# combos are never mixed inside a process, so the module-global scenario
# config each run installs cannot leak between runs.
set -u
cd "$(dirname "$0")/.."
PY=./.venv/Scripts/python.exe
JOBS=outputs/_lc_jobs.txt
: > "$JOBS"

emit() {  # arm wind roles seed
  local arm="$1" wind="$2" roles="$3" seed="$4"
  local combo="${wind}_${roles}"
  echo "$PY outputs/_lc_probe.py --wind $wind --roles $roles --seeds $seed --arm $arm --tag ${arm}_${combo}_${seed} > outputs/_lc_${arm}_${combo}_${seed}.log 2>&1" >> "$JOBS"
}

ORIG_ED="101 202 303"
ORIG_EH="101 202 303 404 505"
ORIG_SH="101 202 303 404 505"
FRESH="606 707 808 909 1010"

# stock + the three what-if arms over the 13-run sample
for arm in none a b c; do
  for s in $ORIG_ED; do emit "$arm" east default "$s"; done
  for s in $ORIG_EH; do emit "$arm" east half    "$s"; done
  for s in $ORIG_SH; do emit "$arm" south half   "$s"; done
done

# fresh-seed replication check, stock only
for s in $FRESH; do emit none east  half "$s"; done
for s in $FRESH; do emit none south half "$s"; done

echo "jobs: $(wc -l < "$JOBS")"
xargs -P "${LCP:-24}" -I CMD sh -c CMD < "$JOBS"
echo "ALL DONE"
