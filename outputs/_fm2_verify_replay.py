"""Adversarial verification of TASK E (fire-only replay). Read-only except stdout.

Independent of outputs/_fm2_fire_replay.py (never imported). Modes:
  data    raw harness JSON checks (writes, intact, d_all, attribution, identities, wall_s)
  study   recompute every study statistic from the analyst's replay OUTPUT JSONs with own code
  draws   check recorded .draws files against burnt sets / draws_per_tick / pin counts
  logs    parse batch logs (rc, per-process wall)
  replay  OWN independent fire replay of one harness run (writes all|none), digest vs harness
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import os
import random
import re
import statistics
import sys
import time
from array import array

REPO = "E:/Projects/SAS"
OUTD = os.path.join(REPO, "outputs")
SCR = "C:/Users/ahrar/AppData/Local/Temp/claude/E--Projects-SAS/4822f5f0-3ec2-4a14-8aeb-d97eb91ddf5a/scratchpad/replay"
CELLS = 2500
CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "def", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
VALID = ([("fmOFF", t, "none") for t in (("east", "half", 101), ("south", "half", 404), ("east", "def", 202), ("south", "half", 909))]
         + [("fmES", t, "all") for t in (("east", "half", 101), ("south", "half", 404), ("east", "def", 202))]
         + [("fmF", t, "all") for t in (("east", "half", 404), ("south", "half", 404), ("east", "def", 303))]
         + [("fmEFS", t, "all") for t in (("south", "half", 303), ("east", "def", 101), ("south", "half", 505))])

_cache = {}


def hpath(tag, t):
    return os.path.join(OUTD, "_ffr_%s_%s_%s_%d.json" % (tag, t[0], t[1], t[2]))


def rpath(tag, t, spec, suffix=""):
    return os.path.join(SCR, "rp_%s_%s_%s_%d_%s%s.json" % (tag, t[0], t[1], t[2], spec, suffix))


def load(p):
    if p not in _cache:
        with open(p, encoding="utf-8") as f:
            _cache[p] = json.load(f)
    return _cache[p]


def lab(t):
    return "%s/%s/%d" % t


def h_intact(d):
    fgf = d["fire_ground_final"]
    assert len(fgf) == CELLS, len(fgf)
    ever = sum(1 for v in fgf.values() if v[0])
    cleared = int(d.get("fire_cleared_unburned_final") or 0)
    return ever, cleared, CELLS - ever - cleared


def wrows(d):
    return [r for r in (d.get("firefight_log") or []) if r.get("wrote")]


def first_div(a, b):
    n = min(len(a), len(b))
    return next((k + 1 for k in range(n) if a[k] != b[k]), None), sum(1 for k in range(n) if a[k] == b[k]), n


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def med(v):
    return statistics.median(v) if v else None


def pearson(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else float("nan")


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


# ------------------------------------------------------------------ data ---
def mode_data():
    print("== VALIDATION TUPLES: write counts and intact from raw harness JSON")
    for tag, t, spec in VALID:
        d = load(hpath(tag, t))
        w = wrows(d)
        ne = sum(1 for r in w if r["action"] == "extinguish")
        nc = sum(1 for r in w if r["action"] == "clear")
        other = sum(1 for r in w if r["action"] not in ("extinguish", "clear"))
        tgt_bad = sum(1 for r in w if r.get("plan") != r["action"])
        print("  %-6s %-15s writes %3d (ext %3d clear %3d other %d plan!=action %d) ever/cleared/intact %s wall_s %s" % (
            tag, lab(t), len(w), ne, nc, other, tgt_bad, h_intact(d), d.get("wall_s")))
    walls = [load(hpath(tag, t)).get("wall_s") for tag, t, _ in VALID]
    print("  harness wall_s over the 13 validation runs: min %.1f max %.1f" % (min(walls), max(walls)))
    wo = [load(hpath("fmOFF", t)).get("wall_s") for tag, t, _ in VALID]
    print("  fmOFF wall_s over the 13 validation tuples: min %.1f max %.1f" % (min(wo), max(wo)))
    allw = [load(hpath(tag, t)).get("wall_s") for tag in ("fmOFF", "fmES", "fmF", "fmEFS") for t in CANON + FRESH]
    print("  harness wall_s all 4 arms x 23 tuples: min %.1f max %.1f" % (min(allw), max(allw)))

    print("== d_all (intact arm - intact fmOFF), per tuple")
    for tag, action in (("fmES", "extinguish"), ("fmF", "clear")):
        rows = []
        for sample, tuples in (("canon", CANON), ("fresh", FRESH)):
            for t in tuples:
                a, o = load(hpath(tag, t)), load(hpath("fmOFF", t))
                w = wrows(a)
                n_act = sum(1 for r in w if r["action"] == action)
                n_oth = len(w) - n_act
                da = h_intact(a)[2] - h_intact(o)[2]
                rows.append((sample, t, da, len(w), n_act, n_oth, (w[0]["step"], tuple(w[0]["target"]), w[0]["action"]) if w else None))
        for r in rows:
            print("  %-5s %-5s %-16s d_all %+5d writes %3d %s %3d other %d first %s" % (tag, r[0], lab(r[1]), r[2], r[3], action[:3], r[4], r[5], r[6]))

        def summ(sel, name):
            v = [r[2] for r in sel]
            print("  %-5s %-8s n=%2d sum %+6d pos/neg/0 %d/%d/%d med|.| %s" % (
                tag, name, len(v), sum(v), sum(1 for x in v if x > 0), sum(1 for x in v if x < 0), sum(1 for x in v if x == 0),
                med([abs(x) for x in v])))
        summ([r for r in rows if r[0] == "canon"], "canon")
        summ([r for r in rows if r[0] == "fresh"], "fresh")
        summ(rows, "counted")
        summ([r for r in rows if r[1][1] != "def"], "dedup")
        wt = [r for r in rows if r[4] >= 1]
        summ(wt, ">=1 " + action[:3])
        summ([r for r in wt if r[0] == "fresh"], "fresh w/")
        print("  %s tuples with >=1 %s: %d; without: %s" % (tag, action, len(wt), [lab(r[1]) for r in rows if r[4] == 0]))

    print("== zero-write arm tuples: fire digests vs fmOFF")
    for tag in ("fmES", "fmF", "fmEFS"):
        for t in CANON + FRESH:
            a = load(hpath(tag, t))
            if not wrows(a):
                fd, m, n = first_div(a["fire_digests"], load(hpath("fmOFF", t))["fire_digests"])
                print("  %-5s %-16s 0 writes: digest %d/%d first_div %s" % (tag, lab(t), m, n, fd))

    print("== east/def vs east/half fmOFF fire identity")
    for s in (101, 202, 303):
        fd, m, n = first_div(load(hpath("fmOFF", ("east", "def", s)))["fire_digests"], load(hpath("fmOFF", ("east", "half", s)))["fire_digests"])
        print("  seed %d: %d/%d first_div %s" % (s, m, n, fd))

    print("== attribution from raw JSON: arm first digest divergence vs fmOFF == first write step")
    for tag in ("fmES", "fmF", "fmEFS"):
        ok = bad = none = 0
        for t in CANON + FRESH:
            a, o = load(hpath(tag, t)), load(hpath("fmOFF", t))
            w = wrows(a)
            fd, m, n = first_div(a["fire_digests"], o["fire_digests"])
            fw = w[0]["step"] if w else None
            if fw is None:
                none += 1 if fd is None else 0
                continue
            if fd == fw:
                ok += 1
            else:
                bad += 1
                print("   MISMATCH %s %s first_div %s first write %s" % (tag, lab(t), fd, fw))
        print("  %-5s first_div == first write %d, mismatch %d, zero-write identical %d" % (tag, ok, bad, none))
    for tag, t, spec in VALID:
        if tag == "fmOFF":
            continue
        a, o = load(hpath(tag, t)), load(hpath("fmOFF", t))
        fd, _, _ = first_div(a["fire_digests"], o["fire_digests"])
        print("  validation %-5s %-15s first write %s (%s) first_div %s" % (tag, lab(t), wrows(a)[0]["step"], wrows(a)[0]["action"], fd))


# ------------------------------------------------------------------ study --
class Trace:
    def __init__(self, d):
        self.d = d
        self.cells = [(c[1], c[2]) for c in d["fires"]]
        self.uid = [c[0] for c in d["fires"]]
        cur = set(d["initial_burning"])
        self.burning = []
        for on, off in zip(d["burning_on"], d["burning_off"]):
            cur = (cur - set(off)) | set(on)
            self.burning.append(frozenset(cur))
        cum = set()
        self.burnt = []
        for new in d["burnt_new"]:
            cum |= set(new)
            self.burnt.append(frozenset(cum))
        self.has_burned = set(d["final_has_burned"])
        self.cleared = set(d["final_cleared"])
        self.intact = CELLS - len(self.has_burned) - len(self.cleared)
        assert self.intact == d["final"]["intact"], (self.intact, d["final"])
        assert len(self.burning) == 240 and len(self.digests()) == 240


    def digests(self):
        return self.d["digests"]


def harness_burning(d, idx_of):
    sets = [set() for _ in range(240)]
    for key, ivs in (d.get("burn_intervals") or {}).items():
        x, y = (int(v) for v in key.split(","))
        i = idx_of[(x, y)]
        for a, b in ivs:
            for s in range(a, 241 if b is None else b):
                sets[s - 1].add(i)
    return [frozenset(s) for s in sets]


def cone_first_out(A, B, t, c, cells, start=None):
    pre = 0
    first_burn = None
    first_out = None
    info = None
    for k in range(240):
        s = k + 1
        D = A[k] ^ B[k]
        if not D:
            continue
        if first_burn is None:
            first_burn = s
        if s < t:
            pre += 1
            continue
        r = 3 * (s // 3 - t // 3)
        outs = [cheb(cells[i], c) for i in D if cheb(cells[i], c) > r]
        if outs and first_out is None:
            first_out = s
            info = (r, len(outs), len(D), max(outs))
    return first_burn, first_out, info, pre


def mode_study():
    rows = []
    checks = {"none_digest_ok": 0, "none_intact_ok": 0, "only_sel_ok": 0, "drop_sel_ok": 0, "fires_same": 0,
              "pre_t_diff": 0, "fb_not_tick": 0, "only_digest_prefix_ok": 0}
    for tag, action in (("fmES", "extinguish"), ("fmF", "clear")):
        for sample, tuples in (("canon", CANON), ("fresh", FRESH)):
            for t in tuples:
                arm, off = load(hpath(tag, t)), load(hpath("fmOFF", t))
                w = wrows(arm)
                if sum(1 for r in w if r["action"] == action) == 0:
                    continue
                dn, do, dd, dp = (load(rpath("fmOFF", t, "none")), load(rpath(tag, t, "only-first")),
                                  load(rpath(tag, t, "drop-first")), load(rpath(tag, t, "only-first", "_pin")))
                N, O, Dr, P = Trace(dn), Trace(do), Trace(dd), Trace(dp)
                if N.cells == O.cells == Dr.cells == P.cells:
                    checks["fires_same"] += 1
                cells = N.cells
                idx_of = {c: i for i, c in enumerate(cells)}
                SO = h_intact(off)[2]
                SA = h_intact(arm)[2]
                fdn, mn, nn = first_div(dn["digests"], off["fire_digests"])
                checks["none_digest_ok"] += int(mn == 240)
                checks["none_intact_ok"] += int(N.intact == SO)
                f0 = w[0]
                c0 = (int(f0["target"][0]), int(f0["target"][1]))
                sel = do["writes_selected"]
                if (len(sel) == 1 and sel[0]["step"] == f0["step"] and tuple(sel[0]["cell"]) == c0
                        and sel[0]["action"] == f0["action"] == action and sel[0]["applied"] is True):
                    checks["only_sel_ok"] += 1
                else:
                    print("  ONLY SEL PROBLEM", tag, lab(t), sel, f0["step"], f0["action"])
                seld = dd["writes_selected"]
                if [(x["step"], tuple(x["cell"]), x["action"]) for x in seld] == [
                        (r["step"], (int(r["target"][0]), int(r["target"][1])), r["action"]) for r in w[1:]]:
                    checks["drop_sel_ok"] += 1
                tw = f0["step"]
                fdo, _, _ = first_div(do["digests"], off["fire_digests"])
                if fdo == tw:
                    checks["only_digest_prefix_ok"] += 1
                # shift: first differing burnt set (only-first vs none)
                fb = next((k + 1 for k in range(240) if O.burnt[k] != N.burnt[k]), None)
                shift = None
                fb_cells = None
                if fb is not None:
                    if fb % 3 != 0:
                        checks["fb_not_tick"] += 1
                    shift = fb + 3
                    fb_cells = O.burnt[fb - 1] ^ N.burnt[fb - 1]
                fbu, fout, info, pre = cone_first_out(O.burning, N.burning, tw, c0, cells)
                checks["pre_t_diff"] += pre
                far = max(cheb(c, c0) for c in cells)
                cover = (tw // 3 + (-(-far // 3))) * 3
                sym = O.has_burned ^ N.has_burned
                sd = [cheb(cells[i], c0) for i in sym]
                pfb, pout, pinfo, ppre = cone_first_out(P.burning, N.burning, tw, c0, cells)
                psym = P.has_burned ^ N.has_burned
                psd = [cheb(cells[i], c0) for i in psym]
                # drop-first vs arm (harness)
                HA = harness_burning(arm, idx_of)
                drop_burn_diff = next((k + 1 for k in range(240) if Dr.burning[k] != HA[k]), None)
                arm_hb = set(idx_of[tuple(int(v) for v in k.split(","))] for k, v in arm["fire_ground_final"].items() if v[0])
                drop_sym = len(Dr.has_burned ^ arm_hb)
                # arm vs only-first: shared change
                O_vs_arm_burn = next((k + 1 for k in range(240) if O.burning[k] != HA[k]), None)
                second_write = w[1]["step"] if len(w) > 1 else None
                shared = sum(1 for i in sym if (i in arm_hb) == (i in O.has_burned))
                rows.append({
                    "tag": tag, "sample": sample, "t": t, "nW": len(w), "tw": tw, "c0": c0,
                    "scorched": f0.get("scorched"), "uid0": N.uid[idx_of[c0]],
                    "d_all": SA - SO, "d_only": O.intact - SO, "d_drop": Dr.intact - SO, "d_pin": P.intact - SO,
                    "fdo": fdo, "fb": fb, "shift": shift, "shift_min_uid": (min(N.uid[i] for i in fb_cells) if fb_cells else None),
                    "fb_has_c0": (idx_of[c0] in fb_cells) if fb_cells else None,
                    "burn1": fbu, "out": fout, "out_info": info, "cover": cover,
                    "sym": len(sym), "sym_gt20": sum(1 for x in sd if x > 20), "sym_le3": sum(1 for x in sd if x <= 3),
                    "pout": pout, "psym": len(psym), "pmax": max(psd) if psd else None,
                    "pin_fallback": dp["pin_counts"]["fallback"], "pin_pinned": dp["pin_counts"]["pinned"],
                    "drop_sel": len(seld), "drop_notapplied": sum(1 for x in seld if not x["applied"]),
                    "drop_burn_diff": drop_burn_diff, "drop_sym": drop_sym,
                    "O_vs_arm_burn1": O_vs_arm_burn, "second_write": second_write, "shared_frac": (shared / len(sym)) if sym else None,
                })
    print("== STUDY integrity checks:", checks, "rows", len(rows))
    print("  tag   tuple            nW   tw  cell   sc d_all d_only d_drop d_pin | fdo  burn1 fb shift out (r,nout,ndiff,max) cover | sym >20 <=3 | pout psym pmax | fb_has_c0 minuid==uid0 | drop notap/sel burn_diff sym | 2nd_w O_vs_arm shared")
    for x in rows:
        print("  %-4s %-16s %4d %4d %-7s %s %+5d %+6d %+6d %+5d | %4s %4s %4s %4s %4s %-18s %4s | %4d %4d %3d | %4s %4d %4s | %s %s | %3d/%4d %4s %4d | %4s %4s %s" % (
            x["tag"][2:], lab(x["t"]), x["nW"], x["tw"], "%d,%d" % x["c0"], {True: "y", False: "n", None: "-"}[x["scorched"]],
            x["d_all"], x["d_only"], x["d_drop"], x["d_pin"], x["fdo"], x["burn1"], x["fb"], x["shift"], x["out"], x["out_info"],
            x["cover"], x["sym"], x["sym_gt20"], x["sym_le3"], x["pout"], x["psym"], x["pmax"], x["fb_has_c0"],
            (x["shift_min_uid"] == x["uid0"]) if x["shift_min_uid"] is not None else None,
            x["drop_notapplied"], x["drop_sel"], x["drop_burn_diff"], x["drop_sym"], x["second_write"], x["O_vs_arm_burn1"],
            ("%.2f" % x["shared_frac"]) if x["shared_frac"] is not None else None))

    for tag in ("fmES", "fmF"):
        for name in ("canon", "fresh", "both", "dedup"):
            xs = [x for x in rows if x["tag"] == tag and (name in ("both", "dedup") or x["sample"] == name)
                  and not (name == "dedup" and x["t"][1] == "def")]
            da = [x["d_all"] for x in xs]
            do = [x["d_only"] for x in xs]
            dr = [x["d_drop"] for x in xs]
            dp = [x["d_pin"] for x in xs]
            sh = [x for x in xs if x["shift"] is not None and x["shift"] <= 240]
            outs = [x for x in xs if x["out"] is not None]
            print("\n  %s %s n=%d" % (tag, name, len(xs)))
            print("    med|d_all| %s  med|d_only| %s  mean|d_only| %.1f mean|d_all| %.1f  sum d_all %+d sum d_only %+d  d_only pos/neg/0 %d/%d/%d range [%+d,%+d]" % (
                med([abs(v) for v in da]), med([abs(v) for v in do]), sum(abs(v) for v in do) / len(do), sum(abs(v) for v in da) / len(da),
                sum(da), sum(do), sum(1 for v in do if v > 0), sum(1 for v in do if v < 0), sum(1 for v in do if v == 0), min(do), max(do)))
            print("    med |d_only|/|d_all| %s  same sign %d opposite %d  pearson(only,all) %.2f spearman %.2f  pearson(drop,all) %.2f spearman %.2f" % (
                med([abs(a) / abs(b) for a, b in zip(do, da) if b]), sum(1 for a, b in zip(do, da) if a * b > 0),
                sum(1 for a, b in zip(do, da) if a * b < 0), pearson(do, da), spearman(do, da), pearson(dr, da), spearman(dr, da)))
            print("    only-first fdo==tw %d/%d  shift<=240 %d  shift lags %s" % (
                sum(1 for x in xs if x["fdo"] == x["tw"]), len(xs), len(sh), sorted(x["shift"] - x["tw"] for x in sh)))
            print("    fb lags %s" % sorted(x["fb"] - x["tw"] for x in xs if x["fb"] is not None))
            print("    leaves cone %d  out==shift %d  out<shift %d  out lags %s" % (
                len(outs), sum(1 for x in outs if x["out"] == x["shift"]), sum(1 for x in outs if x["shift"] is None or x["out"] < x["shift"]),
                sorted(x["out"] - x["tw"] for x in outs)))
            print("    symdiff total %d >20 %d (%.1f%%) <=3 %d" % (sum(x["sym"] for x in xs), sum(x["sym_gt20"] for x in xs),
                                                             100.0 * sum(x["sym_gt20"] for x in xs) / max(1, sum(x["sym"] for x in xs)), sum(x["sym_le3"] for x in xs)))
            print("    d_pin values %s zero %d  pinned leaves cone %d  psym total %d pmax %s  med|d_only-d_pin| %s mean %.1f mean|d_pin| %.1f fallback total %d" % (
                sorted(dp), sum(1 for v in dp if v == 0), sum(1 for x in xs if x["pout"] is not None), sum(x["psym"] for x in xs),
                max((x["pmax"] or 0) for x in xs), med([abs(a - b) for a, b in zip(do, dp)]), sum(abs(a - b) for a, b in zip(do, dp)) / len(xs),
                sum(abs(v) for v in dp) / len(dp), sum(x["pin_fallback"] for x in xs)))
            print("    |d_drop-d_all| %s med %s  drop no burning diff vs arm %d  drop has_burned identical %d  drop not applied %d/%d" % (
                sorted(abs(a - b) for a, b in zip(dr, da)), med([abs(a - b) for a, b in zip(dr, da)]),
                sum(1 for x in xs if x["drop_burn_diff"] is None), sum(1 for x in xs if x["drop_sym"] == 0),
                sum(x["drop_notapplied"] for x in xs), sum(x["drop_sel"] for x in xs)))
            print("    cover lag range %s-%s  shift<cover %d (of which out %d)  scorched %d  fb at written cell %d other %d  shift min uid == write uid %d/%d" % (
                min(x["cover"] - x["tw"] for x in xs), max(x["cover"] - x["tw"] for x in xs),
                sum(1 for x in xs if x["shift"] is not None and x["shift"] < x["cover"]),
                sum(1 for x in xs if x["shift"] is not None and x["shift"] < x["cover"] and x["out"] is not None),
                sum(1 for x in xs if x["scorched"]), sum(1 for x in xs if x["fb_has_c0"] is True), sum(1 for x in xs if x["fb_has_c0"] is False),
                sum(1 for x in xs if x["shift_min_uid"] is not None and x["shift_min_uid"] == x["uid0"]), sum(1 for x in xs if x["shift_min_uid"] is not None)))
            if tag == "fmES":
                print("    second write before shift tick %d, at/after %d; only-first vs arm first burning diff before shift %d" % (
                    sum(1 for x in xs if x["second_write"] is not None and x["shift"] is not None and x["second_write"] < x["shift"]),
                    sum(1 for x in xs if x["second_write"] is not None and x["shift"] is not None and x["second_write"] >= x["shift"]),
                    sum(1 for x in xs if x["O_vs_arm_burn1"] is not None and x["shift"] is not None and x["O_vs_arm_burn1"] < x["shift"])))


def mode_inherit():
    """Does the fmES ARM inherit the only-first re-roll? At the shift tick S (only-first vs none) and
    later ticks, take burning differences O^N lying OUTSIDE the light cone of every arm write made
    up to that step; if the arm's draw stream equals only-first's there, the arm must agree with O
    on those cells (a physical influence cannot reach them)."""
    for tag in ("fmES",):
        tot_agree = tot_n = 0
        for t in CANON + FRESH:
            arm, off = load(hpath(tag, t)), load(hpath("fmOFF", t))
            w = wrows(arm)
            if not w:
                continue
            N, O = Trace(load(rpath("fmOFF", t, "none"))), Trace(load(rpath(tag, t, "only-first")))
            cells = N.cells
            idx_of = {c: i for i, c in enumerate(cells)}
            HA = harness_burning(arm, idx_of)
            fb = next((k + 1 for k in range(240) if O.burnt[k] != N.burnt[k]), None)
            if fb is None:
                print("  %-16s no shift" % lab(t))
                continue
            S = fb + 3
            s1 = w[0]["step"]
            same_tick_writes = [r["step"] for r in w[1:] if (r["step"] // 3 + 1) * 3 <= fb]
            out = []
            for s in (S, S + 3, S + 6, S + 12):
                if s > 240:
                    continue
                D = O.burning[s - 1] ^ N.burning[s - 1]
                ws = [(r["step"], (int(r["target"][0]), int(r["target"][1]))) for r in w if r["step"] <= s]
                far = [i for i in D if all(cheb(cells[i], c) > 3 * (s // 3 - st // 3) for st, c in ws)]
                agreeO = sum(1 for i in far if (i in HA[s - 1]) == (i in O.burning[s - 1]))
                out.append("s=%d far %d agreeO %d" % (s, len(far), agreeO))
                if s == S:
                    tot_agree += agreeO
                    tot_n += len(far)
            print("  %-16s w1 %3d fb %3d S %3d arm writes before w1's burnt tick (would share tick) %s | %s" % (
                lab(t), s1, fb, S, same_tick_writes, " ; ".join(out)))
        print("  at S: agree with only-first %d of %d out-of-every-cone cells" % (tot_agree, tot_n))


def mode_pinphys():
    """Physical footprint of one write in the PINNED replay beyond the final has_burned count:
    cells whose burning history differs at any step, cells whose burnt (burn-out) step differs."""
    for tag, action in (("fmF", "clear"), ("fmES", "extinguish")):
        agg = []
        for t in CANON + FRESH:
            arm = load(hpath(tag, t))
            w = wrows(arm)
            if sum(1 for r in w if r["action"] == action) == 0:
                continue
            N, P = Trace(load(rpath("fmOFF", t, "none"))), Trace(load(rpath(tag, t, "only-first", "_pin")))
            c0 = (int(w[0]["target"][0]), int(w[0]["target"][1]))
            cells = N.cells
            ever = set()
            for k in range(240):
                ever |= (P.burning[k] ^ N.burning[k])
            bt_n, bt_p = {}, {}
            for k in range(240):
                for i in N.burnt[k]:
                    bt_n.setdefault(i, k + 1)
                for i in P.burnt[k]:
                    bt_p.setdefault(i, k + 1)
            burnt_diff = set(i for i in set(bt_n) | set(bt_p) if bt_n.get(i) != bt_p.get(i))
            other = [i for i in ever if cells[i] != c0]
            other_b = [i for i in burnt_diff if cells[i] != c0]
            agg.append((lab(t), len(ever), len(other), max((cheb(cells[i], c0) for i in ever), default=None),
                        len(burnt_diff), len(other_b), P.intact - N.intact))
        print("  %s pinned: tuple, cells with any burning-history diff, of which not the written cell, max dist, cells with differing burn-out step, not written cell, d_pin" % tag)
        for a in agg:
            print("    %-16s hist %4d other %4d maxd %4s | burnout %4d other %4d | d_pin %+d" % a)
        print("    runs with another cell's burning history changed: %d/%d ; another cell's burn-out step changed: %d/%d" % (
            sum(1 for a in agg if a[2] > 0), len(agg), sum(1 for a in agg if a[5] > 0), len(agg)))


def mode_misc():
    print("== the 13 validation replay OUTPUTS (analyst) vs harness: digests, burning sets, writes, counters, final")
    for tag, t, spec in VALID:
        d = load(rpath(tag, t, spec))
        h = load(hpath(tag, t))
        T = Trace(d)
        idx_of = {c: i for i, c in enumerate(T.cells)}
        HB = harness_burning(h, idx_of)
        fd, m, n = first_div(d["digests"], h["fire_digests"])
        bdiff = sum(1 for k in range(240) if HB[k] != T.burning[k])
        hb = set(idx_of[tuple(int(v) for v in k.split(","))] for k, v in h["fire_ground_final"].items() if v[0])
        print("  %-5s %-15s %-4s digest %d/%d burning-set diff steps %d writes sel %d failed %d notapplied %d ctr_bad %d intact %d vs %d has_burned identical %s record_draws %s" % (
            tag, lab(t), spec, m, n, bdiff, len(d["writes_selected"]), len(d["writes_failed"]),
            sum(1 for x in d["writes_selected"] if not x["applied"]), d["steps_counter_mismatches"], T.intact, h_intact(h)[2],
            hb == T.has_burned, bool(d.get("record_draws"))))
    print("== all analyst replay outputs: steps_counter mismatches, stock digest-meaningful matches")
    tot = bad_ctr = 0
    for name in sorted(os.listdir(SCR)):
        if name.startswith("rp_") and name.endswith(".json"):
            d = load(os.path.join(SCR, name))
            tot += 1
            bad_ctr += int(d["steps_counter_mismatches"] != 0)
    print("  outputs %d, with steps_counter mismatches %d" % (tot, bad_ctr))
    p = rpath("fmOFF", ("east", "half", 101), "none", "_pin")
    d = load(p)
    fd, m, n = first_div(d["digests"], load(hpath("fmOFF", ("east", "half", 101)))["fire_digests"])
    print("== pin identity %s: digest %d/%d pin_counts %s" % (os.path.basename(p), m, n, d["pin_counts"]))
    for tag, t in (("fmF", ("east", "half", 404)), ("fmES", ("east", "half", 101))):
        a = load(rpath(tag, t, "only-first", "_crn"))
        b = load(rpath(tag, t, "none", "_crn"))
        print("== crn %s %s only-first writes %s ; d_intact(only-none) %+d ; crn_draws %s" % (
            tag, lab(t), a["writes_selected"], a["final"]["intact"] - b["final"]["intact"], a.get("crn_draws")))
    wo = [load(hpath("fmOFF", t)).get("wall_s") for t in CANON + FRESH]
    print("== fmOFF wall_s over 23 tuples: min %.1f max %.1f" % (min(wo), max(wo)))


# ------------------------------------------------------------------ draws --
def mode_draws():
    bad = 0
    n = 0
    for t in CANON + FRESH:
        p = rpath("fmOFF", t, "none")[:-5] + ".draws"
        if not os.path.exists(p):
            print("  no draws", lab(t))
            continue
        d = load(rpath("fmOFF", t, "none"))
        T = Trace(d)
        vals = array("d")
        with open(p, "rb") as f:
            vals.frombytes(f.read())
        nf = d["n_fire"]
        assert len(vals) == 80 * nf
        per = []
        for k in range(80):
            seg = vals[k * nf:(k + 1) * nf]
            per.append(sum(1 for v in seg if v == v))
        s_tick = [3 * (k + 1) for k in range(80)]
        from_burnt = [nf - len(T.burnt[s - 2]) for s in s_tick]
        dpt = [x[1] for x in d["draws_per_tick"]]
        ok = per == from_burnt == dpt
        # values in [0,1)
        rng_ok = all((v != v) or (0.0 <= v < 1.0) for v in vals)
        n += 1
        bad += int(not ok)
        print("  %-16s draws %d ok %s range_ok %s" % (lab(t), sum(per), ok, rng_ok))
        # pinned counts: pinned + fallback == total draws of the pinned replay
        for tag in ("fmES", "fmF"):
            pp = rpath(tag, t, "only-first", "_pin")
            if os.path.exists(pp):
                dp = load(pp)
                tot = sum(x[1] for x in dp["draws_per_tick"])
                pc = dp["pin_counts"]
                print("     %s pin pinned %d fallback %d sum %d == pinned replay draws %d: %s" % (
                    tag, pc["pinned"], pc["fallback"], pc["pinned"] + pc["fallback"], tot, pc["pinned"] + pc["fallback"] == tot))
    print("  draws files checked %d, inconsistent %d" % (n, bad))


# ------------------------------------------------------------------ logs ---
def mode_logs():
    tot = []
    rcs = {}
    for name in sorted(os.listdir(SCR)):
        if not name.startswith("batch_") or not name.endswith(".log"):
            continue
        with open(os.path.join(SCR, name), encoding="utf-8") as f:
            txt = f.read()
        done = re.findall(r"done rc=(\S+) (\d+)s", txt)
        fin = re.findall(r"finished in (\d+)s", txt)
        for rc, s in done:
            rcs[rc] = rcs.get(rc, 0) + 1
            tot.append(int(s))
        print("  %-28s done %d finished %s" % (name, len(done), fin))
    print("  processes %d rc %s wall min %d mean %.1f max %d" % (len(tot), rcs, min(tot), sum(tot) / len(tot), max(tot)))


# ------------------------------------------------------------------ replay -
def mode_replay(arm_json, writes):
    t_start = time.perf_counter()
    arm = load(arm_json)
    sys.path.insert(0, REPO)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from wildfire_model import WildFireModel
    from serve_dashboard import BUILTIN_SCENARIOS, _resolve_role_count_params
    preset = BUILTIN_SCENARIOS.get(arm["scenario"], {})
    na = int(preset.get("NUM_AGENTS", 3))
    ft, vs = _resolve_role_count_params(na, 2, 2) if arm["roles"] == "half" else _resolve_role_count_params(na, None, None)
    params = {"NUM_AGENTS": na, "NUM_VICTIMS": int(preset.get("NUM_VICTIMS", 5)),
              "NUM_FIREFIGHTERS": int(preset.get("NUM_FIREFIGHTERS", 3)), "WIND_DIRECTION": arm["wind"],
              "BATCH_SIZE": 300, "FIRE_SPREAD_MULTIPLIER": 0.75, "PROBABILITY_MAP": False,
              "NUM_FIRE_TRACKERS": ft, "NUM_VICTIM_SEARCHERS": vs}
    params.update(arm.get("extra_params") or {})
    print("params equal recorded:", params == arm["params"])
    rng = random.Random(int(arm["seed"]))
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        model = WildFireModel()
        model.debug_log = False
    print("FIXED_WIND", cfv.FIXED_WIND, "agents FIRE_SPREAD_SPEED", am.FIRE_SPREAD_SPEED, "agents FIRE_SPREAD_MULTIPLIER", am.FIRE_SPREAD_MULTIPLIER)
    all_rows = wrows(arm)
    sel = all_rows if writes == "all" else []
    by_step = {}
    for r in sel:
        by_step.setdefault(int(r["step"]), []).append(r)
    # schedule position check: every Fire agent precedes every non-Fire agent
    kinds = [type(a).__name__ == "Fire" for a in model.schedule.agents]
    nf = sum(kinds)
    print("schedule: %d agents, %d Fire, all Fire first: %s" % (len(kinds), nf, all(kinds[:nf])))
    digests = []
    wrote_ok = 0
    wrote_fail = []
    rec = arm["fire_digests"]
    first_mm = None
    with contextlib.redirect_stdout(buf):
        for t in range(1, 241):
            fires = [a for a in model.schedule.agents if type(a).__name__ == "Fire"]
            for a in fires:
                a.step()
            for a in fires:
                a.advance()
            for r in by_step.get(t, []):
                cell = (int(r["target"][0]), int(r["target"][1]))
                fire = [a for a in model.grid.get_cell_list_contents([cell]) if type(a).__name__ == "Fire"]
                assert len(fire) == 1
                ok = fire[0].firefighter_extinguish() if r["action"] == "extinguish" else fire[0].firefighter_remove_fuel()
                if ok:
                    wrote_ok += 1
                else:
                    wrote_fail.append((t, cell, r["action"]))
            parts = []
            for a in model.schedule.agents:
                if type(a).__name__ == "Fire":
                    parts.append("%s:%d%d%s" % (a.unique_id, int(bool(a.burning)), int(bool(a.burnt)), a.fuel))
            dg = hashlib.sha256("|".join(parts).encode()).hexdigest()
            digests.append(dg)
            if first_mm is None and dg != rec[t - 1]:
                first_mm = t
    match = sum(1 for k in range(240) if digests[k] == rec[k])
    fgf = {"%d,%d" % (int(a.pos[0]), int(a.pos[1])): [int(bool(a.has_burned)), int(bool(a.burnt)), int(bool(a.burning))]
           for a in model.schedule.agents if type(a).__name__ == "Fire"}
    ever = sum(1 for a in model.schedule.agents if type(a).__name__ == "Fire" and a.has_burned)
    cleared = sum(1 for a in model.schedule.agents if type(a).__name__ == "Fire" and a.fuel <= 0 and not a.has_burned)
    print("OWN REPLAY %s %s/%s/%s writes=%s selected %d wrote_ok %d failed %d digest %d/240 first_mismatch %s" % (
        arm.get("tag"), arm["wind"], arm["roles"], arm["seed"], writes, len(sel), wrote_ok, len(wrote_fail), match, first_mm))
    print("  final ever/cleared/intact %d/%d/%d harness %s ; fire_ground_final per-cell identical: %s ; cleared==harness %s" % (
        ever, cleared, CELLS - ever - cleared, h_intact(arm), fgf == arm["fire_ground_final"],
        cleared == int(arm.get("fire_cleared_unburned_final") or 0)))
    # compare with analyst's replay output for the same run, if present
    t = (arm["wind"], "def" if arm["roles"] == "default" else arm["roles"], int(arm["seed"]))
    ap = rpath(arm["tag"], t, writes)
    if os.path.exists(ap):
        ad = load(ap)
        print("  vs analyst output %s: digests identical %d/240" % (os.path.basename(ap), sum(1 for k in range(240) if ad["digests"][k] == digests[k])))
    print("  wall %.1f s" % (time.perf_counter() - t_start))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["data", "study", "draws", "logs", "replay", "inherit", "pinphys", "misc"])
    ap.add_argument("--arm-json")
    ap.add_argument("--writes", default="all", choices=["all", "none"])
    a = ap.parse_args()
    if a.mode == "data":
        mode_data()
    elif a.mode == "study":
        mode_study()
    elif a.mode == "draws":
        mode_draws()
    elif a.mode == "logs":
        mode_logs()
    elif a.mode == "inherit":
        mode_inherit()
    elif a.mode == "pinphys":
        mode_pinphys()
    elif a.mode == "misc":
        mode_misc()
    else:
        mode_replay(a.arm_json, a.writes)


if __name__ == "__main__":
    main()
