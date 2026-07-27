# Extension package (`src_extension`)

This folder holds the self-adaptive rescue-aware UAV coordination architecture as an extension scaffold. It is intentionally separated from the original Wildfire-UAVSim application code so that:

- baseline simulator behavior (wildfire propagation, smoke generation, existing UAV logic) can remain unchanged unless a future integration deliberately adds minimal, controlled hooks;
- new adaptation, planning, knowledge, monitoring, execution, and dashboard components can evolve in isolation with clear boundaries.

Original simulator logic should not be refactored to fit this package; instead, integration should happen later through small, explicit bridges (for example, read-only environment snapshots and thin execution adapters), marked with `TODO` comments in the scaffold where appropriate.

See `docs/01_system_boundary.md` for what is inside, partially inside, and outside the system boundary.

See `docs/02_managed_vs_managing.md` and `ARCHITECTURE_BOUNDARIES.md` in this folder for the **managed system vs managing system** split and intended data flow.
