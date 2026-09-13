#!/usr/bin/env python
"""dcd4rb round: read the route_blocked gate at dcD's settings.

Implements outputs/dcd4rb_prereg.txt sections 3-9. Read-only on every data file;
runs no simulation. Every UAV-side definition is IMPORTED from outputs/_dcd4_analyze.py
(AN) and outputs/_dcd4_freezes.py (FZ) - nothing is re-derived here, so the numbers
are the dcd4 round's instruments applied to this sample.

ARMS (tags configurable so the script can be dry-run on committed arms):
  --D drgD:drhD   --Z drgZ:drhZ   --K drgK:drhK   (gate shard tag : harness tag)
  --ext drl       extension-run tag prefix (drlD / drlZ / drlK, 300 steps)

MODES
  instruments  prereg 9: (a) harness eval == shard eval per tuple; (b) harness arms vs
               committed dfD / dfzero (and K vs fix-absent dcD, information only);
               (c) end-of-run route_blocked units, harness ff_steps vs shard `latched`;
               shard file-level identity D vs dcrbD, K vs dcrbD, Z vs rbc / ihrest
  gate         prereg 3-4: _ffr_rbcompare.py verbatim, the three items recomputed
               from the shards and cross-checked against the printed verdicts, every
               failing element labelled NEW / CARRIED with secondary attribution
  outcomes     per-seed rescued / dead / nd / ff_deaths for ihrest, Z, D, K, dcrbD
  latch        prereg 5: every unit route_blocked and alive at step 240, its timeline
               and the extension classification
  mechanism    return trips / share / fallback docks, reference dfD (NOT dcD)
  exposure     prereg 8: E1, E2, E3 (AN definitions)
  deadlock     prereg 6: D1-D3, L1-L6 (AN definitions) + positive controls
  standoff     prereg 7: return-leg freezes with blockers (FZ), standoffs, how each
               ended; stationary non-returning UAVs
  all          every mode, in that order
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _dcd4_analyze as AN  # noqa: E402
import _dcd4_freezes as FZ  # noqa: E402

PY = sys.executable
SHARD_SEEDS = {"a": (101, 202, 303, 404, 505), "b": (606, 707, 808, 909),
               "c": (111, 222, 333, 444), "s": (101, 202, 303, 404, 505)}
RB18 = [(w, "half", s) for sh, w in AN.RB_SHARDS for s in SHARD_SEEDS[sh]]
SHARED14 = [t for t in RB18 if t in AN.CANON or t in AN.FRESH]
STEPS = 240
EXT_STEPS = 300
RB_LISTS = ("exact_fires", "exact_recoveries", "fires", "recoveries", "assigns", "latched", "deaths")
STANDOFF_FRAMES = 10

ARGS = None


def arm_tags(role):
    rb, ff = getattr(ARGS, role).split(":")
    return rb, ff


def say(*a):
    print(*a)


# ------------------------------------------------------------------- shards ----
_SHARDS: dict = {}


def shard_file(tag, sh, wind):
    return os.path.join(HERE, "_rblatch_camp2_%s%s_D_%s.json" % (tag, sh, wind))


def shards(tag):
    """Per-seed view of one gate arm. Exact file names, never a glob.
    -> {"by": {(wind, seed): {"eval", lists...}}, "exact": {wind: Counter},
        "stats": {wind: Counter}, "missing": [...], "raw": {(sh, wind): dict}}"""
    if tag in _SHARDS:
        return _SHARDS[tag]
    out = {"by": {}, "exact": collections.defaultdict(collections.Counter),
           "stats": collections.defaultdict(collections.Counter), "missing": [], "raw": {}}
    for sh, wind in AN.RB_SHARDS:
        p = shard_file(tag, sh, wind)
        d = AN.load_json(p)
        if d is None:
            out["missing"].append(os.path.basename(p))
            continue
        out["raw"][(sh, wind)] = d
        out["exact"][wind].update(d.get("exact") or {})
        out["stats"][wind].update(d.get("stats") or {})
        for ev in d.get("evals") or []:
            s = int(ev["seed"])
            rec = {"eval": ev}
            for k in RB_LISTS:
                rec[k] = [r for r in (d.get(k) or []) if int(r.get("seed")) == s]
            out["by"][(wind, s)] = rec
    _SHARDS[tag] = out
    return out


def outc(ev):
    return (int(ev.get("rescued") or 0), int(ev.get("dead") or 0),
            int(ev.get("never_detected") or 0), int(ev.get("firefighter_deaths") or 0))


def gate_items(new, old):
    """_ffr_rbcompare.py's three items, recomputed. new/old are shard views."""
    reg, changed = [], []
    for w, _r, s in RB18:
        en, eo = new["by"].get((w, s)), old["by"].get((w, s))
        if en is None or eo is None:
            continue
        rn, ro = int(en["eval"].get("rescued") or 0), int(eo["eval"].get("rescued") or 0)
        if rn < ro:
            reg.append((w, s, ro, rn))
    rec = sum(c.get("recoveries", 0) for c in new["exact"].values())
    fires = sum(c.get("fires", 0) for c in new["exact"].values())
    latched = [(w, s, r["ff"], tuple(r["pos"]) if r.get("pos") else None)
               for (w, s), v in sorted(new["by"].items()) for r in v["latched"]]
    return {"G1": reg, "G2": rec, "G2fires": fires, "G3": latched}


def rbcompare(new, old):
    r = subprocess.run([PY, os.path.join(HERE, "_ffr_rbcompare.py"), "--new", new, "--old", old],
                       cwd=REPO, capture_output=True, text=True)
    return r.stdout + (("\n[stderr] " + r.stderr) if r.stderr.strip() else "")


# ------------------------------------------------------------------ harness ----
def hpath(tag, t, steps=STEPS):
    return AN.ffr_path(tag, *t)


def hload(tag, t):
    d = AN.load_json(AN.ffr_path(tag, *t))
    return d


def first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return "%s: type %s vs %s" % (path, type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return "%s.%s present in one side only" % (path, k)
            x = first_diff(a[k], b[k], "%s.%s" % (path, k))
            if x:
                return x
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return "%s: length %d vs %d" % (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            z = first_diff(x, y, "%s[%d]" % (path, i))
            if z:
                return z
        return None
    return None if a == b else "%s: %r vs %r" % (path, str(a)[:50], str(b)[:50])


# ============================================================== instruments ====
def mode_instruments(_a):
    say("INSTRUMENTS (prereg section 9) - read before any result")
    for role in ("D", "Z", "K"):
        rbt, fft = arm_tags(role)
        sv = shards(rbt)
        n = same = 0
        diffs = []
        for t in RB18:
            d = hload(fft, t)
            sh = sv["by"].get((t[0], t[2]))
            if d is None or sh is None:
                diffs.append("%s missing (%s)" % (AN.tlabel(t), "harness" if d is None else "shard"))
                continue
            he = dict(d["eval"])
            se = {k: v for k, v in sh["eval"].items() if k not in ("seed", "wall_s")}
            n += 1
            if he == se:
                same += 1
            else:
                diffs.append("%s: %s" % (AN.tlabel(t), first_diff(he, se, "eval")))
            del d
        say("  (a) %s  harness %s eval == shard %s eval, every common field: %d/%d%s"
            % (role, fft, rbt, same, n, "" if not diffs else "   DIFFS: " + " | ".join(diffs)))
        if sv["missing"]:
            say("      shard files missing: %s" % sv["missing"])
    say("")
    say("  (b) harness arms vs committed runs, every JSON field except tag and wall_s")
    _, fD = arm_tags("D")
    _, fZ = arm_tags("Z")
    _, fK = arm_tags("K")
    for new, ref, note in ((fD, "dfD", "prereg 9(b)"), (fZ, "dfzero", "prereg 9(b)"),
                           (fK, "dcD", "information only: K (fix OFF at HEAD) vs dcD (fix ABSENT, 9f77178)")):
        r = subprocess.run([PY, os.path.join(HERE, "_dcd4rb_controls.py"), "--pairs", "%s:%s" % (new, ref)],
                           cwd=REPO, capture_output=True, text=True)
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        say("      [%s] %s" % (note, lines[-1] if lines else "(no output) " + r.stderr[-200:]))
        bad = [ln for ln in lines[:-1] if "DIFFERS" in ln or "missing" in ln]
        for ln in bad[:6]:
            say("        " + ln.strip()[:260])
        if len(bad) > 6:
            say("        ... and %d more non-identical tuples" % (len(bad) - 6))
    say("")
    say("  (c) end-of-run route_blocked AND alive: harness ff_steps[239] vs shard `latched`")
    for role in ("D", "Z", "K"):
        rbt, fft = arm_tags(role)
        sv = shards(rbt)
        hh, ss = set(), set()
        for t in RB18:
            d = hload(fft, t)
            if d is not None:
                for row in d["ff_steps"][-1]:
                    if row[2] == "route_blocked" and not row[5]:
                        hh.add((t[0], t[2], row[0]))
                del d
            sh = sv["by"].get((t[0], t[2]))
            for r in (sh or {}).get("latched", []):
                ss.add((t[0], t[2], r["ff"]))
        say("      %s  harness %s  shard %s  %s" % (role, sorted(hh), sorted(ss),
                                                 "EQUAL" if hh == ss else "DIFFER"))
    say("")
    say("  (d) shard files, field by field (evals compared without wall_s)")
    rD, rZ, rK = arm_tags("D")[0], arm_tags("Z")[0], arm_tags("K")[0]
    for new, ref, ignore_params in ((rD, "dcrbD", ()), (rK, "dcrbD", ("BASE_STATION_DOCK_FIX",)),
                                    (rZ, "rbc", ("BASE_STATION_MODE",)),
                                    (rZ, "ihrest", ("BASE_STATION_MODE",))):
        a, b = shards(new), shards(ref)
        for sh, wind in AN.RB_SHARDS:
            da, db = a["raw"].get((sh, wind)), b["raw"].get((sh, wind))
            if da is None or db is None:
                say("      %s%s vs %s%s: missing" % (new, sh, ref, sh))
                continue
            keys = sorted(set(da) | set(db))
            differ = []
            for k in keys:
                va, vb = da.get(k), db.get(k)
                if k == "tag":
                    continue
                if k == "evals":
                    va = [{x: y for x, y in e.items() if x != "wall_s"} for e in va or []]
                    vb = [{x: y for x, y in e.items() if x != "wall_s"} for e in vb or []]
                if k == "params":
                    va = {x: y for x, y in (va or {}).items() if x not in ignore_params}
                    vb = {x: y for x, y in (vb or {}).items() if x not in ignore_params}
                if va != vb:
                    differ.append(k)
            say("      %-7s vs %-8s %s: %s" % (new + sh, ref + sh, wind,
                                              "IDENTICAL except tag/wall_s%s" % (
                                                  " (params compared without %s)" % ",".join(ignore_params)
                                                  if ignore_params else "")
                                              if not differ else "DIFFER on %s" % differ))


# ===================================================================== gate ====
def mode_gate(_a):
    rD, rZ, rK = arm_tags("D")[0], arm_tags("Z")[0], arm_tags("K")[0]
    say("THE GATE (prereg sections 3-4)")
    say("")
    say("---- verdict tool, verbatim: _ffr_rbcompare.py --new %s --old ihrest ----" % rD)
    txt = rbcompare(rD, "ihrest")
    say(txt.rstrip())
    printed = {}
    for ln in txt.splitlines():
        s = ln.strip()
        for key, frag in (("G1", "rescued does not decrease"), ("G2", "recovery pass still"),
                          ("G3", "no unit left latched")):
            if frag in s and s.startswith("["):
                printed[key] = s[1:s.index("]")]
    D, Z, K = shards(rD), shards(rZ), shards(rK)
    I, C = shards("ihrest"), shards("dcrbD")
    gD, gZ, gK, gC = gate_items(D, I), gate_items(Z, I), gate_items(K, I), gate_items(C, I)
    mine = {"G1": "PASS" if not gD["G1"] else "FAIL", "G2": "PASS" if gD["G2"] > 0 else "CHECK",
            "G3": "PASS" if not gD["G3"] else "FAIL"}
    say("")
    say("---- recomputed from the shard files, cross-checked against the printed verdicts ----")
    for k in ("G1", "G2", "G3"):
        say("  %s printed [%s]  recomputed [%s]  %s" % (k, printed.get(k), mine[k],
                                                      "AGREE" if printed.get(k) == mine[k] else "DISAGREE"))
    say("")
    say("---- classification: NEW or CARRIED (Z = same seeds, same commit, no dcD settings) ----")
    labels = {}
    # G1
    elems = []
    for w, s, ro, rn in gD["G1"]:
        z = int(Z["by"][(w, s)]["eval"]["rescued"]) if (w, s) in Z["by"] else None
        k = int(K["by"][(w, s)]["eval"]["rescued"]) if (w, s) in K["by"] else None
        c = int(C["by"][(w, s)]["eval"]["rescued"]) if (w, s) in C["by"] else None
        lab = "CARRIED" if (z is not None and z <= rn) else "NEW"
        elems.append(lab)
        say("  G1 D/%s %-4s rescued ihrest %d -> D %d | Z %s -> %s | secondary: K %s (%s), dcrbD %s (%s)"
            % (w, s, ro, rn, z, lab, k, "reproduces" if k == rn else "differs", c,
               "same as the depot round" if c == rn else "differs from the depot round"))
    labels["G1"] = "PASS" if not gD["G1"] else ("FAIL (CARRIED)" if all(e == "CARRIED" for e in elems)
                                                else "FAIL (NEW)")
    say("  G1 D regressing seeds %s | Z regressing seeds vs ihrest %s | K %s | dcrbD %s"
        % ([(w, s) for w, s, _o, _n in gD["G1"]], [(w, s) for w, s, _o, _n in gZ["G1"]],
           [(w, s) for w, s, _o, _n in gK["G1"]], [(w, s) for w, s, _o, _n in gC["G1"]]))
    same_as_dcrbd = [(w, s, n) for w, s, _o, n in gD["G1"]] == [(w, s, n) for w, s, _o, n in gC["G1"]]
    say("  G1 is the depot round's recorded [FAIL] (same seeds, same values as dcrbD vs ihrest): %s"
        % ("YES" if same_as_dcrbd else "NO"))
    # G2
    if gD["G2"] > 0:
        labels["G2"] = "PASS"
    else:
        labels["G2"] = "FAIL (CARRIED)" if gZ["G2"] == 0 else "FAIL (NEW)"
    say("  G2 recoveries D %d (fires %d) | Z %d (fires %d) | K %d | dcrbD %d | ihrest %d  -> %s"
        % (gD["G2"], gD["G2fires"], gZ["G2"], gZ["G2fires"], gK["G2"], gC["G2"],
           sum(c.get("recoveries", 0) for c in I["exact"].values()), labels["G2"]))
    # G3
    elems = []
    zl = {(w, s, f) for w, s, f, _p in gZ["G3"]}
    kl = {(w, s, f) for w, s, f, _p in gK["G3"]}
    cl = {(w, s, f) for w, s, f, _p in gC["G3"]}
    for w, s, f, p in gD["G3"]:
        lab = "CARRIED" if (w, s, f) in zl else "NEW"
        elems.append(lab)
        say("  G3 D/%s %s %s at %s -> %s | secondary: in K %s, in dcrbD %s"
            % (w, s, f, p, lab, (w, s, f) in kl, (w, s, f) in cl))
    labels["G3"] = "PASS" if not gD["G3"] else ("FAIL (CARRIED)" if all(e == "CARRIED" for e in elems)
                                                else "FAIL (NEW)")
    say("  G3 latched units: D %s | Z %s | K %s | dcrbD %s | ihrest %s"
        % (gD["G3"], gZ["G3"], gK["G3"], gC["G3"], gate_items(I, I)["G3"]))
    say("")
    met = all(labels[k] in ("PASS", "FAIL (CARRIED)") for k in ("G1", "G2", "G3"))
    say("GATE ITEMS  G1 %s   G2 %s   G3 %s" % (labels["G1"], labels["G2"], labels["G3"]))
    say("PRECONDITION (prereg 4): %s" % ("MET" if met else "NOT MET"))
    say("")
    for new, old, why in ((rZ, "ihrest", "Z's own gate: shipped default at HEAD vs 16b2da8"),
                          (rD, rZ, "D vs Z: what dcD's settings do, same commit"),
                          (rD, "dcrbD", "D vs dcrbD: dock fix ON vs the depot round's fix-absent arm"),
                          (rK, "dcrbD", "K vs dcrbD: fix OFF at HEAD vs fix ABSENT at 9f77178"),
                          (rD, rK, "D vs K: the dock fix alone, same commit"),
                          (rK, "ihrest", "K's own gate"),
                          (rZ, "rbc", "Z vs rbc: mode 0 at HEAD vs e703861")):
        say("---- %s: _ffr_rbcompare.py --new %s --old %s ----" % (why, new, old))
        say(rbcompare(new, old).rstrip())
        say("")
    say("---- information only, never a verdict: _ir_rbmerge.py --prefix %s (70e1b33 reference) ----" % rD)
    r = subprocess.run([PY, os.path.join(HERE, "_ir_rbmerge.py"), "--prefix", rD], cwd=REPO,
                       capture_output=True, text=True)
    tail = [ln for ln in r.stdout.splitlines() if ln.startswith(("ALL 18", "  [", "        "))]
    say("\n".join(tail))


# ================================================================= outcomes ====
def mode_outcomes(_a):
    rD, rZ, rK = arm_tags("D")[0], arm_tags("Z")[0], arm_tags("K")[0]
    cols = [("ihrest", "ihrest"), ("Z", rZ), ("D", rD), ("K", rK), ("dcrbD", "dcrbD")]
    views = {lab: shards(tag) for lab, tag in cols}
    say("OUTCOMES per seed (rescued/dead/never_detected/ff_deaths, terminal_step)")
    say("  REFERENCE: ihrest (gate) and Z (same commit); dcrbD readable because dfA-dfD outcomes")
    say("  equal dcA-dcD to the unit")
    say("  %-12s %s" % ("tuple", "  ".join("%-18s" % lab for lab, _t in cols)))
    tot = {lab: [0, 0, 0, 0] for lab, _t in cols}
    for w, _r, s in RB18:
        cells = []
        for lab, _t in cols:
            v = views[lab]["by"].get((w, s))
            if v is None:
                cells.append("%-18s" % "missing")
                continue
            o = outc(v["eval"])
            for i in range(4):
                tot[lab][i] += o[i]
            cells.append("%-18s" % ("%d/%d/%d/%d t%s" % (o + (v["eval"].get("terminal_step"),))))
        say("  %-12s %s" % ("%s/%d" % (w, s), "  ".join(cells)))
    say("  %-12s %s" % ("TOTAL", "  ".join("%-18s" % ("%d/%d/%d/%d" % tuple(tot[lab])) for lab, _t in cols)))
    say("")
    for a, b in (("D", "Z"), ("D", "ihrest"), ("Z", "ihrest"), ("K", "D"), ("D", "dcrbD")):
        better = worse = 0
        diffs = []
        for w, _r, s in RB18:
            va, vb = views[a]["by"].get((w, s)), views[b]["by"].get((w, s))
            if va is None or vb is None:
                continue
            oa, ob = outc(va["eval"]), outc(vb["eval"])
            if oa != ob:
                diffs.append("%s/%d %s->%s" % (w, s, "/".join(map(str, ob)), "/".join(map(str, oa))))
            better += int(oa[0] > ob[0])
            worse += int(oa[0] < ob[0])
        d = [tot[a][i] - tot[b][i] for i in range(4)]
        say("  %-6s - %-6s rescued %+d dead %+d nd %+d ff_deaths %+d | rescued better/worse seeds %d/%d | "
            "tuples differing %d%s" % (a, b, d[0], d[1], d[2], d[3], better, worse, len(diffs),
                                       (": " + "; ".join(diffs)) if diffs and len(diffs) <= 8 else ""))


# ==================================================================== latch ====
def _episodes(statuses):
    """[(start_step, end_step or None)] of route_blocked episodes; steps are harness steps."""
    eps, start = [], None
    for i, st in enumerate(statuses):
        if st == "route_blocked" and start is None:
            start = i + 1
        elif st != "route_blocked" and start is not None:
            eps.append((start, i))
            start = None
    if start is not None:
        eps.append((start, None))
    return eps


def mode_latch(_a):
    say("LATCHED UNITS (prereg section 5): every unit route_blocked and alive at step 240, any arm")
    pop = []
    for role in ("D", "Z", "K"):
        rbt, fft = arm_tags(role)
        sv = shards(rbt)
        for (w, s), v in sorted(sv["by"].items()):
            for r in v["latched"]:
                pop.append((role, rbt, fft, w, s, r["ff"], r.get("pos")))
    if not pop:
        say("  none in any arm - G3 has no element, and there is nothing to classify")
        return
    counts = collections.Counter()
    for role, rbt, fft, w, s, ff, pos in pop:
        v = shards(rbt)["by"][(w, s)]
        ev = v["eval"]
        say("")
        say("  %s %s/half/%d %s at %s  (terminal_step %s)" % (role, w, s, ff, pos, ev.get("terminal_step")))
        fires = [r["step"] for r in v["fires"] if r["ff"] == ff]
        recs = [(r["step"], r["to"]) for r in v["recoveries"] if r["ff"] == ff]
        xf = [r["step"] for r in v["exact_fires"] if r["ff"] == ff]
        xr = [(r["step"], r["to"]) for r in v["exact_recoveries"] if r["ff"] == ff]
        say("    shard per-step: route_blocked transitions at %s; recoveries %s" % (fires, recs))
        say("    shard exact hooks: fires %s; recoveries %s" % (xf, xr))
        flag_step = fires[-1] if fires else None
        say("    FLAGGED (start of the final episode, shard per-step): step %s" % flag_step)
        d = hload(fft, (w, "half", s))
        if d is None:
            say("    harness run %s missing - no timeline" % fft)
            counts["INDETERMINATE (no harness)"] += 1
            continue
        idx = [row[0] for row in d["ff_steps"][0]].index(ff)
        sts = [d["ff_steps"][i][idx][2] for i in range(len(d["ff_steps"]))]
        eps = _episodes(sts)
        last = eps[-1] if eps else None
        say("    harness ff_steps episodes %s; final episode starts step %s, length at 240: %s"
            % (eps, last[0] if last else None, (STEPS - last[0] + 1) if last else None))
        say("    last 20 statuses (steps 221-240): %s" % " ".join(
            {"route_blocked": "RB", "en_route": "er", "available": "av", "rescuing": "rs",
             "returning": "rt", "dead": "XX"}.get(x, x[:2]) for x in sts[-20:]))
        rec20 = [e for e in eps[:-1] if e[1] is not None and last and last[0] - 20 <= e[1] < last[0]]
        row240 = d["ff_steps"][-1][idx]
        say("    shape: recoveries in the 20 steps before the final episode %d; assigned at 240 %r; "
            "harness flag step == shard flag step: %s" % (len(rec20), row240[3],
                                                          last is not None and last[0] == flag_step))
        del d
        # extension
        ext_tag = ARGS.ext + role
        e = AN.load_json(os.path.join(HERE, "_ffr_%s_%s_half_%d.json" % (ext_tag, w, s)))
        if e is None:
            say("    EXTENSION %s: not run -> INDETERMINATE until it is" % ext_tag)
            counts["INDETERMINATE (extension not run)"] += 1
            continue
        d = hload(fft, (w, "half", s))
        valid = (e.get("steps") == EXT_STEPS and e["fire_digests"][:STEPS] == d["fire_digests"]
                 and e["ff_steps"][:STEPS] == d["ff_steps"])
        del d
        if not valid:
            say("    EXTENSION %s: NOT VALID (steps 1-240 do not reproduce) -> INDETERMINATE" % ext_tag)
            counts["INDETERMINATE (extension invalid)"] += 1
            continue
        xs = [e["ff_steps"][i][idx] for i in range(STEPS, EXT_STEPS)]
        left = next(((STEPS + 1 + i, r[2]) for i, r in enumerate(xs) if r[2] != "route_blocked"), None)
        if left is None:
            cls = "GENUINE LATCH"
        elif left[1] == "dead" or xs[left[0] - STEPS - 1][5]:
            cls = "INDETERMINATE (died while blocked)"
        else:
            cls = "HORIZON ARTIFACT"
        counts[cls] += 1
        say("    EXTENSION %s (valid: fire digests and ff_steps 1-240 identical): %s -> %s"
            % (ext_tag, ("left route_blocked at step %d to %s" % left) if left else
               "route_blocked and alive at every step 241-300", cls))
        say("    extension statuses 241-260: %s" % " ".join(r[2][:2] for r in xs[:20]))
    say("")
    say("  CLASSES (never summed): %s" % dict(counts))


# ================================================================ mechanism ====
def mode_mechanism(_a):
    _, fD = arm_tags("D")
    _, fZ = arm_tags("Z")
    _, fK = arm_tags("K")
    say("MECHANISM  reference dfD (dock fix ON) - NOT dcD, because the dock fix changed return-leg")
    say("share and fallback-dock composition wherever its fallback fired")
    plan = [(fD, "rbgate 18", RB18), (fD, "shared 14", SHARED14), ("dfD", "shared 14", SHARED14),
            ("dfD", "can+fresh", AN.CANON + AN.FRESH), (fK, "rbgate 18", RB18), (fZ, "rbgate 18", RB18)]
    say("  %-6s %-10s %6s %6s %7s %7s %9s %8s %9s %8s %8s"
        % ("arm", "sample", "runs", "trips", "arrived", "mean d", "ret steps", "ret %", "chg steps",
           "chg %", "fallback"))
    aggs = {}
    for tag, lab, tt in plan:
        A = AN.agg_mech([s for _t, s in AN.collect(tag, tt)])
        aggs[(tag, lab)] = A
        say("  %-6s %-10s %6s %6d %7d %7s %9d %7.2f%% %9d %7.2f%% %8d"
            % (tag, lab, "%d/%d" % (A["runs"], len(tt)), A["trips"], A["arrived"],
               "%.2f" % A["mean_d"] if A["mean_d"] is not None else "-", A["ret"], A["ret_pct"],
               A["chg"], A["chg_pct"], A["fb"]))
    say("")
    say("  FALLBACK DOCKS (first match: other-UAV berth, own berth not target, firefighter berth,")
    say("  plain depot cell, OUTSIDE)")
    for (tag, lab), A in aggs.items():
        if not A["fb"]:
            continue
        say("  %-6s %-10s by HOME berths %s | by uav_berths_by_depot %s"
            % (tag, lab, dict(A["home"]), dict(A["dep"])))
        if lab != "can+fresh":
            for l2, t in A["fb_list"]:
                say("      %-30s uid %s trigger %s depot %d berth %s -> dock %s [%s | %s]"
                    % (l2, t["uid"], t["trigger"], t["depot"], AN.fmt_cell(t["target"]),
                       AN.fmt_cell(t["dock"]), t["cls_home"], t["cls_depot"]))
    say("")
    for tag, lab in ((fD, "rbgate 18"), ("dfD", "can+fresh"), (fK, "rbgate 18")):
        A = aggs[(tag, lab)]
        say("  per depot %-6s %-10s %s" % (tag, lab, "   ".join(
            "depot %d: %d trips, mean d %.2f" % (k, v[0], v[1] / float(v[0]))
            for k, v in sorted(A["per_depot"].items())) or "(no trips)"))
    AZ = aggs[(fZ, "rbgate 18")]
    say("  %s zero-trip check: %d trips, %d return steps -> %s" % (
        fZ, AZ["trips"], AZ["ret"], "OK" if AZ["trips"] == 0 and AZ["ret"] == 0 else "NOT ZERO"))
    AN.print_excluded()


# ================================================================= exposure ====
def mode_exposure(_a):
    _, fD = arm_tags("D")
    _, fZ = arm_tags("Z")
    _, fK = arm_tags("K")
    say("DRONE STEPS IN FIRE (prereg section 8)")
    say("  E1 searcher-only = victim_searcher (frame,UAV) on a burning cell (burn_intervals rebuild) /")
    say("     victim_searcher (frame,UAV) - the interior-hazard definition (8520706: 2.12% canonical /")
    say("     2.98% fresh)")
    say("  E2 all-UAV = uav_actions[.][2] over every UAV and base_state - the base-station / depot /")
    say("     dock-fix figure. The dock-fix report calls E2 'the same definition' as the 2.1% / 3.0%;")
    say("     that is WRONG on role scope (8520706 canonical is 1.45% under E2, 2.12% under E1)")
    plan = [(fZ, "rbgate 18", RB18), (fD, "rbgate 18", RB18), (fK, "rbgate 18", RB18),
            (fZ, "shared 14", SHARED14), (fD, "shared 14", SHARED14),
            ("dfzero", "shared 14", SHARED14), ("dfD", "shared 14", SHARED14),
            ("dfzero", "canonical", AN.CANON), ("dfzero", "fresh", AN.FRESH),
            ("dfD", "canonical", AN.CANON), ("dfD", "fresh", AN.FRESH),
            ("d4off", "fourth", AN.FOURTH_PREREG), ("d4D", "fourth", AN.FOURTH_PREREG),
            ("ihbase", "canonical", AN.CANON)]
    aggs = {}
    say("  %-7s %-10s %6s %-24s %-24s %s" % ("arm", "sample", "runs", "E1 searcher", "E2 all-UAV",
                                            "E2 flag mismatches"))
    for tag, lab, tt in plan:
        E = AN.agg_exp([s for _t, s in AN.collect(tag, tt)])
        aggs[(tag, lab)] = (E, len(tt))
        e2 = AN.pct(E["e2n"], E["e2d"]) if E["acts_runs"] else "n/a"
        say("  %-7s %-10s %6s %-24s %-24s %s" % (tag, lab, "%d/%d" % (E["runs"], len(tt)),
                                                AN.pct(E["e1n"], E["e1d"]), e2,
                                                ("%d (uid-order %d)" % (E["mism"], E["omism"]))
                                                if E["acts_runs"] else "-"))
    for a, b in ((fD, fZ), (fK, fZ), (fD, fK)):
        Ea, Eb = aggs[(a, "rbgate 18")][0], aggs[(b, "rbgate 18")][0]
        if Ea["e1d"] and Eb["e1d"] and Ea["e2d"] and Eb["e2d"]:
            say("  %s - %s (same 18 seeds): E1 %+.2f points, E2 %+.2f points" % (
                a, b, 100.0 * (Ea["e1n"] / Ea["e1d"] - Eb["e1n"] / Eb["e1d"]),
                100.0 * (Ea["e2n"] / Ea["e2d"] - Eb["e2n"] / Eb["e2d"])))
    say("")
    say("  E3 CONSECUTIVE STEPS ON BURNING CELLS   columns >=2 >=3 >=5 max; state = majority base_state")
    say("  (ties -> returning, then charging/docked, then flying); per run = runs of 2+ / runs")
    listing = []
    for tag, lab in ((fZ, "rbgate 18"), (fD, "rbgate 18"), (fK, "rbgate 18"), ("dfD", "canonical"),
                     ("dfD", "fresh"), ("d4off", "fourth"), ("d4D", "fourth")):
        E, n = aggs[(tag, lab)]
        say("  %-7s %-10s runs %s" % (tag, lab, "%d/%d" % (E["runs"], n)))
        for scope, runs in (("all UAVs", E["all"]), ("searchers", E["srch"]), ("same-cell", E["same"])):
            parts = []
            for st in AN.STATES:
                parts.append("%s %s" % (st, AN._e3_row([r for r in runs if r[1] == st])))
            mixed = sum(1 for r in runs if r[0] >= 2 and r[2])
            per = sum(1 for r in runs if r[0] >= 2) / float(E["runs"]) if E["runs"] else 0.0
            say("      %-9s total %s (%.2f/run) | %s | mixed %d" % (scope, AN._e3_row(runs), per,
                                                                  " | ".join(parts), mixed))
        if tag in (fZ, fD, fK):
            listing += [(tag, lab) + x for x in E["same"] if x[0] >= 5]
    say("")
    say("  EVERY SAME-CELL STAY OF >= 5 FRAMES in this sample's arms")
    if not listing:
        say("    none")
    for tag, lab, n, st, mixed, l2, uid, role, cell, step, inside in listing:
        say("    %-6s %-30s uid %s %-16s cell %-8s start step %3d length %2d state %s%s inside depot: %s"
            % (tag, l2, uid, role, AN.fmt_cell(cell), step, n, st, " (mixed)" if mixed else "", inside))
    AN.print_excluded()


# ================================================================= deadlock ====
def mode_deadlock(_a):
    _, fD = arm_tags("D")
    _, fZ = arm_tags("Z")
    _, fK = arm_tags("K")
    say("DEADLOCKS AND LIVELOCKS (prereg section 6; AN definitions, constants unchanged)")
    say("  D1 STUCK = returning at the last frame AND >= %d trailing frames on one cell (the redefined"
        % AN.STUCK_FRAMES)
    say("     stranding gate); D2 unarrived trip; D3 zero battery outside every depot;")
    say("  L2 FREEZE >= %d; L3 CYCLE; L4 OSCILLATION (%d-frame window, <= 2 cells, >= 2 changes);"
        % (AN.FREEZE_FRAMES, AN.OSC_WIN))
    say("  L5 REVISIT (>= %d in the collapsed leg); L6 DISTANCE-PROGRESS (%d-frame window). RETURN LEGS ONLY."
        % (AN.REVISIT_COUNT, AN.PROG_WIN))
    plan = [(fD, "rbgate 18", RB18), (fK, "rbgate 18", RB18), (fZ, "rbgate 18", RB18),
            ("dfD", "shared 14", SHARED14), ("dfD", "can+fresh", AN.CANON + AN.FRESH),
            ("d4D", "fourth", AN.FOURTH_PREREG), ("dcB", "fresh", AN.FRESH),
            ("dfm2ref", "canonical", AN.CANON)]
    say("  %-7s %-10s %6s %5s %5s %-11s %4s %5s %6s %5s %4s %5s %-12s %5s %5s"
        % ("arm", "sample", "runs", "UAVs", "STUCK", "unarr T/NOT", "zero", "legs", "freeze", "cycle",
           "osc", "revis", "L6 any/in/out", "ndmax", "align"))
    aggs = []
    for tag, lab, tt in plan:
        D = AN.agg_dead([s for _t, s in AN.collect(tag, tt)])
        aggs.append((tag, lab, D))
        tr = sum(1 for _l, u in D["unarr"] if u["cls"] == "HORIZON-TRUNCATED")
        say("  %-7s %-10s %6s %5d %5d %-11s %4d %5d %6d %5d %4d %5d %-12s %5d %5d"
            % (tag, lab, "%d/%d" % (D["runs"], len(tt)), D["uavs"], len(D["stuck"]),
               "%d/%d" % (tr, len(D["unarr"]) - tr), len(D["zero"]), D["legs"], D["freeze"],
               len(D["cycle"]), len(D["osc"]), len(D["revisit"]),
               "%d/%d/%d" % (D["prog_any"], D["prog_in"], len(D["prog_out"])), D["nd_max"],
               D["align_miss"]))
    say("  (dcB fresh and dfm2ref canonical are POSITIVE CONTROLS: STUCK and L6 must fire there)")
    say("")
    for tag, lab, D in aggs:
        if tag in ("dcB", "dfm2ref", "dfD", "d4D"):
            continue
        pre = "  %-7s" % tag
        for l2, uid, pos, k, b in D["stuck"]:
            say("%s STUCK      %-30s uid %s at %s for %d frames, battery %s" % (
                pre, l2, uid, AN.fmt_cell(pos), k, "%.1f" % b if b is not None else "-"))
        for l2, u in D["unarr"]:
            say("%s UNARRIVED  %-30s uid %s trigger %s target %s last %s -> %s (%s)" % (
                pre, l2, u["uid"], u["trigger"], AN.fmt_cell(u["target"]), AN.fmt_cell(u["last"]),
                u["cls"], u["why"]))
        for l2, uid, pos, b in D["zero"]:
            say("%s ZERO-BATT  %-30s uid %s at %s battery %.1f" % (pre, l2, uid, AN.fmt_cell(pos), b))
        for l2, m in D["cycle"]:
            say("%s CYCLE      %-30s uid %s leg step %d (%d frames) returns to %s" % (
                pre, l2, m["uid"], m["start_step"], m["frames"], AN.fmt_cell(m["cycle"])))
        for l2, m in D["osc"]:
            say("%s OSCILLATE  %-30s uid %s leg step %d window from step %d %s" % (
                pre, l2, m["uid"], m["start_step"], m["osc"][0], [AN.fmt_cell(c) for c in m["osc"][1]]))
        for l2, m in D["revisit"]:
            say("%s REVISIT    %-30s uid %s leg step %d cell %s x%d" % (
                pre, l2, m["uid"], m["start_step"], AN.fmt_cell(m["revisit"][0]), m["revisit"][1]))
        for l2, m in D["prog_out"]:
            s0, c0, d0, d1 = m["prog_first_out"]
            say("%s PROGRESS   %-30s uid %s leg step %d (%d frames, %s) target %s: %d outside-depot k "
                "(first at step %d %s, d %d -> %d), %d inside; freeze %d at %s; nd-stretch %d"
                % (pre, l2, m["uid"], m["start_step"], m["frames"],
                   "arrived" if m["arrived"] else "NOT arrived", AN.fmt_cell(m["target"]), m["prog_out"],
                   s0, AN.fmt_cell(c0), d0, d1, m["prog_in"], m["freeze"], AN.fmt_cell(m["freeze_cell"]),
                   m["nd_stretch"]))
    for tag, lab, D in aggs:
        if tag in ("dcB", "dfm2ref"):
            sl = [m for _l, m in D["leg_list"] if m["stuck"]]
            say("  POSITIVE CONTROL %s %s: STUCK %d; L6 fires (outside) on %d of %d STUCK legs"
                % (tag, lab, len(D["stuck"]), sum(1 for m in sl if m["prog_out"] > 0), len(sl)))
    AN.print_excluded()


# ================================================================= standoff ====
def _ending(d, x):
    """How a freeze ended. uav_steps[i] is the state AFTER step i+1, so for the last frozen
    frame index j the frozen UAV sat on its cell after step j+1 and first moved (if ever) at
    step j+2. For every blocker: its post-step state after steps j, j+1 and j+2, and the
    action labels it carried on the refused frames."""
    rows, acts = d["uav_steps"], d.get("uav_actions") or []
    j = x["start_step"] - 1 + x["frames"] - 1          # last frozen frame index
    out = []
    uids = [c[0] for c in rows[0]]
    me = uids.index(x["uid"])

    def st(c):
        return "%s dir %s batt %s state '%s'" % (AN.fmt_cell(c[1]), c[3], c[4], c[5] or "")

    for u, v in sorted(x["blockers"].items()):
        b = uids.index(u)
        frames = sorted(v["frames"])
        labels = collections.Counter(acts[m][b][1] for m in frames if m < len(acts) and b < len(acts[m])
                                     and str(acts[m][b][0]) == str(u))
        seq = []
        for fi in (j - 1, j, j + 1):
            if 0 <= fi < len(rows):
                seq.append("after step %d: %s" % (fi + 1, st(rows[fi][b])))
        out.append("%s %s%s: %s; labels on refused frames %s" % (
            u, v["role"], " HEAD-ON" if v["head_on"] else "", " | ".join(seq), dict(labels)))
    if j + 1 < len(rows):
        out.append("frozen UAV %s after step %d: %s" % (x["uid"], j + 2, st(rows[j + 1][me])))
    else:
        out.append("frozen UAV %s still on %s at the horizon" % (x["uid"], AN.fmt_cell(x["cell"])))
    return out


def mode_standoff(_a):
    _, fD = arm_tags("D")
    _, fZ = arm_tags("Z")
    _, fK = arm_tags("K")
    say("THE STANDOFF (prereg section 7)")
    say("  FREEZE = >= 3 frames on one cell while returning (FZ.run_freezes: blockers from pre- AND")
    say("  post-step occupancy, both axes). STANDOFF = freeze of >= %d frames OUTSIDE a depot with at"
        % STANDOFF_FRAMES)
    say("  least one blocker that is not itself returning.")
    plan = [(fD, "rbgate 18", RB18), (fK, "rbgate 18", RB18), (fZ, "rbgate 18", RB18),
            ("dfD", "can+fresh", AN.CANON + AN.FRESH), ("d4D", "fourth", AN.FOURTH_PREREG)]
    for tag, lab, tt in plan:
        fz, st, present, legs = [], [], 0, 0
        stand = []
        for t in tt:
            d = AN.load_json(AN.ffr_path(tag, *t))
            if d is None:
                continue
            present += 1
            legs += sum(len(v or []) for v in (d.get("rtb_log") or {}).values())
            f = FZ.run_freezes(tag, t, d)
            for x in f:
                nonret = [u for u, v in x["blockers"].items() if v["state"] - {"returning"}]
                x["nonret"] = nonret
                if x["frames"] >= STANDOFF_FRAMES and not x["inside"] and nonret:
                    x["ending"] = _ending(d, x)
                    stand.append(x)
            fz.extend(f)
            st.extend(FZ.run_stationary(tag, t, d))
            del d
        kinds = collections.Counter(x["kind"] for x in fz)
        hist = collections.Counter(x["frames"] for x in fz)
        say("")
        say("  %-6s %-10s runs %d/%d, return legs (trips) %d, freezes %d by blocker %s lengths %s"
            % (tag, lab, present, len(tt), legs, len(fz), dict(kinds), dict(sorted(hist.items()))))
        say("    STANDOFFS: %d of %d legs%s" % (len(stand), legs, (
            "; frames %s" % [x["frames"] for x in stand]) if stand else ""))
        for x in sorted(stand, key=lambda x: -x["frames"]):
            say("    STANDOFF %s uid %s %d frames steps %d-%d at %s d=%d terminal=%s %s"
                % (x["run"], x["uid"], x["frames"], x["start_step"], x["start_step"] + x["frames"] - 1,
                   AN.fmt_cell(x["cell"]), x["dist"], x["terminal"],
                   "arrived" if x["arrived"] else "NOT ARRIVED"))
            for e in x["ending"]:
                say("        " + e)
        if tag in (fD, fK, fZ):
            for x in sorted(fz, key=lambda x: (-x["frames"], x["run"])):
                bl = "; ".join("%s %s %s%s on %d of %d refused frames" % (
                    u, v["role"], "/".join(sorted(v["state"])), " HEAD-ON" if v["head_on"] else "",
                    len(v["frames"]), x["frames"] - 1) for u, v in sorted(x["blockers"].items()))
                say("    freeze %-30s uid %s %2d frames from step %3d at %-8s d=%-2d %s terminal=%s "
                    "blockers: %s%s" % (x["run"], x["uid"], x["frames"], x["start_step"],
                                        AN.fmt_cell(x["cell"]), x["dist"],
                                        "INSIDE depot " if x["inside"] else "outside depot", x["terminal"],
                                        bl or "none found", "" if x["arrived"] else "  NOT ARRIVED"))
        pre = [x for x in st if not x["after_terminal"]]
        post = [x for x in st if x["after_terminal"]]
        say("    STATIONARY non-returning (>= 10 frames one cell): before terminal %d episodes / %d frames %s;"
            " after terminal %d / %d" % (len(pre), sum(x["frames"] for x in pre),
                                         dict(collections.Counter(x["role"] for x in pre)), len(post),
                                         sum(x["frames"] for x in post)))
        if tag in (fD, fK, fZ):
            for x in sorted(pre, key=lambda x: -x["frames"])[:12]:
                say("      %-30s uid %s %-16s %-8s from step %3d for %3d frames"
                    % (x["run"], x["uid"], x["role"], AN.fmt_cell(x["cell"]), x["start_step"], x["frames"]))


MODES = [("instruments", mode_instruments), ("gate", mode_gate), ("outcomes", mode_outcomes),
         ("latch", mode_latch), ("mechanism", mode_mechanism), ("exposure", mode_exposure),
         ("deadlock", mode_deadlock), ("standoff", mode_standoff)]


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=[m for m, _f in MODES] + ["all"])
    ap.add_argument("--D", default="drgD:drhD")
    ap.add_argument("--Z", default="drgZ:drhZ")
    ap.add_argument("--K", default="drgK:drhK")
    ap.add_argument("--ext", default="drl")
    ARGS = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    say("dcd4rb analysis   D=%s Z=%s K=%s ext=%s" % (ARGS.D, ARGS.Z, ARGS.K, ARGS.ext))
    todo = MODES if ARGS.mode == "all" else [m for m in MODES if m[0] == ARGS.mode]
    for i, (_n, fn) in enumerate(todo):
        say("")
        say("=" * 78)
        fn(ARGS)
    say("")
    say("DCD4RB_ANALYSIS_COMPLETE")


if __name__ == "__main__":
    main()
