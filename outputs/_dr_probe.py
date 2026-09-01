"""Dispatch-reachability instrumentation, hooked at select_rescue_assignment.

Records, for EVERY pairing call that results in an "assign", the full
candidate pool the planner saw, each candidate's Manhattan distance to the
chosen victim, and each candidate's LIVE BFS reachability to that victim at
the moment of commitment - computed with the same
_path_exists_avoiding_fire the route_blocked recovery pass uses
(wildfire_model._revalidate_route_blocked_firefighters, 70e1b33).

It then follows every dispatch forward: per step, until the victim resolves
or the run ends, it re-tests reachability from EVERY original candidate's
current position to the victim's current position.  That is what makes
question (d) - "did a passed-over candidate have a route that stayed open?" -
answerable rather than speculative.

--arm selects a runtime-only what-if variant of the pairing sort:
    none  stock c4d5a25 - passthrough, nothing changed
    a     HARD FILTER    - unreachable candidates are struck from the pool
                           before the Manhattan sort; an empty pool falls
                           through to the planner's own no-firefighter branch
    b     SOFT TIEBREAK  - sort key becomes (manhattan, not reachable, id)
    bt    SOFT TIEBREAK, THRESHOLDED - reachability is consulted only when the
                           top-two Manhattan margin is <= --margin
    c     ROUTE-LENGTH TIEBREAK - sort key (manhattan, bfs_length, id).  Acts
                           only where Manhattan already ties, i.e. only where
                           the stock code falls back to alphabetical unit ID.
    d     ROUTE-LENGTH PRIMARY - sort key (bfs_length, id).  Measured to show
                           whether it buys anything arm c does not.
Nothing is written to source; every arm is a monkeypatch applied by
substituting the module-level name in every module that imported it.
"""
from __future__ import annotations
import argparse, contextlib, io as _io, json, os, random, sys, time
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents as am
import common_fixed_variables as cfv
import wildfire_model as wf
import src_extension.execution.rescue_executor as rx
from src_extension.planning.decision_objects import RescueDecision
from src_extension.planning import rescue_planner as rp
from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
from wildfire_model import WildFireModel
from serve_dashboard import BUILTIN_SCENARIOS, _build_evaluation, _resolve_role_count_params

CUR = {"model": None, "seed": None, "arm": "none", "margin": 2}
DISPATCH = []   # every select_rescue_assignment call that returned "assign"
NOFF = []       # every call that hit the no-firefighter-available branch
FOLLOW = []     # per-step reachability follow-up for each open dispatch
DEATHS = []
EVALS = []
FFTRACE = []
VTRACE = []
BFS = {"calls": 0, "secs": 0.0, "dispatch_calls": 0, "dispatch_secs": 0.0}
OPEN = []       # dispatches still being followed


def _step_no(model):
    return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)


def _mfd(cell, fires):
    if not fires:
        return 999
    cx, cy = cell
    return min(abs(cx - fx) + abs(cy - fy) for fx, fy in fires)


def _man(a, b):
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


def _any_marker(model):
    d = getattr(model, "firefighter_marker_agents", None) or {}
    for m in d.values():
        return m
    return None


def _fire_cells_model(model):
    m = _any_marker(model)
    if m is None:
        return set()
    return m._fire_cells()


def _bfs_len(model, src, dst, fire_cells):
    """Shortest 4-connected path length with active fire impassable.

    DIAGNOSTIC ONLY, and deliberately NOT the production predicate: the arms
    are driven by _path_exists_avoiding_fire, which is what the route_blocked
    recovery pass uses.  This exists to answer the obvious challenge to a
    null result - "your reachability test was too permissive" - by measuring
    the near-continuous version of the same question (detour = bfs - manhattan)
    on exactly the same dispatches.  Same fire semantics as the boolean:
    destination reachable even if itself burning, source never tested.
    """
    from collections import deque
    src = (int(src[0]), int(src[1]))
    dst = (int(dst[0]), int(dst[1]))
    if src == dst:
        return 0
    grid = model.grid
    seen = {src}
    q = deque([(src, 0)])
    while q:
        (cx, cy), d = q.popleft()
        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cell = (cx + ox, cy + oy)
            if grid.out_of_bounds(cell) or cell in seen:
                continue
            if cell == dst:
                return d + 1
            if cell in fire_cells:
                continue
            seen.add(cell)
            q.append((cell, d + 1))
    return None


def _reach(model, src, dst, fire_cells, bucket="dispatch"):
    """Live 4-connected reachability, fire impassable.  Timed."""
    m = _any_marker(model)
    if m is None:
        return None
    t0 = time.perf_counter()
    try:
        ok = bool(m._path_exists_avoiding_fire(
            (int(src[0]), int(src[1])), (int(dst[0]), int(dst[1])), fire_cells))
    except Exception:
        return None
    dt = time.perf_counter() - t0
    BFS["calls"] += 1
    BFS["secs"] += dt
    if bucket == "dispatch":
        BFS["dispatch_calls"] += 1
        BFS["dispatch_secs"] += dt
    return ok


# ---------------------------------------------------------------- candidates
def _candidates(snapshot):
    """The planner's own availability filter, replicated verbatim from
    rescue_planner.select_rescue_assignment:577-591.  The chosen unit is
    cross-checked against this list on every record, so drift shows up as
    data rather than as a silent wrong denominator."""
    out = []
    ffs = snapshot.get("firefighters")
    if not isinstance(ffs, dict):
        return out
    for ff_id, entry in ffs.items():
        ff_s = str(ff_id or "").strip()
        if not ff_s or not isinstance(entry, dict):
            continue
        if bool(entry.get("dead", False)):
            continue
        if bool(entry.get("assigned", False)):
            continue
        if bool(entry.get("route_blocked", False)):
            continue
        if not bool(entry.get("available", True)):
            continue
        pos = entry.get("position")
        if pos is None or len(pos) < 2:
            continue
        out.append((ff_s, (int(pos[0]), int(pos[1]))))
    return out


def _restrict(snapshot, keep):
    """Snapshot with every firefighter outside keep marked unavailable.

    The arms are applied by shrinking the pool and re-calling the REAL
    planner, never by reimplementing its sort - so an arm's decision object
    is exactly what production would emit, including the payload, the
    decision_id and the no-firefighter branch."""
    keep = set(keep)
    ffs = snapshot.get("firefighters") or {}
    new = {}
    for k, v in ffs.items():
        if not isinstance(v, dict):
            new[k] = v
            continue
        if str(k).strip() in keep:
            new[k] = v
        else:
            new[k] = {**v, "available": False}
    s2 = dict(snapshot)
    s2["firefighters"] = new
    return s2


_orig_sra = rp.select_rescue_assignment


def _sra(snapshot, reason, *, victim_id=None):
    model = CUR["model"]
    dec = _orig_sra(snapshot, reason, victim_id=victim_id)
    if model is None:
        return dec

    step = _step_no(model)
    action = ""
    vid = ""
    ffid = ""
    if isinstance(dec, RescueDecision):
        action = str(dec.rescue_action or "").strip().lower()
        vid = str(dec.victim_id or "").strip()
        ffid = str(dec.firefighter_id or "").strip()

    if action != "assign":
        if action in ("delay", "mark_unreachable"):
            NOFF.append({"seed": CUR["seed"], "step": step, "arm": CUR["arm"],
                         "victim": vid, "action": action, "reason": str(reason or ""),
                         "n_cand": len(_candidates(snapshot)), "forced": False})
        return dec

    victims = snapshot.get("victims") or {}
    ventry = victims.get(vid) if isinstance(victims, dict) else None
    vpos = (ventry or {}).get("position")
    if vpos is None:
        return dec
    vpos = (int(vpos[0]), int(vpos[1]))

    cands = _candidates(snapshot)
    fire_cells = _fire_cells_model(model)
    rows = []
    for cid, cpos in cands:
        bl = _bfs_len(model, cpos, vpos, fire_cells)
        man = _man(vpos, cpos)
        rows.append({"ff": cid, "pos": list(cpos), "man": man,
                     "reach": _reach(model, cpos, vpos, fire_cells),
                     "bfs": bl, "detour": (None if bl is None else bl - man)})
    rows.sort(key=lambda r: (r["man"], r["ff"]))

    rec = {
        "seed": CUR["seed"], "step": step, "arm": CUR["arm"],
        "reason": str(reason or ""), "victim": vid, "vpos": list(vpos),
        "n_cand": len(rows), "cands": rows,
        "stock_ff": ffid,
        "stock_in_pool": any(r["ff"] == ffid for r in rows),
        "stock_reach": next((r["reach"] for r in rows if r["ff"] == ffid), None),
        "stock_man": next((r["man"] for r in rows if r["ff"] == ffid), None),
        "n_fire": len(fire_cells),
        "vpos_burning": bool(vpos in fire_cells),
        "margin": (rows[1]["man"] - rows[0]["man"]) if len(rows) >= 2 else None,
        "arm_ff": ffid, "arm_action": "assign", "arm_changed": False,
    }

    arm = CUR["arm"]
    if arm == "a":
        keep = [r["ff"] for r in rows if r["reach"]]
        rec["empty_pool"] = (len(keep) == 0)
        if len(keep) != len(rows):
            dec = _orig_sra(_restrict(snapshot, keep), reason, victim_id=victim_id)
            na = str(getattr(dec, "rescue_action", "") or "").strip().lower()
            nf = str(getattr(dec, "firefighter_id", "") or "").strip()
            rec["arm_action"] = na
            rec["arm_ff"] = nf
            rec["arm_changed"] = (na != "assign") or (nf != ffid)
            if na != "assign":
                NOFF.append({"seed": CUR["seed"], "step": step, "arm": arm,
                             "victim": vid, "action": na, "reason": str(reason or ""),
                             "n_cand": len(rows), "forced": True})
    elif arm in ("b", "bt", "c", "d"):
        consult = True
        if arm == "bt":
            consult = (len(rows) >= 2 and
                       (rows[1]["man"] - rows[0]["man"]) <= int(CUR["margin"]))
        if consult:
            if arm == "c":
                # Manhattan stays the primary key; the ROUTE LENGTH the same
                # BFS already computed replaces the alphabetical-ID fallback
                # as the tiebreak.  Acts only where the primary key says the
                # units are equally good, i.e. only where the stock code is
                # choosing by firefighter name.
                best = sorted(rows, key=lambda r: (
                    r["man"], (10 ** 6 if r.get("bfs") is None else r["bfs"]), r["ff"]))
            elif arm == "d":
                # route length as the PRIMARY key - a larger change, measured
                # only to show whether it buys anything arm c does not.
                best = sorted(rows, key=lambda r: (
                    (10 ** 6 if r.get("bfs") is None else r["bfs"]), r["ff"]))
            else:
                best = sorted(rows, key=lambda r: (r["man"], not bool(r["reach"]), r["ff"]))
            win = best[0]["ff"] if best else ffid
            if win != ffid:
                dec = _orig_sra(_restrict(snapshot, [win]), reason, victim_id=victim_id)
                nf = str(getattr(dec, "firefighter_id", "") or "").strip()
                rec["arm_ff"] = nf
                rec["arm_changed"] = (nf != ffid)
        rec["consulted"] = consult

    DISPATCH.append(rec)
    chosen = rec["arm_ff"]
    if rec["arm_action"] == "assign" and chosen:
        OPEN.append({"seed": CUR["seed"], "step": step, "victim": vid,
                     "chosen": chosen,
                     "cands": [r["ff"] for r in rows],
                     "did": len(DISPATCH) - 1})
    return dec


wf.select_rescue_assignment = _sra
rx.select_rescue_assignment = _sra
rp.select_rescue_assignment = _sra


def _follow(model, step):
    """Per-step reachability re-test for every dispatch still open."""
    if not OPEN:
        return
    vmark = getattr(model, "victim_marker_agents", None) or {}
    fmark = getattr(model, "firefighter_marker_agents", None) or {}
    fire_cells = _fire_cells_model(model)
    still = []
    for d in OPEN:
        vm = vmark.get(d["victim"])
        vstat = str(getattr(vm, "status", "") or "").strip().lower() if vm is not None else "gone"
        vpos = getattr(vm, "pos", None) if vm is not None else None
        if vm is None or vstat in ("rescued", "dead", "unreachable") or vpos is None:
            continue
        vcell = (int(vpos[0]), int(vpos[1]))
        row = {"seed": d["seed"], "step": step, "did": d["did"],
               "victim": d["victim"], "vstat": vstat, "r": {}}
        for cid in d["cands"]:
            fm = fmark.get(cid)
            if fm is None or getattr(fm, "dead", False) or getattr(fm, "pos", None) is None:
                row["r"][cid] = None
                continue
            fc = (int(fm.pos[0]), int(fm.pos[1]))
            row["r"][cid] = _reach(model, fc, vcell, fire_cells, bucket="follow")
        FOLLOW.append(row)
        still.append(d)
    OPEN[:] = still


def _fire_cells(model):
    out = set()
    for a in model.schedule.agents:
        if type(a) is am.Fire and a.is_burning():
            p = getattr(a, "pos", None)
            if p is not None:
                out.add((int(p[0]), int(p[1])))
    return out


def run(seed, params, steps, follow):
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    CUR["seed"] = seed
    OPEN[:] = []
    alive = {}
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(_io.StringIO()):
        model = WildFireModel()
        model.debug_log = False
        CUR["model"] = model
        for s in range(1, steps + 1):
            model.step()
            fires = _fire_cells(model)
            for fid, m in (getattr(model, "firefighter_marker_agents", {}) or {}).items():
                d = bool(getattr(m, "dead", False))
                pos = getattr(m, "pos", None)
                cell = (int(pos[0]), int(pos[1])) if pos is not None else None
                mr = getattr(m, "movement_reason", None) or {}
                nfree = None
                if cell is not None and not d:
                    nfree = sum(1 for n in m._neighbor_cells()
                                if not m._cell_contains_active_fire(n))
                FFTRACE.append({
                    "seed": seed, "step": s, "ff": fid,
                    "pos": (list(cell) if cell else None), "dead": d,
                    "status": str(getattr(m, "status", "") or ""),
                    "assigned": bool(getattr(m, "assigned", False)),
                    "target": (list(m.target_pos)
                               if getattr(m, "target_pos", None) else None),
                    "exiting": bool(getattr(m, "exiting", False)),
                    "stalled": bool(getattr(m, "_idle_retreat_stalled", False)),
                    "last_cell": (list(getattr(m, "_idle_retreat_last_cell", None))
                                  if getattr(m, "_idle_retreat_last_cell", None) else None),
                    "mfd": (_mfd(cell, fires) if cell else None),
                    "n_free": nfree, "cat": str(mr.get("category", "")),
                })
                if fid not in alive:
                    alive[fid] = d
                elif d and not alive[fid]:
                    DEATHS.append({"seed": seed, "step": s, "ff": fid,
                                   "pos": (list(cell) if cell else None),
                                   "cat": str(mr.get("category", ""))})
                alive[fid] = d
            for vid, vm in (getattr(model, "victim_marker_agents", {}) or {}).items():
                vp = getattr(vm, "pos", None)
                VTRACE.append({
                    "seed": seed, "step": s, "v": str(vid),
                    "pos": ([int(vp[0]), int(vp[1])] if vp is not None else None),
                    "status": str(getattr(vm, "status", "") or ""),
                })
            if follow:
                _follow(model, s)
        ev = _build_evaluation(model, None, steps, params)
        ev["seed"] = seed
        EVALS.append(ev)
    CUR["model"] = None
    return time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="D")
    ap.add_argument("--wind", default="east")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--seeds", default="101,202,303,404,505")
    ap.add_argument("--roles", default="half", choices=["half", "default"])
    ap.add_argument("--arm", default="none", choices=["none", "a", "b", "bt", "c", "d"])
    ap.add_argument("--margin", type=int, default=2)
    ap.add_argument("--follow", type=int, default=1)
    ap.add_argument("--tag", default="")
    ap.add_argument("--prefix", default="_dr")
    a = ap.parse_args()
    CUR["arm"] = a.arm
    CUR["margin"] = a.margin
    preset = BUILTIN_SCENARIOS[a.scenario]
    n = preset["NUM_AGENTS"]
    if a.roles == "half":
        ft = n // 2 or 1
        vs = n - ft
    else:
        ft, vs = _resolve_role_count_params(n, None, None)
    params = {"NUM_AGENTS": n, "NUM_VICTIMS": preset["NUM_VICTIMS"],
              "NUM_FIREFIGHTERS": preset["NUM_FIREFIGHTERS"],
              "WIND_DIRECTION": a.wind, "BATCH_SIZE": 300,
              "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}
    walls = []
    for seed in [int(s) for s in a.seeds.split(",")]:
        walls.append(run(seed, params, a.steps, bool(a.follow)))
        sys.stderr.write("seed %s done: disp=%d bfs=%d/%.3fs wall=%.1fs\n"
                         % (seed, len(DISPATCH), BFS["calls"], BFS["secs"], walls[-1]))
        sys.stderr.flush()
    out = {"scenario": a.scenario, "wind": a.wind, "steps": a.steps,
           "seeds": a.seeds, "roles": a.roles, "arm": a.arm,
           "margin": a.margin, "follow": bool(a.follow), "params": params,
           "dispatch": DISPATCH, "noff": NOFF, "follow_rows": FOLLOW,
           "deaths": DEATHS, "evals": EVALS, "fftrace": FFTRACE, "vtrace": VTRACE,
           "bfs": BFS, "wall": walls}
    tag = a.tag or ("%s_%s_%s_%s" % (a.scenario, a.wind, a.roles, a.arm))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "%s_%s.json" % (a.prefix, tag))
    with open(p, "w") as f:
        json.dump(out, f, separators=(",", ":"), default=str)
    print(p)


main()
