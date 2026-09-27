"""Managing system: the nine values of a global UAV-role switch option (planning input only).

Used ONLY with GLOBAL_PLANNER_MODE = 1 (agents.global_planner_mode()); nothing here is
called at 0. Design: outputs/planner_part1.txt section 3 (E3). Every function is a PURE
function of plain numbers - the generator gathers the inputs from the knowledge models and
the managed entities (global_adaptation_generator._generate_role_switch_options); nothing
here reads a model, draws a random number or prints.

A switch option moves UAV u from role a to role b (fire_tracker <-> victim_searcher). Four
demands, each in [0, 1], none depending on who holds which role:
    D_fire   = min(1, |B \\ S| / 289)    B believed-burning cells (probability >= 0.7),
    D_stale  = min(1, |S| / 289)        S the stale part of B; 289 = one UAV's view area
    D_vict   = (N_v - N_det) / N_v       N_v the mission's victim count (a briefing prior),
                                        N_det those with the monotone detection flag
    D_unc    = never-seen cells / all cells
THE SHARE RULE: for a demand D belonging to role r, with n_r the number of UAVs holding r
(ALL holders, returning and docked included),
    share(D, r) = [b = r] * D / (n_r + 1) - [a = r] * D / n_r
- the part of r's demand u would carry after joining r, minus the part it carries now. A
move and its immediate reversal (n_a -> n_a - 1, n_b -> n_b + 1) are exact opposites on
unchanged demands, so only a change in the world can make the planner undo a move.
"""

from __future__ import annotations

import math

FIRE_TRACKER = "fire_tracker"
VICTIM_SEARCHER = "victim_searcher"
LIVE_ROLES = (FIRE_TRACKER, VICTIM_SEARCHER)

# One UAV's observation area, (2 * UAV_OBSERVATION_RADIUS + 1) ** 2 with the radius 8: the
# unit of the two fire demands (design constant, D-6).
VIEW_AREA_CELLS = 289
# switching_cost = SWITCH_BASE + SWITCH_RECENT * max(0, 1 - timer / SWITCH_WINDOW). 0.15 is
# the scorer's own default cost of a role change (utility_evaluation.py); D-6.
SWITCH_BASE = 0.15
SWITCH_RECENT = 0.85
SWITCH_WINDOW = 30.0
# I1: a UAV is available only with more than this many moving steps of battery above its
# return trigger when a base station returns UAVs (D-6).
AVAILABILITY_MARGIN_STEPS = 10

# The nine keys the global scorer reads (utility_evaluation._evaluate_global_mission_option),
# in its order.
NINE_VALUES = (
    "fire_contribution",
    "victim_contribution",
    "communication_contribution",
    "uncertainty_reduction",
    "information_recovery",
    "collision_risk",
    "battery_cost",
    "drift_risk",
    "switching_cost",
)


def live_role(role: object) -> str | None:
    """The live role a stored role string names: fire_tracker, victim_searcher (with the
    live alias victim_search), else None."""
    if role is None:
        return None
    text = str(role).strip().lower()
    if text == FIRE_TRACKER:
        return FIRE_TRACKER
    if text in (VICTIM_SEARCHER, "victim_search"):
        return VICTIM_SEARCHER
    return None


def other_role(role: str) -> str:
    return VICTIM_SEARCHER if role == FIRE_TRACKER else FIRE_TRACKER


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def fire_demand(n_believed_fresh: int) -> float:
    """D_fire: the believed-burning cells that are not stale, in view areas, at most 1."""
    return min(1.0, max(0, int(n_believed_fresh)) / VIEW_AREA_CELLS)


def stale_demand(n_believed_stale: int) -> float:
    """D_stale: the believed-burning cells gone stale, in view areas, at most 1."""
    return min(1.0, max(0, int(n_believed_stale)) / VIEW_AREA_CELLS)


def victim_demand(n_victims: int, n_detected: int) -> float:
    """D_vict: the share of the mission's victims not yet detected; 0 with no victims."""
    n_victims = int(n_victims)
    if n_victims <= 0:
        return 0.0
    return _clamp01((n_victims - int(n_detected)) / n_victims)


def uncertainty_demand(n_never_seen: int, n_cells: int) -> float:
    """D_unc: the share of map cells never seen; 0 with an empty map."""
    n_cells = int(n_cells)
    if n_cells <= 0:
        return 0.0
    return _clamp01(int(n_never_seen) / n_cells)


def share(demand: float, role: str, from_role: str, to_role: str, holders: dict) -> float:
    """share(D, r) = [b = r] * D / (n_r + 1) - [a = r] * D / n_r (section 3.0)."""
    n_r = int(holders.get(role, 0))
    gain = demand / (n_r + 1) if to_role == role else 0.0
    loss = demand / n_r if (from_role == role and n_r > 0) else 0.0
    return gain - loss


def collision_risk(n_near_working_in_new_role: int, n_uavs: int) -> float:
    """The share of the OTHER UAVs that work in the joined role within the security
    distance (returning / docked UAVs excluded by the caller)."""
    others = int(n_uavs) - 1
    if others <= 0:
        return 0.0
    return _clamp01(int(n_near_working_in_new_role) / others)


def battery_cost(
    battery: float,
    trigger_here: float,
    trigger_at_target: float | None,
    distance: int | None,
    per_move: float,
) -> float:
    """The share of the battery margin above the return trigger that flying to the new
    role's nearest work cell uses up, counting the flight and the higher trigger there:
    1 when there is no margin, else min(1, (per_move * d + max(0, tau_c - tau_u)) / m).
    With no work cell (distance None) nothing is consumed."""
    margin = float(battery) - float(trigger_here)
    if margin <= 0.0:
        return 1.0
    if distance is None:
        consumed = 0.0
    else:
        rise = 0.0 if trigger_at_target is None else max(0.0, float(trigger_at_target) - float(trigger_here))
        consumed = float(per_move) * int(distance) + rise
    return min(1.0, consumed / margin)


def drift_risk(drift_level: float | None) -> float:
    """0 before the first move (None), else the last move's drift clamped to [0, 1]."""
    if drift_level is None:
        return 0.0
    value = float(drift_level)
    if not math.isfinite(value):
        return 1.0 if value > 0 else 0.0
    return _clamp01(value)


def switching_cost(role_stability_timer: float | None) -> float:
    """0.15 for any change, plus up to 0.85 more decaying linearly to zero over the 31
    steps after the UAV's previous role assignment (launch included)."""
    timer = 0.0 if role_stability_timer is None else float(role_stability_timer)
    if not math.isfinite(timer):
        timer = 0.0
    return SWITCH_BASE + SWITCH_RECENT * max(0.0, 1.0 - timer / SWITCH_WINDOW)


def switch_option_values(
    *,
    from_role: str,
    to_role: str,
    holders: dict,
    demands: dict,
    n_near_working_in_new_role: int,
    n_uavs: int,
    battery: float,
    trigger_here: float,
    trigger_at_target: float | None,
    target_distance: int | None,
    per_move: float,
    drift_level: float | None,
    role_stability_timer: float | None,
) -> dict[str, float]:
    """The nine values of one switch option, finite floats, in NINE_VALUES order.

    demands: {"fire", "stale", "victim", "uncertainty"} from the *_demand functions.
    holders: {role: number of UAVs holding it}.
    """
    values = {
        "fire_contribution": share(demands["fire"], FIRE_TRACKER, from_role, to_role, holders),
        "victim_contribution": share(demands["victim"], VICTIM_SEARCHER, from_role, to_role, holders),
        # EXPLICIT ZERO (D-3): the simulator has no communication model in which a UAV's
        # role or position changes message delivery. Present, never absent.
        "communication_contribution": 0.0,
        "uncertainty_reduction": share(demands["uncertainty"], VICTIM_SEARCHER, from_role, to_role, holders),
        "information_recovery": share(demands["stale"], FIRE_TRACKER, from_role, to_role, holders),
        "collision_risk": collision_risk(n_near_working_in_new_role, n_uavs),
        "battery_cost": battery_cost(battery, trigger_here, trigger_at_target, target_distance, per_move),
        "drift_risk": drift_risk(drift_level),
        "switching_cost": switching_cost(role_stability_timer),
    }
    return {k: float(values[k]) for k in NINE_VALUES}


def zero_values() -> dict[str, float]:
    """The nine values of a role option that changes nothing (maintain / delay)."""
    return {k: 0.0 for k in NINE_VALUES}
