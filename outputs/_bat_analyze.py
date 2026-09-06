"""Aggregate outputs/_bat_<arm>_<wind>_<roles>_<seed>.json into outputs/_bat_analysis.txt."""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict

OUT = "outputs/_bat_analysis.txt"
CANON = [
    ("east", "half", 101), ("east", "half", 202), ("east", "half", 303), ("east", "half", 404), ("east", "half", 505),
    ("south", "half", 101), ("south", "half", 202), ("south", "half", 303), ("south", "half", 404), ("south", "half", 505),
    ("east", "default", 101), ("east", "default", 202), ("east", "default", 303),
]
LOW, CRIT = 30.0, 15.0

lines: list[str] = []


def p(s: str = "") -> None:
    lines.append(s)


def load() -> dict:
    runs = {}
    for path in sorted(glob.glob("outputs/_bat_*.json")):
        if os.path.getsize(path) == 0:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as exc:  # pragma: no cover
            p("UNREADABLE %s: %r" % (path, exc))
            continue
        if "arm" not in d:
            continue
        runs[(d["arm"], d["wind"], d["roles"], int(d["seed"]))] = d
    return runs


def combo(k) -> str:
    return "%s/%s/%d" % (k[1], k[2], k[3])


def uav_cells(d) -> dict:
    """uid -> list of cells per step."""
    out = defaultdict(list)
    for s in d["rec"]["steps"]:
        for row in s["uavs"]:
            out[row[0]].append(tuple(row[1]) if row[1] is not None else None)
    return out


def first_divergence(a, b):
    ca, cb = uav_cells(a), uav_cells(b)
    n = min(len(a["rec"]["steps"]), len(b["rec"]["steps"]))
    diff_steps = 0
    first = None
    for i in range(n):
        same = all(ca[u][i] == cb.get(u, [None] * n)[i] for u in ca)
        if not same:
            diff_steps += 1
            if first is None:
                first = i + 1
    return first, diff_steps, n


def trend_items(ctx: str) -> list:
    body = ctx.split("TREND_WORSENING:", 1)[1] if "TREND_WORSENING:" in ctx else ""
    return [x.strip().split(" ")[0] for x in body.split(";") if x.strip()]


def per_run_stock(d) -> dict:
    rec = d["rec"]
    steps = rec["steps"]
    last = steps[-1]
    info = {"uavs": {}, "n_steps": len(steps)}
    moves = Counter()
    minlvl = {}
    for st, uid, moved, before, after, status in rec["drain_calls"]:
        if moved:
            moves[uid] += 1
        if after is not None:
            minlvl[uid] = min(minlvl.get(uid, 1e9), after)
    prut_min = {}
    prut_lt120 = Counter()
    for st, uid, prut in rec["prut_samples"]:
        if prut is None:
            continue
        prut_min[uid] = min(prut_min.get(uid, 1e9), prut)
        if prut < 120.0:
            prut_lt120[uid] += 1
    kn_status_seen = defaultdict(Counter)
    ag_status_seen = defaultdict(Counter)
    holds = Counter()
    for s in steps:
        for row in s["uavs"]:
            uid = row[0]
            ag_status_seen[uid][row[6]] += 1
            kn_status_seen[uid][str(row[8])] += 1
            if row[3] == "no_managed_direction_hold":
                holds[uid] += 1
    for row in last["uavs"]:
        uid = row[0]
        info["uavs"][uid] = {
            "role": row[4],
            "final": row[5],
            "min": minlvl.get(uid),
            "moves": moves[uid],
            "holds": holds[uid],
            "ag_status": dict(ag_status_seen[uid]),
            "kn_status": dict(kn_status_seen[uid]),
            "prut_min": prut_min.get(uid),
            "prut_lt120_steps": prut_lt120[uid],
        }
    tc = rec["trigger_type_counts"]
    info["LOW_BATTERY"] = tc.get("LOW_BATTERY", 0)
    info["CRITICAL_BATTERY"] = tc.get("CRITICAL_BATTERY", 0)
    info["RESOURCE_DEGRADING"] = tc.get("RESOURCE_DEGRADING", 0)
    info["TREND_WORSENING"] = tc.get("TREND_WORSENING", 0)
    # RESOURCE_DEGRADING produced by the LOCAL resource analyzer, split by whether the
    # knowledge-side PRUT at that call was < 120 (battery runway) or not (reliability path)
    prut_by = {}
    for st, uid, prut in rec["prut_samples"]:
        prut_by[(st, uid)] = prut
    rd_local = rd_local_runway = 0
    for row in rec["local_resource"]:
        if len(row) < 8:
            continue
        st, uid = row[0], row[1]
        if "RESOURCE_DEGRADING" in row[7]:
            rd_local += 1
            pv = prut_by.get((st - 1, uid))
            if pv is not None and pv < 120.0:
                rd_local_runway += 1
    info["rd_local"] = rd_local
    info["rd_local_runway"] = rd_local_runway
    info["local_latest_has_level"] = sum(1 for r in rec["local_resource"] if len(r) >= 8 and r[2])
    info["local_calls"] = sum(1 for r in rec["local_resource"] if len(r) >= 8)
    tw = [r for r in rec["global_trends"] if "TREND_WORSENING" in r[1]]
    info["tw_steps"] = len(tw)
    info["tw_battery_mentioned"] = sum(1 for r in tw if r[2])
    info["tw_battery_only"] = sum(1 for r in tw if trend_items(r[3]) == ["mean_battery"])
    info["monitor_low"] = sum(1 for r in rec["monitor_events"] if r[1])
    info["monitor_crit"] = sum(1 for r in rec["monitor_events"] if r[2])
    info["alerts"] = sum(s["low_battery_alerts"] for s in steps)
    info["fs_actions"] = Counter(r[2] for r in rec["failsafe_plan"] if len(r) >= 8)
    info["prefer_critical_steps"] = sum(1 for r in rec["failsafe_plan"] if len(r) >= 8 and r[7])
    info["reasons_with_battery"] = sum(1 for r in rec["safety_reasons"] if "critical_battery" in r[1])
    info["modes"] = Counter(r[1] for r in rec["mode_updates"])
    info["weight_modes"] = dict(rec["weight_modes"])
    info["fs_mode_steps"] = Counter(s["fs_mode"] for s in steps)
    info["mgm_phase_steps"] = Counter(s["mgm_phase"] for s in steps)
    info["override_steps"] = sum(1 for s in steps if s["exec"] and s["exec"]["override"])
    info["constraint"] = rec["constraint_battery"]
    info["constraint_reasons_battery"] = rec["constraint_reasons_battery"]
    info["feas"] = rec["utility_feasibility"]
    info["update_battery_calls"] = rec["update_battery_calls"]
    info["eval"] = d["eval"]
    info["terminal"] = d["terminal_step"]
    info["wall"] = d["wall_s"]
    return info


def agg_callers(runs, arm, section, attr) -> dict:
    reads = defaultdict(lambda: [0, None, None])
    writes = defaultdict(lambda: [0, None, None, None, None])
    for k, d in runs.items():
        if k[0] != arm:
            continue
        log = d["rec"][section][attr]
        for c, (n, f, l) in log.get("reads", {}).items():
            r = reads[c]
            r[0] += n
            r[1] = f if r[1] is None else min(r[1], f)
            r[2] = l if r[2] is None else max(r[2], l)
        for c, (n, f, l, mn, mx) in log.get("writes", {}).items():
            w = writes[c]
            w[0] += n
            w[1] = f if w[1] is None else min(w[1], f)
            w[2] = l if w[2] is None else max(w[2], l)
            if mn is not None:
                w[3] = mn if w[3] is None else min(w[3], mn)
            if mx is not None:
                w[4] = mx if w[4] is None else max(w[4], mx)
    return {"reads": dict(reads), "writes": dict(writes)}


def print_callers(title, agg) -> None:
    p(title)
    p("  READS (caller: total count over the arm, first step, last step)")
    for c, (n, f, l) in sorted(agg["reads"].items(), key=lambda kv: -kv[1][0]):
        p("    %-62s %8d  steps %s..%s" % (c, n, f, l))
    p("  WRITES (caller: total count, first step, last step, min value, max value)")
    for c, (n, f, l, mn, mx) in sorted(agg["writes"].items(), key=lambda kv: -kv[1][0]):
        p("    %-62s %8d  steps %s..%s  values %s..%s" % (c, n, f, l, mn, mx))
    p()


def fmt_eval(e) -> str:
    keys = ("rescued", "dead", "unreachable", "candidate", "firefighter_deaths", "burnt_cells", "terminal_step")
    return " ".join("%s=%s" % (k, e.get(k)) for k in keys)


def main() -> int:
    runs = load()
    p("=" * 100)
    p("BATTERY DIAGNOSIS - MEASUREMENT AGGREGATE")
    p("=" * 100)
    arms = Counter(k[0] for k in runs)
    p("runs loaded: %s" % dict(arms))
    missing = [(arm, c) for arm in ("stock", "nodrain") for c in CANON if (arm,) + c not in runs]
    if missing:
        p("MISSING: %s" % missing)
    p()

    # ---------------------------------------------------------------- stock
    p("-" * 100)
    p("1. STOCK ARM - per run, per UAV: final level at step 240, minimum, moves, holds, statuses, runway")
    p("-" * 100)
    stock_infos = {}
    for c in CANON:
        d = runs.get(("stock",) + c)
        if d is None:
            continue
        info = per_run_stock(d)
        stock_infos[c] = info
        p("run %s  terminal=%s wall=%ss  eval: %s" % (combo(("stock",) + c), info["terminal"], info["wall"], fmt_eval(info["eval"])))
        for uid, u in sorted(info["uavs"].items()):
            p("   uav %s %-16s final=%6.2f min=%6.2f moves=%3d holds=%3d agent_status=%s kn_status=%s prut_min=%s prut<120 steps=%d" % (
                uid, u["role"], u["final"], u["min"], u["moves"], u["holds"], u["ag_status"], u["kn_status"],
                ("%.1f" % u["prut_min"]) if u["prut_min"] is not None else None, u["prut_lt120_steps"]))
        p("   triggers: LOW_BATTERY=%d CRITICAL_BATTERY=%d RESOURCE_DEGRADING=%d (local calls=%d, local runway-driven=%d) TREND_WORSENING=%d (battery mentioned=%d, battery-only=%d)" % (
            info["LOW_BATTERY"], info["CRITICAL_BATTERY"], info["RESOURCE_DEGRADING"], info["rd_local"], info["rd_local_runway"],
            info["tw_steps"], info["tw_battery_mentioned"], info["tw_battery_only"]))
        p("   monitor low=%d critical=%d | alerts=%d | local analyzer saw battery_level in latest obs: %d/%d calls | update_battery calls=%d" % (
            info["monitor_low"], info["monitor_crit"], info["alerts"], info["local_latest_has_level"], info["local_calls"], info["update_battery_calls"]))
        p("   fail-safe actions: %s | prefer_critical steps=%d | safety reasons with critical_battery=%d | modes=%s" % (
            dict(info["fs_actions"]), info["prefer_critical_steps"], info["reasons_with_battery"], dict(info["modes"])))
        p("   fs_mode per step=%s | mgm_phase=%s | weight_modes=%s | override steps=%d" % (
            dict(info["fs_mode_steps"]), dict(info["mgm_phase_steps"]), info["weight_modes"], info["override_steps"]))
        p("   constraint _battery_reasons: %s, battery rejection reasons=%d | utility feasibility: %s" % (
            info["constraint"], info["constraint_reasons_battery"], info["feas"]))
        p()

    if stock_infos:
        all_final = [u["final"] for i in stock_infos.values() for u in i["uavs"].values()]
        all_min = [u["min"] for i in stock_infos.values() for u in i["uavs"].values()]
        all_moves = [u["moves"] for i in stock_infos.values() for u in i["uavs"].values()]
        all_prut = [u["prut_min"] for i in stock_infos.values() for u in i["uavs"].values() if u["prut_min"] is not None]
        p("STOCK SUMMARY over %d runs / %d UAV-runs:" % (len(stock_infos), len(all_final)))
        p("   final level at step 240: min=%.2f max=%.2f mean=%.2f" % (min(all_final), max(all_final), sum(all_final) / len(all_final)))
        p("   minimum level reached:   min=%.2f" % min(all_min))
        p("   moves in 240 steps:      min=%d max=%d mean=%.1f" % (min(all_moves), max(all_moves), sum(all_moves) / len(all_moves)))
        p("   knowledge PRUT minimum:  %.1f (RESOURCE_DEGRADING runway gate is < 120)" % min(all_prut))
        p("   LOW_BATTERY total=%d CRITICAL_BATTERY total=%d RESOURCE_DEGRADING total=%d (runway-driven local=%d)" % (
            sum(i["LOW_BATTERY"] for i in stock_infos.values()), sum(i["CRITICAL_BATTERY"] for i in stock_infos.values()),
            sum(i["RESOURCE_DEGRADING"] for i in stock_infos.values()), sum(i["rd_local_runway"] for i in stock_infos.values())))
        p("   TREND_WORSENING steps total=%d, with mean_battery in context=%d, battery the ONLY worsening item=%d" % (
            sum(i["tw_steps"] for i in stock_infos.values()), sum(i["tw_battery_mentioned"] for i in stock_infos.values()),
            sum(i["tw_battery_only"] for i in stock_infos.values())))
        p("   monitor low events=%d critical=%d | low_battery alerts=%d | safety reasons w/ critical_battery=%d" % (
            sum(i["monitor_low"] for i in stock_infos.values()), sum(i["monitor_crit"] for i in stock_infos.values()),
            sum(i["alerts"] for i in stock_infos.values()), sum(i["reasons_with_battery"] for i in stock_infos.values())))
        ct = Counter()
        for i in stock_infos.values():
            ct.update(i["constraint"]["value_types"])
        p("   constraint filter battery value types seen: %s; non-empty battery reasons=%d" % (
            dict(ct), sum(i["constraint"]["nonempty"] for i in stock_infos.values())))
        p("   utility feasibility: calls=%d battery violations=%d params with battery_level=%d projected=%d" % (
            sum(i["feas"]["calls"] for i in stock_infos.values()), sum(i["feas"]["battery_violations"] for i in stock_infos.values()),
            sum(i["feas"]["params_had_battery_level"] for i in stock_infos.values()), sum(i["feas"]["params_had_projected"] for i in stock_infos.values())))
        fa = Counter()
        for i in stock_infos.values():
            fa.update(i["fs_actions"])
        p("   fail-safe actions chosen (all stock steps): %s" % dict(fa))
        # projection: how many steps to reach the gates at the observed max drain
        mean_drain = (100.0 - sum(all_final) / len(all_final)) / 240.0
        max_drain = (100.0 - min(all_final)) / 240.0
        p("   observed drain/step: mean=%.4f max=%.4f -> steps to LOW(30): mean-rate %d, max-rate %d; to CRIT(15): mean-rate %d, max-rate %d" % (
            mean_drain, max_drain, int(70 / mean_drain), int(70 / max_drain), int(85 / mean_drain), int(85 / max_drain)))
        p()

    # ---------------------------------------------------------------- callers
    p("-" * 100)
    p("2. DIRECT READ/WRITE HOOK TOTALS - stock arm, all 13 runs summed")
    p("-" * 100)
    print_callers("2a. agents.UAV.battery_level", agg_callers(runs, "stock", "agent_attr", "battery_level"))
    print_callers("2b. agents.UAV.battery_status", agg_callers(runs, "stock", "agent_attr", "battery_status"))
    print_callers("2c. UAVResourceRuntimeState.battery_level (knowledge)", agg_callers(runs, "stock", "knowledge_attr", "battery_level"))
    print_callers("2d. UAVResourceRuntimeState.battery_status (knowledge)", agg_callers(runs, "stock", "knowledge_attr", "battery_status"))
    print_callers("2e. UAVExtensionState.battery_level (managed mirror)", agg_callers(runs, "stock", "managed_attr", "battery_level"))

    # ---------------------------------------------------------------- nodrain vs stock
    p("-" * 100)
    p("3. COUNTERFACTUAL - nodrain (battery pinned at 100) vs stock, seed-matched")
    p("-" * 100)
    for c in CANON:
        a = runs.get(("stock",) + c)
        b = runs.get(("nodrain",) + c)
        if a is None or b is None:
            p("run %s: missing arm" % combo(("stock",) + c))
            continue
        first, ndiff, n = first_divergence(a, b)
        fd = a["fire_digests"] == b["fire_digests"]
        ev = {k: v for k, v in a["eval"].items()} == {k: v for k, v in b["eval"].items()}
        ta = Counter(a["rec"]["trigger_type_counts"])
        tb = Counter(b["rec"]["trigger_type_counts"])
        dt = {k: (ta.get(k, 0), tb.get(k, 0)) for k in set(ta) | set(tb) if ta.get(k, 0) != tb.get(k, 0)}
        fsa = [r[2] for r in a["rec"]["failsafe_plan"] if len(r) >= 8]
        fsb = [r[2] for r in b["rec"]["failsafe_plan"] if len(r) >= 8]
        fs_diff = sum(1 for x, y in zip(fsa, fsb) if x != y)
        ova = [bool(s["exec"] and s["exec"]["override"]) for s in a["rec"]["steps"]]
        ovb = [bool(s["exec"] and s["exec"]["override"]) for s in b["rec"]["steps"]]
        ov_diff = sum(1 for x, y in zip(ova, ovb) if x != y)
        ma = [s["fs_mode"] for s in a["rec"]["steps"]]
        mb = [s["fs_mode"] for s in b["rec"]["steps"]]
        mode_diff = sum(1 for x, y in zip(ma, mb) if x != y)
        wa = [s["mgm_phase"] for s in a["rec"]["steps"]]
        wb = [s["mgm_phase"] for s in b["rec"]["steps"]]
        ph_diff = sum(1 for x, y in zip(wa, wb) if x != y)
        p("run %s: UAV positions identical=%s (first divergent step=%s, differing steps=%d/%d) | fire digests identical=%s | eval identical=%s" % (
            combo(("stock",) + c), first is None, first, ndiff, n, fd, ev))
        p("     trigger count deltas (stock, nodrain): %s" % (dt if dt else "none"))
        p("     fail-safe action differs on %d steps | override differs on %d | fs_mode differs on %d | mission phase differs on %d" % (
            fs_diff, ov_diff, mode_diff, ph_diff))
        p("     nodrain TREND_WORSENING=%d (stock %d); nodrain weight_modes=%s" % (
            tb.get("TREND_WORSENING", 0), ta.get("TREND_WORSENING", 0), b["rec"]["weight_modes"]))
    p()

    # ---------------------------------------------------------------- forced arms
    p("-" * 100)
    p("4. FORCED ARMS - low25 / crit12 vs stock, seed-matched: does crossing the gates change behaviour?")
    p("-" * 100)
    for arm in ("low25", "crit12"):
        for c in CANON:
            b = runs.get((arm,) + c)
            if b is None:
                continue
            a = runs.get(("stock",) + c)
            rec = b["rec"]
            steps = rec["steps"]
            tc = rec["trigger_type_counts"]
            first_crit = next((s["step"] for s in steps if "CRITICAL_BATTERY" in s["triggers"]), None)
            first_low = next((s["step"] for s in steps if "LOW_BATTERY" in s["triggers"]), None)
            zero_step = {}
            for st, uid, moved, before, after, status in rec["drain_calls"]:
                if after is not None and after <= 0.0 and uid not in zero_step:
                    zero_step[uid] = st
            holds = Counter()
            holds_stock = Counter()
            for s in steps:
                for row in s["uavs"]:
                    if row[3] == "no_managed_direction_hold":
                        holds[row[0]] += 1
            if a is not None:
                for s in a["rec"]["steps"]:
                    for row in s["uavs"]:
                        if row[3] == "no_managed_direction_hold":
                            holds_stock[row[0]] += 1
            overrides = [s["step"] for s in steps if s["exec"] and s["exec"]["override"]]
            ov_reasons = Counter(s["exec"]["override_reason"] for s in steps if s["exec"] and s["exec"]["override"])
            fs_actions = Counter(r[2] for r in rec["failsafe_plan"] if len(r) >= 8)
            modes = Counter(s["fs_mode"] for s in steps)
            phases = Counter(s["mgm_phase"] for s in steps)
            reasons_b = sum(1 for r in rec["safety_reasons"] if "critical_battery" in r[1])
            uav_reasons = Counter()
            for s in steps:
                if s["exec"]:
                    for uid, (applied, reason, action) in s["exec"]["uav"].items():
                        uav_reasons[(applied, reason)] += 1
            p("%s %s: LOW_BATTERY=%d CRITICAL_BATTERY=%d RESOURCE_DEGRADING=%d TREND_WORSENING=%d | first LOW step=%s first CRIT step=%s | level hits 0 at step: %s" % (
                arm, combo((arm,) + c), tc.get("LOW_BATTERY", 0), tc.get("CRITICAL_BATTERY", 0), tc.get("RESOURCE_DEGRADING", 0),
                tc.get("TREND_WORSENING", 0), first_low, first_crit, dict(zero_step) if zero_step else "never"))
            p("     monitor low=%d crit=%d | alerts=%d | safety reasons w/ critical_battery=%d | fail-safe actions=%s" % (
                sum(1 for r in rec["monitor_events"] if r[1]), sum(1 for r in rec["monitor_events"] if r[2]),
                sum(s["low_battery_alerts"] for s in steps), reasons_b, dict(fs_actions)))
            p("     fs_mode steps=%s | mission phase steps=%s | weight_modes=%s" % (dict(modes), dict(phases), rec["weight_modes"]))
            p("     override active on %d steps %s | per-UAV exec (applied, reason) counts=%s" % (
                len(overrides), dict(ov_reasons) if ov_reasons else "", dict(uav_reasons)))
            p("     holds (no_managed_direction_hold) per UAV: %s vs stock %s" % (dict(holds), dict(holds_stock)))
            p("     constraint battery reasons=%d non-empty=%d | utility battery violations=%d" % (
                rec["constraint_reasons_battery"], rec["constraint_battery"]["nonempty"], rec["utility_feasibility"]["battery_violations"]))
            if a is not None:
                first, ndiff, n = first_divergence(a, b)
                fd = a["fire_digests"] == b["fire_digests"]
                ta = Counter(a["rec"]["trigger_type_counts"])
                dt = {k: (ta.get(k, 0), tc.get(k, 0)) for k in set(ta) | set(tc) if ta.get(k, 0) != tc.get(k, 0)}
                fsa = [r[2] for r in a["rec"]["failsafe_plan"] if len(r) >= 8]
                fsb = [r[2] for r in rec["failsafe_plan"] if len(r) >= 8]
                fs_diff = sum(1 for x, y in zip(fsa, fsb) if x != y)
                ma = [s["fs_mode"] for s in a["rec"]["steps"]]
                mb = [s["fs_mode"] for s in steps]
                mode_diff = [(i + 1, x, y) for i, (x, y) in enumerate(zip(ma, mb)) if x != y]
                p("     vs stock: positions identical=%s (first divergent step=%s, differing steps=%d/%d) | fire digests identical=%s | eval stock: %s | eval %s: %s" % (
                    first is None, first, ndiff, n, fd, fmt_eval(a["eval"]), arm, fmt_eval(b["eval"])))
                p("     vs stock: trigger deltas=%s" % (dt if dt else "none"))
                p("     vs stock: fail-safe action differs on %d steps; fs_mode differs on %d steps (first 6: %s)" % (
                    fs_diff, len(mode_diff), mode_diff[:6]))
                ova = {s["step"] for s in a["rec"]["steps"] if s["exec"] and s["exec"]["override"]}
                p("     vs stock: override steps stock=%d %s=%d; fail-safe action distribution stock=%s" % (
                    len(ova), arm, len(overrides), dict(Counter(fsa))))
            p()

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
