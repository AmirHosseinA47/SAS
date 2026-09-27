"""Planner round Part 1: OFFLINE, OPEN-LOOP evaluation of the proposed role-option values.

Reads the per-step ingredients recorded by _pl_shadow.py (observe runs at dfbfbe7, roles never
change), rebuilds for every step the per-UAV switch options the Part 1 design would generate,
and scores them with the REAL, unmodified UtilityEvaluation._evaluate_global_mission_option in
the utility mode that step actually used, against the baseline score that step actually got.

OPEN LOOP: the recorded runs never switch a role, so this answers only "in the states the
local strategy actually passes through, would a switch option out-score the baseline, how
often, and driven by which terms" - it predicts nothing about outcomes and is not a tuning
instrument (no outcome is read here). Formulas: outputs/planner_part1.txt section 3.
"""
from __future__ import annotations
import argparse, collections, glob, json, os, sys, types

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default="/home/user/sas_dfbfbe7")
ap.add_argument("--glob", default="/home/user/SAS/outputs/_pl_verify/_pl_v_observe_*.json")
ap.add_argument("--conf", choices=["one", "trigger"], default="one",
                help="role-option confidence: 1.0 (design) or the recorded trigger mean (as shipped)")
ap.add_argument("--battery", choices=["lo", "hi"], default="lo",
                help="battery_cost bound: lo = flight only (0.3/cell); hi = flight + the trigger "
                     "rising 0.3/cell away from the berth (0.6/cell). The exact design value "
                     "(margin consumed incl. the trigger at the target cell) lies between; the "
                     "recorder kept distances, not target cells.")
ap.add_argument("--variant", choices=["e1", "e2", "e3", "e3x"], default="e3x",
                help="e1 = the first draft of planner_part1.txt section 3; e2 = after the first "
                     "review round; e3 = the final design with battery_cost bracketed (v1 recorder); "
                     "e3x = the final design EXACTLY, from the v2 recorder (target cells), incl. I5 "
                     "(see the change log, section 0.1)")
ap.add_argument("--out", default="")
a = ap.parse_args()
sys.path.insert(0, os.path.abspath(a.repo))
from src_extension.planning.utility_evaluation import UtilityEvaluation  # noqa: E402

UE = UtilityEvaluation()
FT, VS = "fire_tracker", "victim_searcher"
VIEW = 17 * 17          # UAV_OBSERVATION_RADIUS 8 -> one UAV's observation area
E_MOVE = 0.3            # battery per moving step (0.1 per step + 0.2 per move), agents.py:284-285
B_CRIT = 15.0           # BATTERY_CRITICAL_THRESHOLD
SW_BASE, SW_RECENT, SW_WINDOW = 0.15, 0.85, 30.0
H_STEPS = 10            # e3 availability horizon: moving steps of battery above the RTB trigger
NINE = ["fire_contribution", "victim_contribution", "communication_contribution",
        "uncertainty_reduction", "information_recovery", "collision_risk", "battery_cost",
        "drift_risk", "switching_cost"]


BERTHS = {}


def berths_for(roles):
    """Every UAV's own berths (one per depot), read once from a freshly built model: the
    berth geometry depends on the base-station configuration and the UAV index only."""
    if roles in BERTHS:
        return BERTHS[roles]
    import contextlib, io, random as _r
    import agents as am, common_fixed_variables as cfv, wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    rng = _r.Random(101); cfv.SYSTEM_RANDOM = rng; wf.SYSTEM_RANDOM = rng; am.random = rng
    ft, vs = (2, 2) if roles == "half" else (None, None)
    apply_scenario_config(cfv, wf, NUM_AGENTS=4, NUM_VICTIMS=4, NUM_FIREFIGHTERS=2,
                          WIND_DIRECTION="east", BATCH_SIZE=300, FIRE_SPREAD_MULTIPLIER=0.75,
                          PROBABILITY_MAP=False, NUM_FIRE_TRACKERS=ft, NUM_VICTIM_SEARCHERS=vs)
    with contextlib.redirect_stdout(io.StringIO()):
        m = wf.WildFireModel()
    BERTHS[roles] = {str(a.unique_id): [tuple(int(v) for v in b) for b in (a.rtb_berths or ())]
                     for a in m.schedule.agents if type(a).__name__ == "UAV"}
    return BERTHS[roles]


def rtb_trigger_at(uid, cell, berths):
    """The same formula at an arbitrary cell (section 3.7): reserve 0.0, margin 39.23, 0.3/cell."""
    own = berths.get(uid) or []
    if not own or cell is None:
        return B_CRIT
    return max(0.0, E_MOVE * min(abs(cell[0] - b[0]) + abs(cell[1] - b[1]) for b in own) + 39.23)


def rtb_trigger(u, berths):
    """agents.UAV._rtb_trigger_level at the NEAREST own berth (the berth the trigger test uses),
    reserve 0.0, margin 39.23, 0.3 per moving step; no base station -> the critical level."""
    own = berths.get(u["id"]) or []
    if not own:
        return B_CRIT
    x, y = u["pos"]
    d = min(abs(x - b[0]) + abs(y - b[1]) for b in own)
    return max(0.0, E_MOVE * d + 39.23)


def demands(s):
    """e2/e3: the believed-burning set B is PARTITIONED into its stale part S and the rest, both
    on the same unit (one observation area); N_v = len(managed_victims). e1: D_fire = |B|/289,
    D_stale = |S|/|B|, N_v = NUM_VICTIMS."""
    ncells = max(1, int(s["ncells"]))
    B = int(s["B"])
    S = int(s["B_status"].get("stale_information", 0))
    detected = sum(1 for st, conf in s["mv"].values() if conf)
    if a.variant == "e1":
        nv = max(1, int(s["nv"]))
        return {"fire": min(1.0, B / VIEW), "vict": max(0.0, (nv - detected) / nv),
                "unc": s["vis"].get("never_seen", 0) / ncells,
                "stale": (S / B) if B > 0 else 0.0}
    nv = len(s["mv"])
    return {
        "fire": min(1.0, max(0, B - S) / VIEW),
        "vict": 0.0 if nv == 0 else min(1.0, max(0.0, (nv - detected) / nv)),
        "unc": s["vis"].get("never_seen", 0) / ncells,
        "stale": min(1.0, S / VIEW),
    }


def values(s, u, b, D, n, tau, berths=None):
    a_ = u["role"]
    def share(dem, role):
        gain = dem / (n[role] + 1) if b == role else 0.0
        loss = dem / n[role] if a_ == role and n[role] > 0 else 0.0
        return gain - loss
    busy = {x["id"] for x in s["uav"] if x["rtb"] or x["dock"]}
    if a.variant == "e1":
        near_b = sum(1 for w in u["near"] if w[1] == b)
    else:
        near_b = sum(1 for w in u["near"] if w[1] == b and w[0] not in busy)
    d = u["dB"][0] if b == FT else u["dN"][0]
    usable = u["batt"] - tau
    if a.variant == "e3x":
        cell, dd = (u["cF"] if b == FT else u["cN"])
        if cell is None:
            consumed = 0.0
        else:
            consumed = E_MOVE * dd + max(0.0, rtb_trigger_at(u["id"], cell, berths) - tau)
        batt_cost = 1.0 if usable <= 0 else min(1.0, consumed / usable)
    else:
        per_cell = E_MOVE if (a.battery == "lo" or a.variant == "e1") else 2 * E_MOVE
        batt_cost = 1.0 if usable <= 0 else (0.0 if d is None else min(1.0, d * per_cell / usable))
    timer = u["timer"] if u["timer"] is not None else 0.0
    return {
        "fire_contribution": share(D["fire"], FT),
        "victim_contribution": share(D["vict"], VS),
        "communication_contribution": 0.0,
        "uncertainty_reduction": share(D["unc"], VS),
        "information_recovery": share(D["stale"], FT),
        "collision_risk": near_b / max(1, len(s["uav"]) - 1),
        "battery_cost": batt_cost,
        "drift_risk": min(1.0, float(u["drift"] or 0.0)),
        "switching_cost": SW_BASE + SW_RECENT * max(0.0, 1.0 - timer / SW_WINDOW),
    }


def score(vals, u, b, mode, conf, zero=None):
    params = {"current_role": None, "role_stability_timer": None, "role_switch_count": None,
              "battery_state": None, "resource_state": None,
              "assigned_role": b, "target_uav_id": u["id"], "from_role": u["role"], "to_role": b,
              "battery_level": u["batt"]}
    params.update(vals)
    if zero:
        params[zero] = 0.0 if zero != "switching_cost" else 1e-12
    opt = types.SimpleNamespace(option_id="global_role_assignment_%s_%s" % (b, u["id"]),
                                option_type="role_assignment", parameters=params,
                                confidence=conf, cost_estimate=1.0, scope=None)
    ev = UE._evaluate_global_mission_option(opt, None, None, mode)
    return ev.total_utility, ev


rows = []
agg = collections.Counter()
per_run = {}
term_moves = collections.Counter()
first_step = {}
by_mode = collections.Counter()
val_nonzero = collections.Counter()
val_n = 0
margins = []
for path in sorted(glob.glob(a.glob)):
    d = json.load(open(path))
    key = "%s/%s" % (d["label"], d["seed"])
    pr = per_run.setdefault(key, {"steps": 0, "wins": 0, "win_ids": collections.Counter(),
                                  "first_win": None})
    for s in d.get("shadow", []):
        if "err" in s or s.get("base") is None:
            agg["skipped"] += 1
            continue
        pr["steps"] += 1
        by_mode[s["mode"]] += 1
        D = demands(s)
        berths = berths_for("half" if d["label"].endswith("/half") else "default")
        if a.variant == "e1":
            avail = [u for u in s["uav"] if not u["rtb"] and not u["dock"]]
        elif a.variant == "e2":
            avail = [u for u in s["uav"] if not u["rtb"] and not u["dock"]
                     and u["batt"] > rtb_trigger(u, berths)]
        else:   # e3/e3x: at least H = 10 moving steps (3.0 battery) above the RTB trigger
            flagged = {e for t in s.get("instab", []) for e in t[1]} if a.variant == "e3x" else set()
            agg["i5_excluded"] += len(flagged)
            avail = [u for u in s["uav"] if not u["rtb"] and not u["dock"]
                     and u["batt"] - rtb_trigger(u, berths) > H_STEPS * E_MOVE
                     and u["id"] not in flagged]
        agg["unavailable_uav_steps"] += len(s["uav"]) - len(avail)
        n_avail = collections.Counter(u["role"] for u in avail)
        # e1/e2 split demands among AVAILABLE members; e3 among ALL holders of the role
        n = n_avail if a.variant in ("e1", "e2") else collections.Counter(u["role"] for u in s["uav"])
        conf = 1.0 if a.conf == "one" else float(s.get("role_conf") or 0.0)
        best = None
        for u in avail:
            b = VS if u["role"] == FT else FT
            if n_avail[u["role"]] <= 1:   # I2: another AVAILABLE member of the role must remain
                agg["last_member_excluded"] += 1
                continue
            vals = values(s, u, b, D, n, rtb_trigger(u, berths), berths)
            val_n += 1
            for k, v in vals.items():
                if abs(v) > 1e-12:
                    val_nonzero[k] += 1
            sc, ev = score(vals, u, b, s["mode"], conf)
            if best is None or sc > best[0]:
                best = (sc, u, b, vals)
        if best is None:
            continue
        margins.append(best[0] - s["base"])
        if best[0] > s["base"]:
            pr["wins"] += 1
            pr["win_ids"]["%s->%s" % (best[1]["id"], best[2])] += 1
            if pr["first_win"] is None:
                pr["first_win"] = s["step"]
            # which of the nine, zeroed, would flip this step's decision back to the baseline
            for k in NINE:
                sc0, _ = score(best[3], best[1], best[2], s["mode"], conf, zero=k)
                if sc0 <= s["base"]:
                    term_moves[k] += 1
        else:
            # which of the nine, zeroed, would have made the best switch win
            for k in NINE:
                sc0, _ = score(best[3], best[1], best[2], s["mode"], conf, zero=k)
                if sc0 > s["base"]:
                    term_moves[k] += 1

tot_steps = sum(p["steps"] for p in per_run.values())
tot_wins = sum(p["wins"] for p in per_run.values())
out = {
    "conf": a.conf, "runs": len(per_run), "steps": tot_steps, "switch_would_win_steps": tot_wins,
    "share": (tot_wins / tot_steps) if tot_steps else None, "modes": dict(by_mode),
    "per_run": {k: {"steps": v["steps"], "wins": v["wins"], "first_win": v["first_win"],
                    "win_ids": dict(v["win_ids"])} for k, v in per_run.items()},
    "term_decisive_counts": dict(term_moves), "value_nonzero_share":
        {k: round(val_nonzero[k] / val_n, 4) if val_n else None for k in NINE},
    "scored_switch_options": val_n, "counters": dict(agg),
    "margin_quantiles": (lambda m: {q: round(m[int(q * (len(m) - 1))], 4) for q in (0.0, 0.1, 0.5, 0.9, 1.0)})(sorted(margins)) if margins else {},
}
txt = json.dumps(out, indent=1)
print(txt)
if a.out:
    open(a.out, "w").write(txt)
