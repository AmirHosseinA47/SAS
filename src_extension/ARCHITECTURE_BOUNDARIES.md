# Extension architecture: managed vs managing

This scaffold follows `docs/02_managed_vs_managing.md`.

## Which folders are which

**Managed system (operational / domain side)**

- `src_extension/managed/` — operational entities and **environment interaction** support (e.g. `EnvironmentBridge`). This is where **mission execution in the world** is represented and touched, not adaptation policy.

**Managing system (adaptation side)**

- `src_extension/monitoring/` — observe managed operational state and environment-exposed facts.
- `src_extension/knowledge/` — runtime knowledge models and fused picture **about** the mission (for reasoning).
- `src_extension/analysis/` — assess observations and emit triggers.
- `src_extension/planning/` — adaptation decisions (mission, path, rescue, communication adaptation, fail-safe) and **utility evaluation / option ranking** (`utility_evaluation.py`).
- `src_extension/execution/` — **apply** planner decisions to **managed** entities and controlled simulator hooks (**Managing → managed**).
- `src_extension/dashboard/` — operator views, alerts, explanations, overrides (**adaptation-support** presentation; raw operational facts still **originate** from the managed layer).

**Orchestration (managing-side control flow)**

- `src_extension/adaptation_manager.py` — placeholder for wiring the managing pipeline (no business logic yet).

## Data flow (intended)

```
managed (state + env I/O)
    → monitoring (observations)
    → knowledge (update runtime models / shared picture)
    → analysis (triggers)
    → planning (decisions)
    → execution (apply to managed + env)
    → managed (updated operational state)
```

Dashboard modules **consume** knowledge and managed-sourced snapshots for display and explanation; they are not the operational source of truth.

## Simulator foundation

**Wildfire-UAVSim** remains the **operational foundation** for wildfire, smoke, grid world, and baseline dynamics. This extension **does not** replace or refactor that codebase; integration is expected later via **minimal, controlled** hooks (see `README_extension_structure.md`).
