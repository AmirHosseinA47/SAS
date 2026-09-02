"""Recovery-subgraph runtime probe (defect #7 follow-up, re-verification at HEAD).

Measures, per run, the WHOLE ModeManager recovery subgraph:

  1. should_return_to_normal()        -> call count
  2. stable_recovery_counter          -> full trajectory, max, distinct set,
                                         count of non-zero observations
  3. _update_stable_recovery_counter  -> call count + WHICH BRANCH each call
                                         took (normal_reset / satisfied_increment
                                         / unsatisfied_reset) and the mode at the
                                         moment the call ran
  4. _recovery_conditions_satisfied   -> call count, return distribution,
                                         attributed to its caller
  5. FailSafeMode distribution over every update() call
  6. _information_recovery_ready / _information_sufficiency_score /
     _mean_fire_confidence_map / _information_triggers_present -> reached? with
     what results?

EVERY patch is an OBSERVER: it calls the original, records, and returns the
original's result unchanged. No wrapper mutates state, consumes RNG, or alters
control flow. --nopatch runs the same simulation with NO wrappers installed, so
observer-purity is checkable rather than asserted (compare eval + positions sha).

Branch derivation for (3) is done WITHOUT re-running any predicate: the wrapper
reads mode and counter before, calls the original, reads counter after.
  mode == normal              -> normal_reset      (l.139-141)
  counter_after == before + 1 -> satisfied_increment (l.143)
  otherwise                   -> unsatisfied_reset   (l.145)
These are mutually exclusive because the increment branch always yields
before+1 >= 1, which can never equal the reset branch's 0 when before is 0, and
can never equal before for any before.

Scenario params are copied from outputs/_sc_control.py params() so the runs are
the canonical 13-run sample. One process per run (module globals are mutated by
apply_scenario_config, and REC accumulates), driven sequentially.

usage:
    _rh_probe.py --wind east  --roles half    --seed 101 --out <path>
    _rh_probe.py --wind east  --roles half    --seed 101 --out <path> --nopatch
    _rh_probe.py --aggregate --glob outputs/_rh_run_*.json --out outputs/_rh_probe.json
"""
from __future__ import annotations
import argparse, contextlib, glob as _glob, hashlib, io as _io, json, os, random, sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))


def params(wind, ft, vs):
    """Verbatim from outputs/_sc_control.py:35-39 (scenario D)."""
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


CUR = {"step": 0}

REC = {
    # --- (5) update() ---
    "update_calls": 0,
    "mode_hist": {},                 # mode after update() -> count
    "reason_hist": {},               # ",".join(active_reasons) -> count
    "mode_transitions": [],          # (step, prev_mode, new_mode, reasons)

    # --- (1) should_return_to_normal ---
    "srn_calls": 0,
    "srn_results": {},               # "mode|result" -> count

    # --- (2)+(3) counter ---
    "usrc_calls": 0,
    "usrc_branch": {},               # branch -> count
    "usrc_mode_at_entry": {},        # mode at the moment the counter update ran
    "usrc_branch_by_mode": {},       # "mode|branch" -> count
    "counter_traj": [],              # counter value AFTER each usrc call
    "counter_modes": [],             # mode at entry for each usrc call
    "counter_nonzero_events": [],    # (step, mode, before, after) when after != 0

    # --- (4) _recovery_conditions_satisfied ---
    "rcs_calls": 0,
    "rcs_true": 0,
    "rcs_by": {},                    # "caller|mode|result" -> count
    "rcs_empty_reasons": 0,          # calls where active_reasons was empty
                                     # (the `if not reasons: return True` path)

    # --- (6) information-recovery helpers ---
    "irr_calls": 0,
    "irr_by": {},                    # "has_info_reason|result" -> count
    "iss_calls": 0,
    "iss_values": {},                # str(score) -> count
    "mfc_calls": 0,
    "mfc_values": {},                # "None" or str(round(v,3)) -> count
    "itp_calls": 0,
    "itp_values": {},                # "True"/"False" -> count

    # --- step-level ---
    "step_mode": [],                 # (step, mode at end of step)
}

CTX = {"in_usrc": False, "in_srn": False}


def install_patches():
    from src_extension.execution.mode_manager import ModeManager

    # ---------------------------------------------------------- update()
    _orig_update = ModeManager.update

    def _update(self, *a, **k):
        prev_mode = self.current_state.mode.value if self.current_state else "?"
        out = _orig_update(self, *a, **k)
        REC["update_calls"] += 1
        m = out.mode.value
        REC["mode_hist"][m] = REC["mode_hist"].get(m, 0) + 1
        rk = ",".join(r.value for r in out.active_reasons) or "<none>"
        REC["reason_hist"][rk] = REC["reason_hist"].get(rk, 0) + 1
        if m != prev_mode:
            REC["mode_transitions"].append((CUR["step"], prev_mode, m, rk))
        return out

    ModeManager.update = _update

    # ------------------------------------------- should_return_to_normal()
    _orig_srn = ModeManager.should_return_to_normal

    def _srn(self, *a, **k):
        REC["srn_calls"] += 1
        CTX["in_srn"] = True
        try:
            out = _orig_srn(self, *a, **k)
        finally:
            CTX["in_srn"] = False
        key = "%s|%s" % (self.current_state.mode.value, bool(out))
        REC["srn_results"][key] = REC["srn_results"].get(key, 0) + 1
        return out

    ModeManager.should_return_to_normal = _srn

    # --------------------------------- _update_stable_recovery_counter()
    _orig_usrc = ModeManager._update_stable_recovery_counter

    def _usrc(self, **kw):
        mode_before = self.current_state.mode.value
        c_before = self.stable_recovery_counter
        CTX["in_usrc"] = True
        try:
            out = _orig_usrc(self, **kw)
        finally:
            CTX["in_usrc"] = False
        c_after = self.stable_recovery_counter
        if mode_before == "normal":
            branch = "normal_reset"
        elif c_after == c_before + 1:
            branch = "satisfied_increment"
        else:
            branch = "unsatisfied_reset"
        REC["usrc_calls"] += 1
        REC["usrc_branch"][branch] = REC["usrc_branch"].get(branch, 0) + 1
        REC["usrc_mode_at_entry"][mode_before] = (
            REC["usrc_mode_at_entry"].get(mode_before, 0) + 1)
        bk = "%s|%s" % (mode_before, branch)
        REC["usrc_branch_by_mode"][bk] = REC["usrc_branch_by_mode"].get(bk, 0) + 1
        REC["counter_traj"].append(c_after)
        REC["counter_modes"].append(mode_before)
        if c_after != 0 and len(REC["counter_nonzero_events"]) < 2000:
            REC["counter_nonzero_events"].append(
                (CUR["step"], mode_before, c_before, c_after))
        return out

    ModeManager._update_stable_recovery_counter = _usrc

    # ------------------------------- _recovery_conditions_satisfied()
    _orig_rcs = ModeManager._recovery_conditions_satisfied

    def _rcs(self, runtime_models, analysis_snapshot):
        n_reasons = len(self.current_state.active_reasons)
        mode = self.current_state.mode.value
        out = _orig_rcs(self, runtime_models, analysis_snapshot)
        REC["rcs_calls"] += 1
        if out:
            REC["rcs_true"] += 1
        if n_reasons == 0:
            REC["rcs_empty_reasons"] += 1
        caller = "usrc" if CTX["in_usrc"] else ("srn" if CTX["in_srn"] else "other")
        key = "%s|%s|%s" % (caller, mode, bool(out))
        REC["rcs_by"][key] = REC["rcs_by"].get(key, 0) + 1
        return out

    ModeManager._recovery_conditions_satisfied = _rcs

    # ------------------------------------- information-recovery helpers
    _orig_irr = ModeManager._information_recovery_ready

    def _irr(self, runtime_models, analysis_snapshot, reasons):
        from src_extension.execution.mode_manager import _INFORMATION_REASONS
        has_info = bool(set(reasons) & _INFORMATION_REASONS)
        out = _orig_irr(self, runtime_models, analysis_snapshot, reasons)
        REC["irr_calls"] += 1
        key = "%s|%s" % (has_info, bool(out))
        REC["irr_by"][key] = REC["irr_by"].get(key, 0) + 1
        return out

    ModeManager._information_recovery_ready = _irr

    _orig_iss = ModeManager._information_sufficiency_score

    def _iss(self, runtime_models, analysis_snapshot):
        out = _orig_iss(self, runtime_models, analysis_snapshot)
        REC["iss_calls"] += 1
        k = repr(round(float(out), 4))
        REC["iss_values"][k] = REC["iss_values"].get(k, 0) + 1
        return out

    ModeManager._information_sufficiency_score = _iss

    _orig_mfc = ModeManager._mean_fire_confidence_map

    def _mfc(self, runtime_models, analysis_snapshot):
        out = _orig_mfc(self, runtime_models, analysis_snapshot)
        REC["mfc_calls"] += 1
        k = "None" if out is None else repr(round(float(out), 3))
        REC["mfc_values"][k] = REC["mfc_values"].get(k, 0) + 1
        return out

    ModeManager._mean_fire_confidence_map = _mfc

    _orig_itp = ModeManager._information_triggers_present

    def _itp(self, analysis_snapshot):
        out = _orig_itp(self, analysis_snapshot)
        REC["itp_calls"] += 1
        k = str(bool(out))
        REC["itp_values"][k] = REC["itp_values"].get(k, 0) + 1
        return out

    ModeManager._information_triggers_present = _itp


# ------------------------------------------------------------------ runner
def run(seed, p, steps, patched):
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
    terminal_step = None
    n = 0
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            CUR["step"] = n + 1
            model.step()
            n += 1
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = n
            if patched:
                fs = getattr(model, "latest_failsafe_state", None)
                mo = getattr(fs, "mode", None) if fs is not None else None
                REC["step_mode"].append(
                    (n, mo.value if hasattr(mo, "value") else str(mo)))
    ev = _build_evaluation(model, terminal_step, n, p)
    text = buf.getvalue()
    poslist = sorted(
        "%s:%s:%s" % (type(a).__name__, getattr(a, "unique_id", ""), a.pos)
        for a in model.schedule.agents if type(a).__name__ != "Fire"
    )
    return {
        "eval": {k: ev.get(k) for k in
                 ("rescued", "dead", "unreachable", "never_detected",
                  "geographically_isolated", "firefighter_deaths",
                  "burnt_cells", "rescue_rate", "terminal_step")},
        "stdout_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "agent_positions_sha256": hashlib.sha256(
            "\n".join(poslist).encode("utf-8")).hexdigest(),
    }


def summarise(label, seed, steps, base):
    traj = REC["counter_traj"]
    return {
        "label": label,
        "seed": seed,
        "steps": steps,
        "eval": base["eval"],
        "stdout_sha256": base["stdout_sha256"],
        "agent_positions_sha256": base["agent_positions_sha256"],

        "update_calls": REC["update_calls"],
        "mode_hist": REC["mode_hist"],
        "reason_hist": REC["reason_hist"],
        "n_mode_transitions": len(REC["mode_transitions"]),
        "mode_transitions": REC["mode_transitions"][:60],

        "srn_calls": REC["srn_calls"],
        "srn_results": REC["srn_results"],

        "usrc_calls": REC["usrc_calls"],
        "usrc_branch": REC["usrc_branch"],
        "usrc_mode_at_entry": REC["usrc_mode_at_entry"],
        "usrc_branch_by_mode": REC["usrc_branch_by_mode"],
        "counter_max": max(traj) if traj else None,
        "counter_distinct": sorted(set(traj)),
        "counter_nonzero_obs": sum(1 for v in traj if v != 0),
        "counter_len": len(traj),
        "counter_nonzero_events": REC["counter_nonzero_events"][:200],
        "counter_traj": traj,

        "rcs_calls": REC["rcs_calls"],
        "rcs_true": REC["rcs_true"],
        "rcs_by": REC["rcs_by"],
        "rcs_empty_reasons": REC["rcs_empty_reasons"],

        "irr_calls": REC["irr_calls"],
        "irr_by": REC["irr_by"],
        "iss_calls": REC["iss_calls"],
        "iss_values": REC["iss_values"],
        "mfc_calls": REC["mfc_calls"],
        "mfc_values": REC["mfc_values"],
        "itp_calls": REC["itp_calls"],
        "itp_values": REC["itp_values"],

        "step_mode_tail": REC["step_mode"][-5:],
    }


def aggregate(pattern, out):
    runs = []
    for path in sorted(_glob.glob(pattern)):
        with open(path, "r", encoding="utf-8") as fh:
            runs.append(json.load(fh))
    tot = {"update_calls": 0, "srn_calls": 0, "usrc_calls": 0,
           "rcs_calls": 0, "rcs_true": 0, "irr_calls": 0, "iss_calls": 0,
           "mfc_calls": 0, "itp_calls": 0, "counter_nonzero_obs": 0}
    mode_hist, branch, mode_at_entry, rcs_by = {}, {}, {}, {}
    iss_v, mfc_v, itp_v, irr_by, reason_hist = {}, {}, {}, {}, {}
    for r in runs:
        for k in tot:
            tot[k] += r.get(k, 0) or 0
        for src, dst in ((r["mode_hist"], mode_hist), (r["usrc_branch"], branch),
                         (r["usrc_mode_at_entry"], mode_at_entry),
                         (r["rcs_by"], rcs_by), (r["iss_values"], iss_v),
                         (r["mfc_values"], mfc_v), (r["itp_values"], itp_v),
                         (r["irr_by"], irr_by), (r["reason_hist"], reason_hist)):
            for k, v in src.items():
                dst[k] = dst.get(k, 0) + v
    doc = {
        "head": "3b1ffbf",
        "n_runs": len(runs),
        "totals": tot,
        "mode_hist_all": mode_hist,
        "reason_hist_all": reason_hist,
        "usrc_branch_all": branch,
        "usrc_mode_at_entry_all": mode_at_entry,
        "rcs_by_all": rcs_by,
        "iss_values_all": iss_v,
        "mfc_values_all": mfc_v,
        "itp_values_all": itp_v,
        "irr_by_all": irr_by,
        "counter_max_over_all": max(
            [r["counter_max"] for r in runs if r["counter_max"] is not None] or [None]),
        "counter_distinct_union": sorted(
            {v for r in runs for v in r["counter_distinct"]}),
        "runs": runs,
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    print("WROTE %s  (%d runs)" % (out, len(runs)))
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", choices=["half", "default"], default="half")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--out")
    ap.add_argument("--nopatch", action="store_true")
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--glob", default=os.path.join(BASE, "_rh_run_*.json"))
    a = ap.parse_args()

    if a.aggregate:
        aggregate(a.glob, a.out or os.path.join(BASE, "_rh_probe.json"))
        sys.exit(0)

    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    p = params(a.wind, ft, vs)
    label = "D/%s/%s" % (a.wind, a.roles)
    if not a.nopatch:
        install_patches()
    base = run(a.seed, p, a.steps, patched=not a.nopatch)
    if a.nopatch:
        res = {"label": label, "seed": a.seed, "steps": a.steps, "nopatch": True,
               "eval": base["eval"], "stdout_sha256": base["stdout_sha256"],
               "agent_positions_sha256": base["agent_positions_sha256"]}
        print("NOPATCH %s|%d pos_sha=%s stdout_sha=%s rescued=%s dead=%s term=%s"
              % (label, a.seed, base["agent_positions_sha256"][:16],
                 base["stdout_sha256"][:16], base["eval"]["rescued"],
                 base["eval"]["dead"], base["eval"]["terminal_step"]), flush=True)
    else:
        res = summarise(label, a.seed, a.steps, base)
        print("%s|%-4d upd=%d modes=%s | srn=%d | usrc=%d branches=%s "
              "mode@entry=%s | ctr max=%s distinct=%s nonzero=%d | rcs=%d/%d T "
              "| irr=%d iss=%d mfc=%d itp=%d | pos_sha=%s"
              % (label, a.seed, res["update_calls"], json.dumps(res["mode_hist"]),
                 res["srn_calls"], res["usrc_calls"], json.dumps(res["usrc_branch"]),
                 json.dumps(res["usrc_mode_at_entry"]), res["counter_max"],
                 res["counter_distinct"], res["counter_nonzero_obs"],
                 res["rcs_true"], res["rcs_calls"], res["irr_calls"],
                 res["iss_calls"], res["mfc_calls"], res["itp_calls"],
                 base["agent_positions_sha256"][:16]), flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, default=str)
