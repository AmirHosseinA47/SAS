# python libraries

import mesa
import functools
from collections import deque

# own python modules

import common_fixed_variables as cfv
from common_fixed_variables import *
from src_extension.dashboard.movement_explainability import (
    movement_transition_key,
    notable_firefighter_movement_category,
)


# Class Fire holds methods for managing Fire agents
class Fire(mesa.Agent):

    # constructor
    def __init__(self, unique_id, model, burning=False):
        super().__init__(unique_id, model)
        self.fuel = random.randint(FUEL_BOTTOM_LIMIT, FUEL_UPPER_LIMIT)
        self.burning = burning
        self.burnt = False
        self.has_burned = bool(burning)
        self.next_burning_state = None
        self.moore = True
        self.radius = 3
        self.selected_dir = 0
        self.steps_counter = 0
        self.cell_prob = 0.0

        # smoke
        self.smoke = Smoke(fire_cell_fuel=self.fuel)

    # checks if the corresponding Fire agent is burning | True if burning, False if not
    def is_burning(self):
        return self.burning

    def is_burnt(self):
        return self.burnt

    # get the corresponding Fire agent remaining fuel | Integer value
    def get_fuel(self):
        return round(self.fuel)

    # get the corresponding Fire agent burning probability
    def get_prob(self):
        return self.cell_prob

    # function that calculates probability of cell s being burned in next time step (p_t+1(s))
    def probability_of_fire(self):
        if self.burnt:
            return 0
        probs = []
        # if at least cell s has some fuel remaining
        if self.fuel > 0:
            # obtains adjacent cells for a given one (self.pos), based on a radius (self.radius)
            adjacent_cells = self.model.grid.get_neighborhood(
                self.pos, moore=self.moore, include_center=False, radius=self.radius
            )

            # iterates through each adjacent cell to calculate cell s probability of being burned
            # based on the adjacent ones
            for adjacent in adjacent_cells:
                # obtains cell content, such as different agents
                agents_in_adjacent = self.model.grid.get_cell_list_contents([adjacent])
                # iterates through each found agent of an adjacent cell
                for agent in agents_in_adjacent:
                    if type(agent) is Fire:
                        adjacent_burning = 1 if agent.is_burning() else 0
                        # calculates partial probability of burning cell s (self.pos), being influenced by adjacent (s')
                        aux_prob = distance_rate(self.pos, adjacent, self.radius) * adjacent_burning
                        # in this if statement, the wind logic occurs, by biasing the burning cell probability
                        if ACTIVATE_WIND and (adjacent_burning == 1):
                            # applies wind to the partial probability
                            aux_prob = self.model.wind.apply_wind(aux_prob, self.pos, agent.pos)
                        probs.append(1 - aux_prob)
            if len(probs) == 0:  # if a low tree density is set, this might happen, so it must be checked
                P = 0
            else:
                P = 1 - functools.reduce(lambda a, b: a * b, probs)
        else:
            P = 0
        return P

    # Mesa framework native method, which is overwritten, necessary for setting next state of the simulation
    def step(self):
        self.steps_counter += 1
        if self.burnt:
            self.next_burning_state = False
            if ACTIVATE_SMOKE:
                self.smoke.smoke_step(False)
            return
        # make fire spread slower
        if self.steps_counter % FIRE_SPREAD_SPEED == 0:
            # if self.steps_counter == 26: # to model how the wind can suddenly change direction
            #     self.model.wind.wind_direction = 'south'
            self.cell_prob = self.probability_of_fire()
            self.cell_prob = self.cell_prob * FIRE_SPREAD_MULTIPLIER
            self.cell_prob = max(0.0, min(1.0, self.cell_prob))
            generated = random.random()
            self.next_burning_state = generated < self.cell_prob
            if self.burning:
                self.has_burned = True
                if self.fuel > 0:
                    self.fuel = self.fuel - BURNING_RATE
            if self.has_burned and self.fuel <= 0:
                self.burnt = True
                self.burning = False
                self.next_burning_state = False
            # smoke step
            if ACTIVATE_SMOKE:
                self.smoke.smoke_step(self.burning)

    # Mesa framework native method, which is overwritten, necessary for executing changes made in step() method. This
    # logic is required to not update the overall grid state until all cells step() method where executed.
    def advance(self):
        # make fire spread slower
        if self.steps_counter % FIRE_SPREAD_SPEED == 0:
            if self.burnt:
                self.burning = False
                return
            self.burning = self.next_burning_state


# Class Smoke holds methods for managing smoke functionality
class Smoke:

    # constructor
    def __init__(self, fire_cell_fuel):
        self.smoke = False
        self.dispelling_counter_start_value = fire_cell_fuel
        self.dispelling_lower_bound_start_value = SMOKE_PRE_DISPELLING_COUNTER
        self.dispelling_lower_bound = self.dispelling_lower_bound_start_value
        self.dispelling_counter = self.dispelling_counter_start_value

    # it gets the remaining dispelling counter value
    def get_dispelling_counter_value(self):
        return self.dispelling_counter

    # it gets the remaining pre-dispelling counter value
    def get_dispelling_counter_start_value(self):
        return self.dispelling_counter_start_value

    # it gets if smoke is active | True if active, False if not
    def is_smoke_active(self):
        return self.smoke

    # it subtracts one from dispelling counter value
    def subtract_dispelling_counter(self):
        self.dispelling_counter -= 1

    # function that updates smoke state and its counters based on certain conditions
    def smoke_step(self, burning):
        # if smoke isn't activated yet:
        if not self.smoke and self.dispelling_counter == self.dispelling_counter_start_value:
            # if pre-dispelling smoke counter can start (cell is burning), or if it already started:
            if ((burning and self.dispelling_lower_bound == self.dispelling_lower_bound_start_value) or
                    (0 < self.dispelling_lower_bound < self.dispelling_lower_bound_start_value)):
                # subtract from pre-dispelling counter (on the way to start smoke)
                self.dispelling_lower_bound -= 1
            # if pre-dispelling smoke counter already finished:
            elif self.dispelling_lower_bound == 0:
                # start smoke counter (activate smoke)
                self.smoke = True
        # if smoke can start, or if it already started
        elif self.smoke:
            # if dispelling counter can start, or if it already started
            if 0 < self.dispelling_counter <= self.dispelling_counter_start_value:
                # subtract from dispelling counter
                self.subtract_dispelling_counter()
            # if dispelling counter already finished
            elif self.dispelling_counter == 0:
                # smoke counter is stopped
                self.smoke = False


# Class Wind holds methods for managing wind functionality
class Wind:

    # constructor
    def __init__(self):
        self.wind_direction = cfv.normalize_wind_direction(cfv.WIND_DIRECTION)

    # it allows to change wind direction based on FIRST_DIR_PROB value
    def change_direction(self):
        if cfv.SYSTEM_RANDOM.random() < cfv.FIRST_DIR_PROB:
            self.wind_direction = cfv.normalize_wind_direction(cfv.FIRST_DIR)
        else:
            self.wind_direction = cfv.normalize_wind_direction(cfv.SECOND_DIR)

    # function to apply wind to partial burning probability of cell s (relative_center_pos),
    # caused by cell s' (adjacent_pos)
    def apply_wind(self, aux_prob, relative_center_pos, adjacent_pos):
        # if wind is compound by more than one direction
        if not cfv.FIXED_WIND:
            self.change_direction()
            # print("Wind: ", self.wind_direction)
        if self.is_on_wind_direction(relative_center_pos, adjacent_pos):
            aux_prob = aux_prob + (MU * (1 - aux_prob))  # part of 1 I- 'aux_prob' probability is added, depending on mu
        else:
            aux_prob = aux_prob - (MU * aux_prob)  # part of 'aux_prob' probability is removed, depending on mu
        return aux_prob

    # function that checks if cell located in relative_center_pos is on wind direction, influenced by cell located
    # in adjacent_pos
    def is_on_wind_direction(self, relative_center_pos, adjacent_pos):
        on_wind_direction = False
        if self.wind_direction == 'east':
            if (relative_center_pos[0] > adjacent_pos[0]) and (relative_center_pos[1] == adjacent_pos[1]):
                on_wind_direction = True
        elif self.wind_direction == 'west':
            if (relative_center_pos[0] < adjacent_pos[0]) and (relative_center_pos[1] == adjacent_pos[1]):
                on_wind_direction = True
        elif self.wind_direction == 'north':
            if (relative_center_pos[1] > adjacent_pos[1]) and (relative_center_pos[0] == adjacent_pos[0]):
                on_wind_direction = True
        elif self.wind_direction == 'south':
            if (relative_center_pos[1] < adjacent_pos[1]) and (relative_center_pos[0] == adjacent_pos[0]):
                on_wind_direction = True
        return on_wind_direction


# Class UAV holds methods for managing UAV agents
class UAV(mesa.Agent):

    # constructor
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.moore = True
        self.selected_dir = 0
        self.execution_direction_applied = False
        self.execution_action: str | None = None
        # Managed operational battery (observed by Step 5 monitoring; does not affect movement).
        self.battery_level = 100.0
        self.battery_status = "normal"
        self.battery_drain_per_step = 0.1
        self.battery_drain_per_move = 0.2
        self.battery_low_threshold = 30.0
        self.battery_critical_threshold = 15.0
        # Feature 3 (base station). All defaulted so that with BASE_STATION_MODE = 0
        # nothing here is ever read and the class behaves exactly as before.
        # rtb_berth is the UAV's own docking cell, assigned once by the model at
        # spawn; distinct berths are what make the return leg deadlock-free, since
        # not_UAV_adjacent only ever refuses a move into an occupied cell.
        self.rtb_berth: tuple[int, int] | None = None
        # Depot-cost round: with more than one depot a UAV owns a berth in EVERY
        # depot, and returns to the nearest of its own. Owning one berth per depot
        # is what preserves the invariant the single-depot design rests on - no two
        # UAVs ever share a berth, whichever depot each one picks - without needing
        # a claim/release protocol. rtb_berths[i] is this UAV's berth in depot i;
        # with one depot it is (rtb_berth,) and every path below is bit-identical
        # to the single-depot behaviour.
        self.rtb_berths: tuple[tuple[int, int], ...] = ()
        self.rtb_home_depot = 0
        # The TARGET is chosen once, at the trigger, and LATCHED for the trip.
        # Re-running the argmin every step would make a UAV equidistant from two
        # depots flip its target each step, and _rtb_direction would reverse with
        # it - the stall sidestep cannot rescue that (see its own note below).
        self.rtb_target_berth: tuple[int, int] | None = None
        self.rtb_target_depot: int | None = None
        self.rtb_active = False
        self.rtb_docked = False
        self.rtb_last_pos: tuple[int, int] | None = None
        # Dock-fix round. CONSECUTIVE steps of this return leg on which the move
        # was refused; ANY successful move resets it, so a leg that is making
        # progress starts over and blocks scattered earlier in the trip cannot
        # spend the budget. It is its own field rather than a reading of
        # rtb_last_pos because rtb_last_pos is written BELOW the mechanism gate in
        # _apply_return_to_base and so is never set under
        # BASE_STATION_RETURN_MECHANISM 1, while the docking block runs for both.
        self.rtb_stall_steps = 0
        # The depot cell this UAV is routing to while its leg is stalled OUTSIDE
        # the depot; None whenever the recovery is not engaged. LATCHED, and it
        # owns the steer on EVERY step until the depot is reached. Engaging it
        # only on stalled steps is a livelock, not a fix: the escape moves the
        # UAV, so the next step it is not stalled, the unmodified greedy runs and
        # walks it straight back. See outputs/dockfix_part1.txt section 5a.
        self.rtb_recovery_cell: tuple[int, int] | None = None
        # Whether the PREVIOUS steer was toward the recovery cell. The stall is
        # relative to a target: the swap in _rtb_direction breaks a deadlock
        # against the cell we were refused moving toward, so carrying it into the
        # first steer toward a NEW target makes it swap an axis it has never been
        # refused on - and at (4,44) that is the blocked one.
        self.rtb_recovery_steered: tuple[int, int] | None = None
        # Mechanism reporting, read by the harness; none of it feeds behaviour.
        # rtb_log carries ONE RECORD PER TRIP, not just the latest, because the
        # round has to account for every return individually - how long it took,
        # how far the UAV was, whether it arrived at all.
        self.rtb_trips = 0
        self.rtb_cycles = 0
        self.rtb_return_steps = 0
        self.rtb_charge_steps = 0
        self.rtb_log: list[dict] = []
        # Local monitoring (observe-only); monitor object is attached after runtime knowledge init.
        self.local_monitor = None
        self.latest_local_observation = None
        self._monitor_prev_actual_delta = (0, 0)
        self._monitor_prev_drift_error = 0.0

    @property
    def current_role(self) -> str:
        """Return the UAV role stored in managed/runtime state."""
        try:
            uid = str(self.unique_id)
            managed = getattr(self.model, "managed_uav_states", {}) or {}
            if uid in managed:
                role = getattr(managed[uid], "role", "")
                if role:
                    return str(role)
            rm = getattr(self.model, "uav_resource_model", None)
            if rm is not None:
                state = getattr(rm, "by_uav_id", {}).get(uid)
                if state is not None:
                    role = getattr(state, "current_role", "")
                    if role:
                        return str(role)
        except Exception:
            pass
        return ""

    def _update_battery_after_step(self, moved: bool) -> None:
        """Apply per-step and per-move drain; update status labels (no movement or planning effects)."""
        self.battery_level -= self.battery_drain_per_step
        if moved:
            self.battery_level -= self.battery_drain_per_move
        # Feature 3: the depot is the first and only code path in this model that
        # raises battery_level. It is applied after the drain and before the
        # existing clamp, which already caps at 100, so a recharge that overshoots
        # is harmless. A docked UAV never moves, so the net rate is rate - 0.1.
        if self.rtb_docked and base_station_mode() >= 3:
            self.battery_level += base_station_recharge_per_step()
            self.rtb_charge_steps += 1
        self.battery_level = max(0.0, min(100.0, float(self.battery_level)))
        if self.battery_level <= self.battery_critical_threshold:
            self.battery_status = "critical"
        elif self.battery_level <= self.battery_low_threshold:
            self.battery_status = "low"
        else:
            self.battery_status = "normal"

    # function that checks if an UAV in a certain position (pos), has another UAV nearby. If so, it can't move,
    # otherwise it will be possible to move.
    def not_UAV_adjacent(self, pos):
        can_move = True
        agents_in_pos = self.model.grid.get_cell_list_contents([pos])
        for agent in agents_in_pos:
            if type(agent) is UAV:
                can_move = False
        return can_move

    # function for obtaining observed cells for the corresponding UAV
    def surrounding_states(self):
        surrounding_states = []
        # obtains adjacent cells s' from a concrete cell s (self.pos)
        adjacent_cells = self.model.grid.get_neighborhood(
            self.pos, moore=self.moore, include_center=True, radius=UAV_OBSERVATION_RADIUS
        )
        # obtains each fire cell state, in a list (1 if its burning, 0 if it isn't)
        for cell in adjacent_cells:
            agents = self.model.grid.get_cell_list_contents([cell])
            for agent in agents:
                if type(agent) is Fire:
                    surrounding_states.append(int(agent.is_burning() is True))
        return surrounding_states

    # --- Feature 3 (base station): return-to-base, docking and re-launch --------

    def _rtb_trigger_level(self, berth: tuple[int, int]) -> float:
        """Battery at or below which this UAV must turn for home, from where it is.

        The max of a flat reserve (which carries the horizon constraint - the
        return has to FINISH inside the run) and a distance-aware term (which
        carries the fuel constraint - it has to be ABLE to get home from here).
        Neither alone is sufficient; see the derivation in common_fixed_variables.
        """
        per_move = float(self.battery_drain_per_step) + float(self.battery_drain_per_move)
        distance = abs(int(self.pos[0]) - berth[0]) + abs(int(self.pos[1]) - berth[1])
        return max(
            uav_return_to_base_reserve(),
            per_move * distance + base_station_return_margin(),
        )

    def _rtb_direction(self, berth: tuple[int, int], stalled: bool | None = None) -> int:
        """Greedy one-step direction toward the berth, with a stall sidestep.

        `stalled` defaults to None, meaning "work it out from rtb_last_pos as
        before", so every existing call site and test is unaffected. It is passed
        explicitly only by the stall recovery, which steers toward a DIFFERENT
        target and must not inherit a stall recorded against the berth.

        Deliberately re-implemented here rather than borrowing the executor's
        _direction_toward: this keeps agents.py free of a src_extension import,
        and _direction_toward returns the CURRENT direction once it is on target,
        which would walk a docked UAV straight back off the pad.
        """
        x, y = int(self.pos[0]), int(self.pos[1])
        dx, dy = berth[0] - x, berth[1] - y
        # move_x = [1, 0, -1, 0], move_y = [0, -1, 0, 1]
        x_dir = 0 if dx > 0 else (2 if dx < 0 else None)
        y_dir = 3 if dy > 0 else (1 if dy < 0 else None)
        if abs(dx) >= abs(dy):
            primary, secondary = x_dir, y_dir
        else:
            primary, secondary = y_dir, x_dir
        # A blocked move leaves the position unchanged; taking the other axis
        # breaks the deadlock a memoryless greedy steer would sit in forever.
        #
        # THE SIDESTEP CANNOT FIRE ON A PURE-AXIS APPROACH, and as of the dock-fix
        # round that is a DELIBERATE CHOICE rather than an unfixed defect - the
        # recovery lives one level up, in _apply_return_to_base. When dx == 0 (or
        # dy == 0) the corresponding direction is None, so `secondary` is None and
        # the swap below - which is GUARDED by `secondary is not None` and
        # therefore NEVER EXECUTES - is a no-op; `return primary` then re-issues
        # the same refused direction.
        # (The wording here used to say the swap put None in `primary` and the
        # function fell through to the `secondary` branch. That was wrong about
        # its own mechanism and right about the outcome, and it mattered: someone
        # "fixing the None" would have changed nothing at all. The same error is
        # in outputs/depotcost_report.txt section 5 and in the test docstring.)
        # The defect is SYMMETRIC - dy == 0 with dx != 0 has the identical shape -
        # and it is the TERMINAL CONDITION OF EVERY TRIP, not a corner case: the
        # cell before the berth differs from it in exactly one coordinate, so
        # every return leg ends on a pure-axis approach.
        #
        # THIS FUNCTION IS LEFT MEMORYLESS AND DISTANCE-MONOTONE ON PURPOSE.
        # Every successful move here reduces the manhattan distance to the berth
        # by exactly 1, and that is what bounds the number of moves on a leg and
        # makes a consecutive-stall counter a valid termination variant. Any
        # in-steer recovery must temporarily INCREASE the distance, and a
        # memoryless steer that does so is undone by its own next step - the
        # detour cell is closer-to-berth in the greedy sense the moment the UAV
        # stands on it, so the steer walks straight back and the pair cycles
        # forever. That was built, replayed and rejected; see
        # outputs/_df_sandbox.py rule R1. DO NOT ADD A DETOUR HERE.
        # MEASURED BEFORE THE FIX, at BASE_STATION_MODE = 2: all five "en route at
        # 240" legs are the same UAV stuck at (3,44), one cell outside the depot,
        # for 33 to 65 steps with 37-42 battery in hand. Note what that case is
        # NOT: its berth (3,46) is FREE and stays free - the cell between them
        # holds a permanently docked UAV, and at mode 2 a dock is forever. So a
        # trigger that asks "is my berth taken" is silent there for good, which is
        # why the terminator in _apply_return_to_base is keyed on this UAV'S OWN
        # PROGRESS instead. At mode 3 seven more episodes of 9 to 37 steps, one of
        # which ran to the horizon (dcB east/half/808).
        # BASE_STATION_MODE ships at 0, where none of this is reachable.
        # The recovery is _rtb_recovery_berth, called from _apply_return_to_base:
        # this function stays memoryless and is not the place for it.
        if stalled is None:
            stalled = self.rtb_last_pos is not None and self.rtb_last_pos == (x, y)
        if stalled and secondary is not None:
            primary, secondary = secondary, primary
        if primary is not None:
            return primary
        if secondary is not None:
            return secondary
        return int(self.selected_dir)

    def _rtb_inside_depot(self, cell: tuple[int, int]) -> bool:
        """Inside the depot this UAV is CURRENTLY RETURNING TO, not inside any.

        The docking fallback below parks a UAV on whatever depot cell it has
        reached when its own berth is blocked. Against the union of two depots
        that would let a UAV dock - and at mode 3 recharge and re-launch - inside
        a depot it was never flying to, roughly a grid width from where it meant
        to be. The depot index is passed through so the test is scoped to the
        latched target; with one depot it is depot 0 and the union, so this is
        the single-depot behaviour exactly.
        """
        contains = getattr(self.model, "base_station_contains", None)
        if not callable(contains):
            return False
        depot = self.rtb_target_depot
        if depot is None:
            return bool(contains(cell))
        try:
            return bool(contains(cell, depot))
        except TypeError:
            # A model that predates the depot-index parameter (a stand-in in the
            # tests, or an older checkout under --repo) still answers the union.
            return bool(contains(cell))

    def _rtb_select_berth(self) -> tuple[int, int] | None:
        """The nearest of this UAV's own berths, and the depot it belongs to.

        Ties break on the LOWEST DEPOT INDEX, which is ascending bit order, so the
        choice is a pure function of position and configuration. Sets
        rtb_target_berth / rtb_target_depot; the caller latches them for the trip.
        """
        berths = self.rtb_berths or ((self.rtb_berth,) if self.rtb_berth else ())
        if not berths or self.pos is None:
            return None
        x, y = int(self.pos[0]), int(self.pos[1])
        best_i, best_d = 0, None
        for i, b in enumerate(berths):
            if b is None:
                continue
            d = abs(x - int(b[0])) + abs(y - int(b[1]))
            if best_d is None or d < best_d:
                best_i, best_d = i, d
        if best_d is None:
            return None
        self.rtb_target_depot = best_i
        self.rtb_target_berth = (int(berths[best_i][0]), int(berths[best_i][1]))
        return self.rtb_target_berth

    def _rtb_berth_blocked(self, berth: tuple[int, int]) -> bool:
        """True when another UAV is standing on this UAV's berth.

        Only reached with BASE_STATION_DOCK_FIX = 0 now - it is the OFF-path
        predicate for the docking fallback, kept so the kill switch has something
        to switch back to, and used by the tests. Not dead code.
        """
        try:
            occupants = self.model.grid.get_cell_list_contents([berth])
        except Exception:
            return False
        return any(type(o) is UAV and o is not self for o in occupants)

    def _rtb_cell_free(self, cell: tuple[int, int]) -> bool:
        """The two tests move() itself applies, in the same order."""
        try:
            if self.model.grid.out_of_bounds(cell):
                return False
            return bool(self.not_UAV_adjacent(cell))
        except Exception:
            return False

    def _rtb_recovery_berth(self, here: tuple[int, int]):
        """The latched depot cell to steer to instead of the berth, or None.

        A return leg that stalls OUTSIDE its depot has no escape at all in the
        shipped code: the sidestep in _rtb_direction is structurally dead on a
        pure-axis approach (one delta is zero, so there is nothing to swap to),
        and the docking fallback is scoped to the depot interior. Every return leg
        ends on a pure-axis approach, so this is the terminal condition of every
        trip. Measured over the depot-cost and base-station artifacts: twelve
        episodes of 9 to 65 steps, five of them permanent.

        THE LATCH IS THE FIX, AND IT MUST OWN THE STEER ON EVERY STEP. A recovery
        that engages only on the steps where the UAV is stalled ping-pongs: the
        escape step moves the UAV, so on the NEXT step it is not stalled, the
        unmodified greedy toward the berth runs, and it walks straight back. With
        the target latched the steer is monotone toward a cell that does not move,
        so the reversal cannot happen. This is the same device the trip target
        already uses, and for the same stated reason (see rtb_target_berth).

        Re-latching happens only when there is no latch, when the latched cell has
        been reached, or when it has become occupied - NOT every step, or the
        target flips and the heading flips with it.

        Returns None - and the caller then steers to the berth exactly as at HEAD
        - when the fix is off, when the UAV is already inside its target depot,
        when the leg has not stalled long enough, or when there is no grid to
        consult (which is how the geometry unit tests drive the steer).
        """
        if base_station_dock_fix() < 2:
            return None
        if self._rtb_inside_depot(here):
            self.rtb_recovery_cell = None
            return None
        model = getattr(self, "model", None)
        grid = getattr(model, "grid", None)
        station = getattr(model, "base_station", None)
        if grid is None or not station:
            return None
        target = self.rtb_recovery_cell
        if target is not None and target != here and self._rtb_cell_free(target):
            return target
        if self.rtb_stall_steps < base_station_return_stall_limit():
            return None
        depot = 0 if self.rtb_target_depot is None else int(self.rtb_target_depot)
        depots = station.get("depots") or ()
        cells = (depots[depot]["cells"] if depot < len(depots)
                 else station.get("cells") or ())
        best = None
        for cell in sorted(cells):        # ties break on (x, y), so it is a pure
            if cell == here:              # function of position and occupancy and
                continue                  # cannot flip on a tie
            if not self._rtb_cell_free(cell):
                continue
            distance = abs(cell[0] - here[0]) + abs(cell[1] - here[1])
            if best is None or distance < best[0]:
                best = (distance, cell)
        self.rtb_recovery_cell = None if best is None else best[1]
        return self.rtb_recovery_cell

    def _apply_return_to_base(self) -> None:
        """Run before move(): trigger, steer, dock and re-launch.

        Called as the first statement of advance(), which is the last-writer-wins
        slot for selected_dir - the pre-move MAPE cycle has finished and
        _prepare_uav_directions_for_step has already early-returned without
        calling set_drone_dirs, so nothing between here and move() writes it.

        Both mechanisms share the trigger, the docking and the re-launch; only the
        steering differs. Mechanism 1 leaves the direction to the executor, which
        received the berth as a waypoint through the local path channel.
        """
        mode = base_station_mode()
        if mode < 2:
            return
        if self.rtb_berth is None or self.pos is None:
            return
        # While a trip is active the target is the LATCHED one; otherwise the
        # trigger is tested against the nearest berth from where the UAV is now.
        # With one depot both are rtb_berth and nothing here changes.
        berth = self.rtb_target_berth if self.rtb_active else None
        if berth is None:
            berth = self._rtb_select_berth() or self.rtb_berth

        step = int(getattr(self.model, "evaluation_timesteps_counter", 0))

        if self.rtb_docked:
            if mode >= 3 and self.battery_level >= base_station_recharge_release_level():
                self.rtb_docked = False
                self.rtb_active = False
                self.rtb_last_pos = None
                self.rtb_target_berth = None
                self.rtb_target_depot = None
                # Dock-fix round: per-TRIP state, cleared with the rest of it.
                self.rtb_stall_steps = 0
                self.rtb_recovery_cell = None
                self.rtb_recovery_steered = None
                self.rtb_cycles += 1
                if self.rtb_log:
                    self.rtb_log[-1]["released_step"] = step
                    self.rtb_log[-1]["released_level"] = float(self.battery_level)
                self.execution_action = "rtb_relaunch"
            return

        here = (int(self.pos[0]), int(self.pos[1]))
        if not self.rtb_active:
            if self.battery_level > self._rtb_trigger_level(berth):
                return
            self.rtb_active = True
            self.rtb_trips += 1
            # Dock-fix round: a new trip starts with no stall history and no
            # recovery latch. rtb_last_pos is left alone - it is cleared at the
            # relaunch, and on the very first trip it is None from __init__.
            self.rtb_stall_steps = 0
            self.rtb_recovery_cell = None
            self.rtb_recovery_steered = None
            # LATCH the target for the whole trip. rtb_target_* were set by the
            # trigger test above; freezing them here is what stops a UAV that is
            # equidistant from two depots flipping its destination each step.
            self.rtb_target_berth = (int(berth[0]), int(berth[1]))
            self.rtb_log.append({
                "trigger_step": step,
                "trigger_level": float(self.battery_level),
                "trigger_distance": abs(here[0] - berth[0]) + abs(here[1] - berth[1]),
                # Depot-cost round: WHICH depot this trip aimed at. Without it the
                # instrument cannot attribute a return leg to a depot, which is
                # the whole point of a multi-depot arm. Inside the per-trip record
                # rather than in rtb_counters, because rtb_counters is populated at
                # every mode and a new key there would drift the mode-0 baseline.
                "target_depot": (0 if self.rtb_target_depot is None
                                 else int(self.rtb_target_depot)),
                "target_berth": [int(berth[0]), int(berth[1])],
                "home_depot": int(self.rtb_home_depot),
                "arrival_step": None,
                "arrival_level": None,
                "dock_cell": None,
                "released_step": None,
                "released_level": None,
            })

        # Dock at the assigned berth, or - if some OTHER UAV happens to be
        # standing on it - on whatever depot cell this UAV has already reached.
        # Berths are distinct, so no two returning UAVs contend; but a UAV that is
        # not returning can be parked on someone else's berth, and without this
        # fallback the returning UAV would oscillate against not_UAV_adjacent
        # until the blocker happened to move. This guarantees the return
        # terminates, which is what "no UAV stranded" actually requires.
        # THE STALL WITNESS. rtb_last_pos is this leg's position at the previous
        # step, so `== here` means last step's move was refused. Any successful
        # move resets the count. Recorded here, above the mechanism gate below, so
        # it is maintained under BOTH return mechanisms - the docking block runs
        # for both, and rtb_last_pos alone would never be set under mechanism 1.
        if base_station_dock_fix() >= 1:
            if self.rtb_last_pos is not None and self.rtb_last_pos == here:
                self.rtb_stall_steps += 1
            else:
                self.rtb_stall_steps = 0

        # Dock at the assigned berth, or - once this leg has provably STOPPED
        # MOVING - on the depot cell it is standing on.
        #
        # THE FALLBACK IS KEPT, and it is load-bearing. Without it a returning UAV
        # whose approach is blocked has no recovery at all, and the blocker can be
        # permanently immovable: at mode 2 the release branch above is
        # unreachable, so every dock is forever, and a RELEASED UAV is not obliged
        # to leave its berth either (dcB east/half/808, where 2502 held (4,45)
        # from step 216 to the horizon, head-on with 2503). "Wait for the blocker
        # to move" is not a terminating strategy. There is a recorded
        # configuration (dcA south/half/808) in which deleting this block
        # deadlocks two UAVs to the horizon.
        #
        # WHAT WAS WRONG WITH IT WAS THE TRIGGER, NOT THE FALLBACK. It fired on an
        # INSTANT of occupancy, and all UAV work runs in advance() where
        # grid.move_agent mutates the live grid mid-sweep, so a ONE-STEP TRANSIT
        # by an earlier-ordered UAV was enough to re-assign a berth permanently -
        # 34 fallback docks on disk, 7 of them onto another UAV's berth, one of
        # which stranded a third UAV for 37 steps. And it was SILENT where it was
        # needed most: it asked "is my berth taken", so a UAV boxed in with a FREE
        # berth never fired it at all, which is every one of the five mode-2
        # strandings.
        #
        # RE-KEYED to consecutive refused steps: a property of this UAV's own
        # progress and of no other agent's future behaviour, which is the
        # guarantee this block exists to provide. A one-step transit produces at
        # most ONE refused step and so cannot reach the limit by construction.
        #
        # THE DOCK CELL IS DELIBERATELY NOT WIDENED BEYOND THE DEPOT INTERIOR.
        # _update_battery_after_step gates the recharge on rtb_docked ALONE with
        # no positional test, and the harness derives base_state from the same
        # flag, so a dock on the doorstep would refuel a UAV on open ground AND
        # relabel it from "returning" to "charging" - clearing the stranding gate
        # without the UAV ever coming home. See outputs/dockfix_part1.txt 5b.
        docking = here == berth
        if not docking and self._rtb_inside_depot(here):
            if base_station_dock_fix() >= 1:
                docking = self.rtb_stall_steps >= base_station_return_stall_limit()
            else:
                docking = self._rtb_berth_blocked(berth)
        if docking:
            self.rtb_docked = True
            # Dock-fix round: the leg is over, so the recovery latch goes with it.
            # A docked UAV never moves, so leaving rtb_stall_steps to climb would
            # be meaningless; it is reset here and at the trigger.
            self.rtb_stall_steps = 0
            self.rtb_recovery_cell = None
            self.rtb_recovery_steered = None
            self.execution_action = "rtb_docked"
            if self.rtb_log:
                self.rtb_log[-1]["arrival_step"] = step
                self.rtb_log[-1]["arrival_level"] = float(self.battery_level)
                self.rtb_log[-1]["dock_cell"] = here
            return

        self.rtb_return_steps += 1
        if base_station_return_mechanism() != 2:
            # Planner route: the executor already committed a direction from the
            # base waypoint. Overriding it here would mask the mechanism entirely.
            return
        recovery = self._rtb_recovery_berth(here)
        if recovery is not None:
            # Steer to the LATCHED cell, not the berth, and keep doing so on every
            # step until the depot is reached. The stall is relative to a target -
            # the swap breaks a deadlock against the cell we were refused moving
            # toward - so it is only carried over when the target is unchanged.
            direction = self._rtb_direction(
                recovery,
                (self.rtb_recovery_steered == recovery
                 and self.rtb_last_pos is not None
                 and self.rtb_last_pos == here),
            )
            self.rtb_recovery_steered = recovery
        else:
            direction = self._rtb_direction(berth)
            self.rtb_recovery_steered = None
        self.rtb_last_pos = (int(self.pos[0]), int(self.pos[1]))
        self.selected_dir = direction
        self.execution_direction_applied = True
        self.execution_action = "rtb_return"

    # function for moving UAV over the grid area
    def move(self):
        # vectors for moving to different positions, based on 4 directions = [0, 1, 2, 3] = [right, down, left, up].
        # For example, if direction 1 is chosen, then the UAV moves 0 cells in x-axis, and -1 cell in y-axis
        move_x = [1, 0, -1, 0]
        move_y = [0, -1, 0, 1]
        moved = False

        # Feature 3: a docked UAV holds its berth. This has to sit above the
        # pipeline check below, because there is no "stay" action anywhere in the
        # model - all four selected_dir values are moves, and even the executor's
        # own hold commits a direction and walks the agent off the pad.
        if self.rtb_docked:
            self.execution_action = "rtb_docked_hold"
            return False

        pipeline_active = False
        try:
            pipeline_active = bool(
                getattr(self.model, "_is_extension_pipeline_active", lambda: False)()
            )
        except Exception:
            pipeline_active = False
        if pipeline_active and not getattr(self, "execution_direction_applied", False):
            self.execution_action = "no_managed_direction_hold"
            return False

        # it calculates the position the corresponding UAV will move to
        pos_to_move = (self.pos[0] + move_x[self.selected_dir], self.pos[1] + move_y[self.selected_dir])
        # checks if the position to move is inside the grid bounds, and that the UAV doesn't have other UAV nearby. If
        # so, the UAV moves
        if not self.model.grid.out_of_bounds(pos_to_move) and self.not_UAV_adjacent(pos_to_move):
            self.model.grid.move_agent(self, tuple(pos_to_move))
            moved = True

        return moved

    # Mesa framework native method, which is overwritten, necessary for executing changes made in step() method
    # (as it can be seen, in this case UAVs don't need to update anything in step() method, so it isn't overwritten).
    def advance(self):
        self._apply_return_to_base()
        move_x = [1, 0, -1, 0]
        move_y = [0, -1, 0, 1]
        current_time = float(self.model.evaluation_timesteps_counter)
        pos_before = self.pos
        intended_delta = (move_x[self.selected_dir], move_y[self.selected_dir])
        moved = self.move()
        self._update_battery_after_step(moved)
        if self.local_monitor is not None:
            self.local_monitor.finalize_step_after_move(
                self, pos_before, self.pos, intended_delta
            )
            self.latest_local_observation = self.local_monitor.collect_observation(
                self, current_time
            )
            buf = getattr(self.model, "monitoring_buffer", None)
            if buf is not None:
                buf.add_local_observation(str(self.unique_id), self.latest_local_observation)


def victim_flee_trigger_distance() -> int:
    """Feature 2 trigger radius; <= 0 disables the feature entirely.

    Read from the `cfv` module rather than the star-imported copy, and read at
    call time. `apply_scenario_config` sets attributes on common_fixed_variables
    and wildfire_model but NOT on this module, so a per-run override - the
    kill-switch arm included - is only visible through `cfv`.
    """
    try:
        return int(getattr(cfv, "VICTIM_FLEE_TRIGGER_DISTANCE", 0))
    except (TypeError, ValueError):
        return 0


def victim_flee_max_displacement() -> int:
    """Feature 2 leash from the spawn cell, in manhattan cells."""
    try:
        return max(0, int(getattr(cfv, "VICTIM_FLEE_MAX_DISPLACEMENT", 0)))
    except (TypeError, ValueError):
        return 0


# --- Feature 3 (base station) configuration -----------------------------------
# Every one of these reads the `cfv` MODULE at call time, for the same reason
# victim_flee_trigger_distance does: apply_scenario_config sets attributes on
# common_fixed_variables and wildfire_model but NOT on this module, so a per-run
# override - the kill-switch arm included - is only visible through `cfv`. A
# module-level constant or a star-imported name would freeze at import and the
# switch would be silently inert, which is the dead-input defect this repo has
# already hit nine times.

def base_station_mode() -> int:
    """0 off (kill switch) / 1 spawn / 2 +return-to-base / 3 +recharge."""
    try:
        return max(0, min(3, int(getattr(cfv, "BASE_STATION_MODE", 0))))
    except (TypeError, ValueError):
        return 0


def base_station_return_mechanism() -> int:
    """1 = through the planner (fire-aware), 2 = hardcoded in advance() (fire-blind)."""
    try:
        value = int(getattr(cfv, "BASE_STATION_RETURN_MECHANISM", 2))
    except (TypeError, ValueError):
        return 2
    return value if value in (1, 2) else 2


def base_station_size() -> int:
    """Depot footprint edge length, in cells."""
    try:
        return max(1, int(getattr(cfv, "BASE_STATION_SIZE", 5)))
    except (TypeError, ValueError):
        return 5


def base_station_corner() -> int:
    """0 NW (default) / 1 NE / 2 SW / 3 SE. Numeric, so --set never has to carry a string."""
    try:
        value = int(getattr(cfv, "BASE_STATION_CORNER", 0))
    except (TypeError, ValueError):
        return 0
    return value if value in (0, 1, 2, 3) else 0


# Depot anchors, in ASCENDING BIT ORDER. The bit order IS the depot order, so
# depot 0 is the first set bit and the set is deterministic. Kept beside the corner
# accessor because it is the same coordinate convention: x is the HEIGHT axis and
# y is the WIDTH axis.
BASE_STATION_ANCHOR_BITS = ((1, "NW"), (2, "NE"), (4, "SW"), (8, "SE"), (16, "CENTRAL"))
BASE_STATION_DEPOTS_MAX = 31


def base_station_depots() -> int:
    """Bitmask over the five depot anchors; 0 = one depot at BASE_STATION_CORNER.

    RAISES on an unrecognised value instead of falling back. base_station_corner()
    maps anything outside 0..3 to NW silently, and a silent fallback here would run
    a two-depot arm as a one-depot arm - the wave would measure the wrong thing
    with no error anywhere, which is this repo's recorded dead-input defect class.
    """
    raw = getattr(cfv, "BASE_STATION_DEPOTS", 0)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(
            "BASE_STATION_DEPOTS must be an int bitmask in 0..%d, got %r"
            % (BASE_STATION_DEPOTS_MAX, raw)
        ) from None
    if not 0 <= value <= BASE_STATION_DEPOTS_MAX:
        raise ValueError(
            "BASE_STATION_DEPOTS must be a bitmask in 0..%d (NW 1, NE 2, SW 4, "
            "SE 8, CENTRAL 16), got %d" % (BASE_STATION_DEPOTS_MAX, value)
        )
    return value


def base_station_spawn_split() -> int:
    """0 all at depot 0 / 1 alternate by index / 2 partition-nearest searchers."""
    try:
        value = int(getattr(cfv, "BASE_STATION_SPAWN_SPLIT", 0))
    except (TypeError, ValueError):
        return 0
    return value if value in (0, 1, 2) else 0


def base_station_spawn_firefighters() -> bool:
    """False keeps firefighters on their ring while UAVs still spawn at the depot."""
    try:
        return bool(int(getattr(cfv, "BASE_STATION_SPAWN_FIREFIGHTERS", 1)))
    except (TypeError, ValueError):
        return True


def uav_return_to_base_reserve() -> float:
    """Flat battery reserve that triggers a return; see the derivation in cfv."""
    try:
        return float(getattr(cfv, "UAV_RETURN_TO_BASE_RESERVE", 60.0))
    except (TypeError, ValueError):
        return 60.0


def base_station_return_margin() -> float:
    """Points kept in hand on top of the distance-aware term."""
    try:
        return float(getattr(cfv, "BASE_STATION_RETURN_MARGIN", 5.0))
    except (TypeError, ValueError):
        return 5.0


def base_station_recharge_per_step() -> float:
    """Battery points added per step while docked, before the existing clamp."""
    try:
        return max(0.0, float(getattr(cfv, "BASE_STATION_RECHARGE_PER_STEP", 5.0)))
    except (TypeError, ValueError):
        return 5.0


def base_station_recharge_release_level() -> float:
    """Level at which a docked UAV re-launches. Full charge avoids threshold chatter."""
    try:
        return float(getattr(cfv, "BASE_STATION_RECHARGE_RELEASE_LEVEL", 100.0))
    except (TypeError, ValueError):
        return 100.0


def base_station_dock_fix() -> int:
    """0 off (kill switch) / 1 re-keyed docking fallback / 2 + stall recovery."""
    try:
        return max(0, min(2, int(getattr(cfv, "BASE_STATION_DOCK_FIX", 2))))
    except (TypeError, ValueError):
        return 2


def base_station_return_stall_limit() -> int:
    """Consecutive refused steps before a return leg counts as stalled."""
    try:
        return max(1, int(getattr(cfv, "BASE_STATION_RETURN_STALL_LIMIT", 3)))
    except (TypeError, ValueError):
        return 3


def base_station_waypoint_fix() -> bool:
    """True when the mechanism-1 waypoint publishes the LATCHED berth."""
    try:
        return int(getattr(cfv, "BASE_STATION_WAYPOINT_FIX", 1)) != 0
    except (TypeError, ValueError):
        return True


# Orthogonal offsets in a FIXED order for the victim's flee scan. The same four
# offsets in the same order are hardcoded in `Firefighter._neighbor_cells`; that
# copy is deliberately left alone so the firefighter's approach path stays
# byte-identical with the feature off. Movement here is 4-connected for the same
# reason firefighter movement is: every distance and reachability computation in
# the rescue subsystem is manhattan / 4-connected, and a victim that could cut a
# corner a firefighter cannot would be inconsistent with all of them. The order
# is also the flee rule's last tie-break, which is what makes it deterministic.
ORTHOGONAL_OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1))

VICTIM_TERMINAL_STATUSES = ("dead", "rescued")


class Victim(mesa.Agent):
    """Victim marker that steps away from approaching fire (feature 2).

    Was a display-only marker with no-op step/advance. It now runs the flee rule
    described in outputs/victimmove_part1.txt section 1.2.2: hold until fire is
    within the trigger radius, then take the orthogonal step that maximises
    distance from the nearest burning cell, bounded by a leash to the spawn cell.
    """

    def __init__(self, unique_id, model, victim_id: str, position: tuple):
        super().__init__(unique_id, model)
        self.victim_id = victim_id
        self.status = "candidate"
        self.marker_only = True
        # Feature 2: the constructor used to accept `position` and discard it,
        # so the class had no memory of where it started. This is the same
        # rounded cell `_init_managed_victims` places the marker on.
        #
        # Two separate things, deliberately. `spawn_cell` is IMMUTABLE and is
        # what every report means by "displacement from spawn". `leash_anchor`
        # is what the leash is actually measured against, and it RE-ANCHORS when
        # the victim reaches safety - the firefighter's `_idle_retreat_origin`
        # has exactly this renewable semantics and the victim's did not, which
        # is what pinned a fleeing victim inside a permanent diamond around its
        # spawn while the front, which has no leash, kept coming.
        self.spawn_cell = self._round_cell(position)
        self.leash_anchor = self.spawn_cell
        self.leash_reanchors = 0

    @staticmethod
    def _round_cell(position) -> tuple[int, int] | None:
        try:
            return (
                int(round(float(position[0]))),
                int(round(float(position[1]))),
            )
        except (TypeError, ValueError, IndexError):
            return None

    def step(self):
        pass

    def advance(self):
        self._flee_approaching_fire()

    # ------------------------------------------------------------------
    # Feature 2: move away from approaching fire
    # ------------------------------------------------------------------
    def _flee_approaching_fire(self) -> None:
        """One deterministic step away from fire, or hold. Draws from no RNG.

        Ordering makes this work and is not incidental: mesa's
        SimultaneousActivation advances agents in insertion order - Fire, UAV,
        Victim, Firefighter - so by the time this runs the fire has already
        committed THIS step's burning state, and `_check_fire_casualties` has
        not yet run (it is in the post-move cycle). A victim whose own cell
        ignites this step can therefore still step off it and be alive when the
        casualty sweep looks.
        """
        trigger = victim_flee_trigger_distance()
        if trigger <= 0:
            return  # G1 kill switch: advance() is a no-op, as it always was
        if self.pos is None:
            return  # G2
        if str(getattr(self, "status", "") or "").strip().lower() in (
            VICTIM_TERMINAL_STATUSES
        ):
            # G3. `_check_fire_casualties` does NOT remove a dead victim from
            # the grid or the scheduler, so advance() keeps being called for
            # corpses; this guard is mandatory, not defensive. The skip set is
            # deliberately identical to that sweep's, so the set of victims that
            # can MOVE is exactly the set that can DIE - an "unreachable" or
            # "cancelled" victim is still alive and still flees.
            return
        if self._in_firefighter_custody():
            return  # G4
        fire_cells = self._burning_cells()
        if not fire_cells:
            # Nothing is burning anywhere: the safest state there is, so the
            # leash re-centres here (guard 2).
            self._reanchor_leash()
            return  # G5

        cell = (int(self.pos[0]), int(self.pos[1]))
        dist_before = self._min_fire_distance(cell, fire_cells)
        if dist_before > trigger:
            # R2: fire is not close enough to be worth moving for. This is the
            # victim's "safe standoff", and reaching it RE-ANCHORS THE LEASH
            # (guard 2) exactly as the firefighter's does. Same threshold as the
            # trigger, so no new constant enters the model, and the number
            # matches the firefighter's ideal standoff of BUFFER + 1 = 4.
            self._reanchor_leash()
            return

        leash = victim_flee_max_displacement()
        anchor = (
            getattr(self, "leash_anchor", None)
            or getattr(self, "spawn_cell", None)
            or cell
        )
        grid = self.model.grid
        candidates: list[tuple[int, int, int, tuple[int, int], bool]] = []
        leash_blocked = 0
        for order, (off_x, off_y) in enumerate(ORTHOGONAL_OFFSETS):
            ncell = (cell[0] + off_x, cell[1] + off_y)
            if grid.out_of_bounds(ncell):
                continue
            if ncell in fire_cells:
                continue
            from_anchor = abs(ncell[0] - anchor[0]) + abs(ncell[1] - anchor[1])
            if from_anchor > leash:
                leash_blocked += 1
                continue
            candidates.append(
                (
                    self._min_fire_distance(ncell, fire_cells),
                    from_anchor,
                    order,
                    ncell,
                    self._cell_has_onward_exit(ncell, cell, fire_cells),
                )
            )
        if not candidates:
            # R4: boxed in - surrounded, at the grid edge, or out of leash.
            self._note_flee_hold("no_candidate", leash_removed=leash_blocked > 0)
            return

        # R4b DEAD-END AVOIDANCE. Greedy distance-maximising is exactly what walks
        # an agent into a pocket: a cell can be locally further from the nearest
        # flame while the front closes around it. So PREFER a destination that
        # still has somewhere to go next step. This is a preference, not a filter:
        # when every reachable cell is a dead end, the victim still takes the best
        # of them rather than freezing in the open.
        #
        # MEASURED INERT AT 50x50 (guard-1 attribution, Feature 2): fired 3 times
        # in 13 runs, zero outcome changes, and every firing was the one case its
        # geometry can reach here - a victim standing IN fire choosing among escape
        # cells tied at distance 1. KEPT DELIBERATELY pending evaluation on a
        # larger grid, where the pockets it was designed for can form.
        with_exit = [item for item in candidates if item[4]]
        pool = with_exit if with_exit else candidates

        # R5: furthest from fire wins; ties go to the cell nearer the anchor,
        # then to the fixed offset order. A total order, so no RNG and no
        # arbitrary choice.
        dist_after, _from_anchor, _order, target, _has_exit = min(
            pool, key=lambda c: (-c[0], c[1], c[2])
        )

        # R6: a step must genuinely buy distance. The "standing in fire" case
        # needs no separate branch: candidates exclude burning cells, so every
        # candidate is at distance >= 1, which already beats dist_before == 0.
        if dist_after <= dist_before:
            # Instrumented, because whether a LATERAL step should be allowed
            # here is an open question and deserves a measurement rather than an
            # assertion. `lateral_available` marks the holds a lateral rule
            # would actually change; `leash_removed` marks the ones where the
            # leash had already discarded a candidate.
            self._note_flee_hold(
                "no_improvement",
                lateral_available=any(item[0] == dist_before for item in pool),
                leash_removed=leash_blocked > 0,
            )
            return

        self.model.grid.move_agent(self, target)
        recorder = getattr(self.model, "_record_victim_flee", None)
        if callable(recorder):
            recorder(self, cell, target, dist_before, dist_after, anchor)

    def _reanchor_leash(self) -> None:
        """Guard 2: re-centre the leash on the current cell once the victim is safe.

        The victim's leash was measured against `spawn_cell`, which has exactly
        one writer in the whole tree and is never reassigned - so a victim was
        confined to a permanent diamond around where it spawned, while the fire
        front, which has no leash, kept coming. When the front arrives FROM the
        spawn side the leash therefore stops the victim escaping rather than
        bounding a manoeuvre. The firefighter's `_idle_retreat_origin` never had
        that problem: it re-anchors whenever the unit reaches safety, which makes
        its budget renewable. This gives the victim the same property.

        SCOPE: THIS TOUCHES EXACTLY ONE FIELD, AND THAT IS DELIBERATE. The
        firefighter's two re-anchor sites also null `_idle_retreat_last_cell`,
        its anti-oscillation memory - the reset hole diagnosed in 93f23b7
        (verdict B, real but inert, left documented because the obvious fix is a
        provable no-op given both sites clear it). A leash re-anchor has no
        business discarding oscillation history, so the INTENDED behaviour is
        mirrored here and the hole is not inherited. The victim rule keeps no
        such memory today; this method is written so that if one is ever added,
        re-anchoring will still not wipe it.

        `spawn_cell` stays immutable so that every report continues to mean the
        true spawn by "displacement from spawn".
        """
        if self.pos is None:
            return
        cell = (int(self.pos[0]), int(self.pos[1]))
        if getattr(self, "leash_anchor", None) == cell:
            return
        self.leash_anchor = cell
        self.leash_reanchors = int(getattr(self, "leash_reanchors", 0) or 0) + 1

    def _note_flee_hold(self, reason: str, **flags: bool) -> None:
        """Count why a triggered victim held instead of moving. Observation only.

        Cheap counters on the model, read by the validation harness. Nothing in
        the simulation reads them back.
        """
        model = getattr(self, "model", None)
        if model is None:
            return
        counts = getattr(model, "victim_flee_hold_counts", None)
        if not isinstance(counts, dict):
            counts = {}
            try:
                model.victim_flee_hold_counts = counts
            except Exception:
                return
        counts[reason] = int(counts.get(reason, 0) or 0) + 1
        for name, flag in flags.items():
            if not flag:
                continue
            key = "%s.%s" % (reason, name)
            counts[key] = int(counts.get(key, 0) or 0) + 1

    def _cell_has_onward_exit(
        self,
        ncell: tuple[int, int],
        from_cell: tuple[int, int],
        fire_cells: set[tuple[int, int]],
    ) -> bool:
        """One-step lookahead: would the victim still have somewhere to go?

        True when `ncell` has at least one orthogonal neighbour that is in
        bounds and not burning, NOT COUNTING the cell being vacated.

        Excluding `from_cell` is what gives the test any content. Counting it
        would make the answer True for every candidate whenever the victim is
        not already standing in fire, since the cell it is leaving is by
        definition non-burning then - the guard would be vacuous exactly in the
        common case it exists to cover.

        Deliberately NOT leash-aware: it asks whether the cell is a physical
        pocket, which is what "dead end" means here. A cell whose only onward
        exits sit outside the leash is a pocket for this victim specifically,
        and folding that in would couple this guard to the anchor rule; that is
        left open pending the second guard.
        """
        grid = self.model.grid
        for off_x, off_y in ORTHOGONAL_OFFSETS:
            onward = (ncell[0] + off_x, ncell[1] + off_y)
            if onward == from_cell:
                continue
            if grid.out_of_bounds(onward):
                continue
            if onward in fire_cells:
                continue
            return True
        return False

    def _in_firefighter_custody(self) -> bool:
        """True once a firefighter has this victim - carrying it, or on its cell.

        Both clauses are required. `exiting` alone leaves a one-step hole on the
        arrival step: victims advance BEFORE firefighters, so at the step a unit
        sets `exiting` the flag is still False while the unit is already
        standing on the victim. Without the co-location clause the victim would
        step away first and the carry would then teleport it back. Co-location
        is also the requirement's own stopping condition - the victim moves
        "until it be found", and a firefighter on its cell has found it.

        Feature 1's off-grid units carry pos None, which compares unequal to any
        cell, so they need no special case here.
        """
        markers = getattr(self.model, "firefighter_marker_agents", None)
        if not isinstance(markers, dict):
            return False
        for ff_marker in markers.values():
            if getattr(ff_marker, "rescued_victim", None) is not self:
                continue
            if getattr(ff_marker, "dead", False):
                # A casualty keeps its `rescued_victim` binding until an
                # unassign clears it, and `exiting` is not reset on death. A
                # corpse must not hold a live victim in place; the recall paths
                # will unassign it. (In practice a unit that dies carrying dies
                # on the victim's own cell, so the victim dies in the same
                # sweep - but the invariant should not depend on that.)
                continue
            if getattr(ff_marker, "exiting", False):
                return True
            if getattr(ff_marker, "pos", None) == self.pos:
                return True
        return False

    def _burning_cells(self) -> set[tuple[int, int]]:
        """Actively burning cells. Same construction as Firefighter._fire_cells."""
        cells: set[tuple[int, int]] = set()
        for agent in self.model.schedule.agents:
            if type(agent) is not Fire:
                continue
            if not agent.is_burning():
                continue
            pos = getattr(agent, "pos", None)
            if pos is not None:
                cells.add((int(pos[0]), int(pos[1])))
        return cells

    @staticmethod
    def _min_fire_distance(
        cell: tuple[int, int], fire_cells: set[tuple[int, int]]
    ) -> int:
        if not fire_cells:
            return 999
        cx, cy = cell
        return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fire_cells)


IDLE_RETREAT_SAFETY_BUFFER = 3
IDLE_RETREAT_MAX_CELLS = 6


class Firefighter(mesa.Agent):
    """Firefighter marker that moves to victim and exits at boundary."""

    def __init__(self, unique_id, model, unit_id: str, position: tuple):
        super().__init__(unique_id, model)
        self.unit_id = unit_id
        self.dead = False
        self.status = "available"
        self.assigned = False
        self.marker_only = False
        self.target_pos = None
        self.rescued_victim = None
        self.exiting = False
        self.exit_target = None
        self.rescue_completed = False
        # Rescue-absence state (feature 1): while off_grid the unit has pos None
        # (advance() is a no-op), stays scheduled, and is re-placed by the model
        # in the post-move cycle of absent_until_step.
        self.off_grid = False
        self.absent_until_step = None
        self.absence_exit_cell = None
        self._idle_retreat_origin = None
        self._idle_retreat_steps = 0
        self._idle_retreat_stalled = False
        self._idle_retreat_last_cell = None
        self.movement_reason: dict | None = None
        self._last_move_tier = 0
        self._last_move_risk = 0

    def _record_movement_reason(
        self, category: str, reason: str, **factors: object,
    ) -> None:
        fine_cat = str(category)
        notable_cat = notable_firefighter_movement_category(fine_cat)
        key_factors = {str(k): v for k, v in factors.items()}
        prev_key = str(getattr(self, "_movement_last_transition_key", "") or "")
        transition_key = movement_transition_key(
            "firefighter", notable_cat, key_factors,
        )
        prev_notable = str(getattr(self, "_movement_last_notable_category", "") or "")
        self.movement_reason = {
            "category": notable_cat,
            "fine_category": fine_cat,
            "prev_category": prev_notable,
            "reason": str(reason),
            "key_factors": key_factors,
        }
        self._movement_last_notable_category = notable_cat
        if transition_key != prev_key:
            model = getattr(self, "model", None)
            if model is not None:
                log = getattr(model, "_movement_transition_log", None)
                if not isinstance(log, list):
                    log = []
                    model._movement_transition_log = log
                step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
                log.append(
                    {
                        "step": step,
                        "agent_kind": "firefighter",
                        "source_module": "firefighter_move",
                        "target_id": str(
                            getattr(self, "unit_id", getattr(self, "unique_id", ""))
                        ),
                        "category": notable_cat,
                        "fine_category": fine_cat,
                        "prev_category": prev_notable,
                        "transition_key": transition_key,
                        "reason": str(reason),
                        "key_factors": dict(key_factors),
                    }
                )
            self._movement_last_transition_key = transition_key

    def _assigned_victim_label(self) -> str:
        rv = getattr(self, "rescued_victim", None)
        if rv is not None:
            return str(getattr(rv, "unique_id", getattr(rv, "unit_id", "victim")))
        return "victim"

    def step(self):
        pass

    def _refresh_target_from_victim(self) -> None:
        """Track a moving victim (feature 2): re-read the bound victim's cell.

        `target_pos` is written once by the executor at assign
        (wildfire_model.apply_physical_rescue_command) and nothing ever
        refreshed it. That was harmless while victims never moved. With feature
        2 the unit would otherwise walk to a cell the victim has left, find
        `self.pos == self.target_pos` against empty ground, flip to `exiting`,
        and TELEPORT the victim to itself on the first carry step - a completed
        rescue with no contact ever made.

        This is a movement waypoint, not assignment state: it never changes
        WHICH victim the unit is bound to, only where that same victim now is.
        The executor keeps sole authority over `assigned`, `rescued_victim` and
        `status`, and `_assert_no_direct_rescue_mutation` is untouched. advance()
        already writes state of exactly this class - `exiting`, `exit_target`,
        and `status` via `_mark_route_blocked`.

        Skipped entirely when the feature is off, so the pre-feature approach
        path runs literally.
        """
        if victim_flee_trigger_distance() <= 0:
            return
        if self.exiting or not self.target_pos:
            return
        victim = getattr(self, "rescued_victim", None)
        if victim is None:
            return
        if str(getattr(victim, "status", "") or "").strip().lower() in (
            VICTIM_TERMINAL_STATUSES
        ):
            # Do not chase a corpse to a new cell: leave the target where it was
            # and let the existing victim_dead recall path unassign this unit.
            return
        pos = getattr(victim, "pos", None)
        if pos is None:
            return
        cell = (int(pos[0]), int(pos[1]))
        if cell != self.target_pos:
            self.target_pos = cell

    def advance(self):
        if self.pos is None or getattr(self, "dead", False):
            return
        # Before any branch reads self.target_pos - the survival-retreat path
        # walks toward it too, not just the approach path below.
        self._refresh_target_from_victim()
        recorded = False
        if self._needs_immediate_survival_retreat():
            before_pos = self.pos
            cell = (int(before_pos[0]), int(before_pos[1]))
            fire_cells = self._fire_cells()
            nearest = self._min_fire_distance(cell, fire_cells)
            smoke = self._cell_has_active_smoke(cell)
            on_fire = self._cell_contains_active_fire(cell)
            self._survival_move()
            if (
                self.target_pos
                and not self.exiting
                and self.pos == before_pos
            ):
                self._move_toward(self.target_pos)
                self._record_movement_reason(
                    "moving_to_victim",
                    (
                        f"moving to assigned victim {self._assigned_victim_label()} "
                        f"at {self.target_pos} while avoiding hazard "
                        f"(risk tier {self._last_move_tier})"
                    ),
                    nearest_fire_dist=nearest,
                    smoke="yes" if smoke else "no",
                    risk_tier=self._last_move_tier,
                    target_pos=self.target_pos,
                )
            else:
                self._record_movement_reason(
                    "survival_retreat",
                    (
                        f"retreated from fire/smoke: nearest-fire dist {nearest}, "
                        f"smoke={'yes' if smoke else 'no'}"
                    ),
                    nearest_fire_dist=nearest,
                    smoke="yes" if smoke else "no",
                    on_fire=on_fire,
                )
            return
        if self.target_pos and not self.exiting:
            if self.pos == self.target_pos:
                self.exiting = True
                H = getattr(self.model, "HEIGHT", 50)
                W = getattr(self.model, "WIDTH", 50)
                x, y = self.pos
                dists = {
                    (0, y): x,
                    (H - 1, y): H - 1 - x,
                    (x, 0): y,
                    (x, W - 1): W - 1 - y,
                }
                self.exit_target = min(dists, key=dists.get)
                self._record_movement_reason(
                    "exiting_setup",
                    (
                        f"arrived at victim {self._assigned_victim_label()}, "
                        f"exiting toward boundary {self.exit_target}"
                    ),
                    victim_pos=self.target_pos,
                    exit_target=self.exit_target,
                )
                recorded = True
            else:
                self._move_toward(self.target_pos)
                cell = (int(self.pos[0]), int(self.pos[1]))
                self._record_movement_reason(
                    "moving_to_victim",
                    (
                        f"moving to assigned victim {self._assigned_victim_label()} "
                        f"at {self.target_pos}, avoiding fire "
                        f"(chosen step risk tier {self._last_move_tier})"
                    ),
                    nearest_fire_dist=self._min_fire_distance(cell, self._fire_cells()),
                    risk_tier=self._last_move_tier,
                    target_pos=self.target_pos,
                )
                recorded = True
        elif self.exiting and self.exit_target:
            if self.pos == self.exit_target:
                if not hasattr(self.model, "_agents_pending_removal"):
                    self.model._agents_pending_removal = []
                self.model._agents_pending_removal.append(self)
                if self.rescued_victim is not None:
                    self.model._agents_pending_removal.append(
                        self.rescued_victim
                    )
                self.rescue_completed = True
                self.model._rescue_path_clear_requested = True
                print(
                    f"[Rescue Complete] FF-{self.unit_id} exited with victim"
                )
                self._record_movement_reason(
                    "exiting_complete",
                    "carrying rescued victim to boundary (exit complete)",
                    exit_target=self.exit_target,
                )
                recorded = True
            else:
                self._move_toward(self.exit_target)
                if self.rescued_victim is not None:
                    try:
                        self.model.grid.move_agent(
                            self.rescued_victim, self.pos
                        )
                    except Exception:
                        pass
                self._record_movement_reason(
                    "exiting_with_victim",
                    f"carrying rescued victim to boundary {self.exit_target}",
                    exit_target=self.exit_target,
                    risk_tier=self._last_move_tier,
                )
                recorded = True
        elif self._idle_needs_survival_move():
            cell = (int(self.pos[0]), int(self.pos[1]))
            fire_cells = self._fire_cells()
            nearest = self._min_fire_distance(cell, fire_cells)
            smoke = self._cell_has_active_smoke(cell)
            self._survival_move()
            self._record_movement_reason(
                "idle_retreat",
                (
                    f"relocating: fire approaching (nearest-fire dist {nearest}, "
                    f"smoke={'yes' if smoke else 'no'})"
                ),
                nearest_fire_dist=nearest,
                smoke="yes" if smoke else "no",
                position=cell,
            )
            recorded = True
        elif (
            not self.target_pos
            and not self.exiting
            and self.pos is not None
            and self._cell_meets_required_idle_safety(
                (int(self.pos[0]), int(self.pos[1])), self._fire_cells()
            )
        ):
            self._reset_idle_retreat_state()
            self._record_movement_reason(
                "standby",
                f"standby at edge {self.pos}",
                position=self.pos,
            )
            recorded = True
        if not recorded:
            cell = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
            self._record_movement_reason(
                "holding",
                "holding position (no safe improving move / surrounded)",
                position=cell,
                nearest_fire_dist=(
                    self._min_fire_distance(cell, self._fire_cells())
                    if cell is not None
                    else None
                ),
            )

    def _fire_cells(self) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for agent in self.model.schedule.agents:
            if type(agent) is not Fire:
                continue
            if not agent.is_burning():
                continue
            pos = getattr(agent, "pos", None)
            if pos is not None:
                cells.add((int(pos[0]), int(pos[1])))
        return cells

    def _cell_contains_active_fire(self, cell: tuple[int, int]) -> bool:
        if self.model.grid.out_of_bounds(cell):
            return False
        try:
            contents = self.model.grid.get_cell_list_contents([cell])
        except Exception:
            return False
        for agent in contents:
            if type(agent) is Fire and agent.is_burning():
                return True
        return False

    def _cell_has_active_smoke(self, cell: tuple[int, int]) -> bool:
        if self.model.grid.out_of_bounds(cell):
            return False
        try:
            contents = self.model.grid.get_cell_list_contents([cell])
        except Exception:
            return False
        for agent in contents:
            if type(agent) is not Fire:
                continue
            smoke = getattr(agent, "smoke", None)
            if smoke is not None:
                is_smoke_active = getattr(smoke, "is_smoke_active", None)
                if callable(is_smoke_active) and is_smoke_active():
                    return True
        return False

    def _cell_adjacent_to_fire(self, cell: tuple[int, int]) -> bool:
        cx, cy = cell
        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if self._cell_contains_active_fire((cx + ox, cy + oy)):
                return True
        return False

    def _firefighter_cell_risk(self, cell: tuple[int, int]) -> int:
        if self._cell_contains_active_fire(cell):
            return 1_000_000
        risk = 0
        if self._cell_adjacent_to_fire(cell):
            risk += 100
        if self._cell_has_active_smoke(cell):
            risk += 10
        return risk

    def _neighbor_cells(self) -> list[tuple[int, int]]:
        cx, cy = self.pos
        neighbors: list[tuple[int, int]] = []
        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cell = (cx + ox, cy + oy)
            if not self.model.grid.out_of_bounds(cell):
                neighbors.append(cell)
        return neighbors

    def _needs_immediate_survival_retreat(self) -> bool:
        if self.pos is None or getattr(self, "dead", False) or self.exiting:
            return False
        cell = (int(self.pos[0]), int(self.pos[1]))
        if self._cell_contains_active_fire(cell) or self._cell_has_active_smoke(cell):
            return True
        fire_cells = self._fire_cells()
        if not self.target_pos:
            if self._cell_adjacent_to_fire(cell):
                return True
            if self._min_fire_distance(cell, fire_cells) <= IDLE_RETREAT_SAFETY_BUFFER:
                return True
            return False
        if self._cell_adjacent_to_fire(cell):
            return True
        if self._min_fire_distance(cell, fire_cells) <= 1:
            return True
        return False

    def _idle_needs_survival_move(self) -> bool:
        if self.exiting:
            return False
        if self.target_pos:
            return False
        if self.pos is None:
            return False
        cell = (int(self.pos[0]), int(self.pos[1]))
        fire_cells = self._fire_cells()
        return (
            self._cell_contains_active_fire(cell)
            or self._cell_adjacent_to_fire(cell)
            or self._cell_has_active_smoke(cell)
            or self._min_fire_distance(cell, fire_cells) <= IDLE_RETREAT_SAFETY_BUFFER
        )

    def _min_fire_distance(
        self, cell: tuple[int, int], fire_cells: set[tuple[int, int]]
    ) -> int:
        if not fire_cells:
            return 999
        cx, cy = cell
        return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fire_cells)

    def _cell_meets_required_idle_safety(
        self, cell: tuple[int, int], fire_cells: set[tuple[int, int]]
    ) -> bool:
        if self._cell_contains_active_fire(cell):
            return False
        if self._cell_adjacent_to_fire(cell):
            return False
        if self._cell_has_active_smoke(cell):
            return False
        return True

    def _cell_is_ideal_idle_standoff(
        self, cell: tuple[int, int], fire_cells: set[tuple[int, int]]
    ) -> bool:
        if not self._cell_meets_required_idle_safety(cell, fire_cells):
            return False
        return (
            self._min_fire_distance(cell, fire_cells)
            >= IDLE_RETREAT_SAFETY_BUFFER + 1
        )

    def _reset_idle_retreat_state(self) -> None:
        self._idle_retreat_origin = None
        self._idle_retreat_steps = 0
        self._idle_retreat_stalled = False
        self._idle_retreat_last_cell = None

    def _survival_move(self) -> None:
        if self.pos is None:
            return
        cell = (int(self.pos[0]), int(self.pos[1]))
        fire_cells = self._fire_cells()

        if self._cell_is_ideal_idle_standoff(cell, fire_cells):
            self._reset_idle_retreat_state()
            return

        origin = getattr(self, "_idle_retreat_origin", None)
        if origin is None or (
            not self.target_pos
            and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1])
            > IDLE_RETREAT_MAX_CELLS
        ):
            # The leash below is measured from where the retreat began, and the
            # scan only ever steps to cells within IDLE_RETREAT_MAX_CELLS of it.
            # For an idle unit that scan is the only thing that moves it here,
            # so standing further out than the leash allows proves something
            # else did: a walk to a victim, an assigned one-step retreat, or an
            # unassign that left it wherever it happened to be. The recorded
            # origin then belongs to a manoeuvre that is over, and leashing to
            # it tethers a stranded unit to a cell it left long ago. Anchor a
            # fresh manoeuvre here instead. The stall flag goes with it: that
            # verdict was reached through the old leash, so correcting the
            # leash invalidates it. Assigned units are excluded because
            # `_assigned_one_step_retreat` moves them without any leash test,
            # so for them the same distance proves nothing.
            self._idle_retreat_origin = cell
            self._idle_retreat_steps = 0
            self._idle_retreat_stalled = False
            self._idle_retreat_last_cell = None
            origin = cell

        if bool(getattr(self, "_idle_retreat_stalled", False)):
            if self.target_pos:
                self._assigned_one_step_retreat(fire_cells)
                return
            self._revalidate_idle_retreat_stall(cell, origin, fire_cells)
            return

        steps = int(getattr(self, "_idle_retreat_steps", 0) or 0)
        at_cap = steps >= IDLE_RETREAT_MAX_CELLS
        current_dist = self._min_fire_distance(cell, fire_cells)
        current_risk = self._firefighter_cell_risk(cell)
        last_cell = getattr(self, "_idle_retreat_last_cell", None)

        candidates = self._retreat_candidates(
            cell, origin, last_cell, fire_cells, current_dist
        )

        if not candidates:
            if self.target_pos and self._assigned_one_step_retreat(fire_cells):
                return
            self._idle_retreat_stalled = True
            return

        chosen: dict[str, object] | None = None
        if not at_cap:
            chosen = self._pick_improving_retreat(
                candidates, current_dist, current_risk
            )
            if chosen is None:
                chosen = max(
                    candidates,
                    key=lambda c: (int(c["dist"]), -int(c["risk"])),
                )
                if not self.target_pos:
                    self._idle_retreat_stalled = True
        else:
            required_reachable = [c for c in candidates if c["required"]]
            if required_reachable:
                chosen = max(
                    required_reachable,
                    key=lambda c: (int(c["dist"]), -int(c["risk"])),
                )
                if not self.target_pos:
                    self._reset_idle_retreat_state()
            else:
                chosen = max(
                    candidates,
                    key=lambda c: (int(c["dist"]), -int(c["risk"])),
                )
                if not self.target_pos:
                    self._idle_retreat_stalled = True

        if chosen is None:
            if self.target_pos and self._assigned_one_step_retreat(fire_cells):
                return
            self._idle_retreat_stalled = True
            return

        target = chosen["cell"]
        if target == cell:
            if self.target_pos and self._assigned_one_step_retreat(fire_cells):
                return
            self._idle_retreat_stalled = True
            return

        self._idle_retreat_last_cell = cell
        self.model.grid.move_agent(self, target)
        self._idle_retreat_steps = steps + 1

        if self._cell_is_ideal_idle_standoff(target, self._fire_cells()):
            self._reset_idle_retreat_state()
        elif self._cell_meets_required_idle_safety(target, self._fire_cells()) and (
            (at_cap or self._idle_retreat_stalled) and not self.target_pos
        ):
            self._reset_idle_retreat_state()

    def _retreat_candidates(
        self,
        cell: tuple[int, int],
        origin: tuple[int, int],
        last_cell: tuple[int, int] | None,
        fire_cells: set[tuple[int, int]],
        current_dist: int,
    ) -> list[dict[str, object]]:
        """Neighbour cells that survive the retreat filter chain.

        One definition, shared by the normal scan and by
        `_revalidate_idle_retreat_stall`, so the two can never drift apart
        about what "nowhere to go" means.
        """
        candidates: list[dict[str, object]] = []
        for ncell in self._neighbor_cells():
            if self._cell_contains_active_fire(ncell):
                continue
            if ncell == last_cell:
                continue
            from_origin = abs(ncell[0] - origin[0]) + abs(ncell[1] - origin[1])
            if from_origin > IDLE_RETREAT_MAX_CELLS:
                continue
            risk = self._firefighter_cell_risk(ncell)
            new_dist = self._min_fire_distance(ncell, fire_cells)
            candidates.append(
                {
                    "cell": ncell,
                    "risk": risk,
                    "dist": new_dist,
                    "improvement": new_dist - current_dist,
                    "ideal": self._cell_is_ideal_idle_standoff(ncell, fire_cells),
                    "required": self._cell_meets_required_idle_safety(
                        ncell, fire_cells
                    ),
                }
            )
        if not candidates and last_cell is not None and current_dist == 0:
            # The unit is standing on a burning cell and every neighbour it
            # could still step to was ruled out by the anti-oscillation
            # memory. That memory exists to stop a unit ping-ponging between
            # two free cells, and it cannot serve that purpose here: the cell
            # being vacated is on fire, so the fire test above - which comes
            # first and so outranks it - refuses the step back anyway until
            # that cell burns out. Re-run the same chain without it, so
            # `last_cell` is considered only when nothing else survived and
            # every other filter, the leash included, still applies to it.
            return self._retreat_candidates(
                cell, origin, None, fire_cells, current_dist
            )
        return candidates

    def _pick_improving_retreat(
        self,
        candidates: list[dict[str, object]],
        current_dist: int,
        current_risk: int,
    ) -> dict[str, object] | None:
        """Best candidate that genuinely beats standing still, else None.

        An ideal standoff ends the retreat outright, so it wins even when it
        is no further from the fire; otherwise a step must gain fire distance,
        or lower risk without giving distance up. The "take the least-bad
        neighbour anyway" fallback is deliberately not here: repeating that
        step is what the stall latch legitimately exists to stop, so the
        normal scan keeps it and the revalidation pass does not.
        """
        ideal_reachable = [c for c in candidates if c["ideal"]]
        if ideal_reachable:
            return max(
                ideal_reachable,
                key=lambda c: (c["dist"], -int(c["risk"])),
            )
        improving = [
            c
            for c in candidates
            if int(c["improvement"]) > 0
            or (
                int(c["risk"]) < current_risk
                and int(c["dist"]) >= current_dist
            )
        ]
        if improving:
            return max(
                improving,
                key=lambda c: (
                    int(c["improvement"]),
                    int(c["dist"]),
                    -int(c["risk"]),
                ),
            )
        return None

    def _revalidate_idle_retreat_stall(
        self,
        cell: tuple[int, int],
        origin: tuple[int, int],
        fire_cells: set[tuple[int, int]],
    ) -> None:
        """Re-test a stalled idle unit's retreat instead of trusting the flag.

        `_idle_retreat_stalled` only records that on one earlier step nothing
        nearby was worth stepping to. Read as permanent it is fatal: for an
        idle unit the check in `_survival_move` used to return before the
        candidate scan, and the only resets that could clear the flag - the
        ideal-standoff test at the top of `_survival_move`, and the standby
        branch of `advance` - both require the unit to already be safe, which
        is the exact complement of the condition that calls this. So while
        fire stayed near, a stalled idle unit never looked again even as the
        fire moved and its neighbourhood changed.

        Re-run the same filter chain and move only on a genuine improvement.
        A neighbour that is merely reachable is still refused, so when nothing
        has actually changed the unit holds its cell and stays latched exactly
        as before.
        """
        last_cell = getattr(self, "_idle_retreat_last_cell", None)
        current_dist = self._min_fire_distance(cell, fire_cells)
        current_risk = self._firefighter_cell_risk(cell)
        chosen = self._pick_improving_retreat(
            self._retreat_candidates(
                cell, origin, last_cell, fire_cells, current_dist
            ),
            current_dist,
            current_risk,
        )
        if chosen is None:
            return
        steps = int(getattr(self, "_idle_retreat_steps", 0) or 0)
        self._idle_retreat_last_cell = cell
        self.model.grid.move_agent(self, chosen["cell"])
        self._idle_retreat_steps = steps + 1
        # Only the stall flag is cleared. `_reset_idle_retreat_state` would
        # also drop `_idle_retreat_last_cell`, the anti-oscillation memory, on
        # the one path being added here. The existing reset sites still fire
        # normally once the unit is genuinely safe.
        self._idle_retreat_stalled = False

    def _assigned_one_step_retreat(
        self, fire_cells: set[tuple[int, int]] | None = None,
    ) -> bool:
        """Assigned/exiting FF: one safe step away from fire without dropping task."""
        if self.pos is None:
            return False
        if fire_cells is None:
            fire_cells = self._fire_cells()
        cell = (int(self.pos[0]), int(self.pos[1]))
        best: tuple[int, int] | None = None
        best_score = -1
        for ncell in self._neighbor_cells():
            if self._cell_contains_active_fire(ncell):
                continue
            if self._cell_adjacent_to_fire(ncell):
                continue
            if self._cell_has_active_smoke(ncell):
                continue
            score = self._min_fire_distance(ncell, fire_cells)
            if score > best_score:
                best_score = score
                best = ncell
        if best is not None and best != cell:
            self.model.grid.move_agent(self, best)
            return True
        return False

    def _path_exists_avoiding_fire(
        self,
        src: tuple[int, int],
        dst: tuple[int, int],
        fire_cells: set[tuple[int, int]],
    ) -> bool:
        """4-connected reachability with active fire impassable.

        Same notion of "reachable" the model already uses to decide whether a
        victim is unreachable (wildfire_model._safe_path_reachable_cells).
        The destination counts as reachable even when it is itself burning: a
        victim's cell can burn transiently, and calling that "no route" would
        hand a still-rescuable victim to a replacement for nothing. The source
        is never tested, so a unit standing in fire can still be asked whether
        its target is reachable.
        """
        if src == dst:
            return True
        grid = self.model.grid
        seen = {src}
        queue = deque([src])
        while queue:
            cx, cy = queue.popleft()
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cell = (cx + ox, cy + oy)
                if grid.out_of_bounds(cell):
                    continue
                if cell in seen:
                    continue
                if cell == dst:
                    return True
                if cell in fire_cells:
                    continue
                seen.add(cell)
                queue.append(cell)
        return False

    def _mark_route_blocked(self) -> None:
        if str(getattr(self, "status", "") or "").strip().lower() != "route_blocked":
            self.status = "route_blocked"
            handler = getattr(self.model, "_on_firefighter_route_blocked", None)
            if callable(handler):
                handler(self)
            else:
                print(f"[Rescue Blocked] FF-{self.unit_id} no safe route")

    def _cell_is_hazard(self, cell: tuple[int, int]) -> bool:
        if self.model.grid.out_of_bounds(cell):
            return True
        return self._cell_contains_active_fire(cell)

    def _move_toward(self, target):
        tx, ty = target
        cx, cy = self.pos
        dx, dy = tx - cx, ty - cy
        if abs(dx) >= abs(dy):
            nx = cx + (1 if dx > 0 else -1 if dx < 0 else 0)
            ny = cy
        else:
            nx = cx
            ny = cy + (1 if dy > 0 else -1 if dy < 0 else 0)
        preferred = (nx, ny)
        dist_before = abs(cx - tx) + abs(cy - ty)

        # Route is blocked when no fire-free path to the target exists at all,
        # not merely when every neighbour happens to burn. Scoped to the
        # approach phase: for a unit already carrying a victim the replacement
        # pathway is the wrong response, so the exiting path keeps only the
        # original "nowhere to step" condition below.
        route_blocked_now = False
        if not self.exiting:
            route_blocked_now = not self._path_exists_avoiding_fire(
                (int(cx), int(cy)), (int(tx), int(ty)), self._fire_cells(),
            )

        scored: list[dict[str, object]] = []
        for cell in self._neighbor_cells():
            if self._cell_contains_active_fire(cell):
                continue
            dist_after = abs(cell[0] - tx) + abs(cell[1] - ty)
            scored.append(
                {
                    "cell": cell,
                    "dist_after": dist_after,
                    "improving": dist_after < dist_before,
                    "maintaining": dist_after == dist_before,
                    "adjacent_fire": self._cell_adjacent_to_fire(cell),
                    "smoke": self._cell_has_active_smoke(cell),
                    "preferred": cell == preferred,
                    "risk": self._firefighter_cell_risk(cell),
                }
            )

        if not scored:
            self._mark_route_blocked()
            return

        if route_blocked_now:
            # Raise the signal but keep moving: choosing the best available step
            # is the retreat logic's job and is out of scope here.
            self._mark_route_blocked()

        chosen: tuple[int, int] | None = None
        chosen_tier = 4
        tier_pools = [
            [
                item for item in scored
                if item["improving"] and not item["adjacent_fire"] and not item["smoke"]
            ],
            [
                item for item in scored
                if item["maintaining"] and not item["adjacent_fire"] and not item["smoke"]
            ],
            [
                item for item in scored
                if not item["adjacent_fire"] and not item["smoke"]
            ],
        ]
        for tier_idx, pool in enumerate(tier_pools, start=1):
            if pool:
                chosen_item = min(
                    pool,
                    key=lambda item: (item["dist_after"], 0 if item["preferred"] else 1),
                )
                chosen = chosen_item["cell"]
                chosen_tier = tier_idx
                break
        if chosen is None:
            chosen_item = min(
                scored,
                key=lambda item: (
                    item["risk"],
                    item["dist_after"],
                    0 if item["preferred"] else 1,
                ),
            )
            chosen = chosen_item["cell"]
            chosen_tier = 4

        self._last_move_tier = chosen_tier
        self._last_move_risk = int(chosen_item["risk"])

        if not route_blocked_now and (
            str(getattr(self, "status", "") or "").strip().lower() == "route_blocked"
        ):
            self.status = "assigned" if self.assigned else "available"
        self.model.grid.move_agent(self, chosen)


class PathMarker(mesa.Agent):
    """Visual-only path cell between firefighter and victim."""

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.marker_only = True

    def step(self):
        pass

    def advance(self):
        pass
