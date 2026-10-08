"""Verification helper for outputs/_dq_probe.py ("dq_probe v1"; dispatch round 2 Part 2, outputs/dispatch2_part1.txt
12.1, 10.2, 10.3; not a run-loaded file). A port of outputs/_mvg_probe_check.py (mvg round): its summary, kicks and
guard checks (guard_problems verbatim but for the instrument it reads: dq_probe v1's probe_sha), without the movement
round's arm comparisons (pair / zg3 compare arms that do not exist here; Z1-M (i)-(iv) and Zg-3 are void, 10.3) and
without its W3 validation (val: the replay tool's own check, 12.3), plus the round's new checks.

Every subcommand that reads a record REFUSES (exit 2, message on stderr) when a file is missing or unparseable, or a
record is not a dq_probe v1 record; it never guesses. Exit 0 = every check passed, 1 = a check failed.

usage (dispatch worktree root, the parent .venv):
  python outputs/_dq_probe_check.py summary X.json
      the dq / dp-J / mvg digest of one record. Structural fields only (no outcome).
  python outputs/_dq_probe_check.py check X.json [--arm R|0|1]
      one record's PROVENANCE, PURITY and INTERNAL CONSISTENCY:
      - provenance: d['dq'] / d['mvg'] / d['ud'] probe 'dq_probe v1', d['dp'] probe 'dp_probe v3'; dq.probe_sha ==
        mvg.probe_sha == outputs/_dq_probe.py's LF sha256 now; the round-1 shadow's sha == R1_SHADOW_SHA == the file's
        LF sha256 now, no load error; the U1 shadow sha; the arm (inferred, or --arm) against the switches: R = no
        DISPATCH_* key (main), 0 = DISPATCH_JOINT / REASSIGN pinned 0 and off, 1 = both pinned 1 and on; the three FF
        switches pinned 1 on the argv and effective; --repo on the argv; with --crn, fb3.crn.crn_draws > 0;
      - purity: every error list empty (dp, ud, mvg, dq, footprint), ud.shadow_mismatch, mvg.mp_mismatch and the
        replica's mismatch lists empty (the in-run purity guards of every shadow and of the new recorders write into
        those lists);
      - consistency: the movement record (guard_problems, as _mvg_probe_check guard); the kick records (arms R / 0:
        kick_problems; arm 1: no kick record - the shadow is gated); the J record (J off: every J field empty and no
        J point; J on: j_calls / j_timing aligned, every j_detail entry complete, 'unevaluated' empty, Z-R1 recomputed
        from the record twice - by the probe's zr1_check AND by this tool's own independent implementation - both
        empty and the probe's equal to the recorded one, the footprint recomputed offline (the probe's footprint() on
        the record, the repo's joint_dispatch loaded by path, sha-checked against dq.src_sha) equal to the recorded
        one); the sample (one row per step, disjoint victim classes, routes over W + WL, its log rows == the ff_log
        rows of that step and unit, and its W + WL and free-unit routes == dp.waiting's - two independent BFS).
  python outputs/_dq_probe_check.py ident REF.json DQ0.json
      S1 (10.2) on ONE cell: dqR (REF, main 897e93b5) == dq0 value identity on the FROZEN field list S1_FIELDS: a
      listed field missing from either record is a failure. Everything else that differs is reported, never gated
      (the J-only fields, tag / repo / head / out / argv / extra_params / wall_s, the cfv keys absent at main).
  python outputs/_dq_probe_check.py selftest [DQ1.json]
      in-process, NO model step: the probe's pure functions against the repo's joint_dispatch (loaded by path) and the
      frozen round-1 copy on random boards and instances (the instrument's BFS / exemption / unclean set, the fill
      under the corrected and round-1 keys, the planner, the history progress rule, the persistence counters, the
      legacy counterfactual's tie rule), the footprint on hand cases where C1 / C2 / R-1 / R-2 / round 1 must act or
      must not, Z-R1 on a hand-built J point (clean, then five corruptions that must each be flagged), the ident
      rule's positive and negative controls; with DQ1.json also corruption controls on that record's own j_detail.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import importlib.util
import json
import math
import os
import random
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PROBE_FILE = os.path.join(HERE, "_dq_probe.py")
R1_SHADOW_FILE = os.path.join(HERE, "_dq_r1_shadow.py")
U1_SHADOW_SHA = "cfc97ebd6dcc4f3d2b3102468769b7396f78e86d5f93e342f25fe5370632b1cf"
ROW_FIELDS = ("rows_ff", "rows_vic", "rows_uav", "rows_dec", "rows_trig")
FIX_TIER = {"a": 7, "b": 10}
FIX_BRANCH = {"a": "approach_a", "b": "retreat_b"}
VETO_BRANCH = {"a": "approach_a_veto", "b": "retreat_b_veto"}
TODAY_BRANCH = {"a": ("approach",), "b": ("retreat", "retreat_fb")}
FF_SWITCHES = ("FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH", "FF_FIX_STRANDING_GUARD")
FF_ACTIONS = ("extinguish", "clear", "move", "retreat", "none")
# ---- S1 (10.2): the FROZEN field list. Round 1's G-ID fields (_fx3r_analyze FIELDS, every mf2 section but its probe
# string, every dp field that exists without J) plus eval / rows_*, fb3 / mr / ut, the movement record (mv rows without
# fix_ms / inst_ms, mv_events, the guard rows without ms_guard / ms_inst), the per-step sample and the firefighting log.
FX3R_FIELDS = ("rows_uav", "rows_ff", "rows_vic", "rows_dec", "rows_trig", "eval", "terminal_step", "steps_done",
               "crashed", "stdout_sha", "stdout_tags", "inline_violations", "warning_count")
DP_J_ONLY = ("probe", "switches", "src_sha", "j_calls", "j_events", "ledger", "timing", "rc_chain", "j_detail",
             "j_timing")
DP_NON_J_REQUIRED = ("binders", "waiting", "waiting_custody", "m3a", "invariant", "commands", "releases", "m8", "m9",
                     "writeoffs_avoided")
S1_SECTIONS = ("fb3", "mr", "ut")
MV_DROP = ("fix_ms", "inst_ms")
GUARD_DROP = ("ms_guard", "ms_inst")
NOT_COMPARED_TOP = ("tag", "repo", "head", "out", "argv", "extra_params", "wall_s", "src_sha", "dp", "dq", "ud", "mv",
                    "mv_events", "mvg", "fb3", "mr", "ut", "mf2", "fx3", "params")
_PROBE = {}


class Refused(Exception):
    pass


def refuse(msg):
    raise Refused(msg)


def lf_sha256(path):
    """sha256 of a file's LF-normalised bytes (CRLF read as LF): the checker's own copy of the probe's rule."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


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
        _PROBE.update(runpy.run_path(PROBE_FILE, run_name="dq_probe_check_module"))
    return _PROBE


def load_repo_jd(repo=REPO):
    """The repo's src_extension/planning/joint_dispatch.py loaded BY PATH under a private module name (the corrected J
    the record's arm ran; nothing else of the repo is imported). Returns (module, sha256 of its bytes)."""
    path = os.path.join(repo, "src_extension", "planning", "joint_dispatch.py")
    if not os.path.isfile(path):
        refuse("no joint_dispatch.py in %s" % repo)
    with open(path, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    name = "dq_check_joint_dispatch"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module, sha


def need_dq(d, path):
    P = probe_module()
    dq = d.get("dq")
    if not isinstance(dq, dict) or dq.get("probe") != P["VERSION"]:
        refuse("%s is not a %s record (d['dq']['probe'] = %r)" % (
            path, P["VERSION"], (dq or {}).get("probe") if isinstance(dq, dict) else None))
    if ((d.get("mvg") or {}).get("guard") or {}).get("cols") != list(P["GUARD_COLS"]):
        refuse("%s: guard cols differ from GUARD_COLS" % path)
    if (d.get("mv") or {}).get("cols") != list(P["MV_COLS"]):
        refuse("%s: mv cols differ from MV_COLS" % path)
    if (dq.get("sample") or {}).get("cols") != list(P["SAMPLE_COLS"]) or \
            (dq.get("sample") or {}).get("unit_cols") != list(P["SAMPLE_UNIT_COLS"]):
        refuse("%s: sample cols differ from SAMPLE_COLS / SAMPLE_UNIT_COLS" % path)
    return dq


def argv_sets(d):
    """{KEY: VALUE} of the record's --set arguments (the run line)."""
    argv = d.get("argv") or []
    out = {}
    for i, a in enumerate(argv):
        if a == "--set" and i + 1 < len(argv) and "=" in argv[i + 1]:
            k, v = argv[i + 1].split("=", 1)
            out[k] = v
    return out


def arm_of(d):
    """R (no DISPATCH_* key at all: main), 1 (J and reassignment on), 0 (J off), '?' otherwise."""
    sw = (d.get("dq") or {}).get("switches") or {}
    raw = sw.get("raw") or {}
    if raw.get("DISPATCH_JOINT") == "None" and raw.get("DISPATCH_REASSIGN") == "None":
        return "R"
    if sw.get("joint_on") is True and sw.get("reassign_on") is True:
        return "1"
    if sw.get("joint_on") is False and sw.get("reassign_on") is False:
        return "0"
    return "?"


def _pct(values, q):
    v = sorted(values)
    if not v:
        return None
    return v[min(len(v) - 1, int(math.ceil(q * len(v))) - 1)]


# ------------------------------------------------------------------------------------------------- summary
def summary(path):
    d = load(path)
    dq = need_dq(d, path)
    dp = d.get("dp") or {}
    print("probe", dq.get("probe"), "| dp", dp.get("probe"), "| arm", arm_of(d), "| rc", dp.get("rc_chain"), "| steps",
          d.get("steps_done"), "| crashed", d.get("crashed"))
    print("dq switches", json.dumps(dq.get("switches")))
    psha = lf_sha256(PROBE_FILE)
    print("probe sha", dq.get("probe_sha"), "(outputs/_dq_probe.py now: %s)" % (
        "SAME" if dq.get("probe_sha") == psha else "DIFFERS, %s" % psha[:16]))
    print("r1 shadow sha", dq.get("r1_shadow_sha"), "error", dq.get("r1_shadow_error"))
    print("errors: dq %d, dp %d, ud %d, mvg %d | shadow_mismatch %d | kick_gated %s" % (
        len(dq.get("errors") or []), len(dp.get("errors") or []), len((d.get("ud") or {}).get("errors") or []),
        len((d.get("mvg") or {}).get("errors") or []), len((d.get("ud") or {}).get("shadow_mismatch") or []),
        dq.get("kick_gated")))
    print("J: j_calls %d, j_detail %d, j_events %d (%s), ledger %d pairs" % (
        len(dp.get("j_calls") or []), len(dp.get("j_detail") or []), len(dp.get("j_events") or []),
        dict(collections.Counter(e.get("kind") for e in dp.get("j_events") or [])), len(dp.get("ledger") or {})))
    tm = [r[3] for r in dp.get("j_timing") or []]
    print("J net ms per call: n %d, p50 %s, p99 %s, max %s | totals %s" % (
        len(tm), _pct(tm, 0.5), _pct(tm, 0.99), max(tm) if tm else None, json.dumps(dp.get("timing"))))
    print("zr1", json.dumps({k: v for k, v in (dq.get("zr1") or {}).items() if k != "mismatch"}),
          "| footprint", json.dumps({k: (v if k != "base_ne_actual" else len(v)) for k, v in
                                     (dq.get("footprint") or {}).items()}))
    kinds = collections.Counter()
    for _s, _ph, cur in dp.get("j_detail") or []:
        for c in cur.get("calls") or []:
            kinds[c.get("fn")] += 1
    print("cap records", dict(kinds))
    sm = (dq.get("sample") or {}).get("rows") or []
    print("sample rows %d (steps %s..%s), unit rows %d, ff_log rows %d" % (
        len(sm), sm[0][0] if sm else None, sm[-1][0] if sm else None, sum(len(r[5]) for r in sm),
        len((dq.get("ff_log") or {}).get("rows") or [])))
    print("timing", json.dumps(dq.get("timing")))
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
    """v2 definition / consistency problems of one kick record (_mvg_probe_check.kick_problems, verbatim)."""
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


# ------------------------------------------------------------------------------------------------- guard
def _zg2(r, tag):
    """Zg-2's identities for a decision where TODAY's step ran (_mvg_probe_check._zg2, verbatim)."""
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
    """_mvg_probe_check.guard_problems VERBATIM but for the instrument it names: the record's probe_sha must be
    outputs/_dq_probe.py's (dq_probe v1 writes d['mvg']['probe_sha'] = d['dq']['probe_sha'])."""
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
        if "mp_verdict" not in r or r["mp_verdict"] != [r["admit"], r["c"], r["T_v"]]:
            st["mp_verdict differs"] += 1
            probs.append(tag + ": CROSS-CHECK: movement_paths.stranding_guard %r != the instrument's frozen-function "
                         "verdict %r" % (r.get("mp_verdict", "<no column>"), [r["admit"], r["c"], r["T_v"]]))
        else:
            st["mp_verdict equal"] += 1
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
            probs.append("%s: the U1 shadow copy: sha %r (LF form) error %r" % (label, mvg.get("u1_shadow_sha"),
                                                                                mvg.get("u1_shadow_error")))
        mm = mvg.get("mp_mismatch")
        n_diff = 0
        for raw in (mvg.get("guard") or {}).get("rows") or []:
            g = dict(zip(gcols, raw))
            if len(raw) == len(gcols) and g["mp_verdict"] != [g["admit"], g["c"], g["T_v"]]:
                n_diff += 1
        if not isinstance(mm, list):
            probs.append("%s: no d['mvg']['mp_mismatch'] list (not an instrument with the cross-check)" % label)
        else:
            if mm:
                probs.append("%s: mp_mismatch: %d %r" % (label, len(mm), mm[:3]))
            if len(mm) != n_diff:
                probs.append("%s: mp_mismatch lists %d rows, %d guard rows differ" % (label, len(mm), n_diff))
        # the instrument that wrote the record: outputs/_dq_probe.py on disk now (dq_probe v1)
        want = lf_sha256(PROBE_FILE)
        if mvg.get("probe_sha") != want:
            probs.append("%s: d['mvg']['probe_sha'] %r is not outputs/_dq_probe.py's LF sha256 %s" % (
                label, mvg.get("probe_sha"), want[:16]))
        t = mvg.get("timing") or {}
        n_model = sum(1 for raw in (mvg.get("guard") or {}).get("rows") or []
                      if dict(zip(gcols, raw))["model_admit"] is not None)
        if t.get("guard_calls") != n_model:
            probs.append("%s: %r model guard calls timed, %d guard rows with a model verdict" % (
                label, t.get("guard_calls"), n_model))
    return probs, st


# ------------------------------------------------------------------------------------------------- Z-R1 (own)
def _fmin(values):
    finite = [v for v in values if v is not None]
    return min(finite) if finite else None


def own_progress(H, k, kl, route_open, d, c, dh, ch, cell, frozen):
    """This tool's OWN statement of R-1's history rule with C2's counts (2.8, 5.2; amendment A2's reading of an empty
    finite set) - written apart from the probe's hist_progress."""
    cells = {(int(x), int(y)) for x, y in H}
    cells.add((int(cell[0]), int(cell[1])))
    grown = [[x, y] for x, y in sorted(cells)]
    if not route_open:
        return grown, k, kl + (0 if frozen else 1), True
    best_d, best_c = _fmin(dh), _fmin(ch)
    gained = d == 0 or (best_d is not None and d < best_d) or (c is not None and best_c is not None and c < best_c)
    if d is not None and gained:
        return [[int(cell[0]), int(cell[1])]], 0, 0, False
    return grown, k + (0 if frozen else 1), 0, False


def own_zr1(cur):
    """Z-R1 on one j_detail entry by THIS tool's own reading of the record (independent of the probe's zr1_check): every
    d* / clean / open / d / D_c / d over H / D_c over H / FROZEN / delta J passed, and the k / k_L / H it derived,
    against the entry's inst maps and own_progress. Returns (problems, n_checked)."""
    inst, sets = cur["inst"], cur["sets"]
    dist, ucell, vcell, hist = inst["dist"], inst["ucell"], inst["vcell"], inst.get("hist") or {}
    free = sets["free"]
    probs, n = [], 0

    def cell_of(u):
        return (ucell[u][0], ucell[u][1])

    def look(v, u):
        if v not in dist or u not in dist[v]:
            return None
        return dist[v][u]

    def delta(u, v, row):
        if row[0] is not None:
            return row[2]
        return abs(cell_of(u)[0] - vcell[v][0]) + abs(cell_of(u)[1] - vcell[v][1])

    def frozen(u, v):
        return not (look(v, u)[3] or any((look(v, f) or [None, None, None, False])[3] for f in free))

    derived = {}
    for c in cur.get("calls") or []:
        fn = c.get("fn")
        if fn == "solve_fill":
            for u in c["units"]:
                for v in c["victims"]:
                    n += 1
                    row = look(v, u)
                    key = "%s|%s" % (u, v)
                    if row is None or c["d"].get(key) != row[2] or c["clean"].get(key) is not bool(row[3]):
                        probs.append("own: solve_fill %s" % key)
        elif fn == "progress_step":
            n += 1
            u, v = c["binding"] or (None, None)
            row = look(v, u) if u else None
            key = "%s|%s" % (u, v)
            h = (hist.get(key) or {}).get("H")
            before = (cur.get("progress_before") or {}).get(key)
            if row is None or h is None or before is None:
                probs.append("own: progress_step %s unresolvable" % key)
                continue
            op = row[0] is not None
            want_c = row[1] if op else None
            fz = frozen(u, v)
            if (c["open"], c["d"], c["c"], list(c["d_hist"]), list(c["c_hist"]), c["frozen"]) != \
                    (op, row[0], want_c, [x[0] for x in h], [x[1] for x in h], fz):
                probs.append("own: progress_step %s inputs" % key)
            H1, k1, kl1, cl1 = own_progress(before[0], before[1], before[2], op, row[0], want_c,
                                            [x[0] for x in h], [x[1] for x in h], cell_of(u), fz)
            derived[key] = (k1, kl1)
            if c["after"][:4] != [H1, k1, kl1, cl1]:
                probs.append("own: progress_step %s verdict" % key)
        elif fn == "update_persistence":
            n += 1
            u, v = c["binding"] or (None, None)
            row = look(v, u) if u else None
            key = "%s|%s" % (u, v)
            if row is None or c["delta"] != delta(u, v, row) or any(
                    d != (look(v, b) or [None, None, None])[2] for b, d in c["spare_d"].items()):
                probs.append("own: update_persistence %s" % key)
        elif fn == "plan_replacements_detail":
            for vv, u, dl, op, kk, kl, _persist, latched in c["contests"]:
                n += 1
                row = look(vv, u)
                key = "%s|%s" % (u, vv)
                want_k = derived.get(key, (0, 0))
                if row is None or dl != delta(u, vv, row) or op != (row[0] is not None) or (kk, kl) != want_k or \
                        bool(latched) != (str(ucell[u][3]).strip().lower() == "route_blocked"):
                    probs.append("own: plan contest %s" % key)
            for key, d in c["d"].items():
                n += 1
                b, vv = key.split("|", 1)
                row = look(vv, b)
                if row is None or d != row[2] or c["clean"].get(key) is not bool(row[3]):
                    probs.append("own: plan spare %s" % key)
    return probs, n


# ------------------------------------------------------------------------------------------------- check
def j_problems(d, arm, jd=None, r1m=None):
    """The J record's consistency (see the module docstring). Returns (problems, counts)."""
    P = probe_module()
    dp, dq = d.get("dp") or {}, d.get("dq") or {}
    probs = []
    st = collections.Counter()
    jc, jt, jdl = dp.get("j_calls") or [], dp.get("j_timing") or [], dp.get("j_detail") or []
    if arm in ("R", "0"):
        for name in ("j_calls", "j_detail", "j_timing", "j_events"):
            if dp.get(name):
                probs.append("J off: dp.%s holds %d entries" % (name, len(dp.get(name))))
        if (dq.get("zr1") or {}).get("jpoints") or (dq.get("footprint") or {}).get("jpoints"):
            probs.append("J off: J points recorded")
        if (dp.get("timing") or {}).get("j_ms_total"):
            probs.append("J off: J time recorded")
        return probs, st
    if len(jc) != len(jt) or any(a[:2] != b[:2] for a, b in zip(jc, jt)):
        probs.append("j_calls (%d) and j_timing (%d) are not aligned" % (len(jc), len(jt)))
    for row in jt:
        if row[3] > row[2] + 1e-6:
            probs.append("j_timing step %s: net %s > raw %s" % (row[0], row[3], row[2]))
            break
    z = dq.get("zr1") or {}
    if z.get("jpoints") != len(jdl):
        probs.append("zr1.jpoints %r != %d j_detail entries" % (z.get("jpoints"), len(jdl)))
    if z.get("n_mismatch"):
        probs.append("Z-R1 (recorded in-run): %d mismatches, first %r" % (z.get("n_mismatch"), (z.get("mismatch") or [])[:2]))
    fpr = dq.get("footprint") or {}
    if fpr.get("errors"):
        probs.append("footprint errors: %r" % (fpr.get("errors")[:3],))
    need = ("sets", "pre", "calls", "progress_before", "progress", "unevaluated", "initialised", "inst", "contests",
            "zr1", "fp")
    acted = collections.Counter()
    ne_actual = 0
    for step, phase, cur in jdl:
        tag = "j_detail step %s %s" % (step, phase)
        miss = [k for k in need if k not in cur]
        if miss:
            probs.append(tag + ": missing %r" % miss)
            continue
        st["j points"] += 1
        st["cap records"] += len(cur["calls"])
        if cur["unevaluated"]:
            probs.append(tag + ": unevaluated contests %r (a structural 0 in the corrected J)" % cur["unevaluated"])
        if cur["zr1"]:
            probs.append(tag + ": Z-R1 recorded %r" % cur["zr1"][:2])
        again, n, a2, rows = P["zr1_check"](copy.deepcopy(cur))
        st["Z-R1 values checked (probe rule)"] += n
        st["A2 literal differs"] += a2
        if again != cur["zr1"]:
            probs.append(tag + ": zr1_check recomputed offline %r != recorded %r" % (again[:2], cur["zr1"][:2]))
        if rows != cur["contests"]:
            probs.append(tag + ": contest rows recomputed offline differ")
        own, n2 = own_zr1(cur)
        st["Z-R1 values checked (own rule)"] += n2
        if own:
            probs.append(tag + ": Z-R1 (this tool's own reading): %r" % own[:3])
        for c in cur["calls"]:
            if c.get("fn") in ("progress_step", "update_persistence") and not c.get("binding"):
                probs.append(tag + ": a %s record without its binding" % c.get("fn"))
        voi = set(cur["inst"]["dist"])
        need_v = set(cur["sets"]["waiting"]) | set(cur["sets"]["latched"]) | set(cur["sets"]["contest"]) | \
            set(cur["sets"]["latched_binder"])
        if voi != need_v:
            probs.append(tag + ": inst victims %r != W + W_L + contests %r" % (sorted(voi), sorted(need_v)))
        if jd is not None:
            fp, _r1a, _rv1a = P["footprint"](copy.deepcopy(cur), jd, r1m)
            mine = {k: cur["fp"].get(k) for k in fp}
            if fp != mine:
                probs.append(tag + ": footprint recomputed offline differs: %r" % (
                    [k for k in fp if fp[k] != mine[k]],))
        for name in cur["fp"].get("acted") or []:
            acted[name] += 1
        if cur["fp"].get("base_eq_actual") is False:
            ne_actual += 1
    st["base != actual"] = ne_actual
    for k, v in acted.items():
        st["acted " + k] = v
    if dict(acted) != {k: v for k, v in (fpr.get("acted") or {}).items() if v}:
        probs.append("footprint.acted %r != the entries' %r" % (fpr.get("acted"), dict(acted)))
    if len(jdl) and not any(cur.get("calls") for _s, _p, cur in jdl):
        probs.append("J on, PRE held at %d J points, but no cap record was made" % len(jdl))
    return probs, st


def sample_problems(d):
    """The sample's consistency (see the module docstring). Returns (problems, counts)."""
    dq, dp = d.get("dq") or {}, d.get("dp") or {}
    probs = []
    st = collections.Counter()
    rows = (dq.get("sample") or {}).get("rows") or []
    if not rows:
        return ["no sample rows"], st
    steps = [r[0] for r in rows]
    if steps != list(range(steps[0], steps[0] + len(steps))):
        probs.append("sample steps are not one per step: %r..." % steps[:5])
    log = collections.defaultdict(list)
    fcols = (dq.get("ff_log") or {}).get("cols") or []
    fi = {c: i for i, c in enumerate(fcols)}
    for r in (dq.get("ff_log") or {}).get("rows") or []:
        log[(r[fi["step"]], str(r[fi["ff"]]))].append([r[fi["action"]], r[fi["wrote"]]])
    waiting = {r[0]: r for r in dp.get("waiting") or []}
    for step, W, WL, custody, active, units in rows:
        st["rows"] += 1
        allv = W + WL + custody + active
        if len(allv) != len(set(allv)):
            probs.append("step %s: victim classes overlap" % step)
        targets = sorted(W + WL)
        for u in units:
            st["unit rows"] += 1
            uid, status, free, bound, cell, moved, routes, ulog = u
            if [r[0] for r in routes] != targets:
                probs.append("step %s unit %s: routes over %r, W + WL %r" % (step, uid, [r[0] for r in routes], targets))
            if bound and not free:
                probs.append("step %s unit %s: a bound unit sampled without being free" % (step, uid))
            for a, _w in ulog:
                if a not in FF_ACTIONS:
                    probs.append("step %s unit %s: unknown firefighting action %r" % (step, uid, a))
            if ulog != log.get((step, uid), []):
                probs.append("step %s unit %s: log rows %r != ff_log %r" % (step, uid, ulog, log.get((step, uid), [])))
            st["log rows"] += len(ulog)
            if moved is None:
                st["moved None"] += 1
            elif moved:
                st["moved"] += 1
            st["status " + str(status)] += 1
        # the cross-check against dp.waiting (round 1's recorder: its own BFS)
        w = waiting.get(step)
        if w is None:
            probs.append("step %s: no dp.waiting row" % step)
            continue
        if sorted(v for v, _c in w[2]) != targets:
            probs.append("step %s: dp.waiting victims %r != W + WL %r" % (step, sorted(v for v, _c in w[2]), targets))
            continue
        mine = {}
        for u in units:
            if u[2]:
                for v, dv in u[6]:
                    if dv is not None:
                        mine[(v, u[0])] = dv
        theirs = {(v, f): dv for v, cand in w[2] for f, dv, _b in cand}
        if mine != theirs:
            probs.append("step %s: free-unit routes %r != dp.waiting %r" % (step, mine, theirs))
        st["route cross-checks"] += len(theirs)
    n_log = sum(len(v) for v in log.values())
    if st["log rows"] > n_log:
        probs.append("the sample holds %d log rows, the ff_log %d" % (st["log rows"], n_log))
    return probs, st


def check(path, arm=None):
    d = load(path)
    dq = need_dq(d, path)
    P = probe_module()
    results = []

    def res(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    dp, ud, mvg = d.get("dp") or {}, d.get("ud") or {}, d.get("mvg") or {}
    got_arm = arm_of(d)
    res("arm %s (inferred %s)" % (arm or got_arm, got_arm), got_arm != "?" and (arm is None or arm == got_arm))
    arm = arm or got_arm
    # ---- provenance
    res("versions dq/mvg/ud %r, dp %r" % (P["VERSION"], P["DP_VERSION"]),
        dq.get("probe") == mvg.get("probe") == ud.get("probe") == P["VERSION"] and dp.get("probe") == P["DP_VERSION"])
    psha = lf_sha256(PROBE_FILE)
    res("probe_sha == mvg.probe_sha == outputs/_dq_probe.py (LF) now", dq.get("probe_sha") == mvg.get("probe_sha") == psha,
        "%r / %r / %s" % (dq.get("probe_sha"), mvg.get("probe_sha"), psha[:16]))
    rsha = lf_sha256(R1_SHADOW_FILE)
    res("round-1 shadow sha == R1_SHADOW_SHA == outputs/_dq_r1_shadow.py (LF) now, loaded",
        dq.get("r1_shadow_sha") == P["R1_SHADOW_SHA"] == rsha and not dq.get("r1_shadow_error"),
        "%r / %r" % (dq.get("r1_shadow_sha"), dq.get("r1_shadow_error")))
    res("U1 shadow sha", mvg.get("u1_shadow_sha") == U1_SHADOW_SHA and not mvg.get("u1_shadow_error"))
    argv = d.get("argv") or []
    res("--repo on the argv", "--repo" in argv)
    sets = argv_sets(d)
    sw = dq.get("switches") or {}
    ff_ok = all(sets.get(k) == "1" and sw.get(k) is True for k in FF_SWITCHES)
    res("the three FF switches pinned 1 and effective", ff_ok, json.dumps({k: [sets.get(k), sw.get(k)] for k in FF_SWITCHES}))
    if arm == "R":
        ok = not any(k.startswith("DISPATCH_") for k in sets) and "src_extension/planning/joint_dispatch.py" not in \
            (dq.get("src_sha") or {})
        res("arm R: no DISPATCH_* set, no joint_dispatch module in the checkout", ok)
    elif arm == "0":
        res("arm 0: DISPATCH_JOINT / DISPATCH_REASSIGN pinned 0, off",
            sets.get("DISPATCH_JOINT") == "0" and sets.get("DISPATCH_REASSIGN") == "0" and sw.get("joint_on") is False)
    elif arm == "1":
        res("arm 1: DISPATCH_JOINT / DISPATCH_REASSIGN pinned 1, on",
            sets.get("DISPATCH_JOINT") == "1" and sets.get("DISPATCH_REASSIGN") == "1" and sw.get("joint_on") is True
            and sw.get("reassign_on") is True)
    crn = (d.get("fb3") or {}).get("crn") or {}
    draws = crn.get("crn_draws")
    res("CRN on (--crn) with crn_draws > 0 (%r; 0 draws = INVALID, section 9)" % draws,
        crn.get("on") is True and isinstance(draws, int) and draws > 0, json.dumps(crn))
    res("run complete (rc 0, not crashed)", dp.get("rc_chain") == 0 and not d.get("crashed"),
        "rc %r crashed %r" % (dp.get("rc_chain"), d.get("crashed")))
    # ---- purity (the in-run guards write here)
    for name, lst in (("dq.errors", dq.get("errors")), ("dp.errors", dp.get("errors")), ("ud.errors", ud.get("errors")),
                      ("mvg.errors", mvg.get("errors")), ("ud.shadow_mismatch", ud.get("shadow_mismatch")),
                      ("mvg.mp_mismatch", mvg.get("mp_mismatch")),
                      ("footprint.errors", (dq.get("footprint") or {}).get("errors"))):
        res("purity / errors: %s empty" % name, not lst, repr((lst or [])[:3]))
    # ---- movement record
    gp, gst = guard_problems(d, label="")
    res("movement record (guard_problems)", not gp, "; ".join(gp[:4]))
    # ---- kicks
    ks = ud.get("kicks") or []
    if arm == "1":
        res("arm 1: the U1 kick shadow gated (no kick record; %r gated)" % dq.get("kick_gated"), not ks)
    else:
        kp = []
        for K in ks:
            kp += kick_problems(K, False)
        res("kick records (%d, kick_problems)" % len(ks), not kp and not dq.get("kick_gated"), "; ".join(kp[:3]))
    # ---- J
    jd = r1m = None
    if arm == "1":
        jd, jsha = load_repo_jd(REPO)
        want = (dq.get("src_sha") or {}).get("src_extension/planning/joint_dispatch.py")
        if jsha != want:
            res("the repo's joint_dispatch.py is the run's (src_sha)", False, "%s vs %s: footprint not recomputed" % (
                jsha[:16], str(want)[:16]))
            jd = None
        r1m, _sha = P["load_r1_shadow"](R1_SHADOW_FILE)
    jp, jst = j_problems(d, arm, jd, r1m)
    res("J record (arm %s)" % arm, not jp, "; ".join(jp[:4]))
    # ---- sample
    sp, sst = sample_problems(d)
    res("per-step sample", not sp, "; ".join(sp[:3]))
    print("CHECK %s (arm %s)" % (os.path.basename(path), arm))
    for name, ok, detail in results:
        print("  %-4s %s %s" % ("OK" if ok else "FAIL", name, "" if ok else detail))
    print("  counts: guard %s" % json.dumps(dict(sorted(gst.items()))))
    print("  counts: J %s" % json.dumps(dict(sorted(jst.items()))))
    print("  counts: sample %s" % json.dumps(dict(sorted(sst.items()))))
    bad = [x for x in results if not x[1]]
    print("  %d checks, %d failed" % (len(results), len(bad)))
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------------- ident (S1)
def _drop_cols(rows, cols, drop):
    keep = [i for i, c in enumerate(cols) if c not in drop]
    return [[r[i] for i in keep] for r in rows]


def s1_fields(d):
    """{field name: value} of one record on S1_FIELDS (10.2); a missing field reads as the sentinel '<MISSING>'."""
    P = probe_module()
    miss = "<MISSING>"
    out = {}
    for f in FX3R_FIELDS:
        out[f] = d.get(f, miss)
    mf2 = d.get("mf2")
    if not isinstance(mf2, dict):
        out["mf2"] = miss
    else:
        for k in sorted(mf2):
            if k != "probe":
                out["mf2." + k] = mf2[k]
    dp = d.get("dp")
    if not isinstance(dp, dict):
        out["dp"] = miss
    else:
        for k in DP_NON_J_REQUIRED:
            out["dp." + k] = dp.get(k, miss)
        for k in sorted(set(dp) - set(DP_J_ONLY) - set(DP_NON_J_REQUIRED)):
            out["dp." + k] = dp[k]
    for sec in S1_SECTIONS:
        out[sec] = d.get(sec, miss)
    mv = d.get("mv")
    out["mv.rows (no fix_ms / inst_ms)"] = miss if not isinstance(mv, dict) else \
        _drop_cols(mv.get("rows") or [], mv.get("cols") or [], MV_DROP)
    out["mv.cols"] = miss if not isinstance(mv, dict) else mv.get("cols")
    out["mv_events"] = d.get("mv_events", miss)
    g = (d.get("mvg") or {}).get("guard")
    out["mvg.guard.rows (no ms_guard / ms_inst)"] = miss if not isinstance(g, dict) else \
        _drop_cols(g.get("rows") or [], g.get("cols") or list(P["GUARD_COLS"]), GUARD_DROP)
    dq = d.get("dq") or {}
    out["dq.sample"] = dq.get("sample", miss)
    out["dq.ff_log"] = dq.get("ff_log", miss)
    return out


def ident(ref_path, dq0_path):
    a, b = load(ref_path), load(dq0_path)
    need_dq(a, ref_path)
    need_dq(b, dq0_path)
    for f in ("seed", "scenario", "wind", "steps"):
        if a.get(f) != b.get(f):
            refuse("not the same cell: %s %r vs %r" % (f, a.get(f), b.get(f)))
    if arm_of(a) != "R" or arm_of(b) != "0":
        refuse("ident reads a dqR record and a dq0 record (got arms %s / %s)" % (arm_of(a), arm_of(b)))
    if argv_sets(a).get("VICTIM_SPAWN_MODE") != argv_sets(b).get("VICTIM_SPAWN_MODE"):
        refuse("not the same placement")
    fa, fb = s1_fields(a), s1_fields(b)
    bad, rows = s1_compare(fa, fb)
    print("S1 (10.2) %s (dqR) vs %s (dq0): %d fields" % (os.path.basename(ref_path), os.path.basename(dq0_path),
                                                       len(rows)))
    for name, ok, detail in rows:
        print("  %-4s %s %s" % ("OK" if ok else "DIFF", name, detail))
    # reported, never gated
    rep = []
    for k in sorted(set(a) | set(b)):
        if k in FX3R_FIELDS or k in S1_SECTIONS or k in NOT_COMPARED_TOP:
            continue
        if a.get(k) != b.get(k):
            rep.append(k)
    pa, pb = a.get("params") or {}, b.get("params") or {}
    rep += ["params.%s" % k for k in sorted(set(pa) & set(pb)) if pa[k] != pb[k]]
    absent = sorted(set(pb) - set(pa)) + sorted(set(pa) - set(pb))
    if (a.get("fx3") or {}) != (b.get("fx3") or {}):
        rep.append("fx3")
    for k in ("kicks", "decisions", "fates", "cmd_ctx", "rel_ctx"):
        if (a.get("ud") or {}).get(k) != (b.get("ud") or {}).get(k):
            rep.append("ud." + k)
    for k in ("replica", "mp_mismatch"):
        if (a.get("mvg") or {}).get(k) != (b.get("mvg") or {}).get(k):
            rep.append("mvg." + k)
    print("  reported, not gated - differing: %r; cfv keys in one record only (absent at main): %r" % (rep, absent))
    print("  S1 %s" % ("PASS (value-identical on every listed field)" if not bad else "FAIL: %r" % bad))
    return 1 if bad else 0


def s1_compare(fa, fb):
    """(failing field names, [(name, ok, detail)]) of two s1_fields maps."""
    rows = []
    bad = []
    for k in sorted(set(fa) | set(fb)):
        x, y = fa.get(k, "<MISSING>"), fb.get(k, "<MISSING>")
        ok = x == y and x != "<MISSING>"
        detail = ""
        if not ok:
            if x == "<MISSING>" or y == "<MISSING>":
                detail = "missing in %s" % ("both" if x == y else "REF" if x == "<MISSING>" else "DQ0")
            elif isinstance(x, list) and isinstance(y, list):
                i = next((i for i in range(min(len(x), len(y))) if x[i] != y[i]), min(len(x), len(y)))
                detail = "first difference at index %d (%d vs %d items)" % (i, len(x), len(y))
            else:
                detail = "values differ"
            bad.append(k)
        rows.append((k, ok, detail))
    return bad, rows


# ------------------------------------------------------------------------------------------------- selftest
def selftest(record=None):
    P = probe_module()
    jd, _sha = load_repo_jd(REPO)
    r1m, r1sha = P["load_r1_shadow"](R1_SHADOW_FILE)
    rng = random.Random(20261008)
    results = []

    def expect(label, cond, detail=""):
        results.append((label, bool(cond), detail))

    expect("round-1 shadow loads by path, sha %s" % r1sha[:16], r1sha == P["R1_SHADOW_SHA"] and r1m.__name__ ==
           P["R1_SHADOW_MODULE"])
    # 1. the instrument's BFS, exemption and unclean set against joint_dispatch's
    bad = 0
    for _ in range(300):
        w, h = rng.randint(3, 12), rng.randint(3, 12)
        cells = [(x, y) for x in range(w) for y in range(h)]
        burning = set(rng.sample(cells, rng.randint(0, len(cells) // 3)))
        smoky = set(rng.sample(cells, rng.randint(0, len(cells) // 4)))
        v = rng.choice(cells)
        unclean_i = P["inst_unclean"](burning, smoky, w, h)
        unclean_j = {c for c in jd.unclean_cells(burning, smoky) if 0 <= c[0] < w and 0 <= c[1] < h}
        if unclean_i != unclean_j:
            bad += 1
            continue
        fi = P["inst_map"](v, w, h, burning)
        fj = jd.bfs_distances(v, w, h, burning)
        ci = None if v in unclean_i else P["inst_map"](v, w, h, unclean_i)
        cj = None if v in unclean_j else jd.bfs_distances(v, w, h, jd.unclean_cells(burning, smoky))
        for u in cells:
            if P["inst_at"](fi, w, h, u, burning) != jd.route_distance(fj, u, burning):
                bad += 1
            want_c = None if cj is None else jd.route_distance(cj, u, jd.unclean_cells(burning, smoky))
            if P["inst_at"](ci, w, h, u, unclean_i) != want_c:
                bad += 1
    expect("BFS / unit-cell exemption / unclean set == joint_dispatch's on 300 random boards", bad == 0, "%d" % bad)
    # 2. fills
    bad_c = bad_r1 = 0
    for _ in range(400):
        units = ["ff_unit_%d" % i for i in rng.sample(range(12), rng.randint(0, 4))]
        victims = ["victim_%d" % i for i in rng.sample(range(12), rng.randint(0, 4))]
        dist, ledger, clean = {}, {}, {}
        for u in units:
            for v in victims:
                dist[(u, v)] = None if rng.random() < 0.2 else rng.randint(0, 9)
                ledger[(u, v)] = rng.choice((0, 0, 1, 2))
                clean[(u, v)] = rng.random() < 0.6
        capped = [v for v in victims if rng.random() < 0.3]
        got = P["fill_generic"](units, victims, dist, ledger, clean, capped=capped, key="cor")
        want = [(p.victim, p.unit, p.distance, p.reused, p.clean)
                for p in jd.solve_fill(units, victims, dist, ledger, clean=clean, capped=capped)]
        bad_c += got != want
        got1 = [(v, u, dd, ru) for v, u, dd, ru, _cl in
                P["fill_generic"](units, victims, dist, ledger, clean, capped=capped, key="r1")]
        want1 = [(p.victim, p.unit, p.distance, p.reused) for p in r1m.solve_fill(units, victims, dist, ledger,
                                                                                  capped=capped)]
        bad_r1 += got1 != want1
    expect("fill_generic 'cor' == joint_dispatch.solve_fill (400 instances)", bad_c == 0, "%d" % bad_c)
    expect("fill_generic 'r1' == round 1's solve_fill (400 instances)", bad_r1 == 0, "%d" % bad_r1)
    # 3. planners
    bad_p = bad_p1 = 0
    for _ in range(400):
        spares = ["ff_unit_%d" % i for i in rng.sample(range(8), rng.randint(0, 4))]
        contests = []
        for vi in rng.sample(range(8), rng.randint(1, 3)):
            v = "victim_%d" % vi
            op = rng.random() < 0.7
            contests.append({"victim": v, "incumbent": "ff_unit_%d" % (20 + vi), "delta": rng.randint(0, 15),
                             "open": op, "k": rng.randint(0, 14), "k_closed": rng.randint(0, 14),
                             "persist": {s: rng.randint(0, 4) for s in spares if rng.random() < 0.6},
                             "latched": rng.random() < 0.3})
        dist, ledger, clean = {}, {}, {}
        for s in spares:
            for c in contests:
                dist[(s, c["victim"])] = None if rng.random() < 0.15 else rng.randint(0, 15)
                ledger[(s, c["victim"])] = rng.choice((0, 0, 1, 2))
                clean[(s, c["victim"])] = rng.random() < 0.7
        objs = [jd.Contest(victim=c["victim"], incumbent=c["incumbent"], delta=c["delta"], route_open=c["open"],
                           k=c["k"], k_closed=c["k_closed"], persist=c["persist"], latched=c["latched"])
                for c in contests]
        reps, barred = jd.plan_replacements_detail(objs, spares, dist, ledger, clean, stall_steps=10, margin_persist=3)
        want = ([[r.victim, r.old_unit, r.new_unit, r.cause, r.distance, bool(r.latched)] for r in reps],
                [[b.victim, b.incumbent, b.cause, b.distance, list(b.units)] for b in barred])
        bad_p += tuple(P["plan_generic"](contests, spares, dist, ledger, clean, 10, 3)) != want
        # round 1 = nearest allowed (fresh), margin without the clean requirement, on open active contests
        c1s = [dict(c, open=True, latched=False) for c in contests]
        o1 = [r1m.Contest(victim=c["victim"], incumbent=c["incumbent"], d=c["delta"], k=c["k"], persist=c["persist"])
              for c in c1s]
        w1 = [[r.victim, r.old_unit, r.new_unit, r.cause, r.distance, False]
              for r in r1m.plan_replacements(o1, spares, dist, ledger, clean, stall_steps=10, margin_persist=3)]
        g1, _b = P["plan_generic"](c1s, spares, dist, ledger, clean, 10, 3, nearest_allowed=True, margin_clean=False)
        bad_p1 += g1 != w1
    expect("plan_generic == joint_dispatch.plan_replacements_detail (400 instances)", bad_p == 0, "%d" % bad_p)
    expect("plan_generic(nearest allowed, margin without clean) == round 1's plan_replacements (400)", bad_p1 == 0,
           "%d" % bad_p1)
    # 4. progress and persistence
    bad_h = bad_o = bad_q = bad_q1 = 0
    for _ in range(1000):
        H = sorted({(rng.randint(0, 9), rng.randint(0, 9)) for _i in range(rng.randint(1, 4))})
        k, kl = rng.randint(0, 12), rng.randint(0, 12)
        op = rng.random() < 0.8
        d = rng.randint(0, 20) if op else None
        c = (None if rng.random() < 0.4 else rng.randint(0, 25)) if op else None
        dh = [None if rng.random() < 0.3 else rng.randint(0, 20) for _ in H]
        ch = [None if rng.random() < 0.5 else rng.randint(0, 25) for _ in H]
        cell = (rng.randint(0, 9), rng.randint(0, 9))
        fz = rng.random() < 0.2
        st = jd.Progress(history=tuple(H), k=k, k_closed=kl)
        out = jd.progress_step(st, op, d, c, tuple(dh), tuple(ch), cell, fz)
        mine = P["hist_progress"]([list(x) for x in H], k, kl, op, d, c, dh, ch, cell, fz)
        bad_h += [[list(x) for x in out.history], out.k, out.k_closed, out.closed] != list(mine[:4])
        own = own_progress([list(x) for x in H], k, kl, op, d, c, dh, ch, cell, fz)
        bad_o += [[list(x) for x in out.history], out.k, out.k_closed, out.closed] != list(own)
        spare_d = {"ff_unit_%d" % i: (None if rng.random() < 0.2 else rng.randint(0, 20)) for i in range(4)}
        prev = {"ff_unit_%d" % i: rng.randint(1, 3) for i in range(5) if rng.random() < 0.5}
        delta = rng.randint(0, 20)
        st2 = jd.Progress(history=((0, 0),), persist=tuple(sorted(prev.items())))
        bad_q += dict(jd.update_persistence(st2, spare_d, delta, 5).persist_map()) != \
            P["persist_generic"](prev, spare_d, delta, 5)
        fresh = {u: rng.random() < 0.6 for u in spare_d}
        s1 = r1m.Progress(best=3, k=0, d_prev=3, cell_prev=(0, 0), persist=tuple(sorted(prev.items())))
        bad_q1 += dict(r1m.update_persistence(s1, spare_d, delta, 5, fresh).persist_map()) != \
            P["persist_generic"](prev, spare_d, delta, 5, fresh)
    expect("hist_progress == joint_dispatch.progress_step (1000 instances)", bad_h == 0, "%d" % bad_h)
    expect("this tool's own_progress == joint_dispatch.progress_step (1000 instances)", bad_o == 0, "%d" % bad_o)
    expect("persist_generic == joint_dispatch.update_persistence (1000)", bad_q == 0, "%d" % bad_q)
    expect("persist_generic(fresh) == round 1's update_persistence (1000)", bad_q1 == 0, "%d" % bad_q1)
    # the e-shift hybrid reduces to round 1's progress_step on open routes with x and a reference
    bad_e = 0
    for _ in range(500):
        best, kk, dprev = rng.randint(0, 20), rng.randint(0, 9), rng.randint(0, 20)
        d, x = rng.randint(0, 20), rng.randint(0, 20)
        fz = rng.random() < 0.2
        s = r1m.progress_step(r1m.Progress(best=best, k=kk, d_prev=dprev, cell_prev=(1, 1)), d, x, (2, 2), fz)
        hyb = P["eshift_hybrid"]({"best": best, "k": kk, "d_prev": dprev, "cell_prev": [1, 1], "k_closed": 4,
                                  "closed": True, "age": 0, "persist": {}}, True, d, x, (2, 2), fz)
        bad_e += [s.best, s.k, s.d_prev, list(s.cell_prev)] != [hyb["best"], hyb["k"], hyb["d_prev"],
                                                                 hyb["cell_prev"]] or hyb["k_closed"] != 0
    expect("eshift_hybrid == round 1's progress_step on open routes (500)", bad_e == 0, "%d" % bad_e)
    # 5. the legacy counterfactual's tie rule (select_rescue_assignment: smaller id STRING)
    pairs = P["legacy_pairs_data"](["victim_10", "victim_2"], {"victim_10": (0, 0), "victim_2": (5, 5)},
                                   ["ff_unit_2", "ff_unit_10"], {"ff_unit_2": (5, 6), "ff_unit_10": (5, 4)})
    expect("legacy: victim-index order, nearest unchosen, ties to the smaller id string",
           pairs == [["victim_2", "ff_unit_10"], ["victim_10", "ff_unit_2"]], repr(pairs))
    # 6. the footprint on hand cases
    for label, cur, want_acted in hand_cases():
        fp, _a, _b = P["footprint"](cur, jd, r1m)
        expect("footprint %s: acted %r" % (label, want_acted), fp["acted"] == want_acted and fp["base_eq_actual"],
               "acted %r base_eq_actual %r base %r alt %r" % (fp["acted"], fp["base_eq_actual"], fp["base"], fp["alt"]))
        fp2, _a, _b = P["footprint"](copy.deepcopy(cur), jd, r1m)
        expect("footprint %s: deterministic" % label, fp == fp2)
    # 7. Z-R1 on a hand-built J point, then corruptions
    cur = zr1_case(jd)
    probs, n, _a2, _rows = P["zr1_check"](copy.deepcopy(cur))
    own, n2 = own_zr1(copy.deepcopy(cur))
    expect("Z-R1 hand J point: clean (%d / %d values)" % (n, n2), not probs and not own and n > 0, repr(probs + own))
    for label, mutate in zr1_corruptions():
        bad_cur = copy.deepcopy(cur)
        mutate(bad_cur)
        p1, _n, _a, _r = P["zr1_check"](copy.deepcopy(bad_cur))
        p2, _n2 = own_zr1(copy.deepcopy(bad_cur))
        expect("Z-R1 corruption flagged by both readings: %s" % label, bool(p1) and bool(p2), "%r / %r" % (p1, p2))
    # 8. ident's controls
    base = {"rows_ff": [[1]], "eval": {"rescued": 1}, "mf2": {"probe": "x", "uav": [1]},
            "dp": {"commands": [1], "j_calls": [1]}, "fb3": {}, "mr": {}, "ut": {},
            "mv": {"cols": ["step", "fix_ms"], "rows": [[1, 0.5]]}, "mv_events": [],
            "mvg": {"guard": {"cols": list(P["GUARD_COLS"]), "rows": []}}, "dq": {"sample": {}, "ff_log": {}}}
    for f in FX3R_FIELDS:
        base.setdefault(f, None)
    for k in DP_NON_J_REQUIRED:
        base["dp"].setdefault(k, [])
    other = copy.deepcopy(base)
    other["dp"]["j_calls"] = [2]
    other["mv"]["rows"] = [[1, 0.9]]
    other["mf2"]["probe"] = "y"
    bad1, _rows = s1_compare(s1_fields(base), s1_fields(other))
    expect("ident: J-only / timing / mf2.probe differences are not gated", not bad1, repr(bad1))
    for label, mutate in (("rows_ff", lambda x: x["rows_ff"].append([2])),
                          ("dp.commands", lambda x: x["dp"]["commands"].append(2)),
                          ("mv rows", lambda x: x["mv"]["rows"].append([2, 0.1])),
                          ("dq.sample missing", lambda x: x["dq"].pop("sample")),
                          ("dp.m9 missing", lambda x: x["dp"].pop("m9"))):
        x = copy.deepcopy(base)
        mutate(x)
        bad2, _rows = s1_compare(s1_fields(base), s1_fields(x))
        expect("ident: a %s difference fails S1" % label, bool(bad2), repr(bad2))
    # 9. corruption controls on a real dq1 record
    if record:
        d = load(record)
        need_dq(d, record)
        jdl = (d.get("dp") or {}).get("j_detail") or []
        done = collections.Counter()
        for _s, _p, cur in jdl:
            for i, c in enumerate(cur.get("calls") or []):
                fn = c.get("fn")
                if done[fn] >= 2:
                    continue
                bad_cur = copy.deepcopy(cur)
                cc = bad_cur["calls"][i]
                if fn == "solve_fill" and cc["d"]:
                    k = sorted(cc["d"])[0]
                    cc["d"][k] = (cc["d"][k] or 0) + 1
                elif fn == "progress_step":
                    cc["frozen"] = not cc["frozen"]
                elif fn == "update_persistence":
                    cc["delta"] = (cc["delta"] or 0) + 1
                elif fn == "plan_replacements_detail" and cc["contests"]:
                    cc["contests"][0][4] += 1
                else:
                    continue
                p1, _n, _a, _r = P["zr1_check"](copy.deepcopy(bad_cur))
                p2, _n2 = own_zr1(copy.deepcopy(bad_cur))
                expect("record %s: a corrupted %s record is flagged" % (os.path.basename(record), fn),
                       bool(p1) and bool(p2), "%r / %r" % (p1[:1], p2[:1]))
                done[fn] += 1
        for fn in ("solve_fill", "progress_step", "update_persistence", "plan_replacements_detail"):
            if not done[fn]:
                print("  (record %s: no %s record to corrupt - NOT EXERCISED)" % (os.path.basename(record), fn))
    for label, ok, detail in results:
        print("%-4s %s %s" % ("OK" if ok else "FAIL", label, "" if ok else detail))
    bad = [r for r in results if not r[1]]
    print("selftest: %d checks, %d failed" % (len(results), len(bad)))
    return 0 if not bad else 1


def _entry(free, W, WL, contest, lb, ucell, vcell, dist, ledger=None, progress_before=None, binders=None,
           hist=None, post=True, reassign=True, r1_before=None, rv1_before=None, calls=None):
    """A j_detail entry (the probe's form) built by hand."""
    voi = list(dict.fromkeys(list(W) + list(WL) + list(contest) + list(lb)))
    return {"sets": {"free": list(free), "waiting": list(W), "latched": list(WL), "contest": dict(contest),
                     "latched_binder": dict(lb), "fill_victims": list(W) if reassign else list(W) + list(WL),
                     "binders": binders or {v: [] for v in voi}, "reassign": reassign, "post": post},
            "pre": True, "calls": calls or [], "progress_before": progress_before or {},
            "inst": {"digest": "", "nB": 0, "nS": 0, "ucell": ucell, "vcell": vcell, "dist": dist, "hist": hist or {},
                     "ledger": ledger or {}, "SMP": [10, 5, 3]},
            "fp": {"r1_before": r1_before or {}, "rv1_before": rv1_before or {}}}


def hand_cases():
    """(label, entry, the variants that must act) - a board without fire (d == D_c == d*) unless stated."""
    out = []
    # C1: a nearer RE-USED unit beats a farther fresh one in the corrected key; C1 / round 1 send the fresh one
    ucell = {"ff_unit_0": [0, 0, False, "available"], "ff_unit_1": [9, 9, False, "available"]}
    vcell = {"victim_0": [1, 1, True]}
    dist = {"victim_0": {"ff_unit_0": [2, 2, 2, True], "ff_unit_1": [16, 16, 16, True]}}
    out.append(("C1 nearer re-used unit", _entry(["ff_unit_0", "ff_unit_1"], ["victim_0"], [], {}, {}, ucell, vcell,
                                                  dist, ledger={"ff_unit_0|victim_0": 1}), ["r1", "C1"]))
    # R-2: a clean-approach unit beats a NEARER unit without one; R-2 reverted takes the nearer
    dist = {"victim_0": {"ff_unit_0": [2, None, 2, False], "ff_unit_1": [16, 16, 16, True]}}
    out.append(("R-2 clean approach first", _entry(["ff_unit_0", "ff_unit_1"], ["victim_0"], [], {}, {}, ucell, vcell,
                                                    dist), ["r1", "R2"]))
    # R-1: d* ranks a clean detour; d ranks the fire-free shortcut
    dist = {"victim_0": {"ff_unit_0": [4, 20, 20, True], "ff_unit_1": [6, 8, 8, True]}}
    out.append(("R-1 d* not d", _entry(["ff_unit_0", "ff_unit_1"], ["victim_0"], [], {}, {}, ucell, vcell, dist),
                ["r1", "R1"]))
    # C2: a latched incumbent with a small G and a far spare: the corrected J keeps it; C2 / round 1 latch-fill
    ucell = {"ff_unit_0": [5, 5, False, "route_blocked"], "ff_unit_1": [30, 30, False, "available"]}
    vcell = {"victim_0": [5, 8, True]}
    dist = {"victim_0": {"ff_unit_0": [None, None, None, False], "ff_unit_1": [50, 50, 50, True]}}
    pb = {"ff_unit_0|victim_0": [[[5, 5]], 0, 0, True, 1, {}]}
    hist = {"ff_unit_0|victim_0": {"H": [[None, None]]}}
    out.append(("C2 latched incumbent kept", _entry(["ff_unit_1"], [], ["victim_0"], {}, {"victim_0": "ff_unit_0"},
                                                     ucell, vcell, dist, progress_before=pb, hist=hist,
                                                     binders={"victim_0": ["ff_unit_0"]},
                                                     rv1_before={"ff_unit_0|victim_0": {
                                                         "best": None, "k": 0, "d_prev": None, "cell_prev": [5, 5],
                                                         "k_closed": 0, "closed": True, "age": 1, "persist": {}}}),
                ["r1", "C2"]))
    # nothing acts: one fresh clean unit, no fire
    ucell = {"ff_unit_0": [0, 0, False, "available"]}
    vcell = {"victim_0": [1, 1, True]}
    dist = {"victim_0": {"ff_unit_0": [2, 2, 2, True]}}
    out.append(("no variant acts", _entry(["ff_unit_0"], ["victim_0"], [], {}, {}, ucell, vcell, dist), []))
    # the actual decision (cap outputs) must equal base for every hand case: add the stage-2 cap output from base
    P = probe_module()
    jd, _sha = load_repo_jd(REPO)
    for _label, cur, _want in out:
        base, _rv = P["_fp_corrected"](cur, jd, "base")
        fills = [[p[1], p[2], 0, False, True] for p in base["pairs"] if p[0] == "fill"]
        if fills:
            cur["calls"].append({"fn": "solve_fill", "stage": 2, "units": [], "victims": [], "d": {}, "clean": {},
                                 "b": {}, "capped": [], "out": fills})
    return out


def zr1_case(jd):
    """A hand-built J-post with one active contest (ff_unit_0 -> victim_0), one free spare (ff_unit_1) and one waiting
    victim (victim_1); the cap records are J's own functions on the entry's inst values, in the probe's format."""
    ucell = {"ff_unit_0": [2, 2, False, "en_route"], "ff_unit_1": [8, 8, False, "available"]}
    vcell = {"victim_0": [4, 4, True], "victim_1": [9, 9, True]}
    dist = {"victim_0": {"ff_unit_0": [4, 6, 6, True], "ff_unit_1": [8, 8, 8, True]},
            "victim_1": {"ff_unit_0": [14, 14, 14, True], "ff_unit_1": [2, None, 2, False]}}
    pb = {"ff_unit_0|victim_0": [[[2, 3], [3, 3]], 2, 0, False, 5, {"ff_unit_1": 1}]}
    hist = {"ff_unit_0|victim_0": {"H": [[5, 7], [4, 6]]}}
    cur = _entry(["ff_unit_1"], ["victim_1"], [], {"victim_0": "ff_unit_0"}, {}, ucell, vcell, dist,
                 progress_before=pb, hist=hist, binders={"victim_1": [], "victim_0": ["ff_unit_0"]})
    P = probe_module()
    st = P["_jd_progress"](jd, pb["ff_unit_0|victim_0"])
    after = jd.progress_step(st, True, 4, 6, (5, 4), (7, 6), (2, 2), False)
    fill = jd.solve_fill(["ff_unit_1"], ["victim_1"], {("ff_unit_1", "victim_1"): 2}, {},
                         clean={("ff_unit_1", "victim_1"): False})
    cur["calls"] = [
        {"fn": "progress_step", "binding": ["ff_unit_0", "victim_0"], "open": True, "d": 4, "c": 6, "d_hist": [5, 4],
         "c_hist": [7, 6], "cell": [2, 2], "frozen": False, "before": pb["ff_unit_0|victim_0"][:5],
         "after": P["jd_progress_row"](after)[:5]},
        {"fn": "solve_fill", "stage": 2, "units": ["ff_unit_1"], "victims": ["victim_1"], "d": {"ff_unit_1|victim_1": 2},
         "clean": {"ff_unit_1|victim_1": False}, "b": {}, "capped": [],
         "out": [[p.victim, p.unit, p.distance, bool(p.reused), bool(p.clean)] for p in fill]},
        {"fn": "update_persistence", "binding": ["ff_unit_0", "victim_0"], "spare_d": {}, "delta": 6, "M": 5,
         "before": {"ff_unit_1": 1}, "after": {}},
    ]
    return cur


def zr1_corruptions():
    def d_star(cur):
        cur["calls"][1]["d"]["ff_unit_1|victim_1"] = 3

    def clean(cur):
        cur["calls"][1]["clean"]["ff_unit_1|victim_1"] = True

    def frozen(cur):
        cur["calls"][0]["frozen"] = True

    def hist(cur):
        cur["calls"][0]["d_hist"] = [5, 5]

    def verdict(cur):
        cur["calls"][0]["after"][1] += 1

    def delta(cur):
        cur["calls"][2]["delta"] = 4

    return (("a d* in the fill", d_star), ("a clean flag in the fill", clean), ("FROZEN", frozen),
            ("d over H", hist), ("the progress verdict k", verdict), ("the incumbent's delta", delta))


# ------------------------------------------------------------------------------------------------- synthetic
class _World:
    """Hand-built boards on a REAL WildFireModel (the movement round's _mvg_probe_check._World, trimmed): fire is set
    on the Fire agents as numpy.bool_, the simulator's own type after its first tick."""

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
        import contextlib
        import io
        self._quiet_out = lambda: contextlib.redirect_stdout(io.StringIO())
        with self._quiet_out():
            self.model = wf.WildFireModel()
        self.model.debug_log = False

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
        with self._quiet_out():
            return bool(self.model.apply_physical_rescue_command(self.wf.PhysicalRescueCommand(
                action="assign", victim_id=vid, firefighter_id=ff_id, reason="initial",
                metadata={"victim_marker": marker, "target_pos": tuple(marker.pos)})))


def synthetic():
    """In-process, NO model step: the probe installed on a REAL WildFireModel of this checkout; hand-built boards
    driven through the real (wrapped) _sync_firefighter_marker_status, i.e. the revalidation, the real J-post and the
    sample, with DISPATCH_JOINT / DISPATCH_REASSIGN set on cfv per scene. Exercises the paths a short run does not:
    a fill on a nearer re-used pair (C1), a stall REPLACE, a margin REPLACE, a nearest-barred frame, a latched
    incumbent on a closed route kept and then LATCH-FILLed, and the sample with W / W_L non-empty. Every J point must
    pass Z-R1 (both readings) and base == actual; the expected J event and footprint variants are asserted."""
    import contextlib
    import io
    sys.path.insert(0, REPO)
    os.environ.setdefault("MPLBACKEND", "Agg")
    import agents as ag
    import common_fixed_variables as cfv
    import wildfire_model as wf
    import src_extension.adaptation_manager as amod
    import src_extension.adaptation.local_adaptation_generator as gen
    from src_extension.planning import fire_arrival_estimate as fae
    from src_extension.planning import movement_paths as mpm
    P = probe_module()
    udm, _s = P["load_u1_shadow"]()
    r1m, _s1 = P["load_r1_shadow"](R1_SHADOW_FILE)
    jd = wf._jd
    rec = P["install"](ag, cfv, wf, amod, gen, fae, udm, mpm, r1m)
    for name in FF_SWITCHES:
        setattr(cfv, name, 1)
    W = _World(ag, cfv, wf)
    m = W.model
    results = []
    step = [500]

    def expect(label, cond, detail=""):
        results.append((label, bool(cond), detail))

    V0, A, B, C = "victim_0", "ff_unit_0", "ff_unit_1", "ff_unit_2"

    def scene(joint, units, victim_cell, fire=(), bind=None, status=None, progress=None, ledger=None):
        cfv.DISPATCH_JOINT, cfv.DISPATCH_REASSIGN = joint, joint
        W.quiet()
        W.place_units(units)
        W.place_victims({V0: victim_cell})
        m._dispatch_ledger = {}
        m._dispatch_progress = {}
        if bind is not None:
            assert W.assign(V0, bind), "assign failed"
        if status is not None:
            m.firefighter_marker_agents[bind].status = status
        m._dispatch_ledger = dict(ledger or {})
        m._dispatch_progress = dict(progress or {})
        W.burn(fire)
        step[0] += 1
        m.evaluation_timesteps_counter = step[0]
        n_jd, n_ev, n_s = len(rec["j_detail"]), len(getattr(m, "_dispatch_events", None) or []), len(rec["dq_sample"])
        with contextlib.redirect_stdout(io.StringIO()):
            m._sync_firefighter_marker_status()
        return (rec["j_detail"][n_jd:], (getattr(m, "_dispatch_events", None) or [])[n_ev:], rec["dq_sample"][n_s:])

    def jcheck(label, entries, want_kind=None, want_reason=None, events=(), acted=None, contest=None):
        expect("%s: one J-post entry with PRE" % label, len(entries) == 1, "%d entries" % len(entries))
        if len(entries) != 1:
            return None
        cur = json.loads(json.dumps(entries[0][2], default=str))
        own, n2 = own_zr1(cur)
        expect("%s: Z-R1 clean (%d cap records, %d values by this tool's reading)" % (label, len(cur["calls"]), n2),
               not cur["zr1"] and not own, repr(cur["zr1"][:2] + own[:2]))
        expect("%s: base == actual" % label, cur["fp"]["base_eq_actual"], repr(cur["fp"]))
        kinds = [(e.get("kind"), e.get("reason")) for e in events]
        if want_kind is not None:
            expect("%s: J event %s / %s" % (label, want_kind, want_reason), (want_kind, want_reason) in kinds, repr(kinds))
        else:
            expect("%s: no J bind" % label, not [k for k in kinds if k[0] in ("fill", "replace", "latch_fill")],
                   repr(kinds))
        if acted is not None:
            expect("%s: footprint acted %r" % (label, acted), set(acted) <= set(cur["fp"]["acted"]),
                   repr(cur["fp"]["acted"]))
        if contest is not None:
            row = dict(zip(P["CONTEST_COLS"], cur["contests"][0])) if cur["contests"] else {}
            got = {k: row.get(k) for k in contest}
            expect("%s: contest row %r" % (label, contest), got == contest, repr(got))
        fp2, _a, _b = P["footprint"](copy.deepcopy(cur), jd, r1m)
        expect("%s: footprint recomputed from the JSON entry" % label,
               all(fp2[k] == cur["fp"].get(k) for k in fp2), repr(fp2))
        return cur

    vc = (25, 25)
    # S-a: J off, a waiting victim: the sample's W, routes and the dp.waiting cross-check
    _e, ev, smp = scene(0, {A: (25, 28), B: (25, 40)}, vc)
    row = smp[0] if smp else None
    expect("S-a: J off - no J point, no event", not _e and not ev)
    expect("S-a: sample W = [victim_0], routes 3 / 15",
           row is not None and row[1] == [V0] and [[u[0], u[6]] for u in row[5]] == [[A, [[V0, 3]]], [B, [[V0, 15]]]],
           repr(row))
    # S-b: C1 - a nearer RE-USED unit is filled (round 1 and C1-reverted send the fresh, farther one)
    e, ev, _s = scene(1, {A: (25, 28), B: (25, 40)}, vc, ledger={(A, V0): 1})
    jcheck("S-b C1 fill", e, "fill", "joint_initial", ev, acted=["r1", "C1"])
    # S-c: stall REPLACE: the incumbent 20 away, its history holds a cell 15 away (no progress), k 10 -> 11
    prog = {(A, V0): jd.Progress(history=((25, 40),), k=10)}
    e, ev, _s = scene(1, {A: (25, 45), B: (25, 30)}, vc, bind=A, progress=prog)
    jcheck("S-c stall", e, "replace", "reassign_stall", ev,
           contest={"open": True, "delta": 20, "k0": 10, "k1": None, "progressed": False})
    # S-d: nearest barred: the nearest qualifying spare has b = 1; a farther fresh one exists (C1-reverted takes it)
    prog = {(A, V0): jd.Progress(history=((25, 40),), k=10)}
    e, ev, _s = scene(1, {A: (25, 45), B: (25, 30), C: (25, 33)}, vc, bind=A, progress=prog, ledger={(B, V0): 1})
    jcheck("S-d nearest barred", e, "nearest_barred", "nearest_barred_stall", ev, acted=["C1"])
    expect("S-d: no replacement", not [x for x in ev if x.get("kind") == "replace"], repr(ev))
    # S-e: margin REPLACE: progress (21 -> 20), persistence 2 -> 3 for a spare 5 away (5 + 5 <= 20)
    prog = {(A, V0): jd.Progress(history=((25, 46),), k=0, persist=((B, 2),))}
    e, ev, _s = scene(1, {A: (25, 45), B: (25, 30)}, vc, bind=A, progress=prog)
    jcheck("S-e margin", e, "replace", "reassign_margin", ev, contest={"open": True, "delta": 20, "progressed": True})
    # S-f: a LATCHED incumbent whose route is CLOSED (its 4 neighbours burn), G = 3, a far clean spare: kept
    ring = [(24, 28), (26, 28), (25, 27), (25, 29)]
    prog = {(A, V0): jd.Progress(history=((25, 28),), closed=True)}
    e, ev, smp = scene(1, {A: (25, 28), B: (40, 25)}, vc, fire=ring, bind=A, status="route_blocked", progress=prog)
    jcheck("S-f latched kept", e, None, None, ev, acted=["r1", "C2"],
           contest={"latched": True, "open": False, "delta": 3, "kL0": 0, "kL1": 1})
    row = smp[0] if smp else None
    expect("S-f: sample WL = [victim_0], the spare's route 15, the bound latched unit not sampled",
           row is not None and row[2] == [V0] and [[u[0], u[6]] for u in row[5]] == [[B, [[V0, 15]]]], repr(row))
    # S-g: the same, closed for 20 counted J-posts: k_L 21 >= S and 15 < 3 + 21 -> LATCH-FILL
    prog = {(A, V0): jd.Progress(history=((25, 28),), closed=True, k_closed=20)}
    e, ev, _s = scene(1, {A: (25, 28), B: (40, 25)}, vc, fire=ring, bind=A, status="route_blocked", progress=prog)
    jcheck("S-g latch fill", e, "latch_fill", "joint_replace_latched", ev,
           contest={"latched": True, "open": False, "delta": 3, "kL1": None})
    # S-h POSITIVE CONTROL: a defect in J's route builder (joint_dispatch.route_distance reads one step long) must show
    # as Z-R1 mismatches in-run and by this tool's reading; the instrument's own maps never call it
    o_rd = jd.route_distance

    def long_route(dist, cell, blocked):
        value = o_rd(dist, cell, blocked)
        return None if value is None else value + 1

    jd.route_distance = long_route
    try:
        e, ev, _s = scene(1, {A: (25, 28), B: (25, 40)}, vc)
    finally:
        jd.route_distance = o_rd
    cur = json.loads(json.dumps(e[0][2], default=str)) if e else {"zr1": [], "calls": [], "inst": {}, "sets": {}}
    own = own_zr1(cur)[0] if e else []
    expect("S-h control: a one-step-long J route builder is flagged by the in-run Z-R1 and by this tool",
           bool(cur["zr1"]) and bool(own), "%r / %r" % (cur["zr1"][:1], own[:1]))
    expect("synthetic: no instrument error (dq / dp / ud / mvg)", not (rec["dq_errors"] or rec["errors"] or
                                                                       rec["ud_errors"] or rec["mvg_errors"]),
           repr(rec["dq_errors"][:2] + rec["errors"][:2] + rec["ud_errors"][:2] + rec["mvg_errors"][:2]))
    # the sample / dp.waiting cross-check over every sample row of the scenes (one per scene)
    d = {"dq": {"sample": {"rows": [r for r in rec["dq_sample"]]}, "ff_log": {"cols": list(P["FFLOG_COLS"]),
                                                                          "rows": P["ff_log_rows"](m)}},
         "dp": {"waiting": rec["waiting"]}}
    sp, sst = sample_problems(d)
    sp = [p for p in sp if "not one per step" not in p]   # scenes are separate steps, one row each
    expect("synthetic: sample consistency and the dp.waiting route cross-check (%d route pairs)" %
           sst["route cross-checks"], not sp and sst["route cross-checks"] >= 3, "; ".join(sp[:3]))
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
        if cmd == "check" and len(sys.argv) == 3:
            return check(sys.argv[2])
        if cmd == "check" and len(sys.argv) == 5 and sys.argv[3] == "--arm" and sys.argv[4] in ("R", "0", "1"):
            return check(sys.argv[2], sys.argv[4])
        if cmd == "ident" and len(sys.argv) == 4:
            return ident(sys.argv[2], sys.argv[3])
        if cmd == "selftest" and len(sys.argv) in (2, 3):
            return selftest(sys.argv[2] if len(sys.argv) == 3 else None)
        if cmd == "synthetic" and len(sys.argv) == 2:
            return synthetic()
    except Refused as exc:
        print("DQ CHECK REFUSED: %s" % exc, file=sys.stderr)
        return 2
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
