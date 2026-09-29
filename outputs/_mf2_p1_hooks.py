"""fix2 (session 2) Part 1: alarm-attribution hooks around outputs/_sd_probe.py. DIAGNOSIS ONLY.

Every hook is a PASS-THROUGH wrapper installed in THIS process: it calls the original with the
original arguments, returns the original result unchanged, draws from no RNG and writes no
simulation state. A hooked run must be value-identical to the unhooked fix1 probe run of the same
arguments (outputs/_sd_mf1P_*.json, same source as c08456b) - the Part 1 analyzer checks that.

usage: _mf2_p1_hooks.py -- <_sd_probe.py args ...>

Recorded (d["mf2"] in the probe JSON):
  loc   per UAV per analysis call (the analysis of step t reads the move of step t-1):
        [step, uid, role, rtb_active, rtb_docked, x, y, triggers, n_fire_vis, n_smoke_vis,
         n_uncertain, n_negative, drift_error, drift_level, local_risk_status, congestion,
         dmin_air, n_air_le2, dmin_any, last_move]
        dmin_air = Manhattan distance to the nearest OTHER UAV that is not docked (None if none),
        n_air_le2 = other non-docked UAVs within Manhattan 2, dmin_any = nearest other UAV at all.
        last_move = how this UAV's latest UAV.move call ended: moved / docked_hold /
        nodir_hold / refused_occupied / refused_oob.
  glob  per global analysis call: [step, truly_burning, any_uav_sees_fire, belief_high (p>=0.7),
        crit_link_used, delivery_used, failed_n_used, link_trigger, crit_queue_len,
        failed_ids_by_kind, real_trigger_types, shadow_trigger_types]
        shadow = a COPY of the model's GlobalAnalyzer (its own previous_* state only) fed a
        read-only view in which the fire runtime model's attributes resolve on .belief and the
        snapshot carries fire_state_summary.estimated_burning_cells from the belief - i.e. the
        global analyzer as it would run with its fire source fixed. It cannot affect the run.
  move  counters of UAV.move outcomes by executor label family.
  cexec counters of communication action strings the executor scores as a delivery failure.
"""
from __future__ import annotations

import collections
import copy
import json
import os
import runpy
import sys


def main() -> int:
    argv = sys.argv[1:]
    cut = argv.index("--")
    probe_args = argv[cut + 1:]
    repo = r"E:\Projects\SAS"
    out_path = probe_args[probe_args.index("--out") + 1]
    sys.path.insert(0, repo)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am  # noqa: E402
    import wildfire_model as wf  # noqa: E402
    import src_extension.analysis.local_uav_analyzer as lua  # noqa: E402
    import src_extension.analysis.global_analyzer as ga  # noqa: E402
    import src_extension.execution.communication_executor as cx  # noqa: E402

    cur = {"step": 0, "model": None}
    LOC, GLOB = [], []
    MOVE = collections.Counter()
    CEXEC = collections.Counter()
    last_move = {}
    shadow = {"obj": None}

    orig_step = wf.WildFireModel.step

    def model_step(self):
        cur["step"] += 1
        cur["model"] = self
        return orig_step(self)

    wf.WildFireModel.step = model_step

    def uavs(model):
        return [a for a in model.schedule.agents if type(a) is am.UAV]

    # ---- UAV.move outcome ------------------------------------------------------------
    omove = am.UAV.move

    def move(self):
        label = str(getattr(self, "execution_action", "") or "")
        docked = bool(getattr(self, "rtb_docked", False))
        try:
            pipeline = bool(getattr(self.model, "_is_extension_pipeline_active", lambda: False)())
        except Exception:
            pipeline = False
        applied = bool(getattr(self, "execution_direction_applied", False))
        mx, my = [1, 0, -1, 0], [0, -1, 0, 1]
        d = int(self.selected_dir)
        target = (self.pos[0] + mx[d], self.pos[1] + my[d])
        oob = bool(self.model.grid.out_of_bounds(target))
        moved = omove(self)
        if docked:
            cls = "docked_hold"
        elif pipeline and not applied:
            cls = "nodir_hold"
        elif moved:
            cls = "moved"
        elif oob:
            cls = "refused_oob"
        else:
            cls = "refused_occupied"
        last_move[str(self.unique_id)] = cls
        low = label.lower()
        fam = ("hold" if low == "hold" else "fire_flank_hold" if low == "fire_flank_hold"
               else "hold_escape" if low.startswith("hold_escape") else "rtb" if "rtb" in low
               else "other")
        MOVE["%s|%s" % (fam, cls)] += 1
        return moved

    am.UAV.move = move

    # ---- local analyzer --------------------------------------------------------------
    olocal = lua.LocalUAVAnalyzer.analyze
    INTEREST = ("COLLISION_RISK", "DRIFT_TOO_HIGH", "SEARCH_MODE_REQUIRED", "INFORMATION_INSUFFICIENT",
                "CRITICAL_BATTERY", "LOW_BATTERY", "UAV_STUCK")

    def local_analyze(self, uav_id, lom, lpm, st, latest, timestamp):
        res = olocal(self, uav_id, lom, lpm, st, latest, timestamp)
        m = cur["model"]
        try:
            names = sorted({str(t.trigger_type) for t in res.local_trigger_list} & set(INTEREST))
            me = None
            others = []
            for a in uavs(m):
                if str(a.unique_id) == str(uav_id):
                    me = a
                else:
                    others.append(a)
            x = y = None
            dmin_air = dmin_any = None
            n2 = 0
            if me is not None and me.pos is not None:
                x, y = int(me.pos[0]), int(me.pos[1])
                for o in others:
                    if o.pos is None:
                        continue
                    dd = abs(int(o.pos[0]) - x) + abs(int(o.pos[1]) - y)
                    dmin_any = dd if dmin_any is None else min(dmin_any, dd)
                    if not bool(getattr(o, "rtb_docked", False)):
                        dmin_air = dd if dmin_air is None else min(dmin_air, dd)
                        if dd <= 2:
                            n2 += 1
            coll = lpm.local_collision_risk_estimates or {}
            LOC.append([cur["step"], str(uav_id),
                        str(getattr(me, "current_role", "") or "") if me is not None else "",
                        int(bool(getattr(me, "rtb_active", False))) if me is not None else None,
                        int(bool(getattr(me, "rtb_docked", False))) if me is not None else None,
                        x, y, names,
                        len(lom.visible_fire_cells or ()), len(lom.visible_smoke_cells or ()),
                        len(lom.local_uncertainty_patch or {}), len(lom.negative_local_observations or {}),
                        latest.get("drift_error"), st.drift_level, st.local_risk_status,
                        coll.get("congestion"), dmin_air, n2, dmin_any,
                        last_move.get(str(uav_id))])
        except Exception as exc:  # recorded, never raised into the run
            LOC.append([cur["step"], str(uav_id), "HOOK_ERR", repr(exc)[:120]])
        return res

    lua.LocalUAVAnalyzer.analyze = local_analyze

    # ---- global analyzer + shadow with the fire source on .belief ----------------------
    oglobal = ga.GlobalAnalyzer.analyze

    class BeliefView:
        def __init__(self, fr):
            self._fr = fr

        def __getattr__(self, name):
            b = getattr(self._fr, "belief", None)
            if b is not None and hasattr(b, name):
                return getattr(b, name)
            return getattr(self._fr, name)

    def global_analyze(self, sop, snap_dict, runtime_models, t):
        if shadow["obj"] is None:
            shadow["obj"] = copy.copy(self)  # fresh previous_* state, same thresholds
        res = oglobal(self, sop, snap_dict, runtime_models, t)
        m = cur["model"]
        try:
            truth = sum(1 for a in m.schedule.agents if type(a) is am.Fire and a.burning)
            sees = any(len(lom.visible_fire_cells or ()) > 0
                       for lom in (getattr(m, "local_observation_models", {}) or {}).values())
            fr = runtime_models.get("fire_runtime_model")
            b = getattr(fr, "belief", None)
            high = sum(1 for p in (b.fire_probability_map.values() if b is not None else ()) if p >= 0.7)
            cm = runtime_models.get("communication_model")
            snap = self._unwrap_summary_layer((snap_dict or {}).get("communication_summary"))
            crit = self._comm_float(cm, snap, "critical_link_reliability")
            deliv = self._comm_float(cm, snap, "delivery_confidence")
            failed_n = self._failed_message_count(cm, snap)
            kinds = collections.Counter()
            cst = getattr(cm, "state", None)
            for msg in (getattr(cst, "failed_messages", None) or []):
                mid = str(msg.get("message_id", ""))
                kinds["telemetry" if mid.endswith("_telemetry") else
                      "aggregate" if mid.startswith("monitoring_aggregate") else "other"] += 1
            qlen = len(getattr(cst, "critical_message_queue", None) or [])
            real = sorted({str(x.trigger_type) for x in res.trigger_list})
            view_models = dict(runtime_models)
            if fr is not None:
                view_models["fire_runtime_model"] = BeliefView(fr)
            view_snap = dict(snap_dict or {})
            if b is not None:
                view_snap["fire_state_summary"] = {
                    "value": {"estimated_burning_cells": [list(c) for c in b.estimated_burning_cells],
                              "estimated_fire_front_cells": [list(c) for c in b.estimated_fire_front_cells]}}
            sres = oglobal(shadow["obj"], sop, view_snap, view_models, t)  # not the patched one
            sh = sorted({str(x.trigger_type) for x in sres.trigger_list})
            GLOB.append([cur["step"], truth, int(sees), high, crit, deliv, failed_n,
                         int("CRITICAL_LINK_UNRELIABLE" in real), qlen, dict(kinds), real, sh])
        except Exception as exc:
            GLOB.append([cur["step"], "HOOK_ERR", repr(exc)[:160]])
        return res

    ga.GlobalAnalyzer.analyze = global_analyze

    # ---- communication executor failure scoring -------------------------------------
    odeliv = cx.CommunicationExecutor.__dict__["_delivery_status"]
    ofunc = odeliv.__func__ if isinstance(odeliv, staticmethod) else odeliv

    def delivery_status(communication_action):
        r = ofunc(communication_action)
        if r != "success":
            CEXEC["%s|%s" % (r, str(communication_action)[:60])] += 1
        return r

    cx.CommunicationExecutor._delivery_status = staticmethod(delivery_status)

    probe = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sd_probe.py"),
                           run_name="sd_probe_module")
    sys.argv = [sys.argv[0]] + probe_args
    rc = probe["main"]()
    try:
        with open(out_path, encoding="utf-8") as fh:
            d = json.load(fh)
        d["mf2"] = {"loc": LOC, "glob": GLOB, "move": dict(MOVE), "cexec": dict(CEXEC)}
        tmp = out_path + ".hktmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(d, fh, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception as exc:
        print("MF2_HOOKS RECORD FAILED: %r" % (exc,), file=sys.stderr)
        return 5
    print("MF2_HOOKS_DONE")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
