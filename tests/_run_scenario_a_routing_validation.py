"""Scenario A seed=42 validation after executor routing fix."""

from __future__ import annotations

import os
import random

os.environ.setdefault("MPLBACKEND", "Agg")

import agents
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import (
    apply_scenario_config,
    resolve_primary_victim_searcher_uav_id,
)
from wildfire_model import WildFireModel

rng = random.Random(42)
cfv.SYSTEM_RANDOM = wf.SYSTEM_RANDOM = rng
agents.random = rng
apply_scenario_config(
    cfv,
    wf,
    NUM_AGENTS=2,
    NUM_VICTIMS=3,
    NUM_FIREFIGHTERS=3,
    FIRE_SPREAD_MULTIPLIER=0.75,
    BATCH_SIZE=300,
    FIXED_WIND=True,
    WIND_DIRECTION="east",
)

model = WildFireModel()
model.debug_log = False
vs_id = resolve_primary_victim_searcher_uav_id(model)
assert vs_id

positions: list[tuple[int, int]] = []
bfs_actions = 0
retarget_interior = 0
pathfinding_retarget = 0
victim_timeline: dict[str, dict[str, int | None]] = {
    vid: {"detected": None, "dispatched": None, "terminal": None, "terminal_state": None}
    for vid in model.managed_victims
}
prev_status = {vid: str(st.status) for vid, st in model.managed_victims.items()}
terminal_states = {"rescued", "dead", "unreachable", "cancelled"}

for step in range(1, 301):
    model.step()
    agent = next((a for a in model.schedule.agents if str(a.unique_id) == vs_id), None)
    if agent is not None:
        positions.append((int(agent.pos[0]), int(agent.pos[1])))
    exec_r = (model.latest_execution_result or {}).get("local", {})
    ur = (exec_r.get("uav_results") or {}).get(vs_id, {})
    action = str(ur.get("action") or "")
    if action == "victim_search_escape_bfs":
        bfs_actions += 1
    if "retarget_to_interior" in action:
        retarget_interior += 1
        if ur.get("route_method") or "bfs" in action or bfs_actions > 0:
            pathfinding_retarget += 1

    for vid, st in model.managed_victims.items():
        status = str(getattr(st, "status", "") or "").strip().lower()
        prev = prev_status.get(vid, "")
        if prev != status:
            if status in {"confirmed", "detected", "assigned"} and victim_timeline[vid]["detected"] is None:
                victim_timeline[vid]["detected"] = step
            if status == "assigned" and victim_timeline[vid]["dispatched"] is None:
                victim_timeline[vid]["dispatched"] = step
            if status in terminal_states and victim_timeline[vid]["terminal"] is None:
                victim_timeline[vid]["terminal"] = step
                victim_timeline[vid]["terminal_state"] = status
            prev_status[vid] = status
        if getattr(st, "rescue_assigned", False) and victim_timeline[vid]["dispatched"] is None:
            victim_timeline[vid]["dispatched"] = step

burnt_count = 0
reignited = 0
for agent in model.schedule.agents:
    if type(agent) is agents.Fire and getattr(agent, "burnt", False):
        burnt_count += 1
        if getattr(agent, "burning", False):
            reignited += 1

xs = [p[0] for p in positions]
ys = [p[1] for p in positions]
pct_x_le_5 = 100.0 * sum(1 for x in xs if x <= 5) / max(1, len(xs))
pct_x_ge_38 = 100.0 * sum(1 for x in xs if x >= 38) / max(1, len(xs))
crossed = (max(xs) - min(xs) >= 25) if xs else False
all_terminal = all(
    str(getattr(st, "status", "") or "").strip().lower() in terminal_states
    for st in model.managed_victims.values()
)

print("--- victims ---")
for vid in sorted(victim_timeline):
    tl = victim_timeline[vid]
    st = model.managed_victims[vid].status
    print(
        f"{vid}: status={st} detected={tl['detected']} dispatched={tl['dispatched']} "
        f"terminal={tl['terminal_state']}@{tl['terminal']}"
    )
print("--- victim_searcher ---")
print(f"x-range: {min(xs) if xs else 'n/a'}..{max(xs) if xs else 'n/a'}")
print(f"y-range: {min(ys) if ys else 'n/a'}..{max(ys) if ys else 'n/a'}")
print(f"percent x<=5: {pct_x_le_5:.1f}%")
print(f"percent x>=38: {pct_x_ge_38:.1f}%")
print(f"physically crossed map: {'YES' if crossed else 'NO'}")
print(f"bfs_actions: {bfs_actions}")
print(f"retarget_to_interior: {retarget_interior}")
print(f"all victims terminal: {'YES' if all_terminal else 'NO'}")
print("--- environment ---")
print(f"burnt cells: {burnt_count}")
print(f"burnt re-ignited: {reignited}")
