"""Managing system: limited operator overrides.

Operator overrides are documented and recorded in this phase.
They are not executed and do not change simulation behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperatorOverrideCommand:
    """Managing-side override request (input to planning/adaptation in future phases)."""

    override_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    step: int = 0
    requested_by: str = "operator"
    reason: str = ""


# Backward-compatible alias for earlier scaffold name.
OperatorOverride = OperatorOverrideCommand


@dataclass
class OperatorOverrideInterface:
    """Validates and records override requests without applying them to the model."""

    recorded: list[OperatorOverrideCommand] = field(default_factory=list)
    functional: bool = False

    def validate(self, command: OperatorOverrideCommand) -> tuple[bool, str]:
        if not command.override_id:
            return False, "override_id is required"
        if not command.kind:
            return False, "kind is required"
        if not isinstance(command.payload, dict):
            return False, "payload must be a dict"
        return True, ""

    def record(self, command: OperatorOverrideCommand) -> dict[str, Any]:
        ok, err = self.validate(command)
        if not ok:
            return {"accepted": False, "error": err, "executed": False}
        self.recorded.append(command)
        return {
            "accepted": True,
            "executed": False,
            "message": "Override recorded; execution disabled in Step 12B.",
            "override_id": command.override_id,
        }

    def submit(self, command: OperatorOverrideCommand) -> dict[str, Any]:
        """Alias for ``record``; never mutates simulation state."""
        return self.record(command)


@dataclass
class OperatorOverrideRegistry(OperatorOverrideInterface):
    """Backward-compatible registry name."""

    pending: list[OperatorOverrideCommand] = field(default_factory=list)

    def submit(self, override: OperatorOverrideCommand) -> dict[str, Any]:
        result = self.record(override)
        if result.get("accepted"):
            self.pending.append(override)
        return result
