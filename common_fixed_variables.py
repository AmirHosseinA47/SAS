import random
import numpy

# COMMON VARIABLES

SYSTEM_RANDOM = random.SystemRandom()  # ... Not available on all systems ... (Python official doc)

# simulator activators (environment conditions)

FIXED_WIND = True
ACTIVATE_SMOKE = True
ACTIVATE_WIND = True
# To avoid throwing "KeyError: 'Layer'" when prob burning maps are shown (so UAV won't get its "Layer" attribute in the
# "portrayal_method(obj)"), NUM_AGENTS must be set to 0.
PROBABILITY_MAP = False

# model params specifications

BATCH_SIZE = 300
WIDTH = 50  # in python [height, width] for grid, in js [width, heigh]
HEIGHT = 50
BURNING_RATE = 1
FIRE_SPREAD_SPEED = 3
# Fire spread scenario control:
# 0.5 = slow fire
# 1.0 = normal fire
# 1.5 = fast fire
# 2.0 = extreme fire
FIRE_SPREAD_MULTIPLIER = 0.75
FUEL_UPPER_LIMIT = 10
FUEL_BOTTOM_LIMIT = 7

DENSITY_PROB = 1  # Tree density (Float number in the interval [0, 1])

# Direction fire/smoke spreads toward (grid travel semantics, not meteorological "from").
WIND_DIRECTION = 'west'


def normalize_wind_direction(value: object | None = None) -> str:
    """Normalize wind label to north/south/east/west (spread direction)."""
    direction = str(value if value is not None else WIND_DIRECTION).strip().lower()
    if direction in ("north", "south", "east", "west"):
        return direction
    return str(WIND_DIRECTION).strip().lower()


def wind_vector_from_direction(direction: object | None = None) -> tuple[float, float]:
    """Unit vector for the direction fire/smoke is pushed on the grid."""
    label = normalize_wind_direction(direction)
    if label == "north":
        return (0.0, 1.0)
    if label == "south":
        return (0.0, -1.0)
    if label == "east":
        return (1.0, 0.0)
    if label == "west":
        return (-1.0, 0.0)
    return (0.0, 1.0)


# if FIXED_WIND == False (compose wind), then variables inside the if statement are set to be used in the project
if not FIXED_WIND:
    # Possible mixed wind directions: NW, NE, SW, SE"
    FIRST_DIR = 'north'  # Introduce first wind direction (north, south, east, west):
    SECOND_DIR = 'south'  # Introduce second wind direction (probability calculated based on first one),
    FIRST_DIR_PROB = 0.8  # Introduce first wind probability [0, 1]
MU = 0.9  # Wind velocity (Float number in the interval [0, 1])

SMOKE_PRE_DISPELLING_COUNTER = 2

# UAVs params

# ============================================================
# SCENARIO PRESETS — uncomment ONE block to activate
# ============================================================

# Scenario A — Rescue Success (default)
# Expected: victim discovery, firefighter dispatch, rescue completion
NUM_AGENTS = 3
NUM_VICTIMS = 5
NUM_FIREFIGHTERS = 3
# When set, override legacy "last UAV = searcher" assignment. NUM_AGENTS should equal
# NUM_FIRE_TRACKERS + NUM_VICTIM_SEARCHERS when both are specified.
NUM_FIRE_TRACKERS = None
NUM_VICTIM_SEARCHERS = None
LOW_BATTERY_THRESHOLD = 30.0
BATTERY_CRITICAL_THRESHOLD = 15.0

# Scenario B — Battery Fail-Safe Validation
# Expected: fail-safe mode activation when battery falls below threshold
# NUM_AGENTS = 3
# NUM_VICTIMS = 2
# NUM_FIREFIGHTERS = 2
# BATTERY_CRITICAL_THRESHOLD = 50.0

# Scenario C — Large Operation
# Expected: stress-test with more UAVs/victims/firefighters
# NUM_AGENTS = 5
# NUM_VICTIMS = 3
# NUM_FIREFIGHTERS = 3
# BATTERY_CRITICAL_THRESHOLD = 15.0

# Scenario D — Rescue Priority
# Expected: more rescue pressure, more victims
# NUM_AGENTS = 4
# NUM_VICTIMS = 4
# NUM_FIREFIGHTERS = 2
# BATTERY_CRITICAL_THRESHOLD = 15.0

# ============================================================

# Firefighter rescue absence (feature 1). When a firefighter carries a victim to
# its exit cell, the victim is finalised as before and the firefighter is removed
# from the grid for a per-rescue draw of [MIN, MAX] steps (the hand-over), then
# re-enters at that exit cell and becomes available again. MAX <= 0 disables the
# absence and restores the immediate recycle. Overridable per run through
# apply_scenario_config like every other scenario parameter. The draw comes from
# a dedicated RNG seeded from the run seed, never from SYSTEM_RANDOM.
FF_RESCUE_ABSENCE_MIN_STEPS = 3
FF_RESCUE_ABSENCE_MAX_STEPS = 5

# Victim fire flight (feature 2). A victim holds its cell until the nearest
# ACTIVELY BURNING cell is within VICTIM_FLEE_TRIGGER_DISTANCE (manhattan), then
# steps to the orthogonal neighbour that maximises distance from fire - never
# onto a burning cell, and never further than VICTIM_FLEE_MAX_DISPLACEMENT from
# the cell it spawned on. The leash is what keeps a fleeing victim inside the
# searcher coverage its spawn sat in, and what stops a victim outrunning the
# front for the whole run only to die somewhere else.
#
# The two defaults are borrowed, not invented: 3 is IDLE_RETREAT_SAFETY_BUFFER
# and 6 is IDLE_RETREAT_MAX_CELLS (agents.py), already this codebase's notions
# of "fire is too close to stand here" and "how far a unit may wander during
# this kind of manoeuvre", so a victim's sense of danger matches a
# firefighter's.
#
# TRIGGER <= 0 is the kill switch: Victim.advance goes back to a no-op, the
# firefighter's live re-target is skipped so the approach path is the
# pre-feature code literally, and last_known_position stops being updated.
# Overridable per run through apply_scenario_config like every other scenario
# parameter, and read at call time so an override applies. The rule is fully
# deterministic - it draws from no RNG at all.
VICTIM_FLEE_TRIGGER_DISTANCE = 3
VICTIM_FLEE_MAX_DISPLACEMENT = 6

# Victim-searcher interior hazard retreat. The searcher hazard gate in
# src_extension/execution/uav_executor.py replaces the searcher's chosen
# direction with a one-step RETREAT - the strictly safe neighbour furthest from
# any burning or smoke cell - when this rule fires:
#   0       off: the retreat fires only within 2 cells of a grid edge (the
#           edge-only gate, with the retreat scored toward the interior)
#   1..98   on when the nearest strict fire/smoke cell is within this many
#           cells of the searcher (manhattan)
#   >= 99   on at every gated step
# When on, the retreat and the gate's fallback ranking score by hazard distance
# only; keeping off the grid edge is left to the edge-blocked filter (margin 3)
# and the planner's boundary margins, which are live regardless.
# History: until the grid size became readable (dimension fix, 2026-09-06) the
# gate's edge test read 0.0 everywhere and the retreat's boundary terms were 0,
# so the model ran with this rule ALWAYS ON and hazard-only for its whole record
# - by accident. 99 is that behaviour made intentional; 0 is what the edge-only
# code did once the read worked, measured at +1.1 points of searcher steps on a
# burning cell (2.1% -> 3.2%). Overridable per run through apply_scenario_config
# like every other scenario parameter, and read at call time so an override
# applies. Deterministic - it draws from no RNG.
VICTIM_SEARCHER_HAZARD_RETREAT_RANGE = 99

# Base station (feature 3). A set of 5x5 depots - shipped as two, NW and SE (see
# BASE_STATION_DEPOTS) - that the UAV team and the firefighters launch from, that a
# UAV returns to (the nearest of its own berths) when its battery reaches the return
# trigger, and that recharges it.
#
# BASE_STATION_MODE is an ordinal ladder, and each level is a strict superset of
# the one below it, so a level-N vs level-(N-1) comparison attributes exactly one
# increment:
#   0  off - the kill switch. No depot is built, spawn is the pre-feature centre
#      cluster, and every entry point returns before any state write, so this
#      feature's code is inert: the model is byte-identical to the checkout before
#      this feature apart from later, separately switched changes (e.g.
#      ROUTE_BLOCK_STALE_CLEAR, see SHIPPED DEFAULT below).
#   1  spawn only: UAVs (and firefighters, unless BASE_STATION_SPAWN_FIREFIGHTERS
#      is 0) start on depot berths instead of the centre cluster / the ring.
#   2  + return-to-base: a UAV whose battery reaches the trigger flies to its
#      berth and parks there. With no recharge it stays parked, which is the
#      honest cost of a return leg on its own.
#   3  + recharge: a parked UAV refills at BASE_STATION_RECHARGE_PER_STEP and
#      re-launches at BASE_STATION_RECHARGE_RELEASE_LEVEL.
#
# The depot is a MODEL-LEVEL REGION, not an agent and not terrain: it adds no
# agent, consumes no RNG, shifts no unique_agents_id, and does not touch the fire
# model. Fire spreads into it exactly as into any other cell and nothing models
# the depot being destroyed - UAVs are fire-immune (_check_fire_casualties has no
# UAV branch), so a hardened pad would buy no behaviour while inserting a 5x5
# firebreak straight into burnt_cells. See outputs/basestation_part1.txt 1.1-1.3.
#
# BASE_STATION_CORNER's default is the NW block, x in [0,4] and y in [WIDTH-5,
# WIDTH-1]: the only corner upwind of BOTH canonical winds (east pushes fire toward
# +x, south toward -y) and the shortest mean distance to the victim ring in all four
# built-in scenarios. NW is depot 0 of the shipped set, where every tracker and every
# firefighter launches. The shipped set adds SE, which is downwind of both canonical
# winds, so the gated east/south waves DO put a depot in the fire's path.
# NOTE the asymmetry: this module defaults WIND_DIRECTION to 'west', under which NW
# is downwind and SE upwind. That wind reaches `python main.py --mesa` and a bare
# WildFireModel(); a bare `python main.py` launches the dashboard, which defaults to
# east (for 80 steps - spawn geometry only, no return can trigger that early).
# WEST AND NORTH WERE NEVER MEASURED at the shipped configuration (0 of 57 distinct
# dcD runs).
#
# THE FLAT REGIME - the shipped trigger until the dcD flip (2026-09-14), now an
# override. The flat UAV_RETURN_TO_BASE_RESERVE of 60 is derived, not tuned, for a
# SINGLE NW depot. It is the larger of a fuel
# constraint and a horizon constraint over the worst-case return of D = 90 cells
# (the far corner to the nearest depot cell) at 0.3 per moving step:
#   fuel     D*0.2 + (D/f)*0.1 = 27.0 at f=1, + 0.3 trigger latency + 5.0 margin
#            = 32.3
#   horizon  the return needs D steps and must finish by step 240, so
#            R >= 100 - e*(240 - D) where e = 0.1 + 0.2m is the effective drain
#            at outbound move fraction m; at m = 5/6 that is 60.0
# so R = max(32.3, 60.0) = 60. Read backwards, a reserve of 60 guarantees that a
# UAV at the worst cell on the grid completes its return inside 240 steps as long
# as it moved on at least five of every six steps beforehand. Measured move
# fractions are 0.95-1.00. The naive floor of 55 - which assumes the UAV moves on
# every single step - has no slack and fails on the first held step.
#
# The trigger takes the MAX of that reserve and a distance-aware term,
# 0.3 * manhattan_to_berth + BASE_STATION_RETURN_MARGIN, so a UAV that is somehow
# further out than the flat reserve covers turns back earlier.
#
# TWO CORRECTIONS TO THE ABOVE, from the depot-cost round (2026-09-08), left in
# place rather than rewritten because this is the derivation of the flat-regime
# values 60.0 / 5.0:
#   1. D = 90 is the distance to the nearest depot CELL, but the trigger computes
#      the distance to the UAV's OWN BERTH, whose worst case at a single NW depot is
#      92 - berth (3,46), from cell (49,0). A 2-cell understatement that does not
#      change R = 60.
#   2. AT THE FLAT-REGIME VALUES THE DISTANCE TERM IS DEAD CODE. max(60, 0.3d + 5)
#      selects the distance term only at d >= 183.3, and the grid maximum is 92. It
#      was never once the max in any measured flat-regime run. At the SHIPPED
#      reserve of 0.0 it is the only live term.
#
# THE DISTANCE REGIME - SHIPPED. Setting UAV_RETURN_TO_BASE_RESERVE = 0 removes the flat
# floor and leaves the distance term alone; the trigger is a max() over battery
# levels, which are non-negative, so 0 is the identity element and means exactly
# "no flat floor". THE MARGIN IS REGIME-DEPENDENT and 5.0 is only correct for the
# flat regime. In the distance regime the margin must carry the horizon
# constraint, which the flat reserve was carrying before:
#     M >= [100 - e*H + e*blocked] - d*(0.3 - e)      worst at d = 0
#     with e = 0.1 + 0.2*(5/6) = 0.26667, H = 240 and blocked = 11 (the measured
#     maximum blocked-step standoff over 137 recorded mechanism-2 return legs, at the
#     time of the derivation),
#     M >= 38.9333, plus 0.30 of trigger latency  =>  M = 39.23
# (38.9333 + 0.30 = 39.2333, rounded DOWN, so at its own premises the horizon bound
# is met to 240.0125 steps, not 240.)
# At the shipped NW+SE depots the worst nearest-own-berth distance on 50x50 is
# 49/50/49/50/51 for UAV index 0-4, and 53 over all 25 berths, so the trigger never
# exceeds 0.3*53 + 39.23 = 55.13. THIS RULE TURNS A UAV BACK LATER - at a lower
# battery - than the old flat 60 at every reachable cell; it would need d > 69.23
# to be earlier. Its safety rests on the margin carrying the horizon, not on slack
# against the flat rule. (At the old single NW depot, worst own-berth distance 92, it
# was earlier: 66.83 against 60.00.)
# THE DERIVATION'S PREMISES ARE EXCEEDED IN dcD's OWN RECORD. Over the 192 trips of
# the dock-fix-on arms d4D + drhD:
#   blocked  one return leg waited 17 non-moving steps against the 11 allowed
#            (d4D south/half/423146201, UAV 2501; the next longest is 4); with 17 the
#            margin would be 40.83
#   latency  the battery at trigger sat 0.43 below 0.3d + M on 143 trips and 0.53
#            below on 34 - 177 of 192 exceed the 0.30 allowed - because a UAV moving
#            AWAY from its berth raises the threshold 0.3 as its battery falls 0.3
# Over all 57 distinct dcD runs (228 trips) it is 207 of 228 above 0.30 (0.33 on 2,
# 0.43 on 169, 0.53 on 36), with the same 17-step standoff, the same minimum arrival
# and the same latest arrival. The move-fraction premise (5/6) holds (lowest 0.837).
# So the derived arrival of M - 0.30 - 1.10 = 37.83 is NOT a floor. The measured
# minimum is 37.1, on that same leg: 0.60 of extra standoff plus 0.13 of extra
# latency. That is still clear of the LOW_BATTERY (30) and CRITICAL_BATTERY (15)
# analyzer thresholds; every trip arrived (the latest at step 227) and no UAV
# stranded - a sample minimum over 228 trips, not a guarantee. The FUEL-only margin for the same
# mechanism is 16.40 (1.10 blocked + 0.30 latency + 15.00 arrival buffer) and it
# is USELESS: a trigger at 0.3d + 16.40 fires on 22 of 52 measured UAV-runs and
# not one return completes inside the horizon. See outputs/depotcost_part1.txt
# section 3.
# LIMITS OF THE DERIVATION. One trip from full charge with 240 steps of horizon, on
# 50x50. The first trigger comes no earlier than model step 155 (1 UAV), 154 (2-4),
# 153 (5-9), 152 (10-16) or 151 (17+); a run of about 151-239 steps can start a
# return the derivation does not guarantee to finish; a second trigger comes no
# earlier than step 367-371 (370 at 2-4 UAVs), so multi-cycle horizons are outside
# it. On larger
# grids the worst distance grows (about N on N x N): the rule turns back earlier than
# flat 60 from N ~70 and at full charge from N ~203.
# MEASURED SCOPE of the shipped configuration: scenario D (4 UAVs, 4 victims, 2
# firefighters), 50x50, 240 steps, wind east or south with roles half (2+2), or wind
# east with legacy roles.
# Everything else - west/north, the dashboard presets, evaluate_scenarios' scenario-A
# 300-step default - is unmeasured.
#
# BASE_STATION_RETURN_MECHANISM selects between the two routes, which are
# MUTUALLY EXCLUSIVE - an agent-level override is the last writer of selected_dir
# before move() and would silently mask a planner route, so "both" is rejected:
#   1  planner   - a per-UAV local adaptation option carries the berth as a
#                  waypoint through PathDecision to the executor. Keeps the
#                  searcher hazard gate and the final direction safety filter,
#                  so this route is FIRE-AWARE, and it can be suppressed for a
#                  step by a fleet-wide safe_hold fail-safe override.
#   2  hardcoded - agents.UAV.advance steers straight at the berth, bypassing the
#                  adaptation layer. FIRE-BLIND by construction; that is the
#                  declared difference between the arms, not a defect.
#
# Every one of these is overridable per run through apply_scenario_config like
# any other scenario parameter, and every one is read at CALL TIME from the
# common_fixed_variables MODULE (agents.py:base_station_mode and friends), never
# through the star-imported names above and never at import time - otherwise the
# override is invisible and the constant is decorative. Deterministic: the depots,
# the berth ranking and every spawn cell are pure functions of the grid extent, the
# agent counts, the role split and - at BASE_STATION_SPAWN_SPLIT 2 - the wind, and
# draw from no RNG at all.
#
# SHIPPED DEFAULT IS 3 - THE dcD CONFIGURATION: two depots (NW + SE), searchers
# launched from the depot nearest their crosswind lane, return to the nearest own
# berth on the distance-regime trigger (reserve 0.0, margin 39.23), the hardcoded
# return mechanism, recharge, dock fix on. Flipped 2026-09-14.
# THE CASE IS THAT THE FEATURE IS WANTED AT ROUGHLY NEUTRAL COST, NOT THAT IT
# IMPROVES OUTCOMES. It TRADES victim deaths for firefighter survival: on the fourth
# seed set - the only sample that did not select dcD - rescued held at 89, dead rose
# 16 -> 23 and firefighter deaths fell 18 -> 7 (outputs/_dcd4_splits.txt). The
# route_blocked gate's G1 still fails by the NEW rule on east/707, south/101,
# south/202 and south/404, and all four losses are spawn geometry, not the return
# leg (outputs/dcd4_losses_part1.txt). The flip checklist is outputs/flip_part1.txt;
# its validation (full suite, byte identity of the new defaults with the explicit dcD
# arm, the route_blocked gate reproduced) is outputs/flip_report.txt.
# HISTORY: this shipped at 0 from f4e79d5 (outputs/basestation_report.txt section 4)
# through b853617. Mode 0 is still the kill switch; a run that must reproduce the
# pre-flip default sets BASE_STATION_MODE=0 explicitly. (Mode 0 is no longer
# byte-identical to 16b2da8: ROUTE_BLOCK_STALE_CLEAR = 1, from 4795708, changes
# mode-0 output on east/half/202.) Every script, queue line and probe that relied on
# the old default is classified in outputs/flip_runner_register.txt.
# BASE_STATION_DEPOTS - the depot SET, as a bitmask over five anchors, added by
# the depot-cost round. Numeric for the same reason BASE_STATION_CORNER is: a
# --set value is coerced bool -> None -> int -> float -> str, so a scalar int
# survives that channel unambiguously and a list does not.
#   bit 0 (1)  NW      bit 1 (2)  NE      bit 2 (4)  SW
#   bit 3 (8)  SE      bit 4 (16) CENTRAL
# 0 means "one depot, at BASE_STATION_CORNER" - byte-identical to the behaviour
# before the depot-cost round. SHIPPED AT 9 (NW + SE) since the dcD flip. Depots
# are built in ASCENDING
# BIT ORDER, so the set is ordered and deterministic, and depot 0 is the first set
# bit. Unlike base_station_corner(), which silently maps an unrecognised value to
# NW, base_station_depots() RAISES on a value outside 0..31 - a silent fallback
# here would run a two-depot arm as a one-depot arm and the wave would measure the
# wrong thing with no error anywhere. That is this repo's recorded dead-input
# defect class and it is not repeated.
#
# WHY A DEPOT SET AT ALL. The return-leg share of UAV-steps is arithmetic, not a
# tuning constant: one trip costs d steps and the reserve produces one trip per
# UAV per run, so the share is mean_d / 240. Measured mean d was 41.8 and the
# measured share 17.5%; 41.8/240 = 17.4%. Making the reserve distance-based does
# NOT reduce it - at a single NW depot it is half a point worse, because the
# trigger fires from further out. Only shortening d does. Whole-grid mean
# distance: NW 41.40, NW+NE and NW+SW 29.10, NW+SE 25.12, CENTRAL 21.16. NW+SE is
# the diagonally opposite pairing and its worst-case return of 45 is PROVABLY the
# minimum over all 2116 placements of a second 5x5 block with NW fixed. (45 is to
# the nearest depot CELL; the trigger measures to the UAV's own berths, whose worst
# case is 49/50/49/50/51 for UAV index 0-4 and 53 over all 25.)
# LIMITS AT THE SHIPPED 9: the two blocks overlap - and _build_base_station raises -
# iff max(HEIGHT, WIDTH) <= 2*min(5, HEIGHT, WIDTH) - 1 (the block size clamps to the
# smaller grid dimension). A real WildFireModel never gets there: set_fire_agents
# already needs both dimensions >= 21; only test stand-ins reach it. And it raises
# when NUM_AGENTS + NUM_FIREFIGHTERS exceeds one block's berths (25 at size 5): every
# depot holds a berth for every unit, firefighters included in SE although they launch
# only from NW.
# The cost of that pairing, measured on the 20 distinct baseline fires: the SE
# block burns in 19 of them against 3 for NW, because SE is the only corner
# downwind of both canonical winds - which is exactly what NW was chosen to avoid.
# Mechanically free (UAVs are fire-immune) but it is why firefighters stay at the
# NW depot in every arm. See outputs/depotcost_part1.txt sections 0, 4 and 5.
BASE_STATION_DEPOTS = 9

# BASE_STATION_SPAWN_SPLIT - which depot each unit LAUNCHES from when there is
# more than one. It does not affect where a UAV RETURNS to; return is always to
# the nearest of that UAV's own berths.
#   0  every unit at depot 0                (the only possibility with one depot,
#      and byte-identical to the behaviour before the depot-cost round)
#   1  alternate by index, a % n_depots
#   2  partition-nearest: each SEARCHER launches from the depot nearest the
#      centroid of its own crosswind lane; trackers and firefighters stay at
#      depot 0                              (SHIPPED)
# 2 is the measured choice, and ships. A searcher's lane is a pure function of its index
# among searchers and the wind, and NW and SE fall in OPPOSITE halves of both
# possible lane axes - so the assignment that puts each searcher in its own lane
# is the exact opposite for east and south wind, and no wind-blind index rule
# (0 or 1) can be right for both. It matters because the searcher whose lane does
# not contain the depot pays 1.85x the return leg of the one whose does (mean
# trigger distance 54.9 against 29.6, measured on the single-NW bsfull arm's record),
# and never_detected is a searcher metric.
# TRACKERS ARE DELIBERATELY NOT LANE-MATCHED: a tracker's sector is recomputed
# every step from the fire's bounding box - the baseline itself churns them ~1053
# times over 13 runs - so there is no stable tracker home region to match, and
# trackers are measurably nearer NW at trigger under both winds anyway.
# With one searcher (the legacy role split) the lane is None and the searcher
# falls back to depot 0, so at "default" roles this setting is inert by
# construction. Deterministic: every input is a config constant or an agent index,
# and no branch here draws RNG.
BASE_STATION_SPAWN_SPLIT = 2

BASE_STATION_MODE = 3
BASE_STATION_RETURN_MECHANISM = 2
BASE_STATION_SPAWN_FIREFIGHTERS = 1
BASE_STATION_SIZE = 5
UAV_RETURN_TO_BASE_RESERVE = 0.0
BASE_STATION_RETURN_MARGIN = 39.23
BASE_STATION_RECHARGE_PER_STEP = 5.0
BASE_STATION_RECHARGE_RELEASE_LEVEL = 100.0

# BASE_STATION_DOCK_FIX - the docking-deadlock fix, added by the dock-fix round.
# An ordinal ladder like BASE_STATION_MODE, so the two independent halves can be
# ATTRIBUTED rather than only measured as a bundle:
#   0  off. Every path behaves exactly as at 9f77178. THE KILL SWITCH, and the
#      arm that proves byte-identity.
#   1  + the docking fallback is RE-KEYED from "is my berth occupied at this
#      instant" to "has this leg stopped moving for BASE_STATION_RETURN_STALL_-
#      LIMIT consecutive steps". The old trigger fired on a ONE-STEP TRANSIT
#      through a berth - mesa mutates the grid during the advance sweep, so a
#      later-ordered UAV sees it - and permanently re-assigned that berth. It was
#      also silent where it was needed most: it asked about the BERTH, so a UAV
#      boxed in with a FREE berth never fired it at all, which is every one of
#      the five measured mode-2 strandings.
#   2  + a leg that has stalled OUTSIDE its depot latches the nearest free depot
#      cell and steers to it until it is inside, where the re-keyed terminator
#      takes over. Without this the pure-axis approach has no escape at all: the
#      sidestep in _rtb_direction is structurally dead when one delta is zero,
#      and the fallback is scoped to the depot interior.
# Shipped at 2, and LIVE at the shipped BASE_STATION_MODE 3: on a default run,
# DOCK_FIX 0 reverts docking to the 9f77178 behaviour. At BASE_STATION_MODE 0 none
# of this code is reachable.
# Derivation, evidence and the two rejected alternatives: outputs/dockfix_part1.txt.
BASE_STATION_DOCK_FIX = 2

# BASE_STATION_RETURN_STALL_LIMIT - consecutive steps on which a returning UAV's
# move must be refused before its leg counts as stalled.
# DERIVED, not tuned. Over every armed run of the depot-cost and base-station
# rounds, runs of consecutive refused steps on a return leg are 1 step (184
# episodes) or 2 steps (5), then NOTHING AT ALL between 3 and 8, then 13 episodes
# of 9 to 65 steps - every one of them a stall the UAV never escapes on its own.
# 3 sits inside that empty gap. A one-step transit through a berth produces at
# most ONE refused step and so cannot reach 3 by construction, not merely as a
# matter of measured frequency.
BASE_STATION_RETURN_STALL_LIMIT = 3

# BASE_STATION_WAYPOINT_FIX - separate switch, separate defect, measured apart.
# The mechanism-1 planner waypoint published the UAV's HOME berth rather than the
# berth LATCHED for the current trip. With one depot the two are the same value
# and this is inert; with two or more and BASE_STATION_RETURN_MECHANISM = 1 it
# steers a UAV to a berth the docking logic is not scoped to, and the trip cannot
# terminate. It is deliberately NOT folded into BASE_STATION_DOCK_FIX: every arm
# of this round runs mechanism 2, where this code is unreachable, so bundling the
# two would make it impossible to attribute an outcome to either.
#   0  off - publishes rtb_berth, as shipped.
#   1  publishes the latched rtb_target_berth, falling back to rtb_berth.
BASE_STATION_WAYPOINT_FIX = 1
# BASE_STATION_CORNER was never declared here - it existed only as the getattr
# default inside agents.base_station_corner(), reachable through --set because
# apply_scenario_config setattr-creates the attribute. Declared now so the module
# means what it says about every constant being declared and overridable. 0 = NW,
# which is what the accessor already defaulted to, so this line changes nothing.
# READ ONLY WHEN BASE_STATION_DEPOTS IS 0 (wildfire_model._base_station_origins):
# at the shipped 9 the depots are the fixed NW and SE anchors and this is inert.
BASE_STATION_CORNER = 0
# The depot outline colour is #770099, and it lives as an inline literal in both
# renderers rather than here, exactly like #2b2b2b (burnt), #895e00 (scorched) and
# #2f4a1a (spared veg): this module holds colour RAMPS and simulation parameters,
# not single-state display colours, and a per-run override of a colour would be
# meaningless. Violet is the only unclaimed hue band in the palette - greens are
# vegetation, the yellow-orange-red arc is fire and victims, the greys are
# smoke/burnt/probability map, the cyans are the searcher UAV / firefighter /
# assigned victim, and magenta is the fire tracker. Chosen by a CIEDE2000 sweep
# over the 39 co-occurring map colours: minimum 28.76 dE, against 27.34 for the
# already-shipped scorched #895e00 on the identical set.

# ROUTE_BLOCK_STALE_CLEAR - drop a route_blocked flag that has lost its referent.
# An ordinal ladder, each rung a strict superset of the one below, so a
# rung-N vs rung-(N-1) comparison attributes exactly one increment:
#   0  OFF - the kill switch. Provably byte-identical to f4e79d5, stdout included,
#      AT BASE_STATION_MODE 0 (f4e79d5's default). Since the dcD flip a rung-0
#      control must ALSO set BASE_STATION_MODE=0 to keep that identity.
#   1  clear a flag on a unit that is alive, on the grid, not exiting, not
#      rescue_completed, NOT fire-enclosed, and UNASSIGNED AND UNBOUND, once no
#      victim needs rescue at all. This is the entire MEASURED population: the
#      five units the clear fired on in the round's 34-run sweep, covering both
#      baseline-arm latches (east/half 202 at mode 0, east+south/half 808 at
#      mode 3). A sixth unit was flagged - s909 m0 south, raised on the FINAL
#      step with a victim still live - and is a 240-step horizon artifact that
#      neither rung reaches, by design.
#   2  rung 1, plus a unit still assigned/bound to a TERMINAL referent, which is
#      first released through the audited executor unassign and then cleared.
#
# THE DEFECT. route_blocked is raised about ONE target, but every gate reads it
# as a property of the unit. The replacement unassign issued inside the raise's
# own call stack (wildfire_model.py:4449-4453) deletes the whole referent -
# assigned, target_pos, rescued_victim, exiting, exit_target - and leaves the
# flag, which disarms all three clears at once: clear 1 (agents.py:1816) needs
# target_pos, clear 2 (:2657) needs a live victim to test a path against, and
# clear 3 (:3632) needs rescued_victim through the _bound gate at :3582. Once
# the last victim is terminal the flag can never be cleared, and the unit is
# refused by four gates (:3040, :3474, :4339, rescue_planner.py:591) for the
# rest of the run - the end-of-run latch 70e1b33's gate item forbids.
#
# WHAT IT DOES AND DOES NOT BUY. The clear fires only when no victim needs
# rescue, so it is end-state bookkeeping: it closes the latch and it does NOT
# save a victim - by its own trigger it cannot. On seed 202 at BASE_STATION_MODE 0
# (then the shipped default), the victim was lost because the replacement died in
# the same step,
# not because of the flag, which was zero steps old and accurate at that
# instant. See outputs/latchfix_part1.txt section 0.1.
#
# WHY NOT AT THE UNASSIGN. Clearing at the source would hand the just-blocked
# unit back to the replacement decision three statements later at :3416, off a
# snapshot re-derived from the same marker; the planner selects on Manhattan
# distance with no path test anywhere (rescue_planner.py:646-651), and the
# blocked unit is usually the CLOSEST because it walked toward the victim until
# it ran out of route (seed 808 s219: 13 against the actual replacement's 49).
# Its re-claim would then filter the victim out of every other unit's reach at
# rescue_planner.py:560-562. Release, not prevention - the phantom round's
# choice, for a mechanically identical reason.
#
# Rung 2 exists because a unit cleared to status "assigned" by agents.py:1816 is
# undispatchable on a DIFFERENT gate (:3042, on `assigned`) and invisible to any
# check counting status == "route_blocked" - a latch that hides from its own
# detector. Rung 1 leaves that shape flagged; rung 2 releases it first. That
# shape is real and was observed at step 198 of D/south/half seed 606, where the
# route later reopened and the unit was relabelled "assigned" - benign there only
# because the run hit the 240-step horizon with its victim still alive.
#
# SHIPPED DEFAULT IS 1, NOT 2, and the reason is deliberate. Rung 2's release
# path NEVER FIRED: ff_route_blocks_stale_released_total is 0 on every one of the
# round's 34 sweep runs, because all five units it cleared were already unbound.
# So rung 2 behaved exactly as rung 1 everywhere it was measured, and shipping it
# on would add a never-executed code path to a codebase this campaign has spent
# nine rounds removing them from. Rung 1 loses nothing on any run in the record;
# rung 2 stays here, tested, for whenever a case demands it. Raise it to 2 and
# the only difference is that a unit still bound to a TERMINAL victim is released
# before its flag is dropped. See outputs/latchfix_report.txt section 5.
#
# Read at CALL TIME from the common_fixed_variables MODULE
# (WildFireModel._route_block_stale_clear_mode), never through the star import
# above and never at import time, so an apply_scenario_config override is
# visible - otherwise the switch is decorative and this is the tenth dead-input
# instance. Deterministic: it draws from no RNG.
ROUTE_BLOCK_STALE_CLEAR = 1

N_ACTIONS = 4
UAV_OBSERVATION_RADIUS = 8
side = ((UAV_OBSERVATION_RADIUS * 2) + 1)
N_OBSERVATIONS = side * side
SECURITY_DISTANCE = 10
# During the first launch phase, close UAV spacing is expected and should not
# trigger collision-risk fail-safe.
LAUNCH_GRACE_STEPS = 20

# colors

VEGETATION_COLORS = ["#414141", "#9eff89", "#85e370", "#72d05c", "#62c14c", "#459f30",
                     "#389023", "#2f831b", "#236f11", "#1c630b", "#175808", "#124b05"]
FIRE_COLORS = ["#414141", "#d8d675", "#eae740", "#fefa01", "#fed401", "#feaa01",
               "#fe7001", "#fe5501", "#fe3e01", "#fe2f01", "#fe2301", "#fe0101"]
SMOKE_COLORS = ["#ababab"]
BLACK_AND_WHITE_COLORS = ["#ffffff", "#e6e6e6", "#c9c9c9", "#b1b1b1", "#a1a1a1", "#818181",
                          "#636363", "#474747", "#303030", "#1a1a1a", "#000000"]
COLORS_LEN = len(VEGETATION_COLORS)


# functions

# function that normalize fuel values to fit them with vegetation and fire colors
def normalize_fuel_values(fuel, limit):
    if fuel > limit:
        fuel = limit
    return max(0, round((fuel / limit) * COLORS_LEN - 1))


# function that normalize any number into a desired range
def normalize(to_normalize, upper, multiplier, subtractor):
    return ((to_normalize / upper) * multiplier) - subtractor


# function that calculates the Euclidean distance between two certain positions
def euclidean_distance(x1, y1, x2, y2):
    a = numpy.array((x1, y1))
    b = numpy.array((x2, y2))
    dist = numpy.linalg.norm(a - b)
    return dist


# function that calculates the grade of influence of cell s' over cell s, based on a distance_limit
def distance_rate(s, s_, distance_limit):
    m_d = euclidean_distance(s[0], s[1], s_[0], s_[1])
    result = 0
    if m_d <= distance_limit:
        result = m_d ** -2.0
    return result
