# python libraries

import math
import sys
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

import mesa
import matplotlib.pyplot as plt

# own python modules

import agents

from common_fixed_variables import *
from src_extension.knowledge.communication_model import CommunicationModel
from src_extension.knowledge.fire_runtime_model import FireRuntimeModel
from src_extension.knowledge.firefighter_model import FirefighterModel
from src_extension.knowledge.knowledge_manager import KnowledgeManager
from src_extension.knowledge.local_observation_model import LocalObservationModel
from src_extension.knowledge.local_path_context_model import LocalPathContextModel
from src_extension.knowledge.mission_goal_model import MissionGoalModel
from src_extension.knowledge.shared_operational_picture import SharedOperationalPicture
from src_extension.knowledge.uav_resource_model import UAVResourceModel
from src_extension.knowledge.victim_runtime_model import VictimRuntimeModel
from src_extension.knowledge.visibility_model import ObservationStatus, VisibilityModel
from src_extension.managed.environment_bridge import EnvironmentBridge
from src_extension.managed.firefighter_state import FirefighterOperationalState
from src_extension.managed.uav_extension_state import UAVExtensionState
from src_extension.managed.victim_state import VictimState
from src_extension.monitoring.communication_monitor import CommunicationMonitor
from src_extension.monitoring.environment_monitor import EnvironmentMonitor
from src_extension.monitoring.firefighter_monitor import FirefighterMonitor
from src_extension.monitoring.global_monitor import GlobalMonitor
from src_extension.monitoring.local_uav_monitor import LocalUAVMonitor
from src_extension.monitoring.monitoring_buffer import MonitoringBuffer
from src_extension.monitoring.monitoring_interfaces import LocalObservation
from src_extension.analysis.analysis_results import AnalysisSnapshot, build_dashboard_summary
from src_extension.analysis.global_analyzer import GlobalAnalyzer
from src_extension.analysis.local_uav_analyzer import LocalUAVAnalyzer
from src_extension.adaptation.adaptation_results import (
    AdaptationSpaceSnapshot,
    build_adaptation_dashboard_summary,
    collect_all_options,
)
from src_extension.adaptation.communication_adaptation_generator import (
    CommunicationAdaptationGenerator,
)
from src_extension.adaptation_manager import AdaptationManager
from src_extension.adaptation.constraint_filter import ConstraintFilter
from src_extension.adaptation.failsafe_adaptation_generator import FailSafeAdaptationGenerator
from src_extension.adaptation.global_adaptation_generator import GlobalAdaptationSpaceGenerator
from src_extension.adaptation.local_adaptation_generator import (
    LocalAdaptationSpaceGenerator,
    POST_RESCUE_COVERAGE_DURATION,
    _count_unresolved_victims,
    _wind_search_state,
    resolve_victim_searcher_uav_ids,
)
from src_extension.adaptation.rescue_adaptation_generator import RescueAdaptationSpaceGenerator
from src_extension.execution.decision_dispatcher import DecisionDispatcher
from src_extension.execution.execution_log import ExecutionLog
from src_extension.execution.rescue_executor import RescueExecutor
from src_extension.planning.decision_objects import RescueDecision
from src_extension.planning.rescue_planner import (
    RescuePlanner,
    select_rescue_assignment,
    unreachable_escape_victims,
    UNREACHABLE_CAUSE_GEOGRAPHIC,
    UNREACHABLE_CAUSE_UNDETECTED,
)
from src_extension.execution.failsafe_modes import FailSafeMode
from src_extension.execution.mode_manager import ModeManager, build_failsafe_dashboard_summary
from src_extension.execution.safety_checker import SafetyChecker
from src_extension.planning.planning_coordinator import PlanningCoordinator
from src_extension.dashboard.dashboard_state_builder import DashboardStateBuilder
from src_extension.dashboard.dashboard_exporter import DashboardStateExporter


@dataclass(frozen=True)
class PhysicalRescueCommand:
    action: str
    victim_id: str
    firefighter_id: str | None
    reason: str
    metadata: dict


# class WildFireModel holds methods for managing the main logic of the grid, such as the main execution loop,
# setting agents, methods for checking the state of the grid, etc
class WildFireModel(mesa.Model):

    # constructor
    def __init__(self):

        plt.ion()

        # attributes intialization

        self.new_direction_counter = None
        self.datacollector = None
        self.grid = None
        self.unique_agents_id = None
        self.new_direction = None
        self.evaluation_timesteps_counter = None
        self.NUM_AGENTS = NUM_AGENTS
        self.NUM_FIRE_TRACKERS = NUM_FIRE_TRACKERS
        self.NUM_VICTIM_SEARCHERS = NUM_VICTIM_SEARCHERS
        print(self.NUM_AGENTS)

        self.MR1_LIST = [0.0 for i in range(0, self.NUM_AGENTS)]
        self.MR2_VALUE = 0

        self.reset()

    # reset method with attributes initialization. This method should be used whenever it is needed to reset the
    # environment in execution time. For example, when the graphical interface is up, and reset button is pressed, this
    # method is called
    def reset(self):

        self.unique_agents_id = 0
        # Inverted width and height order, because of matrix accessing purposes, like in many examples:
        #   https://snyk.io/advisor/python/Mesa/functions/mesa.space.MultiGrid
        # set some Mesa framework management
        self.grid = mesa.space.MultiGrid(HEIGHT, WIDTH, False)
        self.schedule = mesa.time.SimultaneousActivation(self)
        # set Fire and wind agents (Smoke are created inside Fire agents as well)
        self.set_fire_agents()
        self.wind = agents.Wind()

        self.new_direction_counter = 0
        self.evaluation_timesteps_counter = 0

        # create and configure UAV agents in the grid
        warmup_dirs = (0, 1, 3)
        base_x = HEIGHT // 2
        base_y = WIDTH // 2
        base_cluster = [
            (base_x, base_y),
            (base_x + 1, base_y),
            (base_x, base_y + 1),
            (base_x + 1, base_y + 1),
        ]
        for a in range(0, self.NUM_AGENTS):
            aux_UAV = agents.UAV(self.unique_agents_id, self)
            aux_UAV.selected_dir = warmup_dirs[a % len(warmup_dirs)]
            spawn_pos = base_cluster[a % len(base_cluster)]
            if self.grid.out_of_bounds(spawn_pos):
                spawn_pos = (
                    max(0, min(base_x, HEIGHT - 1)),
                    max(0, min(base_y, WIDTH - 1)),
                )
            self.grid.place_agent(aux_UAV, spawn_pos)
            self.schedule.add(aux_UAV)
            self.unique_agents_id += 1

        # set Mesa framework management
        self.datacollector = mesa.DataCollector()
        self.new_direction = [0 for a in range(0, self.NUM_AGENTS)]
        self._init_runtime_knowledge()

    def _init_runtime_knowledge(self):
        self.fire_runtime_model = FireRuntimeModel()
        self.visibility_model = VisibilityModel()
        self.victim_runtime_model = VictimRuntimeModel()
        self._init_managed_victims()
        self.uav_resource_model = UAVResourceModel()
        self.communication_model = CommunicationModel()
        self.firefighter_model = FirefighterModel()
        self._init_managed_firefighters()
        self._init_managed_uav_states()
        self._assign_uav_roles()
        self.mission_goal_model = MissionGoalModel()
        self.local_observation_models = {}
        self.local_path_context_models = {}
        self.fire_runtime_model.initialize_grid(width=HEIGHT, height=WIDTH)
        self.visibility_model.initialize_grid(width=HEIGHT, height=WIDTH)
        self.visibility_model.set_smoke_obscured_handler(self.fire_runtime_model.mark_smoke_obscured)
        self.environment_bridge = EnvironmentBridge()
        self.environment_bridge.attach(self)
        self.latest_environment_bridge_snapshot = None
        self.monitoring_buffer = MonitoringBuffer()
        self.environment_monitor = EnvironmentMonitor()
        self.shared_operational_picture = SharedOperationalPicture()
        self.knowledge_manager = KnowledgeManager(
            models={
                "fire_model": self.fire_runtime_model,
                "visibility_model": self.visibility_model,
                "victim_model": self.victim_runtime_model,
                "uav_resource_model": self.uav_resource_model,
                "communication_model": self.communication_model,
                "firefighter_model": self.firefighter_model,
                "mission_goal_model": self.mission_goal_model,
            }
        )
        for agent in self.schedule.agents:
            if type(agent) is agents.UAV:
                uav_id = str(agent.unique_id)
                local_obs = LocalObservationModel(uav_id=uav_id)
                local_path = LocalPathContextModel(uav_id=uav_id)
                self.local_observation_models[uav_id] = local_obs
                self.local_path_context_models[uav_id] = local_path
                self.knowledge_manager.register_model(f"local_obs_{uav_id}", local_obs)
                self.knowledge_manager.register_model(f"local_path_{uav_id}", local_path)
                agent.local_monitor = LocalUAVMonitor(
                    uav_id=uav_id,
                    fire_runtime_model=self.fire_runtime_model,
                    visibility_model=self.visibility_model,
                    victim_runtime_model=self.victim_runtime_model,
                    uav_resource_model=self.uav_resource_model,
                )
                agent.latest_local_observation = None

        uavs = [a for a in self.schedule.agents if type(a) is agents.UAV]
        self.communication_monitor = CommunicationMonitor(self.communication_model)
        self.firefighter_monitor = FirefighterMonitor(self.firefighter_model)
        self.global_monitor = GlobalMonitor(
            fire_runtime_model=self.fire_runtime_model,
            visibility_model=self.visibility_model,
            victim_runtime_model=self.victim_runtime_model,
            uav_resource_model=self.uav_resource_model,
            communication_model=self.communication_model,
            firefighter_model=self.firefighter_model,
            communication_monitor=self.communication_monitor,
            firefighter_monitor=self.firefighter_monitor,
            environment_monitor=self.environment_monitor,
            uavs=uavs,
        )
        self.latest_global_snapshot = None
        self.local_uav_analyzer = LocalUAVAnalyzer(
            low_battery_threshold=LOW_BATTERY_THRESHOLD,
            critical_battery_threshold=BATTERY_CRITICAL_THRESHOLD,
        )
        self.global_analyzer = GlobalAnalyzer(
            low_battery_threshold=LOW_BATTERY_THRESHOLD,
            critical_battery_threshold=BATTERY_CRITICAL_THRESHOLD,
        )
        self.latest_analysis_snapshot = None
        self.global_adaptation_generator = GlobalAdaptationSpaceGenerator()
        self.local_adaptation_generator = LocalAdaptationSpaceGenerator()
        self.rescue_adaptation_generator = RescueAdaptationSpaceGenerator()
        self.failsafe_adaptation_generator = FailSafeAdaptationGenerator()
        self.communication_adaptation_generator = CommunicationAdaptationGenerator()
        self.constraint_filter = ConstraintFilter()
        self.latest_adaptation_space_snapshot = None
        self.latest_communication_adaptation_space = None
        self.pending_global_commands: list[dict[str, object]] = []
        self.latest_communication_execution: dict[str, object] | None = None
        self.adaptation_manager = AdaptationManager()
        self.latest_adaptation_cycle_result: dict[str, object] | None = None
        self.latest_post_move_cycle_result: dict[str, object] | None = None
        self.planning_coordinator = PlanningCoordinator()
        self.latest_planning_result = None
        self.execution_log = ExecutionLog()
        self.decision_dispatcher = DecisionDispatcher(
            model=self, execution_log=self.execution_log
        )
        self.latest_execution_result = None
        self.latest_execution_feedback_event = None
        self.mode_manager = ModeManager(SafetyChecker())
        self.latest_failsafe_state = None
        self.latest_failsafe_dashboard_summary = None
        self.uav_visit_counts: dict[tuple[str, int, int], int] = {}
        self.uav_last_failed_dir: dict[str, int] = {}
        self._uav_prev_grid_positions: dict[str, tuple[int, int]] = {}
        self._uav_positions_before_step: dict[str, tuple[int, int]] = {}
        self._uav_stuck_counts: dict[str, int] = {}
        self._uav_position_history: dict[str, list[tuple[int, int]]] = {}
        self._uav_direction_history: dict[str, list[int]] = {}
        self._uav_last_targets: dict[str, tuple[float, float] | None] = {}
        self._uav_target_switch_counts: dict[str, int] = {}
        self._victim_escape_memory: dict[str, dict[str, Any]] = {}
        self._victim_sweep_state: dict[str, dict[str, Any]] = {}
        self._wind_search_target_state: dict[str, dict[str, Any]] = {}
        self._agents_pending_removal: list[Any] = []
        self._rescue_path_clear_requested = False
        self._rescue_failed_logged: set[str] = set()
        self._rescue_blocked_logged: set[tuple[str, str]] = set()
        self._blocked_replacement_attempted: set[tuple[str, str]] = set()
        self._unreachable_geo_streak: dict[str, int] = {}
        self._unreachable_undetected_streak: dict[str, int] = {}
        self._ff_victim_distances: dict[tuple[str, str], int] = {}
        self._unreachable_escape_log: list[dict[str, Any]] = []
        self._firefighter_sync_mismatch_logged: set[str] = set()
        self._rescue_event_log: list[dict[str, Any]] = []
        self._latest_physical_rescue_by_victim: dict[str, dict[str, Any]] = {}
        self.latest_physical_rescue_decision: RescueDecision | None = None
        self.rescue_planner = RescuePlanner()
        self._rescue_incident_queue: list[dict[str, Any]] = []
        self._rescue_incident_seen_keys: set[str] = set()
        self._rescue_incident_processing_enabled = True
        # Legacy compatibility/debug only; production rescue uses incident queue.
        self._allow_sync_victim_dispatch_fallback = False
        self._physical_rescue_command_audit: list[dict[str, Any]] = []
        self._physical_rescue_command_via_executor = False
        self._uav_sector_assignments: dict[str, dict[str, int]] = {}
        self.dashboard_state_builder = DashboardStateBuilder()
        self.dashboard_exporter = DashboardStateExporter()
        self.latest_dashboard_state: dict[str, Any] | None = None
        self.debug_log = True
        self._init_uav_sector_assignments()

    def _uav_assignment_role(self, uav_id: str) -> str | None:
        managed = getattr(self, "managed_uav_states", None)
        if isinstance(managed, dict):
            state = managed.get(uav_id)
            if state is not None:
                role = getattr(state, "role", None)
                if role:
                    return str(role).strip().lower()
        resource_model = getattr(self, "uav_resource_model", None)
        if resource_model is not None:
            by_uav_id = getattr(resource_model, "by_uav_id", None)
            if isinstance(by_uav_id, dict) and uav_id in by_uav_id:
                state = by_uav_id[uav_id]
                role = getattr(state, "current_role", None)
                if role is None and isinstance(state, dict):
                    role = state.get("current_role", state.get("role"))
                if role:
                    return str(role).strip().lower()
        return None

    def _init_uav_sector_assignments(self) -> None:
        """Assign each UAV a deterministic exploration sector on the grid."""
        self._uav_sector_assignments = {}
        uav_agents = sorted(
            [a for a in self.schedule.agents if type(a) is agents.UAV],
            key=lambda a: int(getattr(a, "unique_id", 0)),
        )
        n = len(uav_agents)
        if n == 0:
            return
        half_x = max(0, HEIGHT // 2 - 1)
        half_y = max(0, WIDTH // 2 - 1)
        full_grid_bounds = {
            "x_min": 0,
            "x_max": HEIGHT - 1,
            "y_min": 0,
            "y_max": WIDTH - 1,
        }
        for idx, uav in enumerate(uav_agents):
            uid = str(uav.unique_id)
            role = self._uav_assignment_role(uid)
            if role in {"victim_searcher", "victim_search"}:
                self._uav_sector_assignments[uid] = dict(full_grid_bounds)
                continue
            if role == "fire_tracker":
                self._uav_sector_assignments[uid] = dict(full_grid_bounds)
                continue
            if n == 3:
                if idx == 0:
                    bounds = {
                        "x_min": 0,
                        "x_max": half_x,
                        "y_min": 0,
                        "y_max": half_y,
                    }
                elif idx == 1:
                    bounds = {
                        "x_min": 0,
                        "x_max": half_x,
                        "y_min": half_y + 1,
                        "y_max": WIDTH - 1,
                    }
                else:
                    bounds = {
                        "x_min": half_x + 1,
                        "x_max": HEIGHT - 1,
                        "y_min": 0,
                        "y_max": WIDTH - 1,
                    }
            else:
                band = HEIGHT / n
                x_min = int(idx * band)
                x_max = (
                    int((idx + 1) * band) - 1
                    if idx < n - 1
                    else HEIGHT - 1
                )
                bounds = {
                    "x_min": max(0, x_min),
                    "x_max": min(HEIGHT - 1, x_max),
                    "y_min": 0,
                    "y_max": WIDTH - 1,
                }
            self._uav_sector_assignments[uid] = bounds

    def _collect_fire_cells_for_sector_update(self) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for agent in self.schedule.agents:
            if type(agent) is not agents.Fire:
                continue
            pos = getattr(agent, "pos", None)
            if pos is None:
                continue
            is_burning = getattr(agent, "is_burning", None)
            if callable(is_burning) and is_burning():
                cells.add((int(pos[0]), int(pos[1])))
        fire_runtime = getattr(self, "fire_runtime_model", None)
        if fire_runtime is not None:
            belief = getattr(fire_runtime, "belief", None)
            fire_map = getattr(belief, "fire_probability_map", None) if belief else None
            if isinstance(fire_map, dict):
                for cell_pos, raw_prob in fire_map.items():
                    if float(raw_prob) < 0.45:
                        continue
                    if isinstance(cell_pos, (list, tuple)) and len(cell_pos) >= 2:
                        cells.add((int(cell_pos[0]), int(cell_pos[1])))
        return cells

    def _update_fire_tracker_sector_assignments(self) -> None:
        """Re-anchor fire_tracker sectors on opposite flanks of the live fire front."""
        tracker_ids: list[str] = []
        for uav in self.schedule.agents:
            if type(uav) is not agents.UAV:
                continue
            uid = str(uav.unique_id)
            if self._uav_assignment_role(uid) == "fire_tracker":
                tracker_ids.append(uid)
        if not tracker_ids:
            return

        full_grid_bounds = {
            "x_min": 0,
            "x_max": HEIGHT - 1,
            "y_min": 0,
            "y_max": WIDTH - 1,
            "split_axis": "none",
            "flank_index": 0,
            "flank_count": 1,
        }
        fire_cells = self._collect_fire_cells_for_sector_update()
        if not fire_cells:
            for uid in tracker_ids:
                self._uav_sector_assignments[uid] = dict(full_grid_bounds)
            return

        margin = 10
        xs = [cell[0] for cell in fire_cells]
        ys = [cell[1] for cell in fire_cells]
        x_min = max(0, min(xs) - margin)
        x_max = min(HEIGHT - 1, max(xs) + margin)
        y_min = max(0, min(ys) - margin)
        y_max = min(WIDTH - 1, max(ys) + margin)
        tracker_ids.sort(key=lambda uid: int(uid) if uid.isdigit() else uid)
        n = len(tracker_ids)
        x_extent = x_max - x_min
        y_extent = y_max - y_min
        axis_ratio = 1.15
        if x_extent > y_extent * axis_ratio:
            split_along_x = True
        elif y_extent > x_extent * axis_ratio:
            split_along_x = False
        else:
            prev_axis = getattr(self, "_fire_tracker_last_split_axis", None)
            if prev_axis == "x":
                split_along_x = True
            elif prev_axis == "y":
                split_along_x = False
            else:
                split_along_x = x_extent >= y_extent
        self._fire_tracker_last_split_axis = "x" if split_along_x else "y"

        for idx, uid in enumerate(tracker_ids):
            if n == 1:
                bounds = {
                    "x_min": x_min,
                    "x_max": x_max,
                    "y_min": y_min,
                    "y_max": y_max,
                    "split_axis": "none",
                    "flank_index": 0,
                    "flank_count": 1,
                }
            elif split_along_x:
                x_span = x_max - x_min + 1
                x_lo = x_min + (x_span * idx) // n
                x_hi = x_min + (x_span * (idx + 1)) // n - 1
                if idx == n - 1:
                    x_hi = x_max
                bounds = {
                    "x_min": x_lo,
                    "x_max": x_hi,
                    "y_min": y_min,
                    "y_max": y_max,
                    "split_axis": "x",
                    "flank_index": idx,
                    "flank_count": n,
                }
            else:
                y_span = y_max - y_min + 1
                y_lo = y_min + (y_span * idx) // n
                y_hi = y_min + (y_span * (idx + 1)) // n - 1
                if idx == n - 1:
                    y_hi = y_max
                bounds = {
                    "x_min": x_min,
                    "x_max": x_max,
                    "y_min": y_lo,
                    "y_max": y_hi,
                    "split_axis": "y",
                    "flank_index": idx,
                    "flank_count": n,
                }
            self._uav_sector_assignments[uid] = bounds

    def _init_managed_victims(self) -> None:
        if not hasattr(self, "managed_victims"):
            self.managed_victims = {}
        self.victim_marker_agents = {}

        positions = {}
        for i in range(NUM_VICTIMS):
            angle = (2 * math.pi * i) / max(NUM_VICTIMS, 1)
            r_x = 0.3 + 0.15 * (i % 2)
            r_y = 0.3 + 0.15 * (i % 2)
            vx = max(
                1.0,
                min(
                    float(HEIGHT) - 1,
                    float(HEIGHT) * (0.5 + r_x * math.cos(angle)),
                ),
            )
            vy = max(
                1.0,
                min(
                    float(WIDTH) - 1,
                    float(WIDTH) * (0.5 + r_y * math.sin(angle)),
                ),
            )
            positions[f"victim_{i}"] = (vx, vy)
        for victim_id, position in positions.items():
            self.managed_victims[victim_id] = VictimState(
                victim_id=victim_id,
                status="candidate",
                last_known_position=position,
                confidence=0.65,
                needs_confirmation=True,
            )
            grid_pos = (
                int(round(position[0])),
                int(round(position[1])),
            )
            if self.grid.out_of_bounds(grid_pos):
                grid_pos = (
                    max(0, min(grid_pos[0], HEIGHT - 1)),
                    max(0, min(grid_pos[1], WIDTH - 1)),
                )
            marker = agents.Victim(self.unique_agents_id, self, victim_id, position)
            marker.status = self.managed_victims[victim_id].status
            self.grid.place_agent(marker, grid_pos)
            self.schedule.add(marker)
            self.unique_agents_id += 1
            self.victim_marker_agents[victim_id] = marker

    def _init_managed_firefighters(self) -> None:
        if not hasattr(self, "managed_firefighters"):
            self.managed_firefighters = {}
        self.firefighter_marker_agents = {}

        positions = {}
        for i in range(NUM_FIREFIGHTERS):
            angle = (2 * math.pi * i) / max(NUM_FIREFIGHTERS, 1) + math.pi / 4
            fx = max(
                1.0,
                min(
                    float(HEIGHT) - 1,
                    float(HEIGHT) * (0.5 + 0.4 * math.cos(angle)),
                ),
            )
            fy = max(
                1.0,
                min(
                    float(WIDTH) - 1,
                    float(WIDTH) * (0.5 + 0.4 * math.sin(angle)),
                ),
            )
            positions[f"ff_unit_{i}"] = (fx, fy)
        for unit_id, position in positions.items():
            self.managed_firefighters[unit_id] = FirefighterOperationalState(
                unit_id=unit_id,
                position=position,
                availability="available",
                assignment_state="unassigned",
                route_state="idle",
                route_risk_summary="low",
            )
            self.firefighter_model.update_unit_state(
                unit_id=unit_id,
                current_position=position,
                availability_status="available",
                current_assignment=None,
                route_status="idle",
                route_risk_score=0.1,
                route_feasibility_confidence=0.9,
                source="scenario_init",
                timestamp=0.0,
            )
            grid_pos = (
                int(round(position[0])),
                int(round(position[1])),
            )
            if self.grid.out_of_bounds(grid_pos):
                grid_pos = (
                    max(0, min(grid_pos[0], HEIGHT - 1)),
                    max(0, min(grid_pos[1], WIDTH - 1)),
                )
            marker = agents.Firefighter(self.unique_agents_id, self, unit_id, position)
            self.grid.place_agent(marker, grid_pos)
            self.schedule.add(marker)
            self.unique_agents_id += 1
            self.firefighter_marker_agents[unit_id] = marker

    def _resolve_uav_role_counts(self, n_uavs: int) -> tuple[int, int, bool]:
        """Return (fire_trackers, victim_searchers, use_legacy_last_slot_searcher)."""
        if n_uavs <= 0:
            return 0, 0, True
        ft_raw = getattr(self, "NUM_FIRE_TRACKERS", None)
        vs_raw = getattr(self, "NUM_VICTIM_SEARCHERS", None)
        if ft_raw is None and vs_raw is None:
            return max(0, n_uavs - 1), min(1, n_uavs), True
        ft_count = max(0, int(ft_raw if ft_raw is not None else 0))
        vs_count = max(0, int(vs_raw if vs_raw is not None else 0))
        if ft_raw is None:
            ft_count = max(0, n_uavs - vs_count)
        elif vs_raw is None:
            vs_count = max(0, n_uavs - ft_count)
        if ft_count + vs_count != n_uavs:
            if ft_raw is not None and vs_raw is not None:
                ft_count = min(ft_count, n_uavs)
                vs_count = min(vs_count, n_uavs - ft_count)
            elif ft_raw is not None:
                vs_count = max(0, n_uavs - ft_count)
            else:
                ft_count = max(0, n_uavs - vs_count)
        ft_count = min(ft_count, n_uavs)
        vs_count = min(vs_count, max(0, n_uavs - ft_count))
        return ft_count, vs_count, False

    def _assign_uav_roles(self) -> None:
        uavs = sorted(
            [a for a in self.schedule.agents if type(a) is agents.UAV],
            key=lambda a: int(getattr(a, "unique_id", 0)),
        )
        n_uavs = len(uavs)
        if n_uavs == 0:
            return
        ft_count, vs_count, legacy = self._resolve_uav_role_counts(n_uavs)
        update_role = getattr(self.uav_resource_model, "update_role", None)
        managed_states = getattr(self, "managed_uav_states", None)
        for idx, agent in enumerate(uavs):
            uav_id = str(agent.unique_id)
            if legacy:
                role = "victim_searcher" if idx == n_uavs - 1 else "fire_tracker"
            elif idx < ft_count:
                role = "fire_tracker"
            elif idx < ft_count + vs_count:
                role = "victim_searcher"
            else:
                role = "fire_tracker"
            if callable(update_role):
                update_role(
                    uav_id,
                    role,
                    0.0,
                    source="scenario_init",
                    confidence=0.9,
                )
            if isinstance(managed_states, dict) and uav_id in managed_states:
                state = managed_states[uav_id]
                if hasattr(state, "role"):
                    state.role = role

    def _seed_fire_tracker_uavs(self) -> None:
        """Backward-compatible alias; roles assigned via _assign_uav_roles()."""
        self._assign_uav_roles()

    def _seed_victim_search_uav(self) -> None:
        """Backward-compatible alias; roles assigned via _assign_uav_roles()."""
        return

    def _init_managed_uav_states(self) -> None:
        self.managed_uav_states = {}
        for agent in self.schedule.agents:
            if type(agent) is not agents.UAV:
                continue
            uav_id = str(agent.unique_id)
            pos = getattr(agent, "pos", None)
            position = None if pos is None else (float(pos[0]), float(pos[1]))
            self.managed_uav_states[uav_id] = UAVExtensionState(
                uav_id=uav_id,
                position=position,
                battery_level=float(getattr(agent, "battery_level", 100.0)),
                battery_status=str(getattr(agent, "battery_status", "normal") or "normal"),
                role=getattr(agent, "role", None),
                assigned_task=getattr(agent, "assigned_task", None),
            )

    def _update_managed_uav_states_from_agents(self) -> None:
        if not hasattr(self, "managed_uav_states"):
            self._init_managed_uav_states()
        for agent in self.schedule.agents:
            if type(agent) is not agents.UAV:
                continue
            uav_id = str(agent.unique_id)
            state = self.managed_uav_states.get(uav_id)
            if state is None:
                continue
            pos = getattr(agent, "pos", None)
            state.position = None if pos is None else (float(pos[0]), float(pos[1]))
            state.battery_level = float(getattr(agent, "battery_level", state.battery_level))
            state.battery_status = str(
                getattr(agent, "battery_status", state.battery_status) or state.battery_status
            )
            if pos is not None:
                cell = (int(pos[0]), int(pos[1]))
                visit_key = (uav_id, cell[0], cell[1])
                self.uav_visit_counts[visit_key] = self.uav_visit_counts.get(visit_key, 0) + 1
                previous_cell = self._uav_prev_grid_positions.get(uav_id)
                if previous_cell is not None and previous_cell == cell:
                    self.uav_last_failed_dir[uav_id] = int(getattr(agent, "selected_dir", 0))
                else:
                    self.uav_last_failed_dir.pop(uav_id, None)
                self._uav_prev_grid_positions[uav_id] = cell

    def _gather_simulator_fire_observation_facts(self, current_time: float) -> list[dict]:
        """Collect ground-truth fire/smoke facts from the simulator (no knowledge mutation)."""
        facts: list[dict] = []
        ts = float(current_time)
        for agent in self.schedule.agents:
            if type(agent) is not agents.Fire:
                continue
            cell = agent.pos
            entry = {
                "cell": (int(cell[0]), int(cell[1])),
                "timestamp": ts,
                "burning": bool(agent.is_burning()),
                "smoke_active": bool(ACTIVATE_SMOKE and agent.smoke.is_smoke_active()),
            }
            facts.append(entry)
        return facts

    def _update_runtime_observations(self, current_time: float) -> list[dict]:
        """Compatibility hook: returns passive simulator facts only (does not update runtime knowledge)."""
        return self._gather_simulator_fire_observation_facts(current_time)

    def _max_uav_team_pairwise_distance(self, buffer: MonitoringBuffer) -> float:
        """Largest pairwise distance between UAVs from the latest global team summary (monitoring input)."""
        gs = buffer.global_snapshot
        if gs is None:
            return 0.0
        positions = (gs.uav_team_summary or {}).get("positions") or {}
        coords: list[tuple[float, float]] = []
        for v in positions.values():
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                coords.append((float(v[0]), float(v[1])))
        best = 0.0
        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                d = euclidean_distance(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
                if d > best:
                    best = d
        return best

    def _monitor_snapshot_dict(self, buffer: MonitoringBuffer) -> dict:
        """Normalize communication monitor snapshot to a dict from buffer or global summary."""
        cs = buffer.communication_snapshot
        if cs is not None:
            if isinstance(cs, dict):
                return dict(cs)
            return asdict(cs)
        if buffer.global_snapshot is not None:
            summary = buffer.global_snapshot.communication_summary or {}
            ms = summary.get("monitor_snapshot")
            if isinstance(ms, dict):
                return dict(ms)
        return {}

    def _communication_relay_needed_from_monitoring(self, buffer: MonitoringBuffer) -> bool:
        ms = self._monitor_snapshot_dict(buffer)
        if bool(ms.get("relay_needed", False)):
            return True
        return self._max_uav_team_pairwise_distance(buffer) > float(SECURITY_DISTANCE)

    @staticmethod
    def _cells_declared_in_local_observations(buffer: MonitoringBuffer) -> set[tuple[int, int]]:
        """Union of cells already reported by UAV LocalObservations (environment path must not duplicate these)."""
        out: set[tuple[int, int]] = set()
        for obs in buffer.local_observations.values():
            if not isinstance(obs, LocalObservation):
                continue
            for raw in obs.visible_fire_cells:
                out.add((int(raw[0]), int(raw[1])))
            for raw in obs.visible_smoke_cells:
                out.add((int(raw[0]), int(raw[1])))
            for neg in obs.negative_observations:
                if len(neg) < 1:
                    continue
                c = neg[0]
                out.add((int(c[0]), int(c[1])))
        return out

    def _apply_single_uav_observation_fire(self, obs: LocalObservation) -> None:
        """Apply UAV-local fire belief updates from LocalObservation fields only (no simulator re-query)."""
        src = obs.source or f"local_monitor:{obs.uav_id}"
        ts_obs = float(obs.timestamp)
        conf = float(obs.observation_confidence)

        for raw in obs.visible_fire_cells:
            cell = (int(raw[0]), int(raw[1]))
            self.fire_runtime_model.update_fire_observation(
                cell=cell,
                timestamp=ts_obs,
                source=src,
                confidence=conf,
                probability=1.0,
            )

        for raw in obs.visible_smoke_cells:
            cell = (int(raw[0]), int(raw[1]))
            self.fire_runtime_model.mark_smoke_obscured(
                cell=cell,
                timestamp=ts_obs,
                source=src,
                confidence=conf,
            )

        for neg in obs.negative_observations:
            if len(neg) < 2:
                continue
            raw_cell = neg[0]
            cell = (int(raw_cell[0]), int(raw_cell[1]))
            n_conf = float(neg[1])
            n_ts = float(neg[2]) if len(neg) > 2 else ts_obs
            self.fire_runtime_model.update_no_fire_observation(
                cell=cell,
                timestamp=n_ts,
                source=src,
                confidence=n_conf,
            )

    def _apply_single_uav_observation_visibility(self, obs: LocalObservation) -> None:
        """Apply UAV-local visibility updates from LocalObservation fields only (no simulator re-query)."""
        src = obs.source or f"local_monitor:{obs.uav_id}"
        ts_obs = float(obs.timestamp)

        for raw in obs.visible_fire_cells:
            cell = (int(raw[0]), int(raw[1]))
            self.visibility_model.update_visible_cell(
                cell=cell,
                timestamp=ts_obs,
                status=ObservationStatus.OBSERVED_FIRE,
                confidence=float(obs.observation_confidence),
                source=src,
            )

        for raw in obs.visible_smoke_cells:
            cell = (int(raw[0]), int(raw[1]))
            self.visibility_model.update_smoke_obscured_cell(
                cell=cell,
                timestamp=ts_obs,
                confidence=float(obs.observation_confidence),
                source=src,
            )

        for neg in obs.negative_observations:
            if len(neg) < 2:
                continue
            raw_cell = neg[0]
            cell = (int(raw_cell[0]), int(raw_cell[1]))
            n_conf = float(neg[1])
            self.visibility_model.update_visible_cell(
                cell=cell,
                timestamp=ts_obs,
                status=ObservationStatus.OBSERVED_NO_FIRE,
                confidence=n_conf,
                source=src,
            )

    def _apply_fire_updates(self, buffer: MonitoringBuffer, current_time: float) -> None:
        """Update fire runtime model only from monitoring buffer."""
        ts = float(current_time)
        for obs in buffer.local_observations.values():
            if not isinstance(obs, LocalObservation):
                continue
            self._apply_single_uav_observation_fire(obs)

        declared = self._cells_declared_in_local_observations(buffer)
        env_snap = self.environment_monitor.collect_environment_snapshot(self, ts)
        for fc in env_snap.get("fire_cells") or []:
            if len(fc) < 2:
                continue
            cell = (int(fc[0]), int(fc[1]))
            if cell in declared:
                continue
            self.fire_runtime_model.update_fire_observation(
                cell=cell,
                timestamp=ts,
                source="environment_monitor",
                confidence=0.72,
                probability=1.0,
            )
        for sc in env_snap.get("smoke_cells") or []:
            if len(sc) < 2:
                continue
            cell = (int(sc[0]), int(sc[1]))
            if cell in declared:
                continue
            self.fire_runtime_model.mark_smoke_obscured(
                cell=cell,
                timestamp=ts,
                source="environment_monitor",
                confidence=0.45,
            )

    def _apply_visibility_updates(self, buffer: MonitoringBuffer, current_time: float) -> None:
        """Update visibility model only from monitoring buffer."""
        ts = float(current_time)
        for obs in buffer.local_observations.values():
            if not isinstance(obs, LocalObservation):
                continue
            self._apply_single_uav_observation_visibility(obs)

        declared = self._cells_declared_in_local_observations(buffer)
        env_snap = self.environment_monitor.collect_environment_snapshot(self, ts)
        for fc in env_snap.get("fire_cells") or []:
            if len(fc) < 2:
                continue
            cell = (int(fc[0]), int(fc[1]))
            if cell in declared:
                continue
            self.visibility_model.update_visible_cell(
                cell=cell,
                timestamp=ts,
                status=ObservationStatus.OBSERVED_FIRE,
                confidence=0.72,
                source="environment_monitor",
            )
        for sc in env_snap.get("smoke_cells") or []:
            if len(sc) < 2:
                continue
            cell = (int(sc[0]), int(sc[1]))
            if cell in declared:
                continue
            self.visibility_model.update_smoke_obscured_cell(
                cell=cell,
                timestamp=ts,
                confidence=0.5,
                source="environment_monitor",
            )

    def _detect_victims_in_uav_radius(self) -> None:
        """Detect Victim Mesa agents when a UAV observes their cell."""
        uav_agents = [a for a in self.schedule.agents if type(a) is agents.UAV]
        victim_markers = getattr(self, "victim_marker_agents", {})
        t = float(self.evaluation_timesteps_counter)
        for uav in uav_agents:
            px, py = uav.pos
            for vid, marker in victim_markers.items():
                if marker.pos is None:
                    continue
                managed = (
                    self.managed_victims.get(vid)
                    if isinstance(getattr(self, "managed_victims", None), dict)
                    else None
                )
                if managed is not None:
                    if (
                        getattr(managed, "dead", False)
                        or getattr(managed, "cancelled", False)
                        or getattr(managed, "rescued", False)
                        or str(getattr(managed, "status", "")).lower()
                        in {"dead", "cancelled", "rescued", "unreachable"}
                    ):
                        continue
                marker_status = str(getattr(marker, "status", "") or "").lower()
                if marker_status in {"dead", "cancelled", "rescued", "unreachable"}:
                    continue
                vx, vy = marker.pos
                dist = ((px - vx) ** 2 + (py - vy) ** 2) ** 0.5
                if dist <= UAV_OBSERVATION_RADIUS:
                    already_known = vid in self.victim_runtime_model.victims
                    self.victim_runtime_model.update_detection(
                        victim_id=vid,
                        position=(float(vx), float(vy)),
                        timestamp=t,
                        source="uav_proximity",
                        confidence=0.75,
                    )
                    if not already_known:
                        require_fn = getattr(
                            self.victim_runtime_model, "require_confirmation", None
                        )
                        if callable(require_fn):
                            require_fn(vid)
                        if vid in self.managed_victims:
                            managed_victim = self.managed_victims[vid]
                            managed_victim.confirmed = True
                            managed_victim.confidence = 0.75
                        marker_ref = victim_markers.get(vid)
                        if marker_ref is not None:
                            marker_ref.status = "confirmed"
                        print(
                            f"[Victim Detection] step={int(t)} UAV-{uav.unique_id} "
                            f"detected {vid} at {(vx, vy)}"
                        )
                        uid = str(uav.unique_id)
                        uav_role = self._uav_assignment_role(uid) or ""
                        role_norm = uav_role.strip().lower()
                        if role_norm in {"victim_searcher", "victim_search"}:
                            ws = _wind_search_state(self, uid)
                            ws["searcher_victim_detections"] = (
                                int(ws.get("searcher_victim_detections", 0) or 0) + 1
                            )
                            ws["steps_since_detection"] = 0
                        elif role_norm == "fire_tracker":
                            for vs_id in resolve_victim_searcher_uav_ids(self):
                                vs_ws = _wind_search_state(self, vs_id)
                                vs_ws["fire_tracker_detection_boost"] = min(
                                    0.45,
                                    float(vs_ws.get("fire_tracker_detection_boost", 0.0) or 0.0)
                                    + 0.06,
                                )
                        self._enqueue_rescue_incident(
                            {
                                "type": "victim_confirmed",
                                "victim_id": vid,
                                "firefighter_id": None,
                                "reason": "initial",
                                "metadata": {"step": int(t), "source": "uav_proximity"},
                            }
                        )

    def _apply_victim_updates(self, buffer: MonitoringBuffer, current_time: float) -> None:
        """Update victim runtime model only from monitoring buffer."""
        ts = float(current_time)
        for obs in buffer.local_observations.values():
            if not isinstance(obs, LocalObservation):
                continue
            for vc in obs.visible_victim_candidates:
                vid = vc.get("victim_id")
                cell = vc.get("cell")
                if vid is None or cell is None or len(cell) < 2:
                    continue
                pos = (float(cell[0]), float(cell[1]))
                conf_v = float(vc.get("confidence") or 0.6)
                self.victim_runtime_model.update_detection(
                    victim_id=str(vid),
                    position=pos,
                    timestamp=ts,
                    source="uav_local_monitor",
                    confidence=max(0.0, min(1.0, conf_v)),
                )

    def _apply_uav_resource_updates(self, buffer: MonitoringBuffer, current_time: float) -> None:
        """Update UAV resource model only from monitoring buffer."""
        ts = float(current_time)
        for uav_id, obs in buffer.local_observations.items():
            if not isinstance(obs, LocalObservation):
                continue
            tc = obs.task_context or {}
            role = tc.get("role")
            assigned = tc.get("assigned_task")
            role_s = None if role is None else (role if isinstance(role, str) else str(role))
            task_s = None if assigned is None else (assigned if isinstance(assigned, str) else str(assigned))
            self.uav_resource_model.update_uav_state(
                uav_id=uav_id,
                timestamp=ts,
                current_position=(float(obs.current_position[0]), float(obs.current_position[1])),
                battery_level=obs.battery_level,
                battery_status=obs.battery_status or None,
                communication_status=obs.communication_status or None,
                drift_level=float(obs.drift_error),
                current_role=role_s,
                assigned_task=task_s,
                source="uav_local_monitor",
            )

    def _apply_communication_updates(self, buffer: MonitoringBuffer, current_time: float) -> None:
        """Map monitoring buffer communication views into CommunicationModel (strict Step 5 boundary)."""
        ts = float(current_time)
        cm = self.communication_model
        ms = self._monitor_snapshot_dict(buffer)

        relay = self._communication_relay_needed_from_monitoring(buffer)
        cm.mark_relay_needed(
            relay,
            timestamp=ts,
            source="monitoring_buffer",
            confidence=0.75,
        )

        if buffer.global_snapshot is not None:
            summary = buffer.global_snapshot.communication_summary or {}
            st = summary.get("state")
            if isinstance(st, dict):
                mode = st.get("communication_mode")
                if mode is not None:
                    cm.state.communication_mode = str(mode)

        from_monitor = float(ms.get("delivery_confidence", 0.0))

        failed_n = int(ms.get("failed", 0))
        delayed_n = int(ms.get("delayed", 0))
        if failed_n > 0 and cm.state.last_delivery_status.get("monitoring_aggregate_failures") != "failed":
            cm.update_message_result(
                message_id="monitoring_aggregate_failures",
                delivery_status="failed",
                timestamp=ts,
                critical=False,
                source="monitoring_buffer",
                confidence=0.7,
            )
        if delayed_n > 0 and cm.state.last_delivery_status.get("monitoring_aggregate_delays") != "delayed":
            cm.update_message_result(
                message_id="monitoring_aggregate_delays",
                delivery_status="delayed",
                timestamp=ts,
                critical=False,
                source="monitoring_buffer",
                confidence=0.65,
            )

        for uav_id, obs in buffer.local_observations.items():
            if not isinstance(obs, LocalObservation):
                continue
            mid = f"uav_{uav_id}_telemetry"
            cs_stat = (obs.communication_status or "").lower().strip()
            if cs_stat in ("failed", "lost", "error", "down"):
                want = "failed"
            elif cs_stat in ("delayed", "pending", "degraded"):
                want = "delayed"
            elif float(obs.drift_error) > 1.0:
                want = "failed"
            elif float(obs.drift_error) > 0.5:
                want = "delayed"
            else:
                want = "delivered"
            prev = cm.state.last_delivery_status.get(mid)
            if prev != want:
                cm.update_message_result(
                    mid,
                    want,
                    ts,
                    critical=False,
                    source="monitoring_buffer",
                    confidence=0.75,
                )

        obs_list = [o for o in buffer.local_observations.values() if isinstance(o, LocalObservation)]
        if obs_list:
            avg_drift = sum(float(o.drift_error) for o in obs_list) / float(len(obs_list))
            from_drift = max(0.0, min(1.0, 1.0 - min(1.0, avg_drift)))
            if from_monitor > 0.0:
                cm.state.delivery_confidence = max(
                    0.0, min(1.0, (from_monitor + from_drift) / 2.0)
                )
            else:
                cm.state.delivery_confidence = from_drift
        elif from_monitor > 0.0:
            cm.state.delivery_confidence = max(0.0, min(1.0, from_monitor))

        message_load = int(ms.get("failed", 0)) + int(ms.get("delayed", 0)) + int(ms.get("sent", 0))
        cm.state.link_quality_summary = {
            "delivery_confidence": float(cm.state.delivery_confidence or from_monitor or 0.0),
            "message_load": message_load,
            "degraded": float(cm.state.delivery_confidence or 0.0) < 0.5 or int(ms.get("failed", 0)) > 0,
            "relay_needed": bool(relay),
        }
        cm.step_index = int(getattr(self, "evaluation_timesteps_counter", cm.step_index) or cm.step_index)

    @staticmethod
    def _local_observation_to_report_kwargs(obs: LocalObservation) -> dict:
        """Map monitoring LocalObservation → LocalObservationModel.update_from_local_report kwargs."""
        oc = float(obs.observation_confidence)
        conf_patch: dict[tuple[int, int], float] = {}
        for raw in obs.visible_fire_cells:
            c = (int(raw[0]), int(raw[1]))
            conf_patch[c] = oc
        for raw in obs.visible_smoke_cells:
            c = (int(raw[0]), int(raw[1]))
            conf_patch[c] = oc

        unc_patch: dict[tuple[int, int], float] = {}
        u_score = max(0.0, 1.0 - oc)
        for raw in obs.local_uncertainty_patch:
            c = (int(raw[0]), int(raw[1]))
            unc_patch[c] = u_score

        neg_map: dict[tuple[int, int], str] = {}
        for neg in obs.negative_observations:
            if len(neg) < 2:
                continue
            raw_cell = neg[0]
            c = (int(raw_cell[0]), int(raw_cell[1]))
            neg_map[c] = "no_fire"

        cs = (obs.communication_status or "").lower().strip()
        comm_quality = oc
        if cs in ("failed", "lost", "error", "down"):
            comm_quality = min(comm_quality, 0.35)
        elif cs in ("delayed", "pending", "degraded"):
            comm_quality = min(comm_quality, 0.55)

        drift = float(obs.drift_error)
        if drift <= 0.25:
            drift_label = "nominal"
        elif drift <= 0.75:
            drift_label = "moderate"
        else:
            drift_label = "high"

        return {
            "timestamp": float(obs.timestamp),
            "visible_fire_cells": {(int(a[0]), int(a[1])) for a in obs.visible_fire_cells},
            "visible_smoke_cells": {(int(a[0]), int(a[1])) for a in obs.visible_smoke_cells},
            "visible_victim_candidates": list(obs.visible_victim_candidates),
            "local_confidence_patch": conf_patch,
            "local_uncertainty_patch": unc_patch,
            "nearby_uavs": set(obs.nearby_uavs),
            "local_comm_quality": comm_quality,
            "local_drift_state": drift_label,
            "local_battery_state": obs.battery_status or None,
            "current_task_context": dict(obs.task_context or {}),
            "negative_local_observations": neg_map,
            "source": obs.source or "local_monitor",
            "confidence": float(obs.confidence) if obs.confidence is not None else oc,
        }

    def _apply_local_observation_model_reports(self, buffer: MonitoringBuffer) -> None:
        """Sync each LocalObservationModel from buffer.local_observations (no simulator re-query)."""
        for uav_id, obs in buffer.local_observations.items():
            if not isinstance(obs, LocalObservation):
                continue
            local_model = self.local_observation_models.get(str(uav_id))
            if local_model is None:
                continue
            kwargs = self._local_observation_to_report_kwargs(obs)
            local_model.update_from_local_report(**kwargs)

    @staticmethod
    def _coords_pair(value: Any) -> tuple[float, float] | None:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return (float(value[0]), float(value[1]))
        return None

    def _resolve_uav_path_context_target(self, uav_id: str) -> tuple[float, float] | None:
        planning = getattr(self, "latest_planning_result", None)
        if isinstance(planning, dict):
            path_decisions = planning.get("path_decisions")
            if isinstance(path_decisions, dict) and uav_id in path_decisions:
                decision = path_decisions[uav_id]
                if decision is not None:
                    ctx = getattr(decision, "uncertainty_context", None) or {}
                    if isinstance(ctx, dict):
                        for key in ("target_position", "target_region", "target_location"):
                            coords = self._coords_pair(ctx.get(key))
                            if coords is not None:
                                return coords
                    for key in ("target_position", "target_region", "waypoints"):
                        coords = self._coords_pair(getattr(decision, key, None))
                        if coords is not None:
                            return coords
        execution = getattr(self, "latest_execution_result", None)
        if isinstance(execution, dict):
            for section_name in ("local", "fail_safe"):
                section = execution.get(section_name)
                if not isinstance(section, dict):
                    continue
                uav_results = section.get("uav_results")
                if not isinstance(uav_results, dict):
                    continue
                uav_result = uav_results.get(uav_id)
                if not isinstance(uav_result, dict):
                    continue
                for key in ("target_position", "target_region", "target"):
                    coords = self._coords_pair(uav_result.get(key))
                    if coords is not None:
                        return coords
        return self._uav_last_targets.get(uav_id)

    def _resolve_uav_path_context_action(self, uav_id: str, agent: Any) -> str | None:
        execution = getattr(self, "latest_execution_result", None)
        if isinstance(execution, dict):
            for section_name in ("local", "fail_safe"):
                section = execution.get(section_name)
                if not isinstance(section, dict):
                    continue
                uav_results = section.get("uav_results")
                if not isinstance(uav_results, dict):
                    continue
                uav_result = uav_results.get(uav_id)
                if isinstance(uav_result, dict):
                    action = uav_result.get("action") or uav_result.get("next_action")
                    if action:
                        return str(action)
        execution_action = getattr(agent, "execution_action", None)
        if execution_action:
            return str(execution_action)
        direction_map = {0: "east", 1: "south", 2: "west", 3: "north"}
        selected = getattr(agent, "selected_dir", None)
        if selected is not None:
            return direction_map.get(int(selected) % 4, str(selected))
        return None

    def _hazard_pressure_for_uav(
        self,
        cell: tuple[int, int],
        local_obs_model: LocalObservationModel | None,
    ) -> tuple[float, float]:
        cx, cy = int(cell[0]), int(cell[1])
        fire_pressure = 0.0
        smoke_pressure = 0.0
        if local_obs_model is not None:
            for fire_cell in local_obs_model.visible_fire_cells:
                dist = max(abs(int(fire_cell[0]) - cx), abs(int(fire_cell[1]) - cy))
                if dist <= 4:
                    fire_pressure = max(fire_pressure, 1.0 - (dist / 4.0))
            for smoke_cell in local_obs_model.visible_smoke_cells:
                dist = max(abs(int(smoke_cell[0]) - cx), abs(int(smoke_cell[1]) - cy))
                if dist <= 4:
                    smoke_pressure = max(smoke_pressure, 1.0 - (dist / 4.0))
        fire_model = getattr(self, "fire_runtime_model", None)
        if fire_model is not None:
            belief = getattr(fire_model, "belief", None)
            if belief is not None:
                if (cx, cy) in getattr(belief, "estimated_burning_cells", set()):
                    fire_pressure = max(fire_pressure, 0.9)
                prob_map = getattr(belief, "fire_probability_map", {})
                if isinstance(prob_map, dict):
                    fire_pressure = max(
                        fire_pressure,
                        float(prob_map.get((cx, cy), 0.0) or 0.0) * 0.75,
                    )
        visibility_model = getattr(self, "visibility_model", None)
        if visibility_model is not None:
            state = getattr(visibility_model, "state", None)
            smoke_cells = getattr(state, "smoke_obscured_cells", set()) if state else set()
            if (cx, cy) in smoke_cells:
                smoke_pressure = max(smoke_pressure, 0.85)
        return fire_pressure, smoke_pressure

    @staticmethod
    def _boundary_pressure_for_cell(cell: tuple[int, int]) -> float:
        cx, cy = int(cell[0]), int(cell[1])
        margin = 3
        dist_to_edge = min(cx, cy, HEIGHT - 1 - cx, WIDTH - 1 - cy)
        if dist_to_edge >= margin:
            return 0.0
        return max(0.0, (margin - dist_to_edge) / float(margin))

    def _refresh_local_path_context_models(self, current_step_time: float) -> None:
        """Refresh per-UAV LocalPathContextModel from live execution/runtime state."""
        if not hasattr(self, "local_path_context_models"):
            return
        if not hasattr(self, "_uav_position_history"):
            self._uav_position_history = {}
        if not hasattr(self, "_uav_direction_history"):
            self._uav_direction_history = {}
        if not hasattr(self, "_uav_last_targets"):
            self._uav_last_targets = {}
        if not hasattr(self, "_uav_target_switch_counts"):
            self._uav_target_switch_counts = {}

        stuck_counts = getattr(self, "_uav_stuck_counts", {}) or {}
        sector_assignments = getattr(self, "_uav_sector_assignments", {}) or {}
        buffer = getattr(self, "monitoring_buffer", None)
        buffer_obs: dict[str, LocalObservation] = {}
        if buffer is not None:
            raw = getattr(buffer, "local_observations", {}) or {}
            buffer_obs = {
                str(uav_id): obs
                for uav_id, obs in raw.items()
                if isinstance(obs, LocalObservation)
            }

        for agent in self.schedule.agents:
            if type(agent) is not agents.UAV:
                continue
            uav_id = str(agent.unique_id)
            path_model = self.local_path_context_models.get(uav_id)
            if path_model is None:
                continue
            pos = getattr(agent, "pos", None)
            position = None if pos is None else (float(pos[0]), float(pos[1]))
            grid_cell = None if pos is None else (int(pos[0]), int(pos[1]))
            selected_dir = int(getattr(agent, "selected_dir", 0) or 0)

            history = list(self._uav_position_history.get(uav_id, []))
            if grid_cell is not None:
                if not history or history[-1] != grid_cell:
                    history.append(grid_cell)
            history = history[-8:]
            self._uav_position_history[uav_id] = history

            dir_history = list(self._uav_direction_history.get(uav_id, []))
            dir_history.append(selected_dir)
            dir_history = dir_history[-8:]
            self._uav_direction_history[uav_id] = dir_history

            current_target = self._resolve_uav_path_context_target(uav_id)
            previous_target = self._uav_last_targets.get(uav_id)
            switch_count = int(self._uav_target_switch_counts.get(uav_id, 0) or 0)
            if (
                current_target is not None
                and previous_target is not None
                and current_target != previous_target
            ):
                switch_count += 1
            if current_target is not None:
                self._uav_last_targets[uav_id] = current_target
            self._uav_target_switch_counts[uav_id] = switch_count

            local_obs_model = self.local_observation_models.get(uav_id)
            obs = buffer_obs.get(uav_id)
            if obs is not None and grid_cell is None:
                grid_cell = (int(obs.current_position[0]), int(obs.current_position[1]))
                position = (float(grid_cell[0]), float(grid_cell[1]))
            fire_pressure, smoke_pressure = (
                self._hazard_pressure_for_uav(grid_cell, local_obs_model)
                if grid_cell is not None
                else (0.0, 0.0)
            )
            congestion = 0.0
            if local_obs_model is not None and local_obs_model.nearby_uavs:
                congestion = min(1.0, len(local_obs_model.nearby_uavs) / 3.0)
            elif obs is not None and obs.nearby_uavs:
                congestion = min(1.0, len(obs.nearby_uavs) / 3.0)
            boundary = (
                self._boundary_pressure_for_cell(grid_cell) if grid_cell is not None else 0.0
            )

            resource_state = self.uav_resource_model.by_uav_id.get(uav_id)
            drift_level = 0.0
            local_plan_reliability = None
            if resource_state is not None:
                if resource_state.drift_level is not None:
                    drift_level = float(resource_state.drift_level)
                if resource_state.local_plan_reliability is not None:
                    local_plan_reliability = float(resource_state.local_plan_reliability)
            if obs is not None:
                drift_level = max(drift_level, min(1.0, float(obs.drift_error)))

            sector_bounds = sector_assignments.get(uav_id)
            sector_alignment = LocalPathContextModel.compute_sector_alignment_score(
                position,
                sector_bounds if isinstance(sector_bounds, dict) else None,
            )
            move_x = [1, 0, -1, 0]
            move_y = [0, -1, 0, 1]
            candidate_moves: list[tuple[float, float]] = []
            if position is not None:
                px, py = position
                for direction in range(4):
                    candidate_moves.append(
                        (px + move_x[direction], py + move_y[direction])
                    )

            wind_state = _wind_search_state(self, uav_id)
            path_model.refresh_from_runtime(
                timestamp=float(current_step_time),
                position=position,
                selected_direction=selected_dir,
                current_action=self._resolve_uav_path_context_action(uav_id, agent),
                current_target=current_target,
                last_positions=[(float(x), float(y)) for x, y in history],
                last_directions=dir_history,
                stuck_count=int(stuck_counts.get(uav_id, 0) or 0),
                target_switch_count=switch_count,
                nearby_fire=fire_pressure,
                nearby_smoke=smoke_pressure,
                congestion_pressure=congestion,
                boundary_pressure=boundary,
                drift_level=drift_level,
                sector_alignment_score=sector_alignment,
                local_plan_reliability=local_plan_reliability,
                candidate_moves=candidate_moves,
                wind_edge_streak=int(wind_state.get("edge_streak", 0) or 0),
                wind_hold_streak=int(wind_state.get("hold_streak", 0) or 0),
                wind_same_target_streak=int(wind_state.get("same_target_streak", 0) or 0),
                wind_aware_hold_streak=int(wind_state.get("wind_aware_hold_streak", 0) or 0),
                corridor_targets=list(wind_state.get("corridor_targets") or []),
                corridor_index=int(wind_state.get("corridor_index", 0) or 0),
                recent_corridor_targets=list(wind_state.get("recent_corridor_targets") or []),
                force_wind_retarget=bool(wind_state.get("force_interior_retarget")),
                force_wind_sweep=bool(wind_state.get("force_sweep")),
                pocket_streak=int(wind_state.get("pocket_streak", 0) or 0),
                coverage_priority=float(wind_state.get("coverage_priority", 0.0) or 0.0),
                hazard_buffer_level=int(wind_state.get("hazard_buffer_level", 0) or 0),
                force_coverage_escape=bool(wind_state.get("force_coverage_escape")),
                post_rescue_coverage_steps_remaining=int(
                    wind_state.get("post_rescue_coverage_steps_remaining", 0) or 0
                ),
                unresolved_victim_count=int(
                    wind_state.get("unresolved_victim_count", 0) or 0
                ),
                recent_x_positions=[
                    int(x) for x in (wind_state.get("recent_x_positions") or [])
                ],
                source="wildfire_model_step",
            )

    def _rebuild_shared_operational_picture(self, current_step_time: float, global_snapshot: Any) -> None:
        """Fused operational picture from runtime models after knowledge updates."""
        alerts = None
        if global_snapshot is not None and getattr(global_snapshot, "event_flags", None):
            ef = global_snapshot.event_flags
            if ef:
                alerts = [{"level": "info", "event_flags": dict(ef)}]

        self.shared_operational_picture.rebuild_from_models(
            step_index=int(current_step_time),
            fire_model=self.fire_runtime_model,
            visibility_model=self.visibility_model,
            victim_model=self.victim_runtime_model,
            uav_model=self.uav_resource_model,
            firefighter_model=self.firefighter_model,
            communication_model=self.communication_model,
            active_alerts=alerts,
            mission_mode=None,
            active_adaptation_state="monitoring",
            source="wildfire_model_step5",
            timestamp=float(current_step_time),
        )
        wind_summary = self._wind_summary_for_operational_picture(global_snapshot)
        if wind_summary:
            layers = dict(getattr(self.shared_operational_picture, "layers", {}) or {})
            layers["environment"] = {"wind": dict(wind_summary)}
            self.shared_operational_picture.layers = layers

    def _wind_summary_for_operational_picture(
        self, global_snapshot: Any | None = None
    ) -> dict[str, Any]:
        """Prefer native global snapshot wind; fall back to EnvironmentBridge."""
        if global_snapshot is not None:
            direction = str(getattr(global_snapshot, "wind_direction", "") or "").strip()
            if direction:
                raw_vector = getattr(global_snapshot, "wind_vector", None)
                if isinstance(raw_vector, (list, tuple)) and len(raw_vector) >= 2:
                    vector = [float(raw_vector[0]), float(raw_vector[1])]
                else:
                    vector = list(wind_vector_from_direction(direction))
                return {
                    "direction": direction,
                    "wind_direction": direction,
                    "vector": vector,
                    "wind_vector": vector,
                    "timestamp": float(getattr(global_snapshot, "wind_timestamp", 0.0) or 0.0),
                    "step": int(getattr(global_snapshot, "observation_step", 0) or 0),
                    "source": str(getattr(global_snapshot, "wind_source", "") or "global_monitor"),
                }
        bridge_summary = self.environment_bridge.get_wind_summary()
        return dict(bridge_summary) if bridge_summary else {}

    def _sync_environment_wind(self, current_step_time: float) -> None:
        """Publish wind spread direction to EnvironmentBridge before MAPE-K cycle."""
        wind_agent = getattr(self, "wind", None)
        raw_dir = getattr(wind_agent, "wind_direction", None) if wind_agent else None
        if raw_dir is None:
            raw_dir = WIND_DIRECTION
        direction = normalize_wind_direction(raw_dir)
        vector = wind_vector_from_direction(direction)
        step = int(getattr(self, "evaluation_timesteps_counter", 0) or 0)
        self.environment_bridge.update_wind(
            direction,
            vector,
            float(current_step_time),
            step=step,
            source="fire_model",
        )
        if getattr(self, "debug_log", False):
            print(
                f"[Environment] wind_direction={direction} "
                f"wind_vector={vector} step={step}"
            )

    def _run_analysis(self, current_step_time: float, global_snapshot: Any) -> None:
        """Step 6: structured analysis only (triggers/snapshots); no movement or planning."""
        buf = self.monitoring_buffer
        snap_dict: dict[str, Any] = (
            asdict(global_snapshot) if global_snapshot is not None else {}
        )
        if global_snapshot is not None and getattr(global_snapshot, "wind_direction", ""):
            snap_dict["wind"] = {
                "direction": global_snapshot.wind_direction,
                "wind_direction": global_snapshot.wind_direction,
                "vector": list(global_snapshot.wind_vector),
                "wind_vector": list(global_snapshot.wind_vector),
                "timestamp": float(global_snapshot.wind_timestamp),
                "step": int(global_snapshot.observation_step),
                "source": global_snapshot.wind_source,
            }
        else:
            wind_summary = self.environment_bridge.get_wind_summary()
            if wind_summary:
                snap_dict["wind"] = dict(wind_summary)
                snap_dict["wind_direction"] = wind_summary.get("direction")
                snap_dict["wind_vector"] = wind_summary.get("vector")
        runtime_models: dict[str, Any] = {
            "fire_runtime_model": self.fire_runtime_model,
            "visibility_model": self.visibility_model,
            "victim_runtime_model": self.victim_runtime_model,
            "uav_resource_model": self.uav_resource_model,
            "communication_model": self.communication_model,
            "firefighter_model": self.firefighter_model,
        }

        local_results: list[Any] = []
        for uav_id in sorted(self.local_observation_models.keys()):
            obs = buf.local_observations.get(uav_id)
            latest: dict[str, Any] = asdict(obs) if isinstance(obs, LocalObservation) else {}
            st = self.uav_resource_model.by_uav_id.get(uav_id)
            if st is None:
                continue
            loc_obs = self.local_observation_models[uav_id]
            loc_path = self.local_path_context_models[uav_id]
            local_results.append(
                self.local_uav_analyzer.analyze(
                    uav_id,
                    loc_obs,
                    loc_path,
                    st,
                    latest,
                    float(current_step_time),
                )
            )

        global_result = self.global_analyzer.analyze(
            self.shared_operational_picture,
            snap_dict,
            runtime_models,
            float(current_step_time),
        )

        all_triggers_list: list[Any] = []
        for lr in local_results:
            all_triggers_list.extend(lr.local_trigger_list)
        all_triggers_list.extend(global_result.trigger_list)
        if self.evaluation_timesteps_counter < LAUNCH_GRACE_STEPS:
            all_triggers_list = [
                trigger
                for trigger in all_triggers_list
                if str(getattr(trigger, "trigger_type", "")).upper()
                != "COLLISION_RISK"
            ]
        all_triggers_tuple = tuple(all_triggers_list)
        dashboard_summary = build_dashboard_summary(
            tuple(local_results), global_result, all_triggers_tuple
        )

        self.latest_analysis_snapshot = AnalysisSnapshot(
            timestamp=float(current_step_time),
            local_results=tuple(local_results),
            global_result=global_result,
            all_triggers=all_triggers_tuple,
            dashboard_summary=dashboard_summary,
        )

    def _run_adaptation_space_generation(self) -> None:
        """Step 7: generate/filter adaptation option spaces only; no ranking or execution."""
        analysis_snapshot = self.latest_analysis_snapshot
        if analysis_snapshot is None:
            self.latest_adaptation_space_snapshot = None
            return

        timestamp = float(analysis_snapshot.timestamp)
        runtime_models: dict[str, Any] = {
            "fire_runtime_model": self.fire_runtime_model,
            "visibility_model": self.visibility_model,
            "victim_runtime_model": self.victim_runtime_model,
            "uav_resource_model": self.uav_resource_model,
            "communication_model": self.communication_model,
            "firefighter_model": self.firefighter_model,
            "mission_goal_model": self.mission_goal_model,
            "local_path_context_models": self.local_path_context_models,
            "available_entities": list(self.local_observation_models.keys()),
            "global_observation_snapshot": self.latest_global_snapshot,
            "simulation_model": self,
        }
        runtime_models["mission_goals"] = self.mission_goal_model.runtime_context()

        local_spaces = []
        for local_result in analysis_snapshot.local_results:
            local_input = local_result.to_dict()
            # Canonical trigger contract: ``trigger_batch``; legacy fields kept for adapters.
            local_input["trigger_batch"] = local_result.trigger_batch
            local_input["triggers"] = local_result.local_trigger_list
            local_input["all_triggers"] = analysis_snapshot.all_triggers
            local_input["target_entity"] = local_result.uav_id
            local_models = {
                "local_observation_model": self.local_observation_models.get(local_result.uav_id),
                "local_path_context_model": self.local_path_context_models.get(local_result.uav_id),
            }
            local_runtime_models = {**runtime_models, "uav_id": local_result.uav_id}
            local_spaces.append(
                self.local_adaptation_generator.generate(
                    local_input,
                    local_models,
                    local_runtime_models,
                    timestamp,
                )
            )

        global_input = analysis_snapshot.global_result.to_dict()
        # Canonical trigger contract: ``trigger_batch``; legacy fields kept for adapters.
        global_input["trigger_batch"] = analysis_snapshot.global_result.trigger_batch
        global_input["triggers"] = analysis_snapshot.global_result.trigger_list
        global_input["all_triggers"] = analysis_snapshot.all_triggers
        global_input["target_entity"] = "mission"
        global_space = self.global_adaptation_generator.generate(
            global_input,
            runtime_models,
            timestamp,
        )

        shared_input = {
            # Canonical trigger contract: ``trigger_batch``; legacy fields kept for adapters.
            "trigger_batch": analysis_snapshot.trigger_batch,
            "triggers": analysis_snapshot.all_triggers,
            "all_triggers": analysis_snapshot.all_triggers,
            "target_entity": "mission",
            "dashboard_summary": analysis_snapshot.dashboard_summary,
            "global_result": analysis_snapshot.global_result,
        }
        rescue_space = self.rescue_adaptation_generator.generate(
            shared_input,
            runtime_models,
            timestamp,
        )
        fail_safe_space = self.failsafe_adaptation_generator.generate(
            shared_input,
            runtime_models,
            timestamp,
        )
        communication_input = {
            **shared_input,
            "communication_reliability": float(
                getattr(self.communication_model.state, "delivery_confidence", 0.75) or 0.75
            ),
            "delivery_confidence": float(
                getattr(self.communication_model.state, "delivery_confidence", 0.75) or 0.75
            ),
        }
        communication_space = self.communication_adaptation_generator.generate(
            communication_input,
            runtime_models,
            timestamp,
        )
        self.latest_communication_adaptation_space = communication_space

        generated_options = collect_all_options(
            local_spaces=local_spaces,
            global_space=global_space,
            rescue_space=rescue_space,
            fail_safe_space=fail_safe_space,
        )
        generated_options.extend(communication_space.options)
        filtered_options = self.constraint_filter.filter_options(
            generated_options,
            runtime_models,
            self.mission_goal_model,
        )
        kept_option_ids = {id(option) for option in filtered_options}
        for space in local_spaces:
            space.options = [option for option in space.options if id(option) in kept_option_ids]
        global_space.options = [
            option for option in global_space.options if id(option) in kept_option_ids
        ]
        rescue_space.options = [
            option for option in rescue_space.options if id(option) in kept_option_ids
        ]
        fail_safe_space.options = [
            option for option in fail_safe_space.options if id(option) in kept_option_ids
        ]
        communication_space.options = [
            option for option in communication_space.options if id(option) in kept_option_ids
        ]
        self.latest_communication_adaptation_space = communication_space

        trigger_references = [
            signal.name for signal in analysis_snapshot.trigger_batch.triggers
        ]
        explanation_summaries = [
            f"generated_options={len(generated_options)}",
            f"kept_options={len(filtered_options)}",
            f"removed_options={len(self.constraint_filter.rejected_options)}",
            f"communication_options={len(communication_space.options)}",
        ]
        adaptation_dashboard_summary = build_adaptation_dashboard_summary(
            filtered_options,
            trigger_references=trigger_references,
            rejected_count=len(self.constraint_filter.rejected_options),
        )

        self.latest_adaptation_space_snapshot = AdaptationSpaceSnapshot(
            local_spaces=local_spaces,
            global_space=global_space,
            rescue_space=rescue_space,
            fail_safe_space=fail_safe_space,
            all_options=filtered_options,
            dashboard_summary=adaptation_dashboard_summary,
            trigger_references=trigger_references,
            explanation_summaries=explanation_summaries,
            timestamp=timestamp,
        )

    def _run_planning(self, current_step_time: float) -> None:
        """Step 9: structured planning only; no execution or dispatch."""
        if self.latest_analysis_snapshot is None or self.latest_adaptation_space_snapshot is None:
            self.latest_planning_result = None
            return

        runtime_models: dict[str, Any] = {
            "fire_runtime_model": self.fire_runtime_model,
            "visibility_model": self.visibility_model,
            "victim_runtime_model": self.victim_runtime_model,
            "uav_resource_model": self.uav_resource_model,
            "communication_model": self.communication_model,
            "firefighter_model": self.firefighter_model,
            "mission_goal_model": self.mission_goal_model,
            "mission_goals": self.mission_goal_model.runtime_context(),
            "local_path_context_models": self.local_path_context_models,
            "available_entities": list(self.local_observation_models.keys()),
            "communication_adaptation_space": self.latest_communication_adaptation_space,
            "latest_failsafe_state": self.latest_failsafe_state,
            "simulation_model": self,
        }
        self.latest_planning_result = self.planning_coordinator.run_planning(
            self.latest_adaptation_space_snapshot,
            self.latest_analysis_snapshot,
            runtime_models=runtime_models,
            timestamp=float(current_step_time),
        )

    def _run_execution(self, current_step_time: float) -> None:
        """Step 10: dispatch planning decisions to executors (no direct movement)."""
        if self.latest_planning_result is None:
            self.latest_execution_result = {
                "applied": False,
                "reason": "no_planning_result",
            }
        else:
            self.latest_execution_result = self.decision_dispatcher.dispatch(
                self.latest_planning_result,
                timestamp=float(current_step_time),
            )
        comm_section = (
            self.latest_execution_result.get("communication")
            if isinstance(self.latest_execution_result, dict)
            else None
        )
        if isinstance(comm_section, dict):
            self.latest_communication_execution = {
                "timestamp": float(current_step_time),
                **comm_section,
            }
        self.latest_execution_feedback_event = self._build_execution_feedback_event(
            self.latest_execution_result,
            float(current_step_time),
        )

    def _update_failsafe_mode(self, current_step_time: float) -> None:
        runtime_models: dict[str, Any] = {
            "fire_runtime_model": getattr(self, "fire_runtime_model", None),
            "visibility_model": getattr(self, "visibility_model", None),
            "victim_runtime_model": getattr(self, "victim_runtime_model", None),
            "uav_resource_model": getattr(self, "uav_resource_model", None),
            "communication_model": getattr(self, "communication_model", None),
            "firefighter_model": getattr(self, "firefighter_model", None),
            "mission_goal_model": getattr(self, "mission_goal_model", None),
            "available_entities": list(getattr(self, "local_observation_models", {}).keys()),
        }
        self.latest_failsafe_state = self.mode_manager.update(
            analysis_snapshot=self.latest_analysis_snapshot,
            planning_result=self.latest_planning_result,
            execution_result=self.latest_execution_result,
            runtime_models=runtime_models,
            timestamp=float(current_step_time),
        )
        self.latest_failsafe_dashboard_summary = build_failsafe_dashboard_summary(
            self.latest_failsafe_state
        )
        self._refresh_mission_goal_model(current_step_time)
        sop = getattr(self, "shared_operational_picture", None)
        if sop is None or self.latest_failsafe_state is None:
            return
        if self.latest_failsafe_state.mode != FailSafeMode.NORMAL:
            if hasattr(sop, "mission_mode"):
                sop.mission_mode = self.latest_failsafe_state.mode.value
            if hasattr(sop, "active_adaptation_state"):
                sop.active_adaptation_state = self.latest_failsafe_state.explanation

    def _build_execution_feedback_event(
        self,
        result: dict[str, object] | None,
        timestamp: float,
    ) -> dict[str, object]:
        affected_entities: set[str] = set()
        search_mode_active = False

        if isinstance(result, dict):
            for section_name in ("fail_safe", "local"):
                section = result.get(section_name)
                if not isinstance(section, dict):
                    continue
                uav_results = section.get("uav_results")
                if not isinstance(uav_results, dict):
                    continue
                for uav_id, uav_result in uav_results.items():
                    affected_entities.add(str(uav_id))
                    if (
                        isinstance(uav_result, dict)
                        and uav_result.get("action") == "search_mode"
                    ):
                        search_mode_active = True

            global_section = result.get("global")
            if isinstance(global_section, dict):
                for uav_id in global_section.get("assignments", {}):
                    affected_entities.add(str(uav_id))
                for uav_id in global_section.get("task_assignments", {}):
                    affected_entities.add(str(uav_id))

            rescue_section = result.get("rescue")
            if isinstance(rescue_section, dict):
                payload = rescue_section.get("payload")
                if isinstance(payload, dict):
                    for key in ("victim_id", "firefighter_id"):
                        entity_id = payload.get(key)
                        if entity_id:
                            affected_entities.add(str(entity_id))

        planning = self.latest_planning_result
        if planning is not None:
            fail_safe_decision = (
                planning.get("fail_safe_decision")
                if isinstance(planning, dict)
                else getattr(planning, "fail_safe_decision", None)
            )
            if fail_safe_decision is not None and bool(
                getattr(fail_safe_decision, "search_mode_active", False)
            ):
                search_mode_active = True

        feedback: dict[str, object] = {
            "timestamp": timestamp,
            "result": result if result is not None else {},
            "execution_log_count": len(self.execution_log.entries),
            "affected_entities": sorted(affected_entities),
        }
        if search_mode_active:
            feedback["search_mode_active"] = True
        return feedback

    def _apply_monitoring_to_knowledge(self, buffer: MonitoringBuffer, current_time: float) -> None:
        """Consume monitoring buffer → runtime knowledge (MAPE-K boundary)."""
        self._apply_fire_updates(buffer, current_time)
        self._apply_visibility_updates(buffer, current_time)
        self._apply_victim_updates(buffer, current_time)
        self._apply_uav_resource_updates(buffer, current_time)
        self._apply_communication_updates(buffer, current_time)
        self._apply_local_observation_model_reports(buffer)

    # function that creates all fire agents in a grid
    def set_fire_agents(self):
        margin = 10
        x_c = SYSTEM_RANDOM.randint(margin, HEIGHT - margin - 1)
        y_c = SYSTEM_RANDOM.randint(margin, WIDTH - margin - 1)
        x = [x_c]
        y = [y_c]
        for i in range(HEIGHT):
            for j in range(WIDTH):
                # decides to put a "tree" (fire agent) or not, if less than DENSITY_PROB
                # or if it is in the center of the grid
                if SYSTEM_RANDOM.random() < DENSITY_PROB or (i in x and j in y):
                    # only if it is in the center of the grid, Fire agent is set burning at the beginning, otherwise
                    # it is set to not burning
                    if i in x and j in y:
                        self.new_fire_agent(i, j, True)
                    else:
                        self.new_fire_agent(i, j, False)

    # function that creates new fire agent in a concrete cell
    def new_fire_agent(self, pos_x, pos_y, burning):
        # creates new Fire agent
        source_fire = agents.Fire(self.unique_agents_id, self, burning)
        # set Fire agent unique id, incremented from the one used before it
        self.unique_agents_id += 1
        # add to scheduler
        self.schedule.add(source_fire)
        # place agent in the grid
        self.grid.place_agent(source_fire, tuple([pos_x, pos_y]))

    # manage directions obtained from the new_direction attribute, and make the UAV team move over the forest area
    def set_drone_dirs(self):
        # used for selecting the corresponding direction from new_direction attribute, for each UAV
        self.new_direction_counter = 0
        # searches for all UAV agents in scheduler, and set their new directions
        for agent in self.schedule.agents:
            if type(agent) is agents.UAV:
                agent.selected_dir = self.new_direction[self.new_direction_counter]
                self.new_direction_counter += 1

    def _has_pending_execution_directions(self) -> bool:
        """True when prior-step execution produced UAV direction commands to honor."""
        result = self.latest_execution_result
        if not isinstance(result, dict):
            return False
        for section_name in ("fail_safe", "local"):
            section = result.get(section_name)
            if not isinstance(section, dict):
                continue
            uav_results = section.get("uav_results")
            if not isinstance(uav_results, dict):
                continue
            for uav_result in uav_results.values():
                if (
                    isinstance(uav_result, dict)
                    and uav_result.get("applied") is True
                    and "selected_dir" in uav_result
                ):
                    return True
        return False

    def _sync_new_direction_from_uav_selected_dirs(self) -> None:
        """Mirror executed UAV selected_dir into new_direction for MR metrics."""
        synced: list[int] = []
        for agent in self.schedule.agents:
            if type(agent) is agents.UAV:
                synced.append(int(getattr(agent, "selected_dir", 0)))
        if len(synced) < self.NUM_AGENTS:
            pad_source = list(getattr(self, "new_direction", []) or [])
            while len(synced) < self.NUM_AGENTS:
                synced.append(pad_source[len(synced)] if len(synced) < len(pad_source) else 0)
        elif len(synced) > self.NUM_AGENTS:
            synced = synced[: self.NUM_AGENTS]
        self.new_direction = synced

    def _is_extension_pipeline_active(self) -> bool:
        """True when self-adaptive MAPE execution drives UAV movement."""
        return getattr(self, "decision_dispatcher", None) is not None

    def _clear_uav_execution_direction_flags(self) -> None:
        for agent in self.schedule.agents:
            if type(agent) is agents.UAV:
                agent.execution_direction_applied = False
                agent.execution_action = None

    def _prepare_uav_directions_for_step(self) -> None:
        """Set movement intent for this step; never random when extension pipeline is active."""
        if self._is_extension_pipeline_active():
            self._sync_new_direction_from_uav_selected_dirs()
            return
        if self._has_pending_execution_directions():
            self._sync_new_direction_from_uav_selected_dirs()
            return
        self.new_direction = [
            SYSTEM_RANDOM.choice(range(0, N_ACTIONS))
            for _ in range(0, self.NUM_AGENTS)
        ]
        self.set_drone_dirs()

    def _run_pre_move_decision_cycle(self, current_step_time: float) -> None:
        _ = current_step_time
        self.latest_adaptation_cycle_result = self.adaptation_manager.run_cycle(
            self,
            phase="pre_move",
        )

    def _run_post_move_decision_cycle(self, current_step_time: float) -> None:
        self.latest_post_move_cycle_result = self.adaptation_manager.run_cycle(
            self,
            phase="post_move",
        )

    def _recycle_firefighter_after_exit(self, ff_marker: Any) -> None:
        """Return a firefighter that exited with a victim to available standby at the edge."""
        ff_id = self._firefighter_id_from_marker(ff_marker)
        standby_pos = getattr(ff_marker, "pos", None)
        if standby_pos is None:
            managed_ff = getattr(self, "managed_firefighters", None)
            if isinstance(managed_ff, dict):
                state = managed_ff.get(ff_id)
                if state is not None:
                    base_pos = getattr(state, "position", None)
                    if base_pos is not None:
                        standby_pos = (
                            int(round(base_pos[0])),
                            int(round(base_pos[1])),
                        )
        if standby_pos is not None and not self.grid.out_of_bounds(standby_pos):
            try:
                if getattr(ff_marker, "pos", None) != standby_pos:
                    self.grid.move_agent(ff_marker, standby_pos)
            except Exception:
                pass

        ff_marker.status = "available"
        ff_marker.assigned = False
        ff_marker.target_pos = None
        ff_marker.exiting = False
        ff_marker.exit_target = None
        ff_marker.rescued_victim = None
        ff_marker.rescue_completed = False
        ff_marker.dead = False

        unit_label = str(getattr(ff_marker, "unit_id", ff_id) or ff_id)
        pos = getattr(ff_marker, "pos", None)
        print(f"[Firefighter Recycled] FF-{unit_label} available at {pos}")

        if ff_id:
            self._sync_firefighter_operational_knowledge([ff_id])
        else:
            self._sync_firefighter_operational_knowledge()

    def _try_dispatch_unresolved_confirmed_victims(self) -> None:
        """Re-dispatch confirmed victims that still need rescue when firefighters become available."""
        managed = getattr(self, "managed_victims", None)
        markers = getattr(self, "victim_marker_agents", None)
        if not isinstance(managed, dict) or not isinstance(markers, dict):
            return
        for vid, state in managed.items():
            marker = markers.get(vid)
            if not self._victim_needs_rescue(vid, marker):
                continue
            confirmed = bool(getattr(state, "confirmed", False) if state is not None else False)
            marker_status = (
                str(getattr(marker, "status", "") or "").strip().lower()
                if marker is not None
                else ""
            )
            if not confirmed and marker_status != "confirmed":
                continue
            if self._find_active_firefighter_for_victim(vid, marker):
                continue
            self._dispatch_firefighter_to_victim(vid, marker, "initial")

    def _revalidate_route_blocked_firefighters(self) -> None:
        """Clear a stale route_blocked flag once a live route reopens.

        route_blocked is raised about one specific target, but every dispatch
        gate reads it as a property of the unit, and the only in-run clear sits
        at the end of ``Firefighter._move_toward`` - which an unassigned unit can
        never reach, because reaching it needs a target and a target needs a
        dispatch the flag itself refuses. Without this pass an idle, unharmed
        firefighter stays undispatchable for the rest of the run even after its
        route has reopened.
        """
        markers = getattr(self, "firefighter_marker_agents", None)
        victim_markers = getattr(self, "victim_marker_agents", None)
        if not isinstance(markers, dict) or not isinstance(victim_markers, dict):
            return

        blocked: list[tuple[str, Any]] = []
        for ff_id, ff_marker in markers.items():
            status = str(getattr(ff_marker, "status", "") or "").strip().lower()
            if status != "route_blocked":
                continue
            if getattr(ff_marker, "dead", False):
                continue
            if getattr(ff_marker, "assigned", False):
                continue
            if getattr(ff_marker, "exiting", False):
                continue
            if getattr(ff_marker, "pos", None) is None:
                continue
            blocked.append((str(ff_id), ff_marker))
        if not blocked:
            return

        # Live victim cells. The flag was raised against the cell the victim
        # occupied at dispatch, which goes stale as the victim moves or is
        # carried, so reachability is re-tested against where victims are now.
        victim_cells: list[tuple[int, int]] = []
        for vid, victim_marker in victim_markers.items():
            if not self._victim_needs_rescue(str(vid), victim_marker):
                continue
            pos = getattr(victim_marker, "pos", None)
            if pos is not None:
                victim_cells.append((int(pos[0]), int(pos[1])))
        if not victim_cells:
            return

        recovered: list[str] = []
        fire_cells: set[tuple[int, int]] | None = None
        for ff_id, ff_marker in blocked:
            try:
                if fire_cells is None:
                    fire_cells = ff_marker._fire_cells()
                # A unit with nowhere to step is genuinely blocked no matter who
                # stands nearby. Same condition the trigger uses to raise the
                # flag, and it stops a trapped unit from testing "reachable"
                # at distance zero against a victim in its own cell.
                neighbors = ff_marker._neighbor_cells()
                if all(ff_marker._cell_contains_active_fire(c) for c in neighbors):
                    continue
                cell = (int(ff_marker.pos[0]), int(ff_marker.pos[1]))
                if not any(
                    ff_marker._path_exists_avoiding_fire(cell, vcell, fire_cells)
                    for vcell in victim_cells
                ):
                    continue
                ff_marker.status = "available"
            except Exception:
                continue
            recovered.append(ff_id)
            unit_label = str(getattr(ff_marker, "unit_id", ff_id) or ff_id)
            print(f"[Route Cleared] FF-{unit_label} route reopened at {ff_marker.pos}")
            self._sync_firefighter_operational_knowledge([ff_id])

        # Nothing in this model periodically looks for idle units: dispatch is
        # incident-driven, so a recovered unit would otherwise idle as
        # "available" instead of as "route_blocked" and never be picked up.
        if recovered:
            self._try_dispatch_unresolved_confirmed_victims()

    def _process_pending_agent_removals(self) -> int:
        """Finalize rescued victims and recycle exiting firefighters back to available standby."""
        removed = 0
        recycled = 0
        try:
            pending = list(getattr(self, "_agents_pending_removal", []) or [])
            self._agents_pending_removal = []
            finalized_victim_ids: set[str] = set()
            for agent in pending:
                if type(agent) is agents.PathMarker or type(agent).__name__ == "PathMarker":
                    try:
                        if getattr(agent, "pos", None) is not None:
                            self.grid.remove_agent(agent)
                    except Exception:
                        pass
                    try:
                        if agent.unique_id in getattr(self.schedule, "_agents", {}):
                            self.schedule.remove(agent)
                    except Exception:
                        pass
                    removed += 1
                elif type(agent) is agents.Victim or type(agent).__name__ == "Victim":
                    vid = self._victim_id_from_agent(agent)
                    if vid and vid not in finalized_victim_ids:
                        self._finalize_rescued_victim(vid, agent)
                        finalized_victim_ids.add(vid)
                    try:
                        agent.status = "rescued"
                    except Exception:
                        pass
                    try:
                        if getattr(agent, "pos", None) is not None:
                            self.grid.remove_agent(agent)
                    except Exception:
                        pass
                    try:
                        self.schedule.remove(agent)
                    except Exception:
                        pass
                    removed += 1
                elif type(agent) is agents.Firefighter or type(agent).__name__ == "Firefighter":
                    if getattr(agent, "dead", False):
                        try:
                            if getattr(agent, "pos", None) is not None:
                                self.grid.remove_agent(agent)
                        except Exception:
                            pass
                        try:
                            self.schedule.remove(agent)
                        except Exception:
                            pass
                        removed += 1
                        continue
                    rescued_victim = getattr(agent, "rescued_victim", None)
                    if rescued_victim is not None:
                        vid = self._victim_id_from_agent(rescued_victim)
                        ff_id = str(getattr(agent, "unit_id", "") or "")
                        if vid and vid not in finalized_victim_ids:
                            self._finalize_rescued_victim(
                                vid, rescued_victim, firefighter_id=ff_id
                            )
                            finalized_victim_ids.add(vid)
                    self._recycle_firefighter_after_exit(agent)
                    recycled += 1
        except Exception:
            pass
        if recycled > 0:
            self._try_dispatch_unresolved_confirmed_victims()
        return removed

    def _clear_rescue_path_if_requested(self) -> bool:
        try:
            if getattr(self, "_rescue_path_clear_requested", False):
                self._clear_rescue_path()
                self._rescue_path_clear_requested = False
                return True
        except Exception:
            pass
        return False

    def _update_uav_stuck_counts_after_move(self) -> None:
        try:
            if not hasattr(self, "_uav_stuck_counts"):
                self._uav_stuck_counts = {}
            for agent in self.schedule.agents:
                if type(agent).__name__ != "UAV":
                    continue
                uid = str(agent.unique_id)
                pos = getattr(agent, "pos", None)
                if pos is None:
                    continue
                after_pos = (int(pos[0]), int(pos[1]))
                before_pos = self._uav_positions_before_step.get(uid)
                if (
                    before_pos is not None
                    and before_pos[0] == after_pos[0]
                    and before_pos[1] == after_pos[1]
                ):
                    self._uav_stuck_counts[uid] = (
                        int(self._uav_stuck_counts.get(uid, 0) or 0) + 1
                    )
                else:
                    self._uav_stuck_counts[uid] = 0
        except Exception:
            pass

    def _refresh_post_move_environment_bridge(self, current_step_time: float) -> None:
        self.latest_environment_bridge_snapshot = self.environment_bridge.snapshot(
            current_step_time
        )

    def _collect_post_move_monitoring_snapshots(self, current_step_time: float) -> Any:
        snapshot = self.global_monitor.collect_global_snapshot(self, current_step_time)
        self.monitoring_buffer.set_global_snapshot(snapshot)
        self.monitoring_buffer.communication_snapshot = self.communication_monitor.collect_snapshot(
            current_step_time
        )
        self.monitoring_buffer.firefighter_snapshot = self.firefighter_monitor.collect_snapshot(
            current_step_time
        )
        return snapshot

    def _refresh_knowledge_from_post_move_monitoring(
        self, current_step_time: float, global_snapshot: Any
    ) -> None:
        self._apply_monitoring_to_knowledge(self.monitoring_buffer, current_step_time)
        self.knowledge_manager.update_all_models(current_step_time)
        if not self._is_extension_pipeline_active():
            self._rebuild_shared_operational_picture(current_step_time, global_snapshot)
        self.latest_global_snapshot = global_snapshot
        self._maybe_log_post_move_monitoring_summary(global_snapshot)

    def _maybe_log_post_move_monitoring_summary(self, global_snapshot: Any) -> None:
        if self.evaluation_timesteps_counter % 20 != 0:
            return
        unc = global_snapshot.uncertainty_summary
        avg_n = float(unc.get("avg_normalized_information_gain", 0.0))
        n_unc = int(unc.get("aggregated_uncertain_cell_count", 0))
        print(
            f"[Monitoring] step={self.evaluation_timesteps_counter} "
            f"avg_norm_ig={avg_n:.4f} uncertain_cells={n_unc}"
        )

    # this method obtains effective wildfire monitoring metric (MR1) for time step t
    def MR1(self, state):
        # total amount of burning cells from state variable
        MR1_reward = [sum(aux_state) for aux_state in state]
        # normalized reward amount for each UAV state
        reward = [normalize(float(reward), N_OBSERVATIONS, 1, 0) for reward in MR1_reward]
        # MR1_list with added rewards
        self.MR1_LIST = [a + b for a, b in zip(self.MR1_LIST, reward)]

    # this method obtains collision risk avoidance metric (MR2) for time step t
    def MR2(self):
        counter = 0
        # get UAV agents from scheduler
        UAV_agents = [agent for agent in self.schedule.agents if type(agent) is agents.UAV]

        # checks number of interactions for each UAV with others
        for idx, agent in enumerate(UAV_agents):
            aux_agents_positions = UAV_agents.copy()
            del aux_agents_positions[idx]

            # checks number of interactions for one UAV
            for a in aux_agents_positions:
                x1 = agent.pos[0]
                y1 = agent.pos[1]
                x2 = a.pos[0]
                y2 = a.pos[1]
                # Euclidean distance between two UAV grid positions
                distance = euclidean_distance(x1, y1, x2, y2)
                # if distance between the two UAV is less than the defined security distance, add 1 to the counter
                if distance < SECURITY_DISTANCE:
                    counter += 1
        self.MR2_VALUE += counter // 2  # remove duplicate interactions

    # method for obtaining each UAV partial observation
    def state(self):
        states = []
        # this for loop obtains the amount of burning cells for each agent
        for agent in self.schedule.agents:
            if type(agent) is agents.UAV:
                surrounding_states = agent.surrounding_states()
                states.append(surrounding_states)

        # this for loop adds zeros in those positions of the list that would correspond to cells that cannot be
        # observed. This is done when a UAV reaches an edge/corner, not getting the list in the corresponding format
        # Mesa framework asks for
        for st, _ in enumerate(states):
            counter = len(states[st])
            for i in range(counter, N_OBSERVATIONS):
                states[st].append(0)
        return states

    def _draw_rescue_path(self, ff_pos: tuple, victim_pos: tuple) -> None:
        """Place PathMarker agents along L-shaped route from ff to victim."""
        self._clear_rescue_path()
        fx, fy = int(ff_pos[0]), int(ff_pos[1])
        vx, vy = int(victim_pos[0]), int(victim_pos[1])
        cells = []
        step_x = 1 if vx > fx else -1
        for x in range(fx, vx, step_x):
            cells.append((x, fy))
        step_y = 1 if vy > fy else -1
        for y in range(fy, vy + step_y, step_y):
            cells.append((vx, y))
        for cell in cells:
            if not self.grid.out_of_bounds(cell):
                m = agents.PathMarker(self.unique_agents_id, self)
                self.unique_agents_id += 1
                self.grid.place_agent(m, cell)
                self.schedule.add(m)

    def _clear_rescue_path(self) -> None:
        """Queue PathMarker agents for post-move removal (safe during schedule.step)."""
        pending = getattr(self, "_agents_pending_removal", None)
        if not isinstance(pending, list):
            pending = []
            self._agents_pending_removal = pending
        queued = {id(agent) for agent in pending}
        for agent in list(self.schedule.agents):
            if type(agent) is not agents.PathMarker:
                continue
            if id(agent) in queued:
                continue
            pending.append(agent)
            queued.add(id(agent))

    @staticmethod
    def _manhattan_distance(
        pos_a: tuple[int, int] | tuple[float, float],
        pos_b: tuple[int, int] | tuple[float, float],
    ) -> int:
        return abs(int(pos_a[0]) - int(pos_b[0])) + abs(int(pos_a[1]) - int(pos_b[1]))

    def _firefighter_id_from_marker(self, ff_marker: Any) -> str:
        unit_id = str(getattr(ff_marker, "unit_id", "") or "").strip()
        markers = getattr(self, "firefighter_marker_agents", None)
        if isinstance(markers, dict):
            if unit_id and markers.get(unit_id) is ff_marker:
                return unit_id
            for ff_id, marker in markers.items():
                if marker is ff_marker:
                    return str(ff_id)
        return unit_id or str(getattr(ff_marker, "unique_id", ""))

    def _firefighter_available_for_dispatch(self, ff_marker: Any) -> bool:
        if getattr(ff_marker, "dead", False):
            return False
        status = str(getattr(ff_marker, "status", "") or "").strip().lower()
        if status in ("dead", "route_blocked"):
            return False
        if getattr(ff_marker, "assigned", False):
            return False
        if getattr(ff_marker, "exiting", False):
            return False
        if getattr(ff_marker, "rescue_completed", False):
            return False
        return getattr(ff_marker, "pos", None) is not None

    def _victim_needs_rescue(self, victim_id: str, victim_marker: Any | None) -> bool:
        vid = str(victim_id or "").strip()
        if not vid:
            return False
        if victim_marker is not None:
            marker_status = str(getattr(victim_marker, "status", "") or "").strip().lower()
            if marker_status in ("dead", "rescued", "unreachable"):
                return False
        managed = getattr(self, "managed_victims", None)
        if isinstance(managed, dict):
            state = managed.get(vid)
            if state is not None:
                if getattr(state, "rescued", False):
                    return False
                state_status = str(getattr(state, "status", "") or "").strip().lower()
                if state_status in ("dead", "rescued", "unreachable"):
                    return False
        return True

    def get_rescue_operational_snapshot(self) -> dict[str, Any]:
        """Read-only operational view for rescue pairing (planner input)."""
        step = int(getattr(self, "evaluation_timesteps_counter", 0) or 0)
        victims_out: dict[str, dict[str, Any]] = {}
        markers = getattr(self, "victim_marker_agents", None)
        managed = getattr(self, "managed_victims", None)
        if isinstance(markers, dict):
            for vid, marker in markers.items():
                vid_s = str(vid or "").strip()
                if not vid_s:
                    continue
                state = managed.get(vid_s) if isinstance(managed, dict) else None
                pos = getattr(marker, "pos", None)
                position: tuple[int, int] | None = None
                if pos is not None:
                    position = (int(pos[0]), int(pos[1]))
                marker_status = str(getattr(marker, "status", "") or "").strip().lower()
                active = self._find_active_firefighter_for_victim(vid_s, marker)
                active_ff_id = str(active[0]) if active is not None else None
                victims_out[vid_s] = {
                    "position": position,
                    "confirmed": bool(
                        getattr(state, "confirmed", False) if state is not None else False
                    )
                    or marker_status == "confirmed",
                    "rescued": bool(
                        getattr(state, "rescued", False) if state is not None else False
                    )
                    or marker_status == "rescued",
                    "dead": marker_status == "dead"
                    or (
                        str(getattr(state, "status", "") or "").strip().lower() == "dead"
                        if state is not None
                        else False
                    ),
                    "cancelled": bool(
                        getattr(state, "cancelled", False) if state is not None else False
                    )
                    or marker_status == "cancelled",
                    "unreachable": bool(
                        getattr(state, "unreachable", False) if state is not None else False
                    )
                    or marker_status == "unreachable",
                    "rescue_assigned": bool(
                        getattr(state, "rescue_assigned", False) if state is not None else False
                    ),
                    "active_firefighter_id": active_ff_id,
                }

        firefighters_out: dict[str, dict[str, Any]] = {}
        ff_markers = getattr(self, "firefighter_marker_agents", None)
        if isinstance(ff_markers, dict):
            for ff_id, ff_marker in ff_markers.items():
                ff_s = str(ff_id or "").strip()
                if not ff_s:
                    continue
                pos = getattr(ff_marker, "pos", None)
                position: tuple[int, int] | None = None
                if pos is not None:
                    position = (int(pos[0]), int(pos[1]))
                status = str(getattr(ff_marker, "status", "") or "").strip().lower()
                rv = getattr(ff_marker, "rescued_victim", None)
                target_victim_id = (
                    self._victim_id_from_agent(rv) if rv is not None else None
                )
                firefighters_out[ff_s] = {
                    "position": position,
                    "dead": bool(getattr(ff_marker, "dead", False))
                    or status == "dead",
                    "assigned": bool(getattr(ff_marker, "assigned", False)),
                    "route_blocked": status == "route_blocked",
                    "status": status,
                    "available": self._firefighter_available_for_dispatch(ff_marker),
                    "target_victim_id": target_victim_id,
                }

        incidents = list(getattr(self, "_rescue_incident_queue", []) or [])
        return {
            "step": step,
            "victims": victims_out,
            "firefighters": firefighters_out,
            "incidents": incidents,
        }

    def _build_mission_goal_runtime_context(self, current_step_time: float) -> dict[str, Any]:
        """Collect live operational metrics for ``MissionGoalModel.refresh_from_runtime``."""
        rescue_snapshot = self.get_rescue_operational_snapshot()
        victims = rescue_snapshot.get("victims", {})
        firefighters = rescue_snapshot.get("firefighters", {})

        alive_victims_remaining = 0
        active_rescues = 0
        for payload in victims.values():
            if not isinstance(payload, dict):
                continue
            if payload.get("dead") or payload.get("rescued") or payload.get("unreachable"):
                continue
            alive_victims_remaining += 1
            if payload.get("rescue_assigned") or payload.get("active_firefighter_id"):
                active_rescues += 1

        alive_firefighters = sum(
            1
            for payload in firefighters.values()
            if isinstance(payload, dict) and not payload.get("dead")
        )

        fire_severity_estimate = self._estimate_fire_severity()
        coverage_ratio = self._estimate_coverage_ratio()

        fail_safe_mode = "normal"
        mode_manager = getattr(self, "mode_manager", None)
        if mode_manager is not None:
            current_state = getattr(mode_manager, "current_state", None)
            mode = getattr(current_state, "mode", None)
            if mode is not None:
                fail_safe_mode = str(getattr(mode, "value", mode))

        return {
            "timestamp": float(current_step_time),
            "step_index": int(getattr(self, "evaluation_timesteps_counter", 0) or 0),
            "alive_victims_remaining": alive_victims_remaining,
            "active_rescues": active_rescues,
            "alive_firefighters": alive_firefighters,
            "fire_severity_estimate": fire_severity_estimate,
            "coverage_ratio": coverage_ratio,
            "active_fail_safe_mode": fail_safe_mode,
        }

    def _estimate_fire_severity(self) -> float:
        fire_model = getattr(self, "fire_runtime_model", None)
        if fire_model is not None:
            belief = getattr(fire_model, "belief", None)
            probability_map = getattr(belief, "fire_probability_map", None)
            if isinstance(probability_map, dict) and probability_map:
                high_probability = [
                    float(value)
                    for value in probability_map.values()
                    if isinstance(value, (int, float)) and float(value) >= 0.5
                ]
                if high_probability:
                    return min(1.0, sum(high_probability) / len(probability_map))
                return min(
                    1.0,
                    sum(float(value) for value in probability_map.values() if isinstance(value, (int, float)))
                    / len(probability_map),
                )

        grid = getattr(self, "grid", None)
        if grid is not None and hasattr(grid, "shape"):
            try:
                burning = float((grid >= 1).sum())
                total = float(grid.size or 1)
                return min(1.0, burning / total)
            except Exception:
                return 0.0
        return 0.0

    def _estimate_coverage_ratio(self) -> float:
        fire_model = getattr(self, "fire_runtime_model", None)
        if fire_model is not None:
            belief = getattr(fire_model, "belief", None)
            confidence_map = getattr(belief, "fire_confidence_map", None)
            if isinstance(confidence_map, dict) and confidence_map:
                values = [
                    float(value)
                    for value in confidence_map.values()
                    if isinstance(value, (int, float))
                ]
                if values:
                    return min(1.0, sum(values) / len(values))

        local_models = getattr(self, "local_observation_models", {}) or {}
        if isinstance(local_models, dict) and local_models:
            scores: list[float] = []
            for local_obs in local_models.values():
                summary = getattr(local_obs, "summary", None)
                if isinstance(summary, dict):
                    score = summary.get("coverage_score")
                    if isinstance(score, (int, float)):
                        scores.append(float(score))
            if scores:
                return min(1.0, sum(scores) / len(scores))
        return 0.0

    def _refresh_mission_goal_model(self, current_step_time: float) -> None:
        mission_goal_model = getattr(self, "mission_goal_model", None)
        if mission_goal_model is None or not hasattr(mission_goal_model, "refresh_from_runtime"):
            return
        mission_goal_model.refresh_from_runtime(
            self._build_mission_goal_runtime_context(current_step_time)
        )

    def _rescue_incident_dedup_key(self, incident: dict[str, Any]) -> str:
        step = int(getattr(self, "evaluation_timesteps_counter", 0) or 0)
        itype = str(incident.get("type", "") or "")
        vid = str(incident.get("victim_id", "") or "")
        ff_id = str(incident.get("firefighter_id", "") or "")
        reason = str(incident.get("reason", "") or "")
        return f"{step}:{itype}:{vid}:{ff_id}:{reason}"

    def _enqueue_rescue_incident(self, incident: dict[str, Any]) -> None:
        if not isinstance(incident, dict):
            return
        key = self._rescue_incident_dedup_key(incident)
        seen = getattr(self, "_rescue_incident_seen_keys", None)
        if not isinstance(seen, set):
            self._rescue_incident_seen_keys = set()
            seen = self._rescue_incident_seen_keys
        if key in seen:
            return
        seen.add(key)
        queue = getattr(self, "_rescue_incident_queue", None)
        if not isinstance(queue, list):
            self._rescue_incident_queue = []
            queue = self._rescue_incident_queue
        queue.append(dict(incident))

    def _drain_rescue_incidents(self) -> list[dict[str, Any]]:
        queue = getattr(self, "_rescue_incident_queue", None)
        if not isinstance(queue, list) or not queue:
            return []
        pending = list(queue)
        self._rescue_incident_queue = []
        return pending

    def _rescue_reason_for_incident(self, incident: dict[str, Any]) -> str:
        itype = str(incident.get("type", "") or "").strip().lower()
        reason = str(incident.get("reason", "") or "").strip()
        if reason:
            return reason
        if itype == "victim_confirmed":
            return "initial"
        if itype == "route_blocked":
            return "replacement_after_blocked"
        if itype == "firefighter_casualty":
            return "replacement_after_casualty"
        if itype == "rescue_complete":
            return "physical_rescue_complete"
        return itype

    def _handle_rescue_incident(self, incident: dict[str, Any]) -> None:
        itype = str(incident.get("type", "") or "").strip().lower()
        vid = str(incident.get("victim_id", "") or "").strip()
        ff_id = str(incident.get("firefighter_id", "") or "").strip()
        reason = self._rescue_reason_for_incident(incident)

        if itype == "victim_dead":
            if not vid:
                return
            markers = getattr(self, "victim_marker_agents", None)
            victim_marker = (
                markers.get(vid) if isinstance(markers, dict) else None
            )
            pair = self._find_active_firefighter_for_victim(vid, victim_marker)
            if pair is not None:
                ff_id, _ff_marker = pair
                executor = self._physical_rescue_executor()
                executor.execute_physical_command(
                    self,
                    PhysicalRescueCommand(
                        action="unassign",
                        victim_id=vid,
                        firefighter_id=ff_id,
                        reason=reason or "victim_dead_recall",
                        metadata={},
                    ),
                )
            return

        executor = self._physical_rescue_executor()

        if itype == "rescue_complete":
            if not vid:
                return
            managed = getattr(self, "managed_victims", None)
            if isinstance(managed, dict):
                state = managed.get(vid)
                if state is not None and getattr(state, "rescued", False):
                    return
                if state is not None and (
                    getattr(state, "dead", False)
                    or getattr(state, "cancelled", False)
                    or str(getattr(state, "status", "")).lower()
                    in {"dead", "cancelled"}
                ):
                    return
            markers = getattr(self, "victim_marker_agents", None)
            if isinstance(markers, dict):
                marker = markers.get(vid)
                if marker is not None and (
                    str(getattr(marker, "status", "")).lower()
                    in {"dead", "cancelled"}
                ):
                    return
            agent = None
            markers = getattr(self, "victim_marker_agents", None)
            if isinstance(markers, dict):
                agent = markers.get(vid)
            executor.execute_physical_command(
                self,
                PhysicalRescueCommand(
                    action="finalize_rescue",
                    victim_id=vid,
                    firefighter_id=ff_id or None,
                    reason=reason,
                    metadata={"victim_agent": agent},
                ),
            )
            self._activate_post_rescue_coverage_for_searchers()
            return

        if itype == "route_blocked":
            if not vid or not ff_id:
                return
            markers = getattr(self, "victim_marker_agents", None)
            victim_marker = markers.get(vid) if isinstance(markers, dict) else None
            if victim_marker is None:
                return
            attempt_key = (ff_id, vid)
            if attempt_key in self._blocked_replacement_attempted:
                return
            self._blocked_replacement_attempted.add(attempt_key)
            executor.execute_physical_command(
                self,
                PhysicalRescueCommand(
                    action="unassign",
                    victim_id=vid,
                    firefighter_id=ff_id,
                    reason=reason,
                    metadata={"reset_victim_pending": True},
                ),
            )

        snapshot = self.get_rescue_operational_snapshot()
        decision = select_rescue_assignment(snapshot, reason, victim_id=vid or None)
        victim_marker = None
        if vid:
            markers = getattr(self, "victim_marker_agents", None)
            if isinstance(markers, dict):
                victim_marker = markers.get(vid)
        result = executor.apply_physical_pairing_decision(
            self, decision, victim_marker=victim_marker
        )

        if itype in ("firefighter_casualty", "route_blocked") and not result.get("success"):
            action = ""
            if isinstance(decision, RescueDecision):
                action = str(decision.rescue_action or "").strip().lower()
            elif isinstance(decision, dict):
                action = str(decision.get("action", "") or "").strip().lower()
            if action == "mark_unreachable" and vid:
                if vid not in self._rescue_failed_logged:
                    print(
                        f"[Rescue Failed] no available replacement firefighter for {vid}"
                    )
                    self._rescue_failed_logged.add(vid)
            self._sync_firefighter_operational_knowledge()

    def _activate_post_rescue_coverage_for_searchers(self) -> None:
        if _count_unresolved_victims(self) <= 0:
            return
        for vs_id in resolve_victim_searcher_uav_ids(self):
            wind_state = _wind_search_state(self, vs_id)
            wind_state["post_rescue_coverage_steps_remaining"] = POST_RESCUE_COVERAGE_DURATION
            wind_state["coverage_priority"] = max(
                float(wind_state.get("coverage_priority", 0.0) or 0.0),
                0.85,
            )
            wind_state["steps_since_detection"] = 9999

    def _process_rescue_incidents(self) -> None:
        if not getattr(self, "_rescue_incident_processing_enabled", True):
            return
        for incident in self._drain_rescue_incidents():
            try:
                self._handle_rescue_incident(incident)
            except Exception:
                continue

    def _find_active_firefighter_for_victim(
        self, victim_id: str, victim_marker: Any
    ) -> tuple[str, Any] | None:
        markers = getattr(self, "firefighter_marker_agents", None)
        if not isinstance(markers, dict):
            return None
        for ff_id, ff_marker in markers.items():
            if getattr(ff_marker, "dead", False):
                continue
            if not getattr(ff_marker, "assigned", False):
                continue
            status = str(getattr(ff_marker, "status", "") or "").strip().lower()
            if status in ("dead", "route_blocked"):
                continue
            rv = getattr(ff_marker, "rescued_victim", None)
            if rv is None:
                continue
            rv_id = self._victim_id_from_agent(rv)
            if rv is victim_marker or rv_id == victim_id:
                return str(ff_id), ff_marker
        return None

    def _find_closest_available_firefighter(
        self, victim_pos: tuple[int, int]
    ) -> tuple[str, Any] | None:
        """Compatibility helper: delegates pairing to RescuePlanner snapshot."""
        cell = (int(victim_pos[0]), int(victim_pos[1]))
        snapshot = self.get_rescue_operational_snapshot()
        target_vid: str | None = None
        for vid, entry in snapshot.get("victims", {}).items():
            if not isinstance(entry, dict):
                continue
            pos = entry.get("position")
            if pos is not None and (int(pos[0]), int(pos[1])) == cell:
                target_vid = str(vid)
                break
        if target_vid is None:
            return None
        decision = select_rescue_assignment(snapshot, "initial", victim_id=target_vid)
        if isinstance(decision, RescueDecision):
            if str(decision.rescue_action or "").strip().lower() != "assign":
                return None
            ff_id = str(decision.firefighter_id or "").strip()
            if not ff_id:
                return None
            markers = getattr(self, "firefighter_marker_agents", None)
            if isinstance(markers, dict) and ff_id in markers:
                return ff_id, markers[ff_id]
        return None

    _RESCUE_EVENT_CONSOLE_TYPES = frozenset(
        {
            "dispatch_initial",
            "dispatch_replacement_after_blocked",
            "dispatch_replacement_after_casualty",
            "route_blocked",
            "casualty",
            "rescue_complete",
            "rescue_failed",
            "victim_dead",
        }
    )

    @staticmethod
    def _agent_grid_pos(agent: Any | None) -> tuple[int, int] | None:
        if agent is None:
            return None
        pos = getattr(agent, "pos", None)
        if pos is None:
            return None
        return (int(pos[0]), int(pos[1]))

    @staticmethod
    def _physical_rescue_event_type_from_reason(reason: str) -> str:
        reason_l = str(reason or "").strip().lower()
        if reason_l in ("initial", "test_initial"):
            return "dispatch_initial"
        if reason_l == "replacement_after_blocked":
            return "dispatch_replacement_after_blocked"
        if reason_l == "replacement_after_casualty":
            return "dispatch_replacement_after_casualty"
        if "replacement" in reason_l and "blocked" in reason_l:
            return "dispatch_replacement_after_blocked"
        if "replacement" in reason_l and "casualty" in reason_l:
            return "dispatch_replacement_after_casualty"
        return "dispatch_initial"

    def _physical_rescue_executor(self) -> RescueExecutor:
        dispatcher = getattr(self, "decision_dispatcher", None)
        if dispatcher is not None and hasattr(dispatcher, "rescue_executor"):
            return dispatcher.rescue_executor
        return RescueExecutor(model=self, execution_log=self.execution_log)

    def _execute_physical_rescue_via_executor(
        self, cmd: PhysicalRescueCommand
    ) -> dict[str, Any]:
        """Route physical rescue commands through RescueExecutor authority."""
        result = self._physical_rescue_executor().execute_physical_command(self, cmd)
        return dict(result) if isinstance(result, dict) else {}

    def _assert_no_direct_rescue_mutation(self) -> None:
        """Debug-only: ensure assignment mutations went through executor audit trail."""
        if not getattr(self, "debug_log", False):
            return
        audit = getattr(self, "_physical_rescue_command_audit", None)
        if not isinstance(audit, list):
            return
        markers = getattr(self, "firefighter_marker_agents", None)
        if not isinstance(markers, dict):
            return
        for ff_id, ff_marker in markers.items():
            if not getattr(ff_marker, "assigned", False):
                continue
            vid = ""
            rv = getattr(ff_marker, "rescued_victim", None)
            if rv is not None:
                vid = self._victim_id_from_agent(rv)
            recent = [
                e
                for e in audit[-50:]
                if isinstance(e, dict)
                and e.get("success")
                and e.get("action") == "assign"
                and e.get("firefighter_id") == str(ff_id)
                and (not vid or e.get("victim_id") == vid)
            ]
            if not recent:
                print(
                    f"[RescueAuthority] assigned FF {ff_id} without recent executor "
                    f"assign audit for victim {vid or 'na'}"
                )

    def _mirror_rescue_event_to_execution_bridge(self, event: dict[str, Any]) -> None:
        timestamp = float(event.get("step", 0) or 0)
        event_type = str(event.get("event_type", "") or "")
        victim_id = str(event.get("victim_id", "") or "")
        firefighter_id = str(event.get("firefighter_id", "") or "")
        reason = str(event.get("reason", "") or "")
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        action_map = {
            "dispatch_initial": "physical_dispatch",
            "dispatch_replacement_after_blocked": "physical_dispatch_replacement",
            "dispatch_replacement_after_casualty": "physical_dispatch_replacement",
            "route_blocked": "physical_route_blocked",
            "casualty": "physical_casualty",
            "rescue_complete": "physical_rescue_complete",
            "rescue_failed": "physical_rescue_failed",
            "victim_dead": "physical_victim_dead",
        }
        rescue_action = action_map.get(event_type, f"physical_{event_type}")

        self.latest_physical_rescue_decision = RescueDecision(
            decision_id=f"physical-{event_type}-{victim_id}-{int(timestamp)}",
            selected_option_id="physical_bridge",
            rescue_action=rescue_action,
            victim_id=victim_id,
            firefighter_id=firefighter_id,
            route_choice=str(metadata.get("route_choice", "") or ""),
            payload=dict(metadata),
            confidence_score=1.0,
            uncertainty_context={"physical_bridge": True, "event_type": event_type},
            comparison_summary={"summary": f"Physical rescue bridge: {event_type}"},
            explanation=reason,
        )

        bridge = self._physical_rescue_executor()
        bridge.record_physical_event(
            event_type=event_type,
            victim_id=victim_id,
            firefighter_id=firefighter_id,
            reason=reason,
            timestamp=timestamp,
            victim_pos=event.get("victim_pos"),
            firefighter_pos=event.get("firefighter_pos"),
            metadata=metadata,
        )

    def _record_rescue_event(
        self,
        victim_id: str,
        firefighter_id: str,
        event_type: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Bridge physical rescue actions into MAPE execution history."""
        vid = str(victim_id or "").strip()
        ff_id = str(firefighter_id or "").strip()
        step = int(getattr(self, "evaluation_timesteps_counter", 0) or 0)
        event_type_s = str(event_type or "")
        meta = dict(metadata or {})

        if vid and event_type_s == "rescue_complete":
            prior = getattr(self, "_latest_physical_rescue_by_victim", {}).get(vid)
            if (
                isinstance(prior, dict)
                and prior.get("event_type") == "rescue_complete"
                and int(prior.get("step", -1)) == step
            ):
                return

        victim_pos = None
        ff_pos = None
        markers = getattr(self, "victim_marker_agents", None)
        if isinstance(markers, dict) and vid in markers:
            victim_pos = self._agent_grid_pos(markers[vid])
        ff_markers = getattr(self, "firefighter_marker_agents", None)
        if isinstance(ff_markers, dict) and ff_id in ff_markers:
            ff_pos = self._agent_grid_pos(ff_markers[ff_id])

        event: dict[str, Any] = {
            "step": step,
            "victim_id": vid,
            "firefighter_id": ff_id,
            "event_type": event_type_s,
            "reason": str(reason or ""),
            "victim_pos": victim_pos,
            "firefighter_pos": ff_pos,
            "metadata": meta,
        }
        if not hasattr(self, "_rescue_event_log"):
            self._rescue_event_log = []
        self._rescue_event_log.append(event)
        if vid:
            if not hasattr(self, "_latest_physical_rescue_by_victim"):
                self._latest_physical_rescue_by_victim = {}
            self._latest_physical_rescue_by_victim[vid] = event

        try:
            self._mirror_rescue_event_to_execution_bridge(event)
        except Exception:
            pass

        if str(event_type) in self._RESCUE_EVENT_CONSOLE_TYPES:
            print(
                f"[RescueEvent] type={event_type} victim={vid or 'na'} "
                f"ff={ff_id or 'na'} reason={reason}"
            )

    def _firefighter_id_for_victim(self, victim_id: str) -> str:
        managed = getattr(self, "managed_victims", None)
        if isinstance(managed, dict):
            state = managed.get(victim_id)
            if state is not None:
                ff = getattr(state, "firefighter_id", None)
                if ff:
                    return str(ff)
        markers = getattr(self, "victim_marker_agents", None)
        marker = markers.get(victim_id) if isinstance(markers, dict) else None
        if marker is not None:
            active = self._find_active_firefighter_for_victim(victim_id, marker)
            if active is not None:
                return str(active[0])
        return ""

    def _derive_firefighter_operational_fields(
        self, ff_marker: Any, target_victim_id: str | None
    ) -> dict[str, Any]:
        dead = bool(getattr(ff_marker, "dead", False))
        status = str(getattr(ff_marker, "status", "") or "").strip().lower()
        assigned = bool(getattr(ff_marker, "assigned", False))
        route_blocked = status == "route_blocked"
        exiting = bool(getattr(ff_marker, "exiting", False))
        rescue_completed = bool(getattr(ff_marker, "rescue_completed", False))
        pos = getattr(ff_marker, "pos", None)
        current_position = (
            (float(pos[0]), float(pos[1])) if pos is not None else None
        )
        target_pos = getattr(ff_marker, "target_pos", None)
        target_position = (
            (float(target_pos[0]), float(target_pos[1]))
            if target_pos is not None
            else None
        )

        if dead:
            availability_status = "unavailable"
            assignment_state = "unassigned"
            route_state = "dead"
            current_assignment = None
            route_status = "dead"
            rescue_progress_status = "casualty"
            route_risk_score = 1.0
            route_feasibility_confidence = 0.0
        elif rescue_completed:
            availability_status = "unavailable"
            assignment_state = "unassigned"
            route_state = "completed"
            current_assignment = None
            route_status = "completed"
            rescue_progress_status = "completed"
            route_risk_score = 0.1
            route_feasibility_confidence = 0.9
        elif exiting:
            availability_status = "busy"
            assignment_state = "returning"
            route_state = "exiting"
            current_assignment = "victim_rescue" if target_victim_id else "return_to_base"
            route_status = "exiting"
            rescue_progress_status = "exiting_with_victim"
            route_risk_score = 0.35
            route_feasibility_confidence = 0.75
        elif route_blocked:
            availability_status = "unavailable"
            assignment_state = "assigned" if assigned else "unassigned"
            route_state = "blocked"
            current_assignment = (
                "victim_rescue" if assigned and target_victim_id else None
            )
            route_status = "blocked"
            rescue_progress_status = "blocked"
            route_risk_score = 0.95
            route_feasibility_confidence = 0.15
        elif assigned or status in ("en_route", "assigned"):
            availability_status = "assigned"
            assignment_state = "assigned"
            route_state = "en_route"
            current_assignment = "victim_rescue"
            route_status = "en_route"
            rescue_progress_status = "en_route"
            route_risk_score = 0.45
            route_feasibility_confidence = 0.8
        else:
            availability_status = "available"
            assignment_state = "unassigned"
            route_state = "idle"
            current_assignment = None
            route_status = "idle"
            rescue_progress_status = "none"
            route_risk_score = 0.1
            route_feasibility_confidence = 0.9

        return {
            "dead": dead,
            "assigned": assigned,
            "route_blocked": route_blocked,
            "operational_status": status,
            "current_position": current_position,
            "target_position": target_position,
            "target_victim_id": target_victim_id,
            "availability_status": availability_status,
            "assignment_state": assignment_state,
            "route_state": route_state,
            "current_assignment": current_assignment,
            "route_status": route_status,
            "rescue_progress_status": rescue_progress_status,
            "route_risk_score": route_risk_score,
            "route_feasibility_confidence": route_feasibility_confidence,
        }

    def _sync_one_firefighter_operational_knowledge(
        self, ff_id: str, ff_marker: Any, timestamp: float
    ) -> None:
        victim_ref = getattr(ff_marker, "rescued_victim", None)
        target_victim_id = (
            self._victim_id_from_agent(victim_ref) if victim_ref is not None else None
        )
        fields = self._derive_firefighter_operational_fields(
            ff_marker, target_victim_id
        )

        managed_ff = getattr(self, "managed_firefighters", None)
        if isinstance(managed_ff, dict):
            state = managed_ff.get(ff_id)
            if state is not None:
                pos = fields.get("current_position")
                if pos is not None:
                    try:
                        state.position = (float(pos[0]), float(pos[1]))
                    except Exception:
                        pass
                try:
                    state.availability = str(fields["availability_status"])
                except Exception:
                    pass
                try:
                    state.assignment_state = str(fields["assignment_state"])
                except Exception:
                    pass
                try:
                    state.route_state = str(fields["route_state"])
                except Exception:
                    pass
                try:
                    state.rescue_progress = str(fields["rescue_progress_status"])
                except Exception:
                    pass
                extra = getattr(state, "extra", None)
                if not isinstance(extra, dict):
                    extra = {}
                    state.extra = extra
                extra["dead"] = fields["dead"]
                extra["assigned"] = fields["assigned"]
                extra["route_blocked"] = fields["route_blocked"]
                extra["operational_status"] = fields["operational_status"]
                extra["target_position"] = fields["target_position"]
                extra["target_victim_id"] = fields["target_victim_id"]

        ff_model = getattr(self, "firefighter_model", None)
        if ff_model is not None and hasattr(ff_model, "mirror_operational_state"):
            ff_model.mirror_operational_state(
                ff_id,
                timestamp,
                dead=bool(fields["dead"]),
                assigned=bool(fields["assigned"]),
                route_blocked=bool(fields["route_blocked"]),
                operational_status=str(fields["operational_status"]),
                current_position=fields["current_position"],
                target_position=fields["target_position"],
                target_victim_id=fields["target_victim_id"],
                availability_status=str(fields["availability_status"]),
                current_assignment=fields["current_assignment"],
                route_status=str(fields["route_status"]),
                rescue_progress_status=str(fields["rescue_progress_status"]),
                route_risk_score=float(fields["route_risk_score"]),
                route_feasibility_confidence=float(
                    fields["route_feasibility_confidence"]
                ),
                source="marker_sync",
            )

        if getattr(self, "debug_log", False):
            self._verify_firefighter_sync(ff_id, ff_marker, fields)

    def _sync_firefighter_operational_knowledge(
        self, unit_ids: list[str] | None = None
    ) -> None:
        """Mirror marker firefighter state into managed + firefighter_model knowledge."""
        markers = getattr(self, "firefighter_marker_agents", None)
        if not isinstance(markers, dict):
            return
        timestamp = float(getattr(self, "evaluation_timesteps_counter", 0) or 0)
        ids = unit_ids if unit_ids is not None else list(markers.keys())
        ff_model = getattr(self, "firefighter_model", None)
        if ff_model is not None:
            try:
                ff_model.step_index = int(timestamp)
            except Exception:
                pass
        for ff_id in ids:
            marker = markers.get(ff_id)
            if marker is None:
                continue
            self._sync_one_firefighter_operational_knowledge(ff_id, marker, timestamp)

    def _verify_firefighter_sync(
        self, ff_id: str, ff_marker: Any, derived: dict[str, Any]
    ) -> None:
        if ff_id in getattr(self, "_firefighter_sync_mismatch_logged", set()):
            return
        mismatches: list[str] = []

        managed_ff = getattr(self, "managed_firefighters", None)
        managed = managed_ff.get(ff_id) if isinstance(managed_ff, dict) else None
        unit = None
        ff_model = getattr(self, "firefighter_model", None)
        if ff_model is not None:
            unit = getattr(ff_model, "units", {}).get(ff_id)

        if managed is not None:
            if str(getattr(managed, "availability", "")) != str(
                derived["availability_status"]
            ):
                mismatches.append("managed.availability")
            if str(getattr(managed, "assignment_state", "")) != str(
                derived["assignment_state"]
            ):
                mismatches.append("managed.assignment_state")
            if str(getattr(managed, "route_state", "")) != str(derived["route_state"]):
                mismatches.append("managed.route_state")

        if unit is not None:
            if bool(getattr(unit, "is_dead", False)) != bool(derived["dead"]):
                mismatches.append("knowledge.is_dead")
            if bool(getattr(unit, "is_assigned", False)) != bool(derived["assigned"]):
                mismatches.append("knowledge.is_assigned")
            if bool(getattr(unit, "route_blocked", False)) != bool(
                derived["route_blocked"]
            ):
                mismatches.append("knowledge.route_blocked")
            if str(getattr(unit, "availability_status", "") or "") != str(
                derived["availability_status"]
            ):
                mismatches.append("knowledge.availability_status")
            kv = getattr(unit, "target_victim", None)
            dv = derived.get("target_victim_id")
            if (kv or None) != (dv or None):
                mismatches.append("knowledge.target_victim")

        marker_dead = bool(getattr(ff_marker, "dead", False))
        if marker_dead != bool(derived["dead"]):
            mismatches.append("marker.dead")
        marker_assigned = bool(getattr(ff_marker, "assigned", False))
        if marker_assigned != bool(derived["assigned"]):
            mismatches.append("marker.assigned")

        if mismatches:
            print(
                f"[KnowledgeMismatch] firefighter={ff_id} fields={','.join(mismatches)}"
            )
            self._firefighter_sync_mismatch_logged.add(ff_id)

    def apply_physical_rescue_command(self, cmd: PhysicalRescueCommand) -> bool:
        """Sole entry point for physical rescue assignment state mutations."""
        action = str(cmd.action or "").strip().lower()
        vid = str(cmd.victim_id or "").strip()
        ff_id = str(cmd.firefighter_id or "").strip() if cmd.firefighter_id else ""
        reason = str(cmd.reason or "")
        meta = dict(cmd.metadata or {})

        if action == "assign":
            if not vid or not ff_id:
                return False
            ff_markers = getattr(self, "firefighter_marker_agents", None)
            if not isinstance(ff_markers, dict):
                return False
            ff_marker = ff_markers.get(ff_id)
            if ff_marker is None:
                return False
            victim_marker = meta.get("victim_marker")
            if victim_marker is None:
                victim_markers = getattr(self, "victim_marker_agents", None)
                if isinstance(victim_markers, dict):
                    victim_marker = victim_markers.get(vid)
            if victim_marker is None:
                return False

            if getattr(ff_marker, "dead", False):
                return False
            ff_status = str(getattr(ff_marker, "status", "") or "").strip().lower()
            if ff_status in ("dead", "route_blocked"):
                return False
            if getattr(ff_marker, "assigned", False):
                existing = getattr(ff_marker, "rescued_victim", None)
                if existing is not None:
                    existing_id = self._victim_id_from_agent(existing)
                    if existing_id and existing_id != vid:
                        return False

            victim_pos = meta.get("target_pos")
            if victim_pos is None:
                victim_pos = getattr(victim_marker, "pos", None)
            if victim_pos is None:
                return False
            victim_cell = (int(victim_pos[0]), int(victim_pos[1]))

            ff_marker.assigned = True
            ff_marker.target_pos = victim_cell
            ff_marker.rescued_victim = victim_marker
            ff_marker.status = "en_route"
            ff_marker.exiting = False
            ff_marker.exit_target = None

            managed_ff = getattr(self, "managed_firefighters", None)
            if isinstance(managed_ff, dict):
                ff_state = managed_ff.get(ff_id)
                if ff_state is not None:
                    try:
                        ff_state.assignment_state = "assigned"
                    except Exception:
                        pass
                    try:
                        ff_state.route_state = "en_route"
                    except Exception:
                        pass
                    try:
                        ff_state.availability = "busy"
                    except Exception:
                        pass

            managed = getattr(self, "managed_victims", None)
            if isinstance(managed, dict):
                dispatch_state = managed.get(vid)
                if dispatch_state is not None:
                    try:
                        dispatch_state.rescue_assigned = True
                    except Exception:
                        pass
                    try:
                        dispatch_state.assigned = True
                    except Exception:
                        pass
                    try:
                        dispatch_state.confirmed = True
                    except Exception:
                        pass
                    try:
                        dispatch_state.status = "assigned"
                    except Exception:
                        pass
                    try:
                        dispatch_state.unreachable = False
                    except Exception:
                        pass
                    try:
                        dispatch_state.cancelled = False
                    except Exception:
                        pass
                    try:
                        dispatch_state.firefighter_id = ff_id
                    except Exception:
                        pass

            try:
                victim_marker.status = "assigned"
            except Exception:
                pass

            if ff_marker.pos is not None:
                self._draw_rescue_path(ff_marker.pos, victim_cell)

            self._rescue_failed_logged.discard(vid)

            unit_label = str(getattr(ff_marker, "unit_id", ff_id) or ff_id)
            ff_dist = self._manhattan_distance(ff_marker.pos, victim_cell)
            print(
                f"[Dispatch] FF-{unit_label} assigned to {vid} "
                f"reason={reason} manhattan_dist={ff_dist}"
            )
            event_type = self._physical_rescue_event_type_from_reason(reason)
            self._record_rescue_event(
                vid,
                ff_id,
                event_type,
                reason,
                {"manhattan_dist": ff_dist, "target_pos": victim_cell},
            )
            self._sync_firefighter_operational_knowledge()
            return True

        if action == "unassign":
            if not ff_id:
                return False
            ff_markers = getattr(self, "firefighter_marker_agents", None)
            if not isinstance(ff_markers, dict):
                return False
            ff_marker = ff_markers.get(ff_id)
            if ff_marker is None:
                return False

            ff_marker.assigned = False
            ff_marker.target_pos = None
            ff_marker.rescued_victim = None
            ff_marker.exiting = False
            ff_marker.exit_target = None
            managed_ff = getattr(self, "managed_firefighters", None)
            if isinstance(managed_ff, dict):
                state = managed_ff.get(ff_id)
                if state is not None:
                    try:
                        state.assignment_state = "unassigned"
                    except Exception:
                        pass
                    status = str(getattr(ff_marker, "status", "") or "").strip().lower()
                    if status != "route_blocked":
                        try:
                            state.route_state = "idle"
                        except Exception:
                            pass
                        try:
                            state.availability = "available"
                        except Exception:
                            pass

            if meta.get("reset_victim_pending"):
                managed = getattr(self, "managed_victims", None)
                if isinstance(managed, dict) and vid:
                    victim_state = managed.get(vid)
                    if victim_state is not None:
                        try:
                            victim_state.rescue_assigned = False
                        except Exception:
                            pass
                        try:
                            victim_state.assigned = False
                        except Exception:
                            pass
                        victim_status = str(
                            getattr(victim_state, "status", "") or ""
                        ).strip().lower()
                        if victim_status not in ("dead", "rescued"):
                            try:
                                victim_state.status = "confirmed"
                            except Exception:
                                pass
                victim_markers = getattr(self, "victim_marker_agents", None)
                if isinstance(victim_markers, dict) and vid:
                    victim_marker = victim_markers.get(vid)
                    if victim_marker is not None:
                        try:
                            victim_marker.status = "confirmed"
                        except Exception:
                            pass

            try:
                self._rescue_path_clear_requested = True
            except Exception:
                pass
            self._sync_firefighter_operational_knowledge([ff_id])
            return True

        if action == "mark_unreachable":
            if not vid:
                return False
            managed = getattr(self, "managed_victims", None)
            if isinstance(managed, dict):
                state = managed.get(vid)
                if state is not None:
                    try:
                        state.cancelled = True
                    except Exception:
                        pass
                    try:
                        state.unreachable = True
                    except Exception:
                        pass
                    try:
                        state.status = "unreachable"
                    except Exception:
                        pass
                    try:
                        state.rescue_assigned = False
                    except Exception:
                        pass
                    cause = str(meta.get("unreachable_cause", "") or "").strip()
                    if cause:
                        try:
                            state.unreachable_cause = cause
                        except Exception:
                            pass
                        attrs = getattr(state, "attributes", None)
                        if not isinstance(attrs, dict):
                            attrs = {}
                            try:
                                state.attributes = attrs
                            except Exception:
                                attrs = None
                        if isinstance(attrs, dict):
                            attrs["unreachable_cause"] = cause
            victim_marker = meta.get("victim_marker")
            if victim_marker is None:
                victim_markers = getattr(self, "victim_marker_agents", None)
                if isinstance(victim_markers, dict):
                    victim_marker = victim_markers.get(vid)
            if victim_marker is not None:
                try:
                    victim_marker.status = "unreachable"
                except Exception:
                    pass
            self._record_rescue_event(
                vid,
                self._firefighter_id_for_victim(vid),
                "rescue_failed",
                reason or "no_available_firefighter",
                {"unreachable_cause": str(meta.get("unreachable_cause", "") or "")},
            )
            return True

        if action == "finalize_rescue":
            if not vid:
                return False
            agent = meta.get("victim_agent")
            ff_id = ff_id or self._firefighter_id_for_victim(vid)

            managed = getattr(self, "managed_victims", None)
            if isinstance(managed, dict):
                state = managed.get(vid)
                if state is not None and (
                    getattr(state, "dead", False)
                    or getattr(state, "cancelled", False)
                    or str(getattr(state, "status", "")).lower()
                    in {"dead", "cancelled"}
                ):
                    return False
                if state is not None:
                    try:
                        state.rescued = True
                    except Exception:
                        pass
                    try:
                        state.status = "rescued"
                    except Exception:
                        pass
                    try:
                        state.cancelled = False
                    except Exception:
                        pass
                    try:
                        state.unreachable = False
                    except Exception:
                        pass

            runtime = getattr(self, "victim_runtime_model", None)
            if runtime is not None:
                victims = getattr(runtime, "victims", None)
                if isinstance(victims, dict) and vid in victims:
                    try:
                        del victims[vid]
                    except Exception:
                        pass

            markers = getattr(self, "victim_marker_agents", None)
            if isinstance(markers, dict):
                marker = markers.get(vid)
                if marker is None and agent is not None:
                    for known_id, candidate in markers.items():
                        if candidate is agent:
                            vid = str(known_id)
                            marker = candidate
                            break
                if marker is not None:
                    try:
                        marker.status = "rescued"
                    except Exception:
                        pass

            self._record_rescue_event(
                vid,
                ff_id,
                "rescue_complete",
                reason or "physical_rescue_complete",
                {},
            )
            return True

        return False

    def _unassign_firefighter(self, ff_marker: Any, ff_id: str) -> None:
        victim_marker = getattr(ff_marker, "rescued_victim", None)
        victim_id = (
            self._victim_id_from_agent(victim_marker)
            if victim_marker is not None
            else ""
        )
        self._execute_physical_rescue_via_executor(
            PhysicalRescueCommand(
                action="unassign",
                victim_id=victim_id,
                firefighter_id=ff_id,
                reason="unassign_firefighter",
                metadata={},
            )
        )

    def _mark_victim_unreachable(
        self,
        victim_id: str,
        victim_marker: Any | None,
        reason: str = "no_available_firefighter",
        cause: str = "",
    ) -> None:
        vid = str(victim_id or "").strip()
        if not vid:
            return
        metadata: dict[str, Any] = {"victim_marker": victim_marker}
        cause_s = str(cause or "").strip()
        if cause_s:
            metadata["unreachable_cause"] = cause_s
        self._execute_physical_rescue_via_executor(
            PhysicalRescueCommand(
                action="mark_unreachable",
                victim_id=vid,
                firefighter_id=None,
                reason=str(reason or cause_s or "no_available_firefighter"),
                metadata=metadata,
            )
        )

    def _active_burning_cells(self) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for agent in getattr(self.schedule, "agents", []) or []:
            if type(agent) is not agents.Fire:
                continue
            try:
                if not agent.is_burning():
                    continue
            except Exception:
                continue
            pos = getattr(agent, "pos", None)
            if pos is None:
                continue
            cells.add((int(pos[0]), int(pos[1])))
        return cells

    def _safe_path_reachable_cells(
        self,
        starts: list[tuple[int, int]],
        burning: set[tuple[int, int]],
    ) -> set[tuple[int, int]]:
        """4-connected BFS; active fire cells are impassable, burnt cells are not."""
        reachable: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int]] = deque()
        for start in starts:
            cell = (int(start[0]), int(start[1]))
            if cell in burning or cell in reachable:
                continue
            if self.grid.out_of_bounds(cell):
                continue
            reachable.add(cell)
            queue.append(cell)
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (x + dx, y + dy)
                if nxt in reachable or nxt in burning:
                    continue
                if self.grid.out_of_bounds(nxt):
                    continue
                reachable.add(nxt)
                queue.append(nxt)
        return reachable

    def _update_unreachable_victims(self) -> None:
        """Periodic escape hatch: isolated victims become unreachable after N steps."""
        managed = getattr(self, "managed_victims", None)
        markers = getattr(self, "victim_marker_agents", None)
        if not isinstance(managed, dict) or not isinstance(markers, dict):
            return
        ff_markers = getattr(self, "firefighter_marker_agents", None)
        if not isinstance(ff_markers, dict):
            ff_markers = {}

        living: list[tuple[str, Any, tuple[int, int]]] = []
        starts: list[tuple[int, int]] = []
        for ff_id, ff_marker in ff_markers.items():
            if getattr(ff_marker, "dead", False):
                continue
            status = str(getattr(ff_marker, "status", "") or "").strip().lower()
            if status == "dead":
                continue
            if getattr(ff_marker, "exiting", False):
                continue
            pos = getattr(ff_marker, "pos", None)
            if pos is None:
                continue
            cell = (int(pos[0]), int(pos[1]))
            living.append((str(ff_id), ff_marker, cell))
            starts.append(cell)

        burning = self._active_burning_cells()
        reachable_cells = self._safe_path_reachable_cells(starts, burning)

        prev_dists = getattr(self, "_ff_victim_distances", None)
        if not isinstance(prev_dists, dict):
            prev_dists = {}
        new_dists: dict[tuple[str, str], int] = {}
        flags: dict[str, dict[str, Any]] = {}
        terminal_statuses = frozenset({"rescued", "dead", "unreachable", "cancelled"})

        for vid, state in managed.items():
            vid_s = str(vid or "").strip()
            if not vid_s:
                continue
            marker = markers.get(vid_s)
            status = str(getattr(state, "status", "") or "").strip().lower()
            marker_status = (
                str(getattr(marker, "status", "") or "").strip().lower()
                if marker is not None
                else ""
            )
            terminal = (
                status in terminal_statuses
                or marker_status in terminal_statuses
                or bool(getattr(state, "rescued", False))
                or bool(getattr(state, "dead", False))
                or bool(getattr(state, "unreachable", False))
                or bool(getattr(state, "cancelled", False))
            )
            vpos = None
            if marker is not None:
                vpos = getattr(marker, "pos", None)
            if vpos is None:
                vpos = getattr(state, "last_known_position", None)
            vcell: tuple[int, int] | None = None
            if vpos is not None and len(vpos) >= 2:
                vcell = (int(vpos[0]), int(vpos[1]))

            pair = self._find_active_firefighter_for_victim(vid_s, marker)
            assigned_ff_id = str(pair[0]) if pair is not None else ""
            approaching = False
            assigned_approaching = False
            if vcell is not None:
                for ff_id, _ff_marker, ff_cell in living:
                    dist = abs(ff_cell[0] - vcell[0]) + abs(ff_cell[1] - vcell[1])
                    key = (ff_id, vid_s)
                    new_dists[key] = dist
                    if not assigned_ff_id or ff_id != assigned_ff_id:
                        continue
                    prev = prev_dists.get(key)
                    if prev is not None and dist < int(prev):
                        approaching = True
                        assigned_approaching = True

            confirmed = bool(getattr(state, "confirmed", False)) or marker_status in (
                "confirmed",
                "assigned",
                "rescued",
            )
            geo_reachable = bool(vcell is not None and vcell in reachable_cells)
            flags[vid_s] = {
                "status": status or marker_status,
                "terminal": terminal,
                "assigned": bool(assigned_ff_id),
                "assigned_approaching": assigned_approaching,
                "geo_reachable": geo_reachable,
                "confirmed": confirmed,
                "approaching": approaching,
            }

        self._ff_victim_distances = new_dists
        geo_streaks = getattr(self, "_unreachable_geo_streak", None)
        if not isinstance(geo_streaks, dict):
            geo_streaks = {}
        undetected_streaks = getattr(self, "_unreachable_undetected_streak", None)
        if not isinstance(undetected_streaks, dict):
            undetected_streaks = {}
        marked, geo_streaks, undetected_streaks = unreachable_escape_victims(
            flags,
            geo_streaks,
            undetected_streaks,
        )
        self._unreachable_geo_streak = geo_streaks
        self._unreachable_undetected_streak = undetected_streaks
        if not marked:
            return

        step = int(getattr(self, "evaluation_timesteps_counter", 0) or 0)
        log = getattr(self, "_unreachable_escape_log", None)
        if not isinstance(log, list):
            log = []
            self._unreachable_escape_log = log
        for vid, cause in marked:
            marker = markers.get(vid)
            pair = self._find_active_firefighter_for_victim(vid, marker)
            if pair is not None:
                ff_id, _ff_marker = pair
                self._execute_physical_rescue_via_executor(
                    PhysicalRescueCommand(
                        action="unassign",
                        victim_id=vid,
                        firefighter_id=ff_id,
                        reason=cause or "unreachable_escape",
                        metadata={},
                    )
                )
            if cause == UNREACHABLE_CAUSE_GEOGRAPHIC:
                streak = int(geo_streaks.get(vid, 0) or 0)
            elif cause == UNREACHABLE_CAUSE_UNDETECTED:
                streak = int(undetected_streaks.get(vid, 0) or 0)
            else:
                streak = 0
            log.append(
                {
                    "step": step,
                    "victim_id": vid,
                    "reason": cause or "unreachable_escape",
                    "cause": cause,
                    "streak": streak,
                }
            )
            self._mark_victim_unreachable(
                vid, marker, reason=cause or "unreachable_escape", cause=cause
            )

    def _dispatch_firefighter_to_victim(
        self,
        victim_id: str,
        victim_marker: Any,
        reason: str,
    ) -> bool:
        """Test-compat wrapper: planner pairing + RescueExecutor physical apply."""
        snapshot = self.get_rescue_operational_snapshot()
        decision = select_rescue_assignment(
            snapshot, str(reason or ""), victim_id=str(victim_id or "")
        )
        executor = self._physical_rescue_executor()
        result = executor.apply_physical_pairing_decision(
            self, decision, victim_marker=victim_marker
        )
        return bool(result.get("success"))

    def _on_firefighter_route_blocked(self, ff_marker: Any) -> None:
        ff_id = self._firefighter_id_from_marker(ff_marker)
        victim_marker = getattr(ff_marker, "rescued_victim", None)
        victim_id = (
            self._victim_id_from_agent(victim_marker) if victim_marker is not None else ""
        )
        blocked_key = (ff_id, victim_id or "none")
        if blocked_key not in self._rescue_blocked_logged:
            unit_label = str(getattr(ff_marker, "unit_id", ff_id) or ff_id)
            print(f"[Rescue Blocked] FF-{unit_label} no safe route")
            self._rescue_blocked_logged.add(blocked_key)

        if not victim_id or victim_marker is None:
            return
        self._record_rescue_event(
            victim_id,
            ff_id,
            "route_blocked",
            "no_safe_route",
            {},
        )
        if not self._victim_needs_rescue(victim_id, victim_marker):
            return

        self._enqueue_rescue_incident(
            {
                "type": "route_blocked",
                "victim_id": victim_id,
                "firefighter_id": ff_id,
                "reason": "replacement_after_blocked",
                "metadata": {},
            }
        )
        self._process_rescue_incidents()

    def _try_replacement_after_firefighter_casualty(
        self, victim_marker: Any,
    ) -> None:
        victim_id = self._victim_id_from_agent(victim_marker)
        if not victim_id or not self._victim_needs_rescue(victim_id, victim_marker):
            return
        self._enqueue_rescue_incident(
            {
                "type": "firefighter_casualty",
                "victim_id": victim_id,
                "firefighter_id": None,
                "reason": "replacement_after_casualty",
                "metadata": {},
            }
        )
        self._process_rescue_incidents()

    def _check_fire_casualties(self) -> None:
        """Mark victims/firefighters dead when fire reaches their cell."""
        fire_cells: set[tuple[int, int]] = set()
        for agent in self.schedule.agents:
            if type(agent).__name__ != "Fire":
                continue
            pos = getattr(agent, "pos", None)
            if pos is None:
                continue
            try:
                is_burning = getattr(agent, "is_burning", None)
                if callable(is_burning) and not is_burning():
                    continue
            except Exception:
                pass
            fire_cells.add((int(pos[0]), int(pos[1])))

        if not fire_cells:
            return

        victim_markers = getattr(self, "victim_marker_agents", {}) or {}
        for vid, marker in victim_markers.items():
            status = str(getattr(marker, "status", "") or "").strip().lower()
            if status in ("dead", "rescued"):
                continue
            pos = getattr(marker, "pos", None)
            if pos is None:
                continue
            cell = (int(pos[0]), int(pos[1]))
            if cell not in fire_cells:
                continue
            try:
                marker.status = "dead"
            except Exception:
                pass
            managed = getattr(self, "managed_victims", None)
            if isinstance(managed, dict):
                state = managed.get(vid)
                if state is not None:
                    try:
                        state.status = "dead"
                    except Exception:
                        pass
                    try:
                        state.rescued = False
                    except Exception:
                        pass
                    try:
                        state.cancelled = True
                    except Exception:
                        pass
                    try:
                        state.rescue_assigned = False
                    except Exception:
                        pass
                    try:
                        state.unreachable = False
                    except Exception:
                        pass
                    try:
                        state.unreachable_cause = ""
                    except Exception:
                        pass
                    attrs = getattr(state, "attributes", None)
                    if isinstance(attrs, dict):
                        attrs.pop("unreachable_cause", None)
            runtime_victims = getattr(self.victim_runtime_model, "victims", None)
            if isinstance(runtime_victims, dict) and vid in runtime_victims:
                try:
                    del runtime_victims[vid]
                except Exception:
                    pass
            try:
                self._clear_rescue_path()
            except Exception:
                pass
            print(f"[Casualty] {vid} reached by fire at {cell}")
            self._record_rescue_event(
                vid,
                self._firefighter_id_for_victim(vid),
                "victim_dead",
                "fire_casualty",
                {"cell": cell},
            )
            self._enqueue_rescue_incident(
                {
                    "type": "victim_dead",
                    "victim_id": vid,
                    "firefighter_id": None,
                    "reason": "fire_casualty",
                    "metadata": {"cell": cell},
                }
            )

        ff_markers = getattr(self, "firefighter_marker_agents", {}) or {}
        for ff_id, ff_marker in ff_markers.items():
            if getattr(ff_marker, "dead", False):
                continue
            status = str(getattr(ff_marker, "status", "") or "").strip().lower()
            if status == "dead":
                continue
            pos = getattr(ff_marker, "pos", None)
            if pos is None:
                continue
            cell = (int(pos[0]), int(pos[1]))
            if cell not in fire_cells:
                continue
            victim_ref = getattr(ff_marker, "rescued_victim", None)
            had_active_rescue = bool(
                getattr(ff_marker, "assigned", False)
                or getattr(ff_marker, "target_pos", None) is not None
                or victim_ref is not None
            )
            casualty_vid = (
                self._victim_id_from_agent(victim_ref) if victim_ref is not None else ""
            )
            if had_active_rescue and casualty_vid:
                self._execute_physical_rescue_via_executor(
                    PhysicalRescueCommand(
                        action="unassign",
                        victim_id=casualty_vid,
                        firefighter_id=str(ff_id),
                        reason="firefighter_fire_casualty",
                        metadata={"reset_victim_pending": True},
                    )
                )
            ff_marker.dead = True
            ff_marker.status = "dead"
            ff_marker.exiting = False
            ff_marker.exit_target = None
            managed_ff = getattr(self, "managed_firefighters", None)
            if isinstance(managed_ff, dict):
                ff_state = managed_ff.get(ff_id)
                if ff_state is not None:
                    try:
                        ff_state.availability = "unavailable"
                    except Exception:
                        pass
                    try:
                        ff_state.assignment_state = "unassigned"
                    except Exception:
                        pass
                    try:
                        ff_state.route_state = "cancelled"
                    except Exception:
                        pass
            if had_active_rescue:
                self._rescue_path_clear_requested = True
            unit_id = str(getattr(ff_marker, "unit_id", ff_id) or ff_id)
            print(f"[Casualty] FF-{unit_id} reached by fire at {cell}")
            self._record_rescue_event(
                casualty_vid,
                ff_id,
                "casualty",
                "firefighter_fire_casualty",
                {"cell": cell},
            )
            if victim_ref is not None:
                if casualty_vid:
                    self._enqueue_rescue_incident(
                        {
                            "type": "firefighter_casualty",
                            "victim_id": casualty_vid,
                            "firefighter_id": ff_id,
                            "reason": "replacement_after_casualty",
                            "metadata": {"cell": cell},
                        }
                    )

        self._sync_firefighter_operational_knowledge()
        self._process_rescue_incidents()
        self._assert_no_direct_rescue_mutation()

    def _sync_firefighter_marker_status(self) -> None:
        """Mirror firefighter marker status into managed + knowledge models."""
        self._revalidate_route_blocked_firefighters()
        self._sync_firefighter_operational_knowledge()

    def _victim_id_from_agent(self, agent: Any) -> str:
        """Resolve managed victim id from a Victim marker agent."""
        vid = str(getattr(agent, "victim_id", "") or "").strip()
        if vid:
            return vid
        unit_id = str(getattr(agent, "unit_id", "") or "").strip()
        if unit_id:
            return unit_id
        markers = getattr(self, "victim_marker_agents", None)
        if isinstance(markers, dict):
            for known_id, marker in markers.items():
                if marker is agent:
                    return str(known_id)
        return ""

    def _finalize_rescued_victim(
        self,
        victim_id: str,
        agent: Any | None = None,
        firefighter_id: str | None = None,
    ) -> None:
        """Mark a victim rescued and remove it from active UAV targeting."""
        vid = str(victim_id or "").strip()
        if not vid and agent is not None:
            vid = self._victim_id_from_agent(agent)
        if not vid:
            return

        managed = getattr(self, "managed_victims", None)
        if isinstance(managed, dict):
            state = managed.get(vid)
            if state is not None and (
                getattr(state, "dead", False)
                or getattr(state, "cancelled", False)
                or str(getattr(state, "status", "")).lower()
                in {"dead", "cancelled"}
            ):
                return
        markers = getattr(self, "victim_marker_agents", None)
        if isinstance(markers, dict):
            marker = markers.get(vid)
            if marker is not None and (
                str(getattr(marker, "status", "")).lower() in {"dead", "cancelled"}
            ):
                return

        ff_id = str(firefighter_id or "").strip() or self._firefighter_id_for_victim(vid)
        self._enqueue_rescue_incident(
            {
                "type": "rescue_complete",
                "victim_id": vid,
                "firefighter_id": ff_id or None,
                "reason": "physical_rescue_complete",
                "metadata": {"victim_agent": agent},
            }
        )
        self._process_rescue_incidents()

    def _sync_victim_agent_status(self) -> None:
        """Sync display-only Victim marker colors from managed victim state."""
        _valid_statuses = frozenset(
            {
                "candidate",
                "confirmed",
                "assigned",
                "rescued",
                "cancelled",
                "delayed",
                "unreachable",
            }
        )
        markers = getattr(self, "victim_marker_agents", None)
        if not isinstance(markers, dict):
            return
        managed = getattr(self, "managed_victims", None)
        if not isinstance(managed, dict):
            return
        for victim_id, marker in markers.items():
            try:
                state = managed.get(victim_id)
                if state is None:
                    continue
                if str(getattr(marker, "status", "") or "").strip().lower() == "dead":
                    continue
                if str(getattr(state, "status", "") or "").strip().lower() == "dead":
                    continue
                status_lower = str(getattr(state, "status", "") or "").strip().lower()
                if getattr(state, "rescued", False) or status_lower == "rescued":
                    try:
                        marker.status = "rescued"
                    except Exception:
                        pass
                    continue
                if status_lower in ("unreachable", "cancelled"):
                    if status_lower in _valid_statuses:
                        marker.status = status_lower
                    continue
                if getattr(state, "confirmed", False):
                    marker.status = "confirmed"
                if getattr(state, "rescue_assigned", False):
                    marker.status = "assigned"
                status_str = str(getattr(state, "status", "") or "").strip().lower()
                if status_str in _valid_statuses:
                    marker.status = status_str
                if getattr(state, "rescue_assigned", False):
                    active = self._find_active_firefighter_for_victim(victim_id, marker)
                    if active is None:
                        try:
                            state.rescue_assigned = False
                        except Exception:
                            pass
                    else:
                        continue
                if (
                    getattr(self, "_allow_sync_victim_dispatch_fallback", False)
                    and (
                        getattr(state, "confirmed", False)
                        or marker.status == "confirmed"
                    )
                ):
                    if self._find_active_firefighter_for_victim(victim_id, marker):
                        continue
                    self._dispatch_firefighter_to_victim(
                        victim_id, marker, "initial"
                    )
            except Exception:
                continue

    def _log_step_summary(self) -> None:
        if not getattr(self, "debug_log", False):
            return
        try:
            step_num = int(getattr(self, "evaluation_timesteps_counter", 0))
        except (TypeError, ValueError):
            return
        if step_num % 10 != 0:
            return

        failsafe_mode = "unknown"
        try:
            fs = getattr(self, "latest_failsafe_state", None)
            if fs is not None:
                mode = getattr(fs, "mode", None)
                if mode is not None:
                    failsafe_mode = str(getattr(mode, "value", mode))
        except Exception:
            pass

        path_by_uav: dict[str, object] = {}
        try:
            planning = getattr(self, "latest_planning_result", None)
            if planning is not None:
                if isinstance(planning, dict):
                    raw_paths = planning.get("path_decisions", {})
                else:
                    raw_paths = getattr(planning, "path_decisions", {})
                if isinstance(raw_paths, dict):
                    path_by_uav = raw_paths
                elif isinstance(raw_paths, (list, tuple)):
                    for path_dec in raw_paths:
                        if path_dec is None:
                            continue
                        uav_key = str(
                            getattr(path_dec, "uav_id", "")
                            or getattr(path_dec, "selected_option_id", "")
                        )
                        if uav_key:
                            path_by_uav[uav_key] = path_dec
        except Exception:
            path_by_uav = {}

        print(f"[UAV debug] step={step_num} failsafe_mode={failsafe_mode}")
        planning = getattr(self, "latest_planning_result", None) or {}
        fsd = (
            planning.get("fail_safe_decision")
            if isinstance(planning, dict)
            else getattr(planning, "fail_safe_decision", None)
        )
        if fsd is not None:
            print(
                f"  [FailSafeDecision] "
                f"mission_mode={getattr(fsd, 'mission_mode', '?')} "
                f"search_mode_active={getattr(fsd, 'search_mode_active', '?')} "
                f"action={getattr(fsd, 'fail_safe_action', '?')}"
            )
        try:
            uav_agents = [
                agent for agent in self.schedule.agents if type(agent) is agents.UAV
            ]
        except Exception:
            uav_agents = []

        for agent in uav_agents:
            try:
                uav_id = str(getattr(agent, "unique_id", ""))
                role = ""
                managed = getattr(self, "managed_uav_states", {}) or {}
                if uav_id in managed:
                    role = str(getattr(managed[uav_id], "role", "") or "")
                if not role:
                    rm = getattr(self, "uav_resource_model", None)
                    if rm is not None:
                        state = getattr(rm, "by_uav_id", {}).get(uav_id)
                        if state is not None:
                            role = str(getattr(state, "current_role", "") or "")

                pos = getattr(agent, "pos", None)
                pos_str = str(pos) if pos is not None else "?"

                battery = getattr(agent, "battery_level", "?")
                if isinstance(battery, (int, float)):
                    battery_str = f"{float(battery):.1f}"
                else:
                    battery_str = str(battery)

                selected_dir = str(getattr(agent, "selected_dir", "?"))

                next_action = ""
                selected_option_id = ""
                target_hint = ""
                path_dec = path_by_uav.get(uav_id)
                if path_dec is not None:
                    next_action = str(getattr(path_dec, "next_action", "") or "")
                    selected_option_id = str(
                        getattr(path_dec, "selected_option_id", "") or ""
                    )
                    ctx = getattr(path_dec, "uncertainty_context", None)
                    if isinstance(ctx, dict):
                        for key in ("target_position", "target_region"):
                            value = ctx.get(key)
                            if value is not None:
                                target_hint = f"{key}={value}"
                                break

                exec_parts: list[str] = []
                try:
                    execution = getattr(self, "latest_execution_result", None)
                    if isinstance(execution, dict):
                        if "fail_safe_override_active" in execution:
                            exec_parts.append(
                                "fail_safe_override_active="
                                f"{execution.get('fail_safe_override_active')}"
                            )
                        local = execution.get("local")
                        if isinstance(local, dict):
                            if "fail_safe_override_active" in local:
                                exec_parts.append(
                                    "local_fail_safe_override_active="
                                    f"{local.get('fail_safe_override_active')}"
                                )
                            uav_results = local.get("uav_results")
                            uav_result = (
                                uav_results.get(uav_id)
                                if isinstance(uav_results, dict)
                                else None
                            )
                            if isinstance(uav_result, dict):
                                if "applied" in uav_result:
                                    exec_parts.append(
                                        f"exec_applied={uav_result.get('applied')}"
                                    )
                                action = uav_result.get("action")
                                if action is not None:
                                    exec_parts.append(f"exec_action={action}")
                                if "selected_dir" in uav_result:
                                    exec_parts.append(
                                        f"exec_selected_dir={uav_result.get('selected_dir')}"
                                    )
                                for target_key in (
                                    "search_target",
                                    "target",
                                    "target_position",
                                    "target_region",
                                ):
                                    target_value = uav_result.get(target_key)
                                    if target_value is not None:
                                        exec_parts.append(
                                            f"exec_target={target_value}"
                                        )
                                        break
                                if "override_exempt" in uav_result:
                                    exec_parts.append(
                                        f"override_exempt={uav_result.get('override_exempt')}"
                                    )
                                exempt_reason = uav_result.get("override_exempt_reason")
                                if exempt_reason is not None:
                                    exec_parts.append(
                                        f"override_exempt_reason={exempt_reason}"
                                    )
                    if not any(
                        part.startswith("exec_action=") for part in exec_parts
                    ):
                        agent_action = getattr(agent, "execution_action", None)
                        if agent_action is not None:
                            exec_parts.append(f"exec_action={agent_action}")
                except Exception:
                    pass
                stuck_ct = getattr(self, "_uav_stuck_counts", {}).get(str(uav_id), 0)
                before_pos = getattr(self, "_uav_positions_before_step", {}).get(
                    str(uav_id), None
                )
                current_pos_key = str(uav_id)
                exec_parts.append(
                    f"stuck_count={stuck_ct} before_pos={before_pos} "
                    f"current_pos_key={current_pos_key}"
                )
                exec_info = " ".join(exec_parts)
                sector = getattr(self, "_uav_sector_assignments", {}).get(uav_id)
                sector_hint = f"sector={sector} " if sector else ""

                print(
                    f"  uav={uav_id} role={role} pos={pos_str} "
                    f"{sector_hint}"
                    f"battery={battery_str} dir={selected_dir} "
                    f"next_action={next_action} option_id={selected_option_id} "
                    f"{target_hint} {exec_info}".rstrip()
                )
            except Exception:
                continue

    def get_dashboard_state(self) -> dict[str, Any]:
        """Read-only post-hoc dashboard snapshot (Step 12B)."""
        return self.dashboard_state_builder.build(self)

    def export_dashboard_json(
        self, output_dir: str | None = None
    ) -> dict[str, Any]:
        """Export dashboard state, timeline, and explanations to JSON (read-only)."""
        paths = self.dashboard_exporter.export_all(self, output_dir)
        return {key: str(path) for key, path in paths.items()}

    # Mesa framework native method, which is overwritten, necessary for setting next state of the simulation
    def step(self):
        self.datacollector.collect(self)

        # check if simulation ended, if so print MR1 and MR2 overall metrics,
        # and finish loop. Otherwise, keep executing.
        if BATCH_SIZE == self.evaluation_timesteps_counter - 1:
            print(" --- MR1 --- ")
            print(self.MR1_LIST)
            print(" --- MR2 --- ")
            print(self.MR2_VALUE)
            sys.exit(0)

        self.evaluation_timesteps_counter += 1
        current_step_time = float(self.evaluation_timesteps_counter)

        self._update_fire_tracker_sector_assignments()
        self._clear_uav_execution_direction_flags()
        self.monitoring_buffer.clear()
        self._uav_positions_before_step = {}
        try:
            for agent in self.schedule.agents:
                if type(agent).__name__ != "UAV":
                    continue
                pos = getattr(agent, "pos", None)
                if pos is not None:
                    self._uav_positions_before_step[str(agent.unique_id)] = (
                        int(pos[0]),
                        int(pos[1]),
                    )
        except Exception:
            pass

        if self._is_extension_pipeline_active():
            self._run_pre_move_decision_cycle(current_step_time)

        if sum(isinstance(i, agents.UAV) for i in self.schedule.agents) > 0:
            self._prepare_uav_directions_for_step()
            state = self.state()  # s_t
            self.MR1(state)
            self.MR2()

        self.schedule.step()
        self._run_post_move_decision_cycle(current_step_time)
        self._update_unreachable_victims()
        self._log_step_summary()
        try:
            self.latest_dashboard_state = self.get_dashboard_state()
        except Exception:
            pass
