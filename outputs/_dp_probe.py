"""Dispatch round Part 3 instrument: outputs/_ut_probe.py (UNCHANGED, run in-process) plus read-only dispatch
recorders (outputs/dispatch_part1.txt 14.4, amendment A1 21.2(g)/(h)/(j)).

usage: _dp_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args ...>   (exactly _ut_probe.py's interface)
       --repo is REQUIRED after "--" (every layer below defaults to the main checkout otherwise).

Adds d["dp"] to the probe JSON - written whatever the chain's return code (a crashed run keeps its record). Every
recorder only READS model state: no print to stdout, no warning, no attribute set on the model or an agent, no draw
from any RNG; exceptions are caught and listed in d["dp"]["errors"] (an observer never stops a run). The route
searches here are the instrument's OWN code (an independent cross-check of J's), on grid.out_of_bounds.

d["dp"]:
  version, switches {raw / effective DISPATCH_*, S, M, P}, src_sha {file: sha256} (files the sd probe misses)
  commands   every apply_physical_rescue_command: [step, phase, action, victim, unit, reason, success,
             route_open, d_route, manhattan] - route_open / d_route = the instrument's BFS verdict at an assign
  releases   every _release_other_claimants call: [step, phase, victim, keep, reason, only_ff_id, released]
  j_calls    every J solve point while DISPATCH_JOINT is on: [step, phase, ms, new_events(, {"legacy": [[victim,
             unit], ...], "j_fills": [[victim, unit], ...]})] - M4's counterfactual: today's rule (victim-index
             order, nearest free unit by Manhattan, ties to the smaller id string) on the same state, before J acts
  j_events   the model's _dispatch_events at the end (fill / latch_fill / replace / second_fill / *_refused / *_aborted)
  ledger     {"unit|victim": binds} at the end
  binders    after each _sync_firefighter_marker_status (after J-post, before the escape sweep):
             [step, [[victim, [[unit, status], ...]], ...]] for victims with a living binder
  waiting    same instant: [step, n_free, [[victim, [[unit, d, b], ...]], ...]] for DETECTED needy victims with no
             ACTIVE binder and NOT in custody (no binder exiting, rescue_completed or standing on the victim's cell -
             J's own W / W_L, design 5.2): every free unit with a finite route d, and the pair's ledger count b
  waiting_custody  same instant: [step, [victim, ...]] - detected needy victims with no active binder that ARE in a
             binder's custody (excluded from `waiting`; R3 finding 4)
  m3a        same instant, when some victim is waiting: [step, n_free, n_free_ledger_allowed] (M3(a) split, 14.7)
  invariant  captured _check_rescue_assignment_invariant stderr lines: [step, text] (re-emitted to stderr)
  m8         per detected victim: {victim, detection_step, cell, t_fire, min_d, first_burn_step, death_step}
  m9         K13: [step, unit, from_victim, to_victim, frames_finite (list of P post samples: v reachable?)] - for a
             bind made at J-post the same step's sample is skipped (v is closed by construction there)
  j_detail   every J call while DISPATCH_JOINT is on at which PRE held (14.4): [step, phase, {"sets": {free, waiting,
             latched, contest}, "pre": bool, "calls": [solve_fill / plan_replacements / progress_step inputs and
             outputs], "progress": {"unit|victim": [best, k, d_prev, cell_prev, age, persist]}, "unevaluated":
             [[unit, victim], ...] (contestable bindings with a progress state that were not evaluated: d or x
             infinite, design 6.3 / Part 2 note P2-3)}]
  j_timing   every J call while DISPATCH_JOINT is on: [step, phase, raw_ms, net_ms, thread_ms, gc_collections];
             net_ms (also j_calls[i][2]) = raw minus the instrument's own work nested inside the call (its route
             verdict at an assign, its capture wrappers) - 12.3 times J's builder, BFS, solver and apply only
  writeoffs_avoided, timing {j_ms_total (net), j_ms_raw_total, inst_ms_total}, errors
"""
from __future__ import annotations

import gc
import hashlib
import io
import json
import os
import runpy
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
_N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
SHA_FILES = (
    "src_extension/planning/joint_dispatch.py",
    "src_extension/adaptation_manager.py",
    "src_extension/execution/rescue_executor.py",
    "src_extension/planning/rescue_planner.py",
    "wildfire_model.py",
    "agents.py",
    "common_fixed_variables.py",
)


def _bfs(source, grid, blocked):
    """The instrument's own 4-connected BFS from `source` over in-bounds cells not in `blocked`."""
    start = (int(source[0]), int(source[1]))
    dist = {start: 0}
    queue = deque([start])
    while queue:
        cx, cy = queue.popleft()
        for ox, oy in _N4:
            cell = (cx + ox, cy + oy)
            if cell in dist or cell in blocked or grid.out_of_bounds(cell):
                continue
            dist[cell] = dist[(cx, cy)] + 1
            queue.append(cell)
    return dist


def _at(dist, cell, blocked):
    """d at a unit's cell, the unit's own cell exempt like the route test's source."""
    cell = (int(cell[0]), int(cell[1]))
    if cell in dist:
        return dist[cell]
    if cell not in blocked:
        return None
    near = [dist[(cell[0] + ox, cell[1] + oy)] for ox, oy in _N4 if (cell[0] + ox, cell[1] + oy) in dist]
    return min(near) + 1 if near else None


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _dp_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args>", file=sys.stderr)
        return 2
    probe_args = argv[argv.index("--") + 1:]
    if "--repo" not in probe_args:
        print("DP REFUSED: --repo is required (every layer defaults to the main checkout)", file=sys.stderr)
        return 3
    repo = probe_args[probe_args.index("--repo") + 1]
    out_path = probe_args[probe_args.index("--out") + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as ag  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.adaptation_manager as amod  # noqa: E402
    import src_extension.adaptation.local_adaptation_generator as gen  # noqa: E402

    WM = wf.WildFireModel
    rec = {
        "model": None, "phase": "init", "commands": [], "releases": [], "j_calls": [], "binders": [], "waiting": [],
        "waiting_custody": [], "m3a": [], "invariant": [], "m8": {}, "m9": [], "m9_open": [], "last_release": {}, "errors": [],
        "j_ms": 0.0, "j_raw_ms": 0.0, "inst_ms": 0.0, "j_detail": [], "j_timing": [],
        "in_j": False, "j_phase": None, "j_cur": None, "nest_ms": 0.0, "gc_n": 0,
    }
    # B (the reference arm's checkout) has no dispatch code: every dispatch accessor is optional here.
    joint_on = getattr(ag, "dispatch_joint", None) or (lambda: False)

    def gc_cb(phase, info):
        if rec["in_j"] and phase == "start":
            rec["gc_n"] += 1

    gc.callbacks.append(gc_cb)

    def err(where, exc):
        if len(rec["errors"]) < 30:
            rec["errors"].append(f"{where}: {exc!r}"[:240])

    def step_of(m):
        return int(getattr(m, "evaluation_timesteps_counter", 0) or 0)

    def burning_cells(m):
        cells = set()
        for a in m.schedule.agents:
            if type(a) is ag.Fire and a.pos is not None and a.is_burning():
                cells.add((int(a.pos[0]), int(a.pos[1])))
        return cells

    def living_units(m):
        out = {}
        for fid, fm in (getattr(m, "firefighter_marker_agents", None) or {}).items():
            if getattr(fm, "dead", False) or str(getattr(fm, "status", "") or "").lower() == "dead":
                continue
            out[str(fid)] = fm
        return out

    def needy(m, vid, marker):
        state = (getattr(m, "managed_victims", None) or {}).get(vid)
        ms = str(getattr(marker, "status", "") or "").lower()
        ss = str(getattr(state, "status", "") or "").lower() if state is not None else ""
        if state is None or getattr(marker, "pos", None) is None:
            return False
        if getattr(state, "rescued", False) or "rescued" in (ms, ss) or "dead" in (ms, ss):
            return False
        if getattr(state, "cancelled", False) or ms == "cancelled":
            return False
        if getattr(state, "unreachable", False) or ms == "unreachable":
            return False
        return True

    # ------------------------------------------------------------------ phase markers
    am_cls = None
    for obj in vars(amod).values():
        if isinstance(obj, type) and hasattr(obj, "_run_post_move_cycle") and hasattr(obj, "_run_pre_move_cycle"):
            am_cls = obj
            break
    if am_cls is not None:
        o_pre, o_post = am_cls._run_pre_move_cycle, am_cls._run_post_move_cycle

        def pre_cycle(self, model, *a, **k):
            rec["phase"] = "pre"
            r = o_pre(self, model, *a, **k)
            rec["phase"] = "advance"
            return r

        def post_cycle(self, model, *a, **k):
            rec["phase"] = "post"
            r = o_post(self, model, *a, **k)
            rec["phase"] = "sweep"
            return r

        am_cls._run_pre_move_cycle = pre_cycle
        am_cls._run_post_move_cycle = post_cycle

    # ------------------------------------------------------------------ commands (the sink)
    o_apply = WM.apply_physical_rescue_command

    def apply_cmd(self, cmd):
        info = None
        extra = [None, None, None]
        t0 = time.perf_counter()
        try:
            action = str(cmd.action or "").strip().lower()
            vid = str(cmd.victim_id or "")
            fid = str(cmd.firefighter_id or "")
            # the record first: an observer error below can never drop it (R3 finding 1)
            info = [step_of(self), rec["phase"], action, vid, fid, str(cmd.reason or "")]
        except Exception as exc:
            err("apply_pre", exc)
        if info is not None and info[2] == "assign":
            try:
                vm = (cmd.metadata or {}).get("victim_marker") or (self.victim_marker_agents or {}).get(vid)
                fm = (self.firefighter_marker_agents or {}).get(fid)
                if vm is not None and fm is not None and vm.pos is not None and fm.pos is not None:
                    blocked = burning_cells(self)
                    d_route = _at(_bfs(vm.pos, self.grid, blocked), fm.pos, blocked)
                    extra = [d_route is not None, d_route,
                             abs(int(vm.pos[0]) - int(fm.pos[0])) + abs(int(vm.pos[1]) - int(fm.pos[1]))]
                    # K13 / M9: a unit freed by its first route_blocked raise on v, now bound to w != v
                    last = rec["last_release"].get(fid)
                    if joint_on() and last and last[0] == "o1" and last[1] != vid:
                        v_old = (self.victim_marker_agents or {}).get(last[1])
                        if v_old is not None and v_old.pos is not None and needy(self, last[1], v_old):
                            dmap = _bfs(v_old.pos, self.grid, blocked)
                            closed = all(_at(dmap, u.pos, blocked) is None
                                         for u in living_units(self).values() if u.pos is not None)
                            if closed:
                                entry = [step_of(self), fid, last[1], vid, []]
                                rec["m9"].append(entry)
                                rec["m9_open"].append((entry, step_of(self), rec["j_phase"] if rec["in_j"] else None))
            except Exception as exc:
                err("apply_obs", exc)
        spent = (time.perf_counter() - t0) * 1000.0
        rec["inst_ms"] += spent
        if rec["in_j"]:
            rec["nest_ms"] += spent
        ok = o_apply(self, cmd)
        try:
            if info is not None:
                rec["commands"].append(info + [bool(ok)] + extra)
                if info[2] == "unassign" and ok:
                    kind = "o1" if "replacement" in info[5] and "blocked" in info[5] else "other"
                    rec["last_release"][info[4]] = (kind, info[3], info[0])
                elif info[2] == "assign" and ok:
                    rec["last_release"].pop(info[4], None)
        except Exception as exc:
            err("apply_post", exc)
        return ok

    WM.apply_physical_rescue_command = apply_cmd

    # ------------------------------------------------------------------ releases
    o_release = WM._release_other_claimants

    def release(self, *args, **kwargs):
        out = o_release(self, *args, **kwargs)
        try:
            vid = args[0] if args else kwargs.get("victim_id")
            keep = args[2] if len(args) > 2 else kwargs.get("keep_ff_id")
            reason = args[3] if len(args) > 3 else kwargs.get("reason")
            rec["releases"].append([step_of(self), rec["phase"], str(vid), str(keep or ""), str(reason or ""),
                                    str(kwargs.get("only_ff_id", "") or ""), list(out or [])])
            for fid in out or []:
                rec["last_release"][str(fid)] = ("release", str(vid), step_of(self))
        except Exception as exc:
            err("release", exc)
        return out

    WM._release_other_claimants = release

    # ------------------------------------------------------------------ J solve points (timing)
    o_jpoint = getattr(WM, "_joint_dispatch_point", None)
    if o_jpoint is not None:
        def legacy_pairs(view):
            """M4's counterfactual (14.7): today's rule on the same state - waiting victims in victim-index order,
            each to the nearest free unit by Manhattan distance, ties to the smaller id STRING."""
            units = view["units"]
            used, pairs = set(), []

            def vindex(v):
                tail = v.rsplit("_", 1)[-1]
                return (int(tail) if tail.isdigit() else 10**9, v)

            for vid in sorted(view["waiting"] + view["latched"], key=vindex):
                vc = view["victims"][vid]["cell"]
                best = None
                for uid in view["free"]:
                    if uid in used:
                        continue
                    pos = units[uid].pos
                    dist = abs(int(pos[0]) - vc[0]) + abs(int(pos[1]) - vc[1])
                    if best is None or dist < best[0] or (dist == best[0] and uid < best[1]):
                        best = (dist, uid)
                if best is not None:
                    used.add(best[1])
                    pairs.append([vid, best[1]])
            return pairs

        jd_mod = getattr(wf, "_jd", None)

        def _key(u, v):
            return "%s|%s" % (u, v)

        def _cap(fn_name, record):
            """Wrap one pure J function on the module object wildfire_model calls through (WM reads _jd.<f> at
            call time). Records inputs and outputs only while a J call is open; its own time is nested."""
            original = getattr(jd_mod, fn_name)

            def wrapper(*args, **kwargs):
                out = original(*args, **kwargs)
                if rec["in_j"] and rec["j_cur"] is not None:
                    t = time.perf_counter()
                    try:
                        rec["j_cur"]["calls"].append(record(args, kwargs, out))
                    except Exception as exc:
                        err("cap_" + fn_name, exc)
                    rec["nest_ms"] += (time.perf_counter() - t) * 1000.0
                return out

            setattr(jd_mod, fn_name, wrapper)

        def rec_fill(args, kwargs, out):
            units, victims, dist, ledger = args[:4]
            pairs = [(u, v) for u in units for v in victims]
            return {"fn": "solve_fill", "units": list(units), "victims": list(victims),
                    "d": {_key(u, v): dist.get((u, v)) for u, v in pairs},
                    "b": {_key(u, v): int(ledger.get((u, v), 0) or 0) for u, v in pairs
                          if int(ledger.get((u, v), 0) or 0)},
                    "capped": sorted(kwargs.get("capped") or []),
                    "out": [[p.victim, p.unit, p.distance, bool(p.reused)] for p in out]}

        def rec_plan(args, kwargs, out):
            contests, spares, dist, ledger, clean = args[:5]
            vids = [c.victim for c in contests]
            return {"fn": "plan_replacements",
                    "contests": [[c.victim, c.incumbent, c.d, c.k, dict(c.persist)] for c in contests],
                    "spares": list(spares),
                    "d": {_key(b, v): dist.get((b, v)) for b in spares for v in vids},
                    "b": {_key(b, v): int(ledger.get((b, v), 0) or 0) for b in spares for v in vids
                          if int(ledger.get((b, v), 0) or 0)},
                    "clean": {_key(b, v): bool(c) for (b, v), c in clean.items()},
                    "S": kwargs.get("stall_steps"), "P": kwargs.get("margin_persist"),
                    "out": [[r.victim, r.old_unit, r.new_unit, r.cause, r.distance] for r in out]}

        def rec_prog(args, kwargs, out):
            state, d_now, x_now, cell_now, frozen = args[:5]
            key = None
            m = rec["model"]
            for (u, v), st in (getattr(m, "_dispatch_progress", None) or {}).items():
                if st is state:
                    key = [u, v]
                    break
            return {"fn": "progress_step", "binding": key, "d": d_now, "x": x_now, "frozen": bool(frozen),
                    "before": [state.best, state.k, state.d_prev], "after": [out.best, out.k]}

        if jd_mod is not None:
            _cap("solve_fill", rec_fill)
            _cap("plan_replacements", rec_plan)
            _cap("progress_step", rec_prog)

        def jpoint(self, phase):
            if not joint_on():
                return o_jpoint(self, phase)
            t_inst = time.perf_counter()
            view = None
            try:
                view = self._dispatch_view()
                legacy = legacy_pairs(view)
            except Exception as exc:
                err("legacy", exc)
                legacy = None
            try:
                before = {(u, v) for (u, v) in (getattr(self, "_dispatch_progress", None) or {})}
                reassign = bool(getattr(ag, "dispatch_reassign", lambda: False)())
                post = str(phase) == "post"
                contest = dict(view["contest"]) if (view is not None and reassign and post) else {}
                pre = bool(view is not None and ((view["free"] and (view["waiting"] or view["latched"])) or contest))
                cur = {"sets": {"free": list(view["free"]), "waiting": list(view["waiting"]),
                                "latched": list(view["latched"]), "contest": contest} if view is not None else None,
                       "pre": pre, "calls": []}
            except Exception as exc:
                err("jpoint_pre", exc)
                before, contest, pre, cur = set(), {}, False, None
            rec["inst_ms"] += (time.perf_counter() - t_inst) * 1000.0
            n0 = len(getattr(self, "_dispatch_events", None) or [])
            rec["in_j"], rec["j_phase"], rec["j_cur"] = True, str(phase), cur
            rec["nest_ms"], rec["gc_n"] = 0.0, 0
            t0, c0 = time.perf_counter(), time.thread_time()
            try:
                r = o_jpoint(self, phase)
            finally:
                raw = (time.perf_counter() - t0) * 1000.0
                thread_ms = (time.thread_time() - c0) * 1000.0
                rec["in_j"], rec["j_cur"] = False, None
            nest, gcn = rec["nest_ms"], rec["gc_n"]
            ms = max(0.0, raw - nest)
            rec["j_ms"] += ms
            rec["j_raw_ms"] += raw
            try:
                new = (getattr(self, "_dispatch_events", None) or [])[n0:]
                fills = sorted([e.get("victim_id"), e.get("unit")] for e in new
                               if e.get("kind") in ("fill", "latch_fill", "second_fill"))
                entry = [step_of(self), str(phase), round(ms, 3), len(new)]
                if fills or legacy:
                    entry.append({"legacy": sorted(legacy or []), "j_fills": fills})
                rec["j_calls"].append(entry)
                rec["j_timing"].append([step_of(self), str(phase), round(raw, 3), round(ms, 3),
                                        round(thread_ms, 3), gcn])
                if cur is not None and pre:
                    prog = getattr(self, "_dispatch_progress", None) or {}
                    cur["progress"] = {_key(u, v): [s.best, s.k, s.d_prev, list(s.cell_prev), s.age,
                                                     dict(s.persist_map())]
                                       for (u, v), s in prog.items()}
                    evaluated = {tuple(c["binding"]) for c in cur["calls"]
                                 if c.get("fn") == "progress_step" and c.get("binding")}
                    cur["unevaluated"] = sorted([u, v] for v, u in contest.items()
                                                if (u, v) in before and (u, v) not in evaluated)
                    rec["j_detail"].append([step_of(self), str(phase), cur])
            except Exception as exc:
                err("jpoint", exc)
            return r

        WM._joint_dispatch_point = jpoint

    # ------------------------------------------------------------------ post-J sampling
    o_sync = WM._sync_firefighter_marker_status

    def sync(self, *a, **k):
        r = o_sync(self, *a, **k)
        t0 = time.perf_counter()
        try:
            step = step_of(self)
            units = living_units(self)
            vmarkers = getattr(self, "victim_marker_agents", None) or {}
            by_id = {id(mk): str(v) for v, mk in vmarkers.items()}
            bound: dict[str, list] = {}
            for fid, fm in units.items():
                rv = getattr(fm, "rescued_victim", None)
                if rv is not None and id(rv) in by_id:
                    bound.setdefault(by_id[id(rv)], []).append([fid, str(getattr(fm, "status", "") or "")])
            rec["binders"].append([step, sorted([v, sorted(b)] for v, b in bound.items())])
            free = [fid for fid, fm in units.items() if self._firefighter_available_for_dispatch(fm)]
            detected = gen._detected_victim_ids(self)
            ledger = getattr(self, "_dispatch_ledger", None) or {}
            rows = []
            custody_rows = []
            blocked = None
            for vid in sorted(detected):
                mk = vmarkers.get(vid)
                if mk is None or not needy(self, vid, mk):
                    continue
                if any(str(s).lower() != "route_blocked" for _, s in bound.get(vid, [])):
                    continue
                # custody (design 5.2, J's _dispatch_view): a binder exiting, rescue_completed or on the victim's cell
                cell = (int(mk.pos[0]), int(mk.pos[1]))
                if any(getattr(units[f], "exiting", False) or getattr(units[f], "rescue_completed", False)
                       or (units[f].pos is not None and (int(units[f].pos[0]), int(units[f].pos[1])) == cell)
                       for f, _ in bound.get(vid, [])):
                    custody_rows.append(vid)
                    continue
                if blocked is None:
                    blocked = burning_cells(self)
                dmap = _bfs(mk.pos, self.grid, blocked)
                cand = []
                for fid in free:
                    d = _at(dmap, units[fid].pos, blocked)
                    if d is not None:
                        cand.append([fid, d, int(ledger.get((fid, vid), 0) or 0)])
                rows.append([vid, cand])
            rec["waiting"].append([step, len(free), rows])
            if custody_rows:
                rec["waiting_custody"].append([step, custody_rows])
            if rows:
                # M3(a) split (14.7): a free unit is ledger-allowed when it has an allowed pair with SOME waiting
                # victim, whatever d (a fill is uncapped; a latched-held victim's LATCH-FILL needs b <= 1 under
                # Limit 3 only)
                cap = bool(getattr(ag, "dispatch_reassign", lambda: False)())
                held = {v for v, _ in rows if bound.get(v)}
                n_ok = sum(1 for fid in free
                           if any(not (cap and v in held and int(ledger.get((fid, v), 0) or 0) >= 2) for v, _ in rows))
                rec["m3a"].append([step, len(free), n_ok])
            # M9: P post samples after each K13 bind; a J-post bind's own step is not sampled (v closed there)
            still = []
            for item in rec["m9_open"]:
                entry, bind_step, bind_phase = item
                if bind_phase == "post" and bind_step == step:
                    still.append(item)
                    continue
                vm = vmarkers.get(entry[2])
                if vm is None or vm.pos is None:
                    entry[4].append(None)
                else:
                    if blocked is None:
                        blocked = burning_cells(self)
                    dmap = _bfs(vm.pos, self.grid, blocked)
                    entry[4].append(any(_at(dmap, u.pos, blocked) is not None
                                        for u in units.values() if u.pos is not None))
                if len(entry[4]) < 3:
                    still.append(item)
            rec["m9_open"] = still
        except Exception as exc:
            err("sync", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        return r

    WM._sync_firefighter_marker_status = sync

    # ------------------------------------------------------------------ invariant capture
    o_inv = amod._check_rescue_assignment_invariant

    def inv(model):
        buf = io.StringIO()
        real = sys.stderr
        sys.stderr = buf
        try:
            o_inv(model)
        finally:
            # also when the checker raises: its captured lines are re-emitted and kept (R3 finding 20)
            sys.stderr = real
            text = buf.getvalue()
            if text:
                real.write(text)
                try:
                    step = step_of(model)
                    for line in text.splitlines():
                        if line.strip():
                            rec["invariant"].append([step, line.strip()[:300]])
                except Exception as exc:
                    err("inv", exc)

    amod._check_rescue_assignment_invariant = inv

    # ------------------------------------------------------------------ M8 at detection
    o_detect = WM._detect_victims_in_uav_radius

    def detect(self, *a, **k):
        try:
            before = set(gen._detected_victim_ids(self))
        except Exception as exc:
            err("detect_pre", exc)
            before = None
        r = o_detect(self, *a, **k)
        t0 = time.perf_counter()
        try:
            if before is not None:
                new = sorted(set(gen._detected_victim_ids(self)) - before)
                for vid in new:
                    mk = (self.victim_marker_agents or {}).get(vid)
                    if mk is None or mk.pos is None or vid in rec["m8"]:
                        continue
                    cell = (int(mk.pos[0]), int(mk.pos[1]))
                    blocked = burning_cells(self)
                    dmap = _bfs(cell, self.grid, blocked)
                    ds = [_at(dmap, u.pos, blocked) for u in living_units(self).values() if u.pos is not None]
                    ds = [d for d in ds if d is not None]
                    t_fire = None
                    try:
                        from src_extension.planning import fire_arrival_estimate as fae
                        burning, _smoke = self._fix3b_true_fire()
                        wind = cfv.wind_vector_from_direction(getattr(getattr(self, "wind", None), "wind_direction", None))
                        grid_t = fae.arrival_time(int(self.grid.width), int(self.grid.height), set(burning), wind,
                                                  fae.front_priority_params())
                        value = float(grid_t[cell[0], cell[1]])
                        t_fire = None if value == float("inf") else round(value, 3)
                    except Exception as exc:
                        err("m8_tfire", exc)
                    rec["m8"][vid] = {"victim": vid, "detection_step": step_of(self), "cell": list(cell),
                                      "t_fire": t_fire, "min_d": min(ds) if ds else None,
                                      "first_burn_step": None, "death_step": None}
        except Exception as exc:
            err("detect", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        return r

    WM._detect_victims_in_uav_radius = detect

    # ------------------------------------------------------------------ per step: model capture, M8 follow-up
    o_step = WM.step

    def step(self, *a, **k):
        rec["model"] = self
        r = o_step(self, *a, **k)
        t0 = time.perf_counter()
        try:
            if rec["m8"]:
                burning = None
                for vid, e in rec["m8"].items():
                    if e["first_burn_step"] is None:
                        if burning is None:
                            burning = burning_cells(self)
                        if tuple(e["cell"]) in burning:
                            e["first_burn_step"] = step_of(self)
                    if e["death_step"] is None:
                        mk = (self.victim_marker_agents or {}).get(vid)
                        state = (self.managed_victims or {}).get(vid)
                        ms = str(getattr(mk, "status", "") or "").lower() if mk is not None else ""
                        ss = str(getattr(state, "status", "") or "").lower() if state is not None else ""
                        if "dead" in (ms, ss):
                            e["death_step"] = step_of(self)
        except Exception as exc:
            err("step", exc)
        rec["inst_ms"] += (time.perf_counter() - t0) * 1000.0
        return r

    WM.step = step

    # ------------------------------------------------------------------ run the chain
    # A record already at --out (an earlier attempt's) is moved aside, never written into: the dp section below
    # must belong to THIS run's JSON (R3 finding 20). The moved copy is kept (21.2(j): crashed records are kept).
    if os.path.exists(out_path):
        n = 0
        while os.path.exists("%s.prev%d" % (out_path, n)):
            n += 1
        os.replace(out_path, "%s.prev%d" % (out_path, n))
    rc = None
    chain_exc = None
    try:
        ut = runpy.run_path(os.path.join(HERE, "_ut_probe.py"), run_name="ut_probe_module")
        sys.argv = [os.path.join(HERE, "_ut_probe.py")] + argv
        rc = ut["main"]()
    except BaseException as exc:  # noqa: BLE001 - the dp record is written whatever happened (14.4)
        chain_exc = exc
        rc = 9
        print("DP CHAIN RAISED %r" % (exc,), file=sys.stderr)
    finally:
        try:
            gc.callbacks.remove(gc_cb)
        except ValueError:
            pass

    try:
        m = rec["model"]
        shas = {}
        for rel in SHA_FILES:
            path = os.path.join(repo, rel)
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    shas[rel] = hashlib.sha256(fh.read()).hexdigest()
        ledger = getattr(m, "_dispatch_ledger", None) or {} if m is not None else {}
        dp = {
            "probe": "dp_probe v1",
            "rc_chain": rc,
            "chain_exception": repr(chain_exc) if chain_exc is not None else None,
            "switches": {
                "DISPATCH_JOINT": repr(getattr(cfv, "DISPATCH_JOINT", None)),
                "DISPATCH_REASSIGN": repr(getattr(cfv, "DISPATCH_REASSIGN", None)),
                "joint_on": bool(getattr(ag, "dispatch_joint", lambda: False)()),
                "reassign_on": bool(getattr(ag, "dispatch_reassign", lambda: False)()),
                "S": getattr(ag, "dispatch_stall_steps", lambda: None)(),
                "M": getattr(ag, "dispatch_margin_steps", lambda: None)(),
                "P": getattr(ag, "dispatch_margin_persist", lambda: None)(),
            },
            "src_sha": shas,
            "commands": rec["commands"],
            "releases": rec["releases"],
            "j_calls": rec["j_calls"],
            "j_events": list(getattr(m, "_dispatch_events", None) or []) if m is not None else [],
            "ledger": {f"{u}|{v}": int(b) for (u, v), b in ledger.items()},
            "binders": rec["binders"],
            "waiting": rec["waiting"],
            "waiting_custody": rec["waiting_custody"],
            "m3a": rec["m3a"],
            "invariant": rec["invariant"],
            "m8": sorted(rec["m8"].values(), key=lambda e: e["victim"]),
            "m9": rec["m9"],
            "j_detail": rec["j_detail"],
            "j_timing": rec["j_timing"],
            "writeoffs_avoided": list(getattr(m, "dispatch_writeoffs_avoided", None) or []) if m is not None else [],
            "timing": {"j_ms_total": round(rec["j_ms"], 3), "j_ms_raw_total": round(rec["j_raw_ms"], 3),
                       "inst_ms_total": round(rec["inst_ms"], 3)},
            "errors": rec["errors"],
        }
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as fh:
                d = json.load(fh)
        else:
            d = {"dp_only": True, "crashed": True}
        d["dp"] = dp
        tmp = out_path + ".dptmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"), default=str)
        os.replace(tmp, out_path)
    except Exception as exc:
        print("DP WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 8
    return rc


if __name__ == "__main__":
    sys.exit(main())
