"""Verification helper for outputs/_ud_probe.py (urgency round Part 2; not a run-loaded file).

usage (urgency worktree root):
  .venv/Scripts/python.exe outputs/_ud_probe_check.py compare UD.json DP.json
      G-ID of a ud0 record against a _dp_probe record of the same line, by dispatch:outputs/_dp_analyze.ident_diff
      (FIELDS + every mf2 section + every dp field but J_ONLY), plus every other top-level section reported.
  .venv/Scripts/python.exe outputs/_ud_probe_check.py summary X.json
      the ud / mv / mv_events digest of one record (errors, kicks, rows per branch, ACTED counts, timing).
  .venv/Scripts/python.exe outputs/_ud_probe_check.py pair OFF.json ON.json
      cross-arm shadow agreement on one cell: identical rows_ff and mv rows before s* (the ON arm's first live ACTED
      event or divergent kick), identical decision-time mv columns and kick shadow fields at s*.
  .venv/Scripts/python.exe outputs/_ud_probe_check.py synthetic
      the carry-leg rows (c0 / c1 / c2s / c3 and today's path / fallback / raise), the C-1 cost, and the C-4 / C-5
      detectors on hand-built boards through _ud_probe.install() and the real advance / lookup / casualty sweep;
      v2: the kick flags of ud_probe v2 (R2 B-1 / B-2) - the pure definitions (kick_flags / bind_flags) on
      hand-built records, and the REAL kick (both arms, through install()) on a board whose index and U1 heads the
      planner refuses (state.cancelled, as a reset_victim_pending relabel leaves it): acc, index_wb, u1_wb,
      div_shadow(_head), divergent(_head), attempts, bound, decisions[].accepted, no shadow mismatch.
  .venv/Scripts/python.exe outputs/_ud_probe_check.py kicks X.json
      v2 kick-record consistency on a real record: acc covers W, index_wb / u1_wb / div_shadow / divergent follow
      their definitions from index / u1 / acc / bound, attempts agree with the binds (the successful attempts are
      the bound victims; at |F| = 1 the first success is the shadow's victim and every attempt before it was
      refused by the planner), the order attempted is the order the arm ran, decisions[].accepted == acc; plus
      ud.errors, shadow_mismatch and the dcb column. Prints counts and flags only (no outcome).
  .venv/Scripts/python.exe outputs/_ud_probe_check.py purity STEPS SCENARIO WIND SEED [KEY=VALUE ...]
      builds the cell in-process (the _sd_probe sequence, GLOBAL_PLANNER_MODE 0, VICTIM_SPAWN_MODE 0, BATCH_SIZE
      360, no CRN patch), and at EVERY shadow point of
      _ud_probe (each unit's advance after its target refresh, each dispatch kick - v2: including the planner's
      acceptance reading, get_rescue_operational_snapshot + select_rescue_assignment per W victim) takes a deep
      snapshot of the model (every agent's attributes, the model's attributes to depth 3, the grid's contents, the
      RNG states), runs _ud_probe.mv_shadow / kick_shadow, snapshots again and compares. Exit 1 on any difference.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import io
import json
import os
import random
import runpy
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DISPATCH_OUT = r"E:\Projects\SAS_wt\dispatch\outputs"


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def compare(a_path, b_path):
    sys.path.insert(0, DISPATCH_OUT)
    argv = sys.argv
    sys.argv = argv[:1]
    try:
        import _dp_analyze as DA  # noqa: E402
    finally:
        sys.argv = argv
    a, b = load(a_path), load(b_path)
    diff, note, other = DA.ident_diff(a, b, False)
    print("G-ID (dispatch _dp_analyze.ident_diff): %s" % ("IDENTICAL" if not diff else "DIFFERS %r" % diff))
    if note:
        print("  note:", note)
    print("  other sections differing (fb3/fx3/ut/mr, reported):", other)
    keys = sorted(set(a) | set(b))
    skip = {"argv", "tag", "dp", "ud", "mv", "mv_events", "wall_s", "fb3", "fx3", "ut", "mr", "mf2"}
    rest = [k for k in keys if k not in skip and a.get(k) != b.get(k)]
    print("  other top-level keys differing:", rest)
    print("  only in A:", sorted(set(a) - set(b)), " only in B:", sorted(set(b) - set(a)))
    da, db = a.get("dp") or {}, b.get("dp") or {}
    print("  dp keys equal:", sorted(da) == sorted(db), "| J_ONLY differing:",
          [k for k in DA.J_ONLY if da.get(k) != db.get(k)])
    print("  steps", a.get("steps_done"), b.get("steps_done"), "| wall_s", a.get("wall_s"), b.get("wall_s"),
          "| dp inst_ms", (da.get("timing") or {}).get("inst_ms_total"), (db.get("timing") or {}).get("inst_ms_total"))
    return 0 if not diff else 1


def summary(path):
    d = load(path)
    ud, mv, ev = d.get("ud") or {}, d.get("mv") or {}, d.get("mv_events") or []
    print("probe", ud.get("probe"), "rc", ud.get("rc_chain"), "steps", d.get("steps_done"), "crashed",
          (d.get("crashed") or {}).get("type"))
    print("switches", json.dumps(ud.get("switches")))
    print("ud errors", ud.get("errors"), "| dp errors", (d.get("dp") or {}).get("errors"))
    print("shadow_mismatch", ud.get("shadow_mismatch"))
    cols = mv.get("cols") or []
    rows = mv.get("rows") or []
    ix = {c: i for i, c in enumerate(cols)}
    print("mv rows", len(rows), "branches", dict(collections.Counter(r[ix["branch"]] for r in rows)))
    print("acted (shadow)", dict(collections.Counter(r[ix["acted"]] for r in rows if r[ix["acted"]])))
    print("mv_events", dict(collections.Counter((e["kind"], e["live"]) for e in ev)))
    for e in ev[:8]:
        print("   ", json.dumps(e))
    ks = ud.get("kicks") or []
    print("kicks", len(ks), "qualifying", sum(1 for k in ks if k.get("qualifies")),
          "div_shadow", sum(1 for k in ks if k.get("div_shadow")),
          "divergent", sum(1 for k in ks if k.get("divergent")),
          "| head-based: div_shadow_head", sum(1 for k in ks if k.get("div_shadow_head")),
          "divergent_head", sum(1 for k in ks if k.get("divergent_head")),
          "| acc read", sum(1 for k in ks if k.get("acc") is not None),
          "kicks with a refused W victim", sum(1 for k in ks if k.get("acc") and not all(k["acc"].values())))
    for k in ks[:6]:
        print("   ", json.dumps({x: k.get(x) for x in ("i", "step", "site", "W", "F", "qualifies", "index", "u1", "rec",
                                                       "d", "acc", "index_wb", "u1_wb", "bound", "attempts",
                                                       "divergent", "div_shadow", "divergent_head", "div_shadow_head",
                                                       "ms", "ms_model", "z4_ok", "triage")}))
    print("decisions", len(ud.get("decisions") or []))
    t = ud.get("timing") or {}
    print("timing", json.dumps({k: v for k, v in t.items() if k != "fix_calls"}))
    zrb_bad = [r for r in rows if r[ix["leg"]] == "approach" and r[ix["mt"]] and r[ix["zrb"]] is not None
               and bool(r[ix["rb_call"]]) != bool(r[ix["zrb"]])]
    print("Z-RB disagreements (approach rows with a _move_toward call):", len(zrb_bad))
    for r in rows[:4]:
        print("   ", json.dumps(dict(zip(cols, r))))
    return 0


def _first_accepted(order, acc):
    """The checker's own copy of 16.5's 'the victim the order WOULD BIND' (independent of _ud_probe.first_accepted)."""
    if order is None or acc is None:
        return None
    for vid in order:
        if acc.get(vid):
            return vid
    return None


def kick_problems(K, on):
    """v2 definition / consistency problems of one kick record (list of strings). `on` = DISPATCH_URGENCY effective."""
    probs = []
    i = K.get("i")
    for f in ("acc", "index_wb", "u1_wb", "div_shadow", "divergent", "div_shadow_head", "divergent_head", "attempts",
              "bound"):
        if f not in K:
            probs.append("kick %s: no field %s" % (i, f))
    if probs:
        return probs
    acc, index, u1, bound, att = K["acc"], K.get("index") or [], K.get("u1"), K["bound"] or [], K["attempts"]
    q = bool(K.get("qualifies"))
    if acc is not None and sorted(acc) != sorted(index):
        probs.append("kick %s: acc keys %r != W %r" % (i, sorted(acc), sorted(index)))
    if (acc is None) != (u1 is None):
        probs.append("kick %s: acc read %s but the U1 shadow %s" % (i, acc is not None,
                                                                    "ran" if u1 is not None else "did not run"))
    if K["index_wb"] != _first_accepted(index, acc):
        probs.append("kick %s: index_wb %r != first accepted of index %r" % (i, K["index_wb"], _first_accepted(index, acc)))
    if K["u1_wb"] != _first_accepted(u1, acc):
        probs.append("kick %s: u1_wb %r != first accepted of u1 %r" % (i, K["u1_wb"], _first_accepted(u1, acc)))
    first = bound[0][0] if bound else None
    if K["div_shadow"] != (q and K["u1_wb"] != K["index_wb"]):
        probs.append("kick %s: div_shadow %r against its definition" % (i, K["div_shadow"]))
    if K["divergent"] != (q and first != K["index_wb"]):
        probs.append("kick %s: divergent %r against its definition" % (i, K["divergent"]))
    if K["div_shadow_head"] != bool(q and u1 and index and u1[0] != index[0]):
        probs.append("kick %s: div_shadow_head %r against v1's definition" % (i, K["div_shadow_head"]))
    if K["divergent_head"] != bool(q and bound and index and bound[0][0] != index[0]):
        probs.append("kick %s: divergent_head %r against v1's definition" % (i, K["divergent_head"]))
    if att is None:
        return probs + ["kick %s: attempts is None" % i]
    if any(ok is None for _v, ok in att):
        probs.append("kick %s: an attempt raised %r" % (i, att))
    if [v for v, ok in att if ok] != [b[0] for b in bound]:
        probs.append("kick %s: successful attempts %r != bound %r" % (i, [v for v, ok in att if ok], bound))
    ran = u1 if (on and q) else index
    if [v for v, _ok in att] != list(ran or []):
        probs.append("kick %s: attempted %r != the order the arm ran %r" % (i, [v for v, _ok in att], ran))
    if acc is not None and len(K.get("F") or []) == 1:
        expected = K["u1_wb"] if (on and q) else K["index_wb"]
        if first != expected:
            probs.append("kick %s: first bind %r != the shadow's %r" % (i, first, expected))
        tried = [v for v, _ok in att]
        before = tried[:tried.index(first)] if first in tried else tried
        if any(acc.get(v) for v in before):
            probs.append("kick %s: a planner-accepted victim was attempted and not bound before the bind %r" % (i, att))
    return probs


def kicks(path):
    """v2 kick-record consistency on a real record (counts and flags only; no outcome is printed)."""
    d = load(path)
    ud = d.get("ud") or {}
    on = bool((ud.get("switches") or {}).get("DISPATCH_URGENCY"))
    ks = ud.get("kicks") or []
    st = collections.Counter()
    probs = []
    by_i = {}
    for K in ks:
        by_i[K.get("i")] = K
        st["kicks"] += 1
        st["qualifying"] += bool(K.get("qualifies"))
        acc = K.get("acc")
        if acc is not None:
            st["acc read"] += 1
            st["planner readings"] += len(acc)
            st["refused W victims"] += sum(1 for v in acc.values() if not v)
            st["kicks with index head refused"] += bool(K.get("index") and not acc.get(K["index"][0]))
            st["kicks with u1 head refused"] += bool(K.get("u1") and not acc.get(K["u1"][0]))
            st["kicks with nothing accepted"] += not any(acc.values())
        st["attempts"] += len(K.get("attempts") or [])
        st["attempts refused"] += sum(1 for _v, ok in K.get("attempts") or [] if not ok)
        st["div_shadow"] += bool(K.get("div_shadow"))
        st["divergent"] += bool(K.get("divergent"))
        st["div_shadow_head"] += bool(K.get("div_shadow_head"))
        st["divergent_head"] += bool(K.get("divergent_head"))
        st["head flag != v2 flag"] += (bool(K.get("div_shadow")) != bool(K.get("div_shadow_head"))
                                       or bool(K.get("divergent")) != bool(K.get("divergent_head")))
        probs += kick_problems(K, on)
    for dec in ud.get("decisions") or []:
        K = by_i.get(dec.get("k"))
        if K is None:
            probs.append("decision of an unknown kick %r" % dec.get("k"))
            continue
        acc = K.get("acc")
        want = (None if acc is None else bool(acc.get(dec["vid"])), dec["vid"] == K.get("index_wb"),
                dec["vid"] == K.get("u1_wb"))
        if (dec.get("accepted"), dec.get("index_wb"), dec.get("u1_wb")) != want:
            probs.append("decision k=%s vid=%s: accepted/index_wb/u1_wb %r != %r" % (
                dec.get("k"), dec["vid"], (dec.get("accepted"), dec.get("index_wb"), dec.get("u1_wb")), want))
        st["decisions"] += 1
    mv = d.get("mv") or {}
    cols = list(mv.get("cols") or [])
    if "dcb" not in cols:
        probs.append("mv cols carry no dcb")
    else:
        ix = {c: n for n, c in enumerate(cols)}
        for r in mv.get("rows") or []:
            if len(r) != len(cols):
                probs.append("an mv row has %d values for %d cols" % (len(r), len(cols)))
                break
            # row counts only (no per-leg split: a carry row count is outcome-adjacent on set-1/2 cells)
            st["mv rows"] += 1
            st["mv rows with a finite dcb"] += r[ix["dcb"]] is not None
            st["approach rows with a finite dcb"] += r[ix["leg"]] == "approach" and r[ix["dcb"]] is not None
            if r[ix["leg"]] == "carry" and r[ix["today"]] is not None and r[ix["dcb"]] != r[ix["dc"]]:
                probs.append("carry row step %s unit %s: dcb %r != dc %r" % (r[0], r[1], r[ix["dcb"]], r[ix["dc"]]))
    print("probe %s | DISPATCH_URGENCY effective %s | switches %s" % (
        ud.get("probe"), on, json.dumps({k: v for k, v in (ud.get("switches") or {}).items() if k != "raw"})))
    print("ud.errors: %d %s" % (len(ud.get("errors") or []), (ud.get("errors") or [])[:3]))
    print("shadow_mismatch: %d %s" % (len(ud.get("shadow_mismatch") or []), (ud.get("shadow_mismatch") or [])[:3]))
    print("counts:", json.dumps(dict(st)))
    print("consistency problems: %d" % len(probs))
    for p in probs[:20]:
        print("   ", p)
    bad = probs or ud.get("errors") or ud.get("shadow_mismatch")
    return 1 if bad else 0


PRE_COLS = ("step", "unit", "victim", "leg", "pre", "target", "digest", "st_pre", "trig", "zrb", "today", "fa", "fb",
            "fbB", "fc", "acted", "dc", "dcx", "df", "dm", "dr", "gesc", "cls_pre", "fd_pre", "c1_pre", "dcb")


def pair(off_path, on_path):
    """Cross-arm check of one cell: the OFF arm (all switches 0) and an ON arm. s* = the first step with a LIVE ACTED
    event or a divergent kick in the ON arm. Before s*: rows_ff and every mv row identical (all columns but the timing
    ones); at s*: the decision-time (pre-advance) columns of every row identical (shadow agreement)."""
    a, b = load(off_path), load(on_path)
    ev = [e["step"] for e in b.get("mv_events") or [] if e.get("live")]
    kd = [k["step"] for k in (b.get("ud") or {}).get("kicks") or [] if k.get("divergent")]
    s_star = min(ev + kd) if ev + kd else None
    print("s* (first live ACTED event / divergent kick in the ON arm):", s_star,
          "| live events", len(ev), "| divergent kicks", kd)
    ra, rb = a.get("rows_ff") or [], b.get("rows_ff") or []
    lim = (s_star - 1) if s_star else max(len(ra), len(rb))
    first = next((t for t in range(min(len(ra), len(rb))) if ra[t] != rb[t]), None)
    print("rows_ff: first differing index %s (state after step %s); required >= %s -> %s" % (
        first, None if first is None else first + 1, lim,
        "OK" if first is None or first >= lim else "FAIL"))
    cols = (a.get("mv") or {}).get("cols") or []
    ix = {c: i for i, c in enumerate(cols)}
    full = [c for c in cols if c not in ("fix_ms", "inst_ms")]
    ma = [r for r in (a.get("mv") or {}).get("rows") or []]
    mb = [r for r in (b.get("mv") or {}).get("rows") or []]
    before_a = [[r[ix[c]] for c in full] for r in ma if s_star is None or r[0] < s_star]
    before_b = [[r[ix[c]] for c in full] for r in mb if s_star is None or r[0] < s_star]
    same_before = before_a == before_b
    print("mv rows before s*: %d vs %d, identical (all columns but timing): %s" % (
        len(before_a), len(before_b), same_before))
    if not same_before:
        for x, y in zip(before_a, before_b):
            if x != y:
                print("   first differing row:\n    OFF %s\n    ON  %s" % (x, y))
                break
    if s_star is not None:
        at_a = [[r[ix[c]] for c in PRE_COLS] for r in ma if r[0] == s_star]
        at_b = [[r[ix[c]] for c in PRE_COLS] for r in mb if r[0] == s_star]
        print("decision-time columns at s*: %d vs %d rows, identical: %s" % (len(at_a), len(at_b), at_a == at_b))
        if at_a != at_b:
            for x, y in zip(at_a, at_b):
                if x != y:
                    print("    OFF %s\n    ON  %s" % (x, y))
        ka = [k for k in (a.get("ud") or {}).get("kicks") or [] if k["step"] == s_star]
        kb = [k for k in (b.get("ud") or {}).get("kicks") or [] if k["step"] == s_star]
        keys = ("site", "W", "F", "qualifies", "index", "u1", "rec", "d", "div_shadow", "z4", "acc", "index_wb",
                "u1_wb", "div_shadow_head")
        print("kicks at s*: shadow fields identical:",
              [{k: x.get(k) for k in keys} for x in ka] == [{k: x.get(k) for k in keys} for x in kb])
    ok = (first is None or first >= lim) and same_before
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------- purity
def freeze(v, depth, seen_agents):
    if v is None or isinstance(v, (bool, int, float, str, bytes)):
        return v
    t = type(v)
    mod = getattr(t, "__module__", "")
    if t.__name__ in ("ndarray",):
        try:
            return ("nd", v.dtype.str, v.shape, v.tobytes())
        except Exception:
            return ("nd?",)
    if mod.startswith("numpy"):
        try:
            return ("np", repr(v))
        except Exception:
            return ("np?",)
    if id(v) in seen_agents:
        return ("agent", id(v))
    # no id() of non-agent objects: some state objects hand out fresh sub-objects on every read (an unstable key)
    if depth <= 0:
        try:
            n = len(v)
        except Exception:
            n = None
        return ("obj", t.__name__, n)
    if isinstance(v, dict):
        return ("dict", tuple((freeze(k, 0, seen_agents), freeze(x, depth - 1, seen_agents)) for k, x in v.items()))
    if isinstance(v, (list, tuple)):
        return (t.__name__, tuple(freeze(x, depth - 1, seen_agents) for x in v))
    if isinstance(v, (set, frozenset)):
        return (t.__name__, tuple(sorted((repr(freeze(x, depth - 1, seen_agents)) for x in v))))
    if isinstance(v, collections.deque):
        return ("deque", tuple(freeze(x, depth - 1, seen_agents) for x in v))
    if hasattr(v, "__dict__") and not callable(v):
        return ("obj", t.__name__, freeze(dict(vars(v)), depth - 1, seen_agents))
    return ("other", t.__name__)


def snapshot(model, ag):
    agents = list(model.schedule.agents)
    seen = {id(a) for a in agents}
    seen.add(id(model))
    out = {}
    for a in agents:
        out[("agent", type(a).__name__, str(a.unique_id))] = freeze(
            {k: v for k, v in vars(a).items() if k != "model"}, 3, seen)
    out["model"] = freeze({k: v for k, v in vars(model).items()
                           if k not in ("schedule", "grid", "datacollector")}, 3, seen)
    grid = model.grid
    cells = []
    for x in range(grid.width):
        for y in range(grid.height):
            cells.append(tuple(id(o) for o in grid.get_cell_list_contents([(x, y)])))
    out["grid"] = tuple(cells)
    rngs = []
    for r in (getattr(ag, "random", None), getattr(model, "random", None)):
        rngs.append(r.getstate() if r is not None else None)
    import numpy as np
    st = np.random.get_state()
    rngs.append((st[0], st[1].tobytes(), st[2], st[3], st[4]))
    out["rng"] = tuple(rngs)
    return out


def purity(steps, scenario, wind, seed, sets):
    sys.path.insert(0, REPO)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    import evaluate_scenarios as es
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from src_extension.planning import fire_arrival_estimate as fae
    from src_extension.planning import urgency_dispatch as udm
    from src_extension.planning.rescue_planner import select_rescue_assignment

    probe = runpy.run_path(os.path.join(HERE, "_ud_probe.py"), run_name="ud_probe_module")
    fn = probe["shadow_funcs"](am)
    ns = argparse.Namespace(scenario=scenario, wind=wind, uavs=None, victims=None, firefighters=None,
                            fire_trackers=None, victim_searchers=None, batch_size=300, fire_spread=0.75,
                            ff_absence_min=None, ff_absence_max=None)
    extra = {"GLOBAL_PLANNER_MODE": 0, "VICTIM_SPAWN_MODE": 0, "BATCH_SIZE": 360}
    for item in sets:
        k, v = item.split("=", 1)
        extra[k] = int(v)
    ns.preset_overrides = dict(extra)
    params = es._scenario_params(ns)
    params.update(extra)
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    stats = collections.Counter()
    failures = []
    t_snap = [0.0]
    o_refresh = am.Firefighter._refresh_target_from_victim

    def check(label, fn_call, model):
        t0 = time.perf_counter()
        before = snapshot(model, am)
        t_snap[0] += time.perf_counter() - t0
        out = fn_call()
        t0 = time.perf_counter()
        after = snapshot(model, am)
        t_snap[0] += time.perf_counter() - t0
        if before != after:
            bad = [k for k in before if before.get(k) != after.get(k)][:5]
            if "model" in bad:
                mb, ma = dict(before["model"][1]), dict(after["model"][1])
                bad.append(["model." + str(k) for k in mb if mb.get(k) != ma.get(k)][:5])
            failures.append((label, int(model.evaluation_timesteps_counter or 0), bad))
        stats[label] += 1
        return out

    def refresh(self, *a, **k):
        r = o_refresh(self, *a, **k)
        if not stats["control_unit"]:
            # POSITIVE CONTROLS (restored at once): the snapshot must see a unit write and an RNG draw
            old = self._idle_retreat_steps
            check("control_unit", lambda: setattr(self, "_idle_retreat_steps", old + 1000), self.model)
            self._idle_retreat_steps = old
            state = am.random.getstate()
            check("control_rng", lambda: am.random.random(), self.model)
            am.random.setstate(state)
        S = check("mv_shadow", lambda: probe["mv_shadow"](self, self.model, am, fn), self.model)
        if S is not None:
            stats["mv_row:%s" % S["kind"]] += 1
            if S["acted"]:
                stats["acted:%s" % S["acted"]] += 1
        return r

    o_kick = wf.WildFireModel._try_dispatch_unresolved_confirmed_victims

    def kick(self, *a, **k):
        K = check("kick_shadow", lambda: probe["kick_shadow"](self, am, udm, fae, udm.urgency_order,
                                                              select_rescue_assignment), self)
        if K.get("qualifies"):
            stats["kick_qualifying"] += 1
        if K.get("acc") is not None:
            # v2: the planner acceptance reading (snapshot + select_rescue_assignment per W victim) ran inside check()
            stats["kick_acc_read"] += 1
            stats["kick_acc_planner_calls"] += len(K["acc"])
            if not all(K["acc"].values()):
                stats["kick_acc_with_refused_victim"] += 1
        return o_kick(self, *a, **k)

    am.Firefighter._refresh_target_from_victim = refresh
    wf.WildFireModel._try_dispatch_unresolved_confirmed_victims = kick
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        model = wf.WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()
    print("purity: %d steps in %.0f s (snapshots %.0f s); switches %r" % (
        steps, time.perf_counter() - t0, t_snap[0], extra))
    controls = [f for f in failures if f[0].startswith("control")]
    failures = [f for f in failures if not f[0].startswith("control")]
    print("  shadow points checked:", dict(stats))
    print("  positive controls detected: %d of %d %s" % (
        len(controls), stats["control_unit"] + stats["control_rng"], controls))
    print("  failures:", failures if failures else "NONE")
    return 0 if not failures and len(controls) == 2 else 1


class _MP:
    """A minimal monkeypatch stand-in for tests/urgency_test_support (this process exits after the check)."""

    def setattr(self, obj, name, value, raising=True):
        setattr(obj, name, value)


def kick_synthetic(probe, rec, cols, ag, udm, fae, T, mp, expect):
    """ud_probe v2's kick fields (R2 B-1 / B-2).
    (1) PURE: _ud_probe.kick_flags / bind_flags on hand-built records.
    (2) REAL: one free unit FF_A at (30, 20), victims V0 (10, 12), V1 (40, 30), V2 (20, 40), one burning cell
    (25, 10), wind north; U1's estimator is replaced by a crafted T (V1 100 < V0 200 < V2 300, else 1000; tests'
    _crafted_t), so U1 = [V1, V0, V2] against the index order [V0, V1, V2]. A victim is REFUSED by the planner through
    state.cancelled (W keeps her: a reset_victim_pending relabel leaves marker / state 'confirmed'). The real kick
    runs through install()'s wraps in both arms (DISPATCH_URGENCY 0 / 1) for four refusal sets."""
    import numpy as np
    from src_extension.planning.rescue_planner import select_rescue_assignment

    kf, bf = probe["kick_flags"], probe["bind_flags"]

    def flags(index, u1, acc, qualifies, bound):
        K = {"index": index, "u1": u1, "acc": acc, "qualifies": qualifies}
        kf(K)
        bf(K, bound)
        return {k: K[k] for k in ("index_wb", "u1_wb", "div_shadow", "divergent", "div_shadow_head",
                                  "divergent_head")}

    def want(iw, uw, ds, dv, dsh, dvh):
        return {"index_wb": iw, "u1_wb": uw, "div_shadow": ds, "divergent": dv, "div_shadow_head": dsh,
                "divergent_head": dvh}

    i3, u3 = ["v0", "v1", "v2"], ["v1", "v0", "v2"]
    pure = (
        # index [v0 refused, v1, v2], u1 [v1, v0, v2]: both orders WOULD BIND v1 -> NOT divergent (v1 heads: True)
        ("pure/refused index head, ON bind v1", (i3, u3, {"v0": False, "v1": True, "v2": True}, True, [["v1", "f"]]),
         want("v1", "v1", False, False, True, True)),
        ("pure/refused index head, OFF bind v1", (i3, u3, {"v0": False, "v1": True, "v2": True}, True, [["v1", "f"]]),
         want("v1", "v1", False, False, True, True)),
        # every W victim refused: nothing would bind, binds 0, nothing divergent
        ("pure/all refused, binds 0", (i3, u3, {"v0": False, "v1": False, "v2": False}, True, []),
         want(None, None, False, False, True, False)),
        # a refused U1 head: index [v0, v1 refused, v2], u1 [v1, v0, v2] -> both bind v0
        ("pure/refused U1 head", (i3, u3, {"v0": True, "v1": False, "v2": True}, True, [["v0", "f"]]),
         want("v0", "v0", False, False, True, False)),
        # a genuine divergence: ON binds v1, OFF binds v0
        ("pure/genuine divergence ON", (i3, u3, {"v0": True, "v1": True, "v2": True}, True, [["v1", "f"]]),
         want("v0", "v1", True, True, True, True)),
        ("pure/genuine divergence OFF", (i3, u3, {"v0": True, "v1": True, "v2": True}, True, [["v0", "f"]]),
         want("v0", "v1", True, False, True, False)),
        # a non-qualifying kick is never divergent
        ("pure/not qualifying", (i3, u3, {"v0": False, "v1": True, "v2": True}, False, [["v1", "f"]]),
         want("v1", "v1", False, False, False, False)),
        # no planner reading (acc None): no would-bind victim, nothing divergent
        ("pure/acc None", (i3, None, None, False, []), want(None, None, False, False, False, False)),
    )
    for label, args, w in pure:
        got = flags(*args)
        expect(label, got == w, "got %r want %r" % (got, w))

    # ---- (2) the real kick
    cells = {T.V0: (10, 12), T.V1: (40, 30), T.V2: (20, 40)}
    crafted = {cells[T.V1]: 100.0, cells[T.V0]: 200.0, cells[T.V2]: 300.0}
    o_at = udm.arrival_time

    def fake(x_size, y_size, burning, wind, params):
        grid = np.full((x_size, y_size), 1000.0)
        for cell, value in crafted.items():
            grid[cell] = value
        return grid

    V0, V1, V2, FA = T.V0, T.V1, T.V2, T.FF_A
    order_i, order_u = [V0, V1, V2], [V1, V0, V2]
    #        refused        index_wb u1_wb div_shadow  OFF: bound divergent(_head)    ON: bound divergent(_head)
    cases = (({V0}, V1, V1, False, True, V1, False, True, V1, False, True),
             ({V0, V1, V2}, None, None, False, True, None, False, False, None, False, False),
             (set(), V0, V1, True, True, V0, False, False, V1, True, True),
             ({V1}, V0, V0, False, True, V0, False, False, V0, False, False))
    udm.arrival_time = fake
    try:
        for urgency in (0, 1):
            T.switches(mp, urgency=urgency)
            with contextlib.redirect_stdout(io.StringIO()):
                model = T.pinned_model(mp, seed=9613)
            expect("kick/u=%d switch effective" % urgency, ag.dispatch_urgency() == bool(urgency))
            for (refused, iw, uw, ds, dsh, off_b, off_dv, off_dvh, on_b, on_dv, on_dvh) in cases:
                label = "kick/u=%d/refused %s" % (urgency, sorted(refused) or "none")
                T.quiet_fire(model)
                model.wind.wind_direction = "north"
                T.place_units(model, {FA: (30, 20)})
                T.place_victims(model, cells)
                T.burn(model, [(25, 10)])
                T.set_step(model, 100)
                for vid in refused:
                    model.managed_victims[vid].cancelled = True
                # DEEP purity of the kick shadow WITH the planner reading on this multi-victim board (the purity
                # subcommand's snapshot: every agent, the model to depth 3, the grid, the RNGs), in the probe's own
                # shadow context (rec["inst"] raised, as install()'s kick does)
                before = snapshot(model, ag)
                rec["inst"] += 1
                try:
                    Ks = probe["kick_shadow"](model, ag, udm, fae, udm.urgency_order, select_rescue_assignment)
                finally:
                    rec["inst"] -= 1
                expect(label + " deep purity of kick_shadow + planner reading", snapshot(model, ag) == before
                       and Ks["acc"] == {v: v not in refused for v in order_i}, repr(Ks["acc"]))
                k0, m0, d0, e0 = len(rec["kicks"]), len(rec["mismatch"]), len(rec["decisions"]), len(rec["ud_errors"])
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    model._try_dispatch_unresolved_confirmed_victims()
                if len(rec["kicks"]) != k0 + 1:
                    expect(label + " recorded", False, "no kick record")
                    continue
                K = rec["kicks"][-1]
                b, dv, dvh = (on_b, on_dv, on_dvh) if urgency else (off_b, off_dv, off_dvh)
                acc_want = {v: v not in refused for v in order_i}
                ran = order_u if urgency else order_i
                att_want = [[v, v == b] for v in ran]
                expect(label + " qualifies, index, u1", K["qualifies"] and K["index"] == order_i and K["u1"] == order_u,
                       repr((K["qualifies"], K["index"], K["u1"])))
                expect(label + " acc", K["acc"] == acc_want, repr(K["acc"]))
                expect(label + " index_wb / u1_wb", (K["index_wb"], K["u1_wb"]) == (iw, uw),
                       repr((K["index_wb"], K["u1_wb"])))
                expect(label + " div_shadow / div_shadow_head", (K["div_shadow"], K["div_shadow_head"]) == (ds, dsh),
                       repr((K["div_shadow"], K["div_shadow_head"])))
                expect(label + " bound", K["bound"] == ([[b, FA]] if b else []), repr(K["bound"]))
                expect(label + " divergent / divergent_head", (K["divergent"], K["divergent_head"]) == (dv, dvh),
                       repr((K["divergent"], K["divergent_head"])))
                expect(label + " attempts", K["attempts"] == att_want, "got %r want %r" % (K["attempts"], att_want))
                expect(label + " no shadow mismatch", len(rec["mismatch"]) == m0, repr(rec["mismatch"][m0:]))
                expect(label + " no instrument error", len(rec["ud_errors"]) == e0, repr(rec["ud_errors"][e0:]))
                decs = rec["decisions"][d0:]
                expect(label + " decisions accepted / index_wb / u1_wb",
                       [(x["vid"], x["accepted"], x["index_wb"], x["u1_wb"], x["served"]) for x in decs]
                       == [(v, v not in refused, v == iw, v == uw, v == b) for v in order_i], repr(decs))
                expect(label + " kick record consistent (kicks check)", not kick_problems(K, bool(urgency)),
                       repr(kick_problems(K, bool(urgency))))
                if urgency:
                    tri = [x for x in out.getvalue().splitlines() if x.startswith("[UrgencyTriage]")]
                    expect(label + " triage served", len(tri) == 1 and tri[0].endswith("served=%s" % (b or "none")),
                           repr(tri))
                if urgency == 0 and not refused:
                    # dcb on an APPROACH row (R3 D-16): FF_A bound to V0, one advance from (30, 20); the nearest clean
                    # boundary cell is x = 49 (19 hops; the only fire is (25, 10) and its neighbours)
                    n0 = len(rec["mv_rows"])
                    with contextlib.redirect_stdout(io.StringIO()):
                        T.ff(model, FA).advance()
                    row = dict(zip(cols, rec["mv_rows"][-1])) if len(rec["mv_rows"]) == n0 + 1 else {}
                    expect("approach row dcb", row.get("leg") == "approach" and row.get("dcb") == 19
                           and row.get("pre") == [30, 20], repr({k: row.get(k) for k in ("leg", "pre", "dcb", "dc")}))

        # POSITIVE CONTROLS, after the loop: the u = 1 model and switches. Each must be SEEN; its rows are then removed
        expect("control/arm is ON", ag.dispatch_urgency() is True)

        def scene():
            T.quiet_fire(model)
            model.wind.wind_direction = "north"
            T.place_units(model, {FA: (30, 20)})
            T.place_victims(model, cells)
            T.burn(model, [(25, 10)])
            T.set_step(model, 100)

        def run_kick():
            with contextlib.redirect_stdout(io.StringIO()):
                model._try_dispatch_unresolved_confirmed_victims()

        # (a) the shadow-mismatch detector: the MODEL's order is reversed behind the shadow's back (the shadow calls
        # the original urgency_order), so the ON kick binds V2 while u1_wb is V1
        scene()
        m0 = len(rec["mismatch"])
        o_order = udm.urgency_order

        def reversed_order(*a, **k):
            ordered, records = o_order(*a, **k)
            return list(reversed(ordered)), records

        udm.urgency_order = reversed_order
        try:
            run_kick()
        finally:
            udm.urgency_order = o_order
        rows = rec["mismatch"][m0:]
        expect("control/shadow mismatch detected", len(rows) == 1 and rows[0][2] == "u1" and rows[0][5:] == [V1, V2],
               repr(rows))
        del rec["mismatch"][m0:]
        # (b) the in-run kick purity guard: a planner snapshot that writes a victim marker, then one that draws from
        # agents.random - both inside the kick shadow
        WMc = type(model)
        o_snap = WMc.get_rescue_operational_snapshot
        for what, dirty in (("marker", lambda self: setattr(self.victim_marker_agents[V2], "_ud_ctl", 1)),
                            ("rng", lambda self: ag.random.random())):
            scene()
            e0 = len(rec["ud_errors"])

            def snap(self, _dirty=dirty):
                _dirty(self)
                return o_snap(self)

            WMc.get_rescue_operational_snapshot = snap
            try:
                run_kick()
            finally:
                WMc.get_rescue_operational_snapshot = o_snap
                if hasattr(model.victim_marker_agents[V2], "_ud_ctl"):
                    delattr(model.victim_marker_agents[V2], "_ud_ctl")
            errs = rec["ud_errors"][e0:]
            seen = [e for e in errs if e.startswith("kick_purity") and (
                "victim_marker_agents[%s]" % V2 if what == "marker" else "rng state") in e]
            expect("control/kick purity guard sees a %s change" % what, len(seen) == 1, repr(errs))
            del rec["ud_errors"][e0:]
    finally:
        udm.arrival_time = o_at


def synthetic():
    """The carry-leg recorders and the C-4 / C-5 detectors on hand-built boards, through the probe's own install()
    (every wrap live) and the REAL Firefighter.advance / lookup / casualty sweep: a carrier at (25, 25) with victim_0,
    exit target (0, 25), on four boards, with FF_CARRY_REPLAN 1 and 0."""
    sys.path.insert(0, REPO)
    sys.path.insert(0, os.path.join(REPO, "tests"))
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as ag
    import common_fixed_variables as cfv
    import wildfire_model as wf
    import src_extension.adaptation_manager as amod
    import src_extension.adaptation.local_adaptation_generator as gen
    from src_extension.planning import fire_arrival_estimate as fae
    from src_extension.planning import urgency_dispatch as udm
    import urgency_test_support as T

    probe = runpy.run_path(os.path.join(HERE, "_ud_probe.py"), run_name="ud_probe_module")
    rec = probe["install"](ag, cfv, wf, amod, gen, fae, udm)
    cols = list(probe["MV_COLS"])
    mp = _MP()
    results = []

    def expect(label, cond, detail=""):
        results.append((label, bool(cond), detail))

    perim = [(x, y) for x in range(20, 31) for y in range(20, 31) if x in (20, 30) or y in (20, 30)]
    boards = (("quiet", []), ("gap", [c for c in perim if c != (30, 25)]), ("pocket", perim),
              ("enclosed", [(26, 25), (24, 25), (25, 26), (25, 24)]))

    def carrier(model):
        T.quiet_fire(model)
        T.place_units(model, {T.FF_A: (25, 25)})
        T.place_victims(model, {T.V0: (25, 25)})
        assert T.assign(model, T.V0, T.FF_A)
        u = T.ff(model, T.FF_A)
        u.exiting = True
        u.exit_target = (0, 25)
        return u

    want = {
        1: {"quiet": ("c0", "", "path", None), "gap": ("c1", "c", "replan", [26, 25]),
            "pocket": ("c2s", "c", "shelter_stay", [25, 25]), "enclosed": ("c3", "c", "hold", [25, 25])},
        0: {"quiet": ("path", "", "path", None), "gap": ("fallback", "c", "replan", [24, 25]),
            "pocket": ("fallback", "c", "shelter_stay", [24, 25]), "enclosed": ("fallback_raise", "c", "hold", [25, 25])},
    }
    for carry in (1, 0):
        T.switches(mp, carry=carry)
        with contextlib.redirect_stdout(io.StringIO()):
            model = T.pinned_model(mp, seed=9613)
        expect("carry=%d effective" % carry, ag.ff_carry_replan() == bool(carry))
        for name, cells in boards:
            u = carrier(model)
            T.burn(model, cells)
            n0, e0 = len(rec["mv_rows"]), len(rec["mv_events"])
            with contextlib.redirect_stdout(io.StringIO()):
                u.advance()
            if len(rec["mv_rows"]) != n0 + 1:
                expect("%d/%s row" % (carry, name), False, "no mv row")
                continue
            row = dict(zip(cols, rec["mv_rows"][-1]))
            br, acted, kind, post = want[carry][name]
            got = (row["branch"], row["acted"], row["fc"][0], row["post"])
            ok = row["branch"] == br and row["acted"] == acted and row["fc"][0] == kind and (
                post is None or row["post"] == post)
            expect("%d/%s branch/acted/kind/post" % (carry, name), ok, "got %r today %r fc %r" % (
                got, row["today"], row["fc"]))
            evs = rec["mv_events"][e0:]
            if acted:
                ev = evs[0] if evs else {}
                expect("%d/%s event" % (carry, name), ev.get("kind") == "c" and ev.get("live") == bool(carry)
                       and (ev.get("agree") is True if carry else ev.get("agree") is None), json.dumps(ev))
            else:
                expect("%d/%s no event" % (carry, name), not evs, json.dumps(evs))
            if name == "gap":
                expect("%d/gap c1 cost" % carry, row["c1_pre"] == [1, 0, 24] and row["c1_post"] == (
                    [1, 0, 23] if carry else [1, 0, 25]), "pre %r post %r" % (row["c1_pre"], row["c1_post"]))
                expect("%d/gap distances" % carry, row["dc"] is None and row["df"] is not None and row["dr"] == row["df"],
                       "dc %r df %r dm %r dr %r" % (row["dc"], row["df"], row["dm"], row["dr"]))
            if name == "enclosed":
                expect("%d/enclosed today raise" % carry, row["today"][0] == "raise" and row["today"][3] is True,
                       repr(row["today"]))
                expect("%d/enclosed raise count" % carry, row["rb_call"] == (0 if carry else 1),
                       "rb_call %r rb_set %r" % (row["rb_call"], row["rb_set"]))
            if name == "pocket":
                expect("%d/pocket c1 none" % carry, row["c1_pre"] is None and row["gesc"] is False,
                       "c1 %r gesc %r" % (row["c1_pre"], row["gesc"]))
        # C-4: an exiting carrier labelled route_blocked, bound to victim_0
        u = carrier(model)
        u.status = "route_blocked"
        e0 = len(rec["mv_events"])
        out = model._find_active_firefighter_for_victim(T.V0, T.victim(model, T.V0))
        evs = [e for e in rec["mv_events"][e0:] if e["kind"] == "C4"]
        expect("%d/C-4 lookup" % carry, (out is not None) == bool(carry), repr(out))
        expect("%d/C-4 event" % carry, len(evs) == 1 and evs[0]["live"] == bool(carry) and evs[0]["unit"] == T.FF_A,
               json.dumps(evs))
        # C-5: the carrier's (and its victim's) cell burns; the real casualty sweep
        u = carrier(model)
        T.burn(model, [(25, 25)])
        e0, c0 = len(rec["mv_events"]), len(rec["commands"])
        with contextlib.redirect_stdout(io.StringIO()):
            model._check_fire_casualties()
        evs = [e for e in rec["mv_events"][e0:] if e["kind"] == "C5"]
        cas = [c for c in rec["commands"][c0:] if c[5] == "firefighter_fire_casualty"]
        expect("%d/C-5 event" % carry, len(evs) == 1 and evs[0]["live"] == bool(carry)
               and evs[0]["no_reset"] == bool(carry), json.dumps(evs))
        expect("%d/C-5 casualty command recorded" % carry, len(cas) == 1, repr(cas))
    # dcb on the carry boards (R3 D-16): on carry rows dcb == dc; quiet board: 24 hops from (25, 25) on 50 x 50
    carry_rows = [dict(zip(cols, r)) for r in rec["mv_rows"] if r[cols.index("leg")] == "carry"
                  and r[cols.index("today")] is not None]
    expect("dcb == dc on every carry row", carry_rows and all(r["dcb"] == r["dc"] for r in carry_rows),
           repr([(r["dcb"], r["dc"]) for r in carry_rows]))
    expect("dcb on the quiet / pocket boards", sorted({r["dcb"] for r in carry_rows}, key=repr) == [24, None],
           repr(sorted({r["dcb"] for r in carry_rows}, key=repr)))
    kick_synthetic(probe, rec, cols, ag, udm, fae, T, mp, expect)
    expect("no instrument errors", not rec["ud_errors"] and not rec["errors"], repr(rec["ud_errors"] + rec["errors"]))
    expect("no shadow mismatch", not rec["mismatch"], repr(rec["mismatch"]))
    expect("cmd_ctx aligned", len(rec["cmd_ctx"]) == len(rec["commands"]))
    for label, ok, detail in results:
        print("%-4s %s %s" % ("OK" if ok else "FAIL", label, "" if ok else detail))
    bad = [r for r in results if not r[1]]
    print("synthetic: %d checks, %d failed" % (len(results), len(bad)))
    return 0 if not bad else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "compare":
        return compare(sys.argv[2], sys.argv[3])
    if cmd == "summary":
        return summary(sys.argv[2])
    if cmd == "pair":
        return pair(sys.argv[2], sys.argv[3])
    if cmd == "synthetic":
        return synthetic()
    if cmd == "kicks":
        return kicks(sys.argv[2])
    if cmd == "purity":
        return purity(int(sys.argv[2]), sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
