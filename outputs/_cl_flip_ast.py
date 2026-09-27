"""Carrying-leg round: G7 (0) - the flip commit changes behaviour ONLY through the intended
literals (carryleg_prereg.txt section 10). outputs/_flip_behaviour_diff.py's method (the flip
round), with this round's files and literals.

  1. `git diff --name-only BASE TARGET`, restricted to paths outside outputs/ plus the
     harness files below (this round's outputs/ tooling and documents are not model code):
     every such changed path is one of common_fixed_variables.py, agents.py,
     tests/test_carry_leg.py (the pins) - anything else FAILS;
  2. for every tracked non-test .py of the model and its harnesses (the rule-A2 frozen
     set: agents.py, wildfire_model.py, common_fixed_variables.py, evaluate_scenarios.py,
     serve_dashboard.py, every tracked src_extension/*.py, outputs/_ffr_harness.py,
     outputs/_fm2_probe_harness.py, outputs/_rblatch_campaign2.py), parse at BASE and at
     TARGET, blank every docstring, compare the ASTs node by node: the differing Constant
     nodes must be EXACTLY the EXPECTED multiset, and any other kind of difference FAILS.
Comments never reach the AST. Exit 0 iff both hold.

usage: .venv/Scripts/python.exe -B outputs/_cl_flip_ast.py BASE TARGET   (e.g. 108a0ad HEAD)
"""
import ast
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from _flip_behaviour_diff import Blank, walk_pairs  # noqa: E402  (the flip round's method, unchanged)

ALLOWED_CHANGED = {"common_fixed_variables.py", "agents.py", "tests/test_carry_leg.py"}
FIXED = ["agents.py", "wildfire_model.py", "common_fixed_variables.py", "evaluate_scenarios.py",
         "serve_dashboard.py", "outputs/_ffr_harness.py", "outputs/_fm2_probe_harness.py",
         "outputs/_rblatch_campaign2.py"]
EXPECTED = {
    # FF_EXIT_LEG_MODE 0 -> 2, FF_EXIT_LEG_SERVED 0 -> 1
    "common_fixed_variables.py": sorted([(0, 2), (0, 1)], key=repr),
    # EXIT_LEG_MODE_JUNK 1 -> 2; getattr(cfv, "FF_EXIT_LEG_MODE", 0 -> 2); (..."SERVED", 0 -> 1)
    "agents.py": sorted([(1, 2), (0, 2), (0, 1)], key=repr),
}


def git(*args):
    r = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True)
    if r.returncode != 0:
        raise SystemExit("CL_FLIP_AST: git %s failed: %s" % (" ".join(args), r.stderr.decode(errors="replace")))
    return r.stdout.decode("utf-8")


def source(rev, path):
    return git("show", "%s:%s" % (rev, path)).replace("\r\n", "\n")


def main(argv):
    if len(argv) != 3:
        raise SystemExit(__doc__)
    base, target = argv[1], argv[2]
    ok = True
    files = FIXED + sorted(p for p in git("ls-files", "--", "src_extension").splitlines() if p.endswith(".py"))
    # the behaviour question covers the model, its harnesses and the tests; this round's own
    # outputs/ tooling and documents (committed between BASE and the flip) are not model code
    scope = set(files) | {p for p in git("ls-files", "--", "tests").splitlines()}
    changed = sorted(p for p in git("diff", "--name-only", base, target).splitlines()
                     if p.strip() and (p in scope or p.startswith("tests/") or not p.startswith("outputs/")))
    extra = [p for p in changed if p not in ALLOWED_CHANGED]
    print("G7 (0) AST behaviour diff, docstrings blanked: %s -> %s" % (base, target))
    print("  changed paths: %s" % changed)
    if extra:
        ok = False
        print("  BAD: paths outside %s: %s" % (sorted(ALLOWED_CHANGED), extra))
    for path in files:
        ta = Blank().visit(ast.parse(source(base, path)))
        tb = Blank().visit(ast.parse(source(target, path)))
        diffs = []
        walk_pairs(ta, tb, diffs)
        consts = sorted([(d[2], d[3]) for d in diffs if d[0] == "CONST"], key=repr)
        other = [d for d in diffs if d[0] != "CONST"]
        want = EXPECTED.get(path, [])
        good = not other and consts == want
        ok &= good
        if consts or other or path in EXPECTED:
            print("  %s %s: %d literal change(s)%s" % ("OK " if good else "BAD", path, len(consts),
                  "" if not consts else " " + ", ".join("%r->%r" % c for c in consts)))
        for d in other:
            print("      NON-LITERAL %s: %r vs %r" % (d[1], d[2], d[3]))
        if consts != want:
            print("      expected %s" % want)
    print("  %d files compared; every other file: no AST difference" % len(files))
    print("G7 (0): %s" % ("PASS - EXACTLY THE INTENDED LITERALS" if ok else "FAIL -> STOP"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
