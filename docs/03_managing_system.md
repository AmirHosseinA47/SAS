# Managing System

## 1. Managing system

The managing system is the adaptation part of the project.

- It does not directly perform the mission.
- It observes, reasons, chooses adaptations, and changes the managed system at runtime.

### 1.1 Definition

In this project, the managing system is:

- the hierarchical adaptation layer that monitors the managed system and the environment, maintains runtime knowledge models, analyzes mission quality and uncertainty, evaluates adaptation options, selects the best or safest option, and issues reconfiguration decisions for UAV coordination and rescue support.

---

## 2. Managing system Belonging

### A. Monitor modules

Monitor modules collect and structure data from:

- UAV observations
- environment state
- communication status
- battery status
- drift indicators
- victim detections
- firefighter status

Also:

- the monitor does not decide anything
- it only builds structured observations

### B. Runtime knowledge models

Runtime knowledge models are central to the managing system. They represent the adaptation layer’s structured understanding of the world.

They include:

- fire runtime model
- smoke / visibility model
- victim runtime model
- UAV resource model
- firefighter state model
- communication model
- shared operational picture

Also, these models are not the world itself.

### C. Analyze modules

Analyze modules determine:

- whether mission quality is acceptable
- whether uncertainty is rising
- whether battery is becoming critical
- whether collision risk is increasing
- whether communication degradation threatens rescue support
- whether rescue feasibility has changed

### D. Planning modules

Planning modules include:

- global mission planner
- local UAV planner
- rescue planner
- communication adaptation planner
- fail-safe planner

Also:

- these modules do not directly move a UAV
- they decide what should change

### E. Utility evaluation and option ranking

This layer includes:

- utility functions
- option scoring
- feasibility checks
- threshold checks
- ranking mechanisms

### F. Adaptation manager

The adaptation manager orchestrates the feedback loops. It decides:

- whether adaptation is needed.
- whether adaptation is global or local
- whether to keep the current configuration
- whether to trigger fail-safe behavior
- which plan to send for execution

### G. Explainability logic

- Raw dashboard data comes from the managed system.
- Explanations come from the managing system.

Examples:

- why the UAV role changed
- why rescue was delayed
- why a relay UAV was assigned
- why a safe fallback was chosen

