"""Scenario A east validation: unresolved-victim coverage diagnostics."""

from __future__ import annotations

import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import (
    _corridor_diversity_failure,
    _wind_search_state,
    apply_scenario_config,
    resolve_primary_victim_searcher_uav_id,
)
from wildfire_model import WildFireModel

rng = random.Random(42)
cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
agents.random = rng
os.environ["WIND_DIRECTION"] = "east"
apply_scenario_config(
    cfv,
    wf,
    NUM_AGENTS=2,
    NUM_VICTIMS=3,
    NUM_FIREFIGHTERS=3,
    FIRE_SPREAD_MULTIPLIER=0.75,
    BATCH_SIZE=99_999,
    FIXED_WIND=True,
    WIND_DIRECTION="east",
)

model = WildFireModel()
model.debug_log = False
vs_id = resolve_primary_victim_searcher_uav_id(model)
assert vs_id

victim_timeline: dict[str, dict[str, int | None]] = {
    vid: {"detected": None, "rescued": None, "dead": None, "unreachable": None}
    for vid in model.managed_victims
}
ff_dispatched: dict[str, int | None] = {}
corridor_step: int | None = None
post_rescue_step: int | None = None
left_east_step: int | None = None

prev_status = {vid: str(st.status) for vid, st in model.managed_victims.items()}

for step in range(1, 201):
    model.step()
    ws = _wind_search_state(model, vs_id)
    if _corridor_diversity_failure(ws) and corridor_step is None:
        corridor_step = step
    if int(ws.get("post_rescue_coverage_steps_remaining", 0) or 0) >= 49 and post_rescue_step is None:
        post_rescue_step = step

    agent = next((a for a in model.schedule.agents if str(a.unique_id) == vs_id), None)
    pos = (int(agent.pos[0]), int(agent.pos[1])) if agent else (0, 0)
    if step > 32 and pos[0] < 30 and left_east_step is None:
        left_east_step = step

    for vid, st in model.managed_victims.items():
        status = str(getattr(st, "status", "") or "").strip().lower()
        prev = prev_status.get(vid, "")
        if prev != status:
            if status in {"confirmed", "detected", "assigned"} and victim_timeline[vid]["detected"] is None:
                victim_timeline[vid]["detected"] = step
            if status == "rescued":
                victim_timeline[vid]["rescued"] = step
            if status == "dead":
                victim_timeline[vid]["dead"] = step
            if status == "unreachable":
                victim_timeline[vid]["unreachable"] = step
            prev_status[vid] = status

    for ff_id, ff in getattr(model, "firefighter_marker_agents", {}).items():
        if ff_id not in ff_dispatched and getattr(ff, "assigned", False):
            ff_dispatched[ff_id] = step

    if step % 20 == 0:
        x_band = "west" if pos[0] < 38 else "east"
        exec_r = (model.latest_execution_result or {}).get("local", {})
        ur = (exec_r.get("uav_results") or {}).get(vs_id, {})
        exec_action = str(ur.get("action") or "")
        print(
            f"step={step} vs_pos={pos} x_band={x_band} "
            f"coverage_priority={ws.get('coverage_priority')} "
            f"unresolved={ws.get('unresolved_victim_count')} "
            f"post_rescue={ws.get('post_rescue_coverage_steps_remaining')} "
            f"exec_action={exec_action}"
        )

print("--- summary ---")
for vid, tl in victim_timeline.items():
    terminal = tl["rescued"] or tl["dead"] or tl["unreachable"]
    state = model.managed_victims[vid].status
    print(f"{vid}: status={state} detected={tl['detected']} rescued={tl['rescued']} dead={tl['dead']} unreachable={tl['unreachable']} terminal_step={terminal}")
for ff_id in sorted(getattr(model, "firefighter_marker_agents", {})):
    print(f"{ff_id}: dispatched_step={ff_dispatched.get(ff_id)}")
print(f"victim_searcher left east (x<30 after 32): step={left_east_step}")
print(f"corridor_diversity activated: step={corridor_step}")
print(f"post_rescue_coverage activated: step={post_rescue_step}")
