# System Boundary

## 1. System boundary overview

The project system is a self-adaptive rescue-aware UAV coordination system built on top of Wildfire-UAVSim.

Its main purpose is to:

1. monitor wildfire evolution 
2. search for and track victims 
3. support rescue coordination 
4. adapt UAV behavior at runtime under uncertainty

The primary managed entities are the UAVs.

Firefighters are included as abstract operational agents with meaningful rescue state and route state, but **not** as fully simulated autonomous humans.

---

## 2. Inside the system

These parts are inside the system boundary and should be implemented or clearly modeled.

### 2.1 Primary operational entities

- UAV agents
- victim entities / victim state
- firefighter units in abstract operational form

### 2.2 Self-adaptive managing system

- global adaptation manager
- local UAV adaptation loops
- monitor modules
- analysis modules
- planning modules
- execution coordination
- fail-safe logic

### 2.3 Decision-making logic

- UAV mission planning
- UAV path planning
- victim detection / confirmation logic
- simplified rescue-task planning
- firefighter assignment logic
- simplified firefighter route-risk evaluation
- communication-aware adaptation
- battery-aware adaptation
- wind-drift-aware adaptation

### 2.4 Runtime knowledge and shared state

- fire runtime model
- smoke / visibility model
- victim runtime model
- UAV resource model
- firefighter state model
- communication state model
- shared operational picture

### 2.5 User-facing support

- dashboard
- alerts
- explainability view
- limited operator override hooks

---

## 3. What is partially inside the system

These are included, but in controlled / simplified form.

### 3.1 Firefighter units

Modeled with:

- current position
- availability
- assignment state
- route state
- ETA
- rescue progress
- route risk / feasibility state

Not modeled with:

- detailed low-level movement
- physical fatigue
- rich individual behavior
- detailed team tactics
- full human decision-making psychology

### 3.2 Rescue routing

Included as:

- route generation
- route risk evaluation
- rerouting decisions
- rescue feasibility assessment

Not a full navigation simulator.

### 3.3 Dashboard

Should show:

- wildfire state
- smoke state
- UAV positions and roles
- UAV battery
- victim status
- firefighter assignment and route status
- communication alerts
- adaptation events
- explanation for decisions

---

## 4. What is outside the system

These are outside the main implementation responsibility.

### 4.1 Environmental dynamics provided by Wildfire-UAVSim

- wildfire spread engine
- smoke generation logic
- base wildfire grid world
- baseline environment update loop

### 4.2 Full human rescue behavior

Outside scope:

- detailed firefighter cognition
- realistic multi-human coordination behavior
- evacuation medicine / triage behavior
- real human response variability

### 4.3 Full low-level UAV physics

Outside scope:

- detailed flight control system
- continuous aerodynamics
- real UAV actuator/controller simulation

Instead, the project models:

- task-level adaptation
- path-level adaptation
- wind drift effects at decision level

### 4.4 Real communication stack

Outside scope:

- full network protocol stack
- packet-level implementation
- real radio simulation

Instead, the project models:

- communication quality
- delay/loss state
- message priority
- relay support
- critical-message handling

---

## 5. Environmental assumptions

The system operates in an environment with:

- evolving wildfire
- smoke causing partial observability
- wind affecting wildfire propagation
- wind also affecting UAV movement through drift
- uncertain victim presence and location
- possible communication degradation
- route hazards for firefighters

---

## 6. Primary focus of the project

### Main focus

- mission planning
- path planning

### Mission planning focus

- assigning UAV roles
- allocating UAVs to tasks or sectors
- deciding when UAVs should switch between:
  - fire tracking
  - victim search
  - victim confirmation
  - victim tracking
  - relay support

### Path planning focus

- adaptive UAV route selection
- drift-aware replanning
- battery-aware replanning
- collision-aware movement
- information-driven movement

### Rescue support focus

- included for coherence
- secondary relative to mission and path planning
- project is not primarily about firefighter simulation
- project is primarily about self-adaptive UAV coordination with rescue support.

---

## 7. Explicit simplifications

- firefighters are modeled at operational abstraction level
- rescue execution is simplified
- communication is explicit but not protocol-level
- dashboard is advanced enough for system understanding, not industrial UI complexity
- UAV control is decision-level, not low-level flight dynamics
- victim handling is mission-level and state-based, not human-behavior-rich
