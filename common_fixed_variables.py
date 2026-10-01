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
# fix1 item 3: with both counts None the split is the maintainer's rule, searchers =
# max(1, n // 2) and trackers the rest (agents.half_rule_role_split): A 2+1, B 2+1, C 3+2,
# D 2+2. SHIPPED 1 (ruling D-1); only an exact integral 0 restores the legacy default of
# n-1 trackers + 1 searcher (which gave C 4+1 and D 3+1 in evaluate_scenarios / the
# dashboard, while the harness's --roles half ran D 2+2).
ROLE_SPLIT_HALF_RULE = 1

# fix1 item 4. A victim nobody has detected is never written off (it used to be marked
# unreachable/never_detected after 210 undetected steps, or geographically_isolated after
# 30 fire-isolated ones, and could then never be detected or rescued). A 210-step
# undetected streak now only labels it "long_undetected"; never_detected in the results
# means "not detected by the end of the run". SHIPPED 1 (ruling D-1); only an exact
# integral 0 restores the permanent write-off (agents.undetected_writeoff_fix).
UNDETECTED_WRITEOFF_FIX = 1

# fix1 item 6. The victim searcher's wind-search counters (position samples, streaks,
# steps_since_detection, dwell, post-rescue countdown) advance at most once per model step,
# so COVERAGE_Y_SWEEP_MIN_STEPS, WIND_POCKET_CAMP_THRESHOLD and the rest mean what their
# names say; they were counted per CALL (2-8x per step). SHIPPED 1 (ruling D-1); only an
# exact integral 0 restores per-call counting (agents.searcher_counters_per_step).
SEARCHER_COUNTERS_PER_STEP = 1

# ---- fix2 (session 2): behaviour fixes (outputs/fix2_part1.txt). Every switch SHIPS 1
# (ruling D-1); only an exact integral 0 turns one off; all of them at 0 is c08456b. ----------
# Row (B). The global analyzer reads the fire picture from FireRuntimeModel.belief, where it
# lives (it read top-level attributes that do not exist, so its fire triggers never fired).
# agents.global_analyzer_fire_source_fix.
GLOBAL_ANALYZER_FIRE_SOURCE_FIX = 1
# Item 1. Each fail-safe alarm fires only on the condition it names: COLLISION_RISK on another
# airborne UAV within Manhattan 2; DRIFT_TOO_HIGH on a refused move on >= 2 of the last 5 steps
# (no latch; a docked UAV is not drifting); CRITICAL_LINK_UNRELIABLE on real delivery outcomes;
# the search_mode_required reason on the FLEET having lost sight of a fire it believes burning.
# With no reason the fail-safe planner decides nothing. agents.failsafe_real_alarms.
FAILSAFE_REAL_ALARMS = 1
# Item 2. A hold holds: a committed 'hold' leaves the UAV on its cell (move() had no stay
# action). Under SAFETY_FIRST only the UAV that must yield in a close pair holds (right of way
# to the lower unique_id, never to a UAV on a return leg, at most 3 consecutive steps). A return
# leg never stays. agents.uav_hold_stationary.
UAV_HOLD_STATIONARY = 1
# Item 2 follow-up (maintainer ruling after the D-9 follow-up; fix2_part3_prereg.txt amendment 4):
# refinements of the stationary yield, read only while UAV_HOLD_STATIONARY is on. (1) a yield never
# escapes for standing on the grid edge (a stay cannot leave the grid), and a yield step records no
# drift; (2) a yielder on the cell its partner needs steps aside; (3) no yield when either UAV is on a
# return leg, docked, or within agents.DEPOT_APPROACH_RADIUS (3) of a depot. agents.stationary_yield_fix.
STATIONARY_YIELD_FIX = 1
# Rule (4), SHIPS 0 (on only on an exact integral 1): yield only when a partner's move can contend (its
# target within 1 of the yielder). OFF by the maintainer's test: it cut the non-depot yield stalls 9 -> 1
# but rescued 45 -> 44 and dead 8 -> 10 (outputs/fix2_report.txt). agents.yield_only_when_contending.
YIELD_ONLY_WHEN_CONTENDING = 0
# Item 4. Staggered launch batteries (the variant: STAGGER_COMPACT below). With STAGGER_COMPACT 0,
# the EVEN stagger: L_i = 100 - 0.3 * 220 / n * rank_i, the searchers spread
# evenly over the ~220-step battery cycle, so returns stop coinciding and (with two searchers) one
# searcher is meant to be flying at all times (the design's prediction; outputs/fix2_report.txt has
# the measurement). Scenario B stays a multiplier: 0.5 x L_i. agents.staggered_launch_bases.
# SHIPS OFF (on only on an exact integral 1): the even stagger (Part 3) and the compact stagger (the
# maintainer's follow-up ruling) both failed the D-9 test - before the terminal step the searcher time
# lost exceeds the no-searcher gap closed in C and D (outputs/fix2_report.txt). Off, the no-searcher gap
# and the depot-area contention of simultaneous returns are recorded limitations.
STAGGERED_LAUNCH_BATTERY = 0
# Item 4, the compact variant (maintainer ruling on D-9 after the even stagger's Part 3 STOP): the
# launch phases lie on HALF the battery cycle, the two searchers at its ends (half a cycle apart), the
# trackers between them - fewer early tracker returns, returns less spread. Read only while
# STAGGERED_LAUNCH_BATTERY is on (so inert as shipped); 0 = the even stagger over the whole cycle.
# agents.stagger_compact.
STAGGER_COMPACT = 1
# Item 3a. The victim searcher's coverage y-commit follows the wind (downwind strip first under
# north/south wind; disjoint camping bands under east/west). agents.searcher_wind_coverage_fix.
SEARCHER_WIND_COVERAGE_FIX = 1
# Item 3b. At VICTIM_SEARCHER_HAZARD_RETREAT_RANGE >= 99 the searcher hazard gate retreats only
# within 6 cells of a strict fire/smoke cell (it was a global repulsion on every gated step), and
# the gate-bypassing pathfinding route gets the same near-field rule. agents.searcher_gate_near_field.
SEARCHER_GATE_NEAR_FIELD = 1

# ---- fix3a (session 3a): the depot area and scenario B (outputs/fix3a_part1.txt; rulings R-1..R-5 in
# outputs/fix3a_part3_prereg.txt). Every switch SHIPS 1; only an exact integral 0 turns one off; all of
# them at 0 is a5a496db. ------------------------------------------------------------------------------------
# A1-R. The searcher's pathfinding route plans WITHIN its near-field guard over BURNING cells (smoke is
# impassable, not repelling), with the clearance agents.SEARCHER_ROUTE_CLEARANCE (6); no admissible step ->
# a step strictly away from the fire, else a wait. Replaces fix2 3b(ii)'s veto, which livelocked the
# searcher at the depots (3 never-finishing runs). agents.searcher_route_fire_field.
SEARCHER_ROUTE_FIRE_FIELD = 1
# A1-S. A victim searcher's sector (and its lawnmower sweep) excludes the edge band it may not enter
# (edge distance < agents.SEARCHER_EDGE_BAND, 4). agents.searcher_sweep_in_bounds.
SEARCHER_SWEEP_IN_BOUNDS = 1
# A1-D. The searcher edge filter measures the band's penetration per axis (a corner cell has an exit), and
# the pocket escape does not plan through another UAV. agents.searcher_corner_escape.
SEARCHER_CORNER_ESCAPE = 1
# A2. Free-cell docking: the nearest free depot-footprint cell by a UAV-avoiding path, re-picked when taken
# or unreachable; docked = inside a footprint; charging only inside one. agents.free_cell_docking.
FREE_CELL_DOCKING = 1
# B1. Scenario B's team: 4 UAV (2T + 2S) / 4 victims / 3 FF (0: 3 / 2 / 2). agents.scenario_b_team.
SCENARIO_B_TEAM = 1
# B2. In the battery scenario, launch charges 85 / 65 (searchers), 78 / 72 (trackers) replace the 0.5
# fraction. agents.scenario_b_staggered_launch.
SCENARIO_B_STAGGERED_LAUNCH = 1
# B3. In the battery scenario, a searcher's return waits while the other searcher is away, never below
# the floor 0.3 d + 32.30 (agents.return_delay_floor). agents.scenario_b_return_delay.
SCENARIO_B_RETURN_DELAY = 1
# The battery-scenario MARKER (a run parameter, not a switch): B's preset sets 1, every other preset 0
# (serve_dashboard.scenario_extra_params). agents.battery_scenario.
BATTERY_SCENARIO = 0

# ---- fix3b (session 3b): searcher targeting strategies (outputs/fix3b_part1.txt, rulings in its section
# 15). SEARCHER_TARGETING ships 0 = the current searcher, unchanged; any value that is not exactly one of the
# integers below is 0. agents.searcher_targeting.
#   0 current | 1 least-observed tile (baseline) | 2 Bayes, diffusion motion | 3 Bayes, fire-aware flee
#   motion | 4 random walk (exemplar-equivalent baseline)
SEARCHER_TARGETING = 0
# Ablation switches of the strategies 1-3 (inert at SEARCHER_TARGETING 0). Each ships 1; only an exact 0
# turns one off. REACHABILITY 0 is for the ablation ONLY and is never shipped (a test pins 1).
SEARCHER_TARGETING_COORDINATION = 1
SEARCHER_TARGETING_REACHABILITY = 1
SEARCHER_TARGETING_BATTERY = 1
SEARCHER_BELIEF_MOTION = 1
# The random walk passes through the searcher hazard gate only on an exact 1 (a control; primary = ungated).
SEARCHER_TARGETING_RW_GATED = 0
# Belief / targeting parameters, fixed before any run (fix3b_part1.txt 2.4, 3.4-3.6, 15.3).
SEARCHER_BELIEF_PD = 1.0                 # P_d inside the Euclidean-8 disc (the simulator's rule: 1)
SEARCHER_BELIEF_PD_SMOKE = 1.0           # P_d the belief assumes for smoke cells (sensitivity 0.5)
SEARCHER_BELIEF_DIFFUSION_Q = 0.1        # (a) lazy random walk: move probability
SEARCHER_BELIEF_FLEE_D50 = 5.0           # (b) alarm logistic midpoint, cells (Euclidean to fire)
SEARCHER_BELIEF_FLEE_S = 1.5             # (b) alarm logistic scale
SEARCHER_BELIEF_FLEE_P_GO = 0.8          # (b) an alarmed victim moves with this probability
SEARCHER_BELIEF_FLEE_BETA = 1.5          # (b) softmax weight on the fire-distance gain
SEARCHER_BELIEF_FLEE_Q_CALM = 0.02       # (b) an unalarmed victim's move probability
# Burn-over, per step, of alive mass still on a burning cell after the predict step. 0.1 (ruling R-3,
# 2026-10-01, set AFTER the screen and BEFORE the measurement round; 0.5 was the pre-registered value and is
# kept as a sensitivity): victims flee fire, so a burning cell does not imply its victim is likely dead.
SEARCHER_BELIEF_BURNOVER = 0.1
SEARCHER_BELIEF_STRIDE = 2               # candidate lattice stride
SEARCHER_TARGETING_TOP_M = 12            # candidates scored exactly (along-path gain)
SEARCHER_TARGETING_L0 = 4                # floor of the path length in the ratio
SEARCHER_TARGETING_MIN_DIST = 5          # Bayes targets need an admissible path of >= this many steps
                                         # (ruling R-1: = L0 + 1, so the floor never binds; fix3b report 4.5)
SEARCHER_TARGETING_SWEPT_RHO = 0.25      # held target dropped when its disc mass < rho * at issue
SEARCHER_TARGETING_GIVEUP_COOLDOWN = 15  # G: steps an unreachable target's area is excluded
SEARCHER_TARGETING_FALLBACK_HOLD = 10    # R: steps before retrying after a fallback
SEARCHER_TARGETING_TILE = 7              # least-observed tile size (cells)
SEARCHER_TARGETING_AGE_BUCKET = 10       # least-observed: ages within this many steps tie
# Environment (D-1): victim spawn. 0 = the legacy fixed ring (DEFAULT); 1 = i.i.d. uniform over the cells
# that are not a depot and not burning at t0, from a dedicated digest-seeded stream (the fire stream is
# unchanged). agents.victim_spawn_mode.
VICTIM_SPAWN_MODE = 0
# The ONE battery threshold pair (fix1 item 2), read at call time through
# agents.battery_low_threshold() / battery_critical_threshold() by every reader: the UAV
# labels, both analyzers, the resource model, the global monitor, the dashboard alert and
# the utility feasibility check. The return-to-base rule turns a UAV home at >= 39 %
# (0.3 * distance + BASE_STATION_RETURN_MARGIN), ABOVE LOW, so in flight neither value is
# ever reached, and LOW_BATTERY has no consumer - see outputs/fix1_part1.txt section 2.
LOW_BATTERY_THRESHOLD = 30.0
BATTERY_CRITICAL_THRESHOLD = 15.0

# Launch charge (fix1 item 2). Every UAV launches with UAV_LAUNCH_BATTERY_FRACTION x its
# launch battery (100 today; session 2's staggered launch battery replaces that base and
# this fraction stays a multiplier on it). A value outside (0, 1] RAISES at model build.
# Scenario B's preset (serve_dashboard.BUILTIN_SCENARIOS) sets 0.5; A, C and D leave 1.0.
# REDUCED_LAUNCH_BATTERY is the switch: SHIPPED 1 (ruling D-1); only an exact integral 0
# turns it off, and then the fraction is ignored (B launches at full charge, as before).
UAV_LAUNCH_BATTERY_FRACTION = 1.0
REDUCED_LAUNCH_BATTERY = 1

# Scenario B — Battery-Constrained (fix1 item 2; the team and launch charges are fix3a B1 / B2)
# SINCE fix3a: 4 UAV (2 trackers + 2 searchers) / 4 victims / 3 FF (SCENARIO_B_TEAM; 0 = the old 3 / 2 / 2),
# launching at 85 / 65 (searchers) and 78 / 72 (trackers) (SCENARIO_B_STAGGERED_LAUNCH; 0 = every UAV at
# HALF charge, UAV_LAUNCH_BATTERY_FRACTION 0.5, set by the preset), with the searcher return delay B3
# (SCENARIO_B_RETURN_DELAY). The preset is serve_dashboard.BUILTIN_SCENARIOS["B"] through
# serve_dashboard.scenario_preset. At 0.5 (the fix1 definition, 3 UAVs): an early in-flight return (steps
# ~19-23 at ~43 %) and a second one (~215-246) per UAV, against one (~160-202) in A, C and D. It is NOT a
# "fail-safe on low battery" scenario: no battery trigger fires at this setting.
# DO NOT revive the old `BATTERY_CRITICAL_THRESHOLD = 50.0` of this block: every return
# leg arrives at ~39 %, so every trip would raise CRITICAL_BATTERY and - with the
# collision-risk artifact alarm live on ~91 % of steps - put the whole fleet in EMERGENCY.

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
#   >= 99   on at every gated step - with SEARCHER_GATE_NEAR_FIELD on (fix2 item
#           3b, the default) only while a strict fire/smoke cell is within 6 cells,
#           and the same rule also applies to the pathfinding route
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

# VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX - the legality guard on the two
# fall-through returns of _apply_victim_searcher_hazard_gate
# (src_extension/execution/uav_executor.py:2321 and :2402). Derivation, the three
# rejected alternatives and the full gate: outputs/searcherfix_part1.txt.
#
# THE DEFECT. When no safe in-bounds neighbour exists the retreat returns None
# and the gate hands back the UPSTREAM direction with no bounds test, labelled
# victim_search_hazard_retreat. At a grid edge that direction leaves the grid,
# agents.py move() refuses it on out_of_bounds, the geometry is unchanged, and
# the same illegal direction is re-emitted every step. Measured: 10 distinct
# pins over 57 shipped-default tuples, longest 26 consecutive refused steps, ALL
# on a boundary; 657/657 out-of-bounds refusals are victim searchers and none is
# a tracker in 23,422 tracker-steps.
#   0  OFF. THE KILL SWITCH. Both returns behave exactly as at 737b6c7, and a run
#      is value-identical to that commit.
#   1  ON, REVERSE ONLY - the shipped default. When the fall-through direction
#      leaves the grid it is replaced by (direction + 2) % 4. That reverse is
#      PROVABLY always in bounds (an off-grid step means the offending coordinate
#      is at an extreme, so negating it lands at 1 or max-1) and it strictly
#      increases the distance to the boundary the UAV is pressed against, at
#      corners too. It adds NO preference of any kind: it reads no fire, no
#      smoke and no ground history.
#   2  ON, NEAREST-INDEX SCAN - the attribution arm. Substitutes via the
#      executor's own _first_boundary_safe_direction, scanning (chosen,
#      chosen+1, chosen+3, chosen+2) and taking the first in-bounds one. This can
#      pick a non-inward legal move and so gives up the monotone-inward property
#      that makes rung 1 analysable. Kept SEPARATE, not bundled, because it is
#      the rung that edges toward a preference and the two are not the same
#      experiment.
#
# WHY THE RETREAT ITSELF IS UNTOUCHED. Turning it down is a measured-harmful
# third option: range 99 (shipped) 2.59% < range 6 3.10% < range 0 3.45% of
# searcher steps on burning ground. The feature causing the pins is the best
# setting measured, so this guards only the fall-through.
#
# SCOPE. It fires only when the returned direction is out of bounds - a no-op on
# every step whose direction is already legal (~98.9% of searcher-steps) - and it
# cannot fire for a fire tracker, which never reaches this gate: the primary call
# site is role-guarded at uav_executor.py:419 and the other five sit inside the
# `role_kind == "victim"` block at :923. It makes the DIRECTION legal, not the
# MOVE successful: agents.py:852 also requires not_UAV_adjacent, so an occupancy
# refusal remains possible and is a pre-registered gate item.
#
# ONLY AN EXACT INTEGRAL ZERO DISABLES IT. Read at call time from this module
# through uav_executor._offgrid_guard_level, so an apply_scenario_config override
# applies; its fallback is the SHIPPED value, which carries the recorded hazard
# that a junk override ARMS this rather than disarming it. A bare int() would
# truncate 0.5 to 0 and silently take the OFF path - the defect class this repo
# has now hit three times. Deterministic; draws from no RNG.
VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX = 1

# Firefighter fire mechanic (round 1, outputs/firemech_part1.txt; SHIPPED ON and
# ungated since the ungated round - see below). An IDLE firefighter - one the rescue
# dispatcher counts as available and that has no target - works against the fire
# front from step 1; any rescue assignment preempts it on its very next advance. Both actions are the same write, removing a cell's fuel, and
# the Fire state machine does the rest:
#   EXTINGUISH  a burning front cell within manhattan 2: it stops burning at once
#               and turns burnt (absorbing) at the next fire tick.
#   FIREBREAK   an ignitable cell (not burning, not burnt, fuel > 0 - scorched
#               cells included) within manhattan 1, chosen from the band at
#               EUCLIDEAN distance (2, 5] from the nearest burning cell. A completed
#               band of that euclidean width blocks spread in every orientation; a
#               3-wide manhattan band leaks on a 45-degree front
#               (outputs/_firemech_band_probe.txt).
# FF_FIREFIGHT_ENGAGED_RETREAT_RANGE is retreat suppression: while a unit is
# engaged, its idle retreat distance (IDLE_RETREAT_SAFETY_BUFFER, 3) drops to this
# value. 1 is the distance an ASSIGNED firefighter already retreats at. Extinguish
# at reach 2 is only possible below 2, so without suppression it never acts - which
# is why the shipped value is 1 and not 2: at 2 the shipped configuration would
# silently be firebreak-only. It is a DISTANCE, not a switch: an exact 0 is its
# kill switch (no suppression), 1 and 2 suppress, and an explicit integer 3 or more
# is the unsuppressed buffer itself - what the old accessor returned for every integer
# >= 3, which the flip preserves. (Round 1's firebreak-only arms never set it: they ran
# at the then-default 3, so re-run now they get 1; set 3 explicitly to reproduce them.)
# A negative, non-integral or unparseable value is junk and takes the shipped 1.
# FF_FIREFIGHT_DRY_RUN keeps every decision and suppresses every fire write (the
# targeting then treats the would-be-written cell as done), which isolates the
# behaviour from its effect on the fire. A diagnostic arm, never shipped.
# FF_FIREFIGHT_MISSION_GATE (round 2) is WHEN a unit may engage: 1 = only once every
# managed victim's status is rescued or dead, 0 = any idle unit at any time (round 1's
# policy). The gate makes the feature rescue-neutral BY CONSTRUCTION - before it opens
# no unit moves differently and no fire write lands - at the price of giving up every
# effect before the mission is decided (outputs/firemech2_part1.txt sections 1 and 4).
#
# SHIPPED UNGATED (outputs/ungated_part1.txt, outputs/ungated_report.txt): the
# supervisor's policy, "by the time drones are looking for the victims, the
# firefighter must fight with the fire". EXTINGUISH 1, FIREBREAK 1, RANGE 1, GATE 0 -
# round 1's full configuration (fmEFS). THIS CARRIES A MEASURED, ACCEPTED RESCUE COST,
# by two channels that are never pooled: -2 of 68 rescued in the stock realisation
# (round 1; -2 of 59 de-duplicated), and under common random numbers -3 of 72 counted
# for this configuration (-5 of 66 de-duplicated), where positioning alone (the dry arm)
# is -6 counted / -5 de-duplicated. The writes' counted +3 over the dry arm is ONE run,
# east/def/101, whose fire east/half/101 shares; de-duplicated the writes change no
# rescue (61 vs 61; firemech2_part1.txt:445-447). Under CRN the cost is positioning: idle
# units have walked toward the fire when a rescue is dispatched, which re-times the
# rescue chain (firemech2_report.txt:165-169). In the stock model, which is what ships,
# the writes ALSO re-roll the fire's single random stream and so move individual rescues
# both ways (round 1: positioning -2 / writes +0 counted, -1 / -1 de-duplicated).
# Re-measured at the ungated commit on a fresh independent seed set:
# outputs/ungated_report.txt. Measured with two firefighters (scenario D), east and
# south winds, 240 steps; west/north winds, longer runs and more units are unmeasured.
#
# THE ACCESSORS (agents.py ff_firefight_*) share one rule: ONLY AN EXACT INTEGRAL ZERO
# DISABLES (0, 0.0, "0", False); a MISSING attribute takes the SHIPPED value, so a
# missing value can never silently disagree with this file; anything that is not an
# exact integer - junk, None, 0.5, inf, nan, Decimal("0.5") - ARMS rather than taking
# the zero path. For EXTINGUISH, FIREBREAK and RANGE "arms" is the shipped value. The
# gate is the one switch whose shipped value IS the zero: missing -> 0, and junk
# closes it (ON), so a typo can only make the feature more rescue-neutral, never
# less. FF_FIREFIGHT_DRY_RUN keeps its round-1 accessor (a bare int, fallback 0): its
# default did not change, and closing that truncation belongs to the accessor round.
# Overridable per run through apply_scenario_config like every other scenario parameter,
# and read at call time. Deterministic - it draws from no RNG.
FF_FIREFIGHT_EXTINGUISH = 1
FF_FIREFIGHT_FIREBREAK = 1
FF_FIREFIGHT_ENGAGED_RETREAT_RANGE = 1
FF_FIREFIGHT_DRY_RUN = 0
FF_FIREFIGHT_MISSION_GATE = 0

# The carrying leg (outputs/carryleg_part1.txt): three pre-existing defects of a
# firefighter's trip home with a victim, one switch each, each measured in its own arm.
#   FF_EXIT_LEG_MODE    D1, the memoryless exit-leg livelock. 1 = a rescue completes
#                       on ANY boundary cell, not only the exit cell fixed at pickup;
#                       2 = 1 plus each carrying step takes the first step of a
#                       breadth-first search over clean cells (not burning, not
#                       fire-adjacent, not smoky) to the nearest boundary cell, falling
#                       back to today's rule when no clean path exists.
#   FF_EXIT_LEG_HOLD    D2, the carrier drop. 1 = an enclosed carrier holds its cell
#                       and keeps its victim instead of raising route_blocked, whose
#                       replacement pathway unassigns it and drops the victim.
#   FF_EXIT_LEG_SERVED  D3, the isolation timeout. 1 = a victim in a live carrier's
#                       custody counts as served, so it cannot be written off as
#                       geographically isolated while it is being carried out.
# SHIPPED after the round's gate (outputs/carryleg_report.txt; carryleg_prereg.txt
# section 10): MODE 2 and SERVED 1; HOLD stays 0 (ruling S1: inert under the shipped
# MODE 2 - identical on all 160 Part 3 runs - so it does not ship). With all three
# at an exact 0 the model is value-identical to 6160438 - the kill switch (flip gate clFZ).
# ONLY AN EXACT INTEGRAL ZERO DISABLES: a missing value takes the shipped value, and junk
# arms (MODE and SERVED: their shipped value; HOLD: True) - agents.py ff_exit_leg_*.
# SERVED IS ENFORCED OFF WHENEVER FF_EXIT_LEG_MODE IS 0 (agents.ff_exit_leg_served; the
# maintainer's ruling S2). The reason: at MODE 0 the isolation write-off is a carrier's only
# way out of the D1 edge livelock, and SERVED removes it (the D-9 probe, stock
# east/half/1433805104: the carrier dies with its victim at 288).
# Read at call time through agents.ff_exit_leg_*(), never through the star import, so
# an apply_scenario_config override is visible. Deterministic: no RNG is drawn.
FF_EXIT_LEG_MODE = 2
FF_EXIT_LEG_HOLD = 0
FF_EXIT_LEG_SERVED = 1

# The planning step's strategy for UAV ROLES (outputs/planner_part1.txt). A ladder:
#   0  LOCAL STRATEGY (shipped): today's behaviour. The global planner's role options
#      are generated as before and never win; roles change only at launch. With 0 the
#      model is value-identical to dfbfbe7 (tag carrying-leg-fixed).
#   1  GLOBAL PLANNER FOR UAV ROLES: every step the global role family offers, for each
#      available UAV, "switch this UAV to the other live role" (fire_tracker <->
#      victim_searcher), valued on nine stated world quantities
#      (src_extension/adaptation/role_option_values.py) and ranked by the unchanged
#      scorer against the unchanged do-nothing baseline; a winning switch reaches the
#      UAV through the GlobalExecutor.
# ON ONLY ON AN EXACT 1 (the maintainer's ruling D-1): the planner ships OFF as an
# opt-in strategy, so the mirror of the exact-zero rule applies - missing, junk, "0.0",
# 0.5, 2 and every other value are OFF; no typo can switch the system to an unmeasured
# strategy. A later rung must be added explicitly. Read at call time through
# agents.global_planner_mode(), never through the star import. Deterministic: no RNG.
GLOBAL_PLANNER_MODE = 0

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

# BASE_STATION_FIREPROOF - the depot ground is created WITHOUT FUEL, so the base
# station cannot burn. This is a FIRE-SPREAD change, not a display one: 50 of the
# 2,500 cells (2.0%) stop being ignitable, and the existing corpus says fire
# reaches a depot in 25 of 27 runs, before outcomes settle in 19 of them
# (outputs/depotfireproof_part1.txt section 1). It has its own gated round.
#
# WHY. UAVs are fire-immune, so a burning depot costs nothing in rescue outcomes -
# but the dcd4 round measured 14 of 23 same-cell burning-step stays as UAVs
# CHARGING IN A BURNING DEPOT, and that is the main driver of the drone-steps-in-
# fire metric. A base station that burns while drones keep charging in it is not
# defensible as a model.
#
# HOW. wildfire_model._fireproof_base_station() calls the EXISTING
# agents.Fire.firefighter_remove_fuel() on every depot cell's Fire agent, once, in
# reset(), immediately after the station is built. No new write path. That method
# draws no random number and Fire.__init__ has already drawn the cell's fuel, so
# the clear itself shifts nothing in the shared RNG stream; a fuel-less cell keeps
# drawing its own number on every fire tick (agents.py:103, probability_of_fire
# returns 0 at :84-85), so the two arms stay draw-for-draw aligned until the first
# tick on which a depot cell WOULD have ignited. See depotfireproof_part1.txt 2.2.
#
#   0  OFF - the kill switch. The loop is not entered and nothing is written; the
#      run must be VALUE-IDENTICAL to 6281542 on every recorded value except tag /
#      repo / wall_s and the arm's own params.
#   1  ON - every depot cell's fuel is cleared at init.
#
# BASE_STATION_FIREPROOF_DRY_RUN = 1 identifies and records the depot cells and
# does NOT clear them: every recorded fire value, digests included, must equal the
# switch-0 arm's. A diagnostic arm, never shipped. Its fallback is the NOT-DRY
# value, exactly as FF_FIREFIGHT_DRY_RUN's is.
#
# THE RECORDED HAZARD APPLIES. Like every other base-station accessor,
# agents.base_station_fireproof() falls back to the SHIPPED value, so a junk
# override (--set BASE_STATION_FIREPROOF=off) ARMS the feature rather than
# disarming it. Read at call time through the cfv module, never star-imported, or
# apply_scenario_config's override would be invisible and the switch decorative.
BASE_STATION_FIREPROOF = 1
BASE_STATION_FIREPROOF_DRY_RUN = 0
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
