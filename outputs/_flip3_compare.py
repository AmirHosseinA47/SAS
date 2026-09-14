"""Flip round, Part 3: identity rules for runs at the NEW defaults vs explicit dcD arms.

Pre-registered in outputs/flip3_prereg.txt. Read-only; imports only the standard
library. Every comparison is over an EXPLICIT tuple list with a declared count, so a
missing file is a FAIL, never a vacuous pass.

RULE H (harness JSON, 56 keys), new N vs reference R
  H1  identical key set
  H2  every key except {tag, wall_s, params, extra_params} equal (52 fields: repo,
      eval, stdout_sha256, stdout_lines, uav_steps, uav_actions, ff_steps,
      fire_digests, rtb_log, rtb_counters, base_station, ...)
  H3  N.extra_params == {} and R.extra_params == DCD6
  H4  N.params == R.params minus DCD6
  The --set list is recorded ONLY in params and extra_params, so those are the only
  fields that may legitimately differ between a no-set run and an explicit-set run.
RULE H2ONLY  H1 + H2 (the junk-fallback control, whose params carry junk strings)
RULE STRICT-H  every key except tag and wall_s equal (explicit-set controls)
RULE S (gate shard, 16 keys)
  S1  identical key set (tag ignored)
  S2  evals equal with wall_s dropped from each
  S3  every other key except tag, evals, params equal
  S4  N.params == R.params minus DCD6
RULE STRICT-S  S1-S3 plus params equal

  python outputs/_flip3_compare.py --mode dryrun     (before any Part 3 run)
  python outputs/_flip3_compare.py --mode controls [--q1-alt]
  python outputs/_flip3_compare.py --mode wave
Exit 0 iff every check passes with its declared count.
"""
import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DCD6 = {"BASE_STATION_MODE": 3, "BASE_STATION_RETURN_MECHANISM": 2,
        "UAV_RETURN_TO_BASE_RESERVE": 0, "BASE_STATION_RETURN_MARGIN": 39.23,
        "BASE_STATION_DEPOTS": 9, "BASE_STATION_SPAWN_SPLIT": 2}
H_EXEMPT = {"tag", "wall_s", "params", "extra_params"}
RB18 = [("east", "half", s) for s in (101, 202, 303, 404, 505, 606, 707, 808, 909,
                                      111, 222, 333, 444)] + \
       [("south", "half", s) for s in (101, 202, 303, 404, 505)]
DFD_TUPLES = set([("east", "half", s) for s in (101, 202, 303, 404, 505, 606, 707, 808, 909, 1010)]
                 + [("south", "half", s) for s in (101, 202, 303, 404, 505, 606, 707, 808, 909, 1010)]
                 + [("east", "def", s) for s in (101, 202, 303)])
SHARDS = [("a", "east"), ("b", "east"), ("c", "east"), ("s", "south")]


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def ffr(tag, wind, rr, seed):
    return os.path.join(HERE, "_ffr_%s_%s_%s_%s.json" % (tag, wind, rr, seed))


def shard(tag, wind):
    return os.path.join(HERE, "_rblatch_camp2_%s_D_%s.json" % (tag, wind))


def first_diff(a, b, path="$"):
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return "%s: type %s vs %s" % (path, type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
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
    return None if a == b else "%s: %r vs %r" % (path, str(a)[:50], str(b)[:50])


def strip6(params):
    return {k: v for k, v in params.items() if k not in DCD6}


def rule_h(n, r, mode):
    """mode: H | H2ONLY | STRICT. Returns (ok, failed_items, detail)."""
    fails, detail = [], []
    if set(n) != set(r):
        fails.append("H1")
        detail.append("keys +%s -%s" % (sorted(set(n) - set(r)), sorted(set(r) - set(n))))
    exempt = {"tag", "wall_s"} if mode == "STRICT" else H_EXEMPT
    diff = [k for k in sorted(set(n) | set(r)) if k not in exempt and n.get(k, "<absent>") != r.get(k, "<absent>")]
    if diff:
        fails.append("H2" if mode != "STRICT" else "STRICT")
        detail.append("%d fields differ %s; first %s" % (len(diff), diff[:6], first_diff(n.get(diff[0]), r.get(diff[0]), diff[0])))
    if mode == "H":
        if n.get("extra_params") != {} or r.get("extra_params") != DCD6:
            fails.append("H3")
            detail.append("extra new=%r ref=%r" % (n.get("extra_params"), r.get("extra_params")))
        if n.get("params") != strip6(r.get("params", {})):
            fails.append("H4")
            detail.append("params: %s" % first_diff(n.get("params"), strip6(r.get("params", {})), "params"))
    return not fails, fails, "; ".join(detail)


def rule_s(n, r, strict):
    fails, detail = [], []
    if set(n) != set(r):
        fails.append("S1")
        detail.append("keys +%s -%s" % (sorted(set(n) - set(r)), sorted(set(r) - set(n))))
    en = [{k: v for k, v in e.items() if k != "wall_s"} for e in n.get("evals", [])]
    er = [{k: v for k, v in e.items() if k != "wall_s"} for e in r.get("evals", [])]
    if en != er:
        fails.append("S2")
        detail.append("evals: %s" % first_diff(en, er, "evals"))
    other = [k for k in sorted(set(n) | set(r)) if k not in ("tag", "evals", "params")
             and n.get(k, "<absent>") != r.get(k, "<absent>")]
    if other:
        fails.append("S3")
        detail.append("differ %s" % other)
    want = r.get("params", {}) if strict else strip6(r.get("params", {}))
    if n.get("params") != want:
        fails.append("S4" if not strict else "PARAMS")
        detail.append("params: %s" % first_diff(n.get("params"), want, "params"))
    return not fails, fails, "; ".join(detail)


class Tally:
    def __init__(self):
        self.groups = []

    def group(self, label, results, declared):
        n = len(results)
        n_ok = sum(1 for ok, _ in results if ok)
        passed = n == declared and n_ok == declared
        self.groups.append((label, n_ok, n, declared, passed))
        print("%s  %s: %d/%d pass (declared %d)" % ("PASS" if passed else "FAIL", label, n_ok, n, declared))
        return passed

    def done(self):
        ok = all(g[4] for g in self.groups)
        print("\n%s: %d/%d groups pass" % ("ALL PASS" if ok else "FAILURES", sum(g[4] for g in self.groups), len(self.groups)))
        return 0 if ok else 1


def ff_pair(new_tag, ref_tag, tuples, mode, expect_ok=True, expect_fail=None):
    res = []
    for w, rr, s in tuples:
        pn, pr = ffr(new_tag, w, rr, s), ffr(ref_tag, w, rr, s)
        if not os.path.exists(pn) or not os.path.exists(pr):
            print("    MISSING %s" % os.path.basename(pn if not os.path.exists(pn) else pr))
            res.append((False, "missing"))
            continue
        ok, fails, detail = rule_h(load(pn), load(pr), mode)
        good = ok if expect_ok else (sorted(fails) == sorted(expect_fail))
        print("    %-5s %s vs %s %s/%s/%s  %s%s" % ("ok" if good else "BAD", new_tag, ref_tag, w, rr, s,
              "pass" if ok else "fails %s" % fails, ("  [" + detail + "]") if detail else ""))
        res.append((good, detail))
    return res


def rb_pair(new_prefix, ref_prefix, strict, expect_ok=True, expect_fail=None):
    res = []
    for x, wind in SHARDS:
        pn, pr = shard(new_prefix + x, wind), shard(ref_prefix + x, wind)
        if not os.path.exists(pn) or not os.path.exists(pr):
            print("    MISSING %s" % os.path.basename(pn if not os.path.exists(pn) else pr))
            res.append((False, "missing"))
            continue
        ok, fails, detail = rule_s(load(pn), load(pr), strict)
        good = ok if expect_ok else (set(expect_fail) <= set(fails) and "S4" not in fails and "S1" not in fails)
        print("    %-5s %s%s vs %s%s %s  %s%s" % ("ok" if good else "BAD", new_prefix, x, ref_prefix, x, wind,
              "pass" if ok else "fails %s" % fails, ("  [" + detail[:200] + "]") if detail else ""))
        res.append((good, detail))
    return res


def dryrun():
    t = Tally()
    print("DRY RUN on committed data (no Part 3 file is read)")
    # positive, synthetic: drhD east/half/101 made to look like a no-set run
    r = load(ffr("drhD", "east", "half", 101))
    n = copy.deepcopy(r)
    n["tag"], n["wall_s"], n["extra_params"], n["params"] = "synth", -1.0, {}, strip6(r["params"])
    ok, fails, det = rule_h(n, r, "H")
    print("    synthetic no-set copy of drhD east/half/101 vs drhD: %s" % ("pass" if ok else "fails %s %s" % (fails, det)))
    t.group("H positive (synthetic)", [(ok, det)], 1)
    # negative: synthetic copy with one behaviour field perturbed must fail H2 only
    n2 = copy.deepcopy(n)
    n2["stdout_sha256"] = "0" * 64
    ok2, fails2, det2 = rule_h(n2, r, "H")
    print("    same copy with stdout_sha256 perturbed: fails %s" % fails2)
    t.group("H negative (synthetic perturbation fails H2 only)", [(fails2 == ["H2"], det2)], 1)
    # negative: mainff (mode 0, no --set) vs drhD must fail H2 only, 31 fields at east/half/101
    m = load(ffr("mainff", "east", "half", 101))
    ok3, fails3, det3 = rule_h(m, r, "H")
    n31 = det3.startswith("31 fields")
    print("    mainff vs drhD east/half/101: fails %s  [%s]" % (fails3, det3[:90]))
    t.group("H negative (mainff fails H2 only, 31 fields)", [(fails3 == ["H2"] and n31, det3)], 1)
    # strict-H positive: drhD == dfD on the 14 shared tuples
    shared = [tp for tp in RB18 if tp in DFD_TUPLES]
    t.group("STRICT-H positive (drhD vs dfD, shared)", ff_pair("drhD", "dfD", shared, "STRICT"), 14)
    # strict-H negative: drhZ vs drhD must differ
    t.group("STRICT-H negative (drhZ vs drhD east/half/707 differs)",
            ff_pair("drhZ", "drhD", [("east", "half", 707)], "STRICT", expect_ok=False, expect_fail=["STRICT"]), 1)
    # S positive, synthetic
    sr = load(shard("drgDa", "east"))
    sn = copy.deepcopy(sr)
    sn["tag"], sn["params"] = "synth", strip6(sr["params"])
    for e in sn["evals"]:
        e["wall_s"] = -1.0
    oks, fs, ds = rule_s(sn, sr, strict=False)
    print("    synthetic no-set copy of drgDa vs drgDa: %s" % ("pass" if oks else "fails %s %s" % (fs, ds)))
    t.group("S positive (synthetic)", [(oks, ds)], 1)
    # S negative: ihrest (mode 0, no --set) vs drgD fails S2/S3, passes S4
    t.group("S negative (ihrest vs drgD fails S2+S3, passes S4)",
            rb_pair("ihrest", "drgD", strict=False, expect_ok=False, expect_fail=["S2", "S3"]), 4)
    # strict-S positive: drgD == dcrbD
    t.group("STRICT-S positive (drgD vs dcrbD)", rb_pair("drgD", "dcrbD", strict=True), 4)
    return t.done()


def controls(q1_alt):
    t = Tally()
    print("CONTROLS at the post-flip HEAD")
    t.group("flxD STRICT == drhD (east/half/707, south/half/404)",
            ff_pair("flxD", "drhD", [("east", "half", 707), ("south", "half", 404)], "STRICT"), 2)
    t.group("flxD STRICT == dfD (707, 404, east/def/101)",
            ff_pair("flxD", "dfD", [("east", "half", 707), ("south", "half", 404), ("east", "def", 101)], "STRICT"), 3)
    t.group("flxZ STRICT == drhZ (south/half/101)",
            ff_pair("flxZ", "drhZ", [("south", "half", 101)], "STRICT"), 1)
    ref = "drhZ" if q1_alt else "drhD"
    t.group("flxJ H2ONLY == %s (east/half/707; junk MODE/SPLIT/RESERVE/MARGIN)" % ref,
            ff_pair("flxJ", ref, [("east", "half", 707)], "H2ONLY"), 1)
    return t.done()


def wave():
    t = Tally()
    print("WAVE at the post-flip HEAD")
    t.group("flhD H == drhD (18 rbgate tuples)", ff_pair("flhD", "drhD", RB18, "H"), 18)
    shared = [tp for tp in RB18 if tp in DFD_TUPLES] + [("east", "def", 101)]
    t.group("flhD H == dfD (14 shared + east/def/101)", ff_pair("flhD", "dfD", shared, "H"), 15)
    t.group("flhD H == flxD (east/def/101, same commit)",
            ff_pair("flhD", "flxD", [("east", "def", 101)], "H"), 1)
    t.group("flgD S == drgD", rb_pair("flgD", "drgD", strict=False), 4)
    t.group("flgD S == dcrbD", rb_pair("flgD", "dcrbD", strict=False), 4)
    t.group("flgZ STRICT-S == drgZ", rb_pair("flgZ", "drgZ", strict=True), 4)
    return t.done()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("dryrun", "controls", "wave"), required=True)
    ap.add_argument("--q1-alt", action="store_true",
                    help="MODE fallback kept at 0: flxJ must equal drhZ instead of drhD")
    a = ap.parse_args()
    sys.stdout.reconfigure(newline="\n")
    if a.mode == "dryrun":
        return dryrun()
    if a.mode == "controls":
        return controls(a.q1_alt)
    return wave()


if __name__ == "__main__":
    sys.exit(main())
