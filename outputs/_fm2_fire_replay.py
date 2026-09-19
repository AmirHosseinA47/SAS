"""firemech round 2 - FIRE-ONLY OFFLINE REPLAY instrument. Out of tree, read-only on sources.

Replays the fire of one recorded harness run (outputs/_ffr_<tag>_<wind>_<rr>_<seed>.json)
WITHOUT simulating UAVs, victims or firefighters, applying a chosen subset of the run's own
recorded fire writes (firefight_log rows with wrote True). Single-write ablations of a
closed-loop arm then cost one fire replay instead of one full simulation.

WHY IT IS EXACT (established from the source; checked by --batch validate)
  * Construction is outputs/_ffr_harness.py main() verbatim: same import order, params dict
    (scenario preset, _resolve_role_count_params, BATCH_SIZE 300, FIRE_SPREAD_MULTIPLIER
    0.75, PROBABILITY_MAP False) + the arm's extra_params, rng = random.Random(seed) bound
    to cfv.SYSTEM_RANDOM / wf.SYSTEM_RANDOM / agents.random, apply_scenario_config, then
    WildFireModel() under redirect_stdout and debug_log = False. The recorded params dict
    is asserted equal to the rebuilt one.
  * After construction the shared rng is drawn ONLY by Fire.step (one random.random() per
    non-burnt cell per fire tick; Wind.change_direction is dead because FIXED_WIND is
    True). The only other per-step draw site in the tree, WildFireModel.
    _prepare_uav_directions_for_step, returns before drawing whenever decision_dispatcher
    is set, and __init__ always sets it. No module under src_extension references random.
  * Fire state is written only by Fire.step / Fire.advance and by Firefighter.
    _firefight_execute (firefighter_extinguish / firefighter_remove_fuel), which runs in
    Firefighter.advance, after every Fire.advance (Fire agents are added to the schedule
    first). probability_of_fire reads only Fire agents on the grid, so the positions of
    other agents are irrelevant. Fire.step keeps its own steps_counter (== model step).
  * So one replay step t is: every Fire .step() in schedule order, every Fire .advance(),
    then the selected writes whose log step == t in log order (log step is
    evaluation_timesteps_counter during that model.step(), i.e. t), then the harness's
    digest.

LIMIT (by construction): the write SCHEDULE is held fixed (open loop). In the closed loop a
unit would react to a changed fire; a replay answers "what does this fire do if exactly
these writes land at these cells and steps". A selected write whose cell no longer
qualifies (e.g. not burning any more) returns False and writes nothing; it is counted.

usage
  replay : _fm2_fire_replay.py --arm-json PATH [--writes SPEC] [--crn] [--steps N] --out OUT.json
           SPEC = all | none | only-first | drop-first | prefix:N | only:i | drop:i
                  (indices over the wrote-True rows of firefight_log, in log order)
           --crn  Fire.step's draw becomes crn_uniform(seed, uid, steps_counter) from
                  outputs/_fm2_probe_harness.py, installed as that file does it (source
                  rewrite of the one draw line, globals = the agents module dict). NOTE: a
                  stock arm's recorded extinguish usually does not land on a CRN fire (the
                  cell is not burning there); use it with writes recorded by a CRN arm.
           --record-draws FILE  stock draws (same order and values) also saved per (tick,
                  cell) as float64, NaN = no draw (burnt at that step).
           --pin-draws FILE     every cell that drew at a tick in the recorded run draws
                  exactly that value again; a cell that did not draw there gets
                  crn_uniform(seed, uid, steps_counter). The draw-stream re-roll is off, so a
                  write acts only physically on the recorded fire (validated: a pinned no-write
                  replay == fmOFF 240/240, and pinned single writes never leave the cone).
  compare: _fm2_fire_replay.py --compare A.json B.json [--json OUT.json]
           A / B are replay outputs or harness JSONs (burning sets from burn_intervals).
           Reports first digest divergence, the light cone of the earliest differing write
           (Chebyshev <= radius x fire ticks elapsed since that write; a tick is a step with
           steps_counter % FIRE_SPREAD_SPEED == 0, and a write at a tick step lands after
           that tick's advance so it counts from the next one), the first step a burning
           difference leaves the cone, and - for two replays - the first shift of the shared
           draw stream (first differing burnt set; it shifts draws from the next tick on).
  batch  : _fm2_fire_replay.py --batch validate|study-canonical|study-fresh|pinned-canonical|
                                       pinned-fresh|crn-check --outdir DIR [--jobs 2]
           (study-* = fmOFF none with --record-draws per tuple, then only-first and drop-first
           for every fmES tuple with >= 1 extinguish and fmF tuple with >= 1 clear; pinned-* =
           only-first with --pin-draws of that tuple's recorded no-write draws)
           runs replays as subprocesses, at most --jobs (<= 2) at once, each start gated on
           FreeVirtualMemory >= 4000000 kB. Existing complete outputs are reused.
  report : _fm2_fire_replay.py --report validate|study|crn-check --outdir DIR
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import inspect
import io as _io
import json
import os
import random
import subprocess
import sys
import textwrap
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DEFAULT = os.path.dirname(HERE)
PY = os.path.join(REPO_DEFAULT, ".venv", "Scripts", "python.exe")
CELLS = 2500
MIN_FREE_KB = 4000000
NL = chr(10)


# ============================================================================ replay ===
def _select_writes(rows, spec):
    n = len(rows)
    idx = list(range(n))
    if spec == "all":
        return idx
    if spec == "none":
        return []
    if spec == "only-first":
        return idx[:1]
    if spec == "drop-first":
        return idx[1:]
    kind, _, arg = spec.partition(":")
    if kind == "prefix":
        return idx[:int(arg)]
    if kind == "only":
        i = int(arg)
        if not 0 <= i < n:
            raise SystemExit("only:%d out of range (%d writes)" % (i, n))
        return [i]
    if kind == "drop":
        i = int(arg)
        if not 0 <= i < n:
            raise SystemExit("drop:%d out of range (%d writes)" % (i, n))
        return [j for j in idx if j != i]
    raise SystemExit("bad --writes %r" % spec)


def _install_draw(am, draw):
    """Replace Fire.step's single draw line by draw(self) - the probe harness's install."""
    src = textwrap.dedent(inspect.getsource(am.Fire.step))
    needle = "generated = random.random()"
    if src.count(needle) != 1:
        raise SystemExit("Fire.step draw line not found exactly once - refusing to run")
    body = src.replace(needle, "generated = _fm2p_draw(self)")
    factory = "def _fm2p_make(_fm2p_draw):\n" + textwrap.indent(body, "    ") + "    return step\n"
    ns: dict = {}
    exec(compile(factory, "<fm2 replay Fire.step>", "exec"), am.__dict__, ns)
    patched = ns["_fm2p_make"](draw)
    patched.__qualname__ = am.Fire.step.__qualname__
    am.Fire.step = patched


def _install_crn(am, seed, crn_uniform, counter):
    def _draw(fire):
        counter[0] += 1
        return crn_uniform(seed, fire.unique_id, fire.steps_counter)

    _install_draw(am, _draw)


def run_replay(args) -> int:
    t_start = time.perf_counter()
    with open(args.arm_json, encoding="utf-8") as f:
        arm = json.load(f)
    repo = os.path.abspath(args.repo)
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")

    # ---- imports in the harness's order
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config  # noqa: E402
    from wildfire_model import WildFireModel  # noqa: E402
    from serve_dashboard import BUILTIN_SCENARIOS, _resolve_role_count_params  # noqa: E402
    for mod in (am, cfv, wf):
        p = os.path.abspath(getattr(mod, "__file__", ""))
        if not p.lower().startswith(repo.lower()):
            print("IMPORT MISMATCH: %s from %s" % (mod.__name__, p), file=sys.stderr)
            return 3

    wind, roles, seed = str(arm["wind"]), str(arm["roles"]), int(arm["seed"])
    scenario = str(arm.get("scenario", "D"))
    steps = int(args.steps if args.steps else arm.get("steps", 240))
    preset = BUILTIN_SCENARIOS.get(scenario, {})
    num_agents = int(preset.get("NUM_AGENTS", 3))
    if roles == "half":
        ft, vs = _resolve_role_count_params(num_agents, 2, 2)
    else:
        ft, vs = _resolve_role_count_params(num_agents, None, None)
    params = {
        "NUM_AGENTS": num_agents,
        "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
        "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)),
        "WIND_DIRECTION": wind,
        "BATCH_SIZE": 300,
        "FIRE_SPREAD_MULTIPLIER": 0.75,
        "PROBABILITY_MAP": False,
        "NUM_FIRE_TRACKERS": ft,
        "NUM_VICTIM_SEARCHERS": vs,
    }
    extra = dict(arm.get("extra_params") or {})
    params.update(extra)
    if json.loads(json.dumps(params)) != arm.get("params"):
        print("PARAMS MISMATCH rebuilt %r vs recorded %r" % (params, arm.get("params")), file=sys.stderr)
        return 5

    rows = [r for r in (arm.get("firefight_log") or []) if r.get("wrote")]
    for r in rows:
        if r["action"] not in ("extinguish", "clear"):
            raise SystemExit("unexpected wrote row action %r" % r["action"])
    sel = _select_writes(rows, args.writes)
    by_step: dict = {}
    for i in sel:
        by_step.setdefault(int(rows[i]["step"]), []).append(i)

    crn_draws = [0]
    modes = sum(1 for m in (args.crn, args.record_draws, args.pin_draws) if m)
    if modes > 1:
        raise SystemExit("--crn, --record-draws and --pin-draws are mutually exclusive")
    if args.crn:
        sys.path.insert(0, HERE)
        from _fm2_probe_harness import crn_uniform  # noqa: E402
        _install_crn(am, seed, crn_uniform, crn_draws)
    # --record-draws: the draw is still rng.random(), same order, same values (the digest
    # match vs the arm proves it); each value is stored at (tick, fire index).
    # --pin-draws: every cell that drew at a tick in the recorded run gets exactly that value
    # again, whatever else changed; a cell that did not draw there (burnt in the recorded run,
    # not here) gets crn_uniform(seed, uid, steps_counter). Nothing depends on the shared
    # stream any more, so a write can change the fire only physically - the stock fire world
    # with the draw-stream re-roll switched off.
    draw_state = {"index": None, "speed": None, "vals": None, "fallback": 0, "pinned": 0}
    if args.record_draws or args.pin_draws:
        from array import array
        sys.path.insert(0, HERE)
        from _fm2_probe_harness import crn_uniform  # noqa: E402

        if args.record_draws:
            def _draw(fire):
                v = am.random.random()
                k = fire.steps_counter // draw_state["speed"] - 1
                draw_state["vals"][k * draw_state["n"] + draw_state["index"][fire.unique_id]] = v
                return v
        else:
            def _draw(fire):
                k = fire.steps_counter // draw_state["speed"] - 1
                pos = k * draw_state["n"] + draw_state["index"][fire.unique_id]
                vals = draw_state["vals"]
                v = vals[pos] if pos < len(vals) else float("nan")
                if v != v:
                    draw_state["fallback"] += 1
                    return crn_uniform(seed, fire.unique_id, fire.steps_counter)
                draw_state["pinned"] += 1
                return v
        _install_draw(am, _draw)

    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    buf = _io.StringIO()
    t_build = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
    t_built = time.perf_counter()

    fires = [a for a in model.schedule.agents if type(a).__name__ == "Fire"]
    fire_at = {(int(a.pos[0]), int(a.pos[1])): a for a in fires}
    index_of = {id(a): i for i, a in enumerate(fires)}
    spread_speed = int(getattr(am, "FIRE_SPREAD_SPEED"))
    radius = int(fires[0].radius)
    moore = bool(fires[0].moore)
    torus = bool(getattr(model.grid, "torus", False))
    rng_state_after_build = hashlib.sha256(repr(rng.getstate()).encode()).hexdigest()
    if args.record_draws or args.pin_draws:
        draw_state["index"] = {a.unique_id: i for i, a in enumerate(fires)}
        draw_state["speed"] = spread_speed
        draw_state["n"] = len(fires)
        n_ticks = steps // spread_speed
        if args.record_draws:
            draw_state["vals"] = array("d", [float("nan")]) * (n_ticks * len(fires))
        else:
            vals = array("d")
            with open(args.pin_draws, "rb") as f:
                vals.frombytes(f.read())
            if len(vals) != n_ticks * len(fires):
                raise SystemExit("pin-draws file has %d values, expected %d" % (len(vals), n_ticks * len(fires)))
            draw_state["vals"] = vals

    digests, burning_count, on_list, off_list, burnt_new = [], [], [], [], []
    applied = {}
    failures = []
    prev_burning = set(i for i, a in enumerate(fires) if a.burning)
    initial_burning = sorted(prev_burning)
    prev_burnt = set(i for i, a in enumerate(fires) if a.burnt)
    counter_bad = 0
    draws_per_tick = []
    with contextlib.redirect_stdout(buf):
        for t in range(1, steps + 1):
            model.evaluation_timesteps_counter = t
            for a in fires:
                a.step()
            for a in fires:
                a.advance()
            if t % spread_speed == 0:
                draws_per_tick.append([t, sum(1 for i in range(len(fires)) if i not in prev_burnt)])
            for i in by_step.get(t, ()):
                r = rows[i]
                cell = (int(r["target"][0]), int(r["target"][1]))
                fire = fire_at.get(cell)
                ok = False
                if fire is not None:
                    ok = fire.firefighter_extinguish() if r["action"] == "extinguish" else fire.firefighter_remove_fuel()
                applied[i] = bool(ok)
                if not ok:
                    failures.append([i, t, r["action"], list(cell)])
            parts = []
            burning_now = set()
            burnt_now = set()
            for k, a in enumerate(fires):
                parts.append("%s:%d%d%s" % (a.unique_id, int(bool(a.burning)), int(bool(a.burnt)), a.fuel))
                if a.burning:
                    burning_now.add(k)
                if a.burnt:
                    burnt_now.add(k)
                if a.steps_counter != t:
                    counter_bad += 1
            digests.append(hashlib.sha256("|".join(parts).encode()).hexdigest())
            burning_count.append(len(burning_now))
            on_list.append(sorted(burning_now - prev_burning))
            off_list.append(sorted(prev_burning - burning_now))
            burnt_new.append(sorted(burnt_now - prev_burnt))
            prev_burning, prev_burnt = burning_now, burnt_now
    t_done = time.perf_counter()

    rec = arm.get("fire_digests") or []
    n_cmp = min(len(rec), len(digests))
    matched = sum(1 for k in range(n_cmp) if rec[k] == digests[k])
    first_mm = next((k + 1 for k in range(n_cmp) if rec[k] != digests[k]), None)
    ever = [k for k, a in enumerate(fires) if a.has_burned]
    cleared = [k for k, a in enumerate(fires) if a.fuel <= 0 and not a.has_burned]
    out = {
        "tool": "_fm2_fire_replay", "version": 1,
        "arm_json": os.path.abspath(args.arm_json), "arm_tag": arm.get("tag"),
        "wind": wind, "roles": roles, "seed": seed, "scenario": scenario, "steps": steps,
        "extra_params": extra, "writes_spec": args.writes, "crn": bool(args.crn),
        "spread_speed": spread_speed, "radius": radius, "moore": moore, "torus": torus,
        "n_fire": len(fires),
        "fires": [[int(a.unique_id), int(a.pos[0]), int(a.pos[1])] for a in fires],
        "rng_state_after_build_sha": rng_state_after_build,
        "initial_burning": initial_burning,
        "digests": digests,
        "burning_count": burning_count,
        "burning_on": on_list, "burning_off": off_list, "burnt_new": burnt_new,
        "draws_per_tick": draws_per_tick,
        "crn_draws": crn_draws[0] if args.crn else None,
        "writes_total": len(rows),
        "writes_selected": [
            {"i": i, "step": int(rows[i]["step"]), "ff": rows[i].get("ff"), "action": rows[i]["action"],
             "cell": [int(rows[i]["target"][0]), int(rows[i]["target"][1])], "applied": applied.get(i)}
            for i in sel
        ],
        "writes_failed": failures,
        "steps_counter_mismatches": counter_bad,
        "final": {
            "ever": len(ever), "cleared": len(cleared), "intact": CELLS - len(ever) - len(cleared),
            "burnt": sum(1 for a in fires if a.burnt), "burning": sum(1 for a in fires if a.burning),
        },
        "final_has_burned": ever, "final_cleared": cleared,
        "digest_vs_arm": {"compared": n_cmp, "matched": matched, "first_mismatch": first_mm,
                          "meaningful": (not args.crn and not args.pin_draws)
                          and (args.writes == "all" or (args.writes == "none" and not rows))},
        "wall_s": {"construct": round(t_built - t_build, 2), "replay": round(t_done - t_built, 2),
                   "total": round(t_done - t_start, 2)},
        "stdout_lines": buf.getvalue().count("\n"),
    }
    out["record_draws"] = os.path.abspath(args.record_draws) if args.record_draws else None
    out["pin_draws"] = os.path.abspath(args.pin_draws) if args.pin_draws else None
    out["pin_counts"] = ({"pinned": draw_state["pinned"], "fallback": draw_state["fallback"]}
                         if args.pin_draws else None)
    if args.record_draws:
        tmpd = args.record_draws + ".tmp"
        with open(tmpd, "wb") as f:
            f.write(draw_state["vals"].tobytes())
        os.replace(tmpd, args.record_draws)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f)
    os.replace(tmp, args.out)
    print("replay %s %s/%s/%d writes=%s crn=%s selected=%d failed=%d digest %d/%d first_mm=%s "
          "ever=%d cleared=%d intact=%d counter_bad=%d wall construct %.1fs replay %.1fs total %.1fs" % (
              arm.get("tag"), wind, roles, seed, args.writes, bool(args.crn), len(sel), len(failures),
              matched, n_cmp, first_mm, len(ever), len(cleared), CELLS - len(ever) - len(cleared), counter_bad,
              t_built - t_build, t_done - t_built, t_done - t_start))
    if args.writes == "all" and failures:
        print("ASSERTION: %d selected writes returned False under writes=all: %s" % (len(failures), failures[:5]),
              file=sys.stderr)
        return 4
    return 0


# =========================================================================== compare ===
def load_trace(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    T = {"path": path}
    if d.get("tool") == "_fm2_fire_replay":
        cells = [(c[1], c[2]) for c in d["fires"]]
        T["kind"] = "replay"
        T["uid_of"] = {(c[1], c[2]): c[0] for c in d["fires"]}
        T["digests"] = d["digests"]
        cur = set(cells[i] for i in d["initial_burning"])
        burning = []
        for on, off in zip(d["burning_on"], d["burning_off"]):
            cur = (cur - set(cells[i] for i in off)) | set(cells[i] for i in on)
            burning.append(frozenset(cur))
        T["burning"] = burning
        cum, burnt = set(), []
        for new in d["burnt_new"]:
            cum = cum | set(cells[i] for i in new)
            burnt.append(frozenset(cum))
        T["burnt"] = burnt
        T["writes"] = set((w["step"], tuple(w["cell"]), w["action"]) for w in d["writes_selected"] if w["applied"])
        T["final"] = dict(d["final"])
        T["has_burned"] = set(cells[i] for i in d["final_has_burned"])
        T["spread_speed"], T["radius"] = d["spread_speed"], d["radius"]
        T["label"] = "%s %s/%s/%d writes=%s%s" % (d.get("arm_tag"), d["wind"], d["roles"], d["seed"],
                                                  d["writes_spec"], " crn" if d["crn"] else "")
    else:
        T["kind"] = "harness"
        T["uid_of"] = None
        T["digests"] = d["fire_digests"]
        steps = len(d["fire_digests"])
        sets = [set() for _ in range(steps)]
        for key, ivs in (d.get("burn_intervals") or {}).items():
            x, y = (int(v) for v in key.split(","))
            for a, b in ivs:
                for s in range(a, (steps + 1 if b is None else b)):
                    sets[s - 1].add((x, y))
        T["burning"] = [frozenset(s) for s in sets]
        T["burnt"] = None
        T["writes"] = set((r["step"], (int(r["target"][0]), int(r["target"][1])), r["action"])
                          for r in (d.get("firefight_log") or []) if r.get("wrote"))
        fgf = d.get("fire_ground_final") or {}
        ever = sum(1 for v in fgf.values() if v[0])
        cleared = int(d.get("fire_cleared_unburned_final") or 0)
        T["final"] = {"ever": ever, "cleared": cleared, "intact": CELLS - ever - cleared,
                      "burnt": sum(1 for v in fgf.values() if v[1]), "burning": sum(1 for v in fgf.values() if v[2])}
        T["has_burned"] = set(tuple(int(v) for v in k.split(",")) for k, v in fgf.items() if v[0])
        T["spread_speed"], T["radius"] = 3, 3
        T["label"] = "harness %s %s/%s/%d" % (d.get("tag"), d["wind"], d["roles"], d["seed"])
    return T


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def compare(A, B):
    R = {"a": A["label"], "b": B["label"]}
    n = min(len(A["digests"]), len(B["digests"]))
    R["digest_matched"] = sum(1 for k in range(n) if A["digests"][k] == B["digests"][k])
    R["digest_compared"] = n
    R["first_digest_div"] = next((k + 1 for k in range(n) if A["digests"][k] != B["digests"][k]), None)
    diffw = sorted(A["writes"] ^ B["writes"])
    R["n_differing_writes"] = len(diffw)
    speed, radius = A["spread_speed"], A["radius"]
    t0 = diffw[0][0] if diffw else None
    sources = sorted(set(w[1] for w in diffw if w[0] == t0)) if diffw else []
    R["cone_t0"], R["cone_sources"] = t0, [list(c) for c in sources]
    R["cone_covers_grid_step"] = None
    if sources:
        far = max(min(cheb((x, y), src) for src in sources) for x in range(50) for y in range(50))
        need_ticks = -(-far // radius)
        # the tick count reaches need_ticks at the need_ticks-th tick step after t0
        R["cone_covers_grid_step"] = (t0 // speed + need_ticks) * speed
        R["cone_far"] = far
    first_burn_diff = None
    first_out = None
    out_info = None
    pre_t0_diff = 0
    for k in range(min(len(A["burning"]), len(B["burning"]))):
        s = k + 1
        D = A["burning"][k] ^ B["burning"][k]
        if D and first_burn_diff is None:
            first_burn_diff = s
        if not D:
            continue
        if t0 is None or s < t0:
            pre_t0_diff += 1
            continue
        if first_out is None:
            r = radius * (s // speed - t0 // speed)
            outs = []
            for c in D:
                dmin = min(cheb(c, src) for src in sources)
                if dmin > r:
                    outs.append((dmin, c))
            if outs:
                first_out = s
                outs.sort()
                out_info = {"step": s, "cone_radius": r, "n_outside": len(outs), "n_diff": len(D),
                            "max_dist": outs[-1][0], "min_dist": outs[0][0], "example": list(outs[-1][1])}
    R["first_burning_diff"] = first_burn_diff
    R["steps_with_burning_diff_before_t0"] = pre_t0_diff
    R["first_out_of_cone"] = first_out
    R["out_of_cone"] = out_info
    if A["burnt"] is not None and B["burnt"] is not None:
        fb = next((k + 1 for k in range(min(len(A["burnt"]), len(B["burnt"]))) if A["burnt"][k] != B["burnt"][k]), None)
        R["first_burnt_set_diff"] = fb
        if fb is not None:
            D = A["burnt"][fb - 1] ^ B["burnt"][fb - 1]
            uid_of = A["uid_of"]
            R["stream_shift_tick"] = (fb // speed + 1) * speed
            R["stream_shift_min_uid"] = min(uid_of[c] for c in D)
            R["stream_shift_cells"] = [list(c) for c in sorted(D)][:10]
        else:
            R["stream_shift_tick"] = None
    fa, fbb = A["final"], B["final"]
    R["final_a"], R["final_b"] = fa, fbb
    R["delta_intact_a_minus_b"] = fa["intact"] - fbb["intact"]
    R["delta_ever_a_minus_b"] = fa["ever"] - fbb["ever"]
    HB = A["has_burned"] ^ B["has_burned"]
    R["final_has_burned_symdiff"] = len(HB)
    if sources:
        dists = [min(cheb(c, src) for src in sources) for c in HB]
        R["symdiff_dist_buckets"] = {
            "<=3": sum(1 for x in dists if x <= 3), "4-10": sum(1 for x in dists if 4 <= x <= 10),
            "11-20": sum(1 for x in dists if 11 <= x <= 20), ">20": sum(1 for x in dists if x > 20)}
        R["symdiff_max_dist"] = max(dists) if dists else None
    return R


def run_compare(args) -> int:
    A, B = load_trace(args.compare[0]), load_trace(args.compare[1])
    R = compare(A, B)
    print(json.dumps(R, indent=1))
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(R, f, indent=1)
    return 0


# ============================================================================= batch ===
def arm_path(tag, wind, rr, seed):
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])

VALIDATE_JOBS = (
    [("fmOFF", t, "none") for t in (("east", "half", 101), ("south", "half", 404), ("east", "def", 202),
                                    ("south", "half", 909))]
    + [("fmES", t, "all") for t in (("east", "half", 101), ("south", "half", 404), ("east", "def", 202))]
    + [("fmF", t, "all") for t in (("east", "half", 404), ("south", "half", 404), ("east", "def", 303))]
    + [("fmEFS", t, "all") for t in (("south", "half", 303), ("east", "def", 101), ("south", "half", 505))]
)
CRN_CHECK = [("fmF", ("east", "half", 404), "none", "crn"), ("fmF", ("east", "half", 404), "only-first", "crn"),
             ("fmES", ("east", "half", 101), "none", "crn"), ("fmES", ("east", "half", 101), "only-first", "crn"),
             ("fmOFF", ("east", "half", 101), "none", "pin")]


def out_name(outdir, tag, t, spec, mode=""):
    """mode: "" stock | "rec" stock + draws recorded (same name) | "crn" | "pin" (draws of fmOFF none)."""
    suffix = {"": "", "rec": "", "crn": "_crn", "pin": "_pin"}[mode or ""]
    return os.path.join(outdir, "rp_%s_%s_%s_%d_%s%s.json" % (tag, t[0], t[1], t[2], spec.replace(":", "-"), suffix))


def draws_name(outdir, t):
    return out_name(outdir, "fmOFF", t, "none")[:-5] + ".draws"


def n_writes(tag, t, action):
    with open(arm_path(tag, *t), encoding="utf-8") as f:
        d = json.load(f)
    return sum(1 for r in (d.get("firefight_log") or []) if r.get("wrote") and r["action"] == action)


def study_tuples(tuples):
    out = []
    for tag, action in (("fmES", "extinguish"), ("fmF", "clear")):
        for t in tuples:
            if n_writes(tag, t, action) >= 1:
                out.append((tag, t))
    return out


def study_jobs(tuples):
    jobs = []
    need_none = []
    for tag, t in study_tuples(tuples):
        jobs.append((tag, t, "only-first", ""))
        jobs.append((tag, t, "drop-first", ""))
        if t not in need_none:
            need_none.append(t)
    # one stock no-write replay per tuple (== fmOFF fire), recording its draws: gives the burnt
    # timing the harness JSON does not record (draw-stream shift) and the values --pin-draws uses
    return [("fmOFF", t, "none", "rec") for t in need_none] + jobs


def pinned_jobs(tuples):
    return [(tag, t, "only-first", "pin") for tag, t in study_tuples(tuples)]


def free_kb():
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory"],
                           capture_output=True, text=True, timeout=60)
        return int(r.stdout.strip().splitlines()[-1])
    except Exception:
        return -1


def job_done(outdir, j):
    tag, t, spec, mode = j
    if not os.path.exists(out_name(outdir, tag, t, spec, mode)):
        return False
    if mode == "rec" and not os.path.exists(draws_name(outdir, t)):
        return False
    return True


def run_batch(args) -> int:
    os.makedirs(args.outdir, exist_ok=True)
    jobs = []
    if args.batch == "validate":
        jobs = [(tag, t, spec, "") for tag, t, spec in VALIDATE_JOBS]
    elif args.batch == "study-canonical":
        jobs = study_jobs(CANON)
    elif args.batch == "study-fresh":
        jobs = study_jobs(FRESH)
    elif args.batch == "pinned-canonical":
        jobs = pinned_jobs(CANON)
    elif args.batch == "pinned-fresh":
        jobs = pinned_jobs(FRESH)
    elif args.batch == "crn-check":
        jobs = list(CRN_CHECK)
    jobs_n = max(1, min(2, int(args.jobs)))
    log = open(os.path.join(args.outdir, "batch_%s.log" % args.batch), "a", encoding="utf-8", newline=NL)

    def say(msg):
        line = time.strftime("%H:%M:%S ") + msg
        print(line, flush=True)
        log.write(line + NL)
        log.flush()

    pending = [j for j in jobs if not job_done(args.outdir, j)]
    say("batch %s: %d jobs, %d to run, jobs=%d" % (args.batch, len(jobs), len(pending), jobs_n))
    running = []
    t0 = time.time()
    while pending or running:
        for p, j, ts, errf in list(running):
            if p.poll() is not None:
                errf.close()
                running.remove((p, j, ts, errf))
                say("done rc=%s %.0fs %s" % (p.returncode, time.time() - ts, out_name(args.outdir, *j)))
        if pending and len(running) < jobs_n:
            if pending[0][3] == "pin" and not os.path.exists(draws_name(args.outdir, pending[0][1])):
                say("SKIP (no recorded draws) %s" % (pending[0],))
                pending.pop(0)
                continue
            fk = free_kb()
            if fk < MIN_FREE_KB:
                say("free commit %d kB < %d, waiting" % (fk, MIN_FREE_KB))
                time.sleep(20)
                continue
            j = pending.pop(0)
            tag, t, spec, mode = j
            out = out_name(args.outdir, tag, t, spec, mode)
            cmd = [PY, os.path.abspath(__file__), "--arm-json", arm_path(tag, *t), "--writes", spec, "--out", out]
            if mode == "crn":
                cmd.append("--crn")
            elif mode == "rec":
                cmd += ["--record-draws", draws_name(args.outdir, t)]
            elif mode == "pin":
                cmd += ["--pin-draws", draws_name(args.outdir, t)]
            errf = open(out[:-5] + ".log", "w", encoding="utf-8", newline=NL)
            p = subprocess.Popen(cmd, stdout=errf, stderr=subprocess.STDOUT, cwd=REPO_DEFAULT)
            running.append((p, j, time.time(), errf))
            say("start (free %d kB) %s" % (fk, " ".join(cmd[2:])))
            continue
        time.sleep(2)
    say("batch %s finished in %.0fs" % (args.batch, time.time() - t0))
    log.close()
    return 0


# ============================================================================ report ===
def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def report_validate(args):
    sys.path.insert(0, HERE)
    import _firemech_analyze as FA  # noqa: E402
    print("VALIDATION  (digest match vs the arm JSON's fire_digests; final state vs _firemech_analyze.run_summary)")
    print("  %-6s %-16s %-6s %7s %6s %4s %6s %6s %s | %-24s | %s | %s" % (
        "arm", "tuple", "writes", "digest", "sel", "fail", "ctrbad", "wall", "(construct+replay)",
        "replay ever/cleared/intact", "analyzer ever/cleared/intact", "same"))
    walls = []
    for tag, t, spec in VALIDATE_JOBS:
        p = out_name(args.outdir, tag, t, spec)
        if not os.path.exists(p):
            print("  %-6s %s MISSING" % (tag, t))
            continue
        r = _load(p)
        d = _load(arm_path(tag, *t))
        S = FA.run_summary(d, None)
        fr = r["final"]
        same = (fr["ever"], fr["cleared"], fr["intact"]) == (S["ever"], S["cleared"], S["intact"])
        dv = r["digest_vs_arm"]
        walls.append(r["wall_s"]["total"])
        print("  %-6s %-16s %-6s %3d/%3d %6d %4d %6d %5.1fs (%4.1f+%5.1f) | %4d/%3d/%4d %13s | %4d/%3d/%4d %17s | %s" % (
            tag, "%s/%s/%d" % t, spec, dv["matched"], dv["compared"], len(r["writes_selected"]),
            len(r["writes_failed"]), r["steps_counter_mismatches"], r["wall_s"]["total"], r["wall_s"]["construct"],
            r["wall_s"]["replay"], fr["ever"], fr["cleared"], fr["intact"], "", S["ever"], S["cleared"], S["intact"], "",
            same))
    if walls:
        print("  wall total per replay: min %.1f  mean %.1f  max %.1f s" % (min(walls), sum(walls) / len(walls), max(walls)))


def report_crn(args):
    t = ("east", "half", 101)
    pp = out_name(args.outdir, "fmOFF", t, "none", "pin")
    if os.path.exists(pp):
        R = compare(load_trace(pp), load_trace(arm_path("fmOFF", *t)))
        r = _load(pp)
        print("PIN IDENTITY  fmOFF %s/%s/%d --writes none --pin-draws <its own recorded draws>: digest %d/%d vs fmOFF, "
              "first burning diff %s, pinned %d fallback %d" % (t + (R["digest_matched"], R["digest_compared"],
                                                                     R["first_burning_diff"], r["pin_counts"]["pinned"],
                                                                     r["pin_counts"]["fallback"])))
    print("CRN CHECK  (a CRN replay's single write can act only physically: its burning difference must never")
    print("            leave the light cone; the stock pair is shown for contrast)")
    for tag, t in (("fmF", ("east", "half", 404)), ("fmES", ("east", "half", 101))):
        a = out_name(args.outdir, tag, t, "only-first", "crn")
        b = out_name(args.outdir, tag, t, "none", "crn")
        if os.path.exists(a) and os.path.exists(b):
            R = compare(load_trace(a), load_trace(b))
            print("  %-5s %-15s CRN   first_div %s first_out_of_cone %s stream_shift_tick %s d_intact %+d symdiff %d max_dist %s" % (
                tag, "%s/%s/%d" % t, R["first_digest_div"], R["first_out_of_cone"], R.get("stream_shift_tick"),
                R["delta_intact_a_minus_b"], R["final_has_burned_symdiff"], R.get("symdiff_max_dist")))
        sa = out_name(args.outdir, tag, t, "only-first")
        if os.path.exists(sa):
            R = compare(load_trace(sa), load_trace(arm_path("fmOFF", *t)))
            print("  %-5s %-15s stock first_div %s first_out_of_cone %s d_intact %+d symdiff %d max_dist %s" % (
                tag, "%s/%s/%d" % t, R["first_digest_div"], R["first_out_of_cone"],
                R["delta_intact_a_minus_b"], R["final_has_burned_symdiff"], R.get("symdiff_max_dist")))


def report_study(args):
    sys.path.insert(0, HERE)
    import _firemech_analyze as FA  # noqa: E402
    rows = []
    for tag, action in (("fmES", "extinguish"), ("fmF", "clear")):
        for sample, tuples in (("canon", CANON), ("fresh", FRESH)):
            for t in tuples:
                po = out_name(args.outdir, tag, t, "only-first")
                pd = out_name(args.outdir, tag, t, "drop-first")
                if not (os.path.exists(po) and os.path.exists(pd)):
                    continue
                arm = _load(arm_path(tag, *t))
                off = _load(arm_path("fmOFF", *t))
                SA, SO = FA.run_summary(arm, None), FA.run_summary(off, None)
                ro, rd = _load(po), _load(pd)
                pn = out_name(args.outdir, "fmOFF", t, "none")
                none_ok = None
                if os.path.exists(pn):
                    rn = _load(pn)
                    none_ok = (rn["digest_vs_arm"]["matched"] == rn["digest_vs_arm"]["compared"] == 240
                               and rn["final"]["intact"] == SO["intact"])
                    O = load_trace(pn)
                else:
                    O = load_trace(arm_path("fmOFF", *t))
                Ao, Ad = load_trace(po), load_trace(pd)
                Rso = compare(Ao, O)
                Rsd = compare(Ad, load_trace(arm_path(tag, *t)))
                pp = out_name(args.outdir, tag, t, "only-first", "pin")
                Rp, rp = None, None
                if os.path.exists(pp) and os.path.exists(pn):
                    rp = _load(pp)
                    Rp = compare(load_trace(pp), O)
                wrows = [r for r in arm["firefight_log"] if r.get("wrote")]
                first = wrows[0]
                n_act = sum(1 for r in wrows if r["action"] == action)
                rows.append({
                    "tag": tag, "sample": sample, "t": t, "n_writes": len(wrows), "n_action": n_act,
                    "first_step": first["step"], "first_action": first["action"], "first_cell": first["target"],
                    "d_all": SA["intact"] - SO["intact"],
                    "d_only": ro["final"]["intact"] - SO["intact"],
                    "d_drop": rd["final"]["intact"] - SO["intact"],
                    "only_applied": ro["writes_selected"][0]["applied"] if ro["writes_selected"] else None,
                    "drop_failed": len(rd["writes_failed"]), "drop_sel": len(rd["writes_selected"]),
                    "only_div": Rso["first_digest_div"], "only_out": Rso["first_out_of_cone"],
                    "only_out_info": Rso["out_of_cone"], "only_symdiff": Rso["final_has_burned_symdiff"],
                    "only_buckets": Rso.get("symdiff_dist_buckets"), "only_maxd": Rso.get("symdiff_max_dist"),
                    "only_pre_t0": Rso["steps_with_burning_diff_before_t0"],
                    "only_first_burn_diff": Rso["first_burning_diff"],
                    "drop_vs_all_div": Rsd["first_digest_div"],
                    "drop_vs_all_out": Rsd["first_out_of_cone"],
                    "drop_vs_all_burn1": Rsd["first_burning_diff"],
                    "drop_vs_all_symdiff": Rsd["final_has_burned_symdiff"],
                    "none_ok": none_ok,
                    "only_shift": Rso.get("stream_shift_tick"),
                    "only_shift_uid": Rso.get("stream_shift_min_uid"),
                    "only_first_burnt_diff": Rso.get("first_burnt_set_diff"),
                    "first_uid": (O["uid_of"] or {}).get(tuple(first["target"])),
                    "scorched": first.get("scorched"),
                    "covers": Rso.get("cone_covers_grid_step"),
                    "d_pin": (rp["final"]["intact"] - SO["intact"]) if rp else None,
                    "pin_out": Rp["first_out_of_cone"] if Rp else None,
                    "pin_div": Rp["first_digest_div"] if Rp else None,
                    "pin_symdiff": Rp["final_has_burned_symdiff"] if Rp else None,
                    "pin_maxd": Rp.get("symdiff_max_dist") if Rp else None,
                    "pin_fallback": rp["pin_counts"]["fallback"] if rp else None,
                    "pin_applied": (rp["writes_selected"][0]["applied"] if rp and rp["writes_selected"] else None),
                    "only_first_burning_diff": Rso["first_burning_diff"],
                })
    print("STUDY  intact deltas vs fmOFF (d = replay or arm intact - fmOFF intact, analyzer definition)")
    print("  div = first digest divergence of only-first vs the no-write replay (== fmOFF); shift = first tick")
    print("  whose draw stream differs (first differing burnt set + 1 tick); out = first step a burning difference")
    print("  lies outside the light cone (r = cone radius then, maxd = farthest outside cell); symdiff = final")
    print("  has_burned cells that differ, bucketed by Chebyshev distance from the written cell")
    print("  burn1 = first step a burning state differs; cover = step the cone first covers the whole grid (after it")
    print("  no departure is detectable); d_pin = only-first with every draw pinned to the no-write run's value")
    print("  (physical effect only), pout = its first out-of-cone step (must be -), psym/pmax = its final symdiff and")
    print("  farthest differing cell; sc = first clear hit a scorched cell")
    print("  %-4s %-5s %-15s %4s %5s %7s %3s %6s %6s %6s %6s | %4s %5s %5s %5s %5s %9s %6s %-15s | %5s %5s %4s %4s" % (
        "arm", "set", "tuple", "nW", "first", "cell", "sc", "d_all", "d_only", "d_drop", "d_pin", "div", "burn1",
        "shift", "cover", "out", "(r/maxd)", "symdif", "<=3/4-10/11-20/>20", "pout", "psym", "pmax", "fb"))
    for x in rows:
        oi = x["only_out_info"]
        b = x["only_buckets"] or {}
        print("  %-4s %-5s %-15s %4d %5d %7s %3s %+6d %+6d %+6d %6s | %4s %5s %5s %5s %5s %9s %6d %-15s | %5s %5s %4s %4s%s%s" % (
            x["tag"][2:], x["sample"], "%s/%s/%d" % x["t"], x["n_writes"], x["first_step"],
            "%d,%d" % tuple(x["first_cell"]), {True: "y", False: "n", None: "-"}[x["scorched"]],
            x["d_all"], x["d_only"], x["d_drop"], ("%+d" % x["d_pin"]) if x["d_pin"] is not None else "?",
            x["only_div"], x["only_first_burning_diff"] if x["only_first_burning_diff"] is not None else "-",
            x["only_shift"] if x["only_shift"] is not None else "-", x["covers"],
            x["only_out"] if x["only_out"] is not None else "-",
            ("%d/%d" % (oi["cone_radius"], oi["max_dist"])) if oi else "-", x["only_symdiff"],
            "%s/%s/%s/%s" % (b.get("<=3"), b.get("4-10"), b.get("11-20"), b.get(">20")),
            x["pin_out"] if x["pin_out"] is not None else "-", x["pin_symdiff"], x["pin_maxd"], x["pin_fallback"],
            "" if x["none_ok"] else "  NONE!=OFF",
            "" if x["only_applied"] else "  ONLY-FIRST NOT APPLIED"))

    def med(v):
        v = sorted(v)
        if not v:
            return None
        m = len(v) // 2
        x = v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2.0
        return "%.2f" % x if isinstance(x, float) else str(x)

    print("")
    print("DISTRIBUTIONS")
    for tag in ("fmES", "fmF"):
        for sample in ("canon", "fresh", "both", "dedup"):
            xs = [x for x in rows if x["tag"] == tag and (sample in ("both", "dedup") or x["sample"] == sample)
                  and not (sample == "dedup" and x["t"][1] == "def")]
            if not xs:
                continue
            n = len(xs)
            same_sign = sum(1 for x in xs if x["d_only"] * x["d_all"] > 0)
            opp_sign = sum(1 for x in xs if x["d_only"] * x["d_all"] < 0)
            outc = [x for x in xs if x["only_out"] is not None]
            shift = [x for x in xs if x["only_shift"] is not None and x["only_shift"] <= 240]
            far = sum((x["only_buckets"] or {}).get(">20", 0) for x in xs)
            tot = sum(x["only_symdiff"] for x in xs)
            print("  %-4s %-5s n=%2d | d_all: med|.| %6s sum %+6d pos/neg/0 %d/%d/%d | d_only: med|.| %5s sum %+6d "
                  "pos/neg/0 %d/%d/%d range [%+d,%+d] | |d_only|/|d_all| med %s | sign(d_only)=sign(d_all) %d, opposite %d"
                  % (tag[2:], sample, n, med([abs(x["d_all"]) for x in xs]), sum(x["d_all"] for x in xs),
                     sum(1 for x in xs if x["d_all"] > 0), sum(1 for x in xs if x["d_all"] < 0),
                     sum(1 for x in xs if x["d_all"] == 0),
                     med([abs(x["d_only"]) for x in xs]), sum(x["d_only"] for x in xs),
                     sum(1 for x in xs if x["d_only"] > 0), sum(1 for x in xs if x["d_only"] < 0),
                     sum(1 for x in xs if x["d_only"] == 0), min(x["d_only"] for x in xs), max(x["d_only"] for x in xs),
                     med([abs(x["d_only"]) / abs(x["d_all"]) for x in xs if x["d_all"] != 0]), same_sign, opp_sign))
            print("  %-4s %-5s      | only-first: digest div == write step %d/%d | stream shift <= 240: %d/%d "
                  "(lag after write med %s) | leaves cone: %d/%d (lag med %s; out step >= shift tick %d/%d) | "
                  "final has_burned symdiff total %d, >20 cells away %d | d_drop-d_all med|.| %s"
                  % ("", "", sum(1 for x in xs if x["only_div"] == x["first_step"]), n, len(shift), n,
                     med([x["only_shift"] - x["first_step"] for x in shift]), len(outc), n,
                     med([x["only_out"] - x["first_step"] for x in outc]),
                     sum(1 for x in outc if x["only_shift"] is not None and x["only_out"] >= x["only_shift"]), len(outc),
                     tot, far, med([abs(x["d_drop"] - x["d_all"]) for x in xs])))
            print("  %-4s %-5s      | lag write->first differing burnt set: %s | lag write->first burning difference: %s"
                  % ("", "", sorted((x["only_first_burnt_diff"] - x["first_step"]) if x["only_first_burnt_diff"] else None
                                    for x in xs if x["only_first_burnt_diff"]),
                     sorted((x["only_first_burning_diff"] - x["first_step"]) for x in xs
                            if x["only_first_burning_diff"] is not None)))
            print("  %-4s %-5s      | first write scorched (clear only) %d | only-first with no burning difference "
                  "at all %d | only-first final has_burned identical %d"
                  % ("", "", sum(1 for x in xs if x["scorched"]), sum(1 for x in xs if x["only_first_burning_diff"] is None),
                     sum(1 for x in xs if x["only_symdiff"] == 0)))
            print("  %-4s %-5s      | drop-first vs the arm: no burning difference at all %d/%d | final has_burned "
                  "identical %d/%d | symdiff total %d | |d_drop-d_all| values %s"
                  % ("", "", sum(1 for x in xs if x["drop_vs_all_burn1"] is None), n,
                     sum(1 for x in xs if x["drop_vs_all_symdiff"] == 0), n, sum(x["drop_vs_all_symdiff"] for x in xs),
                     sorted(abs(x["d_drop"] - x["d_all"]) for x in xs)))
            det = [x for x in xs if x["only_shift"] is not None and x["only_shift"] < x["covers"]]
            print("  %-4s %-5s      | shift before the cone covers the grid (departure detectable): %d/%d, of which "
                  "leave the cone %d | no shift <= 240: %d"
                  % ("", "", len(det), n, sum(1 for x in det if x["only_out"] is not None),
                     sum(1 for x in xs if x["only_shift"] is None or x["only_shift"] > 240)))
            ps = [x for x in xs if x["d_pin"] is not None]
            if ps:
                print("  %-4s %-5s      | pinned (physical only) n=%d: d_pin med|.| %s sum %+d range [%+d,%+d] "
                      "pos/neg/0 %d/%d/%d | pinned leaves cone %d | fallback draws total %d | "
                      "re-roll part d_only-d_pin med|.| %s | d_pin symdiff total %d max dist %s"
                      % ("", "", len(ps), med([abs(x["d_pin"]) for x in ps]), sum(x["d_pin"] for x in ps),
                         min(x["d_pin"] for x in ps), max(x["d_pin"] for x in ps),
                         sum(1 for x in ps if x["d_pin"] > 0), sum(1 for x in ps if x["d_pin"] < 0),
                         sum(1 for x in ps if x["d_pin"] == 0), sum(1 for x in ps if x["pin_out"] is not None),
                         sum(x["pin_fallback"] or 0 for x in ps), med([abs(x["d_only"] - x["d_pin"]) for x in ps]),
                         sum(x["pin_symdiff"] for x in ps), max((x["pin_maxd"] or 0) for x in ps)))
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rows, f, indent=1)


# ============================================================================== main ===
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO_DEFAULT)
    ap.add_argument("--arm-json")
    ap.add_argument("--writes", default="all")
    ap.add_argument("--crn", action="store_true")
    ap.add_argument("--record-draws", default="")
    ap.add_argument("--pin-draws", default="")
    ap.add_argument("--steps", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--compare", nargs=2)
    ap.add_argument("--json", default="")
    ap.add_argument("--batch", choices=["validate", "study-canonical", "study-fresh", "pinned-canonical",
                                        "pinned-fresh", "crn-check"])
    ap.add_argument("--report", choices=["validate", "study", "crn-check"])
    ap.add_argument("--outdir")
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args()
    if args.compare:
        return run_compare(args)
    if args.batch:
        return run_batch(args)
    if args.report:
        {"validate": report_validate, "study": report_study, "crn-check": report_crn}[args.report](args)
        return 0
    if not args.arm_json or not args.out:
        ap.error("--arm-json and --out are required for a replay")
    return run_replay(args)


if __name__ == "__main__":
    raise SystemExit(main())
