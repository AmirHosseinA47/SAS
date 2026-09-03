"""belief_gap_regions runtime probe (global_adaptation_generator.py:437-476).

Question: _generate_coverage_strategy_options reads fire_probability_map /
fire_confidence_map off ``global_analysis_result`` then ``runtime_models``.
Neither container carries those keys, so both lookups fall through to {} and
belief_gap_regions (l.467-476) is permanently []. Measure, do not assume.

THREE MODES, one process per (mode, combo, seed):

  observe  - PURE OBSERVERS. Every wrapper calls the original, records, and
             returns the original result unchanged. Records, per call to
             _generate_coverage_strategy_options, the ACTUAL live values by
             reading them back off the returned option ``parameters`` dict
             (base_parameters embeds all four maps; target_regions IS
             belief_gap_regions) - no predicate is reimplemented.
             Alongside, the COUNTERFACTUAL population is computed from
             runtime_models["fire_runtime_model"].belief, which is where the
             maps actually live, using the source predicate verbatim.
             Also wraps GlobalMissionPlanner.plan to record whether the
             belief-gap option survived constraint filtering into the space,
             and what the planner actually selected.

  nopatch  - no wrappers at all. Same seeds. Proves observer purity by
             matching observe eval + stdout sha + agent-position sha.

  arm      - COUNTERFACTUAL. Makes the lookup satisfiable by handing
             _generate_coverage_strategy_options a copy of
             global_analysis_result carrying the real belief maps, so
             belief_gap_regions is populated exactly as a fix would populate
             it. Observers still installed. Compared against nopatch on eval
             + position sha to answer "would any outcome change".

Scenario params verbatim from outputs/_sc_control.py:35-39 (scenario D), so
this is the same canonical 13-run sample used by the previous rounds.

usage:
  _bg_probe.py --mode observe --wind east --roles half --seed 101 --out P.json
  _bg_probe.py --aggregate --glob "outputs/_bg_run_*.json" --out outputs/_bg_probe.json
"""
from __future__ import annotations
import argparse, contextlib, glob as _glob, hashlib, io as _io, json, os, random, sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

BG_ID = "global_coverage_strategy_belief_gap_reduction_strategy"


def params(wind, ft, vs):
    """Verbatim from outputs/_sc_control.py:35-39 (scenario D)."""
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


CUR = {"step": 0}
REC = {
    # --- _generate_coverage_strategy_options ---
    "cso_calls": 0,
    "cso_bg_option_emitted": 0,       # belief-gap option present in the return
    "live_fpm_nonempty": 0,           # fire_probability_map  as actually read
    "live_fcm_nonempty": 0,           # fire_confidence_map   as actually read
    "live_um_nonempty": 0,            # uncertainty_map       as actually read
    "live_vc_nonempty": 0,            # victim_confidence     as actually read
    "live_fpm_types": {},             # type(value) histogram
    "live_fcm_types": {},
    "live_bgr_nonempty": 0,           # belief_gap_regions non-empty
    "live_bgr_sizes": {},             # len(belief_gap_regions) histogram
    "gar_has_fpm_key": 0,             # did global_analysis_result carry the key
    "gar_has_fcm_key": 0,
    "rm_has_fpm_key": 0,              # did runtime_models carry the key
    "rm_has_fcm_key": 0,
    "gar_keys_sample": None,
    "rm_keys_sample": None,

    # --- counterfactual population, from the belief where the maps live ---
    "cf_belief_reachable": 0,
    "cf_fpm_sizes": [],               # len(belief.fire_probability_map) per call
    "cf_fcm_sizes": [],
    "cf_bgr_sizes": [],               # len(counterfactual belief_gap_regions)
    "cf_bgr_nonempty": 0,
    "cf_bgr_max": 0,
    "cf_bgr_example": None,

    # --- GlobalMissionPlanner.plan ---
    "plan_calls": 0,
    "plan_bg_in_space": 0,            # belief-gap option survived filtering
    "plan_candidates": [],            # len(global_space.options) per call
    "selected_hist": {},              # selected_option_id -> count
    "bg_selected": 0,
    "bg_selected_decision": [],       # decision fields when bg WAS selected
}


def _bump(d, k):
    d[k] = d.get(k, 0) + 1


def install(arm: bool):
    from src_extension.adaptation.global_adaptation_generator import (
        GlobalAdaptationSpaceGenerator as G,
    )
    from src_extension.planning.global_mission_planner import GlobalMissionPlanner as P

    orig_cso = G._generate_coverage_strategy_options

    def cso(self, gar, rm, ts):
        # ---- what the source lookups see, before anything is changed
        if REC["gar_keys_sample"] is None and isinstance(gar, dict):
            REC["gar_keys_sample"] = sorted(gar.keys())
        if REC["rm_keys_sample"] is None and isinstance(rm, dict):
            REC["rm_keys_sample"] = sorted(rm.keys())
        if isinstance(gar, dict):
            if "fire_probability_map" in gar:
                REC["gar_has_fpm_key"] += 1
            if "fire_confidence_map" in gar:
                REC["gar_has_fcm_key"] += 1
        if isinstance(rm, dict):
            if "fire_probability_map" in rm:
                REC["rm_has_fpm_key"] += 1
            if "fire_confidence_map" in rm:
                REC["rm_has_fcm_key"] += 1

        # ---- counterfactual population, from where the maps actually live
        belief = getattr(rm.get("fire_runtime_model") if isinstance(rm, dict) else None,
                         "belief", None)
        if belief is not None:
            REC["cf_belief_reachable"] += 1
            cf_fpm = belief.fire_probability_map
            cf_fcm = belief.fire_confidence_map
            REC["cf_fpm_sizes"].append(len(cf_fpm))
            REC["cf_fcm_sizes"].append(len(cf_fcm))
            # source predicate verbatim (l.469-476)
            cf_bgr = [
                region
                for region, probability in cf_fpm.items()
                if isinstance(probability, (int, float))
                and probability >= 0.5
                and isinstance(cf_fcm.get(region), (int, float))
                and cf_fcm[region] <= 0.5
            ]
            REC["cf_bgr_sizes"].append(len(cf_bgr))
            if cf_bgr:
                REC["cf_bgr_nonempty"] += 1
                if len(cf_bgr) > REC["cf_bgr_max"]:
                    REC["cf_bgr_max"] = len(cf_bgr)
                    REC["cf_bgr_example"] = {
                        "step": CUR["step"],
                        "n": len(cf_bgr),
                        "first10": [list(c) for c in sorted(cf_bgr)[:10]],
                    }

        # ---- ARM: make the lookup satisfiable, exactly as a fix would
        call_gar = gar
        if arm and isinstance(gar, dict) and belief is not None:
            call_gar = {**gar,
                        "fire_probability_map": dict(belief.fire_probability_map),
                        "fire_confidence_map": dict(belief.fire_confidence_map)}

        out = orig_cso(self, call_gar, rm, ts)

        # ---- read the LIVE values back off the emitted option
        REC["cso_calls"] += 1
        for o in out:
            if getattr(o, "option_id", "") != BG_ID:
                continue
            REC["cso_bg_option_emitted"] += 1
            pr = o.parameters
            fpm, fcm = pr.get("fire_probability_map"), pr.get("fire_confidence_map")
            um, vc = pr.get("uncertainty_map"), pr.get("victim_confidence")
            bgr = pr.get("target_regions")
            _bump(REC["live_fpm_types"], type(fpm).__name__)
            _bump(REC["live_fcm_types"], type(fcm).__name__)
            if fpm:
                REC["live_fpm_nonempty"] += 1
            if fcm:
                REC["live_fcm_nonempty"] += 1
            if um:
                REC["live_um_nonempty"] += 1
            if vc:
                REC["live_vc_nonempty"] += 1
            if bgr:
                REC["live_bgr_nonempty"] += 1
            _bump(REC["live_bgr_sizes"], str(len(bgr) if bgr is not None else -1))
            break
        return out

    G._generate_coverage_strategy_options = cso

    orig_plan = P.plan

    def plan(self, *a, **kw):
        snap = kw.get("adaptation_space_snapshot")
        gs = getattr(snap, "global_space", None)
        opts = getattr(gs, "options", None) or []
        ids = [str(getattr(o, "option_id", "")) for o in opts]
        REC["plan_calls"] += 1
        REC["plan_candidates"].append(len(ids))
        if BG_ID in ids:
            REC["plan_bg_in_space"] += 1
        out = orig_plan(self, *a, **kw)
        sel = str(getattr(out, "selected_option_id", "") or "<none>")
        _bump(REC["selected_hist"], sel)
        if sel == BG_ID:
            REC["bg_selected"] += 1
            if len(REC["bg_selected_decision"]) < 20:
                REC["bg_selected_decision"].append({
                    "step": CUR["step"],
                    "uav_assignments": dict(getattr(out, "uav_assignments", {}) or {}),
                    "task_assignments": dict(getattr(out, "task_assignments", {}) or {}),
                    "mission_mode": getattr(out, "mission_mode", ""),
                    "recall_orders": list(getattr(out, "recall_orders", ()) or ()),
                    "uncertainty_context_keys": sorted(
                        (getattr(out, "uncertainty_context", {}) or {}).keys()),
                })
        return out

    P.plan = plan


def run(seed, p, steps):
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
            if terminal_step is None:
                panel = model.get_dashboard_state()
                if (panel.get("mission_status", {}) or {}).get("all_victims_terminal"):
                    terminal_step = n
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


def summarise(label, seed, steps, mode, base):
    cf = REC["cf_bgr_sizes"]
    return {
        "label": label, "seed": seed, "steps": steps, "mode": mode,
        "eval": base["eval"],
        "stdout_sha256": base["stdout_sha256"],
        "agent_positions_sha256": base["agent_positions_sha256"],
        "cso_calls": REC["cso_calls"],
        "cso_bg_option_emitted": REC["cso_bg_option_emitted"],
        "gar_has_fpm_key": REC["gar_has_fpm_key"],
        "gar_has_fcm_key": REC["gar_has_fcm_key"],
        "rm_has_fpm_key": REC["rm_has_fpm_key"],
        "rm_has_fcm_key": REC["rm_has_fcm_key"],
        "gar_keys_sample": REC["gar_keys_sample"],
        "rm_keys_sample": REC["rm_keys_sample"],
        "live_fpm_nonempty": REC["live_fpm_nonempty"],
        "live_fcm_nonempty": REC["live_fcm_nonempty"],
        "live_um_nonempty": REC["live_um_nonempty"],
        "live_vc_nonempty": REC["live_vc_nonempty"],
        "live_fpm_types": REC["live_fpm_types"],
        "live_fcm_types": REC["live_fcm_types"],
        "live_bgr_nonempty": REC["live_bgr_nonempty"],
        "live_bgr_sizes": REC["live_bgr_sizes"],
        "cf_belief_reachable": REC["cf_belief_reachable"],
        "cf_fpm_max": max(REC["cf_fpm_sizes"]) if REC["cf_fpm_sizes"] else None,
        "cf_fcm_max": max(REC["cf_fcm_sizes"]) if REC["cf_fcm_sizes"] else None,
        "cf_bgr_nonempty": REC["cf_bgr_nonempty"],
        "cf_bgr_max": REC["cf_bgr_max"],
        "cf_bgr_mean": (sum(cf) / len(cf)) if cf else None,
        "cf_bgr_example": REC["cf_bgr_example"],
        "cf_bgr_sizes_tail": cf[-20:],
        "plan_calls": REC["plan_calls"],
        "plan_bg_in_space": REC["plan_bg_in_space"],
        "plan_candidates_max": max(REC["plan_candidates"]) if REC["plan_candidates"] else None,
        "selected_hist": REC["selected_hist"],
        "bg_selected": REC["bg_selected"],
        "bg_selected_decision": REC["bg_selected_decision"],
    }


def aggregate(pattern, out):
    runs = []
    for p in sorted(_glob.glob(pattern)):
        with open(p, "r", encoding="utf-8") as fh:
            runs.append(json.load(fh))
    by_mode = {}
    for r in runs:
        by_mode.setdefault(r["mode"], []).append(r)
    tot = {}
    for r in by_mode.get("observe", []):
        for k in ("cso_calls", "cso_bg_option_emitted", "live_fpm_nonempty",
                  "live_fcm_nonempty", "live_um_nonempty", "live_vc_nonempty",
                  "live_bgr_nonempty", "gar_has_fpm_key", "gar_has_fcm_key",
                  "rm_has_fpm_key", "rm_has_fcm_key", "cf_belief_reachable",
                  "cf_bgr_nonempty", "plan_calls", "plan_bg_in_space",
                  "bg_selected"):
            tot[k] = tot.get(k, 0) + (r.get(k) or 0)
    sel = {}
    for r in by_mode.get("observe", []):
        for k, v in r["selected_hist"].items():
            sel[k] = sel.get(k, 0) + v
    arm_sel = {}
    for r in by_mode.get("arm", []):
        for k, v in r["selected_hist"].items():
            arm_sel[k] = arm_sel.get(k, 0) + v

    def idx(mode):
        return {"%s|%s" % (r["label"], r["seed"]): r for r in by_mode.get(mode, [])}

    obs, nop, arm = idx("observe"), idx("nopatch"), idx("arm")
    purity, impact = [], []
    for k in sorted(nop):
        if k in obs:
            purity.append({
                "run": k,
                "pos_match": obs[k]["agent_positions_sha256"] == nop[k]["agent_positions_sha256"],
                "stdout_match": obs[k]["stdout_sha256"] == nop[k]["stdout_sha256"],
                "eval_match": obs[k]["eval"] == nop[k]["eval"],
            })
        if k in arm:
            impact.append({
                "run": k,
                "pos_match": arm[k]["agent_positions_sha256"] == nop[k]["agent_positions_sha256"],
                "stdout_match": arm[k]["stdout_sha256"] == nop[k]["stdout_sha256"],
                "eval_match": arm[k]["eval"] == nop[k]["eval"],
                "eval_nopatch": nop[k]["eval"],
                "eval_arm": arm[k]["eval"],
                "arm_live_bgr_nonempty": arm[k]["live_bgr_nonempty"],
                "arm_live_bgr_sizes": arm[k]["live_bgr_sizes"],
                "arm_cso_calls": arm[k]["cso_calls"],
                "arm_bg_selected": arm[k]["bg_selected"],
            })
    doc = {"head": "93f23b7", "n_runs": len(runs),
           "n_by_mode": {m: len(v) for m, v in by_mode.items()},
           "observe_totals": tot, "selected_hist_all": sel,
           "arm_selected_hist_all": arm_sel,
           "purity": purity, "impact": impact, "runs": runs}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    print("WROTE %s (%d runs)" % (out, len(runs)))
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["observe", "nopatch", "arm"], default="observe")
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", choices=["half", "default"], default="half")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--out")
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--glob", default=os.path.join(BASE, "_bg_run_*.json"))
    a = ap.parse_args()

    if a.aggregate:
        aggregate(a.glob, a.out or os.path.join(BASE, "_bg_probe.json"))
        sys.exit(0)

    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    p = params(a.wind, ft, vs)
    label = "D/%s/%s" % (a.wind, a.roles)
    if a.mode != "nopatch":
        install(arm=(a.mode == "arm"))
    base = run(a.seed, p, a.steps)
    if a.mode == "nopatch":
        res = {"label": label, "seed": a.seed, "steps": a.steps, "mode": "nopatch",
               "eval": base["eval"], "stdout_sha256": base["stdout_sha256"],
               "agent_positions_sha256": base["agent_positions_sha256"],
               "selected_hist": {}}
        print("nopatch %s|%-4d pos=%s rescued=%s dead=%s term=%s"
              % (label, a.seed, base["agent_positions_sha256"][:16],
                 base["eval"]["rescued"], base["eval"]["dead"],
                 base["eval"]["terminal_step"]), flush=True)
    else:
        res = summarise(label, a.seed, a.steps, a.mode, base)
        print("%-7s %s|%-4d cso=%d bgopt=%d | LIVE fpm=%d fcm=%d bgr=%d sizes=%s "
              "| CF fpm_max=%s bgr_nonempty=%d/%d bgr_max=%d | plan=%d bg_in_space=%d "
              "bg_sel=%d | pos=%s"
              % (a.mode, label, a.seed, res["cso_calls"], res["cso_bg_option_emitted"],
                 res["live_fpm_nonempty"], res["live_fcm_nonempty"],
                 res["live_bgr_nonempty"], json.dumps(res["live_bgr_sizes"]),
                 res["cf_fpm_max"], res["cf_bgr_nonempty"], res["cf_belief_reachable"],
                 res["cf_bgr_max"], res["plan_calls"], res["plan_bg_in_space"],
                 res["bg_selected"], base["agent_positions_sha256"][:16]), flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, default=str)
