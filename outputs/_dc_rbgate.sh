#!/usr/bin/env bash
# Depot-cost round: the route_blocked gate for the four arms.
#
# The gate could not run on an ARMED arm before this round: outputs/
# _rblatch_campaign2.py had no --set, so the only way to gate a non-default
# configuration was to edit the shipped default, which this round is forbidden to
# do. Part 2 added --set to that script and a passthrough to _ffr_rbgate.sh; this
# runner drives it.
#
# The e703861 REFERENCE costs zero runs - it is already on disk as tag `rbc`.
# `dcinert` is the inertness check: one shard re-run through the MODIFIED script
# with NO --set, which must reproduce `rbca` field for field, or the reference is
# not comparable and every gate result below is unreadable.
#
# THE TAG MUST NOT START WITH `rbc`. _ffr_rbcompare.py globs
# "_rblatch_camp2_<old>*_D_<wind>.json", so a tag like `rbcv` is a PREFIX
# EXTENSION of the reference tag and its shard would be swept into the reference
# merge, silently double-counting east seeds 101-505 in every gate comparison.
# Caught in review before the check was ever run; `dcinert` shares no prefix with
# `rbc`, `ihrest` or any arm tag.
#
# Compare with:  outputs/_ffr_rbcompare.py --new <tag> --old ihrest
# NOT _ir_rbmerge.py alone - its 70e1b33 reference already fails 2 of 3 for
# 16b2da8 itself, so reading it as a verdict misattributes pre-existing behaviour.
#
# usage: bash outputs/_dc_rbgate.sh <arm>      arm in: verify A B C D
cd /e/Projects/SAS || exit 1
ARM="${1:-verify}"

ARMED="--set BASE_STATION_MODE=3 --set BASE_STATION_RETURN_MECHANISM=2"
DIST="--set UAV_RETURN_TO_BASE_RESERVE=0 --set BASE_STATION_RETURN_MARGIN=39.23"

case "$ARM" in
  verify) P=dcinert; EXTRA="" ;;
  A)      P=dcrbA; EXTRA="$ARMED" ;;
  B)      P=dcrbB; EXTRA="$ARMED $DIST" ;;
  C)      P=dcrbC; EXTRA="$ARMED $DIST --set BASE_STATION_DEPOTS=16" ;;
  D)      P=dcrbD; EXTRA="$ARMED $DIST --set BASE_STATION_DEPOTS=9 --set BASE_STATION_SPAWN_SPLIT=2" ;;
  *) echo "unknown arm $ARM"; exit 2 ;;
esac

if [ "$ARM" = "verify" ]; then
  # one shard only, the east 101-505 group that `rbca` holds
  PY=./.venv/Scripts/python.exe
  echo "START dcinert $(date +%H:%M:%S)"
  $PY outputs/_rblatch_campaign2.py --wind east --seeds 101,202,303,404,505 \
      --tag dcinerta > outputs/_ffr_rb_dcinerta.log 2>&1
  echo "DONE dcinert rc=$? $(date +%H:%M:%S)"
else
  # shellcheck disable=SC2086
  bash outputs/_ffr_rbgate.sh "$P" $EXTRA
fi
echo "DC_RBGATE_${ARM}_COMPLETE $(date '+%Y-%m-%d %H:%M:%S')"
