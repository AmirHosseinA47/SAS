"""Post-hoc JSON export for dashboard state, timeline, and explanations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dashboard_state_builder import DashboardStateBuilder
from .explanation_engine import ExplanationEngine
from .timeline_builder import MissionTimelineBuilder


def _ensure_serializable(payload: Any) -> None:
    json.dumps(payload)


def _default_output_dir() -> Path:
    return Path("outputs") / "dashboard"


def _unique_path(base: Path) -> Path:
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix or ".json"
    counter = 1
    while True:
        candidate = base.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


@dataclass
class DashboardStateExporter:
    """Write read-only dashboard artifacts to JSON files."""

    output_dir: Path = field(default_factory=_default_output_dir)
    state_builder: DashboardStateBuilder = field(default_factory=DashboardStateBuilder)
    explanation_engine: ExplanationEngine = field(default_factory=ExplanationEngine)
    timeline_builder: MissionTimelineBuilder = field(default_factory=MissionTimelineBuilder)

    def _build_filename(self, prefix: str, step: int) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"{prefix}_step{step}_{ts}.json"

    def export_dashboard_state(self, model: Any, path: str | Path | None = None) -> Path:
        state = self.state_builder.build(model)
        _ensure_serializable(state)
        step = int(state.get("step", 0) or 0)
        out = Path(path) if path is not None else self.output_dir / self._build_filename("dashboard_state", step)
        return self.export_dashboard_snapshot(state, out)

    def export_dashboard_snapshot(self, state: dict[str, Any], path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out = _unique_path(out)
        _ensure_serializable(state)
        out.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return out

    def export_timeline(self, model: Any, path: str | Path | None = None) -> Path:
        events = self.timeline_builder.build(model)
        step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        payload = {
            "step": step,
            "event_count": len(events),
            "timeline": [e.to_dict() for e in events],
        }
        _ensure_serializable(payload)
        out = (
            Path(path)
            if path is not None
            else self.output_dir / self._build_filename("timeline", step)
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out = _unique_path(out)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out

    def export_explanations(self, model: Any, path: str | Path | None = None) -> Path:
        bundle = self.explanation_engine.collect_bundle(model)
        step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
        payload = bundle.to_dict()
        payload["step"] = step
        _ensure_serializable(payload)
        out = (
            Path(path)
            if path is not None
            else self.output_dir / self._build_filename("explanations", step)
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out = _unique_path(out)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out

    def export_all(self, model: Any, output_dir: str | Path | None = None) -> dict[str, Path]:
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "dashboard_state": self.export_dashboard_state(model),
            "timeline": self.export_timeline(model),
            "explanations": self.export_explanations(model),
        }
