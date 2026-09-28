"""Planner round, Part 3: the analyzer. Read-only over outputs/_ffr_pl*.json, their .plobs.json
sidecars and the rbgate shards. No simulation. Pre-registration: outputs/planner_part1.txt
section 7 (with the maintainer's rulings, section 11, and those of 2026-09-28).

usage: python outputs/_pl_analyze.py <section> [...]   (prints; --out FILE also writes the text)
  id      7.1 (a)-(g)  switch-off identity (plB/plD on the pinned dfbfbe7 worktree)
  plq     the plQ tuple (7 ARMS: the first plZ tuple where plG applied >= 1 switch, else ...)
  c13     P2, P3, P4 and PURITY on C13 (no P1/P5 verdict on 13 runs)
  gate    7.2 in full on C13 + N30 (43 runs): PURITY, P1-P5, CHURN
  cmp     7.3 plC vs plG (C13, N30, pooled; RB7 separately) + the CRN pair plKC / plKG
  safety  7.5 (a)-(g)
  local   finding 11A (b): LOCAL path-planner selections decided by precedence vs by score
  gap     finding 11A (a): steps with no available searcher / tracker / fleet, per run
  ref     7.4 plF and plS against plC on N30
Every run is refused unless its JSON repo is its arm's checkout (the two-checkout hazard).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import statistics
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.normcase(os.path.abspath("E:/Projects/SAS"))
BASE = os.path.normcase(os.path.abspath("E:/Projects/SAS_wt/basedfbfbe7"))
BASE_OUT = os.path.join("E:/Projects/SAS_wt/basedfbfbe7", "outputs")
BASELINE_ID = "global_stability_maintain_current_config"
FT, VS = "fire_tracker", "victim_searcher"
NINE = ("fire_contribution", "victim_contribution", "communication_contribution", "uncertainty_reduction",
        "information_recovery", "collision_risk", "battery_cost", "drift_risk", "switching_cost")
EXPECTED_MOVERS = ("fire_contribution", "victim_contribution", "uncertainty_reduction", "information_recovery",
                   "collision_risk", "battery_cost", "switching_cost")
C13 = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("east", "default", s) for s in (101, 202, 303)])
RB7 = [("east", "half", s) for s in (111, 222, 333, 444, 606, 808, 909)]
ZTUPLES = [("east", "half", 101), ("south", "half", 101), ("east", "default", 101)]
DTUPLES = [("east", "half", 101), ("south", "half", 101)]
RB_SHARDS = {"a": ("east", "101,202,303,404,505"), "b": ("east", "606,707,808,909"),
             "c": ("east", "111,222,333,444"), "s": ("south", "101,202,303,404,505")}
RB_KNOWN = {("east", 707), ("south", 101), ("south", 202), ("south", 404)}
ARM_REPO = {"plB": BASE, "plD": BASE, "plRB": BASE}
OUT_LINES: list = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT_LINES.append(s)
    print(s)


def rr(roles):
    return "def" if roles == "default" else roles


def tl(t):
    return "%s/%s/%s" % t


def n30():
    sys.path.insert(0, HERE)
    import _pl_queue
    return _pl_queue.n30()


_CACHE: dict = {}


def load(tag, t, side=False, must=True):
    w, r, s = t
    path = os.path.join(HERE, "_ffr_%s_%s_%s_%s.%s" % (tag, w, rr(r), s, "plobs.json" if side else "json"))
    key = path
    if key in _CACHE:
        return _CACHE[key]
    if not os.path.exists(path):
        if must:
            raise SystemExit("MISSING %s" % path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    want = ARM_REPO.get(tag, MAIN)
    if os.path.normcase(os.path.abspath(d.get("repo", ""))) != want:
        raise SystemExit("REFUSED %s: repo %r is not the arm's %r" % (path, d.get("repo"), want))
    if side:
        with open(path[: -len(".plobs.json")] + ".json", "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != d.get("json_sha256"):
                raise SystemExit("REFUSED %s: json_sha256 does not match its JSON" % path)
    _CACHE[key] = d
    return d


def exists(tag, t):
    w, r, s = t
    return os.path.exists(os.path.join(HERE, "_ffr_%s_%s_%s_%s.json" % (tag, w, rr(r), s)))


def diff_keys(a, b, ignore):
    """Keys (top level) whose presence or value differs, ignoring `ignore`."""
    ka, kb = set(a) - set(ignore), set(b) - set(ignore)
    out = sorted(ka ^ kb)
    for k in sorted(ka & kb):
        if a[k] != b[k]:
            out.append(k)
    return out


def first_div(a, b, key):
    sa, sb = a.get(key) or [], b.get(key) or []
    for i in range(min(len(sa), len(sb))):
        if sa[i] != sb[i]:
            return i + 1
    return None if len(sa) == len(sb) else min(len(sa), len(sb)) + 1


def uav_steps_no_role(d):
    return [[[u[0], u[1]] + list(u[3:]) for u in row] for row in d.get("uav_steps") or []]


def behavioural_div(a, b):
    """P4: first step at which uav_steps with field 2 (the role) EXCLUDED, fire_digests, ff_steps
    or victim_steps differ; with the series that differs first."""
    best = None
    ua, ub = uav_steps_no_role(a), uav_steps_no_role(b)
    for name, sa, sb in (("uav_steps-role", ua, ub), ("fire_digests", a["fire_digests"], b["fire_digests"]),
                         ("ff_steps", a["ff_steps"], b["ff_steps"]), ("victim_steps", a["victim_steps"], b["victim_steps"])):
        for i in range(min(len(sa), len(sb))):
            if sa[i] != sb[i]:
                if best is None or i + 1 < best[0]:
                    best = (i + 1, name)
                break
    return best


def role_changes(d):
    """[(step, uid, old, new)] from uav_steps field 2 (step t = row t-1; the change is at the
    first row that shows the new role)."""
    out, prev = [], {}
    for i, row in enumerate(d.get("uav_steps") or []):
        for u in row:
            if u[0] in prev and prev[u[0]] != u[2]:
                out.append((i + 1, u[0], prev[u[0]], u[2]))
            prev[u[0]] = u[2]
    return out


# ================================================================== 7.1 identity ==
def sec_id(a):
    say("=" * 90)
    say("7.1 SWITCH OFF IS VALUE-IDENTICAL (gate, first)")
    say("=" * 90)
    res = {}
    ign = ("tag", "repo", "wall_s")
    ign_p = ign + ("params", "extra_params")
    # (a)
    bad = []
    for t in C13:
        b, c = load("plB", t), load("plC", t)
        dk = diff_keys(b, c, ign)
        if dk:
            bad.append((tl(t), dk[:8]))
    res["a"] = not bad
    say("(a) plB (dfbfbe7 worktree) vs plC (branch, mode 0), C13, every key but %s: %d/13 equal  %s"
        % (list(ign), 13 - len(bad), "PASS" if not bad else "FAIL"))
    for x in bad:
        say("      DIFFERS %s %s" % x)
    # (b)
    rows = []
    ok = True
    for t in C13:
        s = load("plC", t, side=True)
        acc = s["accessor"]
        calls = s.get("calls") or {}
        mode1 = sum(v for k, v in calls.items())
        special = sum(r[3] for r in s["census"])
        writes = sum(1 for e in s["exec"] if e.get("applied"))
        hooks = len(s["hooks"])
        good = (acc["values"] == {"0": acc["calls"]} and acc["calls"] == 360 and mode1 == 0 and special == 0
                and writes == 0 and hooks == 0)
        sb = load("plB", t, side=True)
        census_eq = [r[:3] for r in s["census"]] == [r[:3] for r in sb["census"]]
        b_absent = sb["accessor"]["values"] == {"'ABSENT'": sb["accessor"]["calls"]}
        good = good and census_eq and b_absent
        ok = ok and good
        rows.append("      %-18s accessor %s (%d calls) mode-1/value calls %d  options w/ nine|target %d  role writes %d"
                    "  hooks %d  census==plB %s  plB accessor %s  %s"
                    % (tl(t), acc["values"], acc["calls"], mode1, special, writes, hooks, census_eq,
                       sb["accessor"]["values"], "ok" if good else "MISS"))
    res["b"] = ok
    say("(b) plC sidecar at mode 0: accessor 0 on every generator call, 0 mode-1 builder / value-function calls,")
    say("    0 global options carrying any of the nine keys or target_uav_id, per-step census of option ids and")
    say("    parameter-key sets == plB's, 0 GlobalExecutor role writes, 0 hook calls; plB accessor ABSENT:  %s"
        % ("PASS" if ok else "FAIL"))
    for r in rows:
        say(r)
    # (c)
    bad = []
    for t in ZTUPLES:
        dk = diff_keys(load("plZ", t), load("plB", t), ign_p)
        if dk:
            bad.append((tl(t), dk[:8]))
    res["c"] = not bad
    say("(c) plZ (--set GLOBAL_PLANNER_MODE=0) == plB, 3 tuples, all keys but %s: %d/3  %s"
        % (list(ign_p), 3 - len(bad), "PASS" if not bad else "FAIL"))
    for x in bad:
        say("      DIFFERS %s %s" % x)
    # (d)
    bad = []
    for t in DTUPLES:
        dk = diff_keys(load("plD", t), load("plB", t), ign)
        if dk:
            bad.append((tl(t), dk[:8]))
    res["d"] = not bad
    say("(d) plD == plB (same code, fresh process), 2 tuples, all keys but %s: %d/2  %s"
        % (list(ign), 2 - len(bad), "PASS" if not bad else "FAIL"))
    for x in bad:
        say("      DIFFERS %s %s" % x)
    # (e)
    t = ("east", "half", 101)
    dk = diff_keys(load("plP", t), load("plC", t), ign)
    res["e"] = not dk
    say("(e) plP (no sidecar) == plC (sidecar), east/half/101, all keys but %s: %s  %s"
        % (list(ign), "equal" if not dk else dk[:8], "PASS" if not dk else "FAIL"))
    # (f)
    bad = []
    for t in C13:
        sc, sb = load("plC", t, side=True), load("plB", t, side=True)
        fields = ("t", "mode", "scored", "sel", "cat", "base", "margin", "tie", "ua", "decision_sel", "nine", "cf")
        pc = [{k: r.get(k) for k in fields} for r in sc["plan"]]
        pb = [{k: r.get(k) for k in fields} for r in sb["plan"]]
        ec = [(e["t"], e["applied"], e["decision"]) for e in sc["exec"]]
        eb = [(e["t"], e["applied"], e["decision"]) for e in sb["exec"]]
        if pc != pb or ec != eb or len(pc) != 360:
            first = next((i for i in range(min(len(pc), len(pb))) if pc[i] != pb[i]), None)
            bad.append((tl(t), len(pc), len(pb), first, ec == eb))
    res["f"] = not bad
    say("(f) the sidecar's planner records plC == plB on C13 (per step: mode, every scored id with score and")
    say("    feasibility, selected id and category, baseline score, margin, tie flag, uav_assignments, the P5")
    say("    null re-selection; executor applied roles): %d/13  %s" % (13 - len(bad), "PASS" if not bad else "FAIL"))
    for x in bad:
        say("      DIFFERS %s rows %d/%d first differing row %s exec equal %s" % x)
    # (g)
    bad = []
    for t in ZTUPLES:
        dk = diff_keys(load("plJ", t), load("plB", t), ign_p)
        s = load("plJ", t, side=True)
        acc_ok = s["accessor"]["values"] == {"0": s["accessor"]["calls"]} and s["accessor"]["calls"] == 360
        m1 = (s.get("calls") or {}).get("mode1_builder", 0)
        if dk or not acc_ok or m1:
            bad.append((tl(t), dk[:8], s["accessor"]["values"], m1))
    res["g"] = not bad
    say("(g) plJ (--set GLOBAL_PLANNER_MODE=0.5, junk -> OFF, D-1) == plB, all keys but %s; its sidecar reads"
        % (list(ign_p),))
    say("    accessor 0 on every generator call with 0 mode-1 builder calls: %d/3  %s"
        % (3 - len(bad), "PASS" if not bad else "FAIL"))
    for x in bad:
        say("      MISS %s diff %s accessor %s builder %s" % x)
    verdict = all(res.values())
    say("7.1 VERDICT: %s  (%s)" % ("PASS" if verdict else "FAIL - STOP THE ROUND",
                                    " ".join("%s=%s" % (k, "ok" if v else "FAIL") for k, v in sorted(res.items()))))
    return verdict


# ====================================================================== plQ =========
def applied_switches(side):
    return [e for e in side["exec"] if e.get("applied")]


def sec_plq(a):
    for t in ZTUPLES:
        if exists("plG", t) and applied_switches(load("plG", t, side=True)):
            say("plQ tuple: %s (the first plZ tuple where plG applied >= 1 switch)" % tl(t))
            return t
    for t in C13:
        if exists("plG", t) and applied_switches(load("plG", t, side=True)):
            say("plQ tuple: %s (no plZ tuple applied a switch; the first C13 tuple with one)" % tl(t))
            return t
    say("plQ: no C13 run applied a switch - fall back to the first N30 tuple with one, after the N30 wave")
    return None


# ====================================================================== 7.2 =========
_WEIGHT_KEY = {"fire_contribution": "fire_weight", "victim_contribution": "victim_weight",
               "communication_contribution": "communication_weight",
               "uncertainty_reduction": "uncertainty_reduction_weight",
               "information_recovery": "information_recovery_weight", "collision_risk": "collision_risk_weight",
               "battery_cost": "battery_cost_weight", "drift_risk": "drift_risk_weight",
               "switching_cost": "switching_cost_weight"}


def _profile(mode):
    if "E:/Projects/SAS" not in sys.path:
        sys.path.insert(0, "E:/Projects/SAS")
    from src_extension.planning.utility_evaluation import get_weight_profile
    return get_weight_profile(mode)


def switch_rows(side):
    return [r for r in side["plan"] if r["cat"] == "SWITCH"]


def p2_p3(tag, tuples):
    """P2 and P3 over every SWITCH selection of the arm on `tuples`."""
    n = p2 = p3 = skipped = 0
    misses = []
    for t in tuples:
        s = load(tag, t, side=True)
        ex = {e["t"]: e for e in s["exec"]}
        end = {row[0]: row[1] for row in s["roles_end"]}
        skips = set(s["dispatch_skips"])
        for r in switch_rows(s):
            n += 1
            sp = r["sel_params"]
            if r["ua"] == {sp["target"]: sp["to"]}:
                p2 += 1
            else:
                misses.append(("P2", tl(t), r["t"], r["ua"], sp))
            e = ex.get(r["t"])
            u = sp["target"]
            ok = (e is not None and e["pre"].get(u) == [sp["frm"] if "frm" in sp else sp["from"]] * 2
                  and e["post"].get(u) == [sp["to"]] * 2 and end.get(r["t"], {}).get(u) == [sp["to"]] * 2)
            if ok:
                p3 += 1
            elif r["t"] in skips:
                skipped += 1
                misses.append(("P3-skip", tl(t), r["t"]))
            else:
                misses.append(("P3", tl(t), r["t"], e and e["pre"].get(u), e and e["post"].get(u),
                               end.get(r["t"], {}).get(u)))
    return n, p2, p3, skipped, misses


def first_applied(side):
    for e in side["exec"]:
        if e.get("applied") and e["pre"] != e["post"]:
            return e["t"]
    return None


def p4(tuples, ctl="plC", arm="plG", verbose=True):
    ign = ("tag", "repo", "wall_s", "params", "extra_params")
    a_ok = b_ok = True
    chains = []
    rows = []
    for t in tuples:
        g, c = load(arm, t), load(ctl, t)
        s = load(arm, t, side=True)
        fa = first_applied(s)
        if fa is None:
            dk = diff_keys(g, c, ign)
            if dk:
                a_ok = False
            rows.append("      %-24s no applied role change: identical to %s %s" % (tl(t), ctl, "YES" if not dk else "NO %s" % dk[:6]))
            continue
        bd = behavioural_div(g, c)
        if bd is not None and bd[0] < fa:
            b_ok = False
        rows.append("      %-24s first applied change step %-4s first behavioural divergence %s %s"
                    % (tl(t), fa, bd, "ok" if (bd is None or bd[0] >= fa) else "BEFORE THE CHANGE - FAIL"))
        if bd is not None:
            chains.append((t, fa, bd))
    if verbose:
        for r in rows:
            say(r)
    return a_ok, b_ok, chains


def fate_steps(d):
    """victim -> (first step with a terminal status, status) from victim_steps."""
    out = {}
    for i, row in enumerate(d.get("victim_steps") or []):
        for v in row:
            vid, st = v[0], str(v[2])
            if vid not in out and st in ("rescued", "dead", "unreachable"):
                out[vid] = (i + 1, st)
    return out


def chain_text(t, fa, bd, ctl="plC", arm="plG"):
    s = load(arm, t, side=True)
    row = next(r for r in s["plan"] if r["t"] == fa and r["cat"] == "SWITCH")
    vals = row["nine"][row["sel"]]
    g, c = load(arm, t), load(ctl, t)
    fg, fc = fate_steps(g), fate_steps(c)
    fates = []
    for vid in sorted(set(fg) | set(fc)):
        if fg.get(vid, (None, "unresolved"))[1] != fc.get(vid, (None, "unresolved"))[1]:
            fates.append("%s %s(step %s) -> %s(step %s)" % (vid, fc.get(vid, (None, "unresolved"))[1],
                                                            fc.get(vid, (None,))[0], fg.get(vid, (None, "unresolved"))[1],
                                                            fg.get(vid, (None,))[0]))
    lines = ["      %s: DECISION step %d %s margin %+.4f over the baseline (%.4f), mode %s" % (
        tl(t), fa, row["sel"], row["margin"], row["base"], row["mode"]),
        "        nine: " + ", ".join("%s=%.4f" % (k, vals[k]) for k in NINE),
        "        -> first behavioural divergence step %d in %s" % bd,
        "        -> eval %s: rescued %s -> %s, dead %s -> %s, ff_deaths %s -> %s; fates: %s" % (
            ctl + "->" + arm, c["eval"]["rescued"], g["eval"]["rescued"], c["eval"]["dead"], g["eval"]["dead"],
            c["eval"]["firefighter_deaths"], g["eval"]["firefighter_deaths"], "; ".join(fates) or "none differ")]
    return lines


def purity():
    t = None
    for path in sorted(os.listdir(HERE)):
        m = re.match(r"^_ffr_plQ_(\w+)_(half|def)_(\d+)\.json$", path)
        if m:
            t = (m.group(1), "default" if m.group(2) == "def" else "half", int(m.group(3)))
    if t is None:
        return None, None
    dk = diff_keys(load("plQ", t), load("plG", t), ("tag", "repo", "wall_s"))
    return t, dk


def sec_c13(a):
    say("=" * 90)
    say("7.2 on C13 ONLY: PURITY, P2, P3, P4 (no P1 / P5 verdict on 13 runs)")
    say("=" * 90)
    t, dk = purity()
    say("PURITY plQ == plG on %s, all keys but tag/repo/wall_s: %s" % (t and tl(t), "NOT RUN" if t is None else (
        "PASS" if not dk else "FAIL %s" % dk[:8])))
    n, c2, c3, sk, miss = p2_p3("plG", C13)
    say("P2 REACHES: %d/%d SWITCH selections carry uav_assignments == {target: to_role}  %s" % (c2, n, "PASS" if c2 == n else "FAIL"))
    say("P3 ACTS: %d/%d both role stores from_role -> to_role in the step and still to_role at its end; skipped %d  %s"
        % (c3, n, sk, "PASS" if c3 + sk == n else "FAIL"))
    for m in miss[:20]:
        say("      MISS %s" % (m,))
    say("P4 THE DIFFERENCE IS THE PLANNER'S (plG vs plC, C13):")
    a_ok, b_ok, chains = p4(C13)
    say("  (a) %s  (b) %s  (c) named chains: %d" % ("PASS" if a_ok else "FAIL", "PASS" if b_ok else "FAIL", len(chains)))
    for t, fa, bd in chains[:2]:
        for ln in chain_text(t, fa, bd):
            say(ln)
    return (t is None or not dk) and c2 == n and c3 + sk == n and a_ok and b_ok and bool(chains)


def sec_gate(a):
    tuples = C13 + n30()
    say("=" * 90)
    say("7.2 THE PLANNER DECIDES - the primary gate, plG on C13 + N30 (%d runs; RB7 reported separately)" % len(tuples))
    say("=" * 90)
    t, dk = purity()
    pur = t is not None and not dk
    say("PURITY plQ == plG on %s, all keys but tag/repo/wall_s: %s" % (t and tl(t), "NOT RUN - VOID" if t is None else (
        "PASS" if not dk else "FAIL (7.2 void) %s" % dk[:8])))
    # P1
    per_run = []
    tot = collections.Counter()
    for tt in tuples:
        s = load("plG", tt, side=True)
        cats = collections.Counter(r["cat"] for r in s["plan"])
        per_run.append((tt, cats, len(s["plan"])))
        tot.update(cats)
    steps = sum(n for _, _, n in per_run)
    runs_sw = sum(1 for _, c, _ in per_run if c["SWITCH"] > 0)
    share = tot["SWITCH"] / max(1, steps)
    p1 = runs_sw >= 15 and tot["SWITCH"] > 0
    say("P1 SELECTS: planner steps %d; SWITCH %d (%.2f%%), OTHER %d, BASELINE %d; runs with >= 1 SWITCH %d/%d "
        "(required >= 15, and share > 0)  %s" % (steps, tot["SWITCH"], 100 * share, tot["OTHER"], tot["BASELINE"],
                                                   runs_sw, len(tuples), "PASS" if p1 else "FAIL"))
    say("   OTHER selected: %d (expected 0; > 0 is a STOP item)" % tot["OTHER"])
    say("   closed-loop SWITCH share %.2f%% vs the open-loop would-win share 8.24%% (257/3,120; Linux, dfbfbe7 C13, 240 "
        "steps - a Windows closed loop against a Linux open loop, stated as such)" % (100 * share))
    # P2 / P3
    n, c2, c3, sk, miss = p2_p3("plG", tuples)
    say("P2 REACHES: %d/%d  %s" % (c2, n, "PASS" if c2 == n else "FAIL"))
    say("P3 ACTS: %d/%d (skipped by the dispatcher %d)  %s" % (c3, n, sk, "PASS" if c3 + sk == n else "FAIL"))
    for m in miss[:20]:
        say("      MISS %s" % (m,))
    # P4
    say("P4 THE DIFFERENCE IS THE PLANNER'S (plG vs plC):")
    a_ok, b_ok, chains = p4(tuples, verbose=False)
    nchange = sum(1 for tt in tuples if first_applied(load("plG", tt, side=True)) is not None)
    say("  runs with >= 1 applied role change %d/%d; (a) zero-change runs identical to plC: %s; (b) no behavioural "
        "divergence before the first change: %s; (c) chains available %d" % (
            nchange, len(tuples), "PASS" if a_ok else "FAIL", "PASS" if b_ok else "FAIL", len(chains)))
    fate_chains = [c for c in chains if load("plG", c[0])["eval"] != load("plC", c[0])["eval"]]
    for t2, fa, bd in (fate_chains or chains)[:3]:
        for ln in chain_text(t2, fa, bd):
            say(ln)
    # P5
    nz = collections.Counter()
    nscored = 0
    moved = collections.Counter()
    null_ok = null_n = 0
    binding = {v: {"steps": 0, "max_wv": 0.0, "min_gap": None} for v in NINE}
    tie_n = 0
    for tt in tuples:
        s = load("plG", tt, side=True)
        for r in s["plan"]:
            if r.get("tie"):
                tie_n += 1
            cf = r.get("cf") or {}
            null_n += 1
            if cf.get("null") == r["sel"]:
                null_ok += 1
            for k, v in cf.items():
                if k != "null" and v != r["sel"]:
                    moved[k] += 1
            prof = _profile(r["mode"]) if r["nine"] else None
            feas = [x for x in r["scored"] if x[2]]
            gap = (feas[0][1] - feas[1][1]) if len(feas) >= 2 else None
            for oid, vals in r["nine"].items():
                nscored += 1
                for v in NINE:
                    if abs(float(vals[v])) > 1e-12:
                        nz[v] += 1
            if r["nine"]:
                for v in NINE:
                    wv = max((abs(getattr(prof, _WEIGHT_KEY[v]) * float(vals[v])) for vals in r["nine"].values()),
                             default=0.0)
                    if wv > 1e-12:
                        b = binding[v]
                        b["steps"] += 1
                        b["max_wv"] = max(b["max_wv"], wv)
                        if gap is not None:
                            b["min_gap"] = gap if b["min_gap"] is None else min(b["min_gap"], gap)
    null_pass = null_ok == null_n
    say("P5 EVERY VALUE IS LIVE OR REPORTED DEAD - over %d SWITCH-option scorings:" % nscored)
    say("   NULL CONTROL: re-selection with nothing removed reproduces the selected id on %d/%d planner steps  %s"
        % (null_ok, null_n, "PASS" if null_pass else "FAIL (P5 void)"))
    p5i = True
    stop_items = []
    for v in NINE:
        share_nz = nz[v] / max(1, nscored)
        variants = [v] if v != "switching_cost" else ["switching_cost@1e-12", "switching_cost@0.15"]
        mv = ", ".join("%s moved %d" % (x, moved[x]) for x in variants)
        need = v != "communication_contribution"
        ok_i = (share_nz > 0) or not need
        p5i = p5i and ok_i
        note = ""
        if all(moved[x] == 0 for x in variants):
            if nz[v] == 0:
                note = "moves no decision: STRUCTURALLY ZERO"
            else:
                b = binding[v]
                note = "moves no decision: %s (largest |w x value| %.4f; smallest selected-runner-up gap %s)" % (
                    "NEVER BINDING" if (b["min_gap"] is None or b["max_wv"] < b["min_gap"]) else "not binding at the "
                    "steps where it could have (see note)", b["max_wv"], "%.4f" % b["min_gap"] if b["min_gap"] is not None else "n/a")
            if v in EXPECTED_MOVERS:
                stop_items.append("expected mover %s moved no decision" % v)
        say("   %-27s non-zero %6.2f%%  %s  %s%s" % (v, 100 * share_nz, mv, "(i) ok" if ok_i else "(i) FAIL", ("  " + note) if note else ""))
    if moved["drift_risk"]:
        say("   drift_risk moved %d decisions - a SURPRISE (pre-registered to move none), reported, no stop" % moved["drift_risk"])
    say("   exact-tie selections (a non-baseline option scoring exactly the baseline's score): %d" % tie_n)
    # CHURN
    runs_low = []
    burst = []
    for tt, cats, nstep in per_run:
        if cats["BASELINE"] < 0.5 * nstep:
            runs_low.append((tl(tt), cats["BASELINE"], nstep))
        ch = collections.defaultdict(list)
        for step, uid, _o, _n in role_changes(load("plG", tt)):
            ch[uid].append(step)
        for uid, ss in ch.items():
            for i in range(len(ss) - 2):
                if ss[i + 2] - ss[i] < 30:
                    burst.append((tl(tt), uid, ss[i:i + 3]))
                    break
    churn = share > 0.25 or runs_low or burst
    say("CHURN (STOP item): aggregate SWITCH share %.2f%% (> 25%%?) ; runs with baseline < 50%% of steps: %s ; "
        "UAVs switched >= 3 times within 30 steps: %s  -> %s" % (100 * share, runs_low or "none", burst or "none",
                                                                 "STOP" if churn else "no churn"))
    if tot["OTHER"]:
        stop_items.append("OTHER selected %d times" % tot["OTHER"])
    if churn:
        stop_items.append("CHURN")
    gate = pur and p1 and c2 == n and c3 + sk == n and a_ok and b_ok and bool(chains) and p5i and null_pass
    say("PRIMARY GATE 7.2: %s   STOP items: %s" % ("PASS" if gate else "FAIL", stop_items or "none"))
    return gate


# ====================================================================== 7.3 =========
UNDETECTED = ("candidate",)


_DET_RE = re.compile(r"^\[Victim Detection\] step=(\d+) UAV-\S+ detected (\S+) at")


def first_detection(d):
    """victim -> DETECTION step. REVIEW FIX (2026-09-28): a marker keeps reading 'candidate' after its
    victim is detected, until a firefighter is assigned, so the marker status alone measured the first
    ASSIGNMENT. The detection step is the first of the run's '[Victim Detection] step=t ... detected
    <vid>' stdout line (the code path that sets managed_victims[vid].confirmed) and the first row whose
    marker is neither candidate, dead nor unreachable. Same definition as outputs/_pl_verify2.py."""
    out = {}
    p = os.path.join(HERE, "_ffr_%s_%s_%s_%s.stdout.txt" % (d["tag"], d["wind"], rr(d["roles"]), d["seed"]))
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = _DET_RE.match(ln)
            if m and m.group(2) not in out:
                out[m.group(2)] = int(m.group(1))
    for i, row in enumerate(d.get("victim_steps") or []):
        for v in row:
            if str(v[2]) not in UNDETECTED + ("dead", "unreachable") and (v[0] not in out or out[v[0]] > i + 1):
                out[v[0]] = i + 1
    return out


def exposure(d):
    """(E1 burning searcher frames, searcher frames, E2 burning frames, all frames) from uav_actions
    field 2 (the burning bit of the UAV's own cell) with the role of THAT frame (uav_steps field 2)."""
    b1 = n1 = b2 = n2 = 0
    ua, us = d.get("uav_actions") or [], d.get("uav_steps") or []
    for i in range(min(len(ua), len(us))):
        role = {u[0]: u[2] for u in us[i]}
        for r in ua[i]:
            v = int(r[2])
            n2 += 1
            b2 += v
            if role.get(r[0]) == VS:
                n1 += 1
                b1 += v
    return b1, n1, b2, n2


def outcome_row(d):
    e = d["eval"]
    return {"rescued": e["rescued"], "dead": e["dead"], "ff_deaths": e["firefighter_deaths"],
            "never_detected": e["never_detected"], "terminal": d.get("terminal_step")}


def set_table(tag_c, tag_g, tuples, label, sidecars=True):
    agg = {tag: collections.Counter() for tag in (tag_c, tag_g)}
    term = {tag: [] for tag in (tag_c, tag_g)}
    nonterm = collections.Counter()
    expo = {tag: [0, 0, 0, 0] for tag in (tag_c, tag_g)}
    changes = collections.Counter()
    writes = collections.Counter()
    for t in tuples:
        for tag in (tag_c, tag_g):
            d = load(tag, t)
            o = outcome_row(d)
            for k in ("rescued", "dead", "ff_deaths", "never_detected"):
                agg[tag][k] += o[k]
            if o["terminal"] is None:
                nonterm[tag] += 1
            else:
                term[tag].append(o["terminal"])
            ex = exposure(d)
            expo[tag] = [x + y for x, y in zip(expo[tag], ex)]
            changes[tag] += len(role_changes(d))
            if sidecars:
                s = load(tag, t, side=True)
                writes[tag] += sum(1 for e in s["exec"] if e.get("applied") and e["pre"] != e["post"])
    say("  %-8s %-5s runs %2d  rescued %4d  dead %4d  ff_deaths %3d  never_detected %3d  terminal mean %s (%d terminal, "
        "%d non-terminal)  role changes %d (sidecar writes %s)  E1 %.3f%%  E2 %.3f%%" % (
            label, tag_c, len(tuples), agg[tag_c]["rescued"], agg[tag_c]["dead"], agg[tag_c]["ff_deaths"],
            agg[tag_c]["never_detected"], "%.1f" % statistics.mean(term[tag_c]) if term[tag_c] else "-",
            len(term[tag_c]), nonterm[tag_c], changes[tag_c], writes[tag_c] if sidecars else "-",
            100 * expo[tag_c][0] / max(1, expo[tag_c][1]), 100 * expo[tag_c][2] / max(1, expo[tag_c][3])))
    say("  %-8s %-5s runs %2d  rescued %4d  dead %4d  ff_deaths %3d  never_detected %3d  terminal mean %s (%d terminal, "
        "%d non-terminal)  role changes %d (sidecar writes %s)  E1 %.3f%%  E2 %.3f%%" % (
            "", tag_g, len(tuples), agg[tag_g]["rescued"], agg[tag_g]["dead"], agg[tag_g]["ff_deaths"],
            agg[tag_g]["never_detected"], "%.1f" % statistics.mean(term[tag_g]) if term[tag_g] else "-",
            len(term[tag_g]), nonterm[tag_g], changes[tag_g], writes[tag_g] if sidecars else "-",
            100 * expo[tag_g][0] / max(1, expo[tag_g][1]), 100 * expo[tag_g][2] / max(1, expo[tag_g][3])))
    say("  %-8s delta rescued %+d  dead %+d  ff_deaths %+d  never_detected %+d" % (
        "", agg[tag_g]["rescued"] - agg[tag_c]["rescued"], agg[tag_g]["dead"] - agg[tag_c]["dead"],
        agg[tag_g]["ff_deaths"] - agg[tag_c]["ff_deaths"], agg[tag_g]["never_detected"] - agg[tag_c]["never_detected"]))
    return agg


def attribution(tag_c, tag_g, tuples):
    """Per-seed outcome differences: every victim whose fate differs is attributed to the planner
    only where fire_digests are equal up to that fate (the earlier fate step of the two arms)."""
    rows = []
    for t in tuples:
        c, g = load(tag_c, t), load(tag_g, t)
        if c["eval"]["rescued"] == g["eval"]["rescued"] and c["eval"]["dead"] == g["eval"]["dead"]:
            continue
        fc, fg = fate_steps(c), fate_steps(g)
        fd = first_div(c, g, "fire_digests")
        bd = behavioural_div(g, c)
        vict = []
        for vid in sorted(set(fc) | set(fg)):
            a_, b_ = fc.get(vid, (None, "unresolved")), fg.get(vid, (None, "unresolved"))
            if a_[1] != b_[1]:
                step = min(x for x in (a_[0], b_[0]) if x is not None) if (a_[0] or b_[0]) else None
                att = "planner" if (fd is None or (step is not None and fd > step)) else "fire re-rolled"
                vict.append("%s %s->%s @%s [%s]" % (vid, a_[1], b_[1], step, att))
        rows.append((t, c["eval"]["rescued"], g["eval"]["rescued"], fd, bd, vict))
    return rows


def sec_cmp(a):
    N = n30()
    say("=" * 90)
    say("7.3 THE COMPARISON THE PAPER NEEDS - plC (local strategy, mode 0) vs plG (global planner, mode 1), 360 steps")
    say("=" * 90)
    for label, tuples in (("C13", C13), ("N30", N), ("pooled", C13 + N), ("RB7", RB7)):
        if not all(exists(x, t) for x in ("plC", "plG") for t in tuples):
            say("  %s: not complete yet" % label)
            continue
        set_table("plC", "plG", tuples, label)
    say("  never_detected is eval's: it undercounts a victim that dies while a candidate (stated).")
    say("")
    say("per-seed differences (plG - plC), with attribution (planner only where fire_digests are equal up to the fate):")
    for label, tuples in (("C13", C13), ("N30", N), ("RB7", RB7)):
        if not all(exists(x, t) for x in ("plC", "plG") for t in tuples):
            continue
        rows = attribution("plC", "plG", tuples)
        up = sum(1 for r in rows if r[2] > r[1])
        down = sum(1 for r in rows if r[2] < r[1])
        say("  %s: %d seeds differ in rescued/dead; rescued up %d, down %d" % (label, len(rows), up, down))
        for t, rc, rg, fd, bd, vict in rows:
            say("    %-26s rescued %d -> %d  first fire divergence %-4s first behavioural divergence %-18s %s"
                % (tl(t), rc, rg, fd, bd, "; ".join(vict)))
    # decisions, modes, latches
    say("")
    say("planner behaviour (plG sidecars; pooled C13 + N30):")
    modes = {"plC": collections.Counter(), "plG": collections.Counter()}
    latch = []
    inst = 0
    delay = 0
    dirs = collections.Counter()
    first_det = {"plC": [], "plG": []}
    for t in C13 + N:
        for tag in ("plC", "plG"):
            s = load(tag, t, side=True)
            modes[tag].update(r["mode"] for r in s["plan"])
            first_det[tag].extend(first_detection(load(tag, t)).values())
        s = load("plG", t, side=True)
        seen_osc = set()
        prev_inst = set()
        for r in s["plan"]:
            now_inst = set()
            for tt, ents in r["instab"]:
                if tt == "OSCILLATION_RISK":
                    for e in ents:
                        if e not in seen_osc:
                            seen_osc.add(e)
                            latch.append((tl(t), e, r["t"]))
                else:
                    now_inst.update(ents)
            inst += len(now_inst - prev_inst)
            prev_inst = now_inst
            if any(x[0] == "global_role_assignment_delay_change" for x in r["scored"]):
                delay += 1
            if r["cat"] == "SWITCH":
                vc = float(r["nine"][r["sel"]]["victim_contribution"])
                outstanding = abs(vc) > 1e-12       # D_vict > 0 <=> a victim not yet detected (share rule)
                dirs["%s->%s | %s" % (r["sel_params"]["from"], r["sel_params"]["to"],
                                      "victim undetected" if outstanding else "all detected")] += 1
                if r["sel_params"]["to"] == FT and outstanding:
                    say("    to-tracking switch with a victim undetected: %s step %d %s margin %+.4f" % (
                        tl(t), r["t"], r["sel"], r["margin"]))
    say("  switch directions: %s" % dict(dirs))
    say("  utility modes plC: %s" % dict(modes["plC"]))
    say("  utility modes plG: %s" % dict(modes["plG"]))
    say("  OSCILLATION_RISK latch (a UAV's 3rd lifetime switch; reported as a latch, not a count of oscillations): %s"
        % (latch or "never reached"))
    say("  INSTABILITY_DETECTED onsets: %d ; steps where global_role_assignment_delay_change was generated: %d" % (inst, delay))
    for tag in ("plC", "plG"):
        v = first_det[tag]
        say("  first-detection step per victim %s: n %d, mean %.1f, median %s" % (
            tag, len(v), statistics.mean(v) if v else float("nan"), statistics.median(v) if v else "-"))
    # CRN pair
    say("")
    say("THE CRN PAIR plKC / plKG on N30 (FM2P_CRN=1; compared ONLY with each other - a different, equally")
    say("distributed fire realisation, never a second measurement of the stock arms):")
    if not all(exists(tag, t) for tag in ("plKC", "plKG") for t in N):
        say("  NOT RUN (or incomplete) - the CRN attribution reads NOT RUN")
        return
    set_table("plKC", "plKG", N, "N30 CRN")
    rows = attribution("plKC", "plKG", N)
    say("  %d seeds differ under CRN; rescued up %d, down %d" % (len(rows), sum(1 for r in rows if r[2] > r[1]),
                                                                  sum(1 for r in rows if r[2] < r[1])))
    for t, rc, rg, fd, bd, vict in rows:
        say("    %-26s rescued %d -> %d  first fire divergence %-4s first behavioural divergence %-18s %s"
            % (tl(t), rc, rg, fd, bd, "; ".join(vict)))
    say("  stock differences re-examined under CRN (N30):")
    for t, rc, rg, fd, bd, vict in attribution("plC", "plG", N):
        kc, kg = load("plKC", t), load("plKG", t)
        still = kc["eval"]["rescued"] != kg["eval"]["rescued"]
        extra = ""
        if still:
            bd2 = behavioural_div(kg, kc)
            s = load("plKG", t, side=True)
            before = [e["t"] for e in s["exec"] if e.get("applied") and e["pre"] != e["post"] and bd2 and e["t"] <= bd2[0]]
            extra = "; CRN first behavioural divergence %s, role change(s) before it at %s" % (bd2, before[-3:] or "none")
        say("    %-26s stock %d -> %d ; CRN %d -> %d : %s%s" % (tl(t), rc, rg, kc["eval"]["rescued"], kg["eval"]["rescued"],
                                                             "STILL DIFFERS" if still else "no difference under CRN", extra))


# ====================================================================== 7.5 =========
def berths(d):
    return [[tuple(b) for b in bs] for bs in (d.get("base_station") or {}).get("uav_berths_by_depot") or []]


def depots(d):
    bs = d.get("base_station") or {}
    size = int(bs.get("size") or 5)
    return [(int(o[0]), int(o[1]), size) for o in bs.get("depots") or []]


def in_depot(cell, deps):
    return any(ox <= cell[0] < ox + s and oy <= cell[1] < oy + s for ox, oy, s in deps)


def stranding(d):
    """(frames at battery <= 0 outside the depot, D3 ZERO-BATT UAVs, D1 STUCK UAVs)."""
    rows = d.get("uav_steps") or []
    deps = depots(d)
    zero_frames = 0
    for row in rows:
        for u in row:
            if u[4] is not None and u[4] <= 0 and (u[5] if len(u) > 5 else "") not in ("charging", "docked"):
                zero_frames += 1
    d3 = d1 = 0
    if rows:
        for a_i, u in enumerate(rows[-1]):
            if u[4] is not None and u[4] <= 0 and u[1] is not None and not in_depot(u[1], deps):
                d3 += 1
            if (u[5] if len(u) > 5 else "") == "returning":
                n = 0
                for r in reversed(rows):
                    if r[a_i][1] == u[1]:
                        n += 1
                    else:
                        break
                if n >= 10:
                    d1 += 1
    return zero_frames, d3, d1


def stationary(d):
    """flying (base_state "") UAVs on one cell >= 10 frames: (before terminal, after)."""
    rows = d.get("uav_steps") or []
    term = d.get("terminal_step")
    pre = post = 0
    if not rows:
        return 0, 0
    for a_i in range(len(rows[0])):
        f = 0
        while f < len(rows):
            c = rows[f][a_i]
            if c[1] is None or (c[5] if len(c) > 5 else "") != "":
                f += 1
                continue
            g = f
            while g + 1 < len(rows) and rows[g + 1][a_i][1] == c[1] and (rows[g + 1][a_i][5] if len(rows[g + 1][a_i]) > 5 else "") == "":
                g += 1
            if g - f + 1 >= 10:
                if term is not None and f + 1 > term:
                    post += 1
                else:
                    pre += 1
            f = g + 1
    return pre, post


def legs(d):
    """Return legs L1 and the L2-L6 counts (outputs/_dcd4_analyze.py definitions)."""
    rows = d.get("uav_steps") or []
    out = collections.Counter()
    if not rows:
        return out
    trips = d.get("rtb_log") or {}
    for a_i in range(len(rows[0])):
        uid = rows[0][a_i][0]
        f = 0
        while f < len(rows):
            if (rows[f][a_i][5] if len(rows[f][a_i]) > 5 else "") != "returning":
                f += 1
                continue
            g = f
            while g + 1 < len(rows) and (rows[g + 1][a_i][5] if len(rows[g + 1][a_i]) > 5 else "") == "returning":
                g += 1
            leg = [tuple(rows[k][a_i][1]) for k in range(f, g + 1) if rows[k][a_i][1] is not None]
            out["L1"] += 1
            run = best = 1
            for k in range(1, len(leg)):
                run = run + 1 if leg[k] == leg[k - 1] else 1
                best = max(best, run)
            if best >= 3:
                out["L2"] += 1
            col = [leg[0]] if leg else []
            for c in leg[1:]:
                if c != col[-1]:
                    col.append(c)
            if len(set(col)) < len(col):
                out["L3"] += 1
            if any(len(set(leg[k:k + 10])) <= 2 and sum(1 for j in range(k + 1, k + 10) if leg[j] != leg[j - 1]) >= 2
                   for k in range(0, max(0, len(leg) - 9))):
                out["L4"] += 1
            if any(col.count(c) >= 3 for c in set(col)):
                out["L5"] += 1
            trip = next((tr for tr in trips.get(uid, []) if tr.get("trigger_step") == f + 2), None)
            if trip is not None:
                tb = tuple(trip["target_berth"])
                dist = [abs(c[0] - tb[0]) + abs(c[1] - tb[1]) for c in leg]
                if any(dist[k + 10] >= dist[k] for k in range(0, max(0, len(dist) - 10))):
                    out["L6"] += 1
            f = g + 1
    return out


def unarrived(d):
    """(unarrived trips, horizon-truncated, NOT-truncated) - D2."""
    rows = d.get("uav_steps") or []
    ua = tr = nt = 0
    idx = {u[0]: i for i, u in enumerate(rows[0])} if rows else {}
    for uid, trips in (d.get("rtb_log") or {}).items():
        for trip in trips:
            if trip.get("arrival_step") is not None:
                continue
            ua += 1
            i = idx.get(uid)
            last = rows[-1][i]
            tb = tuple(trip["target_berth"])
            stuck = False
            if (last[5] if len(last) > 5 else "") == "returning":
                n = 0
                for r in reversed(rows):
                    if r[i][1] == last[1]:
                        n += 1
                    else:
                        break
                stuck = n >= 10
            dnow = abs(last[1][0] - tb[0]) + abs(last[1][1] - tb[1])
            prev = rows[-11][i][1] if len(rows) > 10 else None
            dprev = abs(prev[0] - tb[0]) + abs(prev[1] - tb[1]) if prev else None
            if (last[5] if len(last) > 5 else "") == "returning" and not stuck and dprev is not None and dnow < dprev:
                tr += 1
            else:
                nt += 1
    return ua, tr, nt


def oob_both(d):
    """off-grid refusals by searchers: (per-step role attribution, step-1 role attribution)."""
    MX, MY = [1, 0, -1, 0], [0, -1, 0, 1]
    h = int((d.get("params") or {}).get("HEIGHT") or 50)
    w = int((d.get("params") or {}).get("WIDTH") or 50)
    rows = d.get("uav_steps") or []
    per = first = 0
    prev = {}
    role1 = {u[0]: u[2] for u in rows[0]} if rows else {}
    for i, row in enumerate(rows):
        for u in row:
            uid, cell, role, dirn = u[0], u[1], u[2], u[3]
            if cell is not None and prev.get(uid) == tuple(cell) and dirn is not None:
                tx, ty = cell[0] + MX[dirn], cell[1] + MY[dirn]
                if not (0 <= tx < h and 0 <= ty < w):
                    if role == VS:
                        per += 1
                    if role1.get(uid) == VS:
                        first += 1
            prev[uid] = tuple(cell) if cell is not None else None
    return per, first


def coverage(d):
    """steps with 0 flying searchers, 0 flying trackers (uav_steps fields 2 and 5), and 0 flying UAVs."""
    ns = nt = nf = 0
    for row in d.get("uav_steps") or []:
        fly = [u for u in row if (u[5] if len(u) > 5 else "") == ""]
        if not any(u[2] == VS for u in fly):
            ns += 1
        if not any(u[2] == FT for u in fly):
            nt += 1
        if not fly:
            nf += 1
    return ns, nt, nf


def load_rb(tag, sfx):
    w, _seeds = RB_SHARDS[sfx]
    # plRB ran from the dfbfbe7 worktree, whose campaign writes next to itself; its four shards were
    # copied byte-identically into this checkout's outputs/ (the worktree is removed after the round)
    p = os.path.join(HERE, "_rblatch_camp2_%s%s_D_%s.json" % (tag, sfx, w))
    if tag == "plRB" and not os.path.exists(p):
        p = os.path.join(BASE_OUT, "_rblatch_camp2_%s%s_D_%s.json" % (tag, sfx, w))
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def rb_evals(tag):
    out = {}
    for sfx, (w, _s) in RB_SHARDS.items():
        d = load_rb(tag, sfx)
        if d is None:
            return None
        for e in d["evals"]:
            out[(w, int(e["seed"]))] = e
    return out


def sec_safety(a):
    N = n30()
    say("=" * 90)
    say("7.5 SAFETY (gate) - plG against plC, 360 steps")
    say("=" * 90)
    sets = (("C13", C13), ("N30", N), ("RB7", RB7))
    # (a)
    res = {}
    tot = {"plC": [0, 0, 0], "plG": [0, 0, 0]}
    for _l, tuples in sets:
        for t in tuples:
            for tag in ("plC", "plG"):
                tot[tag] = [x + y for x, y in zip(tot[tag], stranding(load(tag, t)))]
    res["a"] = tot["plG"] == [0, 0, 0]
    say("(a) NO UAV STRANDED: [frames at battery <= 0 outside the depot, D3 ZERO-BATT, D1 STUCK]  plC %s  plG %s  %s"
        % (tot["plC"], tot["plG"], "PASS" if res["a"] else ("TO THE MAINTAINER (plC non-zero)" if tot["plC"] != [0, 0, 0] else "FAIL")))
    # (b)
    say("(b) NO LIVELOCK: flying UAVs stationary >= 10 frames (before / after the terminal step), return legs L1-L6:")
    pooled = {"plC": collections.Counter(), "plG": collections.Counter()}
    for label, tuples in sets:
        per = {"plC": collections.Counter(), "plG": collections.Counter()}
        for t in tuples:
            for tag in ("plC", "plG"):
                d = load(tag, t)
                pre, post = stationary(d)
                per[tag]["stationary"] += pre
                per[tag]["stationary_after_terminal"] += post
                per[tag].update(legs(d))
        for tag in ("plC", "plG"):
            pooled[tag].update(per[tag])
            say("    %-4s %s %s" % (label, tag, dict(sorted(per[tag].items()))))
    flag = []
    for k in ("stationary", "L2", "L3", "L4", "L5", "L6"):
        c, g = pooled["plC"][k], pooled["plG"][k]
        if g > c * 1.10 and g - c >= 2:
            flag.append("%s %d -> %d" % (k, c, g))
    res["b"] = not flag
    say("    pooled: plC %s" % dict(sorted(pooled["plC"].items())))
    say("    pooled: plG %s" % dict(sorted(pooled["plG"].items())))
    say("    -> %s" % ("no item above plC by > 10%% and >= 2" if not flag else "TO THE MAINTAINER: %s" % flag))
    # (c)
    u = {"plC": [0, 0, 0], "plG": [0, 0, 0]}
    for _l, tuples in sets:
        for t in tuples:
            for tag in ("plC", "plG"):
                u[tag] = [x + y for x, y in zip(u[tag], unarrived(load(tag, t)))]
    res["c"] = u["plG"][2] == 0
    say("(c) BATTERY RETURN COMPLETES: [unarrived trips, horizon-truncated, NOT-truncated]  plC %s  plG %s  %s"
        % (u["plC"], u["plG"], "PASS" if res["c"] else "FAIL"))
    # (d)
    o = {"plC": [0, 0], "plG": [0, 0]}
    for _l, tuples in sets:
        for t in tuples:
            for tag in ("plC", "plG"):
                o[tag] = [x + y for x, y in zip(o[tag], oob_both(load(tag, t)))]
    res["d"] = o["plG"] == [0, 0]
    say("(d) SEARCHER GUARD REFUSALS (off-grid) [searcher per step, searcher by step-1 role]: plC %s  plG %s  %s"
        % (o["plC"], o["plG"], "PASS" if res["d"] else "FAIL"))
    # (e)
    say("(e) NO NEW route_blocked FAILURES (rbgate, 4 shards, 18 seeds, 240 steps):")
    rbB, rbC, rbG = (rb_evals(x) for x in ("plRB", "plRC", "plRG"))
    if rbB is None:
        e1 = None
        say("    (i) plRC == plRB: NOT RUN")
    else:
        bad = []
        for sfx in RB_SHARDS:
            b, c = load_rb("plRB", sfx), load_rb("plRC", sfx)
            dk = diff_keys(b, c, ("tag", "evals"))
            ev_b = [{k: v for k, v in e.items() if k != "wall_s"} for e in b["evals"]]
            ev_c = [{k: v for k, v in e.items() if k != "wall_s"} for e in c["evals"]]
            if dk or ev_b != ev_c:
                bad.append((sfx, dk, ev_b == ev_c))
        e1 = not bad
        say("    (i) plRC (branch, mode 0) == plRB (dfbfbe7 worktree), every key but tag, evals element by element "
            "without wall_s: %d/4 shards  %s" % (4 - len(bad), "PASS" if e1 else "FAIL %s" % bad))
    if rbC is None or rbG is None:
        say("    (ii) NOT RUN")
        e2 = None
    else:
        regr = sorted(k for k in rbC if int(rbG[k]["rescued"]) < int(rbC[k]["rescued"]))
        say("    (ii) plRG vs plRC rescued per seed: regressions %s ; outside the known four: %s"
            % (regr or "none", [k for k in regr if k not in RB_KNOWN] or "NONE"))
        items = []
        rolled = []
        for (w, s) in sorted(rbC):
            t = (w, "half", s)
            if t not in C13 and t not in RB7:
                continue
            c, g = load("plC", t), load("plG", t)
            fd = first_div(c, g, "fire_digests")
            term = c.get("terminal_step") if (c.get("terminal_step") or 999) <= 240 else 240
            if fd is not None and fd < term:
                rolled.append((w, s))
        for k in regr:
            if k in RB_KNOWN:
                continue
            t = (k[0], "half", k[1])
            if t not in C13 and t not in RB7:
                items.append("FAIL: %s no harness pair" % (k,))
            elif k not in rolled:
                items.append("NEW FAIL: %s not re-rolled" % (k,))
            else:
                items.append("re-rolled: %s" % (k,))
        pc = sum(int(rbC[k]["rescued"]) for k in rolled)
        pg = sum(int(rbG[k]["rescued"]) for k in rolled)
        say("      re-rolled seeds (plG vs plC fire_digests diverge before plC's terminal step, 240 cap): %s" % rolled)
        say("      pooled rescued over them plRC %d -> plRG %d" % (pc, pg))
        e2 = not any(x.startswith(("FAIL", "NEW FAIL")) for x in items)
        if any(x.startswith("re-rolled") for x in items) and pg < pc:
            say("      TO THE MAINTAINER: re-rolled regression(s) with a pooled loss")
        say("      %s -> %s" % (items or "no regression outside the known four", "PASS" if e2 else "FAIL"))
        latched = {tag: sum(len(load_rb(tag, sfx).get("latched") or []) for sfx in RB_SHARDS) for tag in ("plRC", "plRG")}
        say("      latched line (units route_blocked and alive at the end): %s" % latched)
        for tag in ("plRC", "plRG") + (("plRB",) if rbB else ()):
            ev = rb_evals(tag)
            say("      %s totals: rescued %d dead %d ff_deaths %d" % (tag, sum(int(e["rescued"]) for e in ev.values()),
                                                                    sum(int(e["dead"]) for e in ev.values()),
                                                                    sum(int(e["firefighter_deaths"]) for e in ev.values())))
    res["e"] = (e1 is not False) and (e2 is not False)
    # (f)
    cov = {"plC": [0, 0, 0], "plG": [0, 0, 0]}
    for _l, tuples in sets:
        for t in tuples:
            for tag in ("plC", "plG"):
                cov[tag] = [x + y for x, y in zip(cov[tag], coverage(load(tag, t)))]
    res["f"] = cov["plG"][0] <= cov["plC"][0] and cov["plG"][1] <= cov["plC"][1]
    say("(f) SEARCH COVERAGE: steps with [0 flying searchers, 0 flying trackers, 0 flying UAVs], pooled C13+N30+RB7: "
        "plC %s  plG %s  -> %s" % (cov["plC"], cov["plG"], "not above plC" if res["f"] else "TO THE MAINTAINER"))
    # (g)
    say("(g) SWITCH TRANSITIONS (reported): per switch, incumbents re-indexed, a new searcher's first 10 steps, "
        "and switches within +/-10 steps of a return trigger or release:")
    g_stats = collections.Counter()
    for _l, tuples in sets:
        for t in tuples:
            d = load("plG", t)
            ps = d.get("partition_steps") or []
            trig = [(tr.get("trigger_step"), tr.get("released_step")) for trs in (d.get("rtb_log") or {}).values() for tr in trs]
            for step, uid, old, new in role_changes(d):
                g_stats["switches"] += 1
                g_stats["to_" + new] += 1
                if 2 <= step <= len(ps):
                    # rows of step t-1 and t; a RE-INDEX is a change of an incumbent's flank index /
                    # flank count or of its lane (the bounds of a tracker's flank move every step anyway)
                    before, after = ps[step - 2], ps[step - 1]

                    def ix(p, u):
                        sec = (p.get("sectors") or {}).get(u)
                        return (None if sec is None else (sec.get("flank_index"), sec.get("flank_count")),
                                (p.get("lanes") or {}).get(u))
                    others = [u for u in set(before.get("sectors") or {}) | set(before.get("lanes") or {}) if u != uid]
                    if any(ix(before, u) != ix(after, u) for u in others):
                        g_stats["incumbents_reindexed"] += 1
                if any((x is not None and abs(x - step) <= 10) for pair in trig for x in pair):
                    g_stats["near_return_or_release"] += 1
                if new == VS:
                    us = d["uav_steps"][step - 1: step + 9]
                    cells = [next(u[1] for u in row if u[0] == uid) for row in us]
                    g_stats["new_searcher_stationary_frames"] += sum(1 for k in range(1, len(cells)) if cells[k] == cells[k - 1])
    say("    %s" % dict(g_stats))
    verdict = res["a"] and res["c"] and res["d"] and res["e"]
    say("7.5 GATE (a)(c)(d)(e): %s ; (b) and (f) are TO-THE-MAINTAINER items: %s" % (
        "PASS" if verdict else "FAIL", {k: res[k] for k in ("b", "f")}))
    return verdict


# ============================================================ 11A (b) local planner ==
def sec_local(a):
    N = n30()
    say("=" * 90)
    say("FINDING 11A (b): the LOCAL path planner's selections - decided by fixed PRECEDENCE or by SCORE")
    say("=" * 90)
    say("  local_uav_path_planner._select_feasible_option, per call (one per UAV per step): rtb = a return-to-base")
    say("  option took precedence; wind = wind_aware_victim_search took precedence; score = the top-scored feasible")
    say("  option; fallback = no feasible option (hold). *_over_top = the precedence option was NOT the top-scored")
    say("  feasible option (precedence decided); *_strict = and the top one scored strictly higher.")
    for tag, tuples in (("plB", C13), ("plC", C13 + N), ("plC", RB7), ("plG", C13 + N), ("plG", RB7)):
        if not all(exists(tag, t) for t in tuples):
            say("  %s on %d runs: not complete" % (tag, len(tuples)))
            continue
        tot = collections.Counter()
        by_role = collections.defaultdict(collections.Counter)
        mism = 0
        for t in tuples:
            s = load(tag, t, side=True)
            tot.update(s["local"]["total"])
            for r, c in s["local"]["by_role"].items():
                by_role[r].update(c)
            mism += s["counters"].get("local_branch_mismatch", 0)
        n = tot["calls"]
        prec = tot["rtb"] + tot["wind"]
        over = tot["rtb_over_top"] + tot["wind_over_top"]
        say("  %s (%d runs): calls %d | precedence %d (%.1f%%: rtb %d, wind %d) of which the precedence option was not the "
            "top-scored %d (%.1f%% of calls; strictly lower-scored %d) | score %d (%.1f%%) | fallback %d | branch "
            "re-derivation mismatches %d" % (tag, len(tuples), n, prec, 100 * prec / max(1, n), tot["rtb"], tot["wind"],
                                              over, 100 * over / max(1, n), tot["rtb_over_top_strict"] + tot["wind_over_top_strict"],
                                              tot["score"], 100 * tot["score"] / max(1, n), tot["fallback"], mism))
        for r in sorted(by_role):
            c = by_role[r]
            say("      role %-16s calls %d  rtb %d  wind %d (over top %d)  score %d  fallback %d" % (
                r, c["calls"], c["rtb"], c["wind"], c["wind_over_top"] + c["rtb_over_top"], c["score"], c["fallback"]))


# ============================================================ 11A (a) coverage gap ==
def sec_gap(a):
    N = n30()
    say("=" * 90)
    say("FINDING 11A (a): synchronized recharging leaves search uncovered - per run, 360 steps")
    say("=" * 90)
    say("  per run: steps with NO flying victim searcher (every searcher returning/charging/docked), its blocks")
    say("  (first-last), steps with no flying UAV at all, and whether a victim was still undetected in the block")
    for tag in ("plC", "plG"):
        allb = []
        und = 0
        for t in C13 + N:
            d = load(tag, t)
            rows = d["uav_steps"]
            det = first_detection(d)
            vids = {v[0] for v in d["victim_steps"][0]} if d["victim_steps"] else set()
            blocks = []
            f = 0
            while f < len(rows):
                fly_vs = any(u[2] == VS and (u[5] if len(u) > 5 else "") == "" for u in rows[f])
                if fly_vs:
                    f += 1
                    continue
                g = f
                while g + 1 < len(rows) and not any(u[2] == VS and (u[5] if len(u) > 5 else "") == "" for u in rows[g + 1]):
                    g += 1
                blocks.append((f + 1, g + 1))
                f = g + 1
            ns, nt, nf = coverage(d)
            # a victim ALIVE (marker candidate) and NOT YET DETECTED (detection step > k) on some step
            # of a no-searcher block - REVIEW FIX: 'candidate' alone persists after detection
            vsteps = d["victim_steps"]
            undetected_in = any(any(str(v[2]) == "candidate" and det.get(v[0], 10 ** 9) > k for v in vsteps[k - 1])
                                for b0, b1 in blocks for k in range(b0, b1 + 1) if k - 1 < len(vsteps))
            und += int(undetected_in)
            allb.append(ns)
            if a.verbose:
                say("    %s %-24s no-searcher steps %3d blocks %s  no-UAV steps %3d  undetected victim in a block: %s" % (
                    tag, tl(t), ns, blocks, nf, undetected_in))
        say("  %s: runs %d, no-searcher steps per run min %d / median %s / max %d; runs with any %d; runs with an undetected "
            "victim during a no-searcher block %d" % (tag, len(allb), min(allb), statistics.median(allb), max(allb),
                                                       sum(1 for x in allb if x), und))
        # why: the return triggers fall in one window (every UAV launches at battery 100, one rule per UAV)
        spans, second, pre_term, fleet_pre, bat1 = [], 0, [], [], collections.Counter()
        for t in C13 + N:
            d = load(tag, t)
            firsts = [trs[0]["trigger_step"] for trs in (d.get("rtb_log") or {}).values() if trs]
            if firsts:
                spans.append((min(firsts), max(firsts)))
            if any(len(trs) >= 2 for trs in (d.get("rtb_log") or {}).values()):
                second += 1
            bat1.update(round(u[4], 1) for u in d["uav_steps"][0])
            term = d.get("terminal_step") or 360
            rows = d["uav_steps"][:term]
            pre_term.append(sum(1 for row in rows if not any(u[2] == VS and (u[5] if len(u) > 5 else "") == "" for u in row)))
            fleet_pre.append(sum(1 for row in rows if not any((u[5] if len(u) > 5 else "") == "" for u in row)))
        say("      first return triggers per run (earliest-latest UAV): earliest %d-%d, latest %d-%d; span of the window "
            "median %s steps; runs with a SECOND return trip inside 360 steps %d/%d" % (
                min(s[0] for s in spans), max(s[0] for s in spans), min(s[1] for s in spans), max(s[1] for s in spans),
                statistics.median(s[1] - s[0] for s in spans), second, len(spans)))
        say("      battery of every UAV after step 1: %s (all launch at 100)" % dict(bat1))
        say("      BEFORE the terminal step only (victims still outstanding): no-searcher steps per run median %s max %d, "
            "runs with any %d; no flying UAV at all: runs with any %d, max %d" % (
                statistics.median(pre_term), max(pre_term), sum(1 for x in pre_term if x),
                sum(1 for x in fleet_pre if x), max(fleet_pre)))


# ================================================================== 7.4 reference ==
def sec_ref(a):
    N = n30()
    say("=" * 90)
    say("7.4 REFERENCE ARMS on N30 at 360 (each against plC's N30): plF = no firefighting during search")
    say("(FF_FIREFIGHT_EXTINGUISH=0, FF_FIREFIGHT_FIREBREAK=0); plS = no base station (BASE_STATION_MODE=0)")
    say("=" * 90)
    for tag in ("plF", "plS"):
        if not all(exists(tag, t) for t in N):
            say("  %s: NOT RUN (dropped or incomplete)" % tag)
            continue
        set_table("plC", tag, N, "N30")


SECTIONS = {"id": sec_id, "plq": sec_plq, "c13": sec_c13, "gate": sec_gate, "cmp": sec_cmp, "safety": sec_safety,
            "local": sec_local, "gap": sec_gap, "ref": sec_ref}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("section")
    ap.add_argument("--out", default="")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    fn = SECTIONS.get(a.section)
    if fn is None:
        raise SystemExit("unknown section %r (have %s)" % (a.section, sorted(SECTIONS)))
    fn(a)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(OUT_LINES) + "\n")


if __name__ == "__main__":
    main()
