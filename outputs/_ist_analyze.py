"""isTrue round Part 1: read the census files and the static site list, print the per-site verdict inputs.

usage: _ist_analyze.py [--census <glob>] [--sites outputs/_ist_sites.json]

Reads ONLY files matching the non-recursive glob (default outputs/_ist_*_census.json) and the site list written by
_ist_sites.py. STOPS (exit 3) on any run with harness_exit != 0, steps_seen != --steps (default 360) or a recorded observer error.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def is_numpy(catname: str) -> bool:
    return catname.startswith("numpy.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", default=os.path.join(HERE, "_ist_*_census.json"))
    ap.add_argument("--sites", default=os.path.join(HERE, "_ist_sites.json"))
    ap.add_argument("--steps", type=int, default=360)
    args = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    paths = sorted(glob.glob(args.census))
    if not paths:
        print("NO CENSUS FILES")
        return 3
    with open(args.sites, encoding="utf-8") as f:
        sites = json.load(f)
    read_keys: dict[str, set] = defaultdict(set)
    for rel, by in sites["helper_keys"].items():
        for fname, keys in by.items():
            for k in keys:
                read_keys[k].add("%s %s" % (os.path.basename(rel), fname))
    for k in ("do_nothing", "stability_control", "maintain_current_config"):
        read_keys[k].add("planner_selection.py _is_maintain_option")
    for k in ("hard_collision_violation", "route_feasible", "requires_critical_communication", "fail_safe_mode"):
        read_keys[k].add("utility_evaluation.py _check_utility_feasibility (literal)")
    for k in ("feasible", "infeasible"):
        read_keys[k].add("constraint_filter.py _feasibility_reasons (literal)")

    runs = []
    bad = 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        name = os.path.basename(p)[len("_ist_"):-len("_census.json")]
        ok = d.get("harness_exit") == 0 and d.get("steps_seen") == args.steps and not d.get("errors")
        bad += 0 if ok else 1
        runs.append((name, d, ok))

    print("RUNS (%d)" % len(runs))
    for name, d, ok in runs:
        log = os.path.join(HERE, "_ist_%s.log" % name)
        tail = ""
        if os.path.exists(log):
            with open(log, encoding="utf-8", errors="replace") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            tail = lines[-1] if lines else ""
        print("  %-16s %s exit=%s steps=%s wall=%ss head=%s errors=%d" % (
            name, "OK " if ok else "BAD", d.get("harness_exit"), d.get("steps_seen"), d.get("wall_s"),
            (d.get("head") or "")[:8], len(d.get("errors") or [])))
        print("      harness: %s" % tail)
        for e in (d.get("errors") or [])[:5]:
            print("      ERROR %s" % e)
    if bad:
        print("STOP: %d run(s) incomplete or with observer errors" % bad)
        return 3

    print("\nSITES (category counts summed over runs; numpy categories marked <<<)")
    merged: dict[str, Counter] = defaultdict(Counter)
    for _n, d, _ok in runs:
        for site, c in d["sites"].items():
            merged[site].update(c)
    for site in sorted(merged):
        c = merged[site]
        flag = " <<<" if any(is_numpy(k) for k in c) else ""
        print("  %-58s %s%s" % (site, dict(sorted(c.items())), flag))

    print("\nMR1 (agents.py:422) per run: the model's sum (literal `is True`) vs truthiness, over all UAV calls")
    for name, d, _ok in runs:
        ms = d["mr1_steps"]
        lit = sum(x[1] for x in ms)
        cor = sum(x[2] for x in ms)
        lit_nz = [x[0] for x in ms if x[1]]
        cor_nz = sum(1 for x in ms if x[2])
        fs = d["fire_steps"]
        first_np = next((x[0] for x in fs if x[1] != x[2]), None)
        last_py = max((x[0] for x in fs if x[2]), default=None)
        print("  %-16s literal total %6d (steps with literal > 0: %s) | truthy total %7d on %3d / %d steps | "
              "fire: first step with a non-Python-True burning cell %s, last step with any Python-True burning cell %s"
              % (name, lit, lit_nz[:5] if lit_nz else "none", cor, cor_nz, len(ms), first_np, last_py))

    print("\nNUMPY-TYPED VALUES IN OPTION PARAMETERS / CONTEXT (any key, any run) and whether an identity helper reads the key")
    for label, field in (("option.parameters (scored)", "keys_option_parameters_scored"),
                         ("option.parameters (generated, at the constraint filter)", "keys_option_parameters_generated"),
                         ("context (scored)", "keys_context_scored")):
        keys: dict[str, Counter] = defaultdict(Counter)
        for _n, d, _ok in runs:
            for k, c in d[field].items():
                keys[k].update(c)
        np_keys = {k: c for k, c in keys.items() if any(is_numpy(x) for x in c)}
        print("  %s: %d distinct keys, %d with a numpy value" % (label, len(keys), len(np_keys)))
        for k in sorted(np_keys):
            readers = sorted(read_keys.get(k, ()))
            print("    %-36s %s  read by identity helper: %s" % (k, {x: n for x, n in sorted(np_keys[k].items()) if is_numpy(x)},
                                                               readers or "NO"))
        read_present = sorted(k for k in keys if k in read_keys)
        print("    keys read by an identity helper that occur at all: %s" % (
            ", ".join("%s %s" % (k, dict(sorted(keys[k].items()))) for k in read_present) or "none"))

    print("\nsafe_float: values that are not None/bool/int/float/str (they return the DEFAULT), by caller and category")
    fell: Counter = Counter()
    calls = 0
    for _n, d, _ok in runs:
        fell.update(d["safe_float_fell_to_default"])
        calls += d["safe_float_calls"]
    print("  calls %d, fell to default %d" % (calls, sum(fell.values())))
    for k, n in sorted(fell.items(), key=lambda kv: -kv[1]):
        print("    %-60s %d%s" % (k, n, " <<<" if "numpy." in k else ""))

    print("\nKEY SETS seen at the analyzer sites (first run)")
    for where, sets in runs[0][1]["keysets"].items():
        for ks in sets:
            print("  %-36s %s" % (where, ks))

    print("\nCALLS (summed)")
    calls_c: Counter = Counter()
    for _n, d, _ok in runs:
        calls_c.update(d["calls"])
    for k, n in sorted(calls_c.items()):
        print("  %-48s %d" % (k, n))
    print("  WildFireModel._has_pending_execution_directions: %d" % calls_c.get(
        "WildFireModel._has_pending_execution_directions", 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
