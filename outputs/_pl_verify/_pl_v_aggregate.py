"""Planner round Part 1: aggregate the dfbfbe7 re-verification wave (outputs/_pl_verify/_pl_v_*.json).

Per mode: runs, scorings, presence of the nine keys, per-option total histogram (baseline vs the
rest), selections, MissionDecision non-empty fields, executor role writes; seed-matched outcome
identity of every mode against the observe runs (the control: hooks only, nothing armed), and of
observe against nopatch (observer purity) on the seeds that have both.
"""
import collections, glob, json, os, sys

D = os.path.dirname(os.path.abspath(__file__))
NINE = ["fire_contribution", "victim_contribution", "communication_contribution",
        "uncertainty_reduction", "information_recovery", "collision_risk", "battery_cost",
        "drift_risk", "switching_cost"]
BASE = "global_stability_maintain_current_config"
KEYS = ("eval", "stdout_sha256", "agent_positions_sha256", "firemap_sha256", "final_role_signature")

runs = collections.defaultdict(dict)
for p in sorted(glob.glob(os.path.join(D, "_pl_v_*.json"))):
    if p.endswith("_aggregate.json"):
        continue
    d = json.load(open(p))
    runs[d["mode"]][(d["label"], d["seed"])] = d

out = {}
for mode, rs in sorted(runs.items()):
    m = {"runs": len(rs)}
    if mode != "nopatch":
        pres = collections.Counter(); scor = 0; tot_base = collections.Counter(); tot_rest = collections.Counter()
        sel = collections.Counter(); md = collections.Counter(); ex = collections.Counter(); keyunion = set()
        role_opt_params = collections.Counter()
        for d in rs.values():
            scor += d["eval_calls"]
            for oid, c in d["by_option"].items():
                for k in NINE:
                    pres[k] += c["key_present"].get(k, 0)
                for v, n in c["total"].items():
                    (tot_base if oid == BASE else tot_rest)[v] += n
                if oid.startswith("global_role_assignment_") and "assigned_role" in c["key_values"]:
                    for v, n in c["key_values"]["assigned_role"].items():
                        role_opt_params[v] += n
            for k, v in d["selected_hist"].items():
                sel[k] += v
            for k, v in d["md_nonempty"].items():
                md[k] += v
            for k, v in d["exec_assign_n"].items():
                ex[str(k)] += v
        m.update(scorings=scor, nine_present=dict(pres), baseline_totals=dict(tot_base),
                 other_totals=dict(tot_rest), selected=dict(sel), md_nonempty=dict(md),
                 exec_assign_n=dict(ex), assigned_role_values=dict(role_opt_params),
                 eval_totals={k: sum(int(d["eval"].get(k) or 0) for d in rs.values())
                              for k in ("rescued", "dead", "firefighter_deaths", "never_detected",
                                        "unreachable", "burnt_cells")})
    out[mode] = m

ctrl = runs.get("observe", {})
cmp = {}
for mode, rs in runs.items():
    if mode == "observe":
        continue
    rows = []
    for key, d in sorted(rs.items()):
        c = ctrl.get(key)
        if c is None:
            continue
        rows.append({"run": "%s/%s" % key, **{k: d.get(k) == c.get(k) for k in KEYS},
                     "eval_mode": d["eval"], "eval_ctrl": c["eval"],
                     "roles_mode": d.get("final_role_signature"), "roles_ctrl": c.get("final_role_signature")})
    cmp[mode] = {"n": len(rows),
                 "all_identical": sum(1 for r in rows if all(r[k] for k in KEYS)),
                 "any_differs": sum(1 for r in rows if not all(r[k] for k in KEYS)),
                 "rows": rows}
out["compare_vs_observe"] = cmp
json.dump(out, open(os.path.join(D, "_pl_v_aggregate.json"), "w"), indent=1, default=str)
for mode, m in out.items():
    if mode == "compare_vs_observe":
        continue
    print(mode, {k: v for k, v in m.items() if k not in ("baseline_totals", "other_totals")})
    if "other_totals" in m:
        nz = sum(n for v, n in m["other_totals"].items() if float(v) != 0.0)
        print("   other options: %d scorings, %d non-zero" % (sum(m["other_totals"].values()), nz))
    if "baseline_totals" in m:
        print("   baseline totals", m["baseline_totals"])
for mode, c in cmp.items():
    print("vs observe:", mode, "n=%d identical=%d differ=%d" % (c["n"], c["all_identical"], c["any_differs"]))
