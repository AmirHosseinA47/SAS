"""Carrying-leg round: THE FLIP GATE G7 (1)-(3) (carryleg_prereg.txt section 10).

  (1) clFZ (flipped tree, explicit 0 x3), C13      == clB  13/13
  (2) clFD (flipped tree, no switch --set), C13+U30 == clA  43/43   (clA == clE2, info)
  (3) clFJ (flipped tree, MODE/SERVED junk), C13    == clA  13/13
FIELD RULE: every top-level key of the harness JSON except {tag, repo, wall_s, params,
extra_params} (stdout_sha256 / stdout_lines included), AND the sidecar's
transition_log_sha256 and movement_reason_sha256. Any difference -> FAIL (STOP).

The flip runs load through _cl_common.RunIndex over outputs/_cl_flip_queue.txt (full
provenance: line, JSON, sidecar - including the sidecar switches the flip arms must report,
_cl_common.ARMS "expect"). The references (clB, clA, clE2) are this round's recorded runs,
loaded by explicit name; they were provenance-checked by their own stage analyses.
Pure reader: writes nothing. Exit 0 iff (1)-(3) all PASS.

usage: .venv/Scripts/python.exe -B outputs/_cl_flipgate.py
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cl_common as C  # noqa: E402
import _cl_seedcheck  # noqa: E402

SKIP = {"tag", "repo", "wall_s", "params", "extra_params"}
SIDE = ("transition_log_sha256", "movement_reason_sha256")
ITEMS = (("(1)", "clFZ", "clB", ("C13",)),
         ("(2)", "clFD", "clA", ("C13", "U30")),
         ("(3)", "clFJ", "clA", ("C13",)))


def diff(a, b, sa, sb):
    keys = sorted((set(a) | set(b)) - SKIP)
    out = [k for k in keys if a.get(k) != b.get(k)]
    out += ["sidecar." + k for k in SIDE if sa.get(k) != sb.get(k)]
    return out


def ref(tag, tup):
    d = C.load_json(C.run_json(tag, tup))
    s = C.load_json(C.sidecar_path(tag, tup))
    return d, s


def main():
    sets = C.seed_sets(_cl_seedcheck.run_checks(say=lambda *_a: None))
    idx = C.RunIndex([os.path.join(HERE, "_cl_flip_queue.txt")], sets)
    n = idx.verify_all()
    print("FLIP GATE G7 (1)-(3) - carryleg_prereg.txt section 10")
    print("  flip runs loaded and provenance-checked (RunIndex, flip-arm 'expect' switches): %d" % n["ff"])
    ok_all = True
    for item, tag, rtag, set_names in ITEMS:
        tuples = [t for sn in set_names for t in idx.tuples(tag, sn)]
        bad, info = [], []
        for t in tuples:
            d, s = idx.load(tag, t), idx.sidecar(tag, t)
            rd, rs = ref(rtag, t)
            dk = diff(d, rd, s, rs)
            if dk:
                bad.append("%s: %s" % (C.label(t), dk[:8]))
            if rtag == "clA":
                ed, es = ref("clE2", t)
                if diff(d, ed, s, es):
                    info.append(C.label(t))
        want = sum(len(sets[sn]) for sn in set_names)
        ok = not bad and len(tuples) == want
        ok_all &= ok
        print("  %s %s == %s over %s: %d/%d %s" % (item, tag, rtag, "+".join(set_names), len(tuples) - len(bad),
                                                   want, "PASS" if ok else "FAIL"))
        for b in bad:
            print("      DIFF " + b)
        if rtag == "clA":
            print("      (info) %s == clE2 as well: %d/%d" % (tag, len(tuples) - len(info), len(tuples)))
    print("G7 (1)-(3): %s" % ("PASS" if ok_all else "FAIL -> STOP"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
