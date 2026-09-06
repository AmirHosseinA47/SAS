"""Dimension round analysis over outputs/_ffr_<tag>_<wind>_<half|def>_<seed>.json.

usage:
  _dim_analyze.py identity   dimbase dimctrl        # byte-identity, every field, per run
  _dim_analyze.py compare    dimbase dimfix         # seed-matched metrics + first divergence
  _dim_analyze.py fresh      dimfreshbase dimfreshfix
  _dim_analyze.py shim       dimfix                 # eval vs the diagnosis's _gs_shim50 arm
  _dim_analyze.py latbase    dimbase                # eval/digests/stdout vs _ffr_latbase
  _dim_analyze.py helpers    diminst dimbase dimfix # the two helpers + consumers, per run
  _dim_analyze.py ablation   dimbase dimfix dimpinall dimA dimB dimC
  _dim_analyze.py trace      dimbase dimfix diminst east half 505
Missing runs are reported, not fatal, so sections can be run while arms are still
in flight.
"""
from __future__ import annotations

import collections
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
CANON = ([("east", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("south", "half", s) for s in (101, 202, 303, 404, 505)]
         + [("east", "default", s) for s in (101, 202, 303)])
FRESH = ([("east", "half", s) for s in (606, 707, 808, 909, 1010)]
         + [("south", "half", s) for s in (606, 707, 808, 909, 1010)])
SKIP = {"tag", "repo", "wall_s", "dim"}
METRICS = ("rescued", "dead", "unreachable", "never_detected", "firefighter_deaths")


def _name(tag, wind, roles, seed):
    rr = "def" if roles == "default" else roles
    return os.path.join(BASE, "_ffr_%s_%s_%s_%d.json" % (tag, wind, rr, seed))


def load(tag, combos):
    runs = {}
    for k in combos:
        p = _name(tag, *k)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            with open(p, encoding="utf-8") as f:
                runs[k] = json.load(f)
    missing = [k for k in combos if k not in runs]
    if missing:
        print("  [%s] MISSING %d/%d: %s" % (tag, len(missing), len(combos), ", ".join(label(k) for k in missing)))
    return runs


def label(k):
    return "D/%s/%s %d" % (k[0], k[1], k[2])


def fmt_ts(v):
    return "-" if v is None else str(v)


def diff_fields(a, b):
    return [k for k in sorted(set(a) | set(b)) if k not in SKIP and a.get(k) != b.get(k)]


def first_div(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i + 1
    return None if len(a) == len(b) else n + 1


def mrow(e):
    return "%d/%d/%d/%d/%s" % (e["rescued"], e["dead"], e["firefighter_deaths"], e.get("never_detected", 0), fmt_ts(e["terminal_step"]))


# ---------------------------------------------------------------------------
def identity(tag_a, tag_b, combos):
    A, B = load(tag_a, combos), load(tag_b, combos)
    print("=== BYTE-IDENTITY %s vs %s (every recorded field except tag/repo/wall_s/dim) ===" % (tag_b, tag_a))
    n_id = n = 0
    for k in combos:
        a, b = A.get(k), B.get(k)
        if a is None or b is None:
            continue
        n += 1
        d = diff_fields(a, b)
        if not d:
            n_id += 1
            print("  %-22s identical (%d fields)" % (label(k), len(set(a) | set(b)) - len(SKIP)))
        else:
            extra = ""
            if "uav_steps" in d:
                extra += " first uav div @%s" % first_div(a["uav_steps"], b["uav_steps"])
            if "fire_digests" in d:
                extra += " FIRE DIGEST DIV @%s" % first_div(a["fire_digests"], b["fire_digests"])
            print("  %-22s DIFFERS: %s%s" % (label(k), d, extra))
    print("  byte-identical: %d/%d" % (n_id, n))
    return n_id, n


def compare(tag_a, tag_b, combos, title=None):
    A, B = load(tag_a, combos), load(tag_b, combos)
    print("=== %s: %s -> %s, seed-matched ===" % (title or "COMPARE", tag_a, tag_b))
    print("  %-22s %-22s %-22s %-8s %-9s %-9s %s" % ("combo", tag_a + " r/d/ff/nd/term", tag_b + " r/d/ff/nd/term", "fire", "uav-div", "ff-div", "eval"))
    tot = {m: [0, 0] for m in METRICS}
    n = n_eval_id = n_byte_id = 0
    for k in combos:
        a, b = A.get(k), B.get(k)
        if a is None or b is None:
            continue
        n += 1
        ea, eb = a["eval"], b["eval"]
        for m in METRICS:
            tot[m][0] += int(ea.get(m, 0) or 0)
            tot[m][1] += int(eb.get(m, 0) or 0)
        fire = "ident" if a["fire_digests"] == b["fire_digests"] else "DIV@%s" % first_div(a["fire_digests"], b["fire_digests"])
        ud = first_div(a.get("uav_steps", []), b.get("uav_steps", []))
        fd = first_div(a["ff_steps"], b["ff_steps"])
        same_eval = ea == eb
        n_eval_id += int(same_eval)
        byte = not diff_fields(a, b)
        n_byte_id += int(byte)
        flags = []
        for m in ("rescued", "dead", "firefighter_deaths", "never_detected"):
            x, y = int(ea.get(m, 0) or 0), int(eb.get(m, 0) or 0)
            if x != y:
                flags.append("%s %+d" % ({"rescued": "resc", "dead": "dead", "firefighter_deaths": "ff", "never_detected": "nd"}[m], y - x))
        print("  %-22s %-22s %-22s %-8s %-9s %-9s %s" % (
            label(k), mrow(ea), mrow(eb), fire, fmt_ts(ud), fmt_ts(fd),
            ("same" if same_eval else "; ".join(flags) or "terminal only") + ("  [byte-identical]" if byte else "")))
    print("  %-22s %-22s %-22s" % ("TOTAL", "/".join(str(tot[m][0]) for m in METRICS), "/".join(str(tot[m][1]) for m in METRICS)))
    print("  (totals are rescued/dead/unreachable/never_detected/ff_deaths)")
    for m in METRICS:
        print("    %-20s %3d -> %3d  (%+d)" % (m, tot[m][0], tot[m][1], tot[m][1] - tot[m][0]))
    print("  eval identical: %d/%d   byte-identical: %d/%d" % (n_eval_id, n, n_byte_id, n))
    return tot


def shim(tag_fix):
    import glob
    F = load(tag_fix, CANON)
    S = {}
    for f in glob.glob(os.path.join(BASE, "_gs_shim50_*.json")):
        d = json.load(open(f, encoding="utf-8"))
        S[(d["wind"], d["roles"], int(d["seed"]))] = d
    print("=== CROSS-CHECK: %s eval vs the diagnosis's _gs_shim50 arm (class-attribute shim) ===" % tag_fix)
    n = ok = 0
    for k in CANON:
        a, b = F.get(k), S.get(k)
        if a is None or b is None:
            continue
        n += 1
        same = a["eval"] == b["eval"]
        ok += int(same)
        print("  %-22s %s   fix=%s shim=%s%s" % (label(k), "same" if same else "DIFF", mrow(a["eval"]), mrow(b["eval"]),
              "   stdout sha same" if a.get("stdout_sha256") == b.get("stdout_sha256") else "   stdout sha DIFF"))
    print("  eval identical: %d/%d" % (ok, n))


def latbase(tag_base):
    import glob
    A = load(tag_base, CANON)
    L = {}
    for f in glob.glob(os.path.join(BASE, "_ffr_latbase_*.json")):
        d = json.load(open(f, encoding="utf-8"))
        L[(d["wind"], d["roles"], int(d["seed"]))] = d
    print("=== REPRODUCIBILITY: %s vs _ffr_latbase (fields recorded by both) ===" % tag_base)
    n = ok = 0
    for k in CANON:
        a, b = A.get(k), L.get(k)
        if a is None or b is None:
            continue
        n += 1
        common = [f for f in sorted(set(a) & set(b)) if f not in SKIP]
        d = [f for f in common if a[f] != b[f]]
        ok += int(not d)
        print("  %-22s %s" % (label(k), "identical on %d common fields" % len(common) if not d else "DIFFERS: %s" % d))
    print("  identical: %d/%d" % (ok, n))


def fresh(tag_a, tag_b):
    tot = compare(tag_a, tag_b, FRESH, "FRESH SEEDS")
    return tot


# ---------------------------------------------------------------------------
def helpers(tag_inst, tag_base, tag_fix):
    I, A, F = load(tag_inst, CANON), load(tag_base, CANON), load(tag_fix, CANON)
    print("=== THE TWO HELPERS AND THEIR CONSUMERS (%s; identity vs %s checked separately) ===" % (tag_inst, tag_fix))
    reads = collections.Counter()
    hcalls = collections.Counter()
    hlive = collections.Counter()
    csum = collections.Counter()
    c3 = 0
    clamp_n = clamp_edge = 0
    writes = 0
    steps_live = collections.Counter()
    print("  per run: first changed consumer decision vs first UAV divergence (%s vs %s)" % (tag_fix, tag_base))
    print("  %-22s %-44s %-9s %-9s %s" % ("combo", "first changed decision [step uav role consumer real->cf]", "uav-div", "ff-div", "agreement"))
    for k in CANON:
        r = I.get(k)
        if r is None or not r.get("dim"):
            continue
        d = r["dim"]
        writes += d["writes"]
        for name, fname, reader, n in d["reads"]:
            reads[(name, fname, reader)] += n
        for h, caller, n in d["helper_calls"]:
            hcalls[(h, caller)] += n
        for h, caller, n in d["helper_live"]:
            hlive[(h, caller)] += n
        for key, n in d["consumer_summary"].items():
            csum[key] += n
        c3 += d["c3_execute_near"]
        for st, uid, tx, ty in d["clamp_targets"]:
            clamp_n += 1
            if tx <= 0 or ty <= 0 or tx >= 49 or ty >= 49:
                clamp_edge += 1
        for h, st, n in d["helper_live_by_step"]:
            steps_live[h] += 1
        fc = d["first_changed"]
        a, f = A.get(k), F.get(k)
        ud = first_div(a["uav_steps"], f["uav_steps"]) if (a and f) else None
        fd = first_div(a["ff_steps"], f["ff_steps"]) if (a and f) else None
        fc_s = "%d %s %s %s %s->%s" % (fc[0], fc[1], fc[2][:8], fc[3].replace("_", "")[:22], fc[4], fc[5]) if fc else "none"
        agree = "-"
        if fc and ud:
            # the executor's decision at step s moves the UAV at step s (positions recorded after the step)
            agree = "consistent" if fc[0] <= ud else "DIVERGES BEFORE FIRST CHANGED DECISION"
        elif not fc and ud:
            agree = "DIVERGES WITH NO CHANGED DECISION"
        elif fc and not ud:
            agree = "changed decision but no divergence (?)"
        print("  %-22s %-44s %-9s %-9s %s" % (label(k), fc_s, fmt_ts(ud), fmt_ts(fd), agree))
    print()
    print("  attribute writes (reset assignments) across runs: %d" % writes)
    print("  reads of HEIGHT/WIDTH by reader (sum over runs):")
    for (name, fname, reader), n in sorted(reads.items(), key=lambda kv: (-kv[1], kv[0])):
        print("    %-6s %-34s %-52s %9d" % (name, fname, reader, n))
    print()
    print("  helper calls by caller (sum over runs): calls / live (non-dead result) / share")
    for (h, caller), n in sorted(hcalls.items()):
        live = hlive.get((h, caller), 0)
        print("    %s  %-40s %8d  %8d  %5.1f%%" % (h, caller, n, live, 100.0 * live / n if n else 0.0))
    print("  steps with at least one live result, summed over runs: %s" % dict(steps_live))
    print()
    print("  consumer decisions: calls / changed by the live value (real != counterfactual)")
    names = sorted(set(k.split("|")[0] for k in csum))
    for nm in names:
        calls = csum.get(nm + "|calls", 0)
        ch = csum.get(nm + "|changed", 0)
        print("    %-40s %8d  %8d  %5.2f%%" % (nm, calls, ch, 100.0 * ch / calls if calls else 0.0))
    print("  C3 (execute: P True or D<2 at the near_boundary read): %d" % c3)
    print("  C9 (_execute_search_mode -> _safe_search_target targets): %d, of which on an edge coordinate: %d" % (clamp_n, clamp_edge))


def ablation(tag_base, tag_fix, arms):
    A, F = load(tag_base, CANON), load(tag_fix, CANON)
    print("=== ABLATION: one wake site live at a time (eval per run; == base? == fix?) ===")
    print("  %-22s %-14s %-14s " % ("combo", "base", "fix") + "".join("%-30s" % a for a in arms))
    tots = {a: {m: 0 for m in METRICS} for a in arms}
    same_base = collections.Counter()
    same_fix = collections.Counter()
    byte_base = collections.Counter()
    byte_fix = collections.Counter()
    R = {a: load(a, CANON) for a in arms}
    for k in CANON:
        a, f = A.get(k), F.get(k)
        cells = []
        for arm in arms:
            r = R[arm].get(k)
            if r is None:
                cells.append("%-30s" % "missing")
                continue
            for m in METRICS:
                tots[arm][m] += int(r["eval"].get(m, 0) or 0)
            sb = a is not None and r["eval"] == a["eval"]
            sf = f is not None and r["eval"] == f["eval"]
            bb = a is not None and not diff_fields(a, r)
            bf = f is not None and not diff_fields(f, r)
            same_base[arm] += int(sb); same_fix[arm] += int(sf)
            byte_base[arm] += int(bb); byte_fix[arm] += int(bf)
            tag = ("=base" if bb else ("~base" if sb else "")) + (" =fix" if bf else (" ~fix" if sf else ""))
            cells.append("%-30s" % ("%s %s" % (mrow(r["eval"]), tag.strip() or "neither")))
        print("  %-22s %-14s %-14s " % (label(k), mrow(a["eval"]) if a else "-", mrow(f["eval"]) if f else "-") + "".join(cells))
    print("  %-22s %-14s %-14s " % ("TOTAL r/d/ff/nd", "%d/%d/%d/%d" % tuple(sum(int(x["eval"].get(m, 0) or 0) for x in A.values()) for m in ("rescued", "dead", "firefighter_deaths", "never_detected")),
                                    "%d/%d/%d/%d" % tuple(sum(int(x["eval"].get(m, 0) or 0) for x in F.values()) for m in ("rescued", "dead", "firefighter_deaths", "never_detected")))
          + "".join("%-30s" % ("%d/%d/%d/%d" % (tots[a]["rescued"], tots[a]["dead"], tots[a]["firefighter_deaths"], tots[a]["never_detected"])) for a in arms))
    print("  (=base / =fix: byte-identical on every field; ~: eval identical only)")
    for arm in arms:
        print("  %-12s byte-identical to base %2d/13, to fix %2d/13;  eval identical to base %2d/13, to fix %2d/13" % (
            arm, byte_base[arm], byte_fix[arm], same_base[arm], same_fix[arm]))


# ---------------------------------------------------------------------------
def _ff_deaths(run):
    out = {}
    for i, row in enumerate(run["ff_steps"]):
        for ff, pos, status, assigned, exiting, dead in row:
            if dead and ff not in out:
                out[ff] = (i + 1, pos)
    return out


def _victim_timeline(run):
    tl = collections.defaultdict(list)
    last = {}
    for i, row in enumerate(run["victim_steps"]):
        for vid, pos, status in row:
            if last.get(vid) != status:
                tl[vid].append((i + 1, status, pos))
                last[vid] = status
    return tl


def trace(tag_base, tag_fix, tag_inst, wind, roles, seed):
    k = (wind, roles, int(seed))
    A, F, I = load(tag_base, [k]), load(tag_fix, [k]), load(tag_inst, [k])
    a, f, i = A.get(k), F.get(k), I.get(k)
    if a is None or f is None:
        print("missing runs"); return
    print("=== TRACE %s: %s -> %s ===" % (label(k), tag_base, tag_fix))
    print("  eval base %s   fix %s" % (mrow(a["eval"]), mrow(f["eval"])))
    ud = first_div(a["uav_steps"], f["uav_steps"]); fd = first_div(a["ff_steps"], f["ff_steps"]); vd = first_div(a["victim_steps"], f["victim_steps"])
    print("  first divergence: uav @%s  ff @%s  victims @%s  fire %s" % (fmt_ts(ud), fmt_ts(fd), fmt_ts(vd), "identical" if a["fire_digests"] == f["fire_digests"] else "DIV"))
    if ud:
        print("  uav rows at step %d:\n    base %s\n    fix  %s" % (ud, a["uav_steps"][ud - 1], f["uav_steps"][ud - 1]))
    if i and i.get("dim"):
        ch = i["dim"]["consumers_changed"]
        print("  changed consumer decisions in %s: %d; first 8:" % (tag_inst, len(ch)))
        for row in ch[:8]:
            print("    step %3d uav %s %-16s at %s  %-36s real=%s cf=%s" % (row[0], row[1], row[2], (row[3], row[4]), row[5], row[6], row[7]))
        per = collections.Counter(r[5] for r in ch)
        print("  changed by consumer: %s" % dict(per))
        first_live = i["dim"].get("helper_live_first", {})
        print("  first live helper result per (helper|caller): %s" % first_live)
    for name, run in (("base", a), ("fix", f)):
        print("  --- %s" % name)
        print("    completions: %s" % [(c["step"], c["ff"], c["victim"], tuple(c["pos"]) if c["pos"] else None) for c in run["completions"]])
        print("    unreachable marks: %s" % [(m["step"], m["vid"], m["reason"]) for m in run["unreachable_marks"] if m["ok"]])
        print("    ff deaths (first dead step, pos): %s" % _ff_deaths(run))
        print("    assigns: %s" % [(x["step"], x["ff"], x["vid"], x["reason"]) for x in run["assigns"] if x["ok"]])
        tl = _victim_timeline(run)
        for vid in sorted(tl):
            print("    victim %-10s %s" % (vid, tl[vid]))


def main(argv):
    if not argv:
        print(__doc__); return 2
    sec = argv[0]
    if sec == "identity":
        identity(argv[1], argv[2], FRESH if "fresh" in argv[1] else CANON)
    elif sec == "compare":
        compare(argv[1], argv[2], CANON, "CANONICAL 13")
    elif sec == "fresh":
        fresh(argv[1], argv[2])
    elif sec == "shim":
        shim(argv[1])
    elif sec == "latbase":
        latbase(argv[1])
    elif sec == "helpers":
        helpers(argv[1], argv[2], argv[3])
    elif sec == "ablation":
        ablation(argv[1], argv[2], argv[3:])
    elif sec == "trace":
        trace(argv[1], argv[2], argv[3], argv[4], argv[5], argv[6])
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
