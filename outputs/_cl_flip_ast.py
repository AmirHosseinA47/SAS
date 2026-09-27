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
       .venv/Scripts/python.exe -B outputs/_cl_flip_ast.py --enforce BASE TARGET
         G7 (0') for ruling S2 (carryleg_prereg.txt section 11): the model change is confined to
         agents.ff_exit_leg_served, whose body must be EXACTLY the base body with one leading
         statement added: `if ff_exit_leg_mode() == 0: return 0`; comment-only changes to
         wildfire_model.py / rescue_planner.py are allowed (their ASTs must be identical).
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


class BlankFunc(ast.NodeTransformer):
    """Replace the BODY of the named top-level function by `pass` (its signature stays)."""
    def __init__(self, name):
        self.name = name
        self.found = 0

    def visit_FunctionDef(self, node):
        if node.name == self.name:
            self.found += 1
            node.body = [ast.Pass()]
        return node


ENFORCE_ALLOWED = ALLOWED_CHANGED | {"wildfire_model.py", "src_extension/planning/rescue_planner.py"}
ENFORCE_GUARD = "if ff_exit_leg_mode() == 0:\n    return 0"


def _body_wo_doc(fn):
    return [s for s in fn.body
            if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))]


def enforce(base, target):
    """G7 (0') - ruling S2: BASE (the flip commit) -> TARGET (the enforcement commit) changes
    the model ONLY inside agents.ff_exit_leg_served: changed paths within ALLOWED_CHANGED,
    common_fixed_variables.py AST-identical (comment-only), agents.py AST-identical once that
    one function's body is blanked on both sides, every other frozen file identical. The
    function itself is printed before/after."""
    ok = True
    files = FIXED + sorted(p for p in git("ls-files", "--", "src_extension").splitlines() if p.endswith(".py"))
    changed = sorted(p for p in git("diff", "--name-only", base, target).splitlines()
                     if p.strip() and (p in files or p.startswith("tests/") or not p.startswith("outputs/")))
    extra = [p for p in changed if p not in ENFORCE_ALLOWED]
    print("G7 (0') ENFORCEMENT SCOPE, docstrings blanked: %s -> %s" % (base, target))
    print("  changed paths: %s" % changed)
    if extra:
        ok = False
        print("  BAD: paths outside %s: %s" % (sorted(ENFORCE_ALLOWED), extra))
    for path in files:
        ta = Blank().visit(ast.parse(source(base, path)))
        tb = Blank().visit(ast.parse(source(target, path)))
        if path == "agents.py":
            fa, fb = BlankFunc("ff_exit_leg_served"), BlankFunc("ff_exit_leg_served")
            before = [n for n in ast.walk(ast.parse(source(base, path)))
                      if isinstance(n, ast.FunctionDef) and n.name == "ff_exit_leg_served"]
            after = [n for n in ast.walk(ast.parse(source(target, path)))
                     if isinstance(n, ast.FunctionDef) and n.name == "ff_exit_leg_served"]
            ta, tb = fa.visit(ta), fb.visit(tb)
            if fa.found != 1 or fb.found != 1:
                ok = False
                print("  BAD agents.py: ff_exit_leg_served found %d / %d times" % (fa.found, fb.found))
        diffs = []
        walk_pairs(ta, tb, diffs)
        if diffs:
            ok = False
            print("  BAD %s: %d difference(s) outside the allowed scope, e.g. %r" % (path, len(diffs), diffs[:3]))
        elif path in ("agents.py", "common_fixed_variables.py"):
            print("  OK  %s: identical%s" % (path, " outside ff_exit_leg_served" if path == "agents.py" else
                                            " (the change is comments only)"))
    if len(before) == 1 and len(after) == 1:
        bb, ab = _body_wo_doc(before[0]), _body_wo_doc(after[0])
        guard_ok = bool(ab) and ast.unparse(ab[0]) == ENFORCE_GUARD
        rest_ok = [ast.dump(s) for s in ab[1:]] == [ast.dump(s) for s in bb]
        same_sig = ast.dump(before[0].args) == ast.dump(after[0].args) and \
            ast.dump(before[0].returns) == ast.dump(after[0].returns)
        if not (guard_ok and rest_ok and same_sig):
            ok = False
        print("  %s ff_exit_leg_served: first statement is the guard %s; the rest == the base body %s; "
              "same signature %s" % ("OK " if guard_ok and rest_ok and same_sig else "BAD", guard_ok, rest_ok,
                                     same_sig))
    for label, fns in (("before", before), ("after", after)):
        for fn in fns:
            fn.body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))]
            print("  ff_exit_leg_served %s (docstring dropped):" % label)
            for ln in ast.unparse(fn).splitlines():
                print("      " + ln)
    print("  %d files compared" % len(files))
    print("G7 (0'): %s" % ("PASS - THE MODEL CHANGE IS CONFINED TO ff_exit_leg_served" if ok else "FAIL -> STOP"))
    return 0 if ok else 1


def main(argv):
    if len(argv) == 4 and argv[1] == "--enforce":
        return enforce(argv[2], argv[3])
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
