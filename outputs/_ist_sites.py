"""isTrue round Part 1: static enumeration of every `is True` / `is False` / `is not True` / `is not False`
identity test, plus the parameter keys each truthiness helper reads.

usage: _ist_sites.py [--repo <checkout>] [--json <out.json>]

Scope (the brief): agents.py, wildfire_model.py, common_fixed_variables.py and src_extension/ (walked with
os.walk; no directory outside src_extension/ is entered, so the quarantined outputs/ subdirectory is never
traversed). An identity site is an ast.Compare whose operator list contains Is / IsNot with a True/False
constant on either side. Comments and docstrings cannot match (the AST has no comments; a docstring is a
Constant, not a Compare).

Helper key lists: for every Call to a name in HELPERS (the module-level `_is_truthy` of four planners and the
utility_evaluation closures ptruth / ptruth_s / ptruth_p / _indicator / sig), the string constants among its
arguments, and for `_is_truthy(params.get("k"))` the key "k". Loops over a module-level tuple (`for key in
_MARKERS: ... _is_truthy(params.get(key))`) are resolved through the tuple's literal value.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys

ROOT_FILES = ("agents.py", "wildfire_model.py", "common_fixed_variables.py")
HELPERS = ("_is_truthy", "ptruth", "ptruth_s", "ptruth_p", "_indicator", "sig")


def _is_bool_const(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _files(repo: str) -> list[str]:
    out = [os.path.join(repo, f) for f in ROOT_FILES]
    base = os.path.join(repo, "src_extension")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for f in sorted(filenames):
            if f.endswith(".py"):
                out.append(os.path.join(dirpath, f))
    return out


def _module_tuples(tree: ast.Module) -> dict[str, tuple]:
    found: dict[str, tuple] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                val = ast.literal_eval(node.value)
            except Exception:
                continue
            if isinstance(val, tuple) and all(isinstance(v, str) for v in val):
                found[node.targets[0].id] = val
    return found


def _get_key(node: ast.AST) -> str | None:
    # params.get("k") / params.get(key)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
            and node.args):
        a = node.args[0]
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return a.value
        if isinstance(a, ast.Name):
            return "<var:%s>" % a.id
    return None


def scan(repo: str) -> dict:
    sites = []
    helper_keys: dict[str, dict[str, list[str]]] = {}
    for path in _files(repo):
        rel = os.path.relpath(path, repo).replace(os.sep, "/")
        with open(path, "rb") as f:
            src = f.read().decode("utf-8")
        tree = ast.parse(src, filename=rel)
        lines = src.splitlines()
        tuples = _module_tuples(tree)
        parent: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node

        def loop_values(call: ast.AST, var: str) -> tuple | None:
            # the nearest enclosing `for <var> in <tuple>` (a module-level tuple name or a literal)
            node = parent.get(call)
            while node is not None:
                if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == var:
                    it = node.iter
                    if isinstance(it, ast.Name) and it.id in tuples:
                        return tuples[it.id]
                    if isinstance(it, (ast.Tuple, ast.List)):
                        vals = [e.value for e in it.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                        if len(vals) == len(it.elts):
                            return tuple(vals)
                    return None
                node = parent.get(node)
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                operands = [node.left] + list(node.comparators)
                for i, op in enumerate(node.ops):
                    if isinstance(op, (ast.Is, ast.IsNot)):
                        lhs, rhs = operands[i], operands[i + 1]
                        if _is_bool_const(lhs) or _is_bool_const(rhs):
                            const = rhs if _is_bool_const(rhs) else lhs
                            other = lhs if const is rhs else rhs
                            sites.append({
                                "file": rel,
                                "line": node.lineno,
                                "op": ("is not " if isinstance(op, ast.IsNot) else "is ") + repr(const.value),
                                "operand": ast.unparse(other),
                                "text": lines[node.lineno - 1].strip(),
                            })
            if isinstance(node, ast.Call):
                fname = node.func.id if isinstance(node.func, ast.Name) else None
                if fname in HELPERS:
                    keys: list[str] = []
                    for a in node.args:
                        if isinstance(a, ast.Constant) and isinstance(a.value, str):
                            keys.append(a.value)
                        else:
                            k = _get_key(a)
                            if k is not None and k.startswith("<var:"):
                                var = k[5:-1]
                                keys.extend(loop_values(node, var) or (k,))
                            elif k is not None:
                                keys.append(k)
                    slot = helper_keys.setdefault(rel, {}).setdefault(fname, [])
                    for k in keys:
                        if k not in slot:
                            slot.append(k)
    sites.sort(key=lambda s: (s["file"], s["line"], s["op"]))
    return {"repo": repo, "n_sites": len(sites), "sites": sites, "helper_keys": helper_keys}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    res = scan(os.path.abspath(args.repo))
    sys.stdout.reconfigure(newline="\n")
    print("identity sites: %d" % res["n_sites"])
    for s in res["sites"]:
        print("  %s:%d  [%s]  %s" % (s["file"], s["line"], s["op"], s["operand"]))
    print("helper keys:")
    for rel, by in sorted(res["helper_keys"].items()):
        for fname, keys in sorted(by.items()):
            print("  %s %s: %s" % (rel, fname, ", ".join(keys)))
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
