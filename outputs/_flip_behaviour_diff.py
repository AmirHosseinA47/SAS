"""Flip round: prove the flip commit changes behaviour ONLY through the intended literals.

For each non-test source file the flip touched, parse the file at a base commit (git
show) and in the working tree (or at a second commit), blank every docstring, and
compare the ASTs node by node. Comments never reach the AST, so any remaining
difference is a real code change. Every differing Constant node is printed with its
old and new value; any other kind of difference is reported as NON-LITERAL and fails.

  python outputs/_flip_behaviour_diff.py [BASE [TARGET]]   (default b853617 vs working tree)
Exit 0 iff the only differences are Constant changes, and they are exactly EXPECTED.
"""
import ast
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["common_fixed_variables.py", "agents.py", "wildfire_model.py",
         "outputs/_ffr_harness.py", "outputs/_rblatch_campaign2.py"]
EXPECTED = {
    "common_fixed_variables.py": sorted([(0, 9), (0, 2), (0, 3), (60.0, 0.0), (5.0, 39.23)], key=repr),
    "agents.py": sorted([(0, 3), (0, 3), (0, 9), (0, 2), (0, 2), (0, 2),
                         (60.0, 0.0), (60.0, 0.0), (5.0, 39.23), (5.0, 39.23)], key=repr),
    "wildfire_model.py": [],
    "outputs/_ffr_harness.py": [],
    "outputs/_rblatch_campaign2.py": [],
}


def source(rev, path):
    if rev is None:
        with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
            return fh.read()
    out = subprocess.run(["git", "show", "%s:%s" % (rev, path)], cwd=ROOT,
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8").replace("\r\n", "\n")


class Blank(ast.NodeTransformer):
    def _strip(self, node):
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            body[0].value.value = "<doc>"
        self.generic_visit(node)
        return node

    visit_Module = visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _strip


def walk_pairs(a, b, diffs, path="$"):
    if type(a) is not type(b):
        diffs.append(("NON-LITERAL", path, type(a).__name__, type(b).__name__))
        return
    if isinstance(a, ast.Constant):
        if a.value != b.value or type(a.value) is not type(b.value):
            diffs.append(("CONST", path, a.value, b.value))
        return
    if isinstance(a, ast.AST):
        for field in a._fields:
            walk_pairs(getattr(a, field, None), getattr(b, field, None), diffs, "%s.%s" % (path, field))
        return
    if isinstance(a, list):
        if len(a) != len(b):
            diffs.append(("NON-LITERAL", path, "len %d" % len(a), "len %d" % len(b)))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            walk_pairs(x, y, diffs, "%s[%d]" % (path, i))
        return
    if a != b:
        diffs.append(("NON-LITERAL", path, a, b))


def main(argv):
    base = argv[1] if len(argv) > 1 else "b853617"
    target = argv[2] if len(argv) > 2 else None
    ok = True
    print("AST diff, docstrings blanked: %s -> %s" % (base, target or "working tree"))
    for path in FILES:
        ta = Blank().visit(ast.parse(source(base, path)))
        tb = Blank().visit(ast.parse(source(target, path)))
        diffs = []
        walk_pairs(ta, tb, diffs)
        consts = sorted([(d[2], d[3]) for d in diffs if d[0] == "CONST"], key=repr)
        other = [d for d in diffs if d[0] != "CONST"]
        good = not other and consts == EXPECTED[path]
        ok &= good
        print("%s  %s: %d literal change(s)%s" % ("OK " if good else "BAD", path, len(consts),
              "" if not consts else " " + ", ".join("%r->%r" % c for c in consts)))
        for d in other:
            print("      NON-LITERAL %s: %r vs %r" % (d[1], d[2], d[3]))
        if consts != EXPECTED[path]:
            print("      expected %s" % EXPECTED[path])
    print("BEHAVIOUR DIFF %s" % ("= EXACTLY THE INTENDED LITERALS" if ok else "HAS UNEXPECTED CHANGES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
