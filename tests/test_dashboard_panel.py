"""live dashboard panel tests."""

from __future__ import annotations

import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from src_extension.dashboard.live_dashboard_panel import DashboardPanel
from wildfire_model import WildFireModel


def _scenario_a_model(*, batch_size: int = 50, seed: int = 42) -> WildFireModel:
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
    agents.random = rng
    apply_scenario_config(
        cfv,
        wf,
        NUM_AGENTS=2,
        NUM_VICTIMS=3,
        NUM_FIREFIGHTERS=3,
        FIRE_SPREAD_MULTIPLIER=0.75,
        BATCH_SIZE=batch_size,
        FIXED_WIND=True,
        WIND_DIRECTION="east",
    )
    model = WildFireModel()
    model.debug_log = False
    return model


def _snapshot_model(model: WildFireModel) -> dict:
    return {
        "step": model.evaluation_timesteps_counter,
        "victim_statuses": {
            vid: str(getattr(st, "status", ""))
            for vid, st in model.managed_victims.items()
        },
        "uav_positions": {
            str(a.unique_id): tuple(a.pos)
            for a in model.schedule.agents
            if type(a) is agents.UAV and a.pos is not None
        },
    }


def test_dashboard_panel_render_returns_string() -> None:
    model = _scenario_a_model()
    for _ in range(5):
        model.step()
    html = DashboardPanel().render(model)
    assert isinstance(html, str)
    assert html
    assert "Step" in html
    assert "mission_mode" in html
    assert "Fire" in html or "fire" in html.lower()
    assert "UAV" in html or "UAVs" in html


def test_dashboard_panel_render_is_read_only() -> None:
    def run(*, with_render: bool) -> dict:
        model = _scenario_a_model(batch_size=30)
        panel = DashboardPanel()
        for _ in range(20):
            if with_render:
                panel.render(model)
            model.step()
        return _snapshot_model(model)

    assert run(with_render=False) == run(with_render=True)


def test_dashboard_panel_render_never_raises() -> None:
    model = WildFireModel()
    html = DashboardPanel().render(model)
    assert isinstance(html, str)
    assert html.startswith("<div")


def test_dashboard_panel_render_on_model_without_get_dashboard_state() -> None:
    class _BareModel:
        pass

    html = DashboardPanel().render(_BareModel())
    assert "unavailable" in html.lower()
