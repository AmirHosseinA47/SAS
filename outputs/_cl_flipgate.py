"""Carrying-leg round: THE FLIP GATE G7 (1)-(3) (carryleg_prereg.txt section 10).

  (1) clFZ (flipped tree, explicit 0 x3), C13      == clB  13/13
  (2) clFD (flipped tree, no switch --set), C13+U30 == clA  43/43   (clA == clE2, info)
  (3) clFJ (flipped tree, MODE/SERVED junk), C13    == clA  13/13
FIELD RULE: every top-level key of the harness JSON except {tag, repo, wall_s, params,
extra_params} (stdout_sha256 / stdout_lines included), AND the sidecar's
transition_log_sha256 and movement_reason_sha256. Any difference -> FAIL (STOP).
--round 2 (carryleg_prereg.txt section 11, ruling S2): _cl_flip2_queue.txt, arms clF2Z (== clB),
clF2M (MODE=0 only, == clB), clF2D (== clA), clF2J (== clA); for an arm whose sidecar must report
served 0 (clF2Z, clF2M) every SERVED counter (OFF_COUNTERS) must also be 0.

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
# ROUND 2: where the arm's sidecar must report served 0 (clF2Z, clF2M), SERVED must also be
# BEHAVIOURALLY off - its site never called. Value identity alone cannot show it on C13:
# MODE 0 + SERVED 1 WITHOUT the enforcement already equals 6160438 there (clSN == clB 13/13,
# yet clSN's sidecars count custody_calls 360 / in_custody_calls 52 on those tuples).
OFF_COUNTERS = ("custody_calls", "custody_victim_steps", "in_custody_calls", "served_by_custody_only",
                "served_by_custody_only_not_geo")
SIDE = ("transition_log_sha256", "movement_reason_sha256")
ITEMS = (("(1)", "clFZ", "clB", ("C13",)),
         ("(2)", "clFD", "clA", ("C13", "U30")),
         ("(3)", "clFJ", "clA", ("C13",)))
# ROUND 2 (--round 2): the same checks on the ruling-S2 enforcement commit, plus (1m): MODE=0
# alone (SERVED left at its shipped 1, enforced 0) must be 6160438 value for value.
QUEUE, QUEUE2 = "_cl_flip_queue.txt", "_cl_flip2_queue.txt"
ITEMS2 = (("(1)", "clF2Z", "clB", ("C13",)),
          ("(1m)", "clF2M", "clB", ("C13",)),
          ("(2)", "clF2D", "clA", ("C13", "U30")),
          ("(3)", "clF2J", "clA", ("C13",)))


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
    queue, items, title = QUEUE, ITEMS, "FLIP GATE G7 (1)-(3) - carryleg_prereg.txt section 10"
    if sys.argv[1:] == ["--round", "2"]:
        queue, items = QUEUE2, ITEMS2
        title = "FLIP GATE ROUND 2 (ruling S2 enforcement) - carryleg_prereg.txt section 11"
    elif sys.argv[1:]:
        raise SystemExit("usage: _cl_flipgate.py [--round 2]")
    sets = C.seed_sets(_cl_seedcheck.run_checks(say=lambda *_a: None))
    idx = C.RunIndex([os.path.join(HERE, queue)], sets)
    n = idx.verify_all()
    print(title)
    print("  flip runs loaded and provenance-checked (RunIndex, flip-arm 'expect' switches): %d" % n["ff"])
    ok_all = True
    for item, tag, rtag, set_names in items:
        tuples = [t for sn in set_names for t in idx.tuples(tag, sn)]
        bad, info = [], []
        for t in tuples:
            d, s = idx.load(tag, t), idx.sidecar(tag, t)
            rd, rs = ref(rtag, t)
            dk = diff(d, rd, s, rs)
            if C.ARMS[tag].get("expect", {}).get("served") == 0:
                ct = s.get("counters") or {}
                dk += ["counters.%s=%r (SERVED must never act)" % (k, ct.get(k)) for k in OFF_COUNTERS
                       if ct.get(k) != 0]
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
    print("%s: %s" % ("G7 (1)-(3)" if items is ITEMS else "ROUND 2 (1)(1m)(2)(3)", "PASS" if ok_all else "FAIL -> STOP"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
