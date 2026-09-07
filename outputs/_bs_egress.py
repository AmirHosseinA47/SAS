"""Read-only probe: can UAVs spawned inside a 5x5 corner depot actually LEAVE?

Mirrors evaluate_scenarios._run_seed seeding exactly, then monkeypatches ONLY the
UAV placement (after construction, before the first step) to a corner block.
No simulation logic is modified.
"""
import argparse, contextlib, io, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default="E:\Projects\SAS")
ap.add_argument("--seed", type=int, default=101)
ap.add_argument("--steps", type=int, default=40)
ap.add_argument("--wind", default="east")
ap.add_argument("--roles", default="half")
ap.add_argument("--corner", default="none", help="none|NW|NE|SW|SE")
a = ap.parse_args()
sys.path.insert(0, a.repo)

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from serve_dashboard import BUILTIN_SCENARIOS, _resolve_role_count_params

preset = BUILTIN_SCENARIOS["D"]
n = int(preset["NUM_AGENTS"])
ft, vs = _resolve_role_count_params(n, None, None) if a.roles == "default" else (n // 2, n - n // 2)
params = {"NUM_AGENTS": n, "NUM_VICTIMS": int(preset["NUM_VICTIMS"]),
          "NUM_FIREFIGHTERS": int(preset["NUM_FIREFIGHTERS"]), "WIND_DIRECTION": a.wind,
          "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
          "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}
rng = random.Random(a.seed)
cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
apply_scenario_config(cfv, wf, **params)

CORNERS = {"NW": (0, 45), "NE": (45, 45), "SW": (0, 0), "SE": (45, 0)}

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    m = wf.WildFireModel()
    m.debug_log = False
    uavs = sorted([x for x in m.schedule.agents if type(x) is am.UAV], key=lambda z: z.unique_id)
    if a.corner != "none":
        ox, oy = CORNERS[a.corner]
        # row-major depot cells, one UAV per cell starting at the block origin
        cells = [(ox + i, oy + j) for i in range(5) for j in range(5)]
        for k, u in enumerate(uavs):
            m.grid.move_agent(u, cells[k])
        for uid, st in (getattr(m, "managed_uav_states", {}) or {}).items():
            for u in uavs:
                if str(u.unique_id) == uid and hasattr(st, "position"):
                    st.position = (float(u.pos[0]), float(u.pos[1]))
    start = {str(u.unique_id): u.pos for u in uavs}
    roles = {str(u.unique_id): m._uav_assignment_role(str(u.unique_id)) for u in uavs}
    tracks = {str(u.unique_id): [u.pos] for u in uavs}
    acts = {str(u.unique_id): [] for u in uavs}
    for _ in range(a.steps):
        m.step()
        for u in uavs:
            tracks[str(u.unique_id)].append(u.pos)
            acts[str(u.unique_id)].append(str(getattr(u, "execution_action", "") or ""))

def inblock(p, ox, oy):
    return ox <= p[0] <= ox + 4 and oy <= p[1] <= oy + 4

print("corner=%s seed=%d steps=%d roles=%s wind=%s" % (a.corner, a.seed, a.steps, a.roles, a.wind))
for uid in sorted(tracks, key=int):
    t = tracks[uid]
    moves = sum(1 for i in range(1, len(t)) if t[i] != t[i - 1])
    manh = abs(t[-1][0] - t[0][0]) + abs(t[-1][1] - t[0][1])
    if a.corner != "none":
        ox, oy = CORNERS[a.corner]
        inside = [i for i, p in enumerate(t) if inblock(p, ox, oy)]
        left = next((i for i, p in enumerate(t) if not inblock(p, ox, oy)), None)
        extra = " depot_steps=%d left_at=%s" % (len(inside), left)
    else:
        extra = ""
    from collections import Counter
    top = Counter(acts[uid]).most_common(3)
    print("  uav %s role=%-15s start=%s end=%s moves=%2d/%d net_manh=%2d%s" %
          (uid, roles[uid], t[0], t[-1], moves, a.steps, manh, extra))
    print("      actions: %s" % ", ".join("%s x%d" % (k or "(none)", v) for k, v in top))
