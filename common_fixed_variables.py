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

# Base station (feature 3). A 5x5 depot in one corner of the grid that the UAV
# team and the firefighters launch from, that a UAV returns to when its battery
# reaches the return reserve, and that recharges it.
#
# BASE_STATION_MODE is an ordinal ladder, and each level is a strict superset of
# the one below it, so a level-N vs level-(N-1) comparison attributes exactly one
# increment:
#   0  off - the kill switch. No depot is built, spawn is the pre-feature centre
#      cluster, and every entry point returns before any state write, so the model
#      is byte-identical to the checkout before this feature.
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
# The corner is the NW block, x in [0,4] and y in [WIDTH-5, WIDTH-1]: the only
# corner upwind of BOTH canonical winds (east pushes fire toward +x, south toward
# -y) and the shortest mean distance to the victim ring in all four built-in
# scenarios. NOTE the asymmetry: common_fixed_variables defaults WIND_DIRECTION to
# 'west', under which this corner is downwind - a bare `python main.py` run
# therefore puts the depot in the fire's path, while the gated east/south wave
# does not.
#
# UAV_RETURN_TO_BASE_RESERVE is derived, not tuned. It is the larger of a fuel
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
# override is invisible and the constant is decorative. Deterministic: the depot,
# the berth ranking and every spawn cell are pure functions of the grid extent and
# the agent counts, and draw from no RNG at all.
#
# SHIPPED DEFAULT IS 0 - OFF. The feature is complete, killable and covered by
# tests, but it is not on by default, because at mode 3 it fails three of the
# round's gate items: never_detected 1 -> 8 over 23 runs, rescued -5 on the
# route_blocked gate's independent 18-seed sample, and - the blocker - TWO
# firefighters left permanently latched as route_blocked on seed 808, which is
# the defect category commit 70e1b33 closed and whose mechanism here is indirect
# and NOT diagnosed. With this at 0 the model's default behaviour is provably
# identical to 16b2da8: that is the bsoff arm, byte-identical on all 27 recorded
# fields across 13 canonical and 10 fresh runs. Set it to 1/2/3 to arm the
# feature. See outputs/basestation_report.txt section 4.
BASE_STATION_MODE = 0
BASE_STATION_RETURN_MECHANISM = 2
BASE_STATION_SPAWN_FIREFIGHTERS = 1
BASE_STATION_SIZE = 5
UAV_RETURN_TO_BASE_RESERVE = 60.0
BASE_STATION_RETURN_MARGIN = 5.0
BASE_STATION_RECHARGE_PER_STEP = 5.0
BASE_STATION_RECHARGE_RELEASE_LEVEL = 100.0
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
#   0  OFF - the kill switch. Provably byte-identical to f4e79d5, stdout included.
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
# save a victim - by its own trigger it cannot. On seed 202, the shipped
# default, the victim was lost because the replacement died in the same step,
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
