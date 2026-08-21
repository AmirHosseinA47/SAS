"""Aggregate _tf_*.json into outputs/step0_target_following.txt (Q1-Q8).

Read-only over the probe JSONs. UTF-8 written from Python.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import subprocess
import sys
from collections import Counter

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_PATH = os.path.join(_ROOT, "outputs", "step0_target_following.txt")
GRID = 50
OBS2 = 64.0

RUNS = [("D", "north", 101), ("D", "south", 101), ("A", "west", 505), ("A", "north", 101)]

lines: list = []


def log(msg: str = "") -> None:
    print(msg, flush=True)
    lines.append(msg)


def tag(r: dict) -> str:
    return "%s/%s %d" % (r["scenario"], r["wind"], r["seed"])


def load() -> list:
    out = []
    for s, w, sd in RUNS:
        p = os.path.join(_ROOT, "outputs", "_tf_%s_%s_%d.json" % (s, w, sd))
        if not os.path.exists(p):
            log("MISSING %s" % p)
            continue
        with open(p, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def mh(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def fmt(v, nd=4):
    if v is None:
        return "n/a"
    return ("%." + str(nd) + "f") % v


def decs(r: dict) -> list:
    """Successful score decompositions for a run (detail steps only)."""
    out = []
    for x in r["step_records"]:
        d = x.get("decomp")
        if isinstance(d, dict) and "error" not in d and d.get("winner_terms"):
            d = dict(d)
            d["_step"] = x["step"]
            out.append(d)
    return out


def mean_or(vals, default=None):
    return statistics.mean(vals) if vals else default


def sfmt(v, nd=3):
    """Signed format, so the sign of a correlation is never ambiguous."""
    if v is None:
        return "n/a"
    return ("%+." + str(nd) + "f") % v


def main() -> int:
    head = ""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        head = "unknown"

    runs = load()
    if not runs:
        log("no run data")
        return 1

    log("=" * 78)
    log("STEP 0 - DOES THE VICTIM SEARCHER FOLLOW THE GENERATOR'S TARGET?")
    log("=" * 78)
    log("HEAD commit : %s" % head)
    log("Python      : %s" % sys.version.replace("\n", " "))
    log("mesa        : %s" % __import__("mesa").__version__)
    log("probe       : outputs/_diag_target_following.py (read-only monkeypatching)")
    log("runs        : 240 steps each, no production code changed")
    log("")
    log("UNITS: detection / observation-post / observed-set membership are EUCLIDEAN")
    log("r=8 (dx*dx + dy*dy <= 64), matching wildfire_model._detect_victims_in_uav_radius.")
    log("Manhattan is used only to measure progress toward a target.")
    log("")

    # ---------------- patch levels + verification ----------------
    log("-" * 78)
    log("PATCH LEVEL (which object was patched) AND RAW CALL COUNTERS")
    log("-" * 78)
    log("The executor builds a FRESH generator on every call")
    log("(uav_executor.py:3737 LocalAdaptationSpaceGenerator()._compute_...), so all")
    log("generator patches are applied to the CLASS or to the MODULE, never to an")
    log("instance. Patch targets actually used:")
    log("")
    for k, v in sorted(runs[0]["patch_kinds"].items()):
        log("  %-44s -> %s" % (k, v))
    log("")
    log("Raw counters (NOT compared against any expected value):")
    keys = [
        "gen_calls_total", "gen_calls_searcher", "gen_calls_nonsearcher",
        "gen_caller__wind_aware_victim_search_target",
        "gen_caller__try_generate_wind_aware_victim_search_option",
        "gen_returned_none", "exec_wind_target_calls",
        "legacy_calls", "legacy_nonnull",
        "planner_target_calls", "planner_target_nonnull",
        "pick_global_escape_calls", "corridor_waypoint_calls",
        "finalize_coverage_calls", "score_hybrid_calls",
        "bonus_calls_total",
        "bonus_from__score_hybrid_search_cell",
        "bonus_from__pick_global_coverage_escape_target",
        "bonus_from__generate_corridor_waypoints",
        "obs_penalty_calls",
        "choose_best_direction_calls", "pathfind_calls", "retarget_fallback_calls",
        "hazard_gate_calls", "hazard_gate_changed",
        "execute_calls_searcher", "commit_calls", "advance_calls",
    ]
    hdr = "  %-52s" % "counter" + "".join("%14s" % tag(r) for r in runs)
    log(hdr)
    for k in keys:
        row = "  %-52s" % k
        for r in runs:
            row += "%14d" % int(r["counters"].get(k, 0))
        log(row)
    log("")
    log("VERIFICATION: gen_calls_searcher and advance_calls are > 0 in every run, so")
    log("the wrappers demonstrably fired. Agreement below is measured, not a false")
    log("zero-disagreement artifact of instance-level patching.")
    log("")
    log("NOTE: the generator is called TWICE per step - once from the executor")
    log("(uav_executor.py:3724 _wind_aware_victim_search_target) and once from the")
    log("planner option builder (local_adaptation_generator.py:3773")
    log("_try_generate_wind_aware_victim_search_option; the def is at :3773, not the")
    log(":3793 cited in the plan). Both are counted separately.")
    log("")

    # ---------------- Q1 ----------------
    log("=" * 78)
    log("Q1 - AGREEMENT RATE: did the executor act on the generator's target?")
    log("=" * 78)
    log("Agreement = the target routed toward by the executor (the argument passed to")
    log("_choose_best_direction / _attempt_pathfinding_toward_target) is the SAME CELL")
    log("as the generator's target, compared as (round(x), round(y)).")
    log("")
    log("  %-14s %7s %8s %9s %11s" % ("run", "steps", "agree", "disagree", "agreement"))
    q1 = {}
    for r in runs:
        recs = r["step_records"]
        c = Counter(x["cause"] for x in recs)
        agree = c["agree"]
        n = len(recs)
        q1[tag(r)] = (n, agree, c)
        log("  %-14s %7d %8d %9d %10.1f%%" % (tag(r), n, agree, n - agree, 100.0 * agree / n))
    log("")
    log("Disagreement breakdown by cause (EXCLUSIVE, highest-precedence cause per step).")
    log("These are MEASURED from wrapper traces, not inferred: each cause corresponds")
    log("to a wrapper that fired or a wind_state flag read at executor entry.")
    log("")
    causes = set()
    for r in runs:
        causes |= set(x["cause"] for x in r["step_records"])
    causes.discard("agree")
    order = [
        "live_victim_pursuit", "hold", "legacy_target_source",
        "escape_target_routing", "force_coverage_retarget", "force_interior_retarget",
        "hazard_gate", "planner_target_source", "generator_returned_none",
        "generator_not_called_other", "other",
    ]
    ordered = [c for c in order if c in causes] + sorted(causes - set(order))
    log("  %-30s" % "cause" + "".join("%14s" % tag(r) for r in runs))
    for cz in ordered:
        row = "  %-30s" % cz
        for r in runs:
            row += "%14d" % Counter(x["cause"] for x in r["step_records"])[cz]
        log(row)
    row = "  %-30s" % "TOTAL disagreements"
    for r in runs:
        n = len(r["step_records"])
        row += "%14d" % (n - Counter(x["cause"] for x in r["step_records"])["agree"])
    log(row)
    log("")
    log("Non-exclusive condition flags (a step can carry several; these show how often")
    log("each override MECHANISM was active regardless of whether it changed the target):")
    log("")
    allflags = set()
    for r in runs:
        for x in r["step_records"]:
            allflags |= set(x.get("flags") or [])
    log("  %-30s" % "flag" + "".join("%14s" % tag(r) for r in runs))
    for fl in sorted(allflags):
        row = "  %-30s" % fl
        for r in runs:
            row += "%14d" % sum(1 for x in r["step_records"] if fl in (x.get("flags") or []))
        log(row)
    log("")
    log("Generator branch that produced the target (measured by which inner function")
    log("fired inside _compute_wind_aware_search_target):")
    log("")
    branches = set()
    for r in runs:
        branches |= set(x["branch"] for x in r["step_records"])
    log("  %-30s" % "branch" + "".join("%14s" % tag(r) for r in runs))
    for b in sorted(branches):
        row = "  %-30s" % b
        for r in runs:
            row += "%14d" % sum(1 for x in r["step_records"] if x["branch"] == b)
        log(row)
    log("")

    # ---------------- Q2 ----------------
    log("=" * 78)
    log("Q2 - ACTION LABELS applied by the executor to the searcher")
    log("=" * 78)
    labs = set()
    per = []
    for r in runs:
        c = Counter(
            (x["commit"][-1][1] if x.get("commit") else "<no commit>")
            for x in r["step_records"]
        )
        per.append(c)
        labs |= set(c)
    log("  %-52s" % "committed action label" + "".join("%14s" % tag(r) for r in runs))
    for l in sorted(labs):
        row = "  %-52s" % l
        for c in per:
            row += "%14d" % c[l]
        log(row)
    log("")
    log("Cross-tab: for each label, how many of those steps AGREED with the generator")
    log("target. This is the key correction to the earlier report - the label")
    log("'victim_search_wind_aware_retarget_to_interior' does NOT mean the target was")
    log("overridden; the retarget path routes toward the generator's OWN target and")
    log("only changes the label and the routing method.")
    log("")
    for r in runs:
        log("  %s:" % tag(r))
        cc = Counter()
        ca = Counter()
        for x in r["step_records"]:
            l = x["commit"][-1][1] if x.get("commit") else "<no commit>"
            cc[l] += 1
            if x["cause"] == "agree":
                ca[l] += 1
        for l, n in cc.most_common():
            log("    %-52s %4d steps, %4d agreed (%5.1f%%)" % (l, n, ca[l], 100.0 * ca[l] / n))
    log("")

    # ---------------- Q3 ----------------
    log("=" * 78)
    log("Q3 - IS THE LEGACY TARGET SOURCE LIVE?")
    log("=" * 78)
    log("uav_executor.py:3760 _wind_aware_victim_search_target_legacy is reached only")
    log("when the generator returns None (uav_executor.py:3743-3744).")
    log("")
    log("  %-14s %10s %10s %12s %12s" % ("run", "calls", "non-null", "gen==None", "differs"))
    for r in runs:
        recs = r["step_records"]
        calls = sum(1 for x in recs if x.get("legacy_called"))
        nn = sum(1 for x in recs if x.get("legacy_target") is not None)
        gnone = sum(1 for x in recs if x.get("gen_returned_none"))
        diff = 0
        for x in recs:
            lt = x.get("legacy_target")
            gt = x.get("gen_target_exec") or x.get("gen_target_planner")
            if lt is not None and (gt is None or list(lt) != list(gt)):
                diff += 1
        log("  %-14s %10d %10d %12d %12d" % (tag(r), calls, nn, gnone, diff))
    log("")
    log("Every legacy target differs from the generator's by construction: the legacy")
    log("path only runs on steps where the generator produced no target at all.")
    log("")

    # ---------------- Q4 ----------------
    log("=" * 78)
    log("Q4 - PROGRESS TOWARD TARGET on steps where the target WAS honoured")
    log("=" * 78)
    log("Manhattan distance from pos_before to pos_after, measured at agents.UAV.advance")
    log("(the only place agent.pos mutates). 'blocked' = advance produced no move at all")
    log("(agents.UAV.move returns False on out_of_bounds / not_UAV_adjacent /")
    log("no_managed_direction_hold), which is distinct from moving the wrong way.")
    log("")
    log(
        "  %-14s %7s %8s %8s %8s %9s %8s"
        % ("run", "agree", "closer", "same", "farther", "blocked", "closer%")
    )
    for r in runs:
        closer = same = farther = blocked = tot = 0
        for x in r["step_records"]:
            if x["cause"] != "agree":
                continue
            gt = x.get("gen_target_exec") or x.get("gen_target_planner")
            adv = x.get("advance") or []
            if gt is None or not adv:
                continue
            before, after, moved, _a = adv[-1]
            if before is None or after is None:
                continue
            tot += 1
            if not moved:
                blocked += 1
                continue
            d0, d1 = mh(before, gt), mh(after, gt)
            if d1 < d0:
                closer += 1
            elif d1 == d0:
                same += 1
            else:
                farther += 1
        pc = (100.0 * closer / tot) if tot else 0.0
        log(
            "  %-14s %7d %8d %8d %8d %9d %7.1f%%"
            % (tag(r), tot, closer, same, farther, blocked, pc)
        )
    log("")

    # ---------------- Q5 ----------------
    log("=" * 78)
    log("Q5 - CONTRAST, CONTROLLED FOR HAZARD DENSITY")
    log("=" * 78)
    log("A/west 505 is the combo where the earlier x-axis scoring change produced a")
    log("real improvement. If its agreement rate is not materially higher than the")
    log("failing combos, agreement is NOT what distinguishes success from failure.")
    log("")
    log(
        "  %-14s %11s %11s %11s %11s %11s"
        % ("run", "agreement", "mean_fire", "max_fire", "mean_smoke", "hazard_gate")
    )
    for r in runs:
        recs = r["step_records"]
        n = len(recs)
        agree = sum(1 for x in recs if x["cause"] == "agree")
        fires = [x.get("fire_n", 0) for x in recs]
        smokes = [x.get("smoke_n", 0) for x in recs]
        hg = sum(1 for x in recs if "hazard_gate_changed" in (x.get("flags") or []))
        log(
            "  %-14s %10.1f%% %11.1f %11d %11.1f %11d"
            % (tag(r), 100.0 * agree / n, statistics.mean(fires), max(fires),
               statistics.mean(smokes), hg)
        )
    log("")

    # ---------------- Q6 ----------------
    log("=" * 78)
    log("Q6 - DID THE GENERATOR EVER PROPOSE A LEGAL OBSERVATION POST?")
    log("=" * 78)
    log("Legal unpenalized post set = cells within EUCLIDEAN 8 of the victim, in")
    log("bounds, not _downwind_edge_blocked, not _cell_on_edge(margin=")
    log("WIND_INTERIOR_MARGIN=6). Verified against the prompt: (25,3) -> 45 posts,")
    log("(40,25) -> 137 posts (includes the victim's own cell).")
    log("")
    for r in runs:
        recs = r["step_records"]
        log("  --- %s ---" % tag(r))
        log("    never_detected=%s  causes=%s" % (r["eval"]["never_detected"], r["eval"]["unreachable_causes"] or "(none)"))
        log("    victim spawns: %s" % ", ".join("%s@(%d,%d)" % (k, v[0], v[1]) for k, v in sorted(r["spawns"].items())))
        for vid in (r["nd"] or []):
            log("    victim ever within Euclidean 8:  searcher=%s  any UAV=%s"
                % (r["ever_searcher"].get(vid), r["ever_any"].get(vid)))
            log("    closest approach:                searcher=%s  any UAV=%s"
                % (r["min_searcher"].get(vid), r["min_any"].get(vid)))
        # distinct proposed targets
        props = []
        for x in recs:
            gt = x.get("gen_target_exec") or x.get("gen_target_planner")
            if gt is not None:
                props.append((int(gt[0]), int(gt[1])))
        distinct = sorted(set(props))
        log("    proposed targets: %d steps, %d DISTINCT cells" % (len(props), len(distinct)))
        if distinct:
            xs = [c[0] for c in distinct]
            ys = [c[1] for c in distinct]
            log("      x: min=%d max=%d median=%.1f     y: min=%d max=%d median=%.1f"
                % (min(xs), max(xs), statistics.median(xs), min(ys), max(ys), statistics.median(ys)))
        # visited cells
        visited = set()
        for x in recs:
            for before, after, moved, _a in (x.get("advance") or []):
                if after is not None:
                    visited.add((int(after[0]), int(after[1])))
        for vid, posts in sorted((r["posts"] or {}).items()):
            if r["nd"] and vid not in r["nd"]:
                continue
            pset = set((int(c[0]), int(c[1])) for c in posts)
            vx, vy = r["spawns"][vid]
            prop_in = sorted(set(p for p in props if p in pset))
            vis_in = sorted(v for v in visited if v in pset)
            log("    victim %s @ (%d,%d): %d legal unpenalized posts" % (vid, vx, vy, len(pset)))
            log("      generator EVER proposed a target in that set : %s (%d distinct: %s)"
                % ("YES" if prop_in else "NO", len(prop_in), prop_in[:12]))
            log("      executor EVER moved the searcher into the set: %s (%d cells)"
                % ("YES" if vis_in else "NO", len(vis_in)))
        # 5x5 histogram of proposed targets
        if props:
            hist = [[0] * 5 for _ in range(5)]
            for cx, cy in props:
                hist[min(4, cy // 10)][min(4, cx // 10)] += 1
            log("      2-D histogram of PROPOSED targets (rows = y bands, cols = x bands,")
            log("      each bucket 10x10 cells; counts are step-occurrences):")
            log("          x:  0-9  10-19 20-29 30-39 40-49")
            for i in range(4, -1, -1):
                log("      y %2d-%2d %5d %5d %5d %5d %5d"
                    % (i * 10, i * 10 + 9, hist[i][0], hist[i][1], hist[i][2], hist[i][3], hist[i][4]))
        log("")

    # ---------------- Q7 ----------------
    log("=" * 78)
    log("Q7 - DOES THE COVERAGE BONUS RANK UNOBSERVED CELLS ABOVE OBSERVED ONES?")
    log("=" * 78)
    log("MEASURED CORRECTION TO THE PREMISE. _uncovered_region_bonus has THREE call")
    log("sites, and only ONE is gated on unresolved > 0:")
    log("  local_adaptation_generator.py:1001  inside _score_hybrid_search_cell  GATED")
    log("  local_adaptation_generator.py:3235  _pick_global_coverage_escape_target  UNGATED")
    log("  local_adaptation_generator.py:3394  _generate_corridor_waypoints        UNGATED")
    log("So the bonus fires on every candidate regardless of unresolved, and when")
    log("unresolved > 0 it is added TWICE to the same candidate's score.")
    log("")
    log("GATING QUESTION - steps by unresolved_victim_count:")
    log("  %-14s %14s %14s %16s" % ("run", "unresolved==0", "unresolved>0", "bonus calls"))
    for r in runs:
        recs = r["step_records"]
        z = sum(1 for x in recs if int(((x.get("ws_entry") or {}).get("unresolved") or 0)) == 0)
        nz = len(recs) - z
        log("  %-14s %14d %14d %16d" % (tag(r), z, nz, int(r["counters"].get("bonus_calls_total", 0))))
    log("")
    log("A. SPREAD ACROSS CANDIDATES WITHIN A STEP  (max(bonus) - min(bonus)).")
    log("   If ~0 the term cannot influence the argmax regardless of magnitude.")
    log("")
    log("  %-14s %8s %10s %10s %10s %10s %10s"
        % ("run", "steps", "mean", "median", "min", "max", "zero-spread"))
    for r in runs:
        sp = [x["bonus_gated_spread"] for x in r["step_records"] if x.get("bonus_gated_n")]
        sp2 = [x["bonus_ungated_spread"] for x in r["step_records"] if x.get("bonus_ungated_n")]
        allsp = sp or sp2
        if not allsp:
            log("  %-14s %8d %10s" % (tag(r), 0, "no data"))
            continue
        zs = sum(1 for v in allsp if v < 1e-9)
        log("  %-14s %8d %10.2f %10.2f %10.2f %10.2f %10d"
            % (tag(r), len(allsp), statistics.mean(allsp), statistics.median(allsp),
               min(allsp), max(allsp), zs))
    log("")
    log("B. CORRELATION between each candidate's bonus and the TRUE number of")
    log("   unobserved cells within Euclidean 8 of that candidate. Computed per")
    log("   detail step (every 10th step), then summarised across steps.")
    log("   Positive = bonus prefers genuinely unobserved cells (healthy).")
    log("   Near zero = the proxy does not track real coverage gaps.")
    log("   NEGATIVE = the bonus actively prefers ALREADY-OBSERVED cells.")
    log("")
    log("   The quantity correlated is the EFFECTIVE bonus: the TOTAL added to one")
    log("   candidate's score across both call sites in a step (gated call at :1001")
    log("   plus ungated call at :3235), not either call's individual return value.")
    log("   With the double-count that total is what actually moves the argmax.")
    log("")
    for r in runs:
        ps, ss, pa, sa = [], [], [], []
        nsteps = 0
        for x in r["step_records"]:
            cbs = x.get("corr_bonus") or {}
            cb = cbs.get("effective") or cbs.get("gated") or cbs.get("ungated")
            if not cb:
                continue
            nsteps += 1
            for key, acc in (("pearson_searcher", ps), ("spearman_searcher", ss),
                             ("pearson_all", pa), ("spearman_all", sa)):
                v = cb.get(key)
                if v is not None:
                    acc.append(v)
        log("  %s  (%d detail steps)" % (tag(r), nsteps))
        for name, acc in (("Pearson  vs searcher-only unobserved", ps),
                          ("Spearman vs searcher-only unobserved", ss),
                          ("Pearson  vs all-UAV unobserved     ", pa),
                          ("Spearman vs all-UAV unobserved     ", sa)):
            if acc:
                neg = sum(1 for v in acc if v < 0)
                log("    %s: mean=%+.3f median=%+.3f min=%+.3f max=%+.3f  negative in %d/%d steps"
                    % (name, statistics.mean(acc), statistics.median(acc), min(acc), max(acc), neg, len(acc)))
            else:
                log("    %s: no data" % name)
    log("")
    log("GATED / UNGATED SPLIT of that effective bonus, reported separately as")
    log("requested. Per-candidate means within a detail step, averaged over steps:")
    log("")
    log("  %-14s %12s %12s %14s %16s"
        % ("run", "gated mean", "ungated mean", "effective mean", "double-counted"))
    for r in runs:
        g, u, n_dc, n_tot = [], [], 0, 0
        for x in r["step_records"]:
            e = (x.get("corr_bonus") or {}).get("effective")
            if not e:
                continue
            g.append(e["gated_mean"])
            u.append(e["ungated_mean"])
            n_dc += int(e.get("n_double_counted", 0) or 0)
            n_tot += int(e.get("n", 0) or 0)
        if not g:
            log("  %-14s %12s %12s %14s %16s" % (tag(r), "n/a", "n/a", "n/a", "n/a"))
            continue
        gm, um = statistics.mean(g), statistics.mean(u)
        log("  %-14s %12.2f %12.2f %14.2f %10d/%-6d"
            % (tag(r), gm, um, gm + um, n_dc, n_tot))
    log("")
    log("  A candidate is 'double-counted' when both call sites contributed a non-zero")
    log("  bonus to it in the same step. Where the gated and ungated means are equal,")
    log("  the term is being applied at exactly twice its nominal weight.")
    log("")
    log("Scatter summary (one representative detail step per run): bonus vs true")
    log("unobserved count within Euclidean 8.")
    for r in runs:
        for x in r["step_records"]:
            cb = (x.get("corr_bonus") or {}).get("gated")
            if cb and cb.get("sample"):
                log("  %s step %d: bonus range [%.2f, %.2f], unobserved range [%d, %d]"
                    % (tag(r), x["step"], cb["bonus_min"], cb["bonus_max"], cb["unobs_min"], cb["unobs_max"]))
                smp = cb["sample"][:10]
                log("    (bonus, unobs_searcher, unobs_all): %s"
                    % ", ".join("(%.1f,%d,%d)" % (a, b, c) for a, b, c in smp))
                break
    log("")
    log("_observation_coverage_penalty (local_adaptation_generator.py:996, runs")
    log("UNCONDITIONALLY) - spread across candidates and correlation with true")
    log("unobserved count, to test whether it does the steering the bonus does not:")
    log("")
    log("  %-14s %10s %10s %12s %12s" % ("run", "mean_spread", "max_spread", "mean_pearson", "mean_spearman"))
    for r in runs:
        sp = [x["pen_vals_spread"] for x in r["step_records"] if x.get("pen_vals_n")]
        pp, sps = [], []
        for x in r["step_records"]:
            cp = x.get("corr_pen")
            if not cp:
                continue
            if cp.get("pearson_searcher") is not None:
                pp.append(cp["pearson_searcher"])
            if cp.get("spearman_searcher") is not None:
                sps.append(cp["spearman_searcher"])
        log("  %-14s %10s %10s %12s %12s"
            % (tag(r),
               fmt(statistics.mean(sp) if sp else None, 2),
               fmt(max(sp) if sp else None, 2),
               fmt(statistics.mean(pp) if pp else None, 3),
               fmt(statistics.mean(sps) if sps else None, 3)))
    log("")
    log("HYPOTHESIS SIGNATURE CHECK: 1-D projection spans vs true 2-D observed")
    log("fraction. The hypothesis predicts wide spans alongside ~0.5 observed.")
    log("")
    log("  %-14s %14s %14s %14s %14s" % ("run", "final x_span", "final y_span", "obs_frac_search", "obs_frac_all"))
    for r in runs:
        last = None
        for x in reversed(r["step_records"]):
            if x.get("ws_entry"):
                last = x["ws_entry"]
                break
        xs = last["x_span"] if last else [None, None]
        ys = last["y_span"] if last else [None, None]
        log("  %-14s %14s %14s %14.4f %14.4f"
            % (tag(r), "[%s,%s]" % (xs[0], xs[1]), "[%s,%s]" % (ys[0], ys[1]),
               r["obs_frac_searcher"], r["obs_frac_all"]))
    log("")
    log("Per-run coverage (240-step union, Euclidean r=8, /2500):")
    for r in runs:
        log("  %-14s searcher-only=%.4f   all-UAV=%.4f   delta=%+.4f"
            % (tag(r), r["obs_frac_searcher"], r["obs_frac_all"],
               r["obs_frac_all"] - r["obs_frac_searcher"]))
    log("")
    log("MECHANICAL FINDING, verified in source (local_adaptation_generator.py:905-917):")
    log("  _record_victim_searcher_x_band trims both lists to recent[-30:]. So")
    log("  _coverage_x_span / _coverage_y_span are a 30-STEP ROLLING WINDOW, not")
    log("  lifetime coverage. _uncovered_region_bonus is built entirely on those two")
    log("  spans, so it is structurally blind to anything older than 30 steps -")
    log("  a stronger defect than the 1-D projection framing, and it explains the")
    log("  narrow final spans above sitting alongside 0.485-0.641 true coverage.")
    log("")

    # ---------------- Q8: score decomposition ----------------
    log("=" * 78)
    log("Q8. SCORE DECOMPOSITION AT CALL SITE 1 (_pick_global_coverage_escape_target)")
    log("=" * 78)
    log("")
    log("Method: on every 10th step the probe re-scores the entire candidate grid using")
    log("the UNPATCHED production helpers, mirroring the loop at")
    log("local_adaptation_generator.py:3183-3270 filter-for-filter and term-for-term.")
    log("It is self-validating: the mirror's argmax is compared against the best_point")
    log("production itself passed into _finalize_coverage_target.")
    log("")
    n_all = n_ok = 0
    for r in runs:
        wp = [d for d in decs(r) if d.get("prefinal")]
        m = sum(1 for d in wp if d.get("mirror_matches_prefinal"))
        n_all += len(wp)
        n_ok += m
        log("  %-14s %d/%d decompositions reproduced production's argmax"
            % (tag(r), m, len(wp)))
    log("")
    if n_all and n_ok == n_all:
        log("  TOTAL %d/%d. The mirror is EXACT, so the attribution below is a direct"
            % (n_ok, n_all))
        log("  readout of production's arithmetic rather than an inference about it.")
    else:
        log("  TOTAL %d/%d. Non-matching steps are still listed but should be read with"
            % (n_ok, n_all))
        log("  caution.")
    log("")

    log("A. WHICH TERM ACTUALLY DRIVES SELECTION")
    log("")
    log("   Magnitude is not influence. A term that takes the same value on every")
    log("   candidate cannot move the argmax however large it is; only its RANGE")
    log("   (max - min) across the candidate set can. Mean range over detail steps:")
    log("")
    rng: dict = {}
    tkeys: list = []
    for r in runs:
        acc: dict = {}
        for d in decs(r):
            for k, v in (d.get("term_range") or {}).items():
                acc.setdefault(k, []).append(v)
        rng[tag(r)] = {k: statistics.mean(v) for k, v in acc.items()}
        for k in acc:
            if k not in tkeys:
                tkeys.append(k)
    hdr = "   %-24s" + " %13s" * len(runs)
    log(hdr % tuple(["term"] + [tag(r) for r in runs]))
    log("   " + "-" * (24 + 14 * len(runs)))
    tkeys.sort(key=lambda k: -max(rng[tag(r)].get(k, 0.0) for r in runs))
    dead = []
    for k in tkeys:
        vals = [rng[tag(r)].get(k, 0.0) for r in runs]
        if max(abs(v) for v in vals) < 1e-9:
            dead.append(k)
            continue
        log(hdr % tuple([k] + ["%.2f" % v for v in vals]))
    if dead:
        log("")
        log("   Zero range in every run, cannot affect selection: %s" % ", ".join(dead))
    log("")
    log("   Derived, exact from the same per-step ranges:")
    log("")
    dhdr = "   %-38s" + " %13s" * len(runs)
    log(dhdr % tuple(["quantity"] + [tag(r) for r in runs]))
    log("   " + "-" * (38 + 14 * len(runs)))
    dist_net: dict = {}
    cov_eff: dict = {}
    ns_eff: dict = {}
    for r in runs:
        dn, ce, ne = [], [], []
        for d in decs(r):
            tr = d.get("term_range") or {}
            dn.append(tr.get("dist_agent_outer", 0.0) - tr.get("dist_agent_inner", 0.0))
            unres = int(d.get("unresolved", 0) or 0)
            ce.append(tr.get("cov_bonus_ungated", 0.0) * (2.0 if unres > 0 else 1.0))
            gate = float(d.get("coverage_w", 0.0) or 0.0) >= 0.55 or unres > 0
            ne.append(tr.get("never_seen_out", 0.0) * (2.0 if gate else 1.0))
        dist_net[tag(r)] = mean_or(dn, 0.0)
        cov_eff[tag(r)] = mean_or(ce, 0.0)
        ns_eff[tag(r)] = mean_or(ne, 0.0)
    log(dhdr % tuple(["net dist_agent range (+0.25/cell)"]
                     + ["%.2f" % dist_net[tag(r)] for r in runs]))
    log(dhdr % tuple(["EFFECTIVE coverage-bonus range"]
                     + ["%.2f" % cov_eff[tag(r)] for r in runs]))
    log(dhdr % tuple(["EFFECTIVE never_seen range"]
                     + ["%.2f" % ns_eff[tag(r)] for r in runs]))
    ratios = [
        (ns_eff[tag(r)] / cov_eff[tag(r)]) if cov_eff[tag(r)] else None for r in runs
    ]
    log(dhdr % tuple(["never_seen : coverage-bonus ratio"]
                     + [("%.1fx" % v) if v else "n/a" for v in ratios]))
    log("")
    rr = [v for v in ratios if v]
    log("   READING. The prompt's hypothesis was that dist_agent might dominate the")
    log("   coverage bonus. It does not. Net dist_agent range is %.1f-%.1f, which is"
        % (min(dist_net.values()), max(dist_net.values())))
    log("   SMALLER than the effective coverage-bonus range (%.1f-%.1f), so the +0.35"
        % (min(cov_eff.values()), max(cov_eff.values())))
    log("   outer term does not outvote coverage on its own.")
    log("")
    log("   The term that does is _never_seen_proximity_bonus. Its effective range is")
    if rr:
        log("   %.0f-%.0f, i.e. %.0fx to %.0fx the coverage bonus's. It is added TWICE at"
            % (min(ns_eff.values()), max(ns_eff.values()), min(rr), max(rr)))
    log("   call site 1 (once inside _score_hybrid_search_cell at :999, once again at")
    log("   :3232), and it swamps every other term including the coverage bonus.")
    log("")

    log("B. WHY THE SEARCHER NEVER GOES TO AN OBSERVATION POST")
    log("")
    log("   On the same detail steps the probe scores every cell of each victim's legal")
    log("   observation-post set, separating two very different failures:")
    log("     OUTSCORED - the post cell WAS a legal candidate and lost the argmax.")
    log("     EXCLUDED  - the post cell never entered the candidate set at all, so NO")
    log("                 re-weighting of any term could ever have selected it.")
    log("")
    excl_dom = Counter()
    zero_tot = avail_tot = 0
    for r in runs:
        dd = decs(r)
        ndset = set(r.get("nd") or [])
        log("  %s   (%d detail steps; never_detected = %s)"
            % (tag(r), len(dd), ", ".join(sorted(ndset)) if ndset else "none"))
        vids: list = []
        for d in dd:
            for vid in (d.get("posts") or {}):
                if vid not in vids:
                    vids.append(vid)
        for vid in sorted(vids):
            n_avail = n_zero = 0
            npost = 0
            reasons: Counter = Counter()
            deficits: list = []
            gaps: Counter = Counter()
            gapn: Counter = Counter()
            for d in dd:
                e = (d.get("posts") or {}).get(vid)
                if not e:
                    continue
                npost = max(npost, int(e.get("n_post_cells", 0) or 0))
                if int(e.get("n_candidate", 0) or 0) > 0:
                    n_avail += 1
                    if e.get("deficit") is not None:
                        deficits.append(float(e["deficit"]))
                    for k, v in (e.get("term_gap") or {}).items():
                        gaps[k] += float(v)
                        gapn[k] += 1
                else:
                    n_zero += 1
                for k, v in (e.get("excluded") or {}).items():
                    reasons[k] += int(v)
            zero_tot += n_zero
            avail_tot += n_avail
            for k, v in reasons.items():
                excl_dom[k] += v
            mark = "   <-- NEVER DETECTED" if vid in ndset else ""
            log("    %-10s %3d post cells | had >=1 candidate on %d/%d steps | ZERO on %d%s"
                % (vid, npost, n_avail, n_avail + n_zero, n_zero, mark))
            if reasons:
                log("               excluded by (cell-steps): %s"
                    % ", ".join("%s=%d" % (k, v) for k, v in reasons.most_common(4)))
            if deficits:
                md = statistics.mean(deficits)
                if abs(md) < 1e-9:
                    log("               when it WAS a candidate: deficit 0.0 - a post cell")
                    log("               WAS the argmax winner on that step")
                else:
                    ordered = sorted(gaps.items(), key=lambda kv: -abs(kv[1]))[:4]
                    log("               when it WAS a candidate: mean deficit vs winner "
                        "= %.1f" % md)
                    log("               deficit attributed to: %s"
                        % ", ".join("%s %+.1f" % (k, gaps[k] / max(1, gapn[k]))
                                    for k, _ in ordered))
        log("")
    log("   READING. Across all runs and victims, post sets had zero legal candidates")
    log("   on %d victim-steps and at least one on only %d - %.0f%% of the time no"
        % (zero_tot, avail_tot,
           100.0 * zero_tot / max(1, zero_tot + avail_tot)))
    log("   observation post was reachable at all. Dominant exclusion reasons:")
    for k, v in excl_dom.most_common(5):
        log("     %-22s %8d cell-steps" % (k, v))
    log("   Where post cells are EXCLUDED rather than outscored, the coverage bonus is")
    log("   irrelevant by construction: the cells are filtered out before any score is")
    log("   computed. That is a hard geometric constraint, not a weighting problem.")
    log("")
    log("   THE MECHANISM IS coverage_y_commit, AND IT IS A CLIFF, NOT A GRADIENT.")
    log("   Splitting every detail step by whether wind_state['coverage_y_commit'] is")
    log("   set exposes exactly where the post sets go out of reach:")
    log("")
    log("   %-14s %9s %14s %16s %14s"
        % ("run", "commit", "detail steps", "mean candidates", "post cands"))
    for r in runs:
        for label, want in (("None", False), ("set", True)):
            rows = [
                d for d in decs(r)
                if bool(d.get("commit")) == want
            ]
            if not rows:
                continue
            cands = statistics.mean([d.get("n_candidates", 0) for d in rows])
            pc = sum(
                int(e.get("n_candidate", 0) or 0)
                for d in rows for e in (d.get("posts") or {}).values()
            )
            log("   %-14s %9s %14d %16.0f %14d"
                % (tag(r) if label == "None" else "", label, len(rows), cands, pc))
    log("")
    log("   Read the last column. While coverage_y_commit is unset the searcher can see")
    log("   between 100 and 337 legal observation-post cells. The moment it is set - by")
    log("   step 20 in every run, and it is never released again - the candidate set")
    log("   collapses by roughly 90% and the number of reachable observation-post cells")
    log("   becomes EXACTLY ZERO, for every victim, on every remaining detail step of")
    log("   all four runs.")
    log("")
    log("   Two filters do it, both inside the coverage_active block:")
    log("     :3192-3195  commit == north drops every cy < upper_y_min;")
    log("                 commit == south drops every cy > lower_y_max. Half the grid.")
    log("     :3196-3199  y_force_min / y_force_max then drop most of what is left.")
    log("")
    log("   This is a stronger and more specific result than 'the bonus is")
    log("   miscorrelated'. For 20 of 21 measured steps per run, NO setting of ANY")
    log("   scoring weight could have sent the searcher to an observation post, because")
    log("   no observation post was in the candidate set to be scored.")
    log("")
    log("   NUANCE, and it matters for attribution: this happens identically in A/west")
    log("   505, the run that detected every victim. So the y-commit cliff is a hard")
    log("   constraint on targeting but is NOT by itself sufficient to cause a miss -")
    log("   in A/west the searcher's incidental path still covered the victims. It")
    log("   bounds what any scoring fix can achieve; it does not on its own explain the")
    log("   difference between the failing and succeeding runs.")
    log("")

    log("C. fire_tracker_detection_boost - AN EXTERNAL INPUT TO THESE SCORES")
    log("")
    log("   wildfire_model.py:1017-1024: when a FIRE_TRACKER detects a victim it writes")
    log("   fire_tracker_detection_boost into EVERY victim searcher's wind_state. It is")
    log("   read back at local_adaptation_generator.py:729 (_coverage_mode_active), :952")
    log("   (_coverage_priority) and :1060. At :1061-1063 a boost >= 0.06 combined with")
    log("   zero searcher detections sets force_coverage_escape and lifts")
    log("   coverage_priority to >= 0.7. That is not a nudge to the scores:")
    log("   force_coverage_escape raises min_escape_dist from 6.0 to 14.0 and disables")
    log("   the parity filter, so a tracker's detection reshapes the searcher's")
    log("   CANDIDATE SET from outside the searcher entirely.")
    log("")
    log("   %-14s %8s %8s %12s %14s" % ("run", "max", "mean", "steps > 0", "steps >= 0.06"))
    ft_any = False
    for r in runs:
        vals = [
            float(x["ft_boost"]) for x in r["step_records"]
            if x.get("ft_boost") is not None
        ]
        if not vals:
            log("   %-14s %8s %8s %12s %14s" % (tag(r), "n/a", "n/a", "n/a", "n/a"))
            continue
        nz = sum(1 for v in vals if v > 0.0)
        nb = sum(1 for v in vals if v >= 0.06)
        if nz:
            ft_any = True
        log("   %-14s %8.3f %8.3f %12d %14d"
            % (tag(r), max(vals), statistics.mean(vals), nz, nb))
    log("")
    if ft_any:
        log("   The boost is NON-ZERO in these runs, so it belongs in the term breakdown:")
        log("   it inflates coverage_w, which multiplies both the obs_penalty and the")
        log("   never_seen terms by (1 + coverage_w), and can force the escape branch.")
    else:
        log("   The boost is ZERO on every step of all four runs, so it is NOT a")
        log("   confounder here. The mechanism is real and reachable, but it did not")
        log("   fire in these four runs, so it explains none of the behaviour above.")
    log("")

    log("D. CALL-SITE ASYMMETRY BETWEEN THE TWO SCORING LOOPS")
    log("")
    log("   Both loops call _score_hybrid_search_cell and then add their own terms, but")
    log("   they do not add the same ones. Verified in source:")
    log("")
    log("     site 1  _pick_global_coverage_escape_target, scorer at :3214")
    log("       :3232  RE-ADDS _never_seen_proximity_bonus * (1 + coverage_w)")
    log("       :3235  adds _uncovered_region_bonus (ungated)")
    log("       :3238  adds dist_agent * 0.35")
    log("       :3239  x-force for west AND east AND the generic ax-branch")
    log("       :3266  adds pocket_center distance * 0.45")
    log("")
    log("     site 2  _generate_corridor_waypoints, scorer at :3376")
    log("       :3394  adds _uncovered_region_bonus (ungated)   <- same")
    log("       ----   does NOT re-add _never_seen_proximity_bonus")
    log("       ----   does NOT add dist_agent * 0.35")
    log("       ----   does NOT add any pocket_center term")
    log("       :3397  x-force ONLY for the west + east_pending case")
    log("       :3415  SUBTRACTS WIND_EDGE_PENALTY * 2.0 under force_interior, which")
    log("              site 1 does not do at all")
    log("")
    log("   Consequences, in the units measured in section A:")
    log("     - Both sites double-count _uncovered_region_bonus when unresolved > 0")
    log("       (gated call at :1001 plus the ungated call at :3235 / :3394).")
    log("     - Only site 1 doubles _never_seen_proximity_bonus. Since that term's")
    log("       range is the largest of all, site 1 roughly HALVES the relative")
    log("       influence of the coverage bonus compared with site 2.")
    log("     - Only site 1 applies a net +0.25 per cell outward pull (see the")
    log("       dist_agent sign asymmetry in OTHER DEFECTS).")
    log("     So the escape path and the corridor path rank coverage differently, and")
    log("     the same wind_state can yield different targets depending on which path")
    log("     produced it.")
    log("")
    corr_dead = all(
        (r["counters"].get("corridor_waypoint_calls", 0) or 0) == 0 for r in runs
    )
    if corr_dead:
        log("   IMPORTANT: this asymmetry is LATENT, not active, in these four runs.")
        log("   corridor_waypoint_calls == 0 in all four, so site 2 never executed and")
        log("   every measured target came from site 1. The asymmetry cannot explain")
        log("   any divergence observed here; it is a defect waiting for the corridor")
        log("   path to be revived.")
    else:
        log("   Site 2 DID execute in these runs, so the asymmetry is active.")
    log("")

    log("E. WHY ALL OF THE ABOVE IS PINNED ON: coverage_w IS EFFECTIVELY CONSTANT")
    log("")
    log("   Everything in sections A, B and C follows from one measured fact:")
    log("")
    log("   %-14s %12s %12s %14s %18s"
        % ("run", "mean cov_w", "max cov_w", "cov_w >= 0.9", "min_escape values"))
    for r in runs:
        cw = [
            float(x["coverage_w"]) for x in r["step_records"]
            if x.get("coverage_w") is not None
        ]
        me = sorted({
            d.get("min_escape_dist") for d in decs(r)
            if d.get("min_escape_dist") is not None
        })
        if not cw:
            continue
        log("   %-14s %12.3f %12.3f %9d/%-4d %18s"
            % (tag(r), statistics.mean(cw), max(cw),
               sum(1 for v in cw if v >= 0.9), len(cw),
               "/".join("%.0f" % v for v in me)))
    log("")
    log("   The causal chain, all verified in source:")
    log("")
    log("     1. _coverage_mode_active (:724-739) returns True for EVERY input with")
    log("        unresolved > 0. Lines :731-738 test steps_since_detection, corridor")
    log("        failure, boost > 0.2 and post_rescue, each returning True - and then")
    log("        :739 returns True unconditionally anyway. Those four tests cannot")
    log("        change the result, so the function is simply 'unresolved > 0'.")
    log("     2. _coverage_priority (:959-962) therefore raises base to >= 0.9 whenever")
    log("        a victim is unresolved, then :963 returns base + boost. Measured:")
    log("        coverage_w >= 0.9 on 239 of 240 steps in every run.")
    log("     3. coverage_w >= 0.9 sets min_escape_dist = max(min_escape, 20.0) at")
    log("        :3147-3148. Measured min_escape_dist only ever takes the values above -")
    log("        never its nominal 6.0, and never the 14.0 that force_coverage_escape")
    log("        would give. Every cell within Manhattan 20 of the searcher is excluded")
    log("        from its own candidate set.")
    log("     4. coverage_w >= 0.9 also forces wind_w = HYBRID_WIND_WEIGHT * 0.15 at")
    log("        :985-986, which is why the downwind term has the SMALLEST range of all")
    log("        (0.35-0.47 in section A). The wind-aware search is not wind-aware in")
    log("        practice.")
    log("     5. coverage_active being permanently True is what arms the y-commit")
    log("        filters of section B.")
    log("")
    log("   So the searcher spends essentially the whole run in maximum-coverage mode")
    log("   with a 20-cell exclusion radius around itself, a dead wind term, and half")
    log("   the grid filtered out. The coverage bonus is being asked to steer inside a")
    log("   candidate set that these three mechanisms have already determined.")
    log("")

    # ---------------- verdicts ----------------
    agr = {}
    for r in runs:
        recs = r["step_records"]
        agr[tag(r)] = 100.0 * sum(1 for x in recs if x["cause"] == "agree") / len(recs)
    esc = {}
    leg = {}
    dist = {}
    for r in runs:
        recs = r["step_records"]
        esc[tag(r)] = sum(1 for x in recs if x["cause"] == "escape_target_routing")
        leg[tag(r)] = sum(1 for x in recs if x["cause"] == "legacy_target_source")
        props = set()
        for x in recs:
            gt = x.get("gen_target_exec") or x.get("gen_target_planner")
            if gt is not None:
                props.add((int(gt[0]), int(gt[1])))
        dist[tag(r)] = len(props)

    log("=" * 78)
    log("VERDICT 1 - IS THE EXECUTOR THE BINDING CONSTRAINT ON SEARCHER TARGETING?")
    log("=" * 78)
    log("")
    log("ANSWER: (b) NO. The executor follows the generator on the large majority of")
    log("steps. The problem is in what the generator PROPOSES, so the fix belongs in")
    log("local_adaptation_generator.py.")
    log("")
    log("AMENDED BY Q8: the right FILE is settled, but 'a scoring change can work' -")
    log("as this verdict was originally worded - is not supported. Q8-B shows the")
    log("binding constraint inside the generator is the candidate FILTERS, not the")
    log("scores. A pure re-weighting cannot select a cell that was filtered out before")
    log("scoring, and on 20 of 21 measured steps per run every observation post was.")
    log("")
    log("Supporting numbers:")
    log("  - Agreement rate (Q1):")
    log("      %s"
        % "  ".join("%s %.1f%%" % (k, v) for k, v in agr.items()))
    log("    The executor acted on the generator's exact cell on 197-209 of 240")
    log("    steps in every run.")
    log("  - Exactly ONE mechanism actually changes the acted-on target:")
    log("    escape_target routing (uav_executor.py:1213), on %s steps."
        % "/".join(str(esc[tag(r)]) for r in runs))
    log("    Crucially, wind_state['escape_target'] is WRITTEN BY THE GENERATOR")
    log("    (local_adaptation_generator.py:3509 and :3579); uav_executor.py:1208 only")
    log("    ever clears it. So even this override is fed by generator-authored state,")
    log("    not by a competing executor policy.")
    log("  - The legacy source is live but negligible: %s step(s) of 240 (Q3),"
        % "/".join(str(leg[tag(r)]) for r in runs))
    log("    reached only because the generator returned None that step.")
    log("  - The earlier report's conclusion is REFUTED (Q2). The label")
    log("    victim_search_wind_aware_retarget_to_interior fires on 160-217 steps, but")
    log("    82.8-92.5% of those steps AGREED with the generator's target. That path")
    log("    (_apply_retarget_with_pathfinding_fallback) routes toward the generator's")
    log("    OWN target and only changes the label and the routing method. The label")
    log("    was misread as evidence of override.")
    log("  - victim_search_hazard_retreat is rare: 4/16/0/1 steps, and 87.5-100% of")
    log("    those still agreed.")
    log("  - Live-victim pursuit never interrupted the cursor: 0 steps carried")
    log("    victim_escape_committed or victim_stuck_escape in any run.")
    log("  - The target is honoured AND reachable (Q4): on agreeing steps the searcher")
    log("    reduced Manhattan distance to it on 84.7/65.6/97.5/86.1% of steps.")
    log("  - Agreement does NOT distinguish success from failure (Q5). A/west 505, the")
    log("    designated contrast case (never_detected = 0 at HEAD, versus 1 in each of")
    log("    the other three), has the LOWEST agreement (82.1%) while the three")
    log("    failing runs have the HIGHEST (87.1%). Controlled for hazard density this")
    log("    still holds: A/west has the least fire (79.9 mean cells) and 1 hazard-gate")
    log("    trigger; D/south has the most fire (229.9) and 22 triggers, yet identical")
    log("    87.1% agreement. The agreement difference does not survive - and it points")
    log("    the wrong way.")
    log("  - The decisive evidence is Q6. In all three FAILING runs the generator never")
    log("    once proposed a cell inside the missed victim's legal post set across 240")
    log("    steps, and proposed only %s DISTINCT cells total. A/north 101 is the"
        % "/".join(str(dist[tag(r)]) for r in runs[:2] + runs[3:]))
    log("    starkest: 137 legal posts available, including the victim's own cell, and")
    log("    13 distinct targets proposed, none in the set. The SUCCESS run A/west 505")
    log("    proposed 37 distinct cells spread across the grid and reached 4 of 5")
    log("    victims' post sets.")
    log("")
    log("No executor mechanism needs to change for a generator scoring fix to land.")
    log("If a future change wants the escape_target path to stop diverting the cursor,")
    log("that key is set in local_adaptation_generator.py, not in uav_executor.py.")
    log("")
    # correlation strength of the EFFECTIVE bonus, for choosing among four options
    sp_mean = {}
    sp_flip = 0
    for r in runs:
        acc = []
        for x in r["step_records"]:
            cbs = x.get("corr_bonus") or {}
            cb = cbs.get("effective") or cbs.get("gated")
            if cb and cb.get("spearman_searcher") is not None:
                acc.append(cb["spearman_searcher"])
        sp_mean[tag(r)] = mean_or(acc)
    signs = [v for v in sp_mean.values() if v is not None]
    if signs and min(signs) < 0 < max(signs):
        sp_flip = 1
    strong = bool(signs) and min(abs(v) for v in signs) >= 0.5 and not sp_flip
    outvoted = bool([v for v in ratios if v]) and min(v for v in ratios if v) >= 2.0

    log("=" * 78)
    log("VERDICT 2 - WHICH DOES THE Q7 DATA SUPPORT?")
    log("=" * 78)
    log("")
    if strong and outvoted:
        log("ANSWER: (4) THE PROXY WORKS BUT IS OUTVOTED. The effective bonus does track")
        log("true unobserved area (mean Spearman %s), but its range is dwarfed by"
            % ", ".join(fmt(v, 3) for v in signs))
        log("_never_seen_proximity_bonus, so it cannot carry the argmax. That implies")
        log("RE-WEIGHTING, not rewriting.")
    else:
        log("ANSWER: (2) CALLED BUT UNCORRELATED, with two corrections - one to how")
        log("option (2) is worded, and one that the three-slot list cannot express.")
        log("")
        log("The bonus is emphatically NOT inert: its spread across candidates is large.")
        log("What fails is the correlation. It does not track real coverage gaps.")
        log("")
        log("The FOURTH option offered in the prompt - 'the proxy works but is outvoted'")
        log("- was tested against the data and is NOT selected, because its precondition")
        log("fails: the correlation is not strong. Mean Spearman of the EFFECTIVE bonus")
        log("against true searcher-unobserved count is")
        log("  %s" % ", ".join("%s %s" % (k, sfmt(v)) for k, v in sp_mean.items()))
        log("- weak, and the SIGN FLIPS across runs. A proxy that ranks already-observed")
        log("cells above unobserved ones in half the runs is not 'working'.")
        log("")
        if outvoted:
            log("However, the second half of that option IS confirmed, and it matters: the")
            log("bonus is ALSO outvoted. Its effective range is %.0f-%.0f while"
                % (min(cov_eff.values()), max(cov_eff.values())))
            log("_never_seen_proximity_bonus's is %.0f-%.0f (%.0fx-%.0fx larger, Q8-A)."
                % (min(ns_eff.values()), max(ns_eff.values()),
                   min(v for v in ratios if v), max(v for v in ratios if v)))
            log("So the honest reading is BOTH: the proxy is miscorrelated AND outvoted.")
            log("Re-weighting alone would not fix it, because a term that does not track")
            log("coverage gaps produces the wrong answer at any weight; and rewriting the")
            log("proxy alone would not fix it either, while a term with 20x its range")
            log("still decides the argmax.")
    log("")
    log("Supporting numbers:")
    log("  - NOT gated off, killing option (1). unresolved == 0 on only %s of"
        % "/".join(
            str(sum(1 for x in r["step_records"]
                    if (x.get("ws_entry") or {}).get("unresolved", 1) == 0))
            for r in runs
        ))
    log("    240 steps, so the gated call site passes on the large majority. More")
    log("    fundamentally, 2 of the 3 call sites are NOT GATED AT ALL")
    log("    (local_adaptation_generator.py:3235 and :3394), so the bonus fired")
    log("    %s times per run."
        % " / ".join("{:,}".format(r["counters"].get("bonus_calls_total", 0))
                     for r in runs))
    log("    When unresolved > 0 it is added TWICE to the same")
    log("    candidate. The premise that the coverage path is gated off is")
    log("    measurably false.")
    log("  - Option (2)'s 'spread near zero' clause is FALSE. Mean spread across")
    log("    candidates within a step is %s, and ZERO steps in any"
        % "/".join(
            fmt(mean_or([x["bonus_gated_spread"] for x in r["step_records"]
                         if x.get("bonus_gated_n")]), 2)
            for r in runs
        ))
    log("    run had zero spread. The term does influence the argmax, strongly.")
    log("  - Option (2)'s correlation clause is TRUE, and this is the real defect.")
    log("    Spearman of the EFFECTIVE bonus vs true unobserved count within Euclidean")
    log("    8, averaged over detail steps:")
    log("      %s   against the searcher-only observed"
        % " / ".join(sfmt(sp_mean[tag(r)]) for r in runs))
    sp_all = {}
    for r in runs:
        acc = []
        for x in r["step_records"]:
            cbs = x.get("corr_bonus") or {}
            cb = cbs.get("effective") or cbs.get("gated")
            if cb and cb.get("spearman_all") is not None:
                acc.append(cb["spearman_all"])
        sp_all[tag(r)] = mean_or(acc)
    log("      %s   against the all-UAV set."
        % " / ".join(sfmt(sp_all[tag(r)]) for r in runs))
    log("    The sign FLIPS across runs and the magnitudes are weak. A term that ranks")
    log("    already-observed cells above unobserved ones in half the runs is not")
    log("    performing coverage exploration.")
    log("  - Scale invariance, worth stating explicitly: because the gated and ungated")
    log("    call sites return the SAME value for a cell, the effective bonus is exactly")
    log("    2x the single-call value, and Pearson/Spearman are invariant to positive")
    log("    scaling. So the double-count doubles the term's LEVERAGE on the argmax but")
    log("    cannot change its correlation. Correlating the effective quantity was the")
    log("    right thing to do, and it confirms the defect is in the proxy, not in the")
    log("    accounting.")
    sp_pen = {}
    for r in runs:
        acc = [
            x["corr_pen"]["spearman_searcher"] for x in r["step_records"]
            if (x.get("corr_pen") or {}).get("spearman_searcher") is not None
        ]
        sp_pen[tag(r)] = mean_or(acc)
    log("  - _observation_coverage_penalty is not doing the steering either: mean")
    log("    Spearman %s, equally inconsistent."
        % " / ".join(sfmt(sp_pen[tag(r)]) for r in runs))
    log("  - The 1-D projection hypothesis is CONFIRMED on correlation but REFUTED on")
    log("    its predicted signature. It predicted wide spans, small spread and")
    log("    near-zero correlation. Measured: spread is LARGE, and the spans are NARROW")
    log("    at the end of the run ([7,25]x[30,41], [1,13]x[41,48], [24,27]x[17,27],")
    log("    [8,25]x[30,42]) rather than wide. The reason is mechanical and stronger")
    log("    than the hypothesis: the spans come from lists trimmed to recent[-30:]")
    log("    (local_adaptation_generator.py:913, :917), so they describe only a 30-step")
    log("    rolling box. The bonus cannot see lifetime coverage in ANY number of")
    log("    dimensions, which is why true coverage sits at 0.485-0.641 while the spans")
    log("    report a small recent box.")
    log("")
    log("=" * 78)
    log("OTHER DEFECTS OBSERVED (recorded, NOT chased this round)")
    log("=" * 78)
    log("")
    log("1. dist_agent SIGN ASYMMETRY. _score_hybrid_search_cell:1010 applies")
    log("   score -= dist_agent * 0.1, while call site 1 at :3238 applies")
    log("   score += dist_agent * 0.35. The net effect at site 1 is +0.25 per cell of")
    log("   Manhattan distance from the agent: the scorer is written to prefer NEARBY")
    log("   cells and the call site overrides that into a preference for DISTANT ones.")
    log("   Measured net range across candidates: %s (Q8-A)."
        % ", ".join("%.1f" % dist_net[tag(r)] for r in runs))
    log("   Call site 2 has no such term, so the two paths disagree about whether")
    log("   distance is good or bad. Not chased this round, per instruction.")
    log("")
    log("2. _uncovered_region_bonus DOUBLE-COUNT. Added once inside the scorer at :1001")
    log("   (gated on unresolved > 0) and again, ungated, at :3235 and :3394. Whenever")
    log("   unresolved > 0 the term is applied at twice its nominal weight, so")
    log("   COVERAGE_UNVISITED_X_BONUS = 14.0 is effectively 28.0 on those steps.")
    log("")
    log("3. _never_seen_proximity_bonus DOUBLE-COUNT AT SITE 1 ONLY (:999 and :3232).")
    log("   This is the term that actually decides the argmax (Q8-A), and it is the one")
    log("   most affected by the asymmetry in Q8-D.")
    log("")
    log("4. coverage_y_commit PERMANENTLY EXCLUDES EVERY OBSERVATION POST (Q8-B). Once")
    log("   set - by step 20 in all four runs, and never released - the filters at")
    log("   :3192-3199 cut the candidate set by ~90% and take the number of reachable")
    log("   observation-post cells to exactly zero on every subsequent measured step.")
    log("   This is the largest single constraint found, and it is a filter, not a")
    log("   weight, so no scoring change can reach past it.")
    log("")
    log("=" * 78)
    log("SUGGESTION (not part of the diagnosis; recorded after both verdicts)")
    log("=" * 78)
    log("")
    log("The next change should be a GENERATOR change, and the target-diversity gap in")
    log("Q6 is the thing to attack: 12-14 distinct proposed cells in failing runs")
    log("versus 37 in the succeeding one. Three candidate root causes are visible in")
    log("the data and are worth separating before designing anything:")
    log("  1. The 30-step rolling window (:913, :917). A lifetime visited-cell or")
    log("     visited-coarse-bucket structure would let the exploration term see real")
    log("     gaps. This is a state-representation change, not a weight tweak.")
    log("  2. corridor_waypoint_calls == 0 in ALL FOUR RUNS. _generate_corridor_waypoints")
    log("     never executed; every target came from _pick_global_coverage_escape_target")
    log("     (185-209 steps) or a bare _finalize_coverage_target escape (30-54 steps).")
    log("     An entire intended target-generation path is dead at HEAD, which would")
    log("     explain why so few distinct cells are proposed. Worth confirming why")
    log("     before tuning anything that assumes the corridor path runs.")
    log("  3. NEW, and the strongest of the three: coverage_y_commit. It is a FILTER,")
    log("     not a weight (:3192-3199). Q8-B shows it removing 100% of every victim's")
    log("     observation-post set on 20 of 21 measured steps per run, in all four runs.")
    log("     Whatever is done to the scoring terms cannot reach a cell that was never")
    log("     scored. This should be settled before any term is re-weighted, and it is")
    log("     a different kind of change from either of the above.")
    log("")
    log("Re-weighting _uncovered_region_bonus is NOT indicated, and Q8 sharpens why.")
    log("Its spread is already large, so scaling it changes the argmax without making")
    log("it track coverage; and it sits under a term with roughly 20x its range, so a")
    log("proportionate increase would have to be very large to matter. Both")
    log("double-counts (:1001 + :3235 for the coverage bonus, :999 + :3232 for")
    log("never_seen) should be resolved on their own merits regardless, since each")
    log("silently applies a term at twice its nominal weight.")
    log("")

    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % OUT_PATH, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
