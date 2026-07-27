"""Self-adaptive rescue-aware UAV coordination extension (scaffold).

This package is intentionally isolated from the original Wildfire-UAVSim codebase.

**Structure:** ``managed/`` holds the **managed system** (operational/domain).
Other subpackages (``monitoring``, ``knowledge``, ``analysis``, ``planning``,
``execution``, ``dashboard``) are **managing system** or adaptation-support.
See ``ARCHITECTURE_BOUNDARIES.md`` and ``docs/02_managed_vs_managing.md``.

TODO: Wire package exports when implementation stabilizes.
"""

from __future__ import annotations

from .adaptation_manager import AdaptationManager

__all__: list[str] = ["AdaptationManager"]
