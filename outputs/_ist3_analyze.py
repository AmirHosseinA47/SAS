"""isTrue round Part 3: the identity gates over the frozen identity-run queue.

usage: _ist3_analyze.py --head-b <sha> --head-i <sha> [--partial]

Reads ONLY outputs/_ist3_configs.json and outputs/_ist3_q.jsonl (re-derived from outputs/_ist3_queue.py first: STOP on
any difference), outputs/_ist3_freeze_launch.json (and _complete.json when present), and for each queue line its --out
JSON, the pool's <out>.argv sidecar and <out>.poollog, and the wrapper's <out>.reach.json. --partial reports what
exists and skips missing runs; without it every run must exist.

G-V, PER RUN (provenance and validity; every failure is listed):
  - chain exit 0: JSON present and parseable, complete, crashed None, steps_done == steps; reach record chain_exit 0;
  - repo == the line's checkout; head == --head-b (arm B) or --head-i (F1 / F12 / K); src_sha == the freeze record's
    hash of each file (same checkout); the freeze record shows both trees clean and (when present) launch == complete;
  - extra_params == the line's --set dict (parsed as _sd_probe parses); argv == the line's args after "--"; the .argv
    sidecar == {argv, cwd} of the line;
  - the arm took effect: fb3.eff.searcher_targeting / victim_spawn_mode as asked; every --set key of FIX3B_KEYS equal
    in fb3.switches; every SEARCHER_FP_* --set key equal in fb3.bp_switches (raw and effective) - a dead key fails;
    effective.global_planner_mode as asked (GP); fb3.bp_switches SEARCHER_TARGETING_FIX raw / eff as asked (BF-fix0);
    params' MR1_TRUTHINESS_FIX / NUMPY_SCALAR_FLAGS exactly the arm's own --set (absent elsewhere);
  - CRN on with draws > 0; fb3.inst present with error_count 0 and broken False; mr.errors, ut.errors and the reach
    errors empty; no HOOK_ERR / ERR marker anywhere in mf2 / fx3;
  - mr record: mr1_steps has one row per step, t = 1..steps, one count per UAV in both columns; n_observations set.
GATES, PER CONFIGURATION (full_diff over every recorded field except SKIP; params compared without the arm's own two
switch keys; the pool log compared with wall-clock tokens and checkout paths normalised):
  G-A  B vs F12   every field equal except mr.mr1_list       (the whole round changes only MR1)
  G-B  F1 vs F12  every field equal, mr.mr1_list included    (F-2 changes nothing)
  G-C  B vs F1    every field equal except mr.mr1_list       (F-1 changes only MR1)
  G-K  B vs K     every field equal, mr.mr1_list included    (both kill switches = the pre-fix code)
  G1-a F1, F12    mr.mr1_list == the CORRECTED accumulation (mr1_steps row[2]), bit-equal, outputs/_bp_analyze.py
                  _mr1_acc verbatim
  G1-b B, K       mr.mr1_list == the LITERAL accumulation (row[1]), bit-equal
  MR1-chg         MR1 changed between B and F12 exactly where the corrected and literal per-step counts differ
SKIP (labels and wall-clock only): top-level probe, tag, repo, head, src_sha, argv, extra_params, wall_s, python, mesa,
  _det; fb3.timing, fb3.probe, fb3.inst.overhead, fb3.inst.src.root; mf2 / fx3 / ut / mr .probe.
REACH (record-only, outputs/_ist3_reach.py): numpy-typed values at each F-2 site per arm. In arm B a numpy bool /
  integer / float32 there is the latent F-2 defect actually reached in that configuration.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TOP_SKIP = {"probe", "tag", "repo", "head", "src_sha", "argv", "extra_params", "wall_s", "python", "mesa", "_det"}
SEC_SKIP = {"mf2": {"probe"}, "fx3": {"probe"}, "fb3": {"timing", "probe"}, "ut": {"probe"}, "mr": {"probe"}}
ARM_KEYS = {"MR1_TRUTHINESS_FIX", "NUMPY_SCALAR_FLAGS"}
ERR_RE = re.compile(r"HOOK_ERR|\"ERR[xXH]?\"|\"ERR |'ERR ")
WALL_RE = re.compile(r"wall=\S+")


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _same_path(a, b) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _mr1_acc(n, counts, nobs):
    """outputs/_bp_analyze.py _mr1_acc, verbatim: the model's MR1 accumulation (wildfire_model.MR1)."""
    acc = [0.0] * n
    for cs in counts:
        reward = [((float(c) / nobs) * 1) - 0 for c in cs]
        acc = [a + b for a, b in zip(acc, reward)]
    return acc


def _diff(path, x, y, out, limit=12):
    if len(out) >= limit:
        return
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y), key=str):
            if k not in x or k not in y:
                out.append("%s.%s (in one run only)" % (path, k))
            else:
                _diff("%s.%s" % (path, k), x[k], y[k], out, limit)
    elif isinstance(x, list) and isinstance(y, list):
        if len(x) != len(y):
            out.append("%s (length %d != %d)" % (path, len(x), len(y)))
            return
        for i, (a, b) in enumerate(zip(x, y)):
            if a != b or type(a) is not type(b):
                _diff("%s[%d]" % (path, i), a, b, out, limit)
                if len(out) >= limit:
                    return
    elif x != y or type(x) is not type(y):
        out.append("%s: %s != %s" % (path, repr(x)[:60], repr(y)[:60]))


def full_diff(a: dict, b: dict, skip_mr1_list: bool) -> list[str]:
    out: list[str] = []
    for k in sorted((set(a) | set(b)) - TOP_SKIP, key=str):
        if k not in a or k not in b:
            out.append("%s (in one run only)" % k)
            continue
        if k == "params":
            pa = {x: v for x, v in (a[k] or {}).items() if x not in ARM_KEYS}
            pb = {x: v for x, v in (b[k] or {}).items() if x not in ARM_KEYS}
            _diff("params", pa, pb, out)
        elif k in SEC_SKIP and isinstance(a[k], dict) and isinstance(b[k], dict):
            skip = set(SEC_SKIP[k]) | ({"mr1_list"} if (k == "mr" and skip_mr1_list) else set())
            for s in sorted((set(a[k]) | set(b[k])) - skip, key=str):
                if s not in a[k] or s not in b[k]:
                    out.append("%s.%s (in one run only)" % (k, s))
                elif k == "fb3" and s == "inst" and isinstance(a[k][s], dict) and isinstance(b[k][s], dict):
                    ia = {x: v for x, v in a[k][s].items() if x != "overhead"}
                    ib = {x: v for x, v in b[k][s].items() if x != "overhead"}
                    for side in (ia, ib):
                        if isinstance(side.get("src"), dict):
                            side["src"] = {x: v for x, v in side["src"].items() if x != "root"}
                    _diff("fb3.inst", ia, ib, out)
                else:
                    _diff("%s.%s" % (k, s), a[k][s], b[k][s], out)
        else:
            _diff(k, a[k], b[k], out)
    return out


def _poollog(path: str, repos, tag: str = "") -> list[str]:
    """The pool log (the chain's stdout + stderr) with the run's own tag, wall-clock tokens and checkout paths
    normalised - the parts that differ between arms by construction."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return ["<missing poollog>"]
    out = []
    for ln in lines:
        if tag:
            ln = ln.replace(tag, "<TAG>")
        ln = WALL_RE.sub("wall=<t>", ln)
        for r in repos:
            ln = ln.replace(r, "<REPO>").replace(r.replace("\\", "/"), "<REPO>")
        out.append(ln)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head-b", required=True)
    ap.add_argument("--head-i", required=True)
    ap.add_argument("--partial", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    Q = _load("_ist3_queue", "_ist3_queue.py")
    SD = _load("_sd_probe_pv", "_sd_probe.py")
    FB3 = _load("_fb3_probe_keys", "_fb3_probe.py")
    cfgs = Q.configs()
    q = Q.queue(cfgs)
    with open(os.path.join(HERE, "_ist3_configs.json"), encoding="utf-8") as f:
        frozen = json.load(f)
    with open(os.path.join(HERE, "_ist3_q.jsonl"), encoding="utf-8") as f:
        qfile = [json.loads(ln) for ln in f if ln.strip()]
    if frozen.get("configs") != json.loads(json.dumps(cfgs)) or qfile != json.loads(json.dumps(q)):
        print("STOP: the frozen configuration list / queue differs from _ist3_queue.py")
        return 3
    print("FROZEN LIST OK: %d configurations, %d queue lines, seeds %d-%d"
          % (len(cfgs), len(q), cfgs[0]["seed"], cfgs[-1]["seed"]))

    freeze = json.load(open(os.path.join(HERE, "_ist3_freeze_launch.json"), encoding="utf-8"))
    problems_global = []
    for key in ("B", "I"):
        if freeze[key]["status"]:
            problems_global.append("freeze %s: tree not clean at launch: %r" % (key, freeze[key]["status"]))
    if not freeze["B"]["head"].startswith(args.head_b) or not freeze["I"]["head"].startswith(args.head_i):
        problems_global.append("freeze heads %s / %s != --head-b / --head-i" % (freeze["B"]["head"][:8],
                                                                                freeze["I"]["head"][:8]))
    comp_path = os.path.join(HERE, "_ist3_freeze_complete.json")
    if os.path.exists(comp_path):
        comp = json.load(open(comp_path, encoding="utf-8"))
        a = {k: v for k, v in freeze.items() if k != "phase"}
        b = {k: v for k, v in comp.items() if k != "phase"}
        print("FREEZE launch == complete:", a == b)
        if a != b:
            problems_global.append("freeze broken: launch != complete")
    else:
        print("FREEZE complete record: not yet taken")
    repos = (freeze["B"]["repo"], freeze["I"]["repo"])

    runs: dict[str, dict] = {}
    logs: dict[str, list] = {}
    reach: dict[str, dict] = {}
    bad_v = []
    missing = []
    for ln in q:
        arm = ln["name"].split("_")[1]
        out = ln["out"]
        if not os.path.exists(out):
            missing.append(ln["name"])
            continue
        try:
            with open(out, encoding="utf-8") as f:
                d = json.load(f)
        except Exception as exc:
            bad_v.append("%s: unparseable (%r)" % (ln["name"], exc))
            continue
        probs = []
        after = ln["argv"][ln["argv"].index("--") + 1:]
        sets = {}
        for i, tok in enumerate(after):
            if tok == "--set":
                k, v = after[i + 1].split("=", 1)
                sets[k.strip()] = SD._parse_value(v)
        steps = int(after[after.index("--steps") + 1])
        if not d.get("complete") or d.get("crashed") or d.get("steps_done") != steps:
            probs.append("complete=%s crashed=%s steps_done=%s" % (d.get("complete"), bool(d.get("crashed")),
                                                                   d.get("steps_done")))
        if not _same_path(d.get("repo"), ln["cwd"]):
            probs.append("repo %s != %s" % (d.get("repo"), ln["cwd"]))
        ck = "B" if arm == "B" else "I"
        want_head = args.head_b if arm == "B" else args.head_i
        if not str(d.get("head") or "").startswith(want_head):
            probs.append("head %s != %s" % (d.get("head"), want_head))
        shas = freeze[ck]["sha"]
        for name, h in (d.get("src_sha") or {}).items():
            rel = name.replace("\\", "/")
            if shas.get(rel) != h:
                probs.append("src_sha %s %s != freeze %s" % (rel, h, shas.get(rel)))
        if not d.get("src_sha"):
            probs.append("src_sha missing")
        if d.get("extra_params") != sets:
            probs.append("extra_params %s != %s" % (d.get("extra_params"), sets))
        if d.get("argv") != after:
            probs.append("argv differs from the queue line")
        try:
            sig = json.load(open(out + ".argv", encoding="utf-8"))
            if sig != {"argv": ln["argv"], "cwd": ln["cwd"]}:
                probs.append(".argv sidecar differs")
        except Exception:
            probs.append(".argv sidecar missing")
        fb3 = d.get("fb3") or {}
        eff = fb3.get("eff") or {}
        if eff.get("searcher_targeting") != int(sets.get("SEARCHER_TARGETING", 0)):
            probs.append("eff searcher_targeting %s != %s" % (eff.get("searcher_targeting"),
                                                              sets.get("SEARCHER_TARGETING", 0)))
        if eff.get("victim_spawn_mode") != int(sets.get("VICTIM_SPAWN_MODE", 0)):
            probs.append("eff victim_spawn_mode %s" % eff.get("victim_spawn_mode"))
        for k, v in sets.items():
            if k in FB3.FIX3B_KEYS and (fb3.get("switches") or {}).get(k) != v:
                probs.append("switch %s recorded %s != %s" % (k, (fb3.get("switches") or {}).get(k), v))
            if k.startswith("SEARCHER_FP_"):
                rec = (fb3.get("bp_switches") or {}).get(k) or {}
                if rec.get("raw") != v or rec.get("eff") is None or float(rec["eff"]) != float(v):
                    probs.append("FP %s recorded %s != %s" % (k, rec, v))
        # GP's GLOBAL_PLANNER_MODE and BF-fix0's SEARCHER_TARGETING_FIX are neither FIX3B nor SEARCHER_FP_* keys; their
        # effective values are recorded by the accessor (_sd_probe effective) and in fb3.bp_switches (report review K20)
        gpm_eff = (d.get("effective") or {}).get("global_planner_mode")
        if gpm_eff != int(sets.get("GLOBAL_PLANNER_MODE", 0)):
            probs.append("effective global_planner_mode %s != %s" % (gpm_eff, sets.get("GLOBAL_PLANNER_MODE", 0)))
        stf = (fb3.get("bp_switches") or {}).get("SEARCHER_TARGETING_FIX") or {}
        want_stf = sets.get("SEARCHER_TARGETING_FIX", 1)
        if stf.get("raw") != want_stf or stf.get("eff") is not (want_stf != 0):
            probs.append("SEARCHER_TARGETING_FIX recorded %s != %s" % (stf, want_stf))
        # the arm's own isTrue switches as the run's params record them (absent = the shipped 1 / not in checkout B)
        for k in sorted(ARM_KEYS):
            want_k = {"F1": {"NUMPY_SCALAR_FLAGS": 0}, "K": {"MR1_TRUTHINESS_FIX": 0, "NUMPY_SCALAR_FLAGS": 0}}.get(
                arm, {}).get(k)
            if (d.get("params") or {}).get(k) != want_k:
                probs.append("params %s = %s, the arm sets %s" % (k, (d.get("params") or {}).get(k), want_k))
        crn = fb3.get("crn") or {}
        if not (crn.get("on") and (crn.get("crn_draws") or 0) > 0):
            probs.append("CRN not on with draws > 0: %s" % crn)
        inst = fb3.get("inst")
        if not isinstance(inst, dict) or inst.get("error_count") or inst.get("broken"):
            probs.append("fb3.inst missing / errors %s broken %s" % (
                (inst or {}).get("error_count") if isinstance(inst, dict) else None,
                (inst or {}).get("broken") if isinstance(inst, dict) else None))
        mr = d.get("mr") or {}
        if mr.get("errors"):
            probs.append("mr errors %s" % mr["errors"][:2])
        if (d.get("ut") or {}).get("errors"):
            probs.append("ut errors %s" % d["ut"]["errors"][:2])
        for sec in ("mf2", "fx3"):
            if ERR_RE.search(json.dumps(d.get(sec))):
                probs.append("%s carries an observer error marker" % sec)
        ms = mr.get("mr1_steps")
        n_uav = len(mr.get("mr1_list") or [])
        if not (isinstance(ms, list) and len(ms) == steps and [x[0] for x in ms] == list(range(1, steps + 1))
                and all(len(x[1]) == n_uav and len(x[2]) == n_uav for x in ms) and mr.get("n_observations")
                and n_uav == int((d.get("params") or {}).get("NUM_AGENTS", n_uav))):
            probs.append("mr record malformed (%s rows, %s UAVs)" % (len(ms or []), n_uav))
        try:
            rch = json.load(open(out + ".reach.json", encoding="utf-8"))
            if rch.get("chain_exit") not in (0, None) or rch.get("errors"):
                probs.append("reach exit %s errors %s" % (rch.get("chain_exit"), rch.get("errors")[:2]))
            if rch.get("f2_present") is not (arm != "B"):
                probs.append("reach f2_present %s for arm %s" % (rch.get("f2_present"), arm))
            reach[ln["name"]] = rch
        except Exception as exc:
            probs.append("reach record missing (%r)" % exc)
        if probs:
            bad_v.append("%s: %s" % (ln["name"], "; ".join(probs)))
        runs[ln["name"]] = d
        logs[ln["name"]] = _poollog(out + ".poollog", repos, ln["name"])
    print("RUNS present %d / %d; G-V failures %d; global problems %d" % (len(runs), len(q), len(bad_v),
                                                                        len(problems_global)))
    for b in problems_global + bad_v[:60]:
        print("  G-V FAIL", b)
    if missing and not args.partial:
        print("STOP: %d runs missing (e.g. %s); use --partial for an interim report" % (len(missing), missing[:3]))
        return 3

    gates = {g: [0, 0] for g in ("G-A", "G-B", "G-C", "G-K", "G1-a", "G1-b", "MR1-chg", "LOG")}
    fails, notes = [], []
    lit_after3 = 0
    lit_nonzero_runs = []
    cor_mean = []
    mr1_changed = 0
    mr1_same = []
    for c in cfgs:
        names = {arm: "ist3_%s_%s" % (arm, c["cid"]) for arm in ("B", "F1", "F12", "K")}
        r = {arm: runs.get(n) for arm, n in names.items()}

        def gate(g, ok, why=""):
            gates[g][0 if ok else 1] += 1
            if not ok:
                fails.append("%s %s: %s" % (g, c["cid"], why))

        for arm in ("B", "F1", "F12", "K"):
            d = r[arm]
            if d is None:
                continue
            mr = d["mr"]
            nobs = float(mr["n_observations"])
            ms = mr["mr1_steps"]
            n = len(mr["mr1_list"])
            lit = _mr1_acc(n, [x[1] for x in ms], nobs)
            cor = _mr1_acc(n, [x[2] for x in ms], nobs)
            if arm in ("F1", "F12"):
                gate("G1-a", cor == list(mr["mr1_list"]), "mr1_list != corrected accumulation")
                if arm == "F12":
                    cor_mean.append((int(c["steps"]), sum(cor) / max(1, n)))
            else:
                gate("G1-b", lit == list(mr["mr1_list"]), "mr1_list != literal accumulation")
                lit_after3 += sum(1 for x in ms if x[0] > 3 and any(x[1]))
                nz = sum(1 for x in ms if any(x[1]))
                if nz:
                    lit_nonzero_runs.append("%s_%s:%d" % (arm, c["cid"], nz))
        for g, x, y, skip in (("G-A", "B", "F12", True), ("G-B", "F1", "F12", False), ("G-C", "B", "F1", True),
                              ("G-K", "B", "K", False)):
            if r[x] is None or r[y] is None:
                continue
            dd = full_diff(r[x], r[y], skip_mr1_list=skip)
            gate(g, not dd, "; ".join(dd[:4]))
            lx, ly = logs.get(names[x]), logs.get(names[y])
            gate("LOG", lx == ly, "%s vs %s pool log differs (first: %s)" % (
                x, y, next((p for p in zip(lx or [], ly or []) if p[0] != p[1]), "length")))
            if g == "G-A":
                # MR1 must change exactly when the corrected and literal per-step counts differ on some step (G-A
                # has shown both columns equal between the arms)
                changed = r[x]["mr"]["mr1_list"] != r[y]["mr"]["mr1_list"]
                expect = any(row[1] != row[2] for row in r[y]["mr"]["mr1_steps"])
                gate("MR1-chg", changed == expect, "MR1 changed %s, corrected != literal on some step %s"
                     % (changed, expect))
                if changed:
                    mr1_changed += 1
                else:
                    mr1_same.append("%s (corrected total %d)" % (c["cid"], sum(sum(row[2])
                                                                             for row in r[y]["mr"]["mr1_steps"])))
    print("\nGATES (pass / fail):")
    for g, (p, f) in gates.items():
        print("  %-5s %4d / %d" % (g, p, f))
    print("MR1-chg = MR1 changed between B and F12 exactly where the corrected and literal per-step counts differ")
    print("configurations whose MR1 changed between B and F12: %d / %d; unchanged: %s"
          % (mr1_changed, len(cfgs), mr1_same))
    print("literal MR1 counts after step 3 in B / K runs (expected 0): %d" % lit_after3)
    print("B / K runs with a non-zero literal count (steps 1-3, the seeded cell): %d: %s"
          % (len(lit_nonzero_runs), lit_nonzero_runs))
    for h in sorted({h for h, _v in cor_mean}):
        s = sorted(v for hh, v in cor_mean if hh == h)
        print("corrected M_R1 (mean over UAVs) across the %d F12 runs at %d steps: min %.3f median %.3f max %.3f%s"
              % (len(s), h, s[0], statistics.median(s), s[-1],
                 ("  (all: %s)" % ", ".join("%.3f" % v for v in s)) if len(s) <= 6 else ""))
    for f in fails[:80]:
        print("  FAIL", f)
    for nn in notes[:20]:
        print("  NOTE", nn)

    print("\nREACH (record-only): numpy-typed values at each F-2 site, summed per arm")
    print("  (calls = values seen; maintain = calls of _is_maintain_option, marker values in its numpy column;")
    print("   plain_scalar_converted = numpy inputs it converted; a site never called shows calls 0)")
    per_arm = defaultdict(lambda: defaultdict(Counter))
    calls = defaultdict(Counter)
    numpy_total = Counter()
    for name, rch in reach.items():
        arm = name.split("_")[1]
        rc = rch.get("calls") or {}
        for site in ("fail_safe_planner", "global_mission_planner", "local_uav_path_planner", "rescue_planner"):
            cnt = (rch.get("truthy") or {}).get(site) or {}
            per_arm[arm]["truthy." + site].update({k: v for k, v in cnt.items() if k.startswith("numpy.")})
            calls[arm]["truthy." + site] += sum(cnt.values())
        for key in ("maintain", "safe_float", "plain_scalar", "plain_scalar_converted"):
            cnt = rch.get(key) or {}
            per_arm[arm][key].update({k: v for k, v in cnt.items() if k.startswith("numpy.")})
            if key == "plain_scalar":          # every call (the tally holds numpy inputs only)
                calls[arm][key] += int(rc.get("plain_scalar", 0))
            elif key == "maintain":            # the tally holds marker-key values; the call count is separate
                calls[arm][key] += int(rc.get("_is_maintain_option", 0))
            elif key == "plain_scalar_converted":
                calls[arm][key] += sum(cnt.values())
            else:
                calls[arm][key] += sum(cnt.values())
        calls[arm]["evaluate_option"] += int(rc.get("evaluate_option", 0))
        calls[arm]["runs"] += 1
        for key in ("params", "context"):
            for k2, cnt in (rch.get(key) or {}).items():
                per_arm[arm]["%s.%s" % (key, k2)].update(cnt)
    for arm in ("B", "F1", "F12", "K"):
        if arm not in calls:
            continue
        print("  arm %s:" % arm)
        for site in sorted(set(per_arm[arm]) | set(calls[arm])):
            print("    %-40s calls %9d  numpy %s" % (site, calls[arm].get(site, 0), dict(per_arm[arm].get(site, {}))))
            numpy_total[arm] += sum(per_arm[arm].get(site, {}).values())
    print("numpy-typed values at any F-2 site, any evaluated parameter or context value, per arm: %s"
          % {a: numpy_total[a] for a in ("B", "F1", "F12", "K") if a in calls})
    ok = not bad_v and not problems_global and not any(f for _p, f in gates.values()) and not missing
    print("\nVERDICT:", "ALL GATES PASS" if ok else ("INCOMPLETE" if missing else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
