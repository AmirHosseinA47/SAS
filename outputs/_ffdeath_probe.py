"""Read-only instrumentation: dispatch reachability vs firefighter deaths."""
from __future__ import annotations
import argparse, collections, contextlib, io as _io, json, os, random, sys
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS

CUR = {"model": None, "seed": None}
EVENTS = []
ROUTE_BLOCKED_FIRES = []
MOVE_STATS = collections.Counter()


def _fire_cells(model):
    cells = set()
    for a in model.schedule.agents:
        if type(a) is am.Fire and a.is_burning():
            p = getattr(a, "pos", None)
            if p is not None:
                cells.add((int(p[0]), int(p[1])))
    return cells


def _bfs_path_len(model, src, dst, blocked):
    W = getattr(model, "WIDTH", 50)
    H = getattr(model, "HEIGHT", 50)
    if src == dst:
        return 0
    seen = {src}
    q = collections.deque([(src, 0)])
    while q:
        (x, y), d = q.popleft()
        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + ox, y + oy)
            if not (0 <= n[0] < H and 0 <= n[1] < W):
                continue
            if n in seen:
                continue
            if n == dst:
                return d + 1
            if n in blocked:
                continue
            seen.add(n)
            q.append((n, d + 1))
    return None


_orig_select = wf.select_rescue_assignment


def _wrapped(snapshot, reason, *, victim_id=None):
    dec = _orig_select(snapshot, reason, victim_id=victim_id)
    model = CUR["model"]
    action = getattr(dec, "rescue_action", None)
    if action is None and isinstance(dec, dict):
        action = dec.get("action")
    if model is None or action != "assign":
        return dec
    vid = getattr(dec, "victim_id", "")
    ffid = getattr(dec, "firefighter_id", "")
    victims = snapshot.get("victims", {}) or {}
    ffs = snapshot.get("firefighters", {}) or {}
    vpos = (victims.get(vid) or {}).get("position")
    fpos = (ffs.get(ffid) or {}).get("position")
    if vpos is None or fpos is None:
        return dec
    vpos = (int(vpos[0]), int(vpos[1]))
    blocked = _fire_cells(model)
    pool = []
    for fid, e in ffs.items():
        if e.get("dead") or e.get("assigned") or e.get("route_blocked"):
            continue
        if not e.get("available", True):
            continue
        p = e.get("position")
        if p is None:
            continue
        p = (int(p[0]), int(p[1]))
        man = abs(p[0] - vpos[0]) + abs(p[1] - vpos[1])
        bfs = _bfs_path_len(model, p, vpos, blocked)
        pool.append({"ff": fid, "manhattan": man, "bfs": bfs,
                     "detour": (None if bfs is None else bfs - man)})
    chosen = None
    for c in pool:
        if c["ff"] == ffid:
            chosen = c
            break
    ch_detour = chosen["detour"] if chosen else None
    EVENTS.append({
        "step": int(snapshot.get("step", 0) or 0),
        "seed": CUR["seed"],
        "victim_id": vid, "ff_id": ffid, "reason": str(reason),
        "manhattan": chosen["manhattan"] if chosen else None,
        "bfs": chosen["bfs"] if chosen else None,
        "detour": ch_detour,
        "pool_size": len(pool),
        "pool": pool,
        "n_clear_alternatives": sum(
            1 for c in pool if c["ff"] != ffid and c["bfs"] is not None),
        "n_strictly_better_alt": sum(
            1 for c in pool
            if c["ff"] != ffid and c["bfs"] is not None
            and (ch_detour is None or c["detour"] < ch_detour)),
    })
    return dec


wf.select_rescue_assignment = _wrapped
try:
    import src_extension.execution.rescue_executor as _rx
    _rx.select_rescue_assignment = _wrapped
except Exception:
    pass


_orig_mark = am.Firefighter._mark_route_blocked


def _mark(self):
    before = str(getattr(self, "status", "") or "")
    _orig_mark(self)
    now = str(getattr(self, "status", "") or "")
    MOVE_STATS["mark_route_blocked_called"] += 1
    if now == "route_blocked" and before != "route_blocked":
        ROUTE_BLOCKED_FIRES.append({
            "seed": CUR["seed"],
            "step": int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0),
            "ff": str(getattr(self, "unit_id", ""))})


am.Firefighter._mark_route_blocked = _mark

_orig_move_toward = am.Firefighter._move_toward


def _move_toward(self, target):
    nb = self._neighbor_cells()
    n_fire = sum(1 for c in nb if self._cell_contains_active_fire(c))
    MOVE_STATS["move_toward_calls"] += 1
    if n_fire:
        MOVE_STATS["calls_with_burning_neighbour"] += 1
        MOVE_STATS["max_burning_neighbours"] = max(
            MOVE_STATS["max_burning_neighbours"], n_fire)
    if nb and n_fire == len(nb):
        MOVE_STATS["calls_all_neighbours_burning"] += 1
        if self._cell_contains_active_fire((int(self.pos[0]), int(self.pos[1]))):
            MOVE_STATS["all_burning_and_self_on_fire"] += 1
    return _orig_move_toward(self, target)


am.Firefighter._move_toward = _move_toward


def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    CUR["seed"] = seed
    deaths = []
    trace = []
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        CUR["model"] = model
        alive = {}
        for s in range(1, steps + 1):
            model.step()
            ffm = getattr(model, "firefighter_marker_agents", {}) or {}
            fires = _fire_cells(model)
            for fid, m in ffm.items():
                d = bool(getattr(m, "dead", False))
                if fid not in alive:
                    alive[fid] = d
                    continue
                if d and not alive[fid]:
                    deaths.append({
                        "seed": seed, "step": s, "ff_id": fid,
                        "pos": tuple(int(v) for v in (getattr(m, "pos", None) or (-1, -1))),
                        "had_target": getattr(m, "target_pos", None) is not None,
                        "exiting": bool(getattr(m, "exiting", False)),
                    })
                alive[fid] = d
            # per-step per-FF route health for FFs currently en route
            for fid, m in ffm.items():
                if getattr(m, "dead", False) or getattr(m, "pos", None) is None:
                    continue
                tgt = getattr(m, "target_pos", None)
                if tgt is None:
                    continue
                src = (int(m.pos[0]), int(m.pos[1]))
                dst = (int(tgt[0]), int(tgt[1]))
                trace.append({"seed": seed, "step": s, "ff_id": fid,
                              "bfs": _bfs_path_len(model, src, dst, fires)})
    CUR["model"] = None
    return deaths, trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", default="101,202,303,404,505")
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft}
    all_deaths = []
    all_trace = []
    for seed in [int(s) for s in a.seeds.split(",")]:
        d, t = run(seed, params, a.steps)
        all_deaths.extend(d)
        all_trace.extend(t)
        sys.stderr.write("seed %s done: %d dispatches, %d deaths\n"
                         % (seed, len(EVENTS), len(all_deaths)))
        sys.stderr.flush()
    out = {"scenario": a.scenario, "wind": a.wind, "steps": a.steps, "seeds": a.seeds,
           "params": params,
           "dispatches": EVENTS, "deaths": all_deaths, "trace": all_trace,
           "route_blocked_fires": ROUTE_BLOCKED_FIRES,
           "move_stats": dict(MOVE_STATS)}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_ffdeath_%s_%s.json" % (a.scenario, a.wind))
    with open(p, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(p)


main()
