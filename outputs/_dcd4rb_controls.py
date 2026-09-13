"""dcd4rb round: the pre-wave controls (outputs/dcd4rb_prereg.txt section 1).

  harness  drx* vs the committed dock-fix-round run of the same tuple: every JSON
           field equal except tag and wall_s (stdout sha256 included)
  gate     drxrb* one-seed process vs the committed shard whose FIRST seed it is:
           params equal; evals[0] equal except wall_s; every per-seed record list
           (seed == that seed) equal
Also usable after the wave for the prereg 9(b) checks:
  --pairs drhD:dfD,drhZ:dfzero  compares every tuple both tags have on disk.
Read-only. Exit 0 iff every comparison is IDENTICAL.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IGNORE_FF = {"tag", "wall_s"}
RB_LISTS = ("exact_fires", "exact_recoveries", "fires", "recoveries", "assigns", "latched", "deaths")

HARNESS_CONTROLS = [
    ("drxD", "dfD", "south", "half", 707), ("drxD", "dfD", "east", "half", 1010),
    ("drxZ", "dfzero", "east", "def", 101), ("drxZ", "dfzero", "south", "half", 909),
    ("drxK", "dfkill", "south", "half", 606), ("drxK", "dfkill", "east", "def", 303),
]
RB_CONTROLS = [
    ("drxrbB", "south", ["dfrbs"]),
    ("drxrbZ", "east", ["rbca", "dcinerta"]),
]


def load(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return "%s: type %s vs %s" % (path, type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return "%s.%s: present only in %s" % (path, k, "new" if k in a else "ref")
            d = first_diff(a[k], b[k], "%s.%s" % (path, k))
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return "%s: length %d vs %d" % (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, "%s[%d]" % (path, i))
            if d:
                return d
        return None
    return None if a == b else "%s: %r vs %r" % (path, str(a)[:60], str(b)[:60])


def ff_compare(new_tag, ref_tag, w, rr, s):
    pn = os.path.join(HERE, "_ffr_%s_%s_%s_%s.json" % (new_tag, w, rr, s))
    pr = os.path.join(HERE, "_ffr_%s_%s_%s_%s.json" % (ref_tag, w, rr, s))
    if not os.path.exists(pn) or not os.path.exists(pr):
        return None, "missing %s" % (os.path.basename(pn) if not os.path.exists(pn) else os.path.basename(pr))
    a, b = load(pn), load(pr)
    keys = sorted((set(a) | set(b)) - IGNORE_FF)
    differing = [k for k in keys if a.get(k, "<absent>") != b.get(k, "<absent>")]
    if not differing:
        return True, "IDENTICAL (%d fields compared, tag/wall_s ignored; stdout_sha256 %s)" % (
            len(keys), a.get("stdout_sha256", "")[:12])
    return False, "DIFFERS on %s; first: %s" % (differing, first_diff(a[differing[0]], b.get(differing[0]), differing[0]))


def rb_compare(new_tag, wind, ref_tag):
    pn = os.path.join(HERE, "_rblatch_camp2_%s_D_%s.json" % (new_tag, wind))
    pr = os.path.join(HERE, "_rblatch_camp2_%s_D_%s.json" % (ref_tag, wind))
    if not os.path.exists(pn):
        return None, "missing %s" % os.path.basename(pn)
    a, b = load(pn), load(pr)
    seeds = [int(x) for x in a["seeds"].split(",")]
    if len(seeds) != 1 or int(b["seeds"].split(",")[0]) != seeds[0]:
        return False, "not a first-seed control: %s vs %s" % (a["seeds"], b["seeds"])
    s = seeds[0]
    problems = []
    if a["params"] != b["params"]:
        problems.append("params: %s" % first_diff(a["params"], b["params"], "params"))
    ea = {k: v for k, v in a["evals"][0].items() if k != "wall_s"}
    eb = {k: v for k, v in b["evals"][0].items() if k != "wall_s"}
    if ea != eb:
        problems.append("evals[0]: %s" % first_diff(ea, eb, "eval"))
    counts = []
    for k in RB_LISTS:
        la = [r for r in (a.get(k) or []) if int(r.get("seed")) == s]
        lb = [r for r in (b.get(k) or []) if int(r.get("seed")) == s]
        counts.append("%s %d" % (k, len(la)))
        if la != lb:
            problems.append("%s: %d vs %d records; %s" % (k, len(la), len(lb), first_diff(la, lb, k)))
    if problems:
        return False, "DIFFERS: " + " | ".join(problems)
    return True, "IDENTICAL on seed %d (params, eval minus wall_s, %s)" % (s, ", ".join(counts))


def pairs_mode(spec):
    ok_all = True
    for pair in spec.split(","):
        new_tag, ref_tag = pair.split(":")
        n_id = n = 0
        for p in sorted(glob.glob(os.path.join(HERE, "_ffr_%s_*.json" % new_tag))):
            m = re.match(r"_ffr_%s_(\w+?)_(half|def)_(\d+)\.json$" % re.escape(new_tag), os.path.basename(p))
            if not m:
                continue
            w, rr, s = m.group(1), m.group(2), m.group(3)
            if not os.path.exists(os.path.join(HERE, "_ffr_%s_%s_%s_%s.json" % (ref_tag, w, rr, s))):
                continue
            ok, msg = ff_compare(new_tag, ref_tag, w, rr, s)
            n += 1
            n_id += bool(ok)
            ok_all &= bool(ok)
            print("  %-6s vs %-7s %s/%s/%s  %s" % (new_tag, ref_tag, w, rr, s, msg))
        print("%s vs %s: %d/%d IDENTICAL" % (new_tag, ref_tag, n_id, n))
    return ok_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="")
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    if a.pairs:
        return 0 if pairs_mode(a.pairs) else 1
    n_ok = n = 0
    print("PRE-WAVE CONTROLS (outputs/dcd4rb_prereg.txt section 1)")
    for new_tag, ref_tag, w, rr, s in HARNESS_CONTROLS:
        ok, msg = ff_compare(new_tag, ref_tag, w, rr, s)
        n += 1
        n_ok += bool(ok)
        print("  %-6s %s/%s/%-5s vs %-7s %s" % (new_tag, w, rr, s, ref_tag, msg))
    for new_tag, wind, refs in RB_CONTROLS:
        for ref in refs:
            ok, msg = rb_compare(new_tag, wind, ref)
            n += 1
            n_ok += bool(ok)
            print("  %-6s %s/101 vs %-9s %s" % (new_tag, wind, ref, msg))
    print("CONTROLS %d/%d IDENTICAL" % (n_ok, n))
    return 0 if n_ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
