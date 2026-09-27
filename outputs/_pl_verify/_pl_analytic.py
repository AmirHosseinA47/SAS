"""Planner round Part 1, section 4.2: the analytic examples, scored by the REAL scorer in every
weight profile, against the baseline's real score in the same profile (confidence 1.0)."""
import sys, types
sys.path.insert(0, "/home/user/sas_dfbfbe7")
from src_extension.planning.utility_evaluation import UtilityEvaluation, _WEIGHT_PROFILES
from src_extension.adaptation.global_adaptation_generator import GlobalAdaptationSpaceGenerator
UE = UtilityEvaluation()
base_opt = GlobalAdaptationSpaceGenerator()._generate_global_noop_option(0.0)

def sh(D, n_to, n_from, to, frm, role):
    return (D / (n_to + 1) if to == role else 0.0) - (D / n_from if frm == role else 0.0)

def opt(vals, frm, to):
    p = {"current_role": None, "role_stability_timer": None, "role_switch_count": None,
         "battery_state": None, "resource_state": None, "assigned_role": to, "target_uav_id": "2500",
         "from_role": frm, "to_role": to, "battery_level": 80.0}
    p.update(vals)
    return types.SimpleNamespace(option_id="x", option_type="role_assignment", parameters=p,
                                 confidence=1.0, cost_estimate=1.0, scope=None)

CASES = {
 # a tracker to search, 2/2 split (so n_VS=2 before, the tracker role keeps 1 available)
 "EARLY FT->VS (half 2/2, step>=31): 4/4 victims undetected, 50% unseen, D_fire 0.1, D_stale 0":
   dict(frm="fire_tracker", to="victim_searcher", n_ft=2, n_vs=2, Df=0.1, Dv=1.0, Du=0.5, Ds=0.0,
        col=0.0, bat=0.05, dr=0.0, sw=0.15),
 "EARLY FT->VS (default 3/1, step>=31): same world":
   dict(frm="fire_tracker", to="victim_searcher", n_ft=3, n_vs=1, Df=0.1, Dv=1.0, Du=0.5, Ds=0.0,
        col=0.0, bat=0.05, dr=0.0, sw=0.15),
 "MID VS->FT (half 2/2): all victims detected, 10% unseen, D_fire 0.5, D_stale 0.3":
   dict(frm="victim_searcher", to="fire_tracker", n_ft=2, n_vs=2, Df=0.5, Dv=0.0, Du=0.1, Ds=0.3,
        col=0.0, bat=0.1, dr=0.0, sw=0.15),
 "MID VS->FT (half 2/2): one victim still undetected, otherwise as above":
   dict(frm="victim_searcher", to="fire_tracker", n_ft=2, n_vs=2, Df=0.5, Dv=0.25, Du=0.1, Ds=0.3,
        col=0.0, bat=0.1, dr=0.0, sw=0.15),
 "NO CASE (half 2/2): balanced demands, the reverse of nothing":
   dict(frm="victim_searcher", to="fire_tracker", n_ft=2, n_vs=2, Df=0.3, Dv=0.5, Du=0.3, Ds=0.1,
        col=0.0, bat=0.1, dr=0.0, sw=0.15),
}
for name, c in CASES.items():
    n = {"fire_tracker": c["n_ft"], "victim_searcher": c["n_vs"]}
    frm, to = c["frm"], c["to"]
    vals = {
        "fire_contribution": sh(c["Df"], n[to], n[frm], to, frm, "fire_tracker"),
        "victim_contribution": sh(c["Dv"], n[to], n[frm], to, frm, "victim_searcher"),
        "communication_contribution": 0.0,
        "uncertainty_reduction": sh(c["Du"], n[to], n[frm], to, frm, "victim_searcher"),
        "information_recovery": sh(c["Ds"], n[to], n[frm], to, frm, "fire_tracker"),
        "collision_risk": c["col"], "battery_cost": c["bat"], "drift_risk": c["dr"], "switching_cost": c["sw"]}
    print(name)
    print("   values: " + ", ".join("%s=%.3f" % (k.split("_")[0], v) for k, v in vals.items()))
    row = []
    for mode in ("normal_monitoring_mode", "information_recovery_mode", "safety_first_mode",
                 "battery_constrained_mode", "victim_support_mode"):
        s = UE._evaluate_global_mission_option(opt(vals, frm, to), None, None, mode).total_utility
        b = UE._evaluate_global_mission_option(base_opt, None, None, mode).total_utility
        row.append("%s %.3f vs %.4f %s" % (mode.split("_")[0], s, b, "WIN" if s > b else "no"))
    print("   " + " | ".join(row))
