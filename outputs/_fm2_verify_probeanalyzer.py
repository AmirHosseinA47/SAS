"""Adversarial verification of outputs/_fm2_analyze.py claims (task probeanalyzer).

Independent re-derivation from raw harness JSON. Does NOT import _fm2_analyze,
_firemech_analyze or _dcd4_analyze. Explicit paths only; no glob; never touches
outputs/_firemech_rewound_20260914/. Read-only; writes nothing.
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = 240
CELLS = 2500
CAN = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
       + [("east", "def", s) for s in (101, 202, 303)])
FRE = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
       + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
ALL = CAN + FRE


def lab(t):
    return "%s/%s/%d" % t


def p(tag, t):
    return os.path.join(HERE, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))


def load(tag, t):
    q = p(tag, t)
    if not os.path.exists(q) or os.path.exists(q + ".tmp") or os.path.exists(q + ".fm2p.tmp"):
        return None
    with open(q, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------- strict equality
def strict_eq(a, b, path="$"):
    """None if equal with type strictness (bool/int/float distinct), else first differing path."""
    if type(a) is not type(b):
        return path + " type %s vs %s" % (type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        if set(a) != set(b):
            return path + " keyset"
        for k in a:
            r = strict_eq(a[k], b[k], path + "." + str(k))
            if r:
                return r
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return path + " len %d vs %d" % (len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            r = strict_eq(x, y, "%s[%d]" % (path, i))
            if r:
                return r
        return None
    return None if a == b else path + " value"


def order_paths(a, b, path="$", out=None):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a) != list(b) and set(a) == set(b):
            out.append(path)
        for k in a:
            if k in b:
                order_paths(a[k], b[k], path + "." + str(k), out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            if isinstance(x, (dict, list)):
                order_paths(x, y, path + "[]", out)
    return out


def identity(tag_a, tag_b, tuples, exclude):
    res = []
    for t in tuples:
        a, b = load(tag_a, t), load(tag_b, t)
        if a is None or b is None:
            res.append((t, "MISSING", None, None, None))
            continue
        keys = sorted((set(a) | set(b)) - set(exclude))
        loose = [k for k in keys if a.get(k, "<abs>") != b.get(k, "<abs>")]
        strict = [k for k in keys if (k not in a) or (k not in b) or strict_eq(a[k], b[k])]
        ords = sorted(set(x.split(".")[1] if x.count(".") >= 1 else x
                          for x in order_paths({k: a.get(k) for k in keys if k in a and k in b},
                                               {k: b.get(k) for k in keys if k in a and k in b})
                          if x != "$"))
        top_order = [k for k in keys if isinstance(a.get(k), dict) and isinstance(b.get(k), dict)
                     and list(a[k]) != list(b[k])]
        res.append((t, "OK", loose, strict, (ords, top_order)))
    return res


# ------------------------------------------------------------- per run summary
def burning(bi, cell, step):
    for s, e in bi.get("%d,%d" % cell) or ():
        if s <= step and (e is None or step < e):
            return True
    return False


def summary(d):
    ev = d["eval"]
    R = {"rescued": int(ev.get("rescued") or 0), "dead": int(ev.get("dead") or 0),
         "ffd": int(ev.get("firefighter_deaths") or 0), "nd": int(ev.get("never_detected") or 0),
         "unreach": int(ev.get("unreachable") or 0), "burnt": int(ev.get("burnt_cells") or 0),
         "term": ev.get("terminal_step")}
    fg = d.get("fire_ground_final") or {}
    bi = d.get("burn_intervals") or {}
    R["ever"] = sum(1 for v in fg.values() if v[0])
    R["cleared"] = int(d.get("fire_cleared_unburned_final") or 0)
    R["intact"] = CELLS - R["ever"] - R["cleared"]
    R["b240"] = sum(1 for v in fg.values() if v[2])
    R["b240_bi"] = sum(1 for v in bi.values() if any(e is None for _s, e in v))
    R["bi_cells"] = sum(1 for v in bi.values() if v)
    # E1 / E2 (own implementation of the interior-hazard / all-UAV definitions)
    e1n = e1d = e2n = e2d = 0
    for i, row in enumerate(d.get("uav_steps") or []):
        for c in row:
            if c[2] == "victim_searcher" and c[1] is not None:
                e1d += 1
                e1n += int(burning(bi, tuple(c[1]), i + 1))
    for arow in d.get("uav_actions") or []:
        for ent in arow or ():
            e2d += 1
            e2n += int(bool(len(ent) > 2 and ent[2]))
    R.update(e1n=e1n, e1d=e1d, e2n=e2n, e2d=e2d)
    log = d.get("firefight_log") or []
    R["rows"] = len(log)
    R["first_row"] = min((r["step"] for r in log), default=None)
    R["first_write"] = min((r["step"] for r in log if r.get("wrote")), default=None)
    R["engaged"] = sum(1 for r in log if r.get("engaged"))
    term = R["term"]
    R["eng_after"] = sum(1 for r in log if r.get("engaged") and term is not None and r["step"] > term)
    R["eng_le"] = sum(1 for r in log if r.get("engaged") and term is not None and r["step"] <= term)
    R["ext"] = sum(1 for r in log if r.get("wrote") and r["action"] == "extinguish")
    R["clear"] = sum(1 for r in log if r.get("wrote") and r["action"] == "clear")
    # ff deaths from ff_steps dead flag
    rows_by = collections.defaultdict(dict)
    for r in log:
        rows_by[r["ff"]][r["step"]] = r
    posd = collections.defaultdict(dict)
    for i, row in enumerate(d.get("ff_steps") or []):
        for ff, pos, st, asg, ex, dead in row:
            posd[ff][i + 1] = (tuple(pos) if pos is not None else None, st, asg, ex, dead)
    deaths = []
    for ff in sorted(posd):
        ds = [s for s in sorted(posd[ff]) if posd[ff][s][4]]
        if not ds:
            continue
        s = ds[0]
        cell = posd[ff][s][0]
        rf = rows_by.get(ff, {})
        eng = bool(rf.get(s, {}).get("engaged"))
        prev = bool(rf.get(s - 1, {}).get("engaged"))
        k = s if s in rf else s - 1
        streak = False
        while k in rf:
            streak = streak or bool(rf[k].get("engaged"))
            k -= 1
        las = [a["step"] for a in d.get("assigns") or [] if a.get("ok") and a["ff"] == ff and a["step"] <= s]
        pre = False
        if las:
            la = max(las)
            if la in rf:
                pre = bool(rf[la].get("engaged"))
            elif (la - 1) in rf:
                pre = bool(rf[la - 1].get("engaged"))
            if any(c["ff"] == ff and la <= c["step"] <= s for c in d.get("completions") or []):
                pre = False
        nb = nbb = 0
        if cell is not None:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cell[0] + dx, cell[1] + dy)
                if 0 <= n[0] < 50 and 0 <= n[1] < 50:
                    nb += 1
                    nbb += int(burning(bi, n, s))
        deaths.append({"ff": ff, "step": s, "engaged": eng, "prev": prev, "streak": streak, "pre": pre,
                       "after": term is not None and s > term, "full": bool(nb) and nb == nbb})
    R["deaths"] = deaths
    R["ffd_steps"] = len(deaths)
    last = (d.get("victim_steps") or [[]])[-1]
    R["victims"] = {v[0]: v[2] for v in last}
    R["resc_vs"] = sum(1 for v in last if v[2] == "rescued")
    fm = (d.get("fm2p") or {}).get("counters") or {}
    R["fm2p"] = {k: int(fm.get(k) or 0) for k in ("leash_dropped", "gate_closed_calls",
                                                  "engage_only_blocked_calls", "dry_forced_calls", "crn_draws")}
    R["fm2p_present"] = "fm2p" in d
    R["digests"] = d.get("fire_digests")
    R["ff_steps"] = d.get("ff_steps")
    R["cfg"] = (d.get("fm2p") or {}).get("config")
    return R


_S = {}


def S(tag, t):
    k = (tag, t)
    if k not in _S:
        d = load(tag, t)
        _S[k] = summary(d) if d is not None else None
    return _S[k]


def first_div(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i + 1
    return None if len(a) == len(b) else min(len(a), len(b)) + 1


def pct(n, d):
    return "%d/%d = %.2f%%" % (n, d, 100.0 * n / d) if d else "-"


def tot(recs, k):
    return sum(r[k] for r in recs)


def out(*a):
    print(" ".join(str(x) for x in a))


def main():
    sec = sys.argv[1:] or ["all"]
    run = lambda name: "all" in sec or name in sec  # noqa: E731

    if run("cov"):
        out("== COVERAGE (explicit paths)")
        for tag in ["fmOFF", "fmREF", "fmDRY", "fmEFS", "fmF", "fmFS", "fmES", "fmS", "fmE", "fmEF",
                    "f2IDD", "f2U0D", "f2U1D", "f2L3D", "f2L8D", "f2GD", "f2GW", "f2GF", "f2cOFF", "f2cES", "f2cF"]:
            out("  %-7s canonical %2d/13 fresh %2d/10" % (
                tag, sum(os.path.exists(p(tag, t)) for t in CAN), sum(os.path.exists(p(tag, t)) for t in FRE)))

    if run("ident"):
        out("== IDENTITY f2IDD vs fmDRY (canonical 13), excl tag/repo/wall_s")
        for t, st, loose, strict, ords in identity("f2IDD", "fmDRY", CAN, ("tag", "repo", "wall_s")):
            out("  %-16s %s loose-diff %s strict-diff %s order(nested) %s top-order %s" % (
                lab(t), st, loose, strict, ords[0] if ords else None, ords[1] if ords else None))
        out("== IDENTITY fmOFF vs fmREF (23)")
        n_same = n_bi = 0
        for t, st, loose, strict, ords in identity("fmOFF", "fmREF", ALL, ("tag", "repo", "wall_s")):
            n_same += int(st == "OK" and not strict)
            n_bi += int(st == "OK" and ords[1] == ["burn_intervals"])
            if st != "OK" or strict or ords[1] not in (["burn_intervals"], []):
                out("  %-16s %s strict %s top-order %s" % (lab(t), st, strict, ords[1] if ords else None))
        out("  fmOFF==fmREF strict-identical runs %d/23; runs whose only top-level dict order diff is burn_intervals %d" % (n_same, n_bi))
        for a_, b_ in (("fmS", "fmOFF"), ("fmE", "fmOFF"), ("fmEF", "fmF")):
            keys = set()
            same2 = 0
            for t, st, loose, strict, ords in identity(a_, b_, CAN, ("tag", "repo", "wall_s")):
                keys |= set(strict or [])
                same2 += int(st == "OK" and not [k for k in strict if k not in ("params", "extra_params")])
            out("  %s vs %s differing keys %s; identical excl params/extra_params %d/13" % (a_, b_, sorted(keys), same2))

    if run("dry"):
        out("== DRY fire_digests vs fmOFF 240/240")
        for arm in ("f2IDD", "f2U0D", "f2U1D", "f2L3D", "f2L8D", "f2GD", "fmDRY"):
            for nm, tt in (("canonical", CAN), ("fresh", FRE)):
                pairs = [(t, S(arm, t), S("fmOFF", t)) for t in tt]
                pairs = [(t, a, b) for t, a, b in pairs if a is not None and b is not None]
                if not pairs:
                    continue
                viol = [(lab(t), first_div(a["digests"], b["digests"])) for t, a, b in pairs
                        if first_div(a["digests"], b["digests"]) is not None]
                lens = set(len(a["digests"]) for _t, a, _b in pairs)
                out("  %-6s %-9s identical %d/%d lens %s viol %s" % (arm, nm, len(pairs) - len(viol), len(pairs), lens, viol))

    if run("tables"):
        out("== CANONICAL 13 COUNTED tables (own code)")
        for arm in ("fmOFF", "fmDRY", "f2IDD", "f2U0D", "f2U1D"):
            rr = [S(arm, t) for t in CAN if S(arm, t) is not None]
            out("  %-6s n %d r/d/ffd %d/%d/%d ffd(ff_steps) %d nd %d unreach %d nonterm %d ever %d clr %d intact %d b240 %d b240_bi %d "
                "E1 %s E2 %s engaged %d eng<=T %d eng>T %d eo_blocked %d rescued(victim_steps) %d" % (
                    arm, len(rr), tot(rr, "rescued"), tot(rr, "dead"), tot(rr, "ffd"), tot(rr, "ffd_steps"), tot(rr, "nd"),
                    tot(rr, "unreach"), sum(1 for r in rr if r["term"] is None), tot(rr, "ever"), tot(rr, "cleared"),
                    tot(rr, "intact"), tot(rr, "b240"), tot(rr, "b240_bi"), pct(tot(rr, "e1n"), tot(rr, "e1d")),
                    pct(tot(rr, "e2n"), tot(rr, "e2d")), tot(rr, "engaged"), tot(rr, "eng_le"), tot(rr, "eng_after"),
                    sum(r["fm2p"]["engage_only_blocked_calls"] for r in rr), tot(rr, "resc_vs")))
            D = [x for r in rr for x in r["deaths"]]
            out("         deaths %d engaged %d prev %d streak %d preempted %d after_T %d full %d" % (
                len(D), sum(x["engaged"] for x in D), sum(x["prev"] for x in D), sum(x["streak"] for x in D),
                sum(x["pre"] for x in D), sum(x["after"] for x in D), sum(x["full"] for x in D)))
        for arm in ("f2U0D", "f2U1D"):
            for ref in ("fmOFF", "fmDRY"):
                dirs = collections.Counter()
                fl = []
                for t in CAN:
                    a, b = S(arm, t), S(ref, t)
                    di = a["intact"] - b["intact"]
                    dirs["up" if di > 0 else "down" if di < 0 else "unch"] += 1
                    f = [(v, b["victims"].get(v), a["victims"].get(v)) for v in sorted(set(a["victims"]) | set(b["victims"]))
                         if a["victims"].get(v) != b["victims"].get(v)]
                    if f or a["rescued"] != b["rescued"] or a["dead"] != b["dead"] or a["ffd"] != b["ffd"]:
                        fl.append("%s r%+d d%+d ffd%+d %s" % (lab(t), a["rescued"] - b["rescued"], a["dead"] - b["dead"],
                                                            a["ffd"] - b["ffd"], f))
                out("  %s vs %s intact dirs %s | runs with flip %d | %s" % (
                    arm, ref, dict(dirs), sum(1 for x in fl if "[(" in x), "; ".join(fl)))
        # victim_steps last row completeness and eval consistency
        bad = []
        for arm in ("fmOFF", "fmDRY", "f2U0D", "f2U1D", "f2GD", "f2GW", "f2GF", "f2cOFF", "f2cES", "f2cF", "f2L3D", "f2L8D"):
            for t in ALL:
                r = S(arm, t)
                if r is None:
                    continue
                if len(r["victims"]) != 4:
                    bad.append((arm, lab(t), "victims in last row %d" % len(r["victims"])))
                if r["resc_vs"] != r["rescued"]:
                    bad.append((arm, lab(t), "rescued eval %d vs last row %d" % (r["rescued"], r["resc_vs"])))
                if r["ffd_steps"] != r["ffd"]:
                    bad.append((arm, lab(t), "ffd eval %d vs ff_steps %d" % (r["ffd"], r["ffd_steps"])))
                if r["b240"] != r["b240_bi"]:
                    bad.append((arm, lab(t), "b240 fgf %d vs bi %d" % (r["b240"], r["b240_bi"])))
        out("  consistency (victims/rescued/ffd/b240) problems: %d %s" % (len(bad), bad[:12]))
        ever_bi = [(lab(t), S("fmOFF", t)["ever"], S("fmOFF", t)["bi_cells"]) for t in ALL]
        out("  fmOFF ever(has_burned) vs cells with any burn interval: %s" % [x for x in ever_bi if x[1] != x[2]][:6])

    if run("r1"):
        out("== ROUND-1 first firefight_log row per run; ff_steps/firefight_log alignment")
        for arm in ("fmF", "fmFS", "fmES", "fmEFS", "fmDRY"):
            frs = collections.Counter(S(arm, t)["first_row"] for t in ALL)
            out("  %-6s first_row distribution %s" % (arm, dict(frs)))
        # alignment: row cell (pre-action) == ff_steps[step-2] position for that unit
        ok = bad = 0
        for t in ALL:
            d = load("fmDRY", t)
            pos = collections.defaultdict(dict)
            for i, row in enumerate(d["ff_steps"]):
                for ff, pp, *_ in row:
                    pos[ff][i + 1] = tuple(pp) if pp is not None else None
            for r in d["firefight_log"]:
                if r["step"] >= 2:
                    if pos[r["ff"]].get(r["step"] - 1) == tuple(r["cell"]):
                        ok += 1
                    else:
                        bad += 1
        out("  fmDRY rows with cell == ff_steps[step-2] pos: %d ok, %d not" % (ok, bad))
        for arm in ("fmF", "fmFS", "fmES", "fmEFS", "fmDRY"):
            dist = collections.Counter(first_div(S(arm, t)["ff_steps"], S("fmOFF", t)["ff_steps"]) for t in ALL)
            out("  %-6s first ff_steps divergence from fmOFF (step: runs) %s" % (arm, dict(dist)))
        out("== GATE controls on round-1")
        v = pre = 0
        for t in ALL:
            a, b = S("fmREF", t), S("fmOFF", t)
            v += int((a["rescued"], a["dead"]) != (b["rescued"], b["dead"]))
            pre += sum(1 for x, y in zip(a["ff_steps"], b["ff_steps"]) if x == y)
        out("  fmREF vs fmOFF: r/d differ runs %d; ff_steps equal steps %d/%d" % (v, pre, 23 * STEPS))
        diff = sorted(lab(t) for t in ALL if (S("fmF", t)["rescued"], S("fmF", t)["dead"]) != (S("fmOFF", t)["rescued"], S("fmOFF", t)["dead"]))
        out("  fmF vs fmOFF runs whose rescued/dead differ: %d %s" % (len(diff), diff))
        out("== CRN-attribution logic on round-1 writing arms vs fmOFF")
        for arm in ("fmF", "fmFS", "fmES", "fmEFS"):
            for nm, tt in (("canonical", CAN), ("fresh", FRE), ("all23", ALL)):
                ident = exact = 0
                viol = []
                for t in tt:
                    a, b = S(arm, t), S("fmOFF", t)
                    dv = first_div(a["digests"], b["digests"])
                    fw = a["first_write"]
                    if fw is None and dv is None:
                        ident += 1
                    elif fw is not None and dv == fw:
                        exact += 1
                    else:
                        viol.append((lab(t), fw, dv))
                out("  %-6s %-9s identical %d exact %d violations %s" % (arm, nm, ident, exact, viol))
        out("== 23-run report numbers")
        for arm in ("fmOFF", "fmEFS", "fmDRY"):
            rr = [S(arm, t) for t in ALL]
            D = [x for r in rr for x in r["deaths"]]
            out("  %-6s r/d/ffd %d/%d/%d intact %d E1 %s E2 %s deaths %d streak %d preempted %d afterT %d engaged %d prev %d full %d" % (
                arm, tot(rr, "rescued"), tot(rr, "dead"), tot(rr, "ffd"), tot(rr, "intact"),
                pct(tot(rr, "e1n"), tot(rr, "e1d")), pct(tot(rr, "e2n"), tot(rr, "e2d")), len(D),
                sum(x["streak"] for x in D), sum(x["pre"] for x in D), sum(x["after"] for x in D),
                sum(x["engaged"] for x in D), sum(x["prev"] for x in D), sum(x["full"] for x in D)))
        out("  fmEFS - fmOFF intact (23): %+d" % (tot([S("fmEFS", t) for t in ALL], "intact") - tot([S("fmOFF", t) for t in ALL], "intact")))

    if run("live"):
        out("== FULL-DATA BY-CONSTRUCTION CHECKS on real f2 runs (pool complete)")
        for arm in ("f2GD", "f2GW", "f2GF"):
            ov, pv, steps = [], [], 0
            early = []
            for t in ALL:
                a, b = S(arm, t), S("fmOFF", t)
                if a is None or b is None:
                    continue
                if (a["rescued"], a["dead"]) != (b["rescued"], b["dead"]):
                    ov.append("%s %d/%d vs %d/%d" % (lab(t), a["rescued"], a["dead"], b["rescued"], b["dead"]))
                fr = a["first_row"]
                n = STEPS if fr is None else max(0, fr - 1)
                steps += n
                dv = first_div(a["ff_steps"][:n], b["ff_steps"][:n])
                if dv is not None:
                    pv.append("%s differs at %d (first row %s)" % (lab(t), dv, fr))
                if a["term"] is None or (fr is not None and fr <= a["term"]):
                    early.append("%s row %s T %s engaged<=T %d gate_closed %d" % (lab(t), fr, a["term"], a["eng_le"],
                                                                               a["fm2p"]["gate_closed_calls"]))
            out("  %-5s outcome viol %d %s" % (arm, len(ov), ov))
            out("        prefix viol %d (%d steps) %s" % (len(pv), steps, pv))
            out("        runs where first row <= terminal or terminal None: %d %s" % (len(early), early))
            out("        fm2p present %d/23, cfg %s" % (sum(1 for t in ALL if S(arm, t)["fm2p_present"]), S(arm, ALL[0])["cfg"]))
        for arm in ("f2cES", "f2cF"):
            ident = exact = 0
            viol = []
            for t in ALL:
                a, b = S(arm, t), S("f2cOFF", t)
                dv = first_div(a["digests"], b["digests"])
                fw = a["first_write"]
                if fw is None and dv is None:
                    ident += 1
                elif fw is not None and dv == fw:
                    exact += 1
                else:
                    viol.append((lab(t), fw, dv))
            out("  %-5s vs f2cOFF: identical %d exact %d violations %d %s" % (arm, ident, exact, len(viol), viol))
        for arm in ("f2U0D", "f2U1D", "f2L3D", "f2L8D", "f2GD", "f2GW", "f2GF", "f2cOFF", "f2cES", "f2cF"):
            for nm, tt in (("canonical", CAN), ("fresh", FRE)):
                rr = [S(arm, t) for t in tt]
                out("  %-6s %-9s r/d/ffd %d/%d/%d intact %d E1 %s leash %d gate_closed %d eo_blocked %d crn %d" % (
                    arm, nm, tot(rr, "rescued"), tot(rr, "dead"), tot(rr, "ffd"), tot(rr, "intact"),
                    pct(tot(rr, "e1n"), tot(rr, "e1d")), sum(r["fm2p"]["leash_dropped"] for r in rr),
                    sum(r["fm2p"]["gate_closed_calls"] for r in rr), sum(r["fm2p"]["engage_only_blocked_calls"] for r in rr),
                    sum(r["fm2p"]["crn_draws"] for r in rr)))
        # gate opening vs terminal_step, independently
        rel = collections.Counter()
        for t in ALL:
            a = S("f2GD", t)
            fr, tm = a["first_row"], a["term"]
            alive_after = None
            if tm is not None:
                last = a["ff_steps"][min(tm, STEPS - 1)]
                alive_after = sum(1 for row in last if not row[5])
            rel["row=None T=None" if fr is None and tm is None else
                "row=None T=%s alive_after_T=%s" % (tm, alive_after) if fr is None else
                "row-T=%s" % (fr - tm if tm is not None else "T None")] += 1
        out("  f2GD first row relative to terminal_step: %s" % dict(rel))
        # dedup premise: east/def and east/half with the same seed share the fire
        for arm in ("fmOFF", "f2cOFF", "f2cES", "f2cF"):
            out("  %-6s east/def vs east/half same-seed fire identical: %s" % (
                arm, [(s, first_div(S(arm, ("east", "def", s))["digests"], S(arm, ("east", "half", s))["digests"]))
                      for s in (101, 202, 303)]))
        # 'ever' (has_burned) vs burning-at-240 cells with has_burned 0
        gap = []
        for t in ALL[:6]:
            d = load("fmOFF", t)
            fg = d["fire_ground_final"]
            n001 = sum(1 for v in fg.values() if not v[0] and v[2])
            gap.append((lab(t), sum(1 for v in d["burn_intervals"].values() if v) - sum(1 for v in fg.values() if v[0]), n001))
        out("  fmOFF (cells with a burn interval - has_burned) vs cells burning@240 with has_burned 0: %s" % gap)
        # f2cOFF vs fmOFF: CRN changes fire realisation (expect differ)
        same = sum(1 for t in ALL if first_div(S("f2cOFF", t)["digests"], S("fmOFF", t)["digests"]) is None)
        out("  f2cOFF fire identical to fmOFF (stock RNG) on %d/23 runs (expected ~0)" % same)


if __name__ == "__main__":
    main()
