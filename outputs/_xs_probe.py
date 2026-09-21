"""Exit-stall round, Part 1 DIAGNOSIS PROBE - out of tree, no source file is modified.

Runs outputs/_ffr_harness.py UNCHANGED in this same process (or, when FM2P_CRN is in the
--set list, outputs/_fm2_probe_harness.py, which itself runs _ffr_harness unchanged),
after wrapping a few attributes of the --repo checkout's classes. Every key is read from
common_fixed_variables at CALL time; the harness puts every --set KEY=VALUE there before
the model is built, so the keys appear in the run JSON's params/extra_params like any
other --set and the pool validator checks them against the queue.

KEYS
  XS_TRACE=1        record, per firefighter per advance():
                      - every instance field (all of vars(unit) with a plain value, so no
                        mode field can be missed) BEFORE the advance, and pos AFTER it
                      - the fire around the unit (radius 3) and at the exit target
                      - _firefight_prepare's return (None, or T/K/plan/suspended/guard)
                      - every grid move of the unit during the advance, with the call
                        chain that made it (which movement function chose the step)
                      - inside _move_toward: every neighbour with its tier tests,
                        recomputed from the unit's own pure helpers, and the tier the
                        function reports - a mismatch with the actual step is flagged
                      - on a CARRYING advance (exiting at entry): the set of attribute
                        names read on the unit and every ff_firefight_* accessor call
                      - moves of the unit OUTSIDE its own advance (model-side), with
                        their call chain, and field changes between two advances
                    Pure reads: no RNG draw, no attribute created on a model or agent.
                    Written to <out minus .json>.xstrace.json after the harness finished.
  XS_RESET=exit     COUNTERFACTUAL: on every carrying advance, before it runs, clear the
                    firefighting/idle-mode fields (_firefight_suspended -> False when it
                    exists; _reset_idle_retreat_state()). If the carrying legs are
                    unchanged, no such field influences the carrying leg.
  XS_RESET=assign   COUNTERFACTUAL: the same clearing on the first advance after a new
                    assignment (target_pos newly set, not exiting): does state left by
                    the idle/firefighting mode steer the APPROACH leg?

WITH NO XS_* KEY SET EVERY WRAP IS A PASS-THROUGH. The trace arm (XS_TRACE only) must be
value-identical to the recorded run it replays - checked by outputs/_xs_analyze.py.
"""
from __future__ import annotations

import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "_ffr_harness.py")
CRN_HARNESS = os.path.join(HERE, "_fm2_probe_harness.py")
RADIUS = 3
PLAIN = (bool, int, float, str, type(None))


def _argv_value(flag):
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def _plain(v):
    if isinstance(v, PLAIN):
        return v
    if isinstance(v, (tuple, list)) and all(isinstance(x, PLAIN) for x in v):
        return list(v)
    return None


def install(repo):
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import mesa  # noqa: E402
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402

    FF = am.Firefighter
    rec = {"advances": [], "outside_moves": [], "between_changes": [], "move_toward": [],
           "accessor_calls": [], "resets": [], "errors": []}
    st = {"cur": None, "carrying": False, "reads": None, "moves": None, "fire_step": None,
          "fire": None, "last_after": {}, "last_target": {}, "mute": False}

    def key(name):
        v = getattr(cfv, name, None)
        return None if v in (None, "", "none", "None", 0, "0") else v

    def step_of(model):
        return int(getattr(model, "evaluation_timesteps_counter", 0) or 0)

    def fire_map(model):
        s = step_of(model)
        if st["fire_step"] == s and st["fire"] is not None:
            return st["fire"]
        m = {}
        for a in model.schedule.agents:
            if type(a) is not am.Fire:
                continue
            p = getattr(a, "pos", None)
            if p is None:
                continue
            c = (int(p[0]), int(p[1]))
            sm = getattr(a, "smoke", None)
            smoke = bool(sm is not None and sm.is_smoke_active())
            if a.is_burning():
                code = "F"
            elif smoke:
                code = "s"
            elif a.is_burnt() or not (a.fuel > 0):
                code = "_"
            else:
                code = "."
            m[c] = code
        st["fire_step"], st["fire"] = s, m
        return m

    def window(model, cell):
        m = fire_map(model)
        g = model.grid
        rows = []
        for dy in range(RADIUS, -RADIUS - 1, -1):          # north (y+) at the top
            row = ""
            for dx in range(-RADIUS, RADIUS + 1):
                c = (cell[0] + dx, cell[1] + dy)
                if g.out_of_bounds(c):
                    row += "#"
                elif dx == 0 and dy == 0:
                    row += "U" if m.get(c, ".") in (".", "_") else m.get(c, ".").upper()
                else:
                    row += m.get(c, ".")
            rows.append(row)
        return rows

    def fields(u):
        out = {}
        for k, v in vars(u).items():
            if k in ("model",):
                continue
            if k == "rescued_victim":
                out[k] = None if v is None else str(getattr(v, "victim_id", getattr(v, "unique_id", "?")))
                continue
            if k == "movement_reason":
                out["movement_reason.fine_category"] = (v or {}).get("fine_category") if isinstance(v, dict) else None
                continue
            pv = _plain(v)
            if pv is not None or v is None:
                out[k] = pv
        return out

    def chain(depth=9):
        names = []
        f = sys._getframe(2)
        while f is not None and len(names) < depth:
            n = f.f_code.co_name
            if not n.startswith("_hook") and n not in ("wrapped", "_obs_advance"):
                names.append(n)
            f = f.f_back
        return names

    # ---- grid moves --------------------------------------------------------------
    G = mesa.space.MultiGrid
    orig_move = G.move_agent

    def _hook_move(self, agent, pos):
        if key("XS_TRACE") and isinstance(agent, FF):
            st["mute"] = True
            try:
                frm = None if agent.pos is None else [int(agent.pos[0]), int(agent.pos[1])]
                entry = {"from": frm, "to": [int(pos[0]), int(pos[1])], "chain": chain()}
                if st["cur"] is agent and st["moves"] is not None:
                    st["moves"].append(entry)
                else:
                    entry.update({"step": step_of(agent.model), "ff": str(agent.unit_id)})
                    rec["outside_moves"].append(entry)
            except Exception as exc:
                rec["errors"].append(repr(exc))
            finally:
                st["mute"] = False
        return orig_move(self, agent, pos)

    G.move_agent = _hook_move

    # ---- attribute reads on a carrying advance ----------------------------------------
    orig_getattribute = FF.__getattribute__

    def _hook_getattribute(self, name):
        if st["reads"] is not None and not st["mute"] and st["cur"] is self and not name.startswith("__"):
            st["reads"].add(name)
        return orig_getattribute(self, name)

    FF.__getattribute__ = _hook_getattribute

    # ---- ff_firefight_* accessors: who reads them, and on which kind of advance ------
    for acc in ("ff_firefight_extinguish", "ff_firefight_firebreak", "ff_firefight_engaged_retreat_range",
                "ff_firefight_dry_run", "ff_firefight_mission_gate"):
        if not hasattr(am, acc):
            continue
        orig_acc = getattr(am, acc)

        def make(name, fn):
            def wrapped(*a, **k):
                if key("XS_TRACE") and st["cur"] is not None and st["carrying"]:
                    st["mute"] = True
                    try:
                        rec["accessor_calls"].append({"step": step_of(st["cur"].model), "ff": str(st["cur"].unit_id),
                                                      "accessor": name, "chain": chain(5)})
                    finally:
                        st["mute"] = False
                return fn(*a, **k)
            wrapped.__name__ = fn.__name__
            return wrapped
        setattr(am, acc, make(acc, orig_acc))

    # ---- _firefight_prepare's return --------------------------------------------------
    prep_box = {}
    if hasattr(FF, "_firefight_prepare"):
        orig_prep = FF._firefight_prepare

        def _hook_prepare(self):
            ctx = orig_prep(self)
            if key("XS_TRACE") and st["cur"] is self:
                prep_box["v"] = None if ctx is None else {
                    "T": ctx.get("T"), "K": ctx.get("K"), "suspended": ctx.get("suspended"),
                    "exit_guard": ctx.get("exit_guard"), "dist": ctx.get("dist"),
                    "plan": None if ctx.get("plan") is None else [ctx["plan"][0], list(ctx["plan"][1])]}
            return ctx

        _hook_prepare.__qualname__ = orig_prep.__qualname__
        FF._firefight_prepare = _hook_prepare

    # ---- _move_toward: the tier tests, recomputed with the unit's own pure helpers ----
    orig_mt = FF._move_toward

    def _hook_move_toward(self, target):
        info = None
        if key("XS_TRACE") and st["cur"] is self:
            st["mute"] = True
            try:
                tx, ty = int(target[0]), int(target[1])
                cx, cy = int(self.pos[0]), int(self.pos[1])
                dx, dy = tx - cx, ty - cy
                if abs(dx) >= abs(dy):
                    pref = (cx + (1 if dx > 0 else -1 if dx < 0 else 0), cy)
                else:
                    pref = (cx, cy + (1 if dy > 0 else -1 if dy < 0 else 0))
                before = abs(dx) + abs(dy)
                nbs = []
                for c in self._neighbor_cells():
                    fire = self._cell_contains_active_fire(c)
                    da = abs(c[0] - tx) + abs(c[1] - ty)
                    nbs.append({"cell": [c[0], c[1]], "fire": fire, "adj_fire": self._cell_adjacent_to_fire(c),
                                "smoke": self._cell_has_active_smoke(c), "dist_after": da,
                                "improving": da < before, "maintaining": da == before, "preferred": c == pref})
                info = {"target": [tx, ty], "dist_before": before, "exiting": bool(self.exiting),
                        "neighbours": nbs}
            except Exception as exc:
                rec["errors"].append(repr(exc))
            finally:
                st["mute"] = False
        result = orig_mt(self, target)
        if info is not None:
            st["mute"] = True
            try:
                info["chosen"] = None if self.pos is None else [int(self.pos[0]), int(self.pos[1])]
                info["tier"] = getattr(self, "_last_move_tier", None)
                info["status_after"] = getattr(self, "status", None)
                st.setdefault("mt", []).append(info)
            finally:
                st["mute"] = False
        return result

    _hook_move_toward.__qualname__ = orig_mt.__qualname__
    FF._move_toward = _hook_move_toward

    # ---- advance: the per-step record, and the counterfactual resets -------------------
    orig_adv = FF.advance

    def _hook_advance(self):
        trace = bool(key("XS_TRACE"))
        reset = key("XS_RESET")
        uid = str(getattr(self, "unit_id", "?"))
        if self.pos is None or getattr(self, "dead", False) or not (trace or reset):
            return orig_adv(self)
        s = step_of(self.model)
        carrying = bool(self.exiting)
        new_assign = bool(self.target_pos) and not carrying and st["last_target"].get(uid) is None
        if reset in ("exit", "assign") and ((reset == "exit" and carrying) or (reset == "assign" and new_assign)):
            before_reset = {k: v for k, v in fields(self).items() if "firefight" in k or "idle_retreat" in k}
            if hasattr(self, "_firefight_suspended"):
                self._firefight_suspended = False
            self._reset_idle_retreat_state()
            after_reset = {k: v for k, v in fields(self).items() if "firefight" in k or "idle_retreat" in k}
            if before_reset != after_reset:
                rec["resets"].append({"step": s, "ff": uid, "kind": reset, "before": before_reset})
        if not trace:
            st["last_target"][uid] = None if not self.target_pos else tuple(self.target_pos)
            return orig_adv(self)
        f0 = fields(self)
        prev = st["last_after"].get(uid)
        if prev is not None:
            changed = {k: [prev.get(k), f0.get(k)] for k in set(prev) | set(f0)
                       if prev.get(k) != f0.get(k) and k != "movement_reason.fine_category"}
            if changed:
                rec["between_changes"].append({"step": s, "ff": uid, "changed": changed})
        cell = (int(self.pos[0]), int(self.pos[1]))
        et = getattr(self, "exit_target", None)
        row = {"step": s, "ff": uid, "carrying": carrying, "pos": [cell[0], cell[1]], "fields": f0,
               "fire": window(self.model, cell),
               "exit_target_fire": None if not et else fire_map(self.model).get((int(et[0]), int(et[1])), "."),
               "nearest_fire": self._min_fire_distance(cell, self._fire_cells())}
        st["cur"], st["carrying"], st["moves"], st["mt"] = self, carrying, [], []
        st["reads"] = set() if carrying else None
        prep_box.clear()
        try:
            result = orig_adv(self)
        finally:
            row["moves"] = st["moves"]
            row["move_toward"] = st.get("mt") or []
            row["prepare"] = prep_box.get("v", "not called")
            if carrying:
                row["reads"] = sorted(st["reads"])
            st["cur"], st["carrying"], st["moves"], st["reads"], st["mt"] = None, False, None, None, []
        row["pos_after"] = None if self.pos is None else [int(self.pos[0]), int(self.pos[1])]
        row["reason_after"] = (getattr(self, "movement_reason", None) or {}).get("fine_category")
        row["tier_after"] = getattr(self, "_last_move_tier", None)
        rec["advances"].append(row)
        st["last_after"][uid] = fields(self)
        st["last_target"][uid] = None if not self.target_pos else tuple(self.target_pos)
        return result

    _hook_advance.__qualname__ = orig_adv.__qualname__
    FF.advance = _hook_advance
    return {"cfv": cfv, "rec": rec}


def main():
    repo = _argv_value("--repo")
    out = _argv_value("--out")
    if repo is None or out is None:
        print("XS: --repo and --out are required", file=sys.stderr)
        return 2
    state = install(os.path.abspath(repo))
    crn = any(a.replace(" ", "").startswith("FM2P_CRN=") for a in sys.argv[1:])
    target = CRN_HARNESS if crn else HARNESS
    sys.argv = [target] + sys.argv[1:]
    code = 0
    try:
        if crn:
            sys.path.insert(0, HERE)
            import _fm2_probe_harness as fm2  # noqa: E402
            code = int(fm2.main() or 0)
        else:
            runpy.run_path(HARNESS, run_name="__main__")
    except SystemExit as exc:
        code = int(exc.code or 0) if not isinstance(exc.code, str) else 1
    if code != 0:
        return code
    cfv = state["cfv"]
    config = {k: getattr(cfv, k) for k in ("XS_TRACE", "XS_RESET") if getattr(cfv, k, None) not in (None, "", 0)}
    if config.get("XS_TRACE"):
        path = out[:-5] + ".xstrace.json" if out.endswith(".json") else out + ".xstrace.json"
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"config": config, "argv": sys.argv[1:], **state["rec"]}, f, separators=(",", ":"))
        os.replace(tmp, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
