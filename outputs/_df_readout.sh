#!/usr/bin/env bash
# Dock-fix round: every measurement the report makes, in one command.
#
# The point is that the report can be checked rather than trusted: each section
# below is the exact invocation whose output the corresponding report section
# quotes. Read-only - runs no simulation.
#
# ARMS
#   dfzero    mode 0 at the shipped defaults, fix ON   -> must equal dcoff
#   dfkill    dcB's config + BASE_STATION_DOCK_FIX=0   -> must equal dcB
#   dfA..dfD  the depot round's four arms, fix ON      -> read against dcA..dcD
#   dfm2ref   mode 2, fix OFF   (same-instrument reference for the mode-2 claim)
#   dfm2fix   mode 2, fix ON    (5 of 13 deadlock permanently at HEAD)
#   dfW0/dfW1 mechanism 1 + two depots, waypoint fix off / on
cd /e/Projects/SAS || exit 1
PY=./.venv/Scripts/python.exe
rule() { echo; echo "=============================================================="; echo "$*"; echo "=============================================================="; }

rule "1a. KILL SWITCH - mode 0, fix ON, against this round's own dcoff"
echo "The shipped configuration. At BASE_STATION_MODE 0 none of the new code is"
echo "reachable, so defaulting the fix ON must change nothing here."
$PY outputs/_dc_arms.py --mode identity --a dfzero --b dcoff --sample both

rule "1b. KILL SWITCH - THE STRONG CONTROL: dcB's config with the switch OFF"
echo "dfzero alone does not prove the switch works, because at mode 0 the changed"
echo "code never executes. This arm runs every changed path with DOCK_FIX=0 and"
echo "must reproduce _ffr_dcB_* field for field."
$PY outputs/_dc_arms.py --mode identity --a dfkill --b dcB --sample both

rule "2. THE PRIMARY GATE - dcB east/half/808"
echo "At 9f77178: UAV 2500 never arrives, sits at (4,44) for 38 steps with 35.4"
echo "battery. Below is the same seed with the fix on."
$PY - <<'PYEOF'
import json
for tag, label in (("dcB", "BEFORE, 9f77178"), ("dfB", "AFTER, fix on")):
    d = json.loads(open("outputs/_ffr_%s_east_half_808.json" % tag, "rb").read().decode("utf-8-sig"))
    print("  %s   terminal_step=%s" % (label, d.get("terminal_step")))
    for uid, log in sorted((d.get("rtb_log") or {}).items()):
        for t in log:
            fb = t.get("dock_cell") and list(t["dock_cell"]) != list(t["target_berth"])
            print("    %s trigger=%-4s target=%-8s arrival=%-5s dock=%-8s%s"
                  % (uid, t["trigger_step"], t["target_berth"], t["arrival_step"],
                     t["dock_cell"], "  <-- fallback" if fb else ""))
    c = (d.get("rtb_counters") or {}).get("2500", {})
    print("    UAV 2500 final_battery=%s final_active=%s cycles=%s"
          % (c.get("final_battery"), c.get("final_active"), c.get("cycles")))
    print("")
PYEOF

rule "3. THE REDEFINED STRANDING GATE - positional, not battery"
echo "BEFORE, at 9f77178:"
$PY outputs/_dc_arms.py --mode stranded --a dcA,dcB,dcC,dcD --sample canonical
echo
$PY outputs/_dc_arms.py --mode stranded --a dcA,dcB,dcC,dcD --sample fresh
echo
echo "AFTER, with the fix on:"
$PY outputs/_dc_arms.py --mode stranded --a dfA,dfB,dfC,dfD --sample canonical
echo
$PY outputs/_dc_arms.py --mode stranded --a dfA,dfB,dfC,dfD --sample fresh

rule "4. THE MODE-2 ARM - the strongest single signal in the round"
echo "5 of these 13 runs deadlock permanently with the fix off."
$PY outputs/_dc_arms.py --mode stranded --a dfm2ref,dfm2fix --sample canonical

rule "5. THE LIVELOCK GATE - what a positional stall gate structurally cannot see"
echo "A UAV that MOVES every step while getting nowhere has an unchanged-position"
echo "count of ZERO. At HEAD cycles and oscillations are zero in every arm, so any"
echo "non-zero result here is caused by the fix."
echo "BEFORE:"
$PY outputs/_df_evidence.py --mode livelock --glob '_ffr_dc[ABCD]_*.json'
echo
$PY outputs/_df_evidence.py --mode livelock --glob '_ffr_bsret_*.json'
echo "AFTER:"
$PY outputs/_df_evidence.py --mode livelock --glob '_ffr_df*_*.json'

rule "6. FALLBACK DOCKS - before and after, and WHERE they land"
echo "The count will not go to zero and should not: contention is real. What must"
echo "go to zero is stranding, and no dock may land outside the depot footprint."
$PY outputs/_df_evidence.py --mode fallback --glob '_ffr_dc[ABCD]_*.json'
echo
$PY outputs/_df_evidence.py --mode fallback --glob '_ffr_df[ABCD]_*.json'

rule "7. CONSECUTIVE-REFUSAL RUN LENGTHS - the sharpest before/after available"
echo "BEFORE: 13 episodes of 9-65 steps, nothing between 3 and 8."
$PY outputs/_df_evidence.py --mode refusals --glob '_ffr_dc[ABCD]_*.json'
echo "AFTER:"
$PY outputs/_df_evidence.py --mode refusals --glob '_ffr_df[ABCD]_*.json'

rule "8. OUTCOMES - seed-matched, each arm against its 9f77178 twin"
for pair in "dfA dcA" "dfB dcB" "dfC dcC" "dfD dcD"; do
  set -- $pair
  echo "---- $1 vs $2 ----"
  $PY outputs/_df_arms.py --mode paired --a "$1" --b "$2" --sample both
  echo
done

rule "8b. OUTCOMES - totals, canonical and fresh"
$PY outputs/_dc_arms.py --mode outcomes --a dcA,dfA --sample both
echo
$PY outputs/_dc_arms.py --mode outcomes --a dcB,dfB --sample both
echo
$PY outputs/_dc_arms.py --mode outcomes --a dcC,dfC --sample both
echo
$PY outputs/_dc_arms.py --mode outcomes --a dcD,dfD --sample both

rule "9. DRONE STEPS IN FIRE - UAV-steps on a burning cell / total UAV-steps"
echo "The definition the interior-hazard round used (2.1% canonical, 3.0% fresh),"
echo "read from the per-UAV per-step 'burning' flag the harness already records at"
echo "uav_actions[i][2]. UAVs are fire-immune: this is a search-quality signal."
echo "BEFORE:"
$PY outputs/_dc_arms.py --mode exposure --a dcA,dcB,dcC,dcD,dcoff --sample canonical
echo
$PY outputs/_dc_arms.py --mode exposure --a dcA,dcB,dcC,dcD,dcoff --sample fresh
echo "AFTER:"
$PY outputs/_dc_arms.py --mode exposure --a dfA,dfB,dfC,dfD,dfzero --sample canonical
echo
$PY outputs/_dc_arms.py --mode exposure --a dfA,dfB,dfC,dfD,dfzero --sample fresh
echo
echo "Consecutive burning-cell occupancy (a UAV sitting still on fire):"
$PY outputs/_df_evidence.py --mode burnstreak --glob '_ffr_dc[ABCD]_*.json'
$PY outputs/_df_evidence.py --mode burnstreak --glob '_ffr_df[ABCD]_*.json'

rule "10. THE WAYPOINT FIX - measured SEPARATELY, mechanism 1 + two depots"
echo "Unreachable under mechanism 2, so no arm above is confounded by it."
$PY outputs/_df_arms.py --mode paired --a dfW1 --b dfW0 --sample waypoint
echo
$PY outputs/_dc_arms.py --mode stranded --a dfW0,dfW1 --sample canonical 2>/dev/null | head -6

rule "11. MECHANISM - the return leg, before and after"
$PY outputs/_dc_arms.py --mode mechanism --a dcA,dfA,dcB,dfB,dcC,dfC,dcD,dfD --sample both

echo
echo "DF_READOUT_COMPLETE $(date '+%Y-%m-%d %H:%M:%S')"
