"""Managing system: execution command objects.

Optional commands derived from planner decisions—inputs for executors,
not execution receipts (see ``execution_log``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class ExecutionCommand:
    """Mapped command ready for an executor (no simulator side effects)."""

    command_id: str
    command_type: str
    target_entity: str
    parameters: dict[str, object]
    source_decision_id: str
    timestamp: float
    priority: str = "normal"
    explanation: str = ""


def command_to_dict(command: ExecutionCommand) -> dict[str, object]:
    return asdict(command)
