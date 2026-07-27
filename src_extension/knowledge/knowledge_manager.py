"""Orchestrator for unified runtime-knowledge time decay updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeManager:
    """Holds model references and applies global time-decay step hooks."""

    models: dict[str, Any] = field(default_factory=dict)
    _update_counter: int = 0

    def register_model(self, name: str, model: Any) -> None:
        self.models[name] = model

    def update_all_models(self, current_time: float) -> None:
        now = float(current_time)
        self._update_counter += 1
        for model in self.models.values():
            decay_fn = getattr(model, "apply_time_decay", None)
            if callable(decay_fn):
                decay_fn(now)
        fire_model = self.models.get("fire_model")
        if fire_model is not None and self._update_counter % 25 == 0:
            conf_values = list(fire_model.belief.fire_confidence_map.values())
            avg_conf = (sum(conf_values) / len(conf_values)) if conf_values else 0.0
            high_prob_cells = sum(
                1 for value in fire_model.belief.fire_probability_map.values() if value >= 0.7
            )
            print(
                f"[KnowledgeManager] t={now:.1f} avg_conf={avg_conf:.3f} high_prob_cells={high_prob_cells}"
            )
