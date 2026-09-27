"""Global adaptation space generator skeleton."""

import math
from typing import Any

from .adaptation_option_objects import AdaptationOption, MissionAdaptationOption, Scope
from .trigger_input import adaptation_trigger_metadata
from .adaptation_results import GlobalAdaptationSpace


class GlobalAdaptationSpaceGenerator:
    """Builds global adaptation option spaces."""

    def _generate_global_noop_option(
        self, timestamp: float, originating_trigger: str | None = None
    ) -> MissionAdaptationOption:
        trigger = (
            originating_trigger if originating_trigger is not None else "global_analysis"
        )
        return MissionAdaptationOption(
            option_id="global_stability_maintain_current_config",
            option_type="stability_control",
            target_entity="fleet",
            parameters={
                "stability_action": "maintain_current_config",
                "do_nothing": True,
            },
            expected_effect=(
                "Keep current global mission configuration; no adaptation applied"
            ),
            cost_estimate=0.0,
            risk_estimate=0.0,
            confidence=1.0,
            scope=Scope["global"],
            timestamp=timestamp,
            originating_trigger=trigger,
            explanation_hint=(
                "Do-nothing global baseline; always present for stability comparison"
            ),
        )

    def generate(
        self,
        global_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> GlobalAdaptationSpace:
        options: list[AdaptationOption] = []

        options.extend(
            self._generate_role_assignment_options(
                global_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_task_allocation_options(
                global_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_coverage_strategy_options(
                global_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_resource_reallocation_options(
                global_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.extend(
            self._generate_fail_safe_mission_options(
                global_analysis_result,
                runtime_models,
                timestamp,
            )
        )
        options.append(self._generate_global_noop_option(timestamp))

        return GlobalAdaptationSpace(
            options=options,
            trigger_references=[],
            explanation_summaries=[],
            timestamp=timestamp,
        )

    def _generate_role_assignment_options(
        self,
        global_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        # GLOBAL_PLANNER_MODE (outputs/planner_part1.txt 6.1), read at call time through a
        # lazy import (a sys.modules lookup at runtime). At 0 the rest of this method is
        # today's body, line for line.
        import agents as _agents

        if _agents.global_planner_mode() != 0:
            return self._generate_role_switch_options(
                global_analysis_result,
                runtime_models,
                timestamp,
            )

        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, trigger_context, confidence, trigger_signals = adaptation_trigger_metadata(
            global_analysis_result,
            default_label="global_analysis",
        )
        trigger_context = trigger_context.lower()
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        current_role = read_value(runtime_models, "current_role", None)
        role_stability_timer = read_value(runtime_models, "role_stability_timer", None)
        role_switch_count = read_value(runtime_models, "role_switch_count", None)
        battery_state = read_value(
            runtime_models,
            "battery_state",
            read_value(runtime_models, "battery", read_value(runtime_models, "battery_level")),
        )
        resource_state = read_value(
            runtime_models,
            "resource_state",
            read_value(runtime_models, "resources", None),
        )
        target_entity = read_value(global_analysis_result, "target_entity", "mission")

        base_parameters = {
            "current_role": current_role,
            "role_stability_timer": role_stability_timer,
            "role_switch_count": role_switch_count,
            "battery_state": battery_state,
            "resource_state": resource_state,
        }
        roles = [
            "fire_tracking",
            "victim_search",
            "victim_confirmation",
            "victim_tracking",
            "communication_relay",
        ]

        options: list[AdaptationOption] = [
            MissionAdaptationOption(
                option_id=f"global_role_assignment_{role}",
                option_type="role_assignment",
                target_entity=target_entity,
                parameters={**base_parameters, "assigned_role": role},
                expected_effect=f"Assign mission role: {role}",
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope["global"],
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=f"Step 6 trigger context suggests considering {role}.",
            )
            for role in roles
        ]

        options.append(
            MissionAdaptationOption(
                option_id="global_role_assignment_maintain_current",
                option_type="role_assignment",
                target_entity=target_entity,
                parameters={**base_parameters, "action": "maintain_current_role"},
                expected_effect="Maintain current mission role assignments",
                cost_estimate=0.0,
                risk_estimate=0.0,
                confidence=confidence,
                scope=Scope["global"],
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint="Always available baseline option for role stability.",
            )
        )

        instability_terms = ("instability", "oscillation", "unstable", "role_switch")
        if any(term in trigger_context for term in instability_terms):
            options.append(
                MissionAdaptationOption(
                    option_id="global_role_assignment_delay_change",
                    option_type="role_assignment",
                    target_entity=target_entity,
                    parameters={**base_parameters, "action": "delay_role_change"},
                    expected_effect="Delay mission role changes during instability",
                    cost_estimate=0.1,
                    risk_estimate=0.1,
                    confidence=confidence,
                    scope=Scope["global"],
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint=(
                        "Instability or oscillation trigger suggests delaying role changes."
                    ),
                )
            )

        return options

    # ---- GLOBAL_PLANNER_MODE 1: the global planner for UAV roles -----------------------
    # Design outputs/planner_part1.txt sections 2-3. Reached only when
    # agents.global_planner_mode() != 0. READS ONLY: knowledge models (fire belief,
    # visibility status map, uav_resource_model.by_uav_id via .get), managed_victims'
    # length and confirmed flags, cfv constants at call time, the analyzer's triggers,
    # and from the UAV agents rtb_active / rtb_docked / berths / drain rates and the pure
    # trigger formula agents.rtb_trigger_level_at. No RNG, no print, no write.

    def _generate_role_switch_options(
        self,
        global_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        from . import role_option_values as rov

        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, trigger_context, confidence, _signals = adaptation_trigger_metadata(
            global_analysis_result,
            default_label="global_analysis",
        )
        trigger_context = trigger_context.lower()

        base_parameters = {
            "current_role": read_value(runtime_models, "current_role", None),
            "role_stability_timer": read_value(runtime_models, "role_stability_timer", None),
            "role_switch_count": read_value(runtime_models, "role_switch_count", None),
            "battery_state": read_value(
                runtime_models,
                "battery_state",
                read_value(runtime_models, "battery", read_value(runtime_models, "battery_level")),
            ),
            "resource_state": read_value(
                runtime_models,
                "resource_state",
                read_value(runtime_models, "resources", None),
            ),
        }
        target_entity = read_value(global_analysis_result, "target_entity", "mission")

        options: list[AdaptationOption] = []
        for spec in self._role_switch_specs(global_analysis_result, runtime_models):
            uid, from_role, to_role, battery, values = spec
            options.append(
                MissionAdaptationOption(
                    option_id=f"global_role_assignment_{to_role}_{uid}",
                    option_type="role_assignment",
                    target_entity=uid,
                    parameters={
                        **base_parameters,
                        # a STRING (hashable: the constraint filter tests it against sets)
                        "assigned_role": to_role,
                        "target_uav_id": uid,
                        # the scorer's own change reader: Cost_switch is charged on a change
                        "from_role": from_role,
                        "to_role": to_role,
                        "battery_level": battery,
                        **values,
                    },
                    expected_effect=f"Switch UAV {uid} from {from_role} to {to_role}",
                    cost_estimate=1.0,
                    risk_estimate=0.2,
                    # D-2 (ruled): the baseline's confidence; the options' evidence is
                    # the nine values, not the analyzer's trigger confidence.
                    confidence=1.0,
                    scope=Scope["global"],
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint=(
                        f"Global planner: move UAV {uid} from {from_role} to {to_role}."
                    ),
                )
            )

        zeros = rov.zero_values()
        options.append(
            MissionAdaptationOption(
                option_id="global_role_assignment_maintain_current",
                option_type="role_assignment",
                target_entity=target_entity,
                parameters={**base_parameters, "action": "maintain_current_role", **zeros},
                expected_effect="Maintain current mission role assignments",
                cost_estimate=0.0,
                risk_estimate=0.0,
                confidence=confidence,
                scope=Scope["global"],
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint="Always available baseline option for role stability.",
            )
        )

        instability_terms = ("instability", "oscillation", "unstable", "role_switch")
        if any(term in trigger_context for term in instability_terms):
            options.append(
                MissionAdaptationOption(
                    option_id="global_role_assignment_delay_change",
                    option_type="role_assignment",
                    target_entity=target_entity,
                    parameters={**base_parameters, "action": "delay_role_change", **zeros},
                    expected_effect="Delay mission role changes during instability",
                    cost_estimate=0.1,
                    risk_estimate=0.1,
                    confidence=confidence,
                    scope=Scope["global"],
                    timestamp=timestamp,
                    originating_trigger=originating_trigger,
                    explanation_hint=(
                        "Instability or oscillation trigger suggests delaying role changes."
                    ),
                )
            )
        return options

    @staticmethod
    def _unstable_uav_ids(global_analysis_result: Any) -> set[str]:
        """I5: the UAVs a current OSCILLATION_RISK or INSTABILITY_DETECTED trigger names."""
        flagged: set[str] = set()
        sources: list[Any] = []
        for key in ("all_triggers", "triggers", "trigger_list"):
            value = (
                global_analysis_result.get(key)
                if isinstance(global_analysis_result, dict)
                else getattr(global_analysis_result, key, None)
            )
            if isinstance(value, (list, tuple)):
                sources.extend(value)
        for trig in sources:
            if isinstance(trig, dict):
                ttype = trig.get("trigger_type")
                entities = trig.get("affected_entities")
            else:
                ttype = getattr(trig, "trigger_type", None)
                entities = getattr(trig, "affected_entities", None)
            if str(ttype or "") not in ("OSCILLATION_RISK", "INSTABILITY_DETECTED"):
                continue
            for entity in entities or ():
                flagged.add(str(entity))
        return flagged

    def _role_switch_specs(
        self,
        global_analysis_result: Any,
        runtime_models: Any,
    ) -> list[tuple[str, str, str, float, dict[str, float]]]:
        """(uid, from_role, to_role, battery, nine values) for every UAV that may switch:
        I1 available, I2 not the last available member of its role, I3 a real change,
        I4 a live id from uav_resource_model.by_uav_id, I5 not flagged unstable."""
        import agents as _agents
        import common_fixed_variables as _cfv
        from . import role_option_values as rov

        if not isinstance(runtime_models, dict):
            return []
        model = runtime_models.get("simulation_model")
        resource_model = runtime_models.get("uav_resource_model")
        by_uav_id = getattr(resource_model, "by_uav_id", None)
        if model is None or not isinstance(by_uav_id, dict) or not by_uav_id:
            return []

        uav_agents = {
            str(a.unique_id): a for a in model.schedule.agents if type(a) is _agents.UAV
        }
        uids = [str(k) for k in by_uav_id.keys()]
        try:
            uids.sort(key=int)
        except ValueError:
            uids.sort()

        role_of: dict[str, str | None] = {
            uid: rov.live_role(model._uav_assignment_role(uid)) for uid in uids
        }
        holders = {
            role: sum(1 for uid in uids if role_of[uid] == role) for role in rov.LIVE_ROLES
        }

        def position(uid: str) -> tuple[int, int] | None:
            state = by_uav_id.get(uid)
            pos = getattr(state, "current_position", None) if state is not None else None
            if pos is None:
                agent = uav_agents.get(uid)
                pos = getattr(agent, "pos", None) if agent is not None else None
            if pos is None:
                return None
            return (int(round(float(pos[0]))), int(round(float(pos[1]))))

        def battery_of(uid: str) -> float | None:
            state = by_uav_id.get(uid)
            level = getattr(state, "battery_level", None) if state is not None else None
            if level is None:
                agent = uav_agents.get(uid)
                level = getattr(agent, "battery_level", None) if agent is not None else None
            return None if level is None else float(level)

        def working(uid: str) -> bool:
            agent = uav_agents.get(uid)
            return (
                agent is not None
                and not bool(getattr(agent, "rtb_active", False))
                and not bool(getattr(agent, "rtb_docked", False))
            )

        returns_home = _agents.base_station_mode() >= 2
        flagged = self._unstable_uav_ids(global_analysis_result)
        available: dict[str, tuple[tuple[int, int], float, float, float]] = {}
        for uid in uids:
            agent = uav_agents.get(uid)
            pos = position(uid)
            battery = battery_of(uid)
            if (
                agent is None
                or pos is None
                or battery is None
                or role_of[uid] is None
                or not working(uid)
                or uid in flagged
            ):
                continue
            per_move = float(agent.battery_drain_per_step) + float(agent.battery_drain_per_move)
            trigger_here = float(_agents.rtb_trigger_level_at(agent, pos))
            if returns_home and battery - trigger_here <= rov.AVAILABILITY_MARGIN_STEPS * per_move:
                continue
            available[uid] = (pos, battery, trigger_here, per_move)
        if not available:
            return []
        n_available = {
            role: sum(1 for uid in available if role_of[uid] == role) for role in rov.LIVE_ROLES
        }

        # the four demands (section 3.0)
        vis_state = getattr(runtime_models.get("visibility_model"), "state", None)
        status_map = getattr(vis_state, "observation_status_map", None) or {}

        def status_text(value: Any) -> str:
            return str(getattr(value, "value", value))

        never_seen = [
            (int(c[0]), int(c[1])) for c, s in status_map.items() if status_text(s) == "never_seen"
        ]
        belief = getattr(runtime_models.get("fire_runtime_model"), "belief", None)
        believed = [
            (int(c[0]), int(c[1])) for c in list(getattr(belief, "estimated_burning_cells", ()) or ())
        ]
        stale = {c for c in believed if status_text(status_map.get(c)) == "stale_information"}
        fresh = [c for c in believed if c not in stale]
        managed_victims = getattr(model, "managed_victims", None) or {}
        n_detected = sum(
            1 for v in managed_victims.values() if bool(getattr(v, "confirmed", False))
        )
        demands = {
            "fire": rov.fire_demand(len(fresh)),
            "stale": rov.stale_demand(len(stale)),
            "victim": rov.victim_demand(len(managed_victims), n_detected),
            "uncertainty": rov.uncertainty_demand(len(never_seen), len(status_map)),
        }

        def nearest(pos: tuple[int, int], cells: list[tuple[int, int]]):
            best = None
            for c in cells:
                key = (abs(pos[0] - c[0]) + abs(pos[1] - c[1]), c[0], c[1])
                if best is None or key < best:
                    best = key
            return (None, None) if best is None else ((best[1], best[2]), best[0])

        security_distance = float(getattr(_cfv, "SECURITY_DISTANCE", 10))
        n_uavs = len(uids)
        specs: list[tuple[str, str, str, float, dict[str, float]]] = []
        for uid in uids:
            if uid not in available:
                continue
            from_role = role_of[uid]
            if n_available[from_role] < 2:
                continue
            to_role = rov.other_role(from_role)
            pos, battery, trigger_here, per_move = available[uid]
            near = 0
            for other in uids:
                if other == uid or role_of[other] != to_role or not working(other):
                    continue
                opos = position(other)
                if opos is None:
                    continue
                if math.hypot(pos[0] - opos[0], pos[1] - opos[1]) <= security_distance:
                    near += 1
            target, distance = nearest(pos, fresh if to_role == rov.FIRE_TRACKER else never_seen)
            trigger_at_target = (
                None if target is None else float(_agents.rtb_trigger_level_at(uav_agents[uid], target))
            )
            state = by_uav_id.get(uid)
            values = rov.switch_option_values(
                from_role=from_role,
                to_role=to_role,
                holders=holders,
                demands=demands,
                n_near_working_in_new_role=near,
                n_uavs=n_uavs,
                battery=battery,
                trigger_here=trigger_here,
                trigger_at_target=trigger_at_target,
                target_distance=distance,
                per_move=per_move,
                drift_level=getattr(state, "drift_level", None),
                role_stability_timer=getattr(state, "role_stability_timer", None),
            )
            specs.append((uid, from_role, to_role, battery, values))
        return specs

    def _generate_task_allocation_options(
        self,
        global_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        def as_region_list(source: Any) -> list[Any]:
            if isinstance(source, dict):
                return list(source.keys())
            if isinstance(source, (list, tuple, set)):
                return list(source)
            return []

        def negative_regions(source: Any) -> list[Any]:
            if isinstance(source, dict):
                return [region for region, observed in source.items() if observed]
            if isinstance(source, (list, tuple, set)):
                regions: list[Any] = []
                for item in source:
                    if isinstance(item, dict):
                        regions.extend(negative_regions(item))
                    else:
                        regions.append(item)
                return regions
            return []

        originating_trigger, trigger_context, confidence, trigger_signals = adaptation_trigger_metadata(
            global_analysis_result,
            default_label="global_analysis",
        )
        trigger_context = trigger_context.lower()
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        fire_probability_map = read_value(
            global_analysis_result,
            "fire_probability_map",
            read_value(runtime_models, "fire_probability_map", {}),
        )
        uncertainty_map = read_value(
            global_analysis_result,
            "uncertainty_map",
            read_value(runtime_models, "uncertainty_map", {}),
        )
        victim_confidence = read_value(
            global_analysis_result,
            "victim_confidence",
            read_value(runtime_models, "victim_confidence", {}),
        )
        negative_observation_maps = read_value(
            global_analysis_result,
            "negative_observation_maps",
            read_value(
                global_analysis_result,
                "negative_observation_map",
                read_value(runtime_models, "negative_observation_maps", {}),
            ),
        )
        stale_information = read_value(
            global_analysis_result,
            "stale_information",
            read_value(runtime_models, "stale_information", {}),
        )
        last_known_fire_regions = as_region_list(
            read_value(
                global_analysis_result,
                "last_known_fire_regions",
                read_value(runtime_models, "last_known_fire_regions", []),
            )
        )
        communication_support_zones = as_region_list(
            read_value(
                global_analysis_result,
                "communication_support_zones",
                read_value(runtime_models, "communication_support_zones", []),
            )
        )
        stale_regions = set(as_region_list(stale_information))
        recently_negative_regions = [
            region
            for region in negative_regions(negative_observation_maps)
            if region not in stale_regions
        ]
        visibility_loss = "visibility" in trigger_context and "loss" in trigger_context
        target_entity = read_value(global_analysis_result, "target_entity", "mission")

        base_parameters = {
            "fire_probability_map": fire_probability_map,
            "uncertainty_map": uncertainty_map,
            "victim_confidence": victim_confidence,
            "negative_observation_maps": negative_observation_maps,
            "stale_information": stale_information,
            "excluded_recent_negative_regions": recently_negative_regions,
        }
        task_options = [
            (
                "assign_high_probability_fire_region",
                "assign_to_high_probability_fire_region",
                {
                    "region_source": "fire_probability_map",
                    "priority_regions": last_known_fire_regions if visibility_loss else [],
                },
                "Assign tasking toward a high-probability fire region",
                "Avoid recent negative observations; use last-known fire regions during visibility loss.",
            ),
            (
                "assign_high_uncertainty_region",
                "assign_to_high_uncertainty_region",
                {"region_source": "uncertainty_map", "trigger_context": trigger_context},
                "Assign tasking toward a high-uncertainty region",
                "Uncertainty triggers suggest collecting information in uncertain regions.",
            ),
            (
                "assign_victim_region",
                "assign_to_victim_region",
                {"region_source": "victim_confidence"},
                "Assign tasking toward a victim region",
                "Victim confidence data suggests considering victim-focused tasking.",
            ),
            (
                "assign_communication_support_zone",
                "assign_to_communication_support_zone",
                {"candidate_zones": communication_support_zones},
                "Assign tasking toward a communication support zone",
                "Communication support zones are available for relay-focused tasking.",
            ),
            (
                "reassign_task",
                "reassign_task",
                {},
                "Reassign an existing mission task",
                "Reassignment option for adapting current task allocation.",
            ),
            (
                "split_region_coverage",
                "split_region_coverage",
                {},
                "Split region coverage across mission assets",
                "Coverage can be split when one region needs broader attention.",
            ),
        ]

        options: list[AdaptationOption] = [
            MissionAdaptationOption(
                option_id=f"global_task_allocation_{option_id}",
                option_type="task_allocation",
                target_entity=target_entity,
                parameters={**base_parameters, **parameters, "task_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope["global"],
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, parameters, expected_effect, explanation_hint in task_options
        ]

        strong_task_region_data = (
            len(triggers) > 0
            or (isinstance(fire_probability_map, dict) and len(fire_probability_map) > 0)
            or (isinstance(uncertainty_map, dict) and len(uncertainty_map) > 0)
            or (isinstance(victim_confidence, dict) and len(victim_confidence) > 0)
            or len(communication_support_zones) > 0
            or len(last_known_fire_regions) > 0
        )
        if not options or not strong_task_region_data:
            task_stability_hint = (
                "Stability baseline: preserve current tasking and sector coverage when "
                "trigger or region evidence is absent or weak."
            )
            options.extend(
                [
                    MissionAdaptationOption(
                        option_id="global_task_allocation_keep_current_task_assignment",
                        option_type="task_allocation",
                        target_entity=target_entity,
                        parameters={
                            **base_parameters,
                            "task_action": "keep_current_task_assignment",
                        },
                        expected_effect="Retain existing global task assignments",
                        cost_estimate=0.0,
                        risk_estimate=0.0,
                        confidence=1.0,
                        scope=Scope["global"],
                        timestamp=timestamp,
                        originating_trigger=originating_trigger,
                        explanation_hint=task_stability_hint,
                    ),
                    MissionAdaptationOption(
                        option_id="global_task_allocation_maintain_current_sector_coverage",
                        option_type="task_allocation",
                        target_entity=target_entity,
                        parameters={
                            **base_parameters,
                            "task_action": "maintain_current_sector_coverage",
                        },
                        expected_effect="Maintain current sector coverage for the fleet",
                        cost_estimate=0.0,
                        risk_estimate=0.0,
                        confidence=1.0,
                        scope=Scope["global"],
                        timestamp=timestamp,
                        originating_trigger=originating_trigger,
                        explanation_hint=task_stability_hint,
                    ),
                ]
            )

        return options

    def _generate_coverage_strategy_options(
        self,
        global_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, trigger_context, confidence, trigger_signals = adaptation_trigger_metadata(
            global_analysis_result,
            default_label="global_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        fire_probability_map = read_value(
            global_analysis_result,
            "fire_probability_map",
            read_value(runtime_models, "fire_probability_map", {}),
        )
        fire_confidence_map = read_value(
            global_analysis_result,
            "fire_confidence_map",
            read_value(runtime_models, "fire_confidence_map", {}),
        )
        uncertainty_map = read_value(
            global_analysis_result,
            "uncertainty_map",
            read_value(runtime_models, "uncertainty_map", {}),
        )
        victim_confidence = read_value(
            global_analysis_result,
            "victim_confidence",
            read_value(runtime_models, "victim_confidence", {}),
        )
        mission_goals = read_value(runtime_models, "mission_goals", {})
        if not mission_goals:
            mission_goal_model = read_value(runtime_models, "mission_goal_model", None)
            if mission_goal_model is not None and hasattr(mission_goal_model, "runtime_context"):
                mission_goals = mission_goal_model.runtime_context()
        goal_priorities = (
            mission_goals.get("goal_priorities", {})
            if isinstance(mission_goals, dict)
            else {}
        )
        belief_gap_regions = []
        if isinstance(fire_probability_map, dict) and isinstance(fire_confidence_map, dict):
            belief_gap_regions = [
                region
                for region, probability in fire_probability_map.items()
                if isinstance(probability, (int, float))
                and probability >= 0.5
                and isinstance(fire_confidence_map.get(region), (int, float))
                and fire_confidence_map[region] <= 0.5
            ]

        search_mode_required = "SEARCH_MODE_REQUIRED" in (
            " ".join(trigger_ids) + " " + trigger_context
        ) or bool(goal_priorities.get("prioritize_victim_search"))
        target_entity = read_value(global_analysis_result, "target_entity", "mission")
        base_parameters = {
            "fire_probability_map": fire_probability_map,
            "fire_confidence_map": fire_confidence_map,
            "uncertainty_map": uncertainty_map,
            "victim_confidence": victim_confidence,
            "search_mode_required": search_mode_required,
            "mission_goal_phase": mission_goals.get("mission_phase") if isinstance(mission_goals, dict) else None,
            "mission_goal_priorities": goal_priorities,
        }
        strategy_options = [
            (
                "fire_front_tracking_mode",
                "fire_front_tracking_mode",
                {"target_source": "fire_probability_map"},
                "Shift coverage strategy toward fire front tracking",
                "Fire probability data supports a fire-front tracking coverage mode.",
            ),
            (
                "uncertainty_reduction_mode",
                "uncertainty_reduction_mode",
                {"target_source": "uncertainty_map"},
                "Shift coverage strategy toward uncertainty reduction",
                "Uncertainty data supports reducing unknown areas.",
            ),
            (
                "victim_search_mode",
                "victim_search_mode",
                {"target_source": "victim_confidence"},
                "Shift coverage strategy toward victim search",
                "Victim confidence data supports victim-oriented coverage.",
            ),
            (
                "belief_gap_reduction_strategy",
                "belief_gap_reduction_strategy",
                {"target_regions": belief_gap_regions},
                "Reduce belief gaps in high-probability low-confidence regions",
                "Belief-gap reduction targets high-probability, low-confidence regions.",
            ),
            (
                "uncertainty_driven_exploration",
                "uncertainty_driven_exploration",
                {"target_source": "uncertainty_map"},
                "Use uncertainty-driven exploration coverage",
                "Exploration can focus on regions with high uncertainty.",
            ),
            (
                "search_mode_activation",
                "search_mode_activation",
                {"explicit_search_mode": search_mode_required},
                "Activate search-oriented coverage mode",
                "SEARCH_MODE_REQUIRED triggers require explicit search-mode options.",
            ),
        ]

        return [
            MissionAdaptationOption(
                option_id=f"global_coverage_strategy_{option_id}",
                option_type="coverage_strategy",
                target_entity=target_entity,
                parameters={**base_parameters, **parameters, "strategy": strategy},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope["global"],
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, strategy, parameters, expected_effect, explanation_hint in (
                strategy_options
            )
        ]

    def _generate_resource_reallocation_options(
        self,
        global_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        def low_value_regions(source: Any) -> list[Any]:
            if isinstance(source, dict):
                return [
                    region
                    for region, value in source.items()
                    if isinstance(value, (int, float)) and value <= 0.2
                ]
            return []

        originating_trigger, _, confidence, trigger_signals = adaptation_trigger_metadata(
            global_analysis_result,
            default_label="global_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)

        predicted_remaining_useful_time = read_value(
            global_analysis_result,
            "predicted_remaining_useful_time",
            read_value(runtime_models, "predicted_remaining_useful_time", {}),
        )
        communication_reliability = read_value(
            global_analysis_result,
            "communication_reliability",
            read_value(runtime_models, "communication_reliability", {}),
        )
        battery = read_value(
            global_analysis_result,
            "battery",
            read_value(runtime_models, "battery", read_value(runtime_models, "battery_state", {})),
        )
        uncertainty_regions = read_value(
            global_analysis_result,
            "uncertainty_regions",
            read_value(runtime_models, "uncertainty_regions", []),
        )
        critical_regions = read_value(
            global_analysis_result,
            "critical_regions",
            read_value(runtime_models, "critical_regions", []),
        )
        region_value_map = read_value(
            global_analysis_result,
            "region_value_map",
            read_value(runtime_models, "region_value_map", {}),
        )
        target_entity = read_value(global_analysis_result, "target_entity", "mission")

        base_parameters = {
            "predicted_remaining_useful_time": predicted_remaining_useful_time,
            "communication_reliability": communication_reliability,
            "battery": battery,
            "uncertainty_regions": uncertainty_regions,
            "critical_regions": critical_regions,
        }
        reallocation_options = [
            (
                "move_uavs_toward_critical_regions",
                "move_uavs_toward_critical_regions",
                {"target_regions": critical_regions},
                "Move UAV resources toward critical regions",
                "Critical regions may need additional UAV resource presence.",
            ),
            (
                "move_uavs_away_from_low_value_regions",
                "move_uavs_away_from_low_value_regions",
                {"candidate_regions": low_value_regions(region_value_map)},
                "Move UAV resources away from low-value regions",
                "Low-value regions can release UAV resources for higher-need areas.",
            ),
            (
                "reduce_weak_uav_load",
                "reduce_weak_uav_load",
                {"weakness_sources": ["predicted_remaining_useful_time", "battery"]},
                "Reduce load on weak UAV resources",
                "Low remaining useful time or battery can justify lower UAV load.",
            ),
            (
                "prioritize_strong_uavs_for_uncertainty_regions",
                "prioritize_strong_uavs_for_uncertainty_regions",
                {
                    "target_regions": uncertainty_regions,
                    "strength_sources": [
                        "predicted_remaining_useful_time",
                        "battery",
                        "communication_reliability",
                    ],
                },
                "Prioritize strong UAVs for uncertainty regions",
                "Uncertainty regions may benefit from UAVs with stronger resource state.",
            ),
        ]

        options: list[AdaptationOption] = [
            MissionAdaptationOption(
                option_id=f"global_resource_reallocation_{option_id}",
                option_type="resource_reallocation",
                target_entity=target_entity,
                parameters={**base_parameters, **parameters, "resource_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope["global"],
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, parameters, expected_effect, explanation_hint in (
                reallocation_options
            )
        ]

        has_resource_trigger = len(triggers) > 0
        if not options or not has_resource_trigger:
            resource_stability_hint = (
                "Stability baseline: preserve current resource allocation and UAV load when "
                "no resource-oriented analysis triggers are present."
            )
            options.extend(
                [
                    MissionAdaptationOption(
                        option_id="global_resource_reallocation_keep_current_resource_allocation",
                        option_type="resource_reallocation",
                        target_entity=target_entity,
                        parameters={
                            **base_parameters,
                            "resource_action": "keep_current_resource_allocation",
                        },
                        expected_effect="Retain current fleet resource allocation",
                        cost_estimate=0.0,
                        risk_estimate=0.0,
                        confidence=1.0,
                        scope=Scope["global"],
                        timestamp=timestamp,
                        originating_trigger=originating_trigger,
                        explanation_hint=resource_stability_hint,
                    ),
                    MissionAdaptationOption(
                        option_id="global_resource_reallocation_maintain_current_uav_load",
                        option_type="resource_reallocation",
                        target_entity=target_entity,
                        parameters={
                            **base_parameters,
                            "resource_action": "maintain_current_uav_load",
                        },
                        expected_effect="Maintain current per-UAV workload distribution",
                        cost_estimate=0.0,
                        risk_estimate=0.0,
                        confidence=1.0,
                        scope=Scope["global"],
                        timestamp=timestamp,
                        originating_trigger=originating_trigger,
                        explanation_hint=resource_stability_hint,
                    ),
                ]
            )

        return options

    def _generate_fail_safe_mission_options(
        self,
        global_analysis_result: Any,
        runtime_models: Any,
        timestamp: float,
    ) -> list[AdaptationOption]:
        def read_value(source: Any, name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)
            return getattr(source, name, default)

        originating_trigger, trigger_context, confidence, trigger_signals = adaptation_trigger_metadata(
            global_analysis_result,
            default_label="global_analysis",
        )
        trigger_ids = [signal.name for signal in trigger_signals]
        triggers = list(trigger_signals)
        trigger_context = trigger_context.upper()
        trigger_text = " ".join(trigger_ids).upper() + " " + trigger_context
        if not any(
            term in trigger_text
            for term in (
                "INFORMATION_COLLAPSE",
                "INFORMATION_INSUFFICIENT",
                "CRITICAL",
                "FAIL_SAFE",
            )
        ):
            return []
        target_entity = read_value(global_analysis_result, "target_entity", "mission")
        mission_options = [
            (
                "search_mode",
                "search_mode",
                "Activate mission search mode",
                "Information collapse suggests explicit search-mode mission options.",
            ),
            (
                "reduce_mission_scope",
                "reduce_mission_scope",
                "Reduce mission scope",
                "Fail-safe mission option only; no mission behavior is executed.",
            ),
            (
                "information_recovery_mission_mode",
                "information_recovery_mission_mode",
                "Shift mission toward information recovery",
                "Fail-safe mission option only; no mission behavior is executed.",
            ),
        ]

        return [
            MissionAdaptationOption(
                option_id=f"global_fail_safe_mission_{option_id}",
                option_type="fail_safe_mission",
                target_entity=target_entity,
                parameters={"failsafe_action": action},
                expected_effect=expected_effect,
                cost_estimate=1.0,
                risk_estimate=0.2,
                confidence=confidence,
                scope=Scope["global"],
                timestamp=timestamp,
                originating_trigger=originating_trigger,
                explanation_hint=explanation_hint,
            )
            for option_id, action, expected_effect, explanation_hint in mission_options
        ]
