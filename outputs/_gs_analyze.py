"""Grid-scale round analysis over outputs/_gs_<tag>_*.json produced by _gs_probe.py.

  --validate <tag>      seed-matched identity check of a 50x50 arm against the
                        recorded _ffr_latbase_* arm (eval, fire digest at 240,
                        stdout sha) plus the 50x50 coverage reference
  --arm <tag> [...]     per-checkpoint tables for 100x100 arms
  --raw <tag>           breakage evidence from a run without --expose-dims
  --timeouts a,b,c      never-detected counterfactuals at these timeouts
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
from collections import defaultdict

OUT = os.path.dirname(os.path.abspath(__file__))


DETECTED_STATUSES = ("confirmed", "assigned", "rescued")


def _first_detection(d: dict) -> dict:
    """First step at which each victim reached a status that implies detection.

    Recomputed from victim_transitions: a candidate -> unreachable (write-off) or
    candidate -> dead transition is NOT a detection."""
    out: dict = {}
    for s, vid, st, pos in d.get("victim_transitions", []):
        if vid not in out and str(st) in DETECTED_STATUSES:
            out[vid] = {"step": int(s), "status": str(st)}
    return out


def _load(tag: str) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(os.path.join(OUT, "_gs_%s_*.json" % tag))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as exc:
            print("  !! unreadable %s: %r" % (f, exc))
            continue
        d["_file"] = os.path.basename(f)
        d["first_detection"] = _first_detection(d)
        rows.append(d)
    return rows


def _key(d: dict) -> tuple:
    return (d["wind"], d["roles"], int(d["seed"]))


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def _fmt(x, nd=2):
    if x is None:
        return "-"
    if isinstance(x, float):
        return ("%%.%df" % nd) % x
    return str(x)


def validate(tag: str) -> None:
    rows = _load(tag)
    base = {}
    for f in glob.glob(os.path.join(OUT, "_ffr_latbase_*.json")):
        d = json.load(open(f, encoding="utf-8"))
        base[(d["wind"], d["roles"], int(d["seed"]))] = d
    print("=== VALIDATION of %s (n=%d) against _ffr_latbase (n=%d) ===" % (tag, len(rows), len(base)))
    n_ok = 0
    for d in sorted(rows, key=_key):
        b = base.get(_key(d))
        if b is None:
            print("  %s: no baseline" % (_key(d),))
            continue
        cp240 = next((c for c in d["checkpoint_records"] if c["step"] == 240), None)
        eval_eq = {k: v for k, v in d["eval"].items()} == {k: v for k, v in b["eval"].items()}
        dig_eq = cp240 is not None and cp240["fire_digest"] == b["fire_digests"][239]
        sha_eq = d["stdout_sha256"] == b["stdout_sha256"]
        ok = eval_eq and dig_eq and sha_eq
        n_ok += int(ok)
        ns = d.get("nsb_stats", {})
        print("  %-24s eval=%s digest240=%s stdout=%s nsb_calls=%d verified=%d mismatch=%d wall=%.0fs (ffr %.0fs)" % (
            "%s/%s/%d" % _key(d), eval_eq, dig_eq, sha_eq, ns.get("calls", 0), ns.get("verified", 0),
            ns.get("mismatch", -1), d["wall_s"], b["wall_s"]))
    print("  IDENTICAL: %d/%d" % (n_ok, len(rows)))
    arm_tables([tag], label="50x50 reference")


def arm_tables(tags: list[str], label: str = "", timeouts: list[int] | None = None) -> None:
    for tag in tags:
        rows = _load(tag)
        if not rows:
            print("=== %s: no runs ===" % tag)
            continue
        d0 = rows[0]
        print("\n=== ARM %s %s | grid=%s expose_dims=%s consts=%s | n=%d runs, steps=%d ===" % (
            tag, label, d0["grid"], d0["expose_dims"],
            {k: v["value"] for k, v in d0.get("consts", {}).items()}, len(rows), d0["steps"]))
        steps_all = sorted({c["step"] for d in rows for c in d["checkpoint_records"]})
        print("  %-6s %4s %7s %7s %7s %7s | %6s %6s %6s %6s %6s %6s | %8s %8s | %7s %8s %8s" % (
            "step", "n", "cov_s", "cov_all", "cov_tr", "vis", "resc", "dead", "nd", "ndmark", "geo", "unres",
            "allterm", "med_ts", "burnt", "wall_s", "peakMB"))
        for s in steps_all:
            cps = [(d, c) for d in rows for c in d["checkpoint_records"] if c["step"] == s]
            n = len(cps)
            cov_s = _mean([c["coverage_searcher"] for _, c in cps])
            cov_a = _mean([c["coverage_all"] for _, c in cps])
            cov_t = _mean([c["coverage_tracker"] for _, c in cps])
            vis = _mean([c["visibility_visible_fraction"] for _, c in cps])
            resc = sum(c["eval"]["rescued"] for _, c in cps)
            dead = sum(c["eval"]["dead"] for _, c in cps)
            nd = sum(c["eval"].get("never_detected", 0) for _, c in cps)
            # write-offs are terminal but the victim stays on the grid and can still burn,
            # so the eval's never_detected can DROP later; count the marks themselves
            ndmark = sum(1 for d, _ in cps for m in d.get("unreachable_marks", [])
                         if "never" in str(m.get("reason", "")).lower() and m["step"] <= s)
            geo = sum(c["eval"].get("geographically_isolated", 0) for _, c in cps)
            unres = sum(c["eval"]["candidate"] for _, c in cps)
            allterm = sum(1 for _, c in cps if c["eval"]["all_terminal"])
            med_ts = _med([c["terminal_step"] for _, c in cps if c["terminal_step"] is not None])
            burnt = _mean([c["burnt_fraction"] for _, c in cps])
            wall = _mean([c["wall_s"] for _, c in cps])
            peak = max([(c.get("mem") or {}).get("peak_commit_mb", 0) or 0 for _, c in cps] or [0])
            print("  %-6d %4d %7s %7s %7s %7s | %6d %6d %6d %6d %6d %6d | %5d/%-2d %8s | %7s %8s %8s" % (
                s, n, _fmt(cov_s, 3), _fmt(cov_a, 3), _fmt(cov_t, 3), _fmt(vis, 3), resc, dead, nd, ndmark, geo, unres,
                allterm, n, _fmt(med_ts, 0), _fmt(burnt, 3), _fmt(wall, 0), _fmt(peak, 0)))
        print("  per run:")
        for d in sorted(rows, key=_key):
            parts = []
            for c in d["checkpoint_records"]:
                e = c["eval"]
                parts.append("@%d[s=%.2f a=%.2f r=%d d=%d nd=%d geo=%d cand=%d ts=%s]" % (
                    c["step"], c["coverage_searcher"], c["coverage_all"], e["rescued"], e["dead"],
                    e.get("never_detected", 0), e.get("geographically_isolated", 0), e["candidate"],
                    c["terminal_step"] if c["terminal_step"] is not None else "-"))
            fd = d.get("first_detection", {})
            det = ",".join("%s:%s" % (k.replace("victim_", "v"), v["step"]) for k, v in sorted(fd.items()))
            print("    %-20s ffd=%d wall=%.0fs %s | first_det=%s | nsb_mismatch=%s" % (
                "%s/%s/%d" % _key(d), d["eval"]["firefighter_deaths"], d["wall_s"], " ".join(parts), det,
                d.get("nsb_stats", {}).get("mismatch")))
        # runtime profile
        sw = [d["step_wall"] for d in rows]
        windows = [(1, 240), (241, 500), (501, 960)]
        print("  step wall (s) mean over runs, by window:", end="")
        for lo, hi in windows:
            vals = []
            for w in sw:
                seg = w[lo - 1:hi]
                if seg:
                    vals.append(sum(seg) / len(seg))
            if vals:
                print("  %d-%d: %.1f (max run %.1f)" % (lo, hi, _mean(vals), max(vals)), end="")
        print()
        walls = [d["wall_s"] for d in rows]
        print("  run wall: mean %.0fs median %.0fs max %.0fs (%.1f h max) | peak commit MB max %s" % (
            _mean(walls), _med(walls), max(walls), max(walls) / 3600.0,
            max([(d.get("mem_final") or {}).get("peak_commit_mb", 0) or 0 for d in rows])))
        # battery at checkpoints
        for s in steps_all:
            bats = [u["battery"] for d in rows for c in d["checkpoint_records"] if c["step"] == s for u in c["uavs"].values()]
            if bats:
                print("  battery @%d: min %.1f mean %.1f max %.1f" % (s, min(bats), _mean(bats), max(bats)))
        # never-detected counterfactuals
        if timeouts:
            guillotine(rows, timeouts)


def guillotine(rows: list[dict], timeouts: list[int]) -> None:
    print("  never-detected counterfactual (victims still undetected at step T are written off at T under timeout T):")
    total_v = 0
    undet_at = defaultdict(int)
    detected_after = defaultdict(list)
    for d in rows:
        fd = d.get("first_detection", {})
        vids = set(d["geometry"]["victim_spawns"].keys())
        total_v += len(vids)
        marks = {m["vid"]: m["step"] for m in d.get("unreachable_marks", []) if m["reason"] == "never_detected" or "never_detected" in str(m.get("reason", ""))}
        for vid in vids:
            step = fd.get(vid, {}).get("step")
            for T in timeouts:
                if step is None or step > T:
                    undet_at[T] += 1
                    if step is not None and step > T:
                        detected_after[T].append(step)
    for T in timeouts:
        da = detected_after[T]
        print("    T=%-4d undetected_at_T=%d/%d  of which detected later in THIS arm: %d (steps %s)" % (
            T, undet_at[T], total_v, len(da), sorted(da)[:20]))
    # actual marks in the arm
    marks = [(d["wind"], d["roles"], d["seed"], m["step"], m["vid"]) for d in rows for m in d.get("unreachable_marks", []) if "never" in str(m.get("reason", "")).lower() or m.get("reason") == "never_detected"]
    print("    actual never_detected marks in arm: %d -> %s" % (len(marks), marks[:20]))
    # detection step distribution
    all_det = sorted(v["step"] for d in rows for v in d.get("first_detection", {}).values())
    print("    first-detection steps (all victims, all runs): n=%d median=%s p90=%s max=%s" % (
        len(all_det), _fmt(_med(all_det), 0), all_det[int(0.9 * (len(all_det) - 1))] if all_det else "-", all_det[-1] if all_det else "-"))


def raw(tag: str) -> None:
    rows = _load(tag)
    print("\n=== RAW %s (no --expose-dims): n=%d ===" % (tag, len(rows)))
    for d in sorted(rows, key=_key):
        g = d["geometry"]
        H, W = d["grid"]
        ex = d["exit_starts"]
        off = [e for e in ex if not e["exit_target_on_boundary"]]
        comp = d["completions"]
        comp_off = [c for c in comp if not c["pos_on_boundary"]]
        print("  %s/%s/%d: model_has_HEIGHT=%s getattr(model,HEIGHT,50)=%s lag_grid_bounds=%s mesa_grid=%s" % (
            d["wind"], d["roles"], d["seed"], g["model_has_HEIGHT_attr"], g["getattr_model_HEIGHT_default50"],
            g["lag_grid_bounds"], g["mesa_grid_w_h"]))
        print("    exit_starts=%d off-boundary exit targets=%d %s" % (len(ex), len(off), [(e["step"], e["ff"], e["ff_pos"], e["exit_target"]) for e in off][:8]))
        print("    completions=%d off-boundary completions=%d %s" % (len(comp), len(comp_off), [(c["step"], c["ff"], c["pos"]) for c in comp_off][:8]))
        roles = {}
        for row in d["uav_steps"]:
            for uid, x, y, role in row:
                roles[uid] = role
        print("    UAV extents [min_x,max_x,min_y,max_y] on %dx%d: %s" % (H, W, {("%s(%s)" % (u, roles.get(u, "")[:8])): v for u, v in d["uav_extent"].items()}))
        for c in d["checkpoint_records"]:
            e = c["eval"]
            print("    @%d cov_s=%.3f cov_all=%.3f resc=%d dead=%d nd=%d cand=%d burnt=%.3f wall=%.0fs" % (
                c["step"], c["coverage_searcher"], c["coverage_all"], e["rescued"], e["dead"], e.get("never_detected", 0), e["candidate"], c["burnt_fraction"], c["wall_s"]))


def compare(tag_a: str, tag_b: str) -> None:
    """Seed-matched comparison: identical run? first step where UAV trajectories differ."""
    a = {_key(d): d for d in _load(tag_a)}
    b = {_key(d): d for d in _load(tag_b)}
    print("\n=== COMPARE %s vs %s (seed-matched) ===" % (tag_a, tag_b))
    n_same = 0
    for k in sorted(set(a) & set(b)):
        da, db = a[k], b[k]
        ua, ub = da["uav_steps"], db["uav_steps"]
        div = None
        for i, (ra, rb) in enumerate(zip(ua, ub)):
            if ra != rb:
                div = i
                break
        da_d = {c["step"]: c["fire_digest"] for c in da["checkpoint_records"]}
        db_d = {c["step"]: c["fire_digest"] for c in db["checkpoint_records"]}
        common = sorted(set(da_d) & set(db_d))
        fa = [da_d[s] for s in common]
        fb = [db_d[s] for s in common]
        same_len = da["steps"] == db["steps"]
        same = div is None and fa == fb and (da["stdout_sha256"] == db["stdout_sha256"] if same_len else True)
        n_same += int(same)
        ea = [(c["step"], c["eval"]["rescued"], c["eval"]["dead"], c["eval"].get("never_detected", 0), c["coverage_searcher"]) for c in da["checkpoint_records"]]
        eb = [(c["step"], c["eval"]["rescued"], c["eval"]["dead"], c["eval"].get("never_detected", 0), c["coverage_searcher"]) for c in db["checkpoint_records"]]
        print("  %-20s identical=%s uav_first_divergence_step=%s fire_digests_equal=%s stdout_equal=%s" % (
            "%s/%s/%d" % k, same, div, fa == fb, da["stdout_sha256"] == db["stdout_sha256"]))
        if not same:
            print("      %s: %s" % (tag_a, ea))
            print("      %s: %s" % (tag_b, eb))
    print("  identical runs: %d/%d" % (n_same, len(set(a) & set(b))))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", default=None)
    ap.add_argument("--arm", action="append", default=[])
    ap.add_argument("--raw", action="append", default=[])
    ap.add_argument("--compare", nargs=2, action="append", default=[], metavar=("TAG_A", "TAG_B"))
    ap.add_argument("--timeouts", default="210,470,930")
    args = ap.parse_args()
    timeouts = [int(t) for t in args.timeouts.split(",") if t.strip()]
    if args.validate:
        validate(args.validate)
    if args.arm:
        arm_tables(args.arm, timeouts=timeouts)
    for t in args.raw:
        raw(t)
    for ta, tb in args.compare:
        compare(ta, tb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
