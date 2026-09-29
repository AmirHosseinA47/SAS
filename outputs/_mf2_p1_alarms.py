"""fix2 Part 1: item 1 evidence from the mf2H hooked runs (outputs/_mf2_p1_hooks.py). Read-only.

1. PASS-THROUGH: every mf2H run must equal its mf1P twin (same argv but --out/--tag) on every
   recorded field - rows_uav / rows_ff / rows_vic / rows_dec / rows_trig, eval, terminal step,
   stdout sha, stdout tags. A difference means a hook perturbed the run: STOP.
2. Per alarm: how often it fires, and how often its REAL condition holds (definitions printed).
3. The fourth trigger (local SEARCH_MODE_REQUIRED): who raises it, and whether the fleet had
   lost sight of the fire at that step.
4. The global analyzer with its fire source fixed (the shadow): which trigger types fire.
5. A STATIC preview of the fail-safe mode if every alarm fired only on its real condition
   (no feedback - the runs themselves are the shipped system; Part 3 measures the real thing).
usage: _mf2_p1_alarms.py
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

OUT = r"E:\Projects\SAS\outputs"
ALL36 = ("COLLISION_RISK CRITICAL_BATTERY CRITICAL_LINK_UNRELIABLE DRIFT_TOO_HIGH FIRE_DIRECTION_SHIFT "
         "FIRE_SPREAD_ACCELERATING HIGH_LOCAL_UNCERTAINTY HIGH_PRIORITY_FIRE_REGION HIGH_UNCERTAINTY_REGION "
         "INFORMATION_INSUFFICIENT INSTABILITY_DETECTED KNOWLEDGE_DESYNC_RISK LOCAL_HAZARD_PRESSURE "
         "LOCAL_PATH_UNRELIABLE LOW_BATTERY LOW_INFORMATION_GAIN LOW_NAVIGATION_CONFIDENCE LOW_PATH_STABILITY "
         "LOW_TASK_SUPPORT OSCILLATION_RISK PATH_OSCILLATION POOR_FIRE_COVERAGE RESCUE_FEASIBLE RESCUE_UNCERTAIN "
         "RESCUE_UNSAFE RESOURCE_DEGRADING SEARCH_MODE_REQUIRED STALE_HIGH_PRIORITY_REGION STALE_INFORMATION "
         "STALE_LOCAL_INFORMATION TREND_IMPROVING TREND_WORSENING UAV_STUCK UNCERTAINTY_INCREASING "
         "UNSAFE_SYSTEM_STATE VICTIM_CONFIDENCE_LOW").split()
FIELDS = ("rows_uav", "rows_ff", "rows_vic", "rows_dec", "rows_trig", "eval", "terminal_step",
          "stdout_sha", "stdout_tags", "steps_done", "complete", "inline_violation_counts")
LOCAL_GLOBAL = {"COLLISION_RISK", "DRIFT_TOO_HIGH", "SEARCH_MODE_REQUIRED"}


def pct(a, b):
    return "%5.1f%%" % (100.0 * a / b) if b else "  n/a"


def main():
    P = print
    runs = []
    bad = 0
    for f in sorted(glob.glob(os.path.join(OUT, "_sd_mf2H_*.json"))):
        if ".json." in os.path.basename(f):
            continue
        d = json.load(open(f, encoding="utf-8"))
        twin = f.replace("_sd_mf2H_", "_sd_mf1P_")
        t = json.load(open(twin, encoding="utf-8"))
        diffs = [k for k in FIELDS if d.get(k) != t.get(k)]
        a1 = list(d["argv"])
        a2 = list(t["argv"])
        for a in (a1, a2):
            for key in ("--out", "--tag"):
                a[a.index(key) + 1] = "*"
        if a1 != a2:
            diffs.append("argv")
        if diffs:
            bad += 1
        P("PASS-THROUGH %-22s vs mf1P twin: %s" % (os.path.basename(f), "IDENTICAL" if not diffs else "DIFF %s" % diffs))
        d["_name"] = os.path.basename(f)[4:-5]
        runs.append(d)
    if bad:
        P("STOP: %d hooked runs differ from their twins - the hooks are not pass-through" % bad)
        return 1
    P("")
    # ---------------- per-alarm -----------------------------------------------------
    nsteps = sum(len(d["rows_dec"]) for d in runs)
    uav_steps = coll_raw = coll_real = coll_real_any = 0
    dmin_hist = collections.Counter()
    drift_steps = 0
    drift_cls = collections.Counter()
    drift_cause = collections.Counter()
    last_move_all = collections.Counter()
    persist45 = persist33 = 0
    fleet_coll_real = fleet_drift_real = 0
    link_steps = 0
    link_why = collections.Counter()
    cexec = collections.Counter()
    fail_kinds = collections.Counter()
    search_uav_steps = 0
    search_by_role = collections.Counter()
    search_fleet = collections.Counter()
    shadow = collections.Counter()
    real_g = collections.Counter()
    fleet_lost = 0
    preview = collections.Counter()
    for d in runs:
        m = d["mf2"]
        for k, v in m["cexec"].items():
            cexec[k] += v
        glob_by_step = {r[0]: r for r in m["glob"] if r[1] != "HOOK_ERR"}
        loc_by_step = collections.defaultdict(list)
        for r in m["loc"]:
            if len(r) < 20:
                continue
            loc_by_step[r[0]].append(r)
        hist = collections.defaultdict(list)  # uid -> off-target flags in order
        for step in sorted(loc_by_step):
            rows = loc_by_step[step]
            g = glob_by_step.get(step)
            any_sees = bool(g[2]) if g else False
            burning = g[1] if g else 0
            believed = (g[3] or 0) > 0 if g else False
            step_coll_real = False
            step_drift_real = False
            step_search_local = False
            for r in rows:
                (_, uid, role, rtb, dock, x, y, trig, nf, ns, nu, nn, derr, dlev, rstat, cong,
                 dmin_air, n2, dmin_any, lm) = r[:20]
                uav_steps += 1
                last_move_all[lm] += 1
                airborne = not dock
                real = airborne and dmin_air is not None and dmin_air <= 2 and step >= 20
                if "COLLISION_RISK" in trig and step >= 20:
                    coll_raw += 1
                if real:
                    coll_real += 1
                    step_coll_real = True
                if airborne and dmin_air is not None and step >= 20:
                    dmin_hist[min(dmin_air, 10)] += 1
                off = lm in ("refused_occupied", "refused_oob")
                hist[uid].append(off)
                w = hist[uid][-5:]
                p45 = len(w) == 5 and sum(w) >= 4
                w3 = hist[uid][-3:]
                p33 = len(w3) == 3 and all(w3)
                persist45 += int(p45)
                persist33 += int(p33)
                if p45:
                    step_drift_real = True
                if "DRIFT_TOO_HIGH" in trig:
                    drift_steps += 1
                    drift_cls[str(rstat)] += 1
                    if dlev is not None and float(dlev) >= 0.3:
                        drift_cause["current reading >= 0.3 after last move %s" % lm] += 1
                    else:
                        drift_cause["LATCH ONLY (current reading %s, status %s)" % (dlev, rstat)] += 1
                if "SEARCH_MODE_REQUIRED" in trig:
                    search_uav_steps += 1
                    step_search_local = True
                    kind = ("docked" if dock else "returning" if rtb else role)
                    search_by_role[kind] += 1
            if step_coll_real:
                fleet_coll_real += 1
            if step_drift_real:
                fleet_drift_real += 1
            lost = believed and not any_sees
            if lost:
                fleet_lost += 1
            if step_search_local:
                if any_sees:
                    search_fleet["another UAV sees fire this step (fleet has the fire in view)"] += 1
                elif burning == 0:
                    search_fleet["no fire burning at all"] += 1
                elif believed:
                    search_fleet["no UAV sees fire, fire believed (belief p>=0.7) - FLEET LOST THE FIRE"] += 1
                else:
                    search_fleet["no UAV sees fire, fire burning but not yet believed (undiscovered)"] += 1
            if g:
                if g[7]:
                    link_steps += 1
                    why = []
                    if g[4] is not None and g[4] < 0.25:
                        why.append("crit_link=%s qlen=%s" % (g[4], g[8]))
                    if g[5] is not None and g[5] < 0.25:
                        why.append("delivery<0.25")
                    if g[6] >= 3:
                        why.append("failed>=3")
                    link_why[" & ".join(why) or "?"] += 1
                for k, v in (g[9] or {}).items():
                    fail_kinds[k] += v
                for tname in g[10]:
                    real_g[tname] += 1
                for tname in g[11]:
                    shadow[tname] += 1
            # static preview: real collision / persistent drift -> safety_first; fleet lost -> info recovery
            if lost:
                preview["information_recovery"] += 1
            elif step_coll_real or step_drift_real:
                preview["safety_first"] += 1
            else:
                preview["normal"] += 1
    P("RUNS %d, steps %d, UAV analysis rows %d" % (len(runs), nsteps, uav_steps))
    P("last UAV.move outcome per analysis row: %s" % dict(last_move_all))
    P("")
    P("ALARM 1 COLLISION_RISK (local). raw = fires (step >= 20); real = this UAV airborne AND another")
    P("  airborne UAV within Manhattan 2 (step >= 20)")
    P("  raw %s of UAV-steps; real %s; steps with >= 1 real pair %s of steps" % (
        pct(coll_raw, uav_steps), pct(coll_real, uav_steps), pct(fleet_coll_real, nsteps)))
    P("  nearest airborne other UAV (Manhattan, 10 = >= 10): %s" % sorted(dmin_hist.items()))
    P("ALARM 2 DRIFT_TOO_HIGH (local). fires on %s of UAV-steps; by resource-model status %s" % (
        pct(drift_steps, uav_steps), dict(drift_cls)))
    for k, v in drift_cause.most_common():
        P("    %6d  %s" % (v, k))
    P("  REAL persistent deviation (refused move on >= 4 of the last 5 steps; docked/no-direction holds are")
    P("  intended stays): %s of UAV-steps, %s of steps; 3-in-a-row: %s of UAV-steps" % (
        pct(persist45, uav_steps), pct(fleet_drift_real, nsteps), pct(persist33, uav_steps)))
    P("ALARM 3 CRITICAL_LINK_UNRELIABLE (global): %s of steps; why %s" % (pct(link_steps, nsteps), dict(link_why)))
    P("  failed-message ids by kind (summed over steps): %s" % dict(fail_kinds))
    P("  communication actions the executor scored as failure/delayed: %s" % dict(cexec))
    P("ALARM 4 SEARCH_MODE_REQUIRED (local): raised on %s of UAV-steps; by raiser %s" % (
        pct(search_uav_steps, uav_steps), dict(search_by_role)))
    tot = sum(search_fleet.values())
    for k, v in search_fleet.most_common():
        P("    %s of the %d steps it is raised: %s" % (pct(v, tot), tot, k))
    P("  fleet-level 'lost the fire' (believed, no UAV sees fire): %s of steps" % pct(fleet_lost, nsteps))
    P("")
    P("GLOBAL ANALYZER WITH THE FIRE SOURCE FIXED (shadow) - share of steps each type fires; real run in ()")
    fired_real = set()
    for d in runs:
        for t in d["rows_trig"]:
            fired_real.update(t)
    never = [t for t in ALL36 if t not in fired_real]
    P("  never fired in the real runs (%d of 36): %s" % (len(never), never))
    for tname in sorted(set(shadow) | set(real_g)):
        P("    %-28s shadow %s   (real global %s)" % (tname, pct(shadow[tname], nsteps), pct(real_g[tname], nsteps)))
    P("  of the never-fired types, now firing in the shadow: %s" % [t for t in never if shadow.get(t)])
    P("")
    P("STATIC PREVIEW of the mode if the alarms fired only on their real conditions (no feedback):")
    for k, v in preview.most_common():
        P("    %-22s %s" % (k, pct(v, nsteps)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
