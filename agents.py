# python libraries

import mesa
import functools

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

    # function for moving UAV over the grid area
    def move(self):
        # vectors for moving to different positions, based on 4 directions = [0, 1, 2, 3] = [right, down, left, up].
        # For example, if direction 1 is chosen, then the UAV moves 0 cells in x-axis, and -1 cell in y-axis
        move_x = [1, 0, -1, 0]
        move_y = [0, -1, 0, 1]
        moved = False

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


class Victim(mesa.Agent):
    """Display-only victim marker."""

    def __init__(self, unique_id, model, victim_id: str, position: tuple):
        super().__init__(unique_id, model)
        self.victim_id = victim_id
        self.status = "candidate"
        self.marker_only = True

    def step(self):
        pass

    def advance(self):
        pass


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

    def advance(self):
        if self.pos is None or getattr(self, "dead", False):
            return
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
        if origin is None:
            self._idle_retreat_origin = cell
            self._idle_retreat_steps = 0
            self._idle_retreat_stalled = False
            self._idle_retreat_last_cell = None
            origin = cell

        if bool(getattr(self, "_idle_retreat_stalled", False)):
            if self.target_pos and self._assigned_one_step_retreat(fire_cells):
                return
            return

        steps = int(getattr(self, "_idle_retreat_steps", 0) or 0)
        at_cap = steps >= IDLE_RETREAT_MAX_CELLS
        current_dist = self._min_fire_distance(cell, fire_cells)
        current_risk = self._firefighter_cell_risk(cell)
        last_cell = getattr(self, "_idle_retreat_last_cell", None)

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

        if not candidates:
            if self.target_pos and self._assigned_one_step_retreat(fire_cells):
                return
            self._idle_retreat_stalled = True
            return

        chosen: dict[str, object] | None = None
        if not at_cap:
            ideal_reachable = [c for c in candidates if c["ideal"]]
            if ideal_reachable:
                chosen = max(
                    ideal_reachable,
                    key=lambda c: (c["dist"], -int(c["risk"])),
                )
            else:
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
                    chosen = max(
                        improving,
                        key=lambda c: (
                            int(c["improvement"]),
                            int(c["dist"]),
                            -int(c["risk"]),
                        ),
                    )
                else:
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

    def _mark_route_blocked(self) -> None:
        if not self._cell_contains_active_fire((int(self.pos[0]), int(self.pos[1]))):
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

        if str(getattr(self, "status", "") or "").strip().lower() == "route_blocked":
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
