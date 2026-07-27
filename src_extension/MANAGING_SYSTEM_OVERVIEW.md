# Managing system

This describes the **managing side** of the self-adaptive layer: components that **observe**, **maintain knowledge**, **interpret**, **plan adaptations**, **orchestrate** the loop, and **explain**—without replacing **direct mission execution** in the **managed** system (`src_extension/managed/`).

See also `docs/02_managed_vs_managing.md` and `ARCHITECTURE_BOUNDARIES.md`.

## What belongs to the managing side

| Concern | Role (conceptual) |
|--------|-------------------|
| **Monitors** | Collect and **structure** data from the **managed system** and **environment** into observations. **No decisions**, **no execution**. |
| **Runtime knowledge models** | The adaptation layer’s **structured understanding** of the world—not the world itself. Updated from observations (and later execution feedback). **No analysis or planning** inside these modules. |
| **Analyzers** | Interpret observations + knowledge context and emit **triggers**. **No** mutation of managed operational state; **no** actuator-style actions. |
| **Planners** | Choose **what should change** (decisions). **Do not** move UAVs or send messages; **execution** applies decisions to managed entities. |
| **Adaptation manager** | Orchestrates **monitoring → knowledge → analysis → planning → (execution)** in one control-flow place. **No** embedded domain state. |
| **Explainability** | **Why** adaptations were chosen—**managing-side** narrative over decisions/triggers/knowledge deltas, not a substitute for raw operational telemetry (which originates from the managed side). |

## Why these are separate

- **Monitors vs knowledge:** raw structured observations vs **persistent, fused** runtime models used across steps.
- **Knowledge vs analysis:** **state of belief/summary** vs **judgment** (triggers) about quality, risk, and uncertainty.
- **Analysis vs planning:** **signals** that something should be reconsidered vs **concrete adaptation options** (decisions).
- **Planning vs execution:** **intent** (what to change) vs **application** to operational entities (how the managed system is driven).
- **Explainability vs dashboards’ raw facts:** explanations are **reasoning-facing**; raw positions/maps/battery often come from **managed** outputs.

## Adaptation reasoning vs mission execution

The managing side **supports adaptation reasoning** (when and how to reconfigure). **Direct mission execution**—movement, sensing actions, operational messaging—remains on the **managed** side once integration exists. This scaffold stays **placeholder-based** until then.
