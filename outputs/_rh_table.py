"""Format outputs/_rh_probe.json into the per-run table for the report."""
from __future__ import annotations
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
doc = json.load(open(os.path.join(BASE, "_rh_probe.json"), encoding="utf-8"))
runs = doc["runs"]


def h(d):
    return " ".join("%s=%d" % (k, v) for k, v in sorted(d.items()))


print("HEAD %s   n_runs=%d" % (doc["head"], doc["n_runs"]))
print()
print("PER-RUN TABLE  (240 steps each; update() runs 2x/step via "
      "adaptation_manager.py:117 and :124)")
print()
hdr = ("%-18s %-5s %5s %6s %6s %5s %5s %5s %5s %5s %5s %5s"
       % ("combo", "seed", "upd", "srn", "usrc", "nrm", "info", "safe", "degr",
          "emrg", "cMax", "cNZ"))
print(hdr)
print("-" * len(hdr))
for r in runs:
    mh = r["mode_hist"]
    print("%-18s %-5d %5d %6d %6d %5d %5d %5d %5d %5d %5s %5d"
          % (r["label"], r["seed"], r["update_calls"], r["srn_calls"],
             r["usrc_calls"],
             mh.get("normal", 0), mh.get("information_recovery", 0),
             mh.get("safety_first", 0), mh.get("degraded", 0),
             mh.get("emergency", 0),
             r["counter_max"], r["counter_nonzero_obs"]))
print()
print("  upd  = ModeManager.update() calls        srn  = should_return_to_normal() calls")
print("  usrc = _update_stable_recovery_counter() calls")
print("  nrm/info/safe/degr/emrg = FailSafeMode distribution over update() calls")
print("  cMax = max stable_recovery_counter ever   cNZ = # observations where counter != 0")
print()

print("PER-RUN: _update_stable_recovery_counter BRANCH TAKEN, and mode at entry")
print()
hdr2 = ("%-18s %-5s %8s %10s %10s %8s %8s"
        % ("combo", "seed", "nrm_rst", "unsat_rst", "sat_incr", "mode=nrm", "mode!=nrm"))
print(hdr2)
print("-" * len(hdr2))
for r in runs:
    b = r["usrc_branch"]
    me = r["usrc_mode_at_entry"]
    nn = sum(v for k, v in me.items() if k != "normal")
    print("%-18s %-5d %8d %10d %10d %8d %8d"
          % (r["label"], r["seed"], b.get("normal_reset", 0),
             b.get("unsatisfied_reset", 0), b.get("satisfied_increment", 0),
             me.get("normal", 0), nn))
print()

print("PER-RUN: _recovery_conditions_satisfied and the information-recovery helpers")
print()
hdr3 = ("%-18s %-5s %7s %7s %7s %7s %7s %7s"
        % ("combo", "seed", "rcs", "rcs_T", "irr", "iss", "mfc", "itp"))
print(hdr3)
print("-" * len(hdr3))
for r in runs:
    print("%-18s %-5d %7d %7d %7d %7d %7d %7d"
          % (r["label"], r["seed"], r["rcs_calls"], r["rcs_true"],
             r["irr_calls"], r["iss_calls"], r["mfc_calls"], r["itp_calls"]))
print()

print("PER-RUN: distinct counter values, distinct reason-sets, mode transitions")
print()
for r in runs:
    print("%-18s seed=%-5d counter_distinct=%s  transitions=%d"
          % (r["label"], r["seed"], r["counter_distinct"],
             r["n_mode_transitions"]))
    for k, v in sorted(r["reason_hist"].items(), key=lambda kv: -kv[1]):
        print("      %5d x  %s" % (v, k))
print()

print("AGGREGATE OVER ALL RUNS")
print("  totals              :", json.dumps(doc["totals"]))
print("  mode_hist_all       :", h(doc["mode_hist_all"]))
print("  usrc_branch_all     :", h(doc["usrc_branch_all"]))
print("  usrc_mode_at_entry  :", h(doc["usrc_mode_at_entry_all"]))
print("  rcs_by_all (caller|mode|result):", h(doc["rcs_by_all"]))
print("  irr_by_all (has_info_reason|result):", h(doc["irr_by_all"]))
print("  iss_values_all      :", h(doc["iss_values_all"]))
print("  mfc_values_all      :", h(doc["mfc_values_all"]))
print("  itp_values_all      :", h(doc["itp_values_all"]))
print("  counter_max_over_all:", doc["counter_max_over_all"])
print("  counter_distinct_union:", doc["counter_distinct_union"])
print()

# EXTERNAL CROSS-CHECK vs outputs/_sc_control_post.json (committed at HEAD 3b1ffbf,
# unpatched, same 240 steps, same params). Any difference means the probe's
# wrappers perturbed the simulation.
ext = os.path.join(BASE, "_sc_control_post.json")
if os.path.exists(ext):
    e = json.load(open(ext, encoding="utf-8"))["runs"]
    print("EXTERNAL CROSS-CHECK vs outputs/_sc_control_post.json (unpatched, at HEAD)")
    print()
    for key, v in e.items():
        label, seed = key.split("|")
        label = label.replace("/default", "/default").replace("/half", "/half")
        match = [r for r in runs if r["label"] == label and r["seed"] == int(seed)]
        if not match:
            print("  %-22s no patched counterpart in this campaign" % key)
            continue
        m = match[0]
        print("  %-22s pos_sha match=%-5s  stdout_sha match=%-5s  eval match=%s"
              % (key,
                 m["agent_positions_sha256"] == v["agent_positions_sha256"],
                 m["stdout_sha256"] == v["stdout_sha256"],
                 m["eval"] == {x: v["eval"].get(x) for x in m["eval"]}))
    print()

ctl = os.path.join(BASE, "_rh_control_nopatch.json")
if os.path.exists(ctl):
    c = json.load(open(ctl, encoding="utf-8"))
    match = [r for r in runs if r["label"] == c["label"] and r["seed"] == c["seed"]]
    print("OBSERVER-PURITY CONTROL  (%s seed=%d, %d steps)"
          % (c["label"], c["seed"], c["steps"]))
    print("  nopatch  pos_sha=%s stdout_sha=%s eval=%s"
          % (c["agent_positions_sha256"], c["stdout_sha256"], json.dumps(c["eval"])))
    if match:
        m = match[0]
        print("  patched  pos_sha=%s stdout_sha=%s eval=%s"
              % (m["agent_positions_sha256"], m["stdout_sha256"], json.dumps(m["eval"])))
        print("  IDENTICAL: positions=%s stdout=%s eval=%s"
              % (m["agent_positions_sha256"] == c["agent_positions_sha256"],
                 m["stdout_sha256"] == c["stdout_sha256"],
                 m["eval"] == c["eval"]))
