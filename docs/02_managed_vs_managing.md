# Managed System vs Managing System

## 1. Separation Importance

The self-adaptive structure must be explicit:

- One part interacts with the environment and carries domain concerns.
- The other part interacts with that first part and carries adaptation concerns.

The project must answer:

- What is the managed system?
- What is the managing system?
- How do they interact?

If this separation is vague, the project reads like a simulator with some smart rules. If it is clear, it reads like a proper self-adaptive system (SAS) design.

---

## 2. Managed system

The managed system is the operational part of the system: it is responsible for actually carrying out the mission in the environment.

### 2.1 Definition

In this project, the managed system is:

- the operational rescue-aware UAV mission system that interacts with the wildfire environment, performs observation, moves UAVs, supports victim handling, exchanges operational messages, and updates abstract firefighter task status.

### 2.2 What belongs to the managed system

#### A. UAV operational agents

- current position
- current path
- current role
- sensing actions
- movement execution
- observation generation
- local message sending
- battery consumption updates
- drift-affected movement outcomes

**Pay attention:** the UAV itself is managed, the reasoning about how it should adapt is not part of the UAV as managed operational agent.
- that reasoning belongs to the managing system.

#### B. Victim operational state

- victim presence
- victim location
- whether a victim is detected or not
- victim observable status
- rescue-related status in the operational world

**Attention:** a victim manager in the adaptation layer reasons about victims; the victims themselves belong to the managed/domain side.

#### C. Abstract firefighter units

- current location
- assigned target
- route progress
- rescue progress
- availability state

**Achtung:) :** the actual firefighter unit state is managed; rescue planning logic belongs to the managing side.

#### D. Environment interaction layer

- reading wildfire cell states from the simulator
- reading smoke effects
- applying actual UAV moves to the simulator
- receiving resulting world state changes
- receiving wind effects and drift outcomes

#### E. Communication execution layer

- sending operational messages
- receiving acknowledgments
- keeping message status
- operational message dispatch
- route/task notifications

**Nochmal Achtung:):** communication policies and adaptation logic belong to the managing system; actual message execution belongs to managed side.

#### F. Dashboard-facing operational state output

The raw mission state shown on the dashboard originates from the managed system:

- UAV positions
- fire map
- victim markers
- firefighter route status
- battery values
- communication status

---

## 3. Managing system

The managing system is the adaptation part: it does not directly perform the mission. It observes, reasons, chooses adaptations, and changes the managed system at runtime.

### 3.1 Definition

In this project, the managing system is:

- the hierarchical adaptation layer that monitors the managed system and the environment, maintains runtime knowledge models, analyzes mission quality and uncertainty, evaluates adaptation options, selects the best or safest option, and issues reconfiguration decisions for UAV coordination and rescue support.

### 3.2 What belongs to the managing system

#### A. Monitor modules

These collect and structure data from:

- UAV observations
- environment state
- communication status
- battery status
- drift indicators
- victim detections
- firefighter status

The monitor does not decide anything. It only builds a structured observation.

#### B. Runtime knowledge models

These are central to the managing system and match the knowledge/runtime model idea: they are not the world itself, they are the adaptation layer’s structured understanding of the world.

Includes:

- fire runtime model
- smoke / visibility model
- victim runtime model
- UAV resource model
- firefighter state model
- communication model
- shared operational picture

#### C. Analyze modules

These determine:

- whether the current mission quality is acceptable
- whether uncertainty is rising
- whether battery is becoming critical
- whether collision risk is increasing
- whether communication degradation threatens rescue support
- whether rescue feasibility has changed

This is adaptation reasoning, so it belongs to the managing side.

#### D. Planning modules

These are core adaptation components:

- global mission planner
- local UAV planner
- rescue planner
- communication adaptation planner
- fail-safe planner

These modules do not directly move a UAV. They decide what should change.

#### E. Utility evaluation and option ranking

Planning proceeds through utility based comparison of options. The following belong to the managing system:

- utility functions
- option scoring
- feasibility checks
- threshold checks
- ranking mechanisms

#### F. Adaptation manager

This is the orchestrator of the feedback loops. It decides:

- whether adaptation is needed.
- whether adaptation is global or local
- whether to keep the current configuration
- whether to trigger fail-safe behavior
- which plan to send for execution

This is a classic managing-system responsibility.

#### G. Explainability logic

The raw data shown on the dashboard comes from the managed system**; the explanations come from the managing system.

Examples:

- why the UAV role changed
- why rescue was delayed
- why a relay UAV was assigned
- why a safe fallback was chosen

That is adaptation reasoning, so it belongs to the managing side.

---

## 4. Clean separation table

| Managed system | Managing system |
|----------------|-----------------|
| UAV position, path, role, sensing, movement, observations, local sends, battery updates, drift outcomes | Mission/path policy, adaptation triggers, utility and option ranking |
| Victim presence, location, detection, observable status, operational rescue-related status | Victim-related reasoning and planning in the adaptation layer (“victim manager”) |
| Firefighter unit location, assignment, route/rescue progress, availability | Rescue planning logic, assignment decisions, route-risk evaluation for planning |
| Reading fire/smoke, applying moves, receiving world updates, wind/drift results as operational outcomes | Models and monitors that interpret observations; replanning and reconfiguration |
| Sending/receiving operational messages, acks, message status, dispatch, route/task notifications | Communication-aware adaptation, priorities, policies |
| Raw dashboard mission state (positions, map, markers, routes, battery, comms status) | Explanation logic and adaptation-oriented views layered on top of managed outputs |

---

## 5. How they interact

- Managed → Managing: the managed system provides observations** and state to the managing system.
- Managing → Managed: the managing system sends adaptation decisions back to the managed system (reconfiguration of coordination, roles, plans, and operational directives as defined by the architecture).

---

## 6. Hierarchical structure

- There is a global managing system for team-level reasoning.
- There are local managing systems for each UAV.
- The managed system still contains the actual operational entities such as: UAVs, victim operational state, abstract firefighter units, environment interaction, communication execution, and operational outputs.

---

## 7. These must not be mixed

Short examples of wrong vs correct separation:

| Wrong | Correct |
|-------|---------|
| A UAV class computes **global mission utility** | Global utility lives in the **managing** layer; the UAV carries **operational** state and execution |
| A **monitor** assigns **rescue** directly | Monitors **observe**; **planning / adaptation** assigns rescue |
| **Execution** invents **policy** | Execution applies **decisions**; **policy and planning** live in the managing system |





