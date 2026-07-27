"""Managing system: execution results and log.

Execution receipts record what an executor applied to a managed entity—
distinct from planner decisions (planning.decision_objects).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Final, Literal

ExecutionStatus = Literal["success", "partial_success", "failure", "delayed_effect"]

EXECUTION_STATUSES: Final[frozenset[str]] = frozenset(
    {"success", "partial_success", "failure", "delayed_effect"}
)


@dataclass
class ExecutionResult:
    """Single execution receipt from an executor."""

    decision_id: str
    executor_type: str
    target_entity: str
    action: str
    status: str
    timestamp: float
    intended_effect: str
    actual_result: str
    feedback_event: dict[str, object] = field(default_factory=dict)
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    explanation: str = ""


@dataclass
class ExecutionLog:
    """Append-only log of execution receipts."""

    entries: list[ExecutionResult] = field(default_factory=list)

    def add(self, result: ExecutionResult) -> None:
        self.entries.append(result)

    def latest(self, n: int = 10) -> list[ExecutionResult]:
        if n <= 0:
            return []
        return self.entries[-n:]

    def to_dict(self) -> dict[str, object]:
        return {"entries": [asdict(entry) for entry in self.entries]}
