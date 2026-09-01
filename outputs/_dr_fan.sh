#!/bin/sh
# Fan the 23-run sample out across processes for one arm.
#   _dr_fan.sh <arm> [margin] [maxjobs] [seedlist-file]
# Each cell is its own process with its own RNG, seeded identically to the
# sequential runs, so parallelism here does not touch determinism - only
# combos WITHIN a process have to stay sequential.
set -u
arm="${1:-none}"; m="${2:-2}"; MAX="${3:-8}"; LIST="${4:-}"
CELLS_ALL="east:default:101 east:default:202 east:default:303 \
east:half:101 east:half:202 east:half:303 east:half:404 east:half:505 \
south:half:101 south:half:202 south:half:303 south:half:404 south:half:505 \
east:half:606 east:half:707 east:half:808 east:half:909 east:half:1010 \
south:half:606 south:half:707 south:half:808 south:half:909 south:half:1010"
if [ -n "$LIST" ]; then CELLS=$(cat "$LIST"); else CELLS="$CELLS_ALL"; fi
n=0
for c in $CELLS; do
  w=$(echo "$c" | cut -d: -f1); r=$(echo "$c" | cut -d: -f2); s=$(echo "$c" | cut -d: -f3)
  sh outputs/_dr_run.sh "$w" "$r" "$s" "$arm" "$m" &
  n=$((n+1))
  if [ "$n" -ge "$MAX" ]; then wait; n=0; fi
done
wait
echo "FAN DONE arm=$arm $(date +%H:%M:%S)"
