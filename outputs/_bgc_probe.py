"""_belief_gap_critical constant-True probe.

Subject
-------
GlobalMonitor._belief_gap_indicators()        global_monitor.py:252
    returns a dict with exactly FOUR keys:
        threshold_probability, threshold_confidence, cells (list, [:50]), count (int)
    "count" is the number of REAL belief gaps; "cells" is that list capped at 50.

GlobalAnalyzer._belief_gap_critical(bg, suff_score, total_gain)
                                              global_analyzer.py:618
        if isinstance(belief_gap, list) and len(belief_gap) >= 3: return True
        if isinstance(belief_gap, dict) and len(belief_gap) >= 3: return True   <-- KEYS, not gaps
        if suff_score is not None and suff_score < 0.15: return True
        if total_gain is not None and total_gain < 0.01: return True
        return False
    Called once per global analysis at global_analyzer.py:506.

What this probe measures (all by DIRECT HOOK, never by per-step snapshot)
------------------------------------------------------------------------
H1  the container the predicate branches on, its len(), the REAL gap count it
    represents, which clause fired, the returned bool, and what a
    count-correct predicate would have returned  -- per call.
H2  the triggers _analyze_information_sufficiency actually emits, with the
    severity / confidence / recommended_planner each carries -- per call.
H3  the PROVENANCE of every fail-safe reason: analysis vs planning-text vs
    execution.  This is the crux for "what drives information_recovery".
H4  every classify_mode call: reasons in, current_mode in, mode out.
H5  every ModeManager.update: previous mode -> new mode, with reasons.
H6  the SharedOperationalPicture.mission_mode latch
    (wildfire_model.py:_update_failsafe_mode only ever WRITES mission_mode when
    mode != NORMAL; it never restores it) -- per step.

Modes
-----
  nopatch  no hooks at all               -- determinism control
  live     hooks record only             -- must be byte-identical to nopatch
  arm      hooks record + _belief_gap_critical replaced by the count-correct
           predicate                     -- the counterfactual

usage:
  _bgc_probe.py --mode live --wind east --roles half --seed 101 --out P.json
  _bgc_probe.py --compare --glob "outputs/_bgc_run_*.json" --out outputs/_bgc_probe.json
"""
from __future__ import annotations
import argparse, contextlib, glob as _glob, hashlib, io as _io, json, os, random, sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

CUR = {"step": 0}

REC = {
    # --- H1: the predicate itself -------------------------------------
    "ind_calls": 0,
    "ind_shape": {},            # "type:len:sorted-keys" -> count
    "crit_calls": 0,
    "crit": [],                 # one dict per call, see _hook_critical
    # --- H2: emitted triggers -----------------------------------------
    "infosuff_calls": 0,
    "triggers": [],             # {step, emitted:[{type,severity,confidence,planner}]}
    # --- H3: reason provenance ----------------------------------------
    "reason_src": [],           # {step, analysis:[], planning:[], execution:[], final:[]}
    "planning_text_sample": [], # what _reasons_from_planning actually scanned
    # which TRIGGER OBJECTS carry the information reasons, and at what scope.
    # "name|scope|severity|passes_conf_gate" -> count, over every analysis batch.
    "analysis_trigger_hist": {},
    # of the triggers that map to search_mode_required / information_insufficient,
    # "name|scope" -> count.  This is what actually pins the mode.
    "info_reason_origin": {},
    # --- H4/H5: mode ---------------------------------------------------
    "classify": [],             # {step, reasons, current_mode, out}
    "mm_update": [],            # {step, prev, new, reasons}
    "mode_transitions": [],     # {step, frm, to} -- only where it changed
    # --- H6: the mission_mode latch ------------------------------------
    "sop_mission_mode": [],     # {step, failsafe_mode, sop_mission_mode}
}


def _bump(d, k):
    d[k] = d.get(k, 0) + 1


def _gap_count(bg):
    """The number of REAL belief gaps the container represents."""
    if isinstance(bg, list):
        return len(bg)
    if isinstance(bg, dict):
        c = bg.get("count")
        if isinstance(c, (int, float)) and not isinstance(c, bool):
            return int(c)
        cells = bg.get("cells")
        return len(cells) if isinstance(cells, list) else 0
    return None


def corrected_belief_gap_critical(belief_gap, suff_score, total_gain):
    """The count-correct predicate: same thresholds, counts GAPS not KEYS."""
    n = _gap_count(belief_gap)
    if n is not None and n >= 3:
        return True
    if suff_score is not None and suff_score < 0.15:
        return True
    if total_gain is not None and total_gain < 0.01:
        return True
    return False


def _which_clause(bg, suff_score, total_gain):
    """Which clause of the LIVE predicate returns first."""
    if isinstance(bg, list) and len(bg) >= 3:
        return "list_len"
    if isinstance(bg, dict) and len(bg) >= 3:
        return "dict_len"
    if suff_score is not None and suff_score < 0.15:
        return "suff_score"
    if total_gain is not None and total_gain < 0.01:
        return "total_gain"
    return "none"


def _which_clause_corrected(bg, suff_score, total_gain):
    n = _gap_count(bg)
    if n is not None and n >= 3:
        return "gap_count"
    if suff_score is not None and suff_score < 0.15:
        return "suff_score"
    if total_gain is not None and total_gain < 0.01:
        return "total_gain"
    return "none"


def install(arm: bool):
    from src_extension.monitoring.global_monitor import GlobalMonitor as M
    from src_extension.analysis.global_analyzer import GlobalAnalyzer as A
    from src_extension.execution.safety_checker import SafetyChecker as S
    from src_extension.execution.mode_manager import ModeManager as MM

    # ---- H1a: _belief_gap_indicators ---------------------------------
    orig_ind = M._belief_gap_indicators

    def ind(self):
        out = orig_ind(self)
        REC["ind_calls"] += 1
        if isinstance(out, dict):
            _bump(REC["ind_shape"],
                  "dict:%d:%s" % (len(out), ",".join(sorted(out.keys()))))
        else:
            _bump(REC["ind_shape"], "%s:%s" % (type(out).__name__, len(out)))
        return out

    M._belief_gap_indicators = ind

    # ---- H1b: _belief_gap_critical (@staticmethod) -------------------
    orig_crit = A._belief_gap_critical

    def crit(belief_gap, suff_score, total_gain):
        live = bool(orig_crit(belief_gap, suff_score, total_gain))
        corr = bool(corrected_belief_gap_critical(belief_gap, suff_score, total_gain))
        n = _gap_count(belief_gap)
        REC["crit_calls"] += 1
        REC["crit"].append({
            "step": CUR["step"],
            "arg_type": type(belief_gap).__name__,
            "arg_len": (len(belief_gap)
                        if isinstance(belief_gap, (list, dict, tuple)) else None),
            "arg_keys": (sorted(belief_gap.keys())
                         if isinstance(belief_gap, dict) else None),
            "gap_count": n,
            "cells_len": (len(belief_gap.get("cells") or [])
                          if isinstance(belief_gap, dict) else None),
            "suff_score": suff_score,
            "total_gain": total_gain,
            "live_clause": _which_clause(belief_gap, suff_score, total_gain),
            "live": live,
            "corrected_clause": _which_clause_corrected(belief_gap, suff_score, total_gain),
            "corrected": corr,
        })
        return corr if arm else live

    A._belief_gap_critical = staticmethod(crit)

    # ---- H2: which triggers actually get emitted ---------------------
    orig_infosuff = A._analyze_information_sufficiency

    def infosuff(self, sop, global_snapshot, runtime_models, timestamp):
        out = orig_infosuff(self, sop, global_snapshot, runtime_models, timestamp)
        REC["infosuff_calls"] += 1
        REC["triggers"].append({
            "step": CUR["step"],
            "emitted": [{
                "type": str(getattr(t, "trigger_type", "")),
                "severity": str(getattr(getattr(t, "severity", None), "value",
                                        getattr(t, "severity", ""))),
                "confidence": round(float(getattr(t, "confidence", 0.0)), 6),
                "planner": str(getattr(t, "recommended_planner", "")),
            } for t in (out or ())],
        })
        return out

    A._analyze_information_sufficiency = infosuff

    # ---- H3: reason provenance ---------------------------------------
    o_from_analysis = S._reasons_from_analysis
    o_from_planning = S._reasons_from_planning
    o_from_execution = S._reasons_from_execution
    o_extract = S.extract_fail_safe_reasons

    PEND = {}

    from src_extension.analysis.trigger_objects import (
        normalize_triggers as _norm,
        trigger_signal_passes_information_confidence as _gate,
    )
    _INFO_NAMES = {"SEARCH_MODE_REQUIRED", "INFORMATION_INSUFFICIENT"}

    def r_analysis(self, snap):
        out = o_from_analysis(self, snap)
        PEND["analysis"] = list(out)
        # record which trigger objects were in the batch, and which of them
        # actually carry an information reason through the confidence gate
        if snap is not None:
            for sig in _norm(snap).triggers:
                nm = sig.name.strip().upper()
                sc = str(getattr(getattr(sig, "scope", None), "value",
                                 getattr(sig, "scope", "")))
                sv = str(getattr(getattr(sig, "severity", None), "value",
                                 getattr(sig, "severity", "")))
                ok = bool(_gate(sig))
                _bump(REC["analysis_trigger_hist"],
                      "%s|%s|%s|%s" % (nm, sc, sv, ok))
                if nm in _INFO_NAMES and ok:
                    _bump(REC["info_reason_origin"], "%s|%s" % (nm, sc))
        return out

    def r_planning(self, res):
        out = o_from_planning(self, res)
        PEND["planning"] = list(out)
        if len(REC["planning_text_sample"]) < 8:
            REC["planning_text_sample"].append({
                "step": CUR["step"],
                "planning_result_type": type(res).__name__,
                "repr_head": repr(res)[:1200],
                "reasons": list(out),
            })
        return out

    def r_execution(self, res):
        out = o_from_execution(self, res)
        PEND["execution"] = list(out)
        return out

    def extract(self, analysis_snapshot=None, planning_result=None,
                execution_result=None, runtime_models=None):
        PEND.clear()
        out = o_extract(self, analysis_snapshot=analysis_snapshot,
                        planning_result=planning_result,
                        execution_result=execution_result,
                        runtime_models=runtime_models)
        REC["reason_src"].append({
            "step": CUR["step"],
            "analysis": PEND.get("analysis", []),
            "planning": PEND.get("planning", []),
            "execution": PEND.get("execution", []),
            "final": list(out),
        })
        return out

    S._reasons_from_analysis = r_analysis
    S._reasons_from_planning = r_planning
    S._reasons_from_execution = r_execution
    S.extract_fail_safe_reasons = extract

    # ---- H4: classify_mode -------------------------------------------
    o_classify = S.classify_mode

    def classify(self, reasons, current_mode="normal"):
        out = o_classify(self, reasons, current_mode=current_mode)
        REC["classify"].append({
            "step": CUR["step"],
            "reasons": list(reasons),
            "current_mode": str(current_mode),
            "out": str(out),
        })
        return out

    S.classify_mode = classify

    # ---- H5: ModeManager.update --------------------------------------
    o_update = MM.update

    def update(self, analysis_snapshot=None, planning_result=None,
               execution_result=None, runtime_models=None, timestamp=0.0):
        prev = str(getattr(getattr(self, "current_state", None), "mode", ""))
        prev = getattr(getattr(self.current_state, "mode", None), "value", prev)
        st = o_update(self, analysis_snapshot=analysis_snapshot,
                      planning_result=planning_result,
                      execution_result=execution_result,
                      runtime_models=runtime_models, timestamp=timestamp)
        new = getattr(getattr(st, "mode", None), "value", str(getattr(st, "mode", "")))
        REC["mm_update"].append({
            "step": CUR["step"],
            "prev": str(prev),
            "new": str(new),
            "reasons": [getattr(r, "value", str(r)) for r in (getattr(st, "active_reasons", ()) or ())],
        })
        if str(prev) != str(new):
            REC["mode_transitions"].append({"step": CUR["step"],
                                            "frm": str(prev), "to": str(new)})
        return st

    MM.update = update


def params(wind, ft, vs):
    """Verbatim from outputs/_sc_control.py:35-39 (scenario D)."""
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


def run(seed, p, steps, hooked):
    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from wildfire_model import WildFireModel
    from serve_dashboard import _build_evaluation

    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **p)
    buf = _io.StringIO()
    terminal_step, n = None, 0
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            CUR["step"] = n + 1
            model.step()
            n += 1
            if hooked:
                st = getattr(model, "latest_failsafe_state", None)
                sop = getattr(model, "shared_operational_picture", None)
                REC["sop_mission_mode"].append({
                    "step": n,
                    "failsafe_mode": getattr(getattr(st, "mode", None), "value", None),
                    "sop_mission_mode": getattr(sop, "mission_mode", None),
                })
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = n
    ev = _build_evaluation(model, terminal_step, n, p)
    poslist = sorted(
        "%s:%s:%s" % (type(a).__name__, getattr(a, "unique_id", ""), a.pos)
        for a in model.schedule.agents if type(a).__name__ != "Fire"
    )
    return {
        "eval": {k: ev.get(k) for k in
                 ("rescued", "dead", "unreachable", "never_detected",
                  "geographically_isolated", "firefighter_deaths",
                  "burnt_cells", "rescue_rate", "terminal_step")},
        "stdout_sha256": hashlib.sha256(buf.getvalue().encode("utf-8")).hexdigest(),
        "agent_positions_sha256": hashlib.sha256(
            "\n".join(poslist).encode("utf-8")).hexdigest(),
    }


def _mode_series(rec):
    """Step-by-step mode trajectory from the ModeManager.update HOOK (not a snapshot)."""
    return [(u["step"], u["new"]) for u in rec.get("mm_update", [])]


def _runlen(series):
    out = []
    for _, m in series:
        if out and out[-1][0] == m:
            out[-1][1] += 1
        else:
            out.append([m, 1])
    return [{"mode": m, "steps": n} for m, n in out]


def compare(pattern, out):
    runs = []
    for p in sorted(_glob.glob(pattern)):
        with open(p, "r", encoding="utf-8") as fh:
            runs.append(json.load(fh))
    idx = {}
    for r in runs:
        idx.setdefault(r["mode"], {})["%s|%s" % (r["label"], r["seed"])] = r
    live, armd, nop = idx.get("live", {}), idx.get("arm", {}), idx.get("nopatch", {})

    # ---- H1 aggregate over the LIVE arm (the real system) -------------
    agg = {"crit_calls": 0, "live_true": 0, "corrected_true": 0,
           "zero_gap_calls": 0, "zero_gap_live_true": 0,
           "live_clause": {}, "corrected_clause": {},
           "gap_count_hist": {}, "arg_shape": {},
           "disagree": 0}
    for r in live.values():
        for c in r["crit"]:
            agg["crit_calls"] += 1
            agg["live_true"] += 1 if c["live"] else 0
            agg["corrected_true"] += 1 if c["corrected"] else 0
            if c["gap_count"] == 0:
                agg["zero_gap_calls"] += 1
                agg["zero_gap_live_true"] += 1 if c["live"] else 0
            if c["live"] != c["corrected"]:
                agg["disagree"] += 1
            _bump(agg["live_clause"], c["live_clause"])
            _bump(agg["corrected_clause"], c["corrected_clause"])
            _bump(agg["gap_count_hist"], str(c["gap_count"]))
            _bump(agg["arg_shape"], "%s:%s" % (c["arg_type"], c["arg_len"]))

    pairs = []
    for k in sorted(set(live) & set(armd)):
        lo, ar = live[k], armd[k]
        ls, as_ = _mode_series(lo), _mode_series(ar)
        l_ent = next((s for s, m in ls if m != "normal"), None)
        a_ent = next((s for s, m in as_ if m != "normal"), None)
        l_ir = next((s for s, m in ls if m == "information_recovery"), None)
        a_ir = next((s for s, m in as_ if m == "information_recovery"), None)
        pairs.append({
            "run": k,
            # -- predicate
            "crit_calls": len(lo["crit"]),
            "live_true": sum(1 for c in lo["crit"] if c["live"]),
            "arm_returned_true": sum(1 for c in ar["crit"] if c["corrected"]),
            "arm_severity_changed_calls": sum(1 for c in ar["crit"] if not c["corrected"]),
            # -- mode
            "mode_series_identical": ls == as_,
            "live_first_nonnormal_step": l_ent,
            "arm_first_nonnormal_step": a_ent,
            "live_first_info_recovery_step": l_ir,
            "arm_first_info_recovery_step": a_ir,
            "live_returns_to_normal": any(m == "normal" for s, m in ls if l_ent and s > l_ent),
            "arm_returns_to_normal": any(m == "normal" for s, m in as_ if a_ent and s > a_ent),
            "live_mode_runlen": _runlen(ls),
            "arm_mode_runlen": _runlen(as_),
            "live_transitions": lo["mode_transitions"],
            "arm_transitions": ar["mode_transitions"],
            # -- outcomes, seed-matched
            "eval_identical": lo["eval"] == ar["eval"],
            "eval_live": lo["eval"],
            "eval_arm": ar["eval"],
            "stdout_identical": lo["stdout_sha256"] == ar["stdout_sha256"],
            "pos_identical": lo["agent_positions_sha256"] == ar["agent_positions_sha256"],
        })

    # observer-cleanliness control
    ctrl = []
    for k in sorted(set(live) & set(nop)):
        ctrl.append({
            "run": k,
            "eval_identical": live[k]["eval"] == nop[k]["eval"],
            "stdout_identical": live[k]["stdout_sha256"] == nop[k]["stdout_sha256"],
            "pos_identical": live[k]["agent_positions_sha256"] == nop[k]["agent_positions_sha256"],
        })

    # reason provenance, live arm
    prov = {"analysis_only": 0, "planning_only": 0, "execution_only": 0,
            "mixed": 0, "empty": 0, "reason_hist": {}, "src_hist": {}}
    for r in live.values():
        for e in r["reason_src"]:
            srcs = [s for s in ("analysis", "planning", "execution") if e.get(s)]
            key = "+".join(srcs) if srcs else "empty"
            _bump(prov["src_hist"], key)
            if not srcs:
                prov["empty"] += 1
            elif len(srcs) == 1:
                prov[srcs[0] + "_only"] += 1
            else:
                prov["mixed"] += 1
            for rr in e["final"]:
                _bump(prov["reason_hist"], str(rr))

    # the same, for the armed arm
    prov_arm = {"src_hist": {}, "reason_hist": {}}
    for r in armd.values():
        for e in r["reason_src"]:
            srcs = [s for s in ("analysis", "planning", "execution") if e.get(s)]
            _bump(prov_arm["src_hist"], "+".join(srcs) if srcs else "empty")
            for rr in e["final"]:
                _bump(prov_arm["reason_hist"], str(rr))

    # mission_mode latch
    latch = []
    for k, r in sorted(live.items()):
        rows = r.get("sop_mission_mode") or []
        mism = [x for x in rows if x["failsafe_mode"] == "normal"
                and x["sop_mission_mode"] not in (None, "normal")]
        latch.append({"run": k, "steps": len(rows),
                      "normal_but_sop_stale": len(mism),
                      "first_mismatch": mism[0] if mism else None,
                      "sop_values": sorted({str(x["sop_mission_mode"]) for x in rows})})

    doc = {"head": "319d404", "n_runs": len(runs),
           "predicate_aggregate_live": agg,
           "observer_control": ctrl,
           "live_vs_arm": pairs,
           "reason_provenance_live": prov,
           "reason_provenance_arm": prov_arm,
           "mission_mode_latch": latch,
           "planning_text_sample": (list(live.values())[0]["planning_text_sample"]
                                    if live else []),
           "runs": runs}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    print("WROTE %s (%d runs)" % (out, len(runs)))
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["nopatch", "live", "arm"], default="live")
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", choices=["half", "default"], default="half")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--out")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--glob", default=os.path.join(BASE, "_bgc_run_*.json"))
    a = ap.parse_args()

    if a.compare:
        compare(a.glob, a.out or os.path.join(BASE, "_bgc_probe.json"))
        sys.exit(0)

    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    p = params(a.wind, ft, vs)
    label = "D/%s/%s" % (a.wind, a.roles)
    hooked = a.mode != "nopatch"
    if hooked:
        install(arm=(a.mode == "arm"))
    base = run(a.seed, p, a.steps, hooked)
    res = dict(REC)
    res.update({"label": label, "seed": a.seed, "steps": a.steps, "mode": a.mode,
                "eval": base["eval"], "stdout_sha256": base["stdout_sha256"],
                "agent_positions_sha256": base["agent_positions_sha256"]})
    ser = _mode_series(res)
    print("%-7s %s|%-4d crit=%d live_true=%d corr_true=%d zero_gap=%d | "
          "modes=%s | first_nonnormal=%s | rescued=%s dead=%s ff=%s nd=%s ts=%s"
          % (a.mode, label, a.seed, res["crit_calls"],
             sum(1 for c in res["crit"] if c["live"]),
             sum(1 for c in res["crit"] if c["corrected"]),
             sum(1 for c in res["crit"] if c["gap_count"] == 0),
             json.dumps(_runlen(ser))[:200],
             next((s for s, m in ser if m != "normal"), None),
             base["eval"].get("rescued"), base["eval"].get("dead"),
             base["eval"].get("firefighter_deaths"),
             base["eval"].get("never_detected"),
             base["eval"].get("terminal_step")),
          flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, default=str)
