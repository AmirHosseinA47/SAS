"""belief_gap_regions PLANNER-GATE probe (round 2).

Probe 1 (_bg_probe.py) established: belief_gap_regions is [] on 240/240 calls,
the belief-gap option nevertheless reaches the planner on 240/240 steps, and
GlobalMissionPlanner.plan selected global_stability_maintain_current_config on
2400/2400 calls. Probe 1 could not say WHY, nor whether populating
target_regions changes the option's standing at all.

This probe answers three things by hooking the scoring layer directly
(NOT by reading a per-step snapshot):

  Q1  Which branch of _select_feasible_option fires?
        for entry in scored:                       <- "feasible_loop"
            if entry.evaluation.feasible: return entry.option
        return find_maintain_option(options)       <- "maintain_fallback"
      H1 = maintain is genuinely the top-scoring feasible option every step.
      H2 = nothing is ever feasible and the fallback always returns maintain,
           i.e. the WHOLE global option space is inert, not just belief-gap.

  Q2  Where does the belief-gap option rank, what is its utility, is it
      feasible, and what constraint violations does it carry?

  Q3  THE CRUX. Does populating target_regions change the belief-gap option's
      utility score, feasibility, or rank AT ALL? Run --mode observe (live,
      target_regions=[]) and --mode arm (target_regions populated from the real
      belief) on the SAME seed. Probe 1 proved arm and nopatch produce
      byte-identical trajectories, so the two runs walk identical state and the
      per-step score series are directly comparable. If the series are equal
      element-for-element, target_regions provably does not enter scoring and no
      fix to the lookup could ever promote the option.

Both modes install observers; arm additionally makes the lookup satisfiable the
same way _bg_probe.py --mode arm does (a copy of global_analysis_result carrying
the real belief maps). Scenario params verbatim from outputs/_sc_control.py:35-39.

usage:
  _bg_probe2.py --mode observe --wind east --roles half --seed 101 --out P.json
  _bg_probe2.py --compare --glob "outputs/_bg2_run_*.json" --out outputs/_bg_probe2.json
"""
from __future__ import annotations
import argparse, contextlib, glob as _glob, hashlib, io as _io, json, os, random, sys

os.environ.setdefault("MPLBACKEND", "Agg")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))

BG_ID = "global_coverage_strategy_belief_gap_reduction_strategy"
MAINTAIN_ID = "global_stability_maintain_current_config"

CUR = {"step": 0}
REC = {
    "plan_calls": 0,
    "branch_hist": {},            # feasible_loop / maintain_fallback / none
    "n_options": [],              # len(mission_options) per plan call
    "n_feasible": [],             # how many scored entries were feasible
    "feasible_ids": {},           # option_id -> times it was feasible
    "selected_hist": {},

    # belief-gap option, per plan call
    "bg_present": 0,
    "bg_rank": [],                # 0-based rank in the score-sorted tuple
    "bg_score": [],               # total_utility
    "bg_feasible": 0,
    "bg_violations": {},          # violation tuple -> count
    "bg_target_regions_len": [],  # len(parameters["target_regions"]) at scoring time

    # maintain option, per plan call
    "mt_present": 0,
    "mt_rank": [],
    "mt_score": [],
    "mt_feasible": 0,

    # full top-of-list picture, sampled
    "top3_sample": [],
    "score_table_sample": [],     # one full scored table, for the record
}


def _bump(d, k):
    d[k] = d.get(k, 0) + 1


def install(arm: bool):
    from src_extension.adaptation.global_adaptation_generator import (
        GlobalAdaptationSpaceGenerator as G,
    )
    from src_extension.planning import global_mission_planner as gmp

    # ---- arm: make the lookup satisfiable, exactly as a fix would ----
    orig_cso = G._generate_coverage_strategy_options

    def cso(self, gar, rm, ts):
        call_gar = gar
        if arm and isinstance(gar, dict):
            belief = getattr(rm.get("fire_runtime_model") if isinstance(rm, dict) else None,
                             "belief", None)
            if belief is not None:
                call_gar = {**gar,
                            "fire_probability_map": dict(belief.fire_probability_map),
                            "fire_confidence_map": dict(belief.fire_confidence_map)}
        return orig_cso(self, call_gar, rm, ts)

    G._generate_coverage_strategy_options = cso

    # ---- observe the scoring layer ----
    orig_select = gmp._select_feasible_option

    def select(scored, options):
        REC["plan_calls"] += 1
        REC["n_options"].append(len(options))
        nfeas = 0
        bg = mt = None
        for rank, entry in enumerate(scored):
            oid = str(getattr(entry.option, "option_id", "") or "")
            ev = entry.evaluation
            if ev.feasible:
                nfeas += 1
                _bump(REC["feasible_ids"], oid)
            if oid == BG_ID:
                bg = (rank, entry)
            elif oid == MAINTAIN_ID:
                mt = (rank, entry)
        REC["n_feasible"].append(nfeas)

        if bg is not None:
            rank, entry = bg
            REC["bg_present"] += 1
            REC["bg_rank"].append(rank)
            REC["bg_score"].append(round(float(entry.evaluation.total_utility), 9))
            if entry.evaluation.feasible:
                REC["bg_feasible"] += 1
            _bump(REC["bg_violations"], "|".join(entry.evaluation.constraint_violations) or "<none>")
            tr = (getattr(entry.option, "parameters", {}) or {}).get("target_regions")
            REC["bg_target_regions_len"].append(len(tr) if tr is not None else -1)
        if mt is not None:
            rank, entry = mt
            REC["mt_present"] += 1
            REC["mt_rank"].append(rank)
            REC["mt_score"].append(round(float(entry.evaluation.total_utility), 9))
            if entry.evaluation.feasible:
                REC["mt_feasible"] += 1

        if len(REC["top3_sample"]) < 5:
            REC["top3_sample"].append({
                "step": CUR["step"],
                "top3": [{"id": str(getattr(e.option, "option_id", "")),
                          "score": round(float(e.evaluation.total_utility), 6),
                          "feasible": bool(e.evaluation.feasible)}
                         for e in scored[:3]],
            })
        if not REC["score_table_sample"] and len(scored) > 5:
            REC["score_table_sample"] = [
                {"rank": i, "id": str(getattr(e.option, "option_id", "")),
                 "score": round(float(e.evaluation.total_utility), 6),
                 "feasible": bool(e.evaluation.feasible),
                 "violations": list(e.evaluation.constraint_violations)}
                for i, e in enumerate(scored)]

        out = orig_select(scored, options)

        # which branch produced it
        first_feasible = None
        for entry in scored:
            if entry.evaluation.feasible:
                first_feasible = entry.option
                break
        if first_feasible is not None and out is first_feasible:
            _bump(REC["branch_hist"], "feasible_loop")
        elif out is None:
            _bump(REC["branch_hist"], "none")
        else:
            _bump(REC["branch_hist"], "maintain_fallback")
        _bump(REC["selected_hist"], str(getattr(out, "option_id", "") or "<none>"))
        return out

    gmp._select_feasible_option = select


def params(wind, ft, vs):
    """Verbatim from outputs/_sc_control.py:35-39 (scenario D)."""
    return {"NUM_AGENTS": 4, "NUM_VICTIMS": 4, "NUM_FIREFIGHTERS": 2,
            "WIND_DIRECTION": wind, "BATCH_SIZE": 300,
            "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
            "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}


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


def compare(pattern, out):
    runs = []
    for p in sorted(_glob.glob(pattern)):
        with open(p, "r", encoding="utf-8") as fh:
            runs.append(json.load(fh))
    idx = {}
    for r in runs:
        idx.setdefault(r["mode"], {})["%s|%s" % (r["label"], r["seed"])] = r
    obs, arm = idx.get("observe", {}), idx.get("arm", {})
    pairs = []
    for k in sorted(set(obs) & set(arm)):
        o, a = obs[k], arm[k]
        pairs.append({
            "run": k,
            "bg_score_series_identical": o["bg_score"] == a["bg_score"],
            "bg_rank_series_identical": o["bg_rank"] == a["bg_rank"],
            "bg_feasible_obs": o["bg_feasible"], "bg_feasible_arm": a["bg_feasible"],
            "bg_tr_len_obs_max": max(o["bg_target_regions_len"]) if o["bg_target_regions_len"] else None,
            "bg_tr_len_arm_max": max(a["bg_target_regions_len"]) if a["bg_target_regions_len"] else None,
            "bg_tr_len_arm_nonzero": sum(1 for x in a["bg_target_regions_len"] if x > 0),
            "first_score_diff": next(
                ({"i": i, "obs": x, "arm": y}
                 for i, (x, y) in enumerate(zip(o["bg_score"], a["bg_score"])) if x != y),
                None),
            "eval_identical": o["eval"] == a["eval"],
            "pos_identical": o["agent_positions_sha256"] == a["agent_positions_sha256"],
        })
    tot = {}
    for r in runs:
        for k in ("plan_calls", "bg_present", "bg_feasible", "mt_present", "mt_feasible"):
            tot.setdefault(r["mode"], {})
            tot[r["mode"]][k] = tot[r["mode"]].get(k, 0) + (r.get(k) or 0)
    branch = {}
    for r in runs:
        for k, v in r["branch_hist"].items():
            branch.setdefault(r["mode"], {})
            branch[r["mode"]][k] = branch[r["mode"]].get(k, 0) + v
    doc = {"head": "93f23b7", "n_runs": len(runs),
           "totals_by_mode": tot, "branch_by_mode": branch,
           "observe_vs_arm": pairs, "runs": runs}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    print("WROTE %s (%d runs)" % (out, len(runs)))
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["observe", "arm"], default="observe")
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--wind", default="east")
    ap.add_argument("--roles", choices=["half", "default"], default="half")
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--out")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--glob", default=os.path.join(BASE, "_bg2_run_*.json"))
    a = ap.parse_args()

    if a.compare:
        compare(a.glob, a.out or os.path.join(BASE, "_bg_probe2.json"))
        sys.exit(0)

    ft, vs = (2, 2) if a.roles == "half" else (None, None)
    p = params(a.wind, ft, vs)
    label = "D/%s/%s" % (a.wind, a.roles)
    install(arm=(a.mode == "arm"))
    base = run(a.seed, p, a.steps)
    res = dict(REC)
    res.update({"label": label, "seed": a.seed, "steps": a.steps, "mode": a.mode,
                "eval": base["eval"], "stdout_sha256": base["stdout_sha256"],
                "agent_positions_sha256": base["agent_positions_sha256"]})
    print("%-7s %s|%-4d plan=%d branch=%s | nfeas_max=%s | BG present=%d feasible=%d "
          "rank_set=%s score_set=%s tr_len_max=%s | MT present=%d feasible=%d rank_set=%s"
          % (a.mode, label, a.seed, res["plan_calls"], json.dumps(res["branch_hist"]),
             max(res["n_feasible"]) if res["n_feasible"] else None,
             res["bg_present"], res["bg_feasible"],
             sorted(set(res["bg_rank"])), sorted(set(res["bg_score"]))[:4],
             max(res["bg_target_regions_len"]) if res["bg_target_regions_len"] else None,
             res["mt_present"], res["mt_feasible"], sorted(set(res["mt_rank"]))),
          flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, default=str)
