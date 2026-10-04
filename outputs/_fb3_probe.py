"""fix3b instrument: outputs/_fx3_probe.py (UNCHANGED) plus a CRN switch and read-only fix3b recorders.

usage: _fb3_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args ...>

  --crn     common random numbers for the fire: Fire.step's single draw becomes crn_uniform(seed, cell
            unique_id, cell steps_counter) - EXACTLY outputs/_fm2_probe_harness.py's FM2P_CRN=1 construction
            (crn_uniform imported from it). The JSON records fb3.crn.crn_draws; a CRN run with 0 draws is
            invalid. CRN arms compare only with CRN arms.
  --hazard  passed through to _fx3_probe.py.
  --instrument  bayesprep item 3: the record-only calibration instrument (fix3b_part1.txt 18.4, bayesprep_part1.txt
            section 3). Adds d["fb3"]["inst"] and d["fb3"]["bp_switches"] and NOTHING else; without the flag no
            instrument code is installed and the output is exactly the probe's as before. Its format, the shared
            arithmetic and the offline replay / readers are documented in outputs/_bp_inst.py. Hook points (each a
            pass-through that calls the original once with the original arguments and returns its result):
              WildFireModel.step (first entry only: the launch inputs and the shadow beliefs' prior + launch measure),
              WildFireModel._init_victim_search_belief (identifies the run's own belief for the launch measure),
              WildFireModel._apply_monitoring_to_knowledge (after it returns: the post-move inputs, the shadows' update,
              the per-step record), VictimSearchBelief.measure / predict / burn_over (class level, acting ONLY when
              self is the model's own belief: r_k, the burn-over mass, the held targets' disc-mass change per stage,
              the arguments for the input check), searcher_targeting._bump (drop_swept / drop_covered events).
            No RNG draw, no write into the model or any model object; the shadow beliefs are the instrument's own
            objects; truth (victim cells) never leaves the probe. An observer exception is recorded, never raised.
  REFUSES any --set FM2P_CRN=...: _fx3_probe / _sd_probe accept that key and silently ignore it
  (outputs/fix3b_crn_audit.txt). CRN is requested with --crn only.

Adds d["fb3"] to the probe JSON (read-only observers; no RNG draw, no simulation write):
  crn        {"on": bool, "crn_draws": n}
  coverage   every 10 steps (and the last): [step, share of cells ever inside any UAV's Euclidean-8
             detection disc (the probe's own record, all arms), belief summary or None]
  spawn      {victim_id: [x, y]} at step 1 (before any move)
  stats      model._searcher_targeting_stats (per searcher: selections, give-ups, drops, fallbacks, ...)
  issued     model._searcher_targeting_issued: [step, uid, target, L, G, S, reachable_at_issue]
  timing     per-step ms of the belief update and the planner post-pass: {name: {n, median, p95, max, raw}}
  switches   the fix3b switch values the run saw
  inst, bp_switches   only with --instrument (above)
Adds d["mr"] (record-only, every run; rulings on the bayesprep report 2026-10-04): a pass-through hook on
  WildFireModel.MR2 records per step [t, the model's own MR2 increment, the same rule recomputed (pairs under
  SECURITY_DISTANCE), AIRBORNE pairs (neither UAV rtb_docked), pairs with one docked, pairs with both docked]; at the
  end mr1_list (the model's MR1_LIST, one entry per UAV), mr2_value, security_distance; errors (observer only).
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import math
import os
import runpy
import sys
import textwrap
import time
import traceback
import inspect

HERE = os.path.dirname(os.path.abspath(__file__))
FIX3B_KEYS = ("SEARCHER_TARGETING", "SEARCHER_TARGETING_COORDINATION", "SEARCHER_TARGETING_REACHABILITY",
              "SEARCHER_TARGETING_BATTERY", "SEARCHER_BELIEF_MOTION", "SEARCHER_TARGETING_RW_GATED",
              "SEARCHER_BELIEF_PD", "SEARCHER_BELIEF_PD_SMOKE", "SEARCHER_BELIEF_DIFFUSION_Q",
              "SEARCHER_BELIEF_FLEE_D50", "SEARCHER_BELIEF_FLEE_S", "SEARCHER_BELIEF_FLEE_P_GO",
              "SEARCHER_BELIEF_FLEE_BETA", "SEARCHER_BELIEF_FLEE_Q_CALM", "SEARCHER_BELIEF_BURNOVER",
              "SEARCHER_BELIEF_STRIDE", "SEARCHER_TARGETING_TOP_M", "SEARCHER_TARGETING_L0",
              "SEARCHER_TARGETING_SWEPT_RHO", "SEARCHER_TARGETING_MIN_DIST", "SEARCHER_TARGETING_GIVEUP_COOLDOWN",
              "SEARCHER_TARGETING_FALLBACK_HOLD", "SEARCHER_TARGETING_TILE", "SEARCHER_TARGETING_AGE_BUCKET",
              "VICTIM_SPAWN_MODE")


def _crn_uniform():
    spec = importlib.util.spec_from_file_location("_fm2_probe_harness_crn", os.path.join(HERE, "_fm2_probe_harness.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.crn_uniform


def _summ(values):
    if not values:
        return {"n": 0}
    s = sorted(values)
    return {"n": len(s), "median": s[len(s) // 2], "p95": s[min(len(s) - 1, int(math.ceil(0.95 * len(s))) - 1)],
            "max": s[-1], "raw": values}


# ---- bayesprep item 3: the record-only calibration instrument (--instrument only) ---------------------------------
FP_FIELDS = {"SEARCHER_FP_U10_KMH": "u10_kmh", "SEARCHER_FP_ROS_WIND_FRACTION": "ros_wind_fraction",
             "SEARCHER_FP_WALK_SPEED_MS": "walk_speed_ms", "SEARCHER_FP_WAF": "waf",
             "SEARCHER_FP_10M_TO_20FT": "k_20ft", "SEARCHER_FP_LW_PER_MPH": "lw_per_mph",
             "SEARCHER_FP_LW_MAX": "lw_max", "SEARCHER_FP_KAPPA": "kappa", "SEARCHER_FP_TAU": "tau"}


def _jsafe(v):
    return v if v is None or isinstance(v, (bool, int, float, str)) else repr(v)


def _load_bp_inst():
    spec = importlib.util.spec_from_file_location("_bp_inst_probe", os.path.join(HERE, "_bp_inst.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bp_switches(am, cfv) -> dict:
    """Raw + effective values of the round's switches and every SEARCHER_FP_* key."""
    from src_extension.planning.fire_arrival_estimate import front_priority_params
    fpp = dataclasses.asdict(front_priority_params())
    out = {"SEARCHER_TARGETING_FIX": {"raw": _jsafe(getattr(cfv, "SEARCHER_TARGETING_FIX", None)),
                                      "eff": bool(am.searcher_targeting_fix())},
           "UAV_DOCKED_NOT_OBSTACLE": {"raw": _jsafe(getattr(cfv, "UAV_DOCKED_NOT_OBSTACLE", None)),
                                       "eff": bool(am.uav_docked_not_obstacle())}}
    for k in sorted(n for n in dir(cfv) if n.startswith("SEARCHER_FP_")):
        out[k] = {"raw": _jsafe(getattr(cfv, k)), "eff": fpp.get(FP_FIELDS.get(k))}
    return out


class _Instrument:
    """The live recorder of outputs/_bp_inst.py's record. See the module docstring for the hook points."""

    def __init__(self, wf, am, cfv):
        from src_extension.knowledge import victim_search_belief as vsb
        from src_extension.planning import fire_arrival_estimate as fae
        import src_extension.planning.searcher_targeting as stg
        self.wf, self.am, self.cfv, self.vsb, self.fae, self.stg = wf, am, cfv, vsb, fae, stg
        self.bp = _load_bp_inst()
        self.clock = time.perf_counter
        self.model = None
        self.launched = False
        self.broken = False
        self.errors: list = []
        self.error_count = 0
        self.cur: dict = {}          # the own belief's captures during the current post-move update
        self.own_launch: dict = {}   # ... during the launch measure (inside WildFireModel.__init__)
        self.shadows: dict = {}      # name -> VictimSearchBelief (the instrument's own objects)
        self.names: list = []
        self.det: set = set()
        self.steps: list = []
        self.swept: list = []
        self.acc: dict = {}          # uid -> the held target's disc-mass accumulator
        self.issued_seen = 0
        self.mask_cache: dict = {}
        self.acc_ms = 0.0
        self.step_ms: list = []
        self.launch_ms = None
        self.launch = None
        self.mode = None
        self.own_cfg = None
        self.v3_shadow = None
        self.wind_cur = None
        self.wind_label = None
        self.prev_burn: set = set()
        self.prev_smoke: set = set()
        self.meta: dict = {}
        self.check = {"compared_steps": 0, "mismatch_steps": 0, "first_mismatch": None, "launch_match": None,
                      "inputs": {"compared": 0, "mismatch": 0, "first": None}, "order": {"steps": 0, "mismatch": 0}}

    # ---- bookkeeping -------------------------------------------------------------------------------------------
    def _err(self, exc):
        self.error_count += 1
        if len(self.errors) < 20:
            if isinstance(exc, BaseException):
                tb = traceback.extract_tb(exc.__traceback__)
                where = ("%s:%d" % (os.path.basename(tb[-1].filename), tb[-1].lineno)) if tb else "?"
                self.errors.append("%s @ %s" % (repr(exc)[:240], where))
            else:
                self.errors.append(str(exc)[:300])

    def _is_own(self, b) -> bool:
        m = self.model
        return m is not None and b is getattr(m, "victim_search_belief", None)

    def _disc(self, cell):
        mask = self.mask_cache.get(cell)
        if mask is None:
            b = self.model.victim_search_belief
            mask = self.vsb.disc_mask(int(b.height), int(b.width), [cell], b.offsets)
            self.mask_cache[cell] = mask
        return mask

    @staticmethod
    def _new_acc(target, since):
        return {"target": target, "since": since, "cov": 0.0, "mot": 0.0, "bo": 0.0, "n": 0, "disc_issue": None}

    def _sync_held(self) -> list:
        """The run's held targets now; an accumulator restarts at every issue (the planner's issued log)."""
        m = self.model
        issued = getattr(m, "_searcher_targeting_issued", None)
        if isinstance(issued, list) and len(issued) > self.issued_seen:
            for row in issued[self.issued_seen:]:
                self.acc[str(row[1])] = self._new_acc((int(row[2][0]), int(row[2][1])), int(row[0]))
            self.issued_seen = len(issued)
        held = []
        states = getattr(m, "_searcher_targeting_state", None)
        if isinstance(states, dict):
            for uid, st in states.items():
                tgt = st.get("target") if isinstance(st, dict) else None
                if tgt is None:
                    self.acc.pop(str(uid), None)
                    continue
                tgt = (int(tgt[0]), int(tgt[1]))
                a = self.acc.get(str(uid))
                if a is None or a["target"] != tgt:
                    a = self.acc[str(uid)] = self._new_acc(tgt, None)
                held.append(a)
        return held

    def _stage_pre(self, b) -> list:
        return [(a, float(b.p[self._disc(a["target"])].sum())) for a in self._sync_held()]

    def _stage_post(self, b, pre, key):
        for a, before in pre:
            if a["disc_issue"] is None:
                a["disc_issue"] = before
            a[key] += float(b.p[self._disc(a["target"])].sum()) - before
            if key == "cov":
                a["n"] += 1

    # ---- installation ------------------------------------------------------------------------------------------
    def install(self):
        ins = self
        M = self.wf.WildFireModel
        B = self.vsb.VictimSearchBelief
        o_init, o_amk, o_step = M._init_victim_search_belief, M._apply_monitoring_to_knowledge, M.step
        o_measure, o_predict, o_burn, o_bump = B.measure, B.predict, B.burn_over, self.stg._bump
        sig_m, sig_p, sig_b = inspect.signature(o_measure), inspect.signature(o_predict), inspect.signature(o_burn)
        seq = (set, frozenset, list, tuple)

        def init_belief(self_):
            ins.model = self_
            ins.cur = {}
            r = o_init(self_)
            ins.own_launch, ins.cur = ins.cur, {}
            return r

        def step(self_):
            if not ins.launched:
                ins._launch(self_)
            return o_step(self_)

        def apply_monitoring(self_, buffer, current_time):
            ins.cur = {}
            r = o_amk(self_, buffer, current_time)
            ins._post_update(self_, buffer, current_time)
            return r

        def measure(*args, **kwargs):
            if not ins._is_own(args[0]):
                return o_measure(*args, **kwargs)
            t0 = ins.clock()
            pre = None
            try:
                a = sig_m.bind(*args, **kwargs)
                a.apply_defaults()
                a = a.arguments
                cells, smoke = a["uav_cells"], a["smoke"]
                if isinstance(cells, (list, tuple)):
                    ins.cur["r_k"] = ins.bp.removed_mass(args[0], cells, smoke, a["pd"], a["pd_smoke"],
                                                         ins.vsb.disc_mask)
                    ins.cur["cells"] = [(int(c[0]), int(c[1])) for c in cells]
                else:
                    ins._err("own measure: uav_cells is a %s - r_k not recorded" % type(cells).__name__)
                ins.cur["smoke"] = set(smoke) if isinstance(smoke, seq) else None
                ins.cur["pd"] = (a["pd"], a["pd_smoke"])
                ins.cur["mstep"] = a["step"]
                pre = ins._stage_pre(args[0])
            except Exception as exc:
                ins._err(exc)
            ins.acc_ms += (ins.clock() - t0) * 1000.0
            r = o_measure(*args, **kwargs)
            t0 = ins.clock()
            try:
                if pre is not None:
                    ins._stage_post(args[0], pre, "cov")
            except Exception as exc:
                ins._err(exc)
            ins.acc_ms += (ins.clock() - t0) * 1000.0
            return r

        def predict(*args, **kwargs):
            if not ins._is_own(args[0]):
                return o_predict(*args, **kwargs)
            t0 = ins.clock()
            pre = None
            try:
                a = sig_p.bind(*args, **kwargs)
                a.apply_defaults()
                a = a.arguments
                ins.cur["burn_p"] = list(a["burning"]) if isinstance(a["burning"], seq) else None
                ins.cur["motion"] = a["motion"]
                pre = ins._stage_pre(args[0])
            except Exception as exc:
                ins._err(exc)
            ins.acc_ms += (ins.clock() - t0) * 1000.0
            r = o_predict(*args, **kwargs)
            t0 = ins.clock()
            try:
                if pre is not None:
                    ins._stage_post(args[0], pre, "mot")
            except Exception as exc:
                ins._err(exc)
            ins.acc_ms += (ins.clock() - t0) * 1000.0
            return r

        def burn_over(*args, **kwargs):
            if not ins._is_own(args[0]):
                return o_burn(*args, **kwargs)
            t0 = ins.clock()
            pre = None
            d0 = args[0].dead
            try:
                a = sig_b.bind(*args, **kwargs)
                a.apply_defaults()
                a = a.arguments
                ins.cur["burn_b"] = list(a["burning"]) if isinstance(a["burning"], seq) else None
                ins.cur["p_bo"] = a["p_bo"]
                pre = ins._stage_pre(args[0])
            except Exception as exc:
                ins._err(exc)
            ins.acc_ms += (ins.clock() - t0) * 1000.0
            r = o_burn(*args, **kwargs)
            t0 = ins.clock()
            try:
                ins.cur["bo"] = float(args[0].dead) - float(d0)
                if pre is not None:
                    ins._stage_post(args[0], pre, "bo")
            except Exception as exc:
                ins._err(exc)
            ins.acc_ms += (ins.clock() - t0) * 1000.0
            return r

        def bump(*args, **kwargs):
            try:
                key = args[2] if len(args) > 2 else kwargs.get("key")
                if key in ("drop_swept", "drop_covered"):
                    t0 = ins.clock()
                    ins._swept_event(args[0] if args else kwargs.get("model"),
                                     args[1] if len(args) > 1 else kwargs.get("uid"), key)
                    ins.acc_ms += (ins.clock() - t0) * 1000.0
            except Exception as exc:
                ins._err(exc)
            return o_bump(*args, **kwargs)

        M._init_victim_search_belief = init_belief
        M.step = step
        M._apply_monitoring_to_knowledge = apply_monitoring
        B.measure = measure
        B.predict = predict
        B.burn_over = burn_over
        self.stg._bump = bump

    # ---- recorders ---------------------------------------------------------------------------------------------
    def _swept_event(self, m, uid, key):
        uid = str(uid)
        st = (getattr(m, "_searcher_targeting_state", None) or {}).get(uid)
        tgt = st.get("target") if isinstance(st, dict) else None
        rec = {"kind": key, "cov": None, "mot": None, "bo": None, "since": None, "n": 0, "disc_issue": None,
               "disc_now": None, "disc_n": None, "rem_n": None, "rem_issue": None, "rem_now": None}
        if tgt is not None:
            tgt = (int(tgt[0]), int(tgt[1]))
            a = self.acc.get(uid)
            if a is not None and a["target"] == tgt:
                rec.update(cov=a["cov"], mot=a["mot"], bo=a["bo"], since=a["since"], n=a["n"],
                           disc_issue=a["disc_issue"])
            b = getattr(m, "victim_search_belief", None)
            if b is not None:
                disc = self._disc(tgt)
                rec["disc_now"] = float(b.p[disc].sum())
                rec["disc_n"] = int(disc.sum())
                # ruling R-5 (bp_inst v2): F1-c's REMAINDER - the target disc minus the holder's own footprint since
                # issue, the set the swept rule actually compares - its size and its posterior mass at issue and now
                # (read from the planner's state before the drop clears it; None with the fix off)
                own, p_issue = st.get("own"), st.get("p_issue")
                if own is not None and p_issue is not None:
                    rem = disc & ~own
                    rec.update(rem_n=int(rem.sum()), rem_issue=float(p_issue[rem].sum()),
                               rem_now=float(b.p[rem].sum()))
        self.swept.append([int(getattr(m, "evaluation_timesteps_counter", 0) or 0), uid,
                           list(tgt) if tgt is not None else None, rec])

    def _launch(self, m):
        """First-step entry: the launch inputs exactly as wildfire_model._init_victim_search_belief reads them."""
        self.launched = True
        t0 = self.clock()
        try:
            am, wf, bp, vsb = self.am, self.wf, self.bp, self.vsb
            self.model = m
            H, W = int(wf.HEIGHT), int(wf.WIDTH)
            self.meta = {"H": H, "W": W, "n_brief": int(wf.NUM_VICTIMS), "radius": float(wf.UAV_OBSERVATION_RADIUS)}
            self.mode = int(am.searcher_targeting())
            uavs = [(str(a.unique_id), int(a.pos[0]), int(a.pos[1])) for a in m.schedule.agents
                    if type(a) is am.UAV and a.pos is not None]
            cells = [(x, y) for _, x, y in uavs]
            excluded = m.victim_search_prior_excluded()
            burning, smoke = m._fix3b_true_fire()
            pd, pd_s = am.fix3b_param("SEARCHER_BELIEF_PD", 1.0), am.fix3b_param("SEARCHER_BELIEF_PD_SMOKE", 1.0)
            reflect = bool(am.searcher_targeting_fix())
            self.meta.update(pd=pd, pd_smoke=pd_s, reflect=reflect,
                             motion={k: am.fix3b_param(name, default) for k, name, default in bp.MOTION_FIELDS})
            self.names = bp.shadow_names(self.mode)
            sh = {}
            for name in self.names:
                b, r0 = bp.launch(vsb.VictimSearchBelief, H, W, self.meta["n_brief"], excluded, self.meta["radius"],
                                  cells, smoke, pd, pd_s, vsb.disc_mask)
                self.shadows[name] = b
                sh[name] = bp.scalars(b, r0, None)
            own_b = getattr(m, "victim_search_belief", None)
            own = None
            if own_b is not None:
                own = bp.scalars(own_b, self.own_launch.get("r_k"), None, own=True)
                own_mode = bp.OWN_MODE.get(self.mode, "diffusion") if am.searcher_belief_motion() else "off"
                self.own_cfg = {"mode": own_mode, "burnover": am.fix3b_param("SEARCHER_BELIEF_BURNOVER", 0.1),
                                "bayes": self.mode in bp.BAYES_MODES}
                if self.own_cfg["bayes"]:
                    for name in self.names:
                        if bp.shadow_cfg(name) == (own_mode, self.own_cfg["burnover"]):
                            self.v3_shadow = name
                            break
                if self.v3_shadow is not None:
                    s = sh[self.v3_shadow]
                    self.check["launch_match"] = all(repr(own[k]) == repr(s[k])
                                                     for k in ("phash", "dead", "alive", "r_k"))
                # the launch inputs the own belief used (captured in __init__) vs the ones read here
                c = self.check["inputs"]
                c["compared"] += 1
                diff = [k for k, mine in (("cells", cells), ("smoke", set(smoke)), ("pd", (pd, pd_s)), ("mstep", 0))
                        if self.own_launch.get(k) != mine]
                if diff:
                    c["mismatch"] += 1
                    c["first"] = {"t": 0, "diff": diff}
            self.wind_label = str(getattr(getattr(m, "wind", None), "wind_direction", None))
            self.wind_cur = tuple(float(v) for v in self.cfv.wind_vector_from_direction(m.wind.wind_direction))
            self.prev_burn = set(bp.flat(burning, W))
            self.prev_smoke = set(bp.flat(smoke, W))
            self.launch = {"uav_cells": [[u, x, y] for u, x, y in uavs], "excluded": bp.flat(excluded, W),
                           "smoke": sorted(self.prev_smoke), "burning": sorted(self.prev_burn), "own": own, "sh": sh}
        except Exception as exc:
            self._err(exc)
            self.broken = True
        self.launch_ms = (self.clock() - t0) * 1000.0

    def _post_update(self, m, buffer, current_time):
        """After _apply_monitoring_to_knowledge: the inputs exactly as _update_victim_search_belief reads them."""
        t0 = self.clock()
        try:
            if not self.broken and self.launched:
                self._record_step(m, buffer, current_time)
        except Exception as exc:
            self._err(exc)
            self.broken = True
        self.step_ms.append(self.acc_ms + (self.clock() - t0) * 1000.0)
        self.acc_ms = 0.0

    def _record_step(self, m, buffer, current_time):
        am, bp, vsb, fae = self.am, self.bp, self.vsb, self.fae
        H, W = self.meta["H"], self.meta["W"]
        t = int(current_time)
        burning, smoke = m._fix3b_true_fire()
        cells: dict = {}
        for uid, obs in (getattr(buffer, "local_observations", {}) or {}).items():
            pos = getattr(obs, "current_position", None)
            if pos is not None:
                cells[str(uid)] = (int(round(float(pos[0]))), int(round(float(pos[1]))))
        for a in m.schedule.agents:
            if type(a) is am.UAV and a.pos is not None and str(a.unique_id) not in cells:
                cells[str(a.unique_id)] = (int(a.pos[0]), int(a.pos[1]))
        cell_list = list(cells.values())
        for vid, st in (getattr(m, "managed_victims", {}) or {}).items():
            if getattr(st, "confirmed", False):
                self.det.add(str(vid))
        for vid in (getattr(getattr(m, "victim_runtime_model", None), "victims", {}) or {}):
            self.det.add(str(vid))
        pd, pd_s = am.fix3b_param("SEARCHER_BELIEF_PD", 1.0), am.fix3b_param("SEARCHER_BELIEF_PD_SMOKE", 1.0)
        reflect = bool(am.searcher_targeting_fix())
        sh = {}
        for name, b in self.shadows.items():
            mode, p_bo = bp.shadow_cfg(name)
            r, bo = bp.advance(b, bp.motion_params(vsb.MotionParams, mode, p_bo, reflect, am.fix3b_param), burning,
                               smoke, cell_list, t, pd, pd_s, self.det, vsb.disc_mask)
            sh[name] = bp.scalars(b, r, bo)
        own_b = getattr(m, "victim_search_belief", None)
        own = None
        if own_b is not None:
            own = bp.scalars(own_b, self.cur.get("r_k"), self.cur.get("bo"), own=True)
            # the own belief's actual arguments this step vs the instrument's inputs (identical inputs, exact order)
            c = self.check["inputs"]
            c["compared"] += 1
            diff = [k for k, mine in (("cells", cell_list), ("smoke", set(smoke)), ("pd", (pd, pd_s)), ("mstep", t))
                    if self.cur.get(k) != mine]
            if set(own_b.detected_ids) != self.det:
                diff.append("det")
            if self.own_cfg["bayes"]:
                bl = list(burning)
                own_mode = bp.OWN_MODE.get(self.mode, "diffusion") if am.searcher_belief_motion() else "off"
                exp = bp.motion_params(vsb.MotionParams, own_mode, am.fix3b_param("SEARCHER_BELIEF_BURNOVER", 0.1),
                                       reflect, am.fix3b_param)
                diff += [k for k, mine in (("burn_p", bl), ("burn_b", bl), ("motion", exp), ("p_bo", exp.burnover))
                         if self.cur.get(k) != mine]
            if diff:
                c["mismatch"] += 1
                if c["first"] is None:
                    c["first"] = {"t": t, "diff": diff}
            # V3: the shadow configured like the own belief must equal it, every step
            if self.v3_shadow is not None:
                s = sh[self.v3_shadow]
                self.check["compared_steps"] += 1
                bad = [k for k in ("phash", "dead", "alive", "r_k", "bo") if repr(own[k]) != repr(s[k])]
                if bad:
                    self.check["mismatch_steps"] += 1
                    if self.check["first_mismatch"] is None:
                        self.check["first_mismatch"] = {"t": t, "fields": bad, "own": own, "shadow": s}
        fl = bp.flat(burning, W)
        self.check["order"]["steps"] += 1
        if list(bp.cell_set(fl, W)) != list(burning):
            self.check["order"]["mismatch"] += 1
        cur_b, cur_s = set(fl), set(bp.flat(smoke, W))
        entry = {"t": t, "burn_on": sorted(cur_b - self.prev_burn), "burn_off": sorted(self.prev_burn - cur_b),
                 "smoke_on": sorted(cur_s - self.prev_smoke), "smoke_off": sorted(self.prev_smoke - cur_s),
                 "uav": [[u, x, y] for u, (x, y) in cells.items()], "det": sorted(self.det), "own": own, "sh": sh}
        self.prev_burn, self.prev_smoke = cur_b, cur_s
        wind = tuple(float(v) for v in self.cfv.wind_vector_from_direction(m.wind.wind_direction))
        if wind != self.wind_cur:
            entry["wind"] = list(wind)
            self.wind_cur = wind
        # every victim truly alive (marker not dead / rescued, on the grid) and undetected: a_v per belief, T_hat
        vic = []
        tgrid = None
        beliefs = ([("own", own_b)] if own_b is not None else []) + list(self.shadows.items())
        offsets = beliefs[0][1].offsets
        for vid, mk in (getattr(m, "victim_marker_agents", {}) or {}).items():
            pos = getattr(mk, "pos", None)
            status = str(getattr(mk, "status", "") or "").strip().lower()
            if pos is None or status in ("dead", "rescued") or str(vid) in self.det:
                continue
            x, y = int(pos[0]), int(pos[1])
            mask = vsb.disc_mask(H, W, [(x, y)], offsets)
            if tgrid is None:
                tgrid = fae.arrival_time(H, W, burning, self.wind_cur, fae.front_priority_params())
            v = float(tgrid[x, y])
            vic.append([str(vid), x, y, {n: bp.mass_share(b, mask) for n, b in beliefs}, v if math.isfinite(v) else None])
        entry["vic"] = vic
        self.steps.append(entry)

    def result(self) -> dict:
        ms = sorted(self.step_ms)
        if ms:
            over = {"n": len(ms), "median": ms[len(ms) // 2], "p95": ms[min(len(ms) - 1, int(math.ceil(0.95 * len(ms))) - 1)],
                    "max": ms[-1], "total_ms": sum(ms), "launch_ms": self.launch_ms}
        else:
            over = {"n": 0, "launch_ms": self.launch_ms}
        fpp = self.fae.front_priority_params()
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(self.vsb.__file__))))
        return {
            "version": self.bp.VERSION, "W": self.meta.get("W"), "H": self.meta.get("H"),
            "n_brief": self.meta.get("n_brief"), "radius": self.meta.get("radius"), "mode": self.mode,
            "shadows": list(self.names),
            "shadow_cfg": {n: {"mode": self.bp.shadow_cfg(n)[0], "burnover": self.bp.shadow_cfg(n)[1]}
                           for n in self.names},
            "motion": self.meta.get("motion"), "reflect": self.meta.get("reflect"), "pd": self.meta.get("pd"),
            "pd_smoke": self.meta.get("pd_smoke"), "own_cfg": self.own_cfg,
            "fp_params": dataclasses.asdict(fpp),
            "fp_derived": {"head_rate": fpp.head_rate, "length_to_width": fpp.length_to_width,
                           "eccentricity": fpp.eccentricity},
            "wind": list(self.wind_cur) if self.wind_cur is not None else None, "wind_label": self.wind_label,
            "src": {"victim_search_belief.py": self.bp.src_sha(self.vsb.__file__),
                    "fire_arrival_estimate.py": self.bp.src_sha(self.fae.__file__),
                    "root": root},
            "launch": self.launch, "steps": self.steps, "swept": self.swept,
            "self_check": dict({"mode": self.mode, "shadow": self.v3_shadow}, **self.check),
            "overhead": over, "errors": self.errors, "error_count": self.error_count, "broken": self.broken,
        }


def main() -> int:
    argv = sys.argv[1:]
    if "--" not in argv:
        print("usage: _fb3_probe.py [--crn] [--hazard] [--instrument] -- <_sd_probe.py args>", file=sys.stderr)
        return 2
    own = argv[:argv.index("--")]
    probe_args = argv[argv.index("--") + 1:]
    unknown = [a for a in own if a not in ("--crn", "--hazard", "--instrument")]
    if unknown:
        print("FB3 REFUSED: unknown own flag(s) %r (only --crn, --hazard, --instrument)" % (unknown,), file=sys.stderr)
        return 2
    for i, a in enumerate(probe_args):
        key = None
        if a == "--set" and i + 1 < len(probe_args):
            key = probe_args[i + 1]
        elif a.startswith("--set="):
            key = a[len("--set="):]
        if key is not None and key.split("=", 1)[0].strip().upper() == "FM2P_CRN":
            print("FB3 REFUSED: --set FM2P_CRN is ignored by _fx3_probe/_sd_probe; use --crn", file=sys.stderr)
            return 3
    use_crn = "--crn" in own
    out_path = probe_args[probe_args.index("--out") + 1]
    seed = int(probe_args[probe_args.index("--seed") + 1])
    repo = r"E:\Projects\SAS"
    for i, a in enumerate(probe_args):
        if a == "--repo":
            repo = probe_args[i + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import common_fixed_variables as cfv  # noqa: E402
    import wildfire_model as wf  # noqa: E402

    crn = {"on": use_crn, "crn_draws": 0}
    if use_crn:
        crn_uniform = _crn_uniform()
        src = textwrap.dedent(inspect.getsource(am.Fire.step))
        needle = "generated = random.random()"
        if src.count(needle) != 1:
            print("FB3: Fire.step draw line not found exactly once - refusing to run", file=sys.stderr)
            return 4
        body = src.replace(needle, "generated = _fb3_draw(self)")
        factory = "def _fb3_make(_fb3_draw):\n" + textwrap.indent(body, "    ") + "    return step\n"
        ns: dict = {}
        exec(compile(factory, "<fb3 Fire.step>", "exec"), am.__dict__, ns)

        def _draw(fire):
            crn["crn_draws"] += 1
            return crn_uniform(seed, fire.unique_id, fire.steps_counter)

        patched = ns["_fb3_make"](_draw)
        patched.__qualname__ = am.Fire.step.__qualname__
        am.Fire.step = patched

    from src_extension.knowledge.victim_search_belief import disc_mask, disc_offsets  # noqa: E402

    state = {"model": None, "step": 0, "covered": None, "rows": [], "spawn": None}
    ostep = wf.WildFireModel.step

    def step(self):
        if state["spawn"] is None:
            state["spawn"] = {vid: [int(m.pos[0]), int(m.pos[1])] for vid, m in
                              (getattr(self, "victim_marker_agents", {}) or {}).items() if m.pos is not None}
        r = ostep(self)
        state["model"] = self
        state["step"] += 1
        try:
            h, w = int(self.HEIGHT), int(self.WIDTH)
            if state["covered"] is None:
                state["offsets"] = disc_offsets(float(getattr(wf, "UAV_OBSERVATION_RADIUS", 8)))
                state["covered"] = disc_mask(h, w, [], state["offsets"])
            cells = [(int(a.pos[0]), int(a.pos[1])) for a in self.schedule.agents
                     if type(a).__name__ == "UAV" and a.pos is not None]
            state["covered"] |= disc_mask(h, w, cells, state["offsets"])
            if state["step"] % 10 == 0:
                belief = getattr(self, "victim_search_belief", None)
                state["rows"].append([state["step"], round(float(state["covered"].mean()), 4),
                                      belief.summary() if belief is not None else None])
        except Exception as exc:  # an observer never stops the run
            state["rows"].append([state["step"], "ERR", repr(exc)[:200]])
        return r

    wf.WildFireModel.step = step

    # RECORD-ONLY (maintainer rulings on the bayesprep report, 2026-10-04): the model's own MR2 call, observed at the
    # moment it counts (pre-move positions, the same step), plus the same rule restricted to AIRBORNE pairs. A pass-
    # through: the original runs once with its arguments; this reads positions / rtb_docked and writes nothing.
    mr = {"probe": "fb3 mr v1", "steps": [], "errors": []}
    o_mr2 = wf.WildFireModel.MR2

    def mr2(self, *a, **kw):
        before = getattr(self, "MR2_VALUE", None)
        r = o_mr2(self, *a, **kw)
        try:
            uavs = [u for u in self.schedule.agents if type(u) is am.UAV]
            n_all = n_air = n_one = n_both = 0
            for i in range(len(uavs)):
                for j in range(i + 1, len(uavs)):
                    p, q = uavs[i].pos, uavs[j].pos
                    if wf.euclidean_distance(p[0], p[1], q[0], q[1]) < wf.SECURITY_DISTANCE:
                        n_all += 1
                        docked = int(bool(getattr(uavs[i], "rtb_docked", False))) + int(
                            bool(getattr(uavs[j], "rtb_docked", False)))
                        if docked == 0:
                            n_air += 1
                        elif docked == 1:
                            n_one += 1
                        else:
                            n_both += 1
            mr["steps"].append([int(self.evaluation_timesteps_counter), int(self.MR2_VALUE) - int(before or 0), n_all,
                                n_air, n_one, n_both])
        except Exception as exc:  # an observer never stops the run
            if len(mr["errors"]) < 20:
                mr["errors"].append(repr(exc)[:200])
        return r

    wf.WildFireModel.MR2 = mr2
    inst = None
    if "--instrument" in own:          # bayesprep item 3; nothing of it exists without the flag
        inst = _Instrument(wf, am, cfv)
        inst.install()

    fx3 = runpy.run_path(os.path.join(HERE, "_fx3_probe.py"), run_name="fx3_probe_module")
    sys.argv = [sys.argv[0]] + (["--hazard"] if "--hazard" in own else []) + ["--"] + probe_args
    rc = fx3["main"]()
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        m = state["model"]
        if state["rows"] and state["rows"][-1][0] != state["step"] and state["covered"] is not None:
            belief = getattr(m, "victim_search_belief", None)
            state["rows"].append([state["step"], round(float(state["covered"].mean()), 4),
                                  belief.summary() if belief is not None else None])
        timing = getattr(m, "_searcher_targeting_timing", None) or {}
        d["fb3"] = {
            "probe": "fb3_probe v1",
            "crn": crn,
            "coverage": state["rows"],
            "spawn": state["spawn"],
            "stats": getattr(m, "_searcher_targeting_stats", None) or {},
            "issued": getattr(m, "_searcher_targeting_issued", None) or [],
            "timing": {k: _summ(list(v)) for k, v in timing.items()},
            "switches": {k: getattr(cfv, k, None) for k in FIX3B_KEYS},
            "eff": {"searcher_targeting": am.searcher_targeting(), "victim_spawn_mode": am.victim_spawn_mode(),
                    "belief_built": getattr(m, "victim_search_belief", None) is not None,
                    "rw_stream_built": getattr(m, "_searcher_rw_rng", None) is not None,
                    "spawn_stream_built": getattr(m, "_victim_spawn_rng", None) is not None},
        }
        if inst is not None:
            d["fb3"]["inst"] = inst.result()
            d["fb3"]["bp_switches"] = _bp_switches(am, cfv)
        mr1 = getattr(m, "MR1_LIST", None)
        mr.update(security_distance=_jsafe(getattr(wf, "SECURITY_DISTANCE", None)),
                  mr1_list=[float(v) for v in mr1] if isinstance(mr1, (list, tuple)) else None,
                  mr2_value=_jsafe(getattr(m, "MR2_VALUE", None)))
        d["mr"] = mr
        tmp = out_path + ".fb3tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("FB3 WRITE FAILED %r" % (exc,), file=sys.stderr)
        return 5
    if use_crn and crn["crn_draws"] == 0:
        print("FB3: --crn run made 0 CRN draws - INVALID", file=sys.stderr)
        return 6
    return rc


if __name__ == "__main__":
    sys.exit(main())
