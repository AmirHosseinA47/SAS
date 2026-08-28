"""route_blocked campaign harness.

Read-only when --mode before: wraps _move_toward / _mark_route_blocked to record
what the OLD trigger did and what the NEW trigger WOULD do, changing nothing.
With --tag after it records the same fields against whatever agents.py now does.

Params mirror outputs/_ffdeath_probe.py exactly so the 18-run sample and its 16
classified deaths line up seed-for-seed.
"""
from __future__ import annotations
import argparse, collections, contextlib, io as _io, json, os, random, sys, time
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation

CUR = {"model": None, "seed": None}
CALLS = []          # one row per _move_toward call
FIRES = []          # actual route_blocked transitions
MARKS = []          # every _mark_route_blocked call (incl. suppressed)
DEATHS = []
LATCH = []          # end-of-run firefighters stuck in route_blocked
STATS = collections.Counter()
TIMING = collections.Counter()


def _fire_cells(model):
    cells = set()
    for a in model.schedule.agents:
        if type(a) is am.Fire and a.is_burning():
            p = getattr(a, "pos", None)
            if p is not None:
                cells.add((int(p[0]), int(p[1])))
    return cells


def _bfs_reachable(model, src, dst, blocked):
    """Same semantics as outputs/_ffdeath_probe._bfs_path_len: dst counts as
    reachable even when dst itself burns. Returns path length or None."""
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


_orig_move = am.Firefighter._move_toward
_orig_mark = am.Firefighter._mark_route_blocked


def _traced_move(self, target):
    model = self.model
    step = int(getattr(model, "evaluation_timesteps_counter", 0) or 0)
    line = sys._getframe(1).f_lineno
    src = (int(self.pos[0]), int(self.pos[1]))
    dst = (int(target[0]), int(target[1]))
    nb = self._neighbor_cells()
    n_fire = sum(1 for c in nb if self._cell_contains_active_fire(c))
    self_fire = self._cell_contains_active_fire(src)
    t0 = time.perf_counter()
    fires = _fire_cells(model)
    t1 = time.perf_counter()
    plen = _bfs_reachable(model, src, dst, fires)
    t2 = time.perf_counter()
    TIMING["firecells_ns"] += int((t1 - t0) * 1e9)
    TIMING["bfs_ns"] += int((t2 - t1) * 1e9)
    STATS["move_toward_calls"] += 1
    STATS["site_%d" % line] += 1
    scored_empty = bool(nb) and n_fire == len(nb)
    if scored_empty:
        STATS["old_trigger_hit"] += 1
        STATS["old_trigger_hit_site_%d" % line] += 1
    if plen is None:
        STATS["new_trigger_hit"] += 1
        STATS["new_trigger_hit_site_%d" % line] += 1
        if not self.exiting:
            STATS["new_trigger_hit_approach"] += 1
    CALLS.append({
        "seed": CUR["seed"], "step": step,
        "ff": str(getattr(self, "unit_id", "")),
        "line": line, "src": src, "dst": dst,
        "exiting": bool(self.exiting),
        "n_nb": len(nb), "n_fire": n_fire,
        "scored_empty": scored_empty,
        "self_on_fire": bool(self_fire),
        "bfs": plen,
        "manhattan": abs(src[0] - dst[0]) + abs(src[1] - dst[1]),
        "status_before": str(getattr(self, "status", "") or ""),
    })
    return _orig_move(self, target)


def _traced_mark(self):
    before = str(getattr(self, "status", "") or "")
    src = (int(self.pos[0]), int(self.pos[1])) if self.pos else None
    self_fire = self._cell_contains_active_fire(src) if src else False
    _orig_mark(self)
    now = str(getattr(self, "status", "") or "")
    step = int(getattr(self.model, "evaluation_timesteps_counter", 0) or 0)
    STATS["mark_calls"] += 1
    rec = {"seed": CUR["seed"], "step": step,
           "ff": str(getattr(self, "unit_id", "")),
           "before": before, "after": now, "self_on_fire": bool(self_fire),
           "pos": src, "exiting": bool(getattr(self, "exiting", False))}
    MARKS.append(rec)
    if now == "route_blocked" and before != "route_blocked":
        STATS["mark_set"] += 1
        FIRES.append(rec)
    elif now != "route_blocked":
        STATS["mark_suppressed"] += 1
        if self_fire:
            STATS["mark_suppressed_self_on_fire"] += 1
    return None


am.Firefighter._move_toward = _traced_move
am.Firefighter._mark_route_blocked = _traced_mark


def run(seed, params, steps):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    CUR["seed"] = seed
    terminal_step = None
    ran = 0
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        CUR["model"] = model
        alive = {}
        for s in range(1, steps + 1):
            model.step()
            ran = s
            ffm = getattr(model, "firefighter_marker_agents", {}) or {}
            for fid, m in ffm.items():
                d = bool(getattr(m, "dead", False))
                if fid not in alive:
                    alive[fid] = d
                    continue
                if d and not alive[fid]:
                    DEATHS.append({
                        "seed": seed, "step": s, "ff_id": fid,
                        "unit_id": str(getattr(m, "unit_id", "")),
                        "pos": tuple(int(v) for v in (getattr(m, "pos", None) or (-1, -1))),
                        "had_target": getattr(m, "target_pos", None) is not None,
                        "exiting": bool(getattr(m, "exiting", False)),
                    })
                alive[fid] = d
            if terminal_step is None:
                panel = model.get_dashboard_state()
                mission = panel.get("mission_status", {}) or {}
                if mission.get("all_victims_terminal"):
                    terminal_step = s
        for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
            st = str(getattr(m, "status", "") or "").strip().lower()
            if st == "route_blocked" and not getattr(m, "dead", False):
                LATCH.append({"seed": seed, "ff_id": fid, "status": st,
                              "assigned": bool(getattr(m, "assigned", False)),
                              "target_pos": getattr(m, "target_pos", None),
                              "pos": getattr(m, "pos", None)})
        ev = _build_evaluation(model, terminal_step, ran, params)
    ev["seed"] = seed
    ev["wall_s"] = round(time.perf_counter() - t0, 1)
    CUR["model"] = None
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    ft = n // 2 or 1
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"], "WIND_DIRECTION": a.wind,
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": n - ft}
    evals = []
    for seed in [int(s) for s in a.seeds.split(",")]:
        ev = run(seed, params, a.steps)
        evals.append(ev)
        sys.stderr.write(
            "%s seed %s done in %ss: rescued=%s dead=%s ff_deaths=%s "
            "| move_calls=%s old_hit=%s new_hit=%s mark_set=%s\n"
            % (a.tag, seed, ev.get("wall_s"), ev.get("rescued"), ev.get("dead"),
               ev.get("firefighter_deaths"), STATS["move_toward_calls"],
               STATS["old_trigger_hit"], STATS["new_trigger_hit"], STATS["mark_set"]))
        sys.stderr.flush()
    out = {"tag": a.tag, "scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "params": params, "evals": evals,
           "stats": dict(STATS), "timing_ns": dict(TIMING),
           "fires": FIRES, "marks": MARKS, "deaths": DEATHS, "latched": LATCH,
           "calls": CALLS}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_rb_%s_%s_%s.json" % (a.tag, a.scenario, a.wind))
    with open(p, "w") as f:
        json.dump(out, f, default=str)
    print(p)


main()
