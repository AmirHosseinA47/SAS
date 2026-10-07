"""Verification helper for outputs/_mvg_probe.py and outputs/_mvg_replay.py (MVG round Part 2d; not a run-loaded file).
A port of urgency:outputs/_ud_probe_check.py (5dba5bcb) without its fix (c) / C-4 / C-5 and U1-in-the-model material,
plus the guard checks of Part 1d 1d.6.2 (Zg-1 two-sided, Zg-2, Zg-3) and the W3 tooling validation of 1d.13.4.

Every subcommand that reads a record REFUSES (exit 2, message on stderr) when a file is missing or unparseable, or a
record is not what the subcommand needs; it never guesses. Exit 0 = every check passed, 1 = a check failed.

usage (mvg worktree root, the parent .venv):
  python outputs/_mvg_probe_check.py summary X.json
      the ud / mv / mvg digest of one record (errors, kicks, rows per branch, ACTED counts, guard rows, replica,
      timing). Structural fields only (no outcome).
  python outputs/_mvg_probe_check.py kicks X.json
      ud_probe v2's kick-record consistency on a real record (acc, index_wb / u1_wb / div_shadow / divergent against
      their definitions, attempts against binds, decisions[].accepted), plus ud.errors, shadow_mismatch and dcb.
  python outputs/_mvg_probe_check.py guard X.json
      the guard record of one run (guard_problems): every guard row's verdict against its own rule (admit iff c finite
      and c + 1 <= T_v), by arm: fix off -> today's step and no model verdict; guard off -> the fix's step; guard on ->
      Zg-1 TWO-SIDED (an admitted step where the instrument vetoes, and a veto where it admits, both fail; the model's
      verdict equals the instrument's), Zg-2 at every veto (the cell, the raise, today's tier where today's
      _move_toward writes one, and for (b) the _idle_retreat_* writes against the pure replica), the same today-step
      identities on every non-live (shadow) row; the cross-links with d["mv"] (gA / gB / veto / acted_g / branch) and
      d["mv_events"] (guard, vetoed, ran, agree); the replica's in-run checks; the U1 shadow's sha; every error list.
  python outputs/_mvg_probe_check.py frozen X.json BOARDS.json
      every guard row's verdict recomputed with the FROZEN guard (urgency:outputs/_mvg_guard_diag.guard, sha256
      70eeba78... of its LF form, imported in the URGENCY checkout's context so it reads U1's own helpers) on the
      replay's recorded decision board, wind and grid; (admit, c_n, T_v) must be equal on every row. Run in a fresh
      process (it must import the urgency checkout's src_extension, not this one's).
  python outputs/_mvg_probe_check.py val R0|KOown|KOothers MVG.json REF.json [MVG_BOARDS REF_BOARDS]
      the W3 tooling validation (1d.13.4): rows_ff / rows_vic / rows_uav / rows_dec / rows_trig, eval, dp.commands,
      the mv rows' first 23 columns (normalised for fix (c), which this round does not carry: a REF carry row's
      branch c0 - fix (c)'s MODE-2 path kind - reads as path, and the fc column is not compared; any other (c)
      branch or a "c" in acted REFUSES), the v2 fields of every mv_event, stdout (the .stdout.txt files and
      stdout_sha); also compared and required: steps_done / terminal_step / complete / crashed, the remaining mv
      columns but timing, and with boards: decisions, boards, wind, grid, ko_rules, ko_applied.
  python outputs/_mvg_probe_check.py zg3 N.json G.json
      Zg-3 on one cell: G (the guard on) and N (the guard off) identical up to G's first veto (rows_*, commands and
      mv rows before it); the first per-step difference at the veto step when it is an (a) veto or a (b) veto whose
      today's retreat cell is defined, at or after it otherwise; a cell with no veto identical end to end (rows_*,
      eval, commands, stdout).
  python outputs/_mvg_probe_check.py compare MVG.json REF.json
      G-ID of an mvg record against a reference of the same line (W1: mvg0 vs ud0) by
      dispatch:outputs/_dp_analyze.ident_diff (FIELDS + every mf2 section + every dp field but J_ONLY), as
      _ud_probe_check compare.
  python outputs/_mvg_probe_check.py pair OFF.json ON.json
      cross-arm shadow agreement on one cell (mvg0 vs mvg1 / mvg2): identical rows_* and mv rows before s* (the ON
      arm's first ACTED event whose fix step RAN), a vetoed decision reading as today's step; identical decision-time
      columns at s* (incl. the instrument's guard verdicts).
  python outputs/_mvg_probe_check.py synthetic
      in-process, NO model step: the probe's install() and the replay's install_ko() on a real WildFireModel with
      hand-built boards, through the REAL Firefighter.advance: fix (a) and fix (b) boards whose guard admits / vetoes,
      in arms 0 / G / N (branch labels, guard rows, events, Zg-1 / Zg-2 by guard_problems, the replica); the replica
      in five _idle_retreat_* states; positive controls (veto acts -> under-veto; an inverted model verdict ->
      over-veto; a wrong today's step and wrong writes at a veto -> Zg-2; an impure shadow -> mv_purity; deep-snapshot
      controls); the replay's knockouts a / b / g and its rule parser; the U1 SHADOW self-check (loaded by path; a
      synthetic qualifying kick yields a non-None U1 order with Z4's recomputation equal; a crafted estimate yields a
      divergent shadow order while the model binds the index order); deep purity of mv_shadow and kick_shadow.
  python outputs/_mvg_probe_check.py purity STEPS SCENARIO WIND SEED [KEY=VALUE ...]
      ported from _ud_probe_check: builds the cell in-process and deep-snapshots the model around EVERY shadow point
      (mv_shadow with the guard and the replica, kick_shadow with the planner reading). It STEPS the model: a model
      run, not part of the Part 2d validation.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import random
import runpy
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
URGENCY = r"E:\Projects\SAS_wt\urgency"
FROZEN_GUARD_SHA = "70eeba7877dae6174999ae2a00774bdeeb36ced08d35df407f27318cd3a313b2"
U1_SHADOW_SHA = "cfc97ebd6dcc4f3d2b3102468769b7396f78e86d5f93e342f25fe5370632b1cf"
ROW_FIELDS = ("rows_ff", "rows_vic", "rows_uav", "rows_dec", "rows_trig")
V2_EVENT_KEYS = ("step", "kind", "unit", "victim", "live", "row", "cell", "today", "taken", "branch", "detail", "agree")
FIX_TIER = {"a": 7, "b": 10}
FIX_BRANCH = {"a": "approach_a", "b": "retreat_b"}
VETO_BRANCH = {"a": "approach_a_veto", "b": "retreat_b_veto"}
TODAY_BRANCH = {"a": ("approach",), "b": ("retreat", "retreat_fb")}
_PROBE = {}


class Refused(Exception):
    pass


def refuse(msg):
    raise Refused(msg)


def load(path):
    if not os.path.isfile(path):
        refuse("no such file: %s" % path)
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        refuse("unreadable JSON %s: %r" % (path, exc))


def probe_module():
    """The probe's module namespace (constants and pure functions), loaded once by path."""
    if not _PROBE:
        _PROBE.update(runpy.run_path(os.path.join(HERE, "_mvg_probe.py"), run_name="mvg_probe_check_module"))
    return _PROBE


def need_mvg(d, path):
    P = probe_module()
    mvg = d.get("mvg")
    if not isinstance(mvg, dict) or mvg.get("probe") != P["VERSION"]:
        refuse("%s is not an %s record (d['mvg']['probe'] = %r)" % (
            path, P["VERSION"], (mvg or {}).get("probe") if isinstance(mvg, dict) else None))
    if (mvg.get("guard") or {}).get("cols") != list(P["GUARD_COLS"]):
        refuse("%s: guard cols differ from GUARD_COLS" % path)
    if (d.get("mv") or {}).get("cols") != list(P["MV_COLS"]):
        refuse("%s: mv cols differ from MV_COLS" % path)
    return mvg


def _pct(values, q):
    v = sorted(values)
    if not v:
        return None
    return v[min(len(v) - 1, int(math.ceil(q * len(v))) - 1)]


# ------------------------------------------------------------------------------------------------- summary
def summary(path):
    d = load(path)
    mvg = need_mvg(d, path)
    ud, mv, ev = d.get("ud") or {}, d.get("mv") or {}, d.get("mv_events") or []
    print("probe", mvg.get("probe"), "rc", ud.get("rc_chain"), "steps", d.get("steps_done"), "crashed",
          (d.get("crashed") or {}).get("type") if isinstance(d.get("crashed"), dict) else d.get("crashed"))
    print("mvg switches", json.dumps(mvg.get("switches")))
    print("u1 shadow sha", mvg.get("u1_shadow_sha"), "(frozen copy %s)" % (
        "OK" if mvg.get("u1_shadow_sha") == U1_SHADOW_SHA else "DIFFERS"), "error", mvg.get("u1_shadow_error"))
    print("src_sha", json.dumps(mvg.get("src_sha")))
    print("ud errors", ud.get("errors"), "| mvg errors", mvg.get("errors"), "| dp errors", (d.get("dp") or {}).get("errors"))
    print("shadow_mismatch", ud.get("shadow_mismatch"))
    cols = mv.get("cols") or []
    rows = mv.get("rows") or []
    ix = {c: i for i, c in enumerate(cols)}
    print("mv rows", len(rows), "branches", dict(collections.Counter(r[ix["branch"]] for r in rows)))
    print("acted (unguarded shadow)", dict(collections.Counter(r[ix["acted"]] for r in rows if r[ix["acted"]])),
          "| acted_g", dict(collections.Counter(r[ix["acted_g"]] for r in rows if r[ix["acted_g"]])),
          "| veto", dict(collections.Counter(r[ix["veto"]] for r in rows if r[ix["veto"]])))
    print("mv_events", dict(collections.Counter((e["kind"], e["live"], e.get("vetoed")) for e in ev)))
    g = mvg.get("guard") or {}
    gc = g.get("cols") or []
    grows = [dict(zip(gc, r)) for r in g.get("rows") or []]
    print("guard rows", len(grows), dict(collections.Counter((r["kind"], r["admit"], r["model_admit"], r["took"])
                                                               for r in grows)), "(kind, admit, model_admit, took)")
    print("replica", json.dumps({k: (v if isinstance(v, int) else len(v)) for k, v in (mvg.get("replica") or {}).items()}))
    t = mvg.get("timing") or {}
    gm, im = t.get("guard_ms") or [], t.get("inst_guard_ms") or []
    print("guard timing: model calls %d, p50 %s p99 %s max %s ms | instrument %d, p50 %s p99 %s max %s ms" % (
        len(gm), _pct(gm, 0.5), _pct(gm, 0.99), max(gm) if gm else None, len(im), _pct(im, 0.5), _pct(im, 0.99),
        max(im) if im else None))
    ks = ud.get("kicks") or []
    print("kicks", len(ks), "qualifying", sum(1 for k in ks if k.get("qualifies")),
          "u1 computed", sum(1 for k in ks if k.get("u1") is not None),
          "div_shadow", sum(1 for k in ks if k.get("div_shadow")),
          "divergent", sum(1 for k in ks if k.get("divergent")),
          "z4_ok false", sum(1 for k in ks if k.get("z4_ok") is False))
    tm = ud.get("timing") or {}
    print("timing", json.dumps({k: v for k, v in tm.items() if k != "fix_calls"}))
    return 0


# ------------------------------------------------------------------------------------------------- kicks (v2)
def _first_accepted(order, acc):
    """The checker's own copy of 16.5's 'the victim the order WOULD BIND' (independent of the probe's)."""
    if order is None or acc is None:
        return None
    for vid in order:
        if acc.get(vid):
            return vid
    return None


def kick_problems(K, on):
    """v2 definition / consistency problems of one kick record (list of strings). `on` = DISPATCH_URGENCY effective
    (never in this round: U1 is not in the model)."""
    probs = []
    i = K.get("i")
    for f in ("acc", "index_wb", "u1_wb", "div_shadow", "divergent", "div_shadow_head", "divergent_head", "attempts",
              "bound"):
        if f not in K:
            probs.append("kick %s: no field %s" % (i, f))
    if probs:
        return probs
    acc, index, u1, bound, att = K["acc"], K.get("index") or [], K.get("u1"), K["bound"] or [], K["attempts"]
    q = bool(K.get("qualifies"))
    if acc is not None and sorted(acc) != sorted(index):
        probs.append("kick %s: acc keys %r != W %r" % (i, sorted(acc), sorted(index)))
    if (acc is None) != (u1 is None):
        probs.append("kick %s: acc read %s but the U1 shadow %s" % (i, acc is not None,
                                                                    "ran" if u1 is not None else "did not run"))
    if K["index_wb"] != _first_accepted(index, acc):
        probs.append("kick %s: index_wb %r != first accepted of index %r" % (i, K["index_wb"], _first_accepted(index, acc)))
    if K["u1_wb"] != _first_accepted(u1, acc):
        probs.append("kick %s: u1_wb %r != first accepted of u1 %r" % (i, K["u1_wb"], _first_accepted(u1, acc)))
    first = bound[0][0] if bound else None
    if K["div_shadow"] != (q and K["u1_wb"] != K["index_wb"]):
        probs.append("kick %s: div_shadow %r against its definition" % (i, K["div_shadow"]))
    if K["divergent"] != (q and first != K["index_wb"]):
        probs.append("kick %s: divergent %r against its definition" % (i, K["divergent"]))
    if K["div_shadow_head"] != bool(q and u1 and index and u1[0] != index[0]):
        probs.append("kick %s: div_shadow_head %r against v1's definition" % (i, K["div_shadow_head"]))
    if K["divergent_head"] != bool(q and bound and index and bound[0][0] != index[0]):
        probs.append("kick %s: divergent_head %r against v1's definition" % (i, K["divergent_head"]))
    if att is None:
        return probs + ["kick %s: attempts is None" % i]
    if any(ok is None for _v, ok in att):
        probs.append("kick %s: an attempt raised %r" % (i, att))
    if [v for v, ok in att if ok] != [b[0] for b in bound]:
        probs.append("kick %s: successful attempts %r != bound %r" % (i, [v for v, ok in att if ok], bound))
    ran = u1 if (on and q) else index
    if [v for v, _ok in att] != list(ran or []):
        probs.append("kick %s: attempted %r != the order the arm ran %r" % (i, [v for v, _ok in att], ran))
    if acc is not None and len(K.get("F") or []) == 1:
        expected = K["u1_wb"] if (on and q) else K["index_wb"]
        if first != expected:
            probs.append("kick %s: first bind %r != the shadow's %r" % (i, first, expected))
        tried = [v for v, _ok in att]
        before = tried[:tried.index(first)] if first in tried else tried
        if any(acc.get(v) for v in before):
            probs.append("kick %s: a planner-accepted victim was attempted and not bound before the bind %r" % (i, att))
    if q and K.get("u1") is None:
        probs.append("kick %s: a qualifying kick without a U1 shadow order" % i)
    if q and K.get("z4_ok") is not True:
        probs.append("kick %s: Z4's independent recomputation differs from the U1 shadow's records" % i)
    return probs


def kicks(path):
    """v2 kick-record consistency on a real record (counts and flags only; no outcome is printed)."""
    d = load(path)
    need_mvg(d, path)
    ud = d.get("ud") or {}
    on = bool((ud.get("switches") or {}).get("DISPATCH_URGENCY"))
    ks = ud.get("kicks") or []
    st = collections.Counter()
    probs = []
    by_i = {}
    for K in ks:
        by_i[K.get("i")] = K
        st["kicks"] += 1
        st["qualifying"] += bool(K.get("qualifies"))
        st["u1 computed"] += K.get("u1") is not None
        acc = K.get("acc")
        if acc is not None:
            st["acc read"] += 1
            st["planner readings"] += len(acc)
            st["refused W victims"] += sum(1 for v in acc.values() if not v)
        st["attempts"] += len(K.get("attempts") or [])
        st["div_shadow"] += bool(K.get("div_shadow"))
        st["divergent"] += bool(K.get("divergent"))
        probs += kick_problems(K, on)
    for dec in ud.get("decisions") or []:
        K = by_i.get(dec.get("k"))
        if K is None:
            probs.append("decision of an unknown kick %r" % dec.get("k"))
            continue
        acc = K.get("acc")
        want = (None if acc is None else bool(acc.get(dec["vid"])), dec["vid"] == K.get("index_wb"),
                dec["vid"] == K.get("u1_wb"))
        if (dec.get("accepted"), dec.get("index_wb"), dec.get("u1_wb")) != want:
            probs.append("decision k=%s vid=%s: accepted/index_wb/u1_wb %r != %r" % (
                dec.get("k"), dec["vid"], (dec.get("accepted"), dec.get("index_wb"), dec.get("u1_wb")), want))
        st["decisions"] += 1
    mv = d.get("mv") or {}
    cols = list(mv.get("cols") or [])
    ix = {c: n for n, c in enumerate(cols)}
    for r in mv.get("rows") or []:
        if len(r) != len(cols):
            probs.append("an mv row has %d values for %d cols" % (len(r), len(cols)))
            break
        st["mv rows"] += 1
        if r[ix["leg"]] == "carry" and r[ix["today"]] is not None and r[ix["dcb"]] != r[ix["dc"]]:
            probs.append("carry row step %s unit %s: dcb %r != dc %r" % (r[0], r[1], r[ix["dcb"]], r[ix["dc"]]))
    print("probe %s | DISPATCH_URGENCY effective %s" % (ud.get("probe"), on))
    print("ud.errors: %d %s" % (len(ud.get("errors") or []), (ud.get("errors") or [])[:3]))
    print("shadow_mismatch: %d %s" % (len(ud.get("shadow_mismatch") or []), (ud.get("shadow_mismatch") or [])[:3]))
    print("counts:", json.dumps(dict(st)))
    print("consistency problems: %d" % len(probs))
    for p in probs[:20]:
        print("   ", p)
    bad = probs or ud.get("errors") or ud.get("shadow_mismatch")
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------------- guard
def _zg2(r, tag):
    """Zg-2's identities for a decision where TODAY's step ran (a veto, or a non-live shadow row): the cell, the raise,
    today's tier where today's _move_toward writes one, and for (b) the _idle_retreat_* writes against the replica."""
    probs = []
    today_cell = r["today"] if r["today"] is not None else r["u"]
    if r["post"] != today_cell:
        probs.append(tag + ": today's step: post %r != today's cell %r (%s)" % (r["post"], today_cell, r["today_kind"]))
    if bool(r["raise"]) != bool(r["today_raise"]):
        probs.append(tag + ": today's step: raise %r != today's raise %r" % (r["raise"], r["today_raise"]))
    if r["today_kind"] in ("greedy", "fallback") and r["today"] is not None and r["tier"] != r["today_tier"]:
        probs.append(tag + ": today's step: tier %r != today's tier %r" % (r["tier"], r["today_tier"]))
    if r["kind"] == "b":
        if r["pred_writes"] is None or r["post_writes"] is None:
            probs.append(tag + ": (b) row without the _idle_retreat_* writes")
        elif r["pred_writes"] != r["post_writes"]:
            probs.append(tag + ": today's step: _idle_retreat_* writes %r != the replica's %r" % (
                r["post_writes"], r["pred_writes"]))
    return probs


def guard_problems(d, label="", errors=True, scope=None):
    """(problems, counts) of one record's guard material (see the module docstring, 'guard'). With errors=False the
    error lists and the replica's mismatch lists are not read; scope = the mv row indices the completeness check covers
    (None = every row; synthetic per-case records pass the case's own rows)."""
    P = probe_module()
    probs = []
    st = collections.Counter()
    mvg = d.get("mvg") or {}
    gcols = list(P["GUARD_COLS"])
    sw = mvg.get("switches") or {}
    on = {"a": sw.get("FF_APPROACH_PATH") is True, "b": sw.get("FF_RETREAT_KEEP_APPROACH") is True}
    g_on = sw.get("FF_FIX_STRANDING_GUARD") is True
    mvcols = list(P["MV_COLS"])
    mvrows = (d.get("mv") or {}).get("rows") or []
    events = [e for e in d.get("mv_events") or [] if e.get("kind") in ("a", "b")]
    ev_by = {}
    for e in events:
        if (e.get("row"), e.get("kind")) in ev_by:
            probs.append("%s: two events for row %s kind %s" % (label, e.get("row"), e.get("kind")))
        ev_by[(e.get("row"), e.get("kind"))] = e
    seen = set()
    for raw in (mvg.get("guard") or {}).get("rows") or []:
        if len(raw) != len(gcols):
            probs.append("%s: a guard row has %d values for %d cols" % (label, len(raw), len(gcols)))
            continue
        r = dict(zip(gcols, raw))
        k = r["kind"]
        tag = "%s guard row step %s unit %s kind %s" % (label, r["step"], r["unit"], k)
        if k not in ("a", "b"):
            probs.append(tag + ": unknown kind")
            continue
        st["rows " + k] += 1
        if (r["row"], k) in seen:
            probs.append(tag + ": duplicate (row, kind)")
        seen.add((r["row"], k))
        u, n = r["u"], r["n"]
        if u is None or n is None or abs(u[0] - n[0]) + abs(u[1] - n[1]) != 1:
            probs.append(tag + ": n %r is not a 4-neighbour of u %r" % (n, u))
        if r["today"] is not None and r["today"] == n:
            probs.append(tag + ": n == today's cell (the fix would not act)")
        if r["admit"] is None:
            probs.append(tag + ": no instrument verdict")
            continue
        c, tv = r["c"], r["T_v"]
        if bool(r["admit"]) != (c is not None and (tv is None or c + 1 <= tv)):
            probs.append(tag + ": instrument admit %r against c %r and T_v %r (admit iff c finite and c + 1 <= T_v)" % (
                r["admit"], c, tv))
        st["instrument " + ("admits" if r["admit"] else "vetoes")] += 1
        live = on[k]
        model_veto = r["model_admit"] is False
        if not live:
            st["shadow rows (fix off)"] += 1
            if r["model_admit"] is not None:
                probs.append(tag + ": a model verdict while the fix is off")
            if r["took"] != "today":
                probs.append(tag + ": the fix is off but its step was taken")
            probs += _zg2(r, tag + " [today-step identity, fix off]")
        elif not g_on:
            st["unguarded fix steps (guard off)"] += 1
            if r["model_admit"] is not None:
                probs.append(tag + ": a model verdict while the guard is off")
            if r["took"] != "fix" or r["post"] != n or r["tier"] != FIX_TIER[k]:
                probs.append(tag + ": guard off, the fix's step was not taken (took %r post %r tier %r)" % (
                    r["took"], r["post"], r["tier"]))
        else:
            if r["model_admit"] is None:
                probs.append(tag + ": the fix and the guard are on but the model did not evaluate the guard")
            else:
                if bool(r["model_admit"]) != bool(r["admit"]):
                    probs.append(tag + ": Zg-1 the model's verdict %r != the instrument's %r" % (
                        r["model_admit"], r["admit"]))
                if r["model_verdict"] is not None and r["model_verdict"] != [r["admit"], r["c"], r["T_v"]]:
                    probs.append(tag + ": the model's (admit, c, T_v) %r != the instrument's %r" % (
                        r["model_verdict"], [r["admit"], r["c"], r["T_v"]]))
                if r["model_cell"] != n:
                    probs.append(tag + ": the model judged cell %r, the shadow's fix cell is %r" % (r["model_cell"], n))
            if r["admit"] and r["took"] != "fix":
                st["Zg-1 over-veto"] += 1
                probs.append(tag + ": Zg-1 OVER-VETO: the instrument admits, today's step was taken")
            if not r["admit"] and r["took"] != "today":
                st["Zg-1 under-veto"] += 1
                probs.append(tag + ": Zg-1 UNDER-VETO: the instrument vetoes, the fix's step was taken")
            if r["took"] == "fix" and (r["post"] != n or r["tier"] != FIX_TIER[k]):
                probs.append(tag + ": an admitted step that is not the fix's (post %r tier %r)" % (r["post"], r["tier"]))
            if model_veto:
                st["vetoes " + k] += 1
                probs += _zg2(r, tag + " [Zg-2]")
            else:
                st["admitted " + k] += 1
        # the cross-links: d["mv"] row and the ACTED event
        if not isinstance(r["row"], int) or not 0 <= r["row"] < len(mvrows):
            probs.append(tag + ": row index %r outside d['mv']" % (r["row"],))
            continue
        m = dict(zip(mvcols, mvrows[r["row"]]))
        if (m["step"], m["unit"]) != (r["step"], r["unit"]) or m["pre"] != u or m["target"] != r["v"] \
                or m["post"] != r["post"] or m["tier"] != r["tier"]:
            probs.append(tag + ": the mv row's step/unit/pre/target/post/tier differ")
        if k not in (m["acted"] or "") or m["f" + k] != n or (m["today"] or [None, None])[1] != r["today"]:
            probs.append(tag + ": the mv row's acted / f%s / today differ" % k)
        if m["g" + k.upper()] != r["admit"]:
            probs.append(tag + ": mv g%s %r != admit %r" % (k.upper(), m["g" + k.upper()], r["admit"]))
        if (k in (m["veto"] or "")) != model_veto:
            probs.append(tag + ": mv veto %r against the model verdict %r" % (m["veto"], r["model_admit"]))
        if (k in (m["acted_g"] or "")) != bool(r["admit"]):
            probs.append(tag + ": mv acted_g %r against admit %r" % (m["acted_g"], r["admit"]))
        if r["took"] == "fix":
            want_br = (FIX_BRANCH[k],)
        elif live and model_veto:
            want_br = (VETO_BRANCH[k],)
        else:
            want_br = TODAY_BRANCH[k]
        if m["branch"] not in want_br:
            probs.append(tag + ": mv branch %r, expected %r" % (m["branch"], want_br))
        e = ev_by.get((r["row"], k))
        if e is None:
            probs.append(tag + ": no ACTED event")
            continue
        want_g = {"admit": r["admit"], "c": r["c"], "T_v": r["T_v"], "model_admit": r["model_admit"]}
        if e.get("guard") != want_g:
            probs.append(tag + ": event guard %r != the row's %r" % (e.get("guard"), want_g))
        if e.get("live") is not live or e.get("vetoed") is not bool(live and model_veto) \
                or e.get("ran") is not bool(live and not model_veto):
            probs.append(tag + ": event live / vetoed / ran %r against the row" % (
                [e.get("live"), e.get("vetoed"), e.get("ran")],))
        if live and e.get("agree") is not True:
            probs.append(tag + ": a live event that disagrees with the guarded shadow (agree %r)" % e.get("agree"))
        if not live and e.get("agree") is not None:
            probs.append(tag + ": a non-live event with agree %r" % e.get("agree"))
    # completeness: every acting fix of every mv row has its guard row and its event
    for i, raw in enumerate(mvrows):
        if scope is not None and i not in scope:
            continue
        m = dict(zip(mvcols, raw))
        for k in m["acted"] or "":
            if (i, k) not in seen:
                probs.append("%s: mv row %d (step %s unit %s) acted %s without a guard row" % (
                    label, i, m["step"], m["unit"], k))
    for key in ev_by:
        if key not in seen:
            probs.append("%s: an ACTED event (row %s kind %s) without a guard row" % (label, key[0], key[1]))
    if errors:
        rp = mvg.get("replica") or {}
        for name in ("mismatch", "fix_mismatch", "cell_mismatch"):
            if rp.get(name):
                probs.append("%s: replica %s: %d %r" % (label, name, len(rp[name]), rp[name][:3]))
        st["replica checked"] = rp.get("checked", 0)
        st["replica fix_checked"] = rp.get("fix_checked", 0)
        st["replica cell_checked"] = rp.get("cell_checked", 0)
        for name, lst in (("ud.errors", (d.get("ud") or {}).get("errors")), ("mvg.errors", mvg.get("errors")),
                          ("dp.errors", (d.get("dp") or {}).get("errors")),
                          ("ud.shadow_mismatch", (d.get("ud") or {}).get("shadow_mismatch"))):
            if lst:
                probs.append("%s: %s: %d %r" % (label, name, len(lst), lst[:3]))
        if mvg.get("u1_shadow_sha") != U1_SHADOW_SHA or mvg.get("u1_shadow_error"):
            probs.append("%s: the U1 shadow copy: sha %r error %r" % (label, mvg.get("u1_shadow_sha"),
                                                                      mvg.get("u1_shadow_error")))
        t = mvg.get("timing") or {}
        n_model = sum(1 for raw in (mvg.get("guard") or {}).get("rows") or []
                      if dict(zip(gcols, raw))["model_admit"] is not None)
        if t.get("guard_calls") != n_model:
            probs.append("%s: %r model guard calls timed, %d guard rows with a model verdict" % (
                label, t.get("guard_calls"), n_model))
    return probs, st


def guard(path):
    d = load(path)
    need_mvg(d, path)
    probs, st = guard_problems(d, label=os.path.basename(path))
    sw = (d["mvg"].get("switches") or {})
    print("guard check %s | switches a=%s b=%s guard=%s" % (os.path.basename(path), sw.get("FF_APPROACH_PATH"),
                                                          sw.get("FF_RETREAT_KEEP_APPROACH"),
                                                          sw.get("FF_FIX_STRANDING_GUARD")))
    print("counts:", json.dumps(dict(sorted(st.items()))))
    print("problems: %d" % len(probs))
    for p in probs[:40]:
        print("   ", p)
    return 1 if probs else 0


# ------------------------------------------------------------------------------------------------- frozen
def _mv_digest(burning, smoky):
    h = hashlib.sha1()
    h.update(repr(sorted(burning)).encode())
    h.update(b"|")
    h.update(repr(sorted(smoky)).encode())
    return h.hexdigest()[:16]


def load_frozen_guard():
    """The frozen guard() of urgency:outputs/_mvg_guard_diag.py, imported in the URGENCY checkout's context (the file
    inserts that checkout into sys.path and imports U1's unclean_cells / t_star / safe_route_hops from it). Its sha256
    (of the LF form) must be FROZEN_GUARD_SHA. Refuses when src_extension is already imported (it would be the wrong
    checkout's)."""
    path = os.path.join(URGENCY, "outputs", "_mvg_guard_diag.py")
    if not os.path.isfile(path):
        refuse("the frozen guard is missing: %s" % path)
    with open(path, "rb") as fh:
        raw = fh.read()
    lf = raw.replace(b"\r\n", b"\n")
    if hashlib.sha256(lf).hexdigest() != FROZEN_GUARD_SHA:
        refuse("the frozen guard's sha256 (LF form) is %s, not %s" % (hashlib.sha256(lf).hexdigest(), FROZEN_GUARD_SHA))
    if any(name == "src_extension" or name.startswith("src_extension.") for name in sys.modules):
        refuse("src_extension is already imported in this process; the frozen guard must import the urgency checkout's")
    spec = importlib.util.spec_from_file_location("_mvg_guard_diag_frozen", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    src = os.path.normcase(os.path.abspath(sys.modules["src_extension.planning.urgency_dispatch"].__file__))
    if not src.startswith(os.path.normcase(os.path.abspath(URGENCY))):
        refuse("the frozen guard imported U1's helpers from %s, not the urgency checkout" % src)
    return module, hashlib.sha256(raw).hexdigest() == FROZEN_GUARD_SHA


def frozen(path, boards_path):
    d = load(path)
    need_mvg(d, path)
    b = load(boards_path)
    argv = b.get("argv") or []
    try:
        out = argv[argv.index("--out") + 1]
    except (ValueError, IndexError):
        refuse("%s carries no --out in its argv" % boards_path)
    if os.path.normcase(os.path.abspath(out)) != os.path.normcase(os.path.abspath(path)):
        refuse("the boards %s belong to the run writing %s, not %s" % (boards_path, out, path))
    module, raw_lf = load_frozen_guard()
    print("frozen guard: %s (sha256 %s of the LF form; the file itself is %s)" % (
        module.__file__, FROZEN_GUARD_SHA[:16], "LF" if raw_lf else "CRLF"))
    gcols = list(probe_module()["GUARD_COLS"])
    mvcols = list(probe_module()["MV_COLS"])
    mvrows = d["mv"]["rows"]
    idx = {}
    for dec in b.get("decisions") or []:
        key = (dec[0], dec[1])
        if key in idx:
            refuse("two board decisions for step %s unit %s" % key)
        idx[key] = dec
    wind = b.get("wind") or {}
    vec = tuple(wind.get("vector")) if wind.get("vector") is not None else None
    w, h = b.get("grid") or (None, None)
    probs = []
    n = 0
    stats = collections.Counter()
    for raw in d["mvg"]["guard"]["rows"]:
        r = dict(zip(gcols, raw))
        tag = "step %s unit %s kind %s" % (r["step"], r["unit"], r["kind"])
        dec = idx.get((r["step"], r["unit"]))
        if dec is None:
            probs.append(tag + ": no board decision")
            continue
        if dec[2] != r["u"]:
            probs.append(tag + ": board decision cell %r != u %r" % (dec[2], r["u"]))
        if dec[3] != r["v"]:
            # the board is read at advance entry, the target refreshed after it (a moving victim): reported, not a
            # problem - the guard is judged on the row's own v
            stats["target refreshed after the board read"] += 1
        board = b["boards"][dec[6]]
        burning = [(int(x), int(y)) for x, y in board["burning"]]
        smoky = [(int(x), int(y)) for x, y in board["smoky"]]
        m = dict(zip(mvcols, mvrows[r["row"]]))
        if _mv_digest(burning, smoky) != m["digest"]:
            probs.append(tag + ": the board is not the decision board (digest)")
            continue
        adm, c, tv = module.guard(tuple(r["u"]), tuple(r["n"]), tuple(r["v"]), burning, smoky, vec, w, h)
        tv = None if math.isinf(float(tv)) else float(tv)
        got = [bool(adm), c, tv]
        want = [r["admit"], r["c"], r["T_v"]]
        n += 1
        stats[("admit" if adm else "veto") + " " + r["kind"]] += 1
        if got != want:
            probs.append(tag + ": frozen %r != recorded %r" % (got, want))
    print("frozen guard on %d guard rows (%s): %d equal, %d problems" % (n, json.dumps(dict(stats)),
                                                                        n - sum(1 for p in probs if "frozen" in p),
                                                                        len(probs)))
    for p in probs[:20]:
        print("   ", p)
    return 1 if (probs or n == 0) else 0


# ------------------------------------------------------------------------------------------------- val
def _first_diff(a, b):
    if a == b:
        return None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return min(len(a), len(b))


def _stdout_path(path):
    return path[:-5] + ".stdout.txt" if path.endswith(".json") else path + ".stdout.txt"


def _norm_ref_row(r, ix):
    """A REF (urgency, fix (c) on) mv row's first 23 columns read for an arm without (c): carry branch c0 (fix (c)'s
    MODE-2 path kind, the same step) -> path; fc (the (c) shadow) -> None. Refuses any other (c) carry branch, and
    a "c" in acted (fix (c) acted: the identity cannot be judged). Returns (row, normalised?)."""
    out = list(r[:23])
    changed = False
    br = out[ix["branch"]]
    if out[ix["leg"]] == "carry" and br in ("c1", "c2", "c2s", "c3", "c?"):
        refuse("REF carry row step %s unit %s took fix (c)'s branch %s" % (out[0], out[1], br))
    if "c" in str(out[ix["acted"]] or ""):
        refuse("REF row step %s unit %s: fix (c) acted" % (out[0], out[1]))
    if out[ix["leg"]] == "carry" and br == "c0":
        out[ix["branch"]] = "path"
        changed = True
    if out[ix["fc"]] is not None:
        out[ix["fc"]] = None
        changed = True
    return out, changed


def val(kind, mvg_path, ref_path, mvg_boards=None, ref_boards=None):
    d, r = load(mvg_path), load(ref_path)
    need_mvg(d, mvg_path)
    if not isinstance(r.get("ud"), dict) or r["ud"].get("probe") != "ud_probe v2":
        refuse("%s is not a ud_probe v2 record" % ref_path)
    for f in ("seed", "scenario"):
        if d.get(f) != r.get(f):
            refuse("not the same cell: %s %r vs %r" % (f, d.get(f), r.get(f)))
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    for f in ROW_FIELDS:
        a, b = d.get(f), r.get(f)
        if a is None or b is None:
            check(f, False, "missing")
            continue
        i = _first_diff(a, b)
        check(f, i is None, "" if i is None else "first difference at index %d (state after step %d); %d vs %d rows" % (
            i, i + 1, len(a), len(b)))
    check("eval", d.get("eval") == r.get("eval"), "")
    for f in ("steps_done", "terminal_step", "complete", "crashed"):
        check(f, d.get(f) == r.get(f), "%r vs %r" % (d.get(f), r.get(f)))
    ca, cb = (d.get("dp") or {}).get("commands"), (r.get("dp") or {}).get("commands")
    i = _first_diff(ca or [], cb or [])
    check("dp.commands", ca is not None and i is None, "" if i is None else "first difference at %d: %r vs %r" % (
        i, (ca or [None])[i] if i < len(ca or []) else None, (cb or [None])[i] if i < len(cb or []) else None))
    # mv rows
    P = probe_module()
    ix = {c: n for n, c in enumerate(P["MV_COLS"])}
    rcols = (r.get("mv") or {}).get("cols") or []
    if rcols[:23] != list(P["MV_COLS"])[:23] or rcols[23:38] != list(P["MV_COLS"])[23:38]:
        refuse("REF mv cols are not v2's")
    ma, mb = d["mv"]["rows"], r["mv"]["rows"]
    check("mv rows count", len(ma) == len(mb), "%d vs %d" % (len(ma), len(mb)))
    normed = 0
    first23 = None
    rest = None
    fc_mvg = sum(1 for row in ma if row[ix["fc"]] is not None)
    for n, (x, y) in enumerate(zip(ma, mb)):
        yn, ch = _norm_ref_row(y, ix)
        normed += ch
        if first23 is None and list(x[:23]) != yn:
            first23 = (n, list(x[:23]), yn)
        keep = [c for c in range(23, 38) if c not in (ix["fix_ms"], ix["inst_ms"])]
        if rest is None and [x[c] for c in keep] != [y[c] for c in keep]:
            rest = (n, [x[c] for c in keep], [y[c] for c in keep])
    check("mv rows: first 23 columns (REF normalised for fix (c): %d rows)" % normed, first23 is None and fc_mvg == 0,
          "" if first23 is None else "row %d:\n      MVG %s\n      REF %s" % first23)
    check("mv rows: columns 23-37 but fix_ms / inst_ms", rest is None,
          "" if rest is None else "row %d:\n      MVG %s\n      REF %s" % rest)
    # events
    ea = [{k: e.get(k) for k in V2_EVENT_KEYS} for e in d.get("mv_events") or []]
    eb_raw = r.get("mv_events") or []
    if any(e.get("kind") not in ("a", "b") for e in eb_raw):
        refuse("REF has events other than a / b (fix (c) material): %r" % sorted({e.get("kind") for e in eb_raw}))
    eb = [{k: e.get(k) for k in V2_EVENT_KEYS} for e in eb_raw]
    i = _first_diff(ea, eb)
    check("mv_events v2 fields (%d vs %d)" % (len(ea), len(eb)), i is None,
          "" if i is None else "first difference at %d: %r vs %r" % (i, ea[i] if i < len(ea) else None,
                                                                     eb[i] if i < len(eb) else None))
    # stdout
    sa, sb = _stdout_path(mvg_path), _stdout_path(ref_path)
    if not os.path.isfile(sa) or not os.path.isfile(sb):
        check("stdout", False, "missing %s / %s" % (sa, sb))
    else:
        with open(sa, "rb") as fh:
            ta = fh.read()
        with open(sb, "rb") as fh:
            tb = fh.read()
        check("stdout (.stdout.txt bytes, %d vs %d)" % (len(ta), len(tb)), ta == tb, "")
    check("stdout_sha", d.get("stdout_sha") == r.get("stdout_sha"), "")
    if mvg_boards and ref_boards:
        ba, bb = load(mvg_boards), load(ref_boards)
        for f in ("decisions", "boards", "wind", "grid", "ko_rules", "ko_applied"):
            x, y = ba.get(f), bb.get(f)
            detail = ""
            if f == "decisions" and x != y:
                j = _first_diff(x or [], y or [])
                detail = "first difference at %s" % j
            if f == "ko_applied":
                detail = "%r" % (x,)
            check("boards." + f, x == y and (f != "ko_applied" or kind == "R0" or x), detail)
        if ba.get("errors"):
            check("boards.errors", False, repr(ba.get("errors")[:3]))
    # the MVG record's own instrument state
    probs, st = guard_problems(d, label="MVG")
    check("MVG guard record (guard_problems)", not probs, "; ".join(probs[:5]))
    print("VALIDATION %s: %s vs %s" % (kind, os.path.basename(mvg_path), os.path.basename(ref_path)))
    for name, ok, detail in results:
        print("  %-4s %s %s" % ("OK" if ok else "DIFF", name, detail))
    print("  guard rows / replica counts:", json.dumps(dict(sorted(st.items()))))
    bad = [x for x in results if not x[1]]
    print("  %d comparisons, %d differ" % (len(results), len(bad)))
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------------- compare / pair
DISPATCH_OUT = r"E:\Projects\SAS_wt\dispatch\outputs"


def compare(a_path, b_path):
    """G-ID of an mvg record against a reference record of the same line (ud0 / dp), by
    dispatch:outputs/_dp_analyze.ident_diff (FIELDS + every mf2 section + every dp field but J_ONLY), plus every other
    top-level section reported (as _ud_probe_check compare)."""
    a, b = load(a_path), load(b_path)
    need_mvg(a, a_path)
    if not os.path.isfile(os.path.join(DISPATCH_OUT, "_dp_analyze.py")):
        refuse("dispatch:outputs/_dp_analyze.py is missing (%s)" % DISPATCH_OUT)
    sys.path.insert(0, DISPATCH_OUT)
    argv = sys.argv
    sys.argv = argv[:1]
    try:
        import _dp_analyze as DA  # noqa: E402
    finally:
        sys.argv = argv
    diff, note, other = DA.ident_diff(a, b, False)
    print("G-ID (dispatch _dp_analyze.ident_diff): %s" % ("IDENTICAL" if not diff else "DIFFERS %r" % diff))
    if note:
        print("  note:", note)
    print("  other sections differing (fb3/fx3/ut/mr, reported):", other)
    keys = sorted(set(a) | set(b))
    skip = {"argv", "tag", "dp", "ud", "mv", "mv_events", "mvg", "wall_s", "fb3", "fx3", "ut", "mr", "mf2"}
    rest = [k for k in keys if k not in skip and a.get(k) != b.get(k)]
    print("  other top-level keys differing:", rest)
    print("  only in A:", sorted(set(a) - set(b)), " only in B:", sorted(set(b) - set(a)))
    da, db = a.get("dp") or {}, b.get("dp") or {}
    print("  dp keys equal:", sorted(da) == sorted(db), "| J_ONLY differing:",
          [k for k in DA.J_ONLY if da.get(k) != db.get(k)])
    return 0 if not diff else 1


def _branch_equiv(off, on):
    """An ON-arm branch at a decision where the OFF arm (fixes 0) took today's step: equal, or the ON arm's veto label
    of today's step."""
    return off == on or (on == "approach_a_veto" and off == "approach") or (
        on == "retreat_b_veto" and off in ("retreat", "retreat_fb"))


def pair(off_path, on_path):
    """Cross-arm check of one cell: the OFF arm (mvg0: both fixes 0) and an ON arm (mvg1 or mvg2). s* = the first step
    with an ACTED event whose fix step RAN in the ON arm (ran: live and not vetoed - a vetoed decision is today's step,
    G1) or a divergent kick. Before s*: rows_* identical, and every mv row identical but timing, with the branch equal
    or the ON arm's veto label of today's step (and veto empty in OFF); at s*: the decision-time columns of every row
    identical (shadow agreement, incl. the instrument's guard verdicts)."""
    a, b = load(off_path), load(on_path)
    need_mvg(a, off_path)
    need_mvg(b, on_path)
    for f in ("seed", "scenario", "wind"):
        if a.get(f) != b.get(f):
            refuse("not the same cell: %s %r vs %r" % (f, a.get(f), b.get(f)))
    sa = a["mvg"]["switches"]
    if sa.get("FF_APPROACH_PATH") or sa.get("FF_RETREAT_KEEP_APPROACH"):
        refuse("%s is not the OFF arm: %r" % (off_path, sa))
    ev = [e["step"] for e in b.get("mv_events") or [] if e.get("ran")]
    kd = [k["step"] for k in (b.get("ud") or {}).get("kicks") or [] if k.get("divergent")]
    s_star = min(ev + kd) if ev + kd else None
    print("s* (first ACTED event whose fix step ran / divergent kick in the ON arm):", s_star,
          "| ran events", len(ev), "| divergent kicks", kd)
    lim = (s_star - 1) if s_star else None
    ok = True
    for f in ROW_FIELDS:
        ra, rb = a.get(f) or [], b.get(f) or []
        first = _first_diff(ra, rb)
        good = first is None or (lim is not None and first >= lim)
        ok = ok and good
        print("%s: first differing index %s; required >= %s -> %s" % (f, first, lim, "OK" if good else "FAIL"))
    P = probe_module()
    ix = {c: i for i, c in enumerate(P["MV_COLS"])}
    full = [c for c in P["MV_COLS"] if c not in ("fix_ms", "inst_ms", "branch", "veto")]
    ma = [r for r in a["mv"]["rows"] if s_star is None or r[0] < s_star]
    mb = [r for r in b["mv"]["rows"] if s_star is None or r[0] < s_star]
    same = len(ma) == len(mb) and all(
        [x[ix[c]] for c in full] == [y[ix[c]] for c in full] and _branch_equiv(x[ix["branch"]], y[ix["branch"]])
        and not x[ix["veto"]] for x, y in zip(ma, mb))
    ok = ok and same
    print("mv rows before s*: %d vs %d, identical (but timing; branch / veto as today's step): %s" % (
        len(ma), len(mb), same))
    if s_star is not None:
        at_a = [[r[ix[c]] for c in PRE_COLS] for r in a["mv"]["rows"] if r[0] == s_star]
        at_b = [[r[ix[c]] for c in PRE_COLS] for r in b["mv"]["rows"] if r[0] == s_star]
        print("decision-time columns at s*: %d vs %d rows, identical: %s" % (len(at_a), len(at_b), at_a == at_b))
        ok = ok and at_a == at_b
    else:
        print("eval identical (no fix step ran): %s" % (a.get("eval") == b.get("eval")))
        ok = ok and a.get("eval") == b.get("eval")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------- zg3
PRE_COLS =("step", "unit", "victim", "leg", "pre", "target", "digest", "st_pre", "trig", "zrb", "today", "fa", "fb",
            "fbB", "fc", "acted", "dc", "dcx", "df", "dm", "dr", "gesc", "cls_pre", "fd_pre", "c1_pre", "dcb", "gA",
            "gB", "acted_g")


def zg3(n_path, g_path):
    dn, dg = load(n_path), load(g_path)
    need_mvg(dn, n_path)
    need_mvg(dg, g_path)
    for f in ("seed", "scenario", "wind"):
        if dn.get(f) != dg.get(f):
            refuse("not the same cell: %s %r vs %r" % (f, dn.get(f), dg.get(f)))
    sn, sg = dn["mvg"]["switches"], dg["mvg"]["switches"]
    if not (sn.get("FF_APPROACH_PATH") and sn.get("FF_RETREAT_KEEP_APPROACH") and sn.get("FF_FIX_STRANDING_GUARD") is False):
        refuse("%s is not arm N (the fixes on, the guard off): %r" % (n_path, sn))
    if not (sg.get("FF_APPROACH_PATH") and sg.get("FF_RETREAT_KEEP_APPROACH") and sg.get("FF_FIX_STRANDING_GUARD") is True):
        refuse("%s is not arm G (the fixes on, the guard on): %r" % (g_path, sg))
    P = probe_module()
    gcols = list(P["GUARD_COLS"])
    vetoes = sorted((r["step"], r["unit"], r["kind"], r["today_kind"]) for r in
                    (dict(zip(gcols, raw)) for raw in dg["mvg"]["guard"]["rows"]) if r["model_admit"] is False)
    firsts = {}
    for f in ROW_FIELDS:
        firsts[f] = _first_diff(dn.get(f) or [], dg.get(f) or [])
    ds = [i for i in firsts.values() if i is not None]
    first = min(ds) if ds else None
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    ix = {c: i for i, c in enumerate(P["MV_COLS"])}
    full = [c for c in P["MV_COLS"] if c not in ("fix_ms", "inst_ms")]
    if not vetoes:
        check("no veto in G: rows_* identical end to end", first is None, json.dumps(firsts))
        check("no veto in G: eval identical", dn.get("eval") == dg.get("eval"))
        check("no veto in G: dp.commands identical", (dn.get("dp") or {}).get("commands") == (dg.get("dp") or {}).get("commands"))
        check("no veto in G: stdout_sha identical", dn.get("stdout_sha") == dg.get("stdout_sha"))
        check("no veto in G: mv rows identical (all but timing)",
              [[x[ix[c]] for c in full] for x in dn["mv"]["rows"]] == [[x[ix[c]] for c in full] for x in dg["mv"]["rows"]])
    else:
        s_v, unit, kind, today_kind = vetoes[0]
        lim = s_v - 1
        exact = kind == "a" or (kind == "b" and today_kind == "survival")
        print("first veto in G: step %d unit %s kind %s (today %s) -> the first difference must be %s rows index %d "
              "(state after step %d)" % (s_v, unit, kind, today_kind, "AT" if exact else "at or after", lim, s_v))
        check("rows_*: no difference before the first veto's step", first is not None and first >= lim,
              json.dumps(firsts))
        if exact:
            check("rows_*: the first difference is at the first veto's step", first == lim, json.dumps(firsts))
        ca = [c for c in (dn.get("dp") or {}).get("commands") or [] if c[0] < s_v]
        cb = [c for c in (dg.get("dp") or {}).get("commands") or [] if c[0] < s_v]
        check("dp.commands before the first veto identical (%d vs %d)" % (len(ca), len(cb)), ca == cb)
        ra = [[x[ix[c]] for c in full] for x in dn["mv"]["rows"] if x[0] < s_v]
        rb = [[x[ix[c]] for c in full] for x in dg["mv"]["rows"] if x[0] < s_v]
        check("mv rows before the first veto identical, all columns but timing (%d vs %d)" % (len(ra), len(rb)), ra == rb)
        pa = [[x[ix[c]] for c in PRE_COLS] for x in dn["mv"]["rows"] if x[0] == s_v]
        pb = [[x[ix[c]] for c in PRE_COLS] for x in dg["mv"]["rows"] if x[0] == s_v]
        check("mv rows at the first veto's step: decision-time columns identical (%d vs %d)" % (len(pa), len(pb)),
              pa == pb)
        print("vetoes in G: %d (%s)" % (len(vetoes), json.dumps(collections.Counter(v[2] for v in vetoes))))
    print("Zg-3 %s (N) vs %s (G)" % (os.path.basename(n_path), os.path.basename(g_path)))
    for name, ok, detail in results:
        print("  %-4s %s %s" % ("OK" if ok else "FAIL", name, detail))
    return 0 if all(x[1] for x in results) else 1


# ------------------------------------------------------------------------------------------- purity (deep)
def freeze(v, depth, seen_agents):
    if v is None or isinstance(v, (bool, int, float, str, bytes)):
        return v
    t = type(v)
    mod = getattr(t, "__module__", "")
    if t.__name__ in ("ndarray",):
        try:
            return ("nd", v.dtype.str, v.shape, v.tobytes())
        except Exception:
            return ("nd?",)
    if mod.startswith("numpy"):
        try:
            return ("np", repr(v))
        except Exception:
            return ("np?",)
    if id(v) in seen_agents:
        return ("agent", id(v))
    # no id() of non-agent objects: some state objects hand out fresh sub-objects on every read (an unstable key)
    if depth <= 0:
        try:
            n = len(v)
        except Exception:
            n = None
        return ("obj", t.__name__, n)
    if isinstance(v, dict):
        return ("dict", tuple((freeze(k, 0, seen_agents), freeze(x, depth - 1, seen_agents)) for k, x in v.items()))
    if isinstance(v, (list, tuple)):
        return (t.__name__, tuple(freeze(x, depth - 1, seen_agents) for x in v))
    if isinstance(v, (set, frozenset)):
        return (t.__name__, tuple(sorted((repr(freeze(x, depth - 1, seen_agents)) for x in v))))
    if isinstance(v, collections.deque):
        return ("deque", tuple(freeze(x, depth - 1, seen_agents) for x in v))
    if hasattr(v, "__dict__") and not callable(v):
        return ("obj", t.__name__, freeze(dict(vars(v)), depth - 1, seen_agents))
    return ("other", t.__name__)


def snapshot(model, ag):
    agents = list(model.schedule.agents)
    seen = {id(a) for a in agents}
    seen.add(id(model))
    out = {}
    for a in agents:
        out[("agent", type(a).__name__, str(a.unique_id))] = freeze(
            {k: v for k, v in vars(a).items() if k != "model"}, 3, seen)
    out["model"] = freeze({k: v for k, v in vars(model).items()
                           if k not in ("schedule", "grid", "datacollector")}, 3, seen)
    grid = model.grid
    cells = []
    for x in range(grid.width):
        for y in range(grid.height):
            cells.append(tuple(id(o) for o in grid.get_cell_list_contents([(x, y)])))
    out["grid"] = tuple(cells)
    rngs = []
    for r in (getattr(ag, "random", None), getattr(model, "random", None)):
        rngs.append(r.getstate() if r is not None else None)
    import numpy as np
    st = np.random.get_state()
    rngs.append((st[0], st[1].tobytes(), st[2], st[3], st[4]))
    out["rng"] = tuple(rngs)
    return out


def purity(steps, scenario, wind, seed, sets):
    sys.path.insert(0, REPO)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as am
    import common_fixed_variables as cfv
    import wildfire_model as wf
    import evaluate_scenarios as es
    from src_extension.adaptation.local_adaptation_generator import apply_scenario_config
    from src_extension.planning import fire_arrival_estimate as fae
    from src_extension.planning import movement_paths as mpm
    from src_extension.planning.rescue_planner import select_rescue_assignment

    probe = probe_module()
    udm, _sha = probe["load_u1_shadow"]()
    fn = probe["shadow_funcs"](am)
    ns = argparse.Namespace(scenario=scenario, wind=wind, uavs=None, victims=None, firefighters=None,
                            fire_trackers=None, victim_searchers=None, batch_size=300, fire_spread=0.75,
                            ff_absence_min=None, ff_absence_max=None)
    extra = {"GLOBAL_PLANNER_MODE": 0, "VICTIM_SPAWN_MODE": 0, "BATCH_SIZE": 360}
    for item in sets:
        k, v = item.split("=", 1)
        extra[k] = int(v)
    ns.preset_overrides = dict(extra)
    params = es._scenario_params(ns)
    params.update(extra)
    rng = random.Random(seed)
    cfv.SYSTEM_RANDOM = rng
    wf.SYSTEM_RANDOM = rng
    am.random = rng
    apply_scenario_config(cfv, wf, **params)

    stats = collections.Counter()
    failures = []
    t_snap = [0.0]
    o_refresh = am.Firefighter._refresh_target_from_victim

    def check(label, fn_call, model):
        t0 = time.perf_counter()
        before = snapshot(model, am)
        t_snap[0] += time.perf_counter() - t0
        out = fn_call()
        t0 = time.perf_counter()
        after = snapshot(model, am)
        t_snap[0] += time.perf_counter() - t0
        if before != after:
            bad = [k for k in before if before.get(k) != after.get(k)][:5]
            failures.append((label, int(model.evaluation_timesteps_counter or 0), bad))
        stats[label] += 1
        return out

    def refresh(self, *a, **k):
        r = o_refresh(self, *a, **k)
        if not stats["control_unit"]:
            old = self._idle_retreat_steps
            check("control_unit", lambda: setattr(self, "_idle_retreat_steps", old + 1000), self.model)
            self._idle_retreat_steps = old
            state = am.random.getstate()
            check("control_rng", lambda: am.random.random(), self.model)
            am.random.setstate(state)
        S = check("mv_shadow", lambda: probe["mv_shadow"](self, self.model, am, fn, mpm.stranding_guard, cfv),
                  self.model)
        if S is not None:
            stats["mv_row:%s" % S["kind"]] += 1
            if S["acted"]:
                stats["acted:%s" % S["acted"]] += 1
        return r

    o_kick = wf.WildFireModel._try_dispatch_unresolved_confirmed_victims

    def kick(self, *a, **k):
        K = check("kick_shadow", lambda: probe["kick_shadow"](self, am, udm, fae, udm.urgency_order,
                                                              select_rescue_assignment, cfv), self)
        if K.get("qualifies"):
            stats["kick_qualifying"] += 1
        return o_kick(self, *a, **k)

    am.Firefighter._refresh_target_from_victim = refresh
    wf.WildFireModel._try_dispatch_unresolved_confirmed_victims = kick
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        model = wf.WildFireModel()
        model.debug_log = False
        for _ in range(steps):
            model.step()
    print("purity: %d steps in %.0f s (snapshots %.0f s); switches %r" % (
        steps, time.perf_counter() - t0, t_snap[0], extra))
    controls = [f for f in failures if f[0].startswith("control")]
    failures = [f for f in failures if not f[0].startswith("control")]
    print("  shadow points checked:", dict(stats))
    print("  positive controls detected: %d of %d %s" % (
        len(controls), stats["control_unit"] + stats["control_rng"], controls))
    print("  failures:", failures if failures else "NONE")
    return 0 if not failures and len(controls) == 2 else 1


# ------------------------------------------------------------------------------------------- synthetic
V0, V1, V2 = "victim_0", "victim_1", "victim_2"
FF_A = "ff_unit_0"


class _World:
    """Hand-built boards on a REAL WildFireModel (helpers ported from urgency:tests/urgency_test_support.py; fire is
    set on the Fire agents as numpy.bool_, the simulator's own type after its first tick)."""

    def __init__(self, ag, cfv, wf, seed=4242):
        import numpy as np
        self.np, self.ag, self.cfv, self.wf = np, ag, cfv, wf
        rng = random.Random(seed)
        for mod in (cfv, wf):
            mod.SYSTEM_RANDOM = rng
            for name, value in (("NUM_AGENTS", 3), ("NUM_VICTIMS", 5), ("NUM_FIREFIGHTERS", 3)):
                setattr(mod, name, value)
        ag.random = rng
        cfv.VICTIM_SPAWN_MODE = 0
        with contextlib.redirect_stdout(io.StringIO()):
            self.model = wf.WildFireModel()
        self.model.debug_log = False

    def switches(self, a, b, g):
        self.cfv.FF_APPROACH_PATH, self.cfv.FF_RETREAT_KEEP_APPROACH, self.cfv.FF_FIX_STRANDING_GUARD = a, b, g

    def fire_at(self, cell):
        for agent in self.model.grid.get_cell_list_contents([cell]):
            if type(agent) is self.ag.Fire:
                return agent
        raise AssertionError("no Fire agent at %r" % (cell,))

    def quiet(self):
        for agent in self.model.schedule.agents:
            if type(agent) is self.ag.Fire:
                agent.burning = False
                agent.smoke.smoke = False

    def burn(self, cells):
        for cell in cells:
            self.fire_at(cell).burning = self.np.bool_(True)

    def place_units(self, units):
        m = self.model
        for ff_id, marker in m.firefighter_marker_agents.items():
            marker.assigned = False
            marker.target_pos = None
            marker.rescued_victim = None
            marker.exiting = False
            marker.exit_target = None
            marker.rescue_completed = False
            marker._idle_retreat_origin = None
            marker._idle_retreat_steps = 0
            marker._idle_retreat_stalled = False
            marker._idle_retreat_last_cell = None
            if ff_id in units:
                marker.dead = False
                marker.status = "available"
                if marker.pos is None:
                    m.grid.place_agent(marker, units[ff_id])
                else:
                    m.grid.move_agent(marker, units[ff_id])
            else:
                marker.dead = True
                marker.status = "dead"

    def place_victims(self, victims):
        m = self.model
        runtime = getattr(m, "victim_runtime_model", None)
        records = getattr(runtime, "victims", None)
        if isinstance(records, dict):
            records.clear()
        for vid, marker in m.victim_marker_agents.items():
            state = m.managed_victims[vid]
            if vid in victims:
                cell = victims[vid]
                if marker.pos is None:
                    m.grid.place_agent(marker, cell)
                else:
                    m.grid.move_agent(marker, cell)
                if hasattr(marker, "spawn_cell"):
                    marker.spawn_cell = cell
                if hasattr(marker, "leash_anchor"):
                    marker.leash_anchor = cell
            state.rescued = False
            state.cancelled = False
            state.unreachable = False
            state.rescue_assigned = False
            state.assigned = False
            if vid in victims:
                state.confirmed = True
                state.status = "confirmed"
                marker.status = "confirmed"
            else:
                state.confirmed = False
                state.status = "candidate"
                marker.status = "candidate"

    def assign(self, vid, ff_id):
        marker = self.model.victim_marker_agents[vid]
        with contextlib.redirect_stdout(io.StringIO()):
            return bool(self.model.apply_physical_rescue_command(self.wf.PhysicalRescueCommand(
                action="assign", victim_id=vid, firefighter_id=ff_id, reason="initial",
                metadata={"victim_marker": marker, "target_pos": tuple(marker.pos)})))

    def unit(self, ff_id=FF_A):
        return self.model.firefighter_marker_agents[ff_id]

    def scene(self, wind, unit_cell, victim_cell, fire, step):
        self.quiet()
        self.model.wind.wind_direction = wind
        self.place_units({FF_A: unit_cell})
        self.place_victims({V0: victim_cell})
        assert self.assign(V0, FF_A), "assign failed"
        self.burn(fire)
        self.model.evaluation_timesteps_counter = int(step)
        return self.unit()


# the four guard boards (found by hand on the real model; the expected verdicts are asserted, not assumed)
POCKET = [(x, 17) for x in range(19, 24)] + [(x, 23) for x in range(19, 24)] + [(23, y) for y in range(17, 24)]
BOARDS = {
    # fix (a): the unit in a pocket open to -x, the victim beyond its far wall; greedy steps deeper into the pocket
    "A_admit": {"wind": "west", "unit": (20, 20), "victim": (26, 20), "fire": POCKET, "kind": "a", "admit": True,
                "n": (19, 20), "today": (21, 20)},
    "A_veto": {"wind": "north", "unit": (20, 20), "victim": (26, 20), "fire": POCKET, "kind": "a", "admit": False,
               "n": (19, 20), "today": (21, 20)},
    # fix (b): one burning cell beside the unit, between it and the victim; today's retreat goes back (-x)
    "B_admit": {"wind": "west", "unit": (20, 20), "victim": (26, 20), "fire": [(21, 20)], "kind": "b", "admit": True,
                "n": (20, 21), "today": (19, 20)},
    "B_veto": {"wind": "east", "unit": (20, 20), "victim": (26, 20), "fire": [(21, 20)], "kind": "b", "admit": False,
               "n": (20, 21), "today": (19, 20)},
}
ARMS = {"0": (0, 0, 1), "G": (1, 1, 1), "N": (1, 1, 0)}


def synthetic():
    sys.path.insert(0, REPO)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as ag
    import common_fixed_variables as cfv
    import wildfire_model as wf
    import src_extension.adaptation_manager as amod
    import src_extension.adaptation.local_adaptation_generator as gen
    from src_extension.planning import fire_arrival_estimate as fae
    from src_extension.planning import movement_paths as mpm
    from src_extension.planning.rescue_planner import select_rescue_assignment

    probe = probe_module()
    replay = runpy.run_path(os.path.join(HERE, "_mvg_replay.py"), run_name="mvg_replay_check_module")
    results = []

    def expect(label, cond, detail=""):
        results.append((label, bool(cond), detail))

    # ---- the U1 shadow: loaded BY PATH, never from the repo
    udm, sha = probe["load_u1_shadow"]()
    expect("u1/loaded by path from outputs/_mvg_u1_shadow.py",
           os.path.normcase(os.path.abspath(udm.__file__)) == os.path.normcase(os.path.join(HERE, "_mvg_u1_shadow.py"))
           and udm.__name__ == "mvg_u1_shadow", repr((udm.__file__, udm.__name__)))
    expect("u1/sha256 is the frozen copy's", sha == U1_SHADOW_SHA, sha)
    expect("u1/not importable from the repo", not os.path.exists(os.path.join(REPO, "src_extension", "planning",
                                                                              "urgency_dispatch.py"))
           and "src_extension.planning.urgency_dispatch" not in sys.modules)

    # ---- the replay's knockouts first (class level, BEFORE the probe, as _mvg_replay.main), then the probe
    rules, ko_log = [], {}
    replay["install_ko"](ag, rules, ko_log)
    rec = probe["install"](ag, cfv, wf, amod, gen, fae, udm, mpm)
    cols = list(probe["MV_COLS"])
    gcols = list(probe["GUARD_COLS"])
    fn = probe["shadow_funcs"](ag)
    W = _World(ag, cfv, wf)
    model = W.model
    step = [1000]

    def next_step():
        step[0] += 1
        return step[0]

    def run(board, arm, prep=None):
        """One advance of FF_A on `board` in `arm`; returns (mv row dict, guard rows, events, new mismatch, new ud /
        mvg errors, replica delta)."""
        W.switches(*ARMS[arm])
        bd = BOARDS[board]
        u = W.scene(bd["wind"], bd["unit"], bd["victim"], bd["fire"], next_step())
        if prep is not None:
            prep(u)
        n0, g0, e0, m0 = len(rec["mv_rows"]), len(rec["guard_rows"]), len(rec["mv_events"]), len(rec["mismatch"])
        u0, x0 = len(rec["ud_errors"]), len(rec["mvg_errors"])
        rp0 = {k: (v if isinstance(v, int) else len(v)) for k, v in rec["replica"].items()}
        with contextlib.redirect_stdout(io.StringIO()):
            u.advance()
        rows = rec["mv_rows"][n0:]
        rp1 = {k: (v if isinstance(v, int) else len(v)) for k, v in rec["replica"].items()}
        return (dict(zip(cols, rows[0])) if len(rows) == 1 else None, [dict(zip(gcols, r)) for r in rec["guard_rows"][g0:]],
                rec["mv_events"][e0:], rec["mismatch"][m0:], rec["ud_errors"][u0:] + rec["mvg_errors"][x0:],
                {k: rp1[k] - rp0[k] for k in rp1}, (g0, e0, n0))

    def mini(arm, g0, e0, n0):
        a, b, g = ARMS[arm]
        return ({"mvg": {"switches": {"FF_APPROACH_PATH": a == 1, "FF_RETREAT_KEEP_APPROACH": b == 1,
                                      "FF_FIX_STRANDING_GUARD": g == 1},
                         "guard": {"cols": gcols, "rows": rec["guard_rows"][g0:]}},
                 "mv": {"cols": cols, "rows": rec["mv_rows"]}, "mv_events": rec["mv_events"][e0:]},
                set(range(n0, len(rec["mv_rows"]))))

    # ---- the four boards x three arms
    for board, bd in BOARDS.items():
        k = bd["kind"]
        n, today = list(bd["n"]), list(bd["today"])
        for arm in ("0", "G", "N"):
            label = "%s/arm %s" % (board, arm)
            row, grows, evs, mism, errs, rpd, (g0, e0, n0) = run(board, arm)
            if row is None:
                expect(label + " row", False, "no single mv row")
                continue
            live = arm != "0"
            vetoed = arm == "G" and not bd["admit"]
            fix_taken = live and not vetoed
            want_br = FIX_BRANCH[k] if fix_taken else VETO_BRANCH[k] if vetoed else ("approach" if k == "a" else "retreat")
            expect(label + " branch", row["branch"] == want_br, "got %r want %r" % (row["branch"], want_br))
            expect(label + " post", row["post"] == (n if fix_taken else today), "post %r" % (row["post"],))
            expect(label + " acted (unguarded shadow)", row["acted"] == k and row["f" + k] == n, repr(row["acted"]))
            expect(label + " g%s / veto / acted_g" % k.upper(),
                   row["g" + k.upper()] is bd["admit"] and row["veto"] == (k if vetoed else "")
                   and row["acted_g"] == (k if bd["admit"] else ""),
                   repr((row["g" + k.upper()], row["veto"], row["acted_g"])))
            ok_rows = len(grows) == 1
            g = grows[0] if ok_rows else {}
            expect(label + " one guard row", ok_rows, repr(grows))
            if ok_rows:
                want_model = bd["admit"] if arm == "G" else None
                expect(label + " guard row verdicts", g["admit"] is bd["admit"] and g["model_admit"] is want_model
                       and g["took"] == ("fix" if fix_taken else "today") and g["n"] == n and g["today"] == today
                       and g["u"] == list(bd["unit"]) and g["v"] == list(bd["victim"]),
                       repr({x: g[x] for x in ("admit", "c", "T_v", "model_admit", "took", "n", "today")}))
                expect(label + " guard row ms", (g["ms_guard"] is not None) == (arm == "G") and g["ms_inst"] is not None,
                       repr((g["ms_guard"], g["ms_inst"])))
                if arm == "G":
                    expect(label + " model verdict tuple == instrument's",
                           g["model_verdict"] == [g["admit"], g["c"], g["T_v"]] and g["model_cell"] == n,
                           repr((g["model_verdict"], g["model_cell"])))
            ev = evs[0] if len(evs) == 1 else {}
            expect(label + " event", len(evs) == 1 and ev.get("live") is live and ev.get("vetoed") is vetoed
                   and ev.get("ran") is bool(fix_taken) and ev.get("agree") is (True if live else None),
                   json.dumps(evs))
            expect(label + " no shadow mismatch, no instrument error", not mism and not errs, repr((mism, errs)))
            if k == "b":
                if fix_taken:
                    expect(label + " replica: fix step leaves _idle_retreat_* unchanged",
                           rpd["fix_checked"] == 1 and rpd["fix_mismatch"] == 0, repr(rpd))
                else:
                    expect(label + " replica: today's survival writes == the replica's",
                           rpd["checked"] == 1 and rpd["mismatch"] == 0 and rpd["cell_mismatch"] == 0, repr(rpd))
                    if ok_rows:
                        expect(label + " Zg-2 writes in the guard row", g["pred_writes"] == g["post_writes"]
                               and g["pred_writes"] is not None, repr((g["pred_writes"], g["post_writes"])))
            dd, scope = mini(arm, g0, e0, n0)
            probs, _st = guard_problems(dd, label=label, errors=False, scope=scope)
            expect(label + " guard_problems clean", not probs, "; ".join(probs[:3]))

    # ---- the replica in five _idle_retreat_* states (arm 0: today's _survival_move runs on the B board)
    def state(**kw):
        def prep(u):
            for key, value in kw.items():
                setattr(u, "_idle_retreat_" + key, value)
        return prep

    for name, prep in (("stalled", state(stalled=True, origin=(20, 20))),
                       ("at cap", state(steps=6, origin=(20, 20))),
                       ("last cell excluded", state(origin=(20, 20), last_cell=(19, 20), steps=2)),
                       ("origin far (leashed out)", state(origin=(30, 30), steps=1)),
                       ("origin near, steps 3", state(origin=(21, 21), steps=3))):
        row, grows, evs, mism, errs, rpd, _ = run("B_admit", "0", prep)
        expect("replica/%s: writes and cell == the model's" % name,
               rpd["checked"] == 1 and rpd["mismatch"] == 0 and rpd["cell_mismatch"] == 0 and not errs,
               repr((rpd, errs, rec["replica"]["mismatch"][-1:], rec["replica"]["cell_mismatch"][-1:])))
        if grows:   # fix (b)'s shadow acts unless today's retreat cell is on the route (a guard row only then)
            g = grows[0]
            expect("replica/%s: guard row pred_writes == post_writes" % name, g["pred_writes"] == g["post_writes"],
                   repr({x: g.get(x) for x in ("pre_writes", "pred_writes", "post_writes", "post", "today")}))

    # ---- POSITIVE CONTROLS (each must be SEEN; its rows are removed after)
    def control(label, board, arm, patch, unpatch, want_text, want_problem):
        m0, x0 = len(rec["mismatch"]), len(rec["mvg_errors"])
        patch()
        try:
            row, grows, evs, mism, errs, rpd, (g0, e0, n0) = run(board, arm)
        finally:
            unpatch()
        dd, scope = mini(arm, g0, e0, n0)
        probs, _st = guard_problems(dd, label=label, errors=False, scope=scope)
        seen = [x for x in mism if want_text in str(x[3])] if want_text else []
        expect("control/" + label + " (mismatch detector)", (not want_text) or bool(seen), repr(mism))
        expect("control/" + label + " (guard_problems)", any(want_problem in p for p in probs), repr(probs[:4]))
        del rec["mismatch"][m0:]
        del rec["mvg_errors"][x0:]
        return row, grows, evs, rpd

    FF = ag.Firefighter
    o_guarded = FF._guarded

    def veto_acts(self, step_cell):
        if step_cell is None or not ag.ff_fix_stranding_guard():
            return step_cell
        self._stranding_guard_verdict(step_cell)
        return step_cell

    control("veto acts (the fix's step taken although the model vetoes)", "A_veto", "G",
            lambda: setattr(FF, "_guarded", veto_acts), lambda: setattr(FF, "_guarded", o_guarded),
            "guard vetoes (instrument)", "UNDER-VETO")
    control("veto acts on (b)", "B_veto", "G",
            lambda: setattr(FF, "_guarded", veto_acts), lambda: setattr(FF, "_guarded", o_guarded),
            "guard vetoes (instrument)", "UNDER-VETO")
    o_sg = mpm.stranding_guard

    def inverted(*a, **k):
        adm, c, tv = o_sg(*a, **k)
        return (not adm, c, tv)

    control("the model's verdict inverted on an admit board (over-veto)", "A_admit", "G",
            lambda: setattr(mpm, "stranding_guard", inverted), lambda: setattr(mpm, "stranding_guard", o_sg),
            "model guard verdict != instrument verdict", "OVER-VETO")
    control("the model's verdict inverted on a veto board (under-veto)", "A_veto", "G",
            lambda: setattr(mpm, "stranding_guard", inverted), lambda: setattr(mpm, "stranding_guard", o_sg),
            "model guard verdict != instrument verdict", "UNDER-VETO")
    o_survival = FF._survival_move

    def survival_extra(self):
        o_survival(self)
        self._idle_retreat_steps = int(self._idle_retreat_steps or 0) + 5

    r0 = len(rec["replica"]["mismatch"])
    control("a veto whose _idle_retreat_* writes differ from today's (Zg-2 writes)", "B_veto", "G",
            lambda: setattr(FF, "_survival_move", survival_extra), lambda: setattr(FF, "_survival_move", o_survival),
            None, "_idle_retreat_* writes")
    expect("control/the in-run replica check sees the wrong writes", len(rec["replica"]["mismatch"]) == r0 + 1,
           repr(rec["replica"]["mismatch"][r0:]))
    del rec["replica"]["mismatch"][r0:]
    o_mt = FF._move_toward   # the probe's thin wrapper

    def wrong_step(self, target):
        o_mt(self, target)
        self.model.grid.move_agent(self, (20, 21))

    control("a veto whose step is not today's (Zg-2 cell)", "A_veto", "G",
            lambda: setattr(FF, "_move_toward", wrong_step), lambda: setattr(FF, "_move_toward", o_mt),
            "guard vetoes (instrument), model did not take today's step", "today's step: post")
    o_fbs = ag.fire_board_sets

    def dirty_board_sets(m):
        m._mvg_ctl = int(getattr(m, "_mvg_ctl", 0) or 0) + 1
        return o_fbs(m)

    u0 = len(rec["ud_errors"])
    ag.fire_board_sets = dirty_board_sets
    try:
        run("A_admit", "0")
    finally:
        ag.fire_board_sets = o_fbs
        if hasattr(model, "_mvg_ctl"):
            delattr(model, "_mvg_ctl")
    seen = [e for e in rec["ud_errors"][u0:] if e.startswith("mv_purity") and "_mvg_ctl" in e]
    expect("control/the in-run mv purity guard sees a shadow that writes the model", len(seen) == 1,
           repr(rec["ud_errors"][u0:]))
    del rec["ud_errors"][u0:]

    # ---- deep purity of mv_shadow (guard + replica) on every board, with positive controls
    for board, bd in BOARDS.items():
        W.switches(*ARMS["G"])
        u = W.scene(bd["wind"], bd["unit"], bd["victim"], bd["fire"], next_step())
        before = snapshot(model, ag)
        rec["inst"] += 1
        try:
            S = probe["mv_shadow"](u, model, ag, fn, mpm.stranding_guard, cfv)
        finally:
            rec["inst"] -= 1
        expect("deep purity/mv_shadow on %s" % board, snapshot(model, ag) == before and S is not None
               and S["g" + bd["kind"]] is not None and S["g" + bd["kind"]][0] is bd["admit"],
               repr(S and S.get("g" + bd["kind"])))
    before = snapshot(model, ag)
    u = W.unit()
    old = u._idle_retreat_steps
    u._idle_retreat_steps = old + 1000
    expect("deep purity/control: a unit write is seen", snapshot(model, ag) != before)
    u._idle_retreat_steps = old
    before = snapshot(model, ag)
    st_rng = ag.random.getstate()
    ag.random.random()
    expect("deep purity/control: an RNG draw is seen", snapshot(model, ag) != before)
    ag.random.setstate(st_rng)

    # ---- the replay's knockouts (installed under the probe, as in a replay)
    def ko(rule, board, arm):
        rules[:] = [rule]
        k0 = dict(ko_log)
        try:
            out = run(board, arm)
        finally:
            rules[:] = []
        return out, [v for key, v in ko_log.items() if key not in k0]

    s = step[0] + 1
    (row, grows, evs, mism, errs, rpd, _), new = ko({"unit": FF_A, "kinds": "a", "from": s, "to": s}, "A_admit", "G")
    expect("ko/a: today's step, guard not evaluated, logged", row and row["branch"] == "approach"
           and row["post"] == [21, 20] and not grows and new == [[s, FF_A, "a", [19, 20]]] and not mism,
           repr((row and row["branch"], grows, new, mism)))
    s = step[0] + 1
    (row, grows, evs, mism, errs, rpd, _), new = ko({"unit": "!" + FF_A, "kinds": "ab", "from": 0, "to": 10 ** 6},
                                                    "A_admit", "G")
    expect("ko/!unit does not match the unit itself", row and row["branch"] == "approach_a" and not new,
           repr((row and row["branch"], new)))
    s = step[0] + 1
    (row, grows, evs, mism, errs, rpd, _), new = ko({"unit": "*", "kinds": "b", "from": s, "to": s}, "B_admit", "G")
    expect("ko/b: today's retreat, logged", row and row["branch"] == "retreat" and row["post"] == [19, 20]
           and new == [[s, FF_A, "b", [20, 21]]], repr((row and row["branch"], new)))
    s = step[0] + 1
    (row, grows, evs, mism, errs, rpd, _), new = ko({"unit": FF_A, "kinds": "g", "from": s, "to": s}, "A_veto", "G")
    g = grows[0] if grows else {}
    expect("ko/g (KO-GUARD): the vetoed step is taken as the fix's, logged; the instrument keeps the true verdict",
           row and row["branch"] == "approach_a" and row["post"] == [19, 20] and new == [[s, FF_A, "g", [19, 20]]]
           and g.get("admit") is False and g.get("model_admit") is True and g.get("took") == "fix",
           repr((row and row["branch"], new, {x: g.get(x) for x in ("admit", "model_admit", "took")})))
    del rec["mismatch"][len(rec["mismatch"]) - len(mism):]   # the knocked-out guard disagrees by design
    s = step[0] + 1
    (row, grows, evs, mism, errs, rpd, _), new = ko({"unit": FF_A, "kinds": "g", "from": s, "to": s}, "A_admit", "G")
    expect("ko/g on an admitted step: nothing to knock out, nothing logged", row and row["branch"] == "approach_a"
           and not new and not mism, repr((row and row["branch"], new, mism)))
    s = step[0] + 1
    (row, grows, evs, mism, errs, rpd, _), new = ko({"unit": FF_A, "kinds": "a", "from": s + 1, "to": s + 5},
                                                    "A_admit", "G")
    expect("ko/outside [from, to]: no knockout", row and row["branch"] == "approach_a" and not new, repr(new))
    parse = replay["parse_rules"]
    bad = 0
    for text in ('{"unit": "x"}', '[{"unit": "x", "kinds": "abx"}]', '[{"unit": "x", "kinds": ""}]',
                 '[{"unit": "x", "from": 5, "to": 4}]', '[{"unit": "x", "kind": "a"}]', '[1]'):
        try:
            parse(text)
        except (ValueError, TypeError):
            bad += 1
    expect("ko/the rule parser refuses 6 malformed --ko values", bad == 6, "refused %d" % bad)
    expect("ko/the rule parser accepts the urgency review's rules",
           parse('[{"unit":"ff_unit_1","kinds":"ab","from":0,"to":54}]') == [
               {"unit": "ff_unit_1", "kinds": "ab", "from": 0, "to": 54}])

    # ---- the U1 SHADOW self-check: a synthetic qualifying kick
    W.switches(0, 0, 1)
    cells = {V0: (10, 12), V1: (40, 30), V2: (20, 40)}

    def kick_scene():
        W.quiet()
        model.wind.wind_direction = "north"
        W.place_units({FF_A: (30, 20)})
        W.place_victims(cells)
        W.burn([(25, 10)])
        model.evaluation_timesteps_counter = 100

    kick_scene()
    before = snapshot(model, ag)
    rec["inst"] += 1
    try:
        Ks = probe["kick_shadow"](model, ag, udm, fae, udm.urgency_order, select_rescue_assignment, cfv)
    finally:
        rec["inst"] -= 1
    expect("u1/deep purity of kick_shadow + planner reading", snapshot(model, ag) == before, "")
    k0, m0 = len(rec["kicks"]), len(rec["mismatch"])
    with contextlib.redirect_stdout(io.StringIO()):
        model._try_dispatch_unresolved_confirmed_victims()
    K = rec["kicks"][-1] if len(rec["kicks"]) == k0 + 1 else {}
    expect("u1/a qualifying kick yields a non-None U1 order", K.get("qualifies") is True and K.get("u1") is not None
           and sorted(K["u1"]) == sorted([V0, V1, V2]) and len(K.get("rec") or {}) == 3,
           repr({x: K.get(x) for x in ("qualifies", "index", "u1", "rec")}))
    expect("u1/Z4's independent recomputation equals the shadow's records", K.get("z4_ok") is True,
           repr((K.get("z4"), K.get("rec"))))
    expect("u1/the model binds the index order (no U1 in the model)", K.get("bound") == [[V0, FF_A]]
           and K.get("switch") is False and K.get("acc") == {V0: True, V1: True, V2: True},
           repr((K.get("bound"), K.get("acc"))))
    expect("u1/kick record consistent", not kick_problems(K, False) and len(rec["mismatch"]) == m0,
           repr((kick_problems(K, False), rec["mismatch"][m0:])))
    import numpy as np
    crafted = {cells[V1]: 100.0, cells[V0]: 200.0, cells[V2]: 300.0}
    o_at = udm.arrival_time

    def fake(x_size, y_size, burning, wind, params):
        grid = np.full((x_size, y_size), 1000.0)
        for cell, value in crafted.items():
            grid[cell] = value
        return grid

    udm.arrival_time = fake
    try:
        kick_scene()
        k0 = len(rec["kicks"])
        with contextlib.redirect_stdout(io.StringIO()):
            model._try_dispatch_unresolved_confirmed_victims()
    finally:
        udm.arrival_time = o_at
    K = rec["kicks"][-1] if len(rec["kicks"]) == k0 + 1 else {}
    expect("u1/a crafted estimate: the shadow orders [V1, V0, V2], div_shadow, the model binds V0 (not divergent)",
           K.get("u1") == [V1, V0, V2] and K.get("u1_wb") == V1 and K.get("index_wb") == V0
           and K.get("div_shadow") is True and K.get("divergent") is False and K.get("bound") == [[V0, FF_A]],
           repr({x: K.get(x) for x in ("u1", "u1_wb", "index_wb", "div_shadow", "divergent", "bound")}))

    expect("no instrument errors left", not rec["ud_errors"] and not rec["errors"] and not rec["mvg_errors"],
           repr(rec["ud_errors"] + rec["errors"] + rec["mvg_errors"]))
    expect("no shadow mismatch left", not rec["mismatch"], repr(rec["mismatch"]))
    for label, ok, detail in results:
        print("%-4s %s %s" % ("OK" if ok else "FAIL", label, "" if ok else detail))
    bad = [r for r in results if not r[1]]
    print("synthetic: %d checks, %d failed" % (len(results), len(bad)))
    return 0 if not bad else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    try:
        if cmd == "summary" and len(sys.argv) == 3:
            return summary(sys.argv[2])
        if cmd == "kicks" and len(sys.argv) == 3:
            return kicks(sys.argv[2])
        if cmd == "guard" and len(sys.argv) == 3:
            return guard(sys.argv[2])
        if cmd == "frozen" and len(sys.argv) == 4:
            return frozen(sys.argv[2], sys.argv[3])
        if cmd == "val" and len(sys.argv) in (5, 7) and sys.argv[2] in ("R0", "KOown", "KOothers"):
            return val(sys.argv[2], sys.argv[3], sys.argv[4], *(sys.argv[5:7] if len(sys.argv) == 7 else ()))
        if cmd == "zg3" and len(sys.argv) == 4:
            return zg3(sys.argv[2], sys.argv[3])
        if cmd == "compare" and len(sys.argv) == 4:
            return compare(sys.argv[2], sys.argv[3])
        if cmd == "pair" and len(sys.argv) == 4:
            return pair(sys.argv[2], sys.argv[3])
        if cmd == "synthetic" and len(sys.argv) == 2:
            return synthetic()
        if cmd == "purity" and len(sys.argv) >= 6:
            return purity(int(sys.argv[2]), sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6:])
    except Refused as exc:
        print("MVG CHECK REFUSED: %s" % exc, file=sys.stderr)
        return 2
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
