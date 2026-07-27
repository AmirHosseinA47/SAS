# Separation Table

## 1. Introduction

The project split between the managed system and the managing system in a precise, implementation-friendly form so responsibilities stay clear during design and implementation.

---

## 2. Separation table

| Managed system | Managing system |
|----------------|-------------------|
| UAV operational state and execution | monitoring |
| victim operational entities/state | runtime models / knowledge |
| abstract firefighter operational state | context interpretation |
| movement execution | uncertainty reasoning |
| sensing execution | analysis |
| communication execution | adaptation trigger detection |
| battery depletion as operational state update | adaptation option generation |
| wind/drift physical effect outcome | utility-based ranking |
| environment interaction | planning |
| raw mission state for display | fail-safe reasoning |
| | adaptation manager |
| | explanation generation |

---

## 3. Interpretation

- The managed system performs operational mission behavior in the environment.
- The managing system performs adaptation reasoning about how that behavior should change.
- The managing system does not directly perform the mission.
- The managed system does not decide adaptation policy.

---

## 4. Implementation note

This separation should be respected in the extension architecture under `src_extension/`, while the original Wildfire-UAVSim simulator remains unchanged as the operational foundation unless integration deliberately adds minimal, controlled hooks.

---

# Runtime Knowledge Models

The design works better under partial observability, smoke, wind, uncertain victim detection, delayed or incomplete knowledge, and distributed coordination. The main upgrade is that the knowledge layer should no longer behave like a purely deterministic world model; it must become a belief-based, time-aware, and confidence-aware runtime knowledge layer.

## Purpose of the runtime knowledge layer

The runtime knowledge layer must:

- Represent wildfire, UAV team, victims, rescue state, and communication state in a structured way.
- Represent uncertainty and partial observability, not only known facts.
- Preserve time-awareness, so stale information is not treated as fresh truth.
- Support utility-based planning and fail-safe reasoning.
- Support distributed information sharing among UAVs and the global manager.

## Design principles

### Belief-based, not purely deterministic

- Store likelihood, confidence, freshness, and source for knowledge items.

### Time-aware

- Include timestamp, last seen, and staleness so age of information is explicit.

### Confidence-aware

- Every asserted quantity is confidence-qualified; together with likelihood, freshness, and source so evidence is weighted, not binary.

### Negative information is also knowledge

- Negative information must be time-stamped, confidence-aware, and allowed to decay; it is not permanent truth without context.

### Distributed and layered

- Distinguish global runtime models and local UAV runtime models so fusion, sharing, and autonomy stay coherent.

## Updated runtime model set

Global models

- Fire Belief Runtime Model
- Visibility and Uncertainty Model
- Victim Runtime Model
- UAV Resource and Role Model
- Firefighter Operational Model
- Communication Runtime Model
- Mission Goal and Constraint Model
- Shared Operational Picture

Local models

- Local Observation Model
- Local Path Context Model

## Updated Fire Belief Runtime Model

Purpose: Maintain a structured, uncertainty-aware picture of where fire is believed to be, how it may evolve, and what has been ruled out (with limits).

Core idea: Fire state is represented as beliefs over cells and fronts, not as a single crisp map assumed fully correct.

Fields

- `estimated_burning_cells`
- `estimated_fire_front_cells`
- `fire_probability_map`
- `fire_confidence_map`
- `predicted_fire_front_map`
- `predicted_spread_bias`
- `last_observed_fire_time`
- `negative_observation_map`
- `negative_observation_time`
- `fire_sector_map`
- `fire_sector_priority`
- `uncertain_fire_regions`

Explanations

- `fire_probability_map`:Per-cell or region estimate of fire presence likelihood, supporting planning under uncertainty.
- `fire_confidence_map`:How much weight to place on the probability estimates sensor quality, consistency, corroboration.
- `predicted_fire_front_map`:Anticipated front geometry or cells for lookahead planning and risk budgeting.
- `negative_observation_map`:Where no fire seen or equivalent has been asserted, as explicit negative evidence.
- `negative_observation_time`:When those negative assertions were made, enabling decay and conflict resolution with newer positives.
- `uncertain_fire_regions`:Regions where smoke, occlusion, or sparse sensing leave fire state ambiguous; planners can allocate sensing or avoid overconfident commitments.

Reason: Under smoke, wind, and partial views, a crisp fire grid misleads adaptation; belief maps align planning and fail-safes with what is known, unknown, and contradicted over time.

## Visibility and Uncertainty Model

Purpose: Track what can be seen, what is obscured, and how trustworthy and fresh per-cell information is.

Fields

- `visible_cells`
- `smoke_obscured_cells`
- `observation_status_map`
- `cell_confidence_map`
- `staleness_map`
- `last_seen_timestamp_per_cell`
- `visibility_confidence_decay`
- `region_uncertainty_score`
- `unknown_or_uncertain_regions`
- `information_freshness_map`

Observation status values

- `observed_fire`
- `observed_no_fire`
- `smoke_obscured`
- `never_seen`
- `stale_information`

Importance: Prevents treating occlusion or gaps as “no hazard,” and keeps adaptation sensitive to where sensing is weak or outdated.

## Victim Runtime Model

Purpose: Represent victims as entities with uncertain location, evolving detections, and rescue coordination state.

Fields

- `victim_id`
- `estimated_position`
- `position_uncertainty_radius`
- `confidence_score`
- `detection_confidence_history`
- `detection_history`
- `last_seen_time`
- `last_confirmation_time`
- `status`
- `priority`
- `confirmation_required_flag`
- `lost_contact_flag`
- `reachability_estimate`
- `assigned_firefighter_unit`
- `supporting_uav`
- `rescue_state`

Explanations

- `position_uncertainty_radius`:Spatial envelope for where the victim may be given noisy or intermittent sensing.
- `detection_confidence_history`:Time series of detection strength or classifier confidence for trend and gating decisions.
- `confirmation_required_flag`:Signals that another observation or modality is needed before high-stakes commitment.
- `lost_contact_flag`:Indicates the track is stale or broken relative to communication or sensing expectations.

Importance: Victim handling under uncertain detection and delays needs explicit uncertainty and confirmation logic, not a single “known position” fiction.

## UAV Resource and Role Model

Purpose — Describe each UAV’s operational posture, constraints, and how stable or reliable its current task and plan are.

Fields

- `uav_id`
- `current_position`
- `current_role`
- `assigned_task`
- `battery_level`
- `battery_status`
- `communication_status`
- `drift_level`
- `path_feasibility_status`
- `local_risk_status`
- `task_effectiveness_score`
- `role_stability_timer`
- `role_switch_count`
- `task_commitment_age`
- `predicted_remaining_useful_time`
- `local_plan_reliability`
- `last_update_time`

Explanations

- **`role_stability_timer`**:How long the UAV has held its current role, supporting hysteresis against churn.
- **`role_switch_count`**:Count of recent role changes for oscillation detection and adaptation penalties.
- **`task_commitment_age`**:How long the UAV has been committed to the current task, for preemption and fairness logic.
- **`predicted_remaining_useful_time`**:Horizon of useful operation given battery, risk, and environment (e.g., wind/drift stress).
- **`local_plan_reliability`**:Estimate of how dependable the current local plan is given drift, smoke, and comms.

Importance: Distributed coordination needs per agent readiness, stability, and horizon signals to avoid brittle reassignment under noise.

## Firefighter Operational Model

Purpose: Capture ground-rescue units’ state, assignments, and route/rescue progress for coordination with UAVs.

Fields

- `unit_id`
- `current_position`
- `availability_status`
- `current_assignment`
- `target_victim`
- `route_status`
- `route_risk_score`
- `route_feasibility_confidence`
- `eta`
- `rescue_progress_status`
- `last_update_time`

Explanation of `route_feasibility_confidence`:Confidence that the planned route remains achievable given fire belief, visibility, congestion, and dynamic hazards.

## Communication Runtime Model

Purpose: Represent link behavior, queues, and delivery quality so adaptation does not assume perfect, instantaneous shared knowledge.

Fields

- `link_quality_summary`
- `critical_message_queue`
- `ack_status`
- `last_delivery_status`
- `delayed_messages`
- `failed_messages`
- `relay_needed_flag`
- `communication_mode`
- `delivery_confidence`
- `critical_link_reliability`
- `message_staleness`
- `shared_knowledge_sync_quality`

Reasoning: They make delays, losses, retries, and partial sync explicit so planners do not over rely on stale or never-arrived data and can trigger relays, backoff, or conservative modes.

## Mission Goal and Constraint Model

Purpose: Encode what the mission is optimizing for, what is inviolable, and how trade-offs are ordered under uncertainty.

Fields

- `adaptation_goals`
- `goal_weights`
- `hard_constraints`
- `soft_preferences`
- `priority_ordering`
- `safety_thresholds`
- `resource_thresholds`
- `uncertainty_tolerance_thresholds`

Explanation of `uncertainty_tolerance_thresholds`:Bounds on how much ambiguity like in fire or victim state is acceptable before triggering sensing actions, conservative routing, or human-facing alerts.

## Shared Operational Picture

Purpose: A single fused view for managers and high-level adaptation that aggregates global models into an actionable summary.

Integrated contents

- Fire belief summary
- Visibility summary
- Uncertainty summary
- Victim confidence summary
- UAV team summary
- Firefighter summary
- Communication reliability summary
- Active alerts
- Mission mode
- Active adaptation state

Exposure: The picture should surface what is believed, how certain it is, and how fresh it is, so decisions are not mistaken for ground truth.

## Local Observation Model

Fields

- `visible_fire_cells`
- `visible_smoke_cells`
- `visible_victim_candidates`
- `local_confidence_patch`
- `local_uncertainty_patch`
- `nearby_uavs`
- `local_comm_quality`
- `local_drift_state`
- `local_battery_state`
- `current_task_context`
- `negative_local_observations`

## Local Path Context Model

Fields

- `current_path_segment`
- `candidate_moves`
- `candidate_horizon_length`
- `local_path_utility_estimates`
- `local_collision_risk_estimates`
- `local_smoke_penalty_estimates`
- `local_drift_penalty_estimates`
- `task_support_score`
- `belief_gain_score`
- `path_stability_score`

## Global rule for runtime knowledge

Every important knowledge item should carry:

- Timestamp
- Confidence
- Source

## Decay rules

- Freshness decay: Older observations lose effective weight unless refreshed.
- Negative information decay: No fire seen and similar negatives expire or soften as conditions change.
- Belief persistence: Stable beliefs persist with explicit evidence and half life rules rather than arbitrary flicker.

## Implementation priority

Must-have first

- Fire Belief Runtime Model
- Visibility and Uncertainty Model
- UAV Resource and Role Model
- Mission Goal and Constraint Model
- Local Observation Model

Second wave

- Victim Runtime Model
- Communication Runtime Model
- Shared Operational Picture

Third wave

- Firefighter Operational Model
- richer Local Path Context Model
----
