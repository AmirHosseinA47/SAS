"""Urgency round Part 2 - the mutation check (outputs/urgency_part1.txt 15.3, 15.4 and 22.6.2). The engine is a port
of dispatch:outputs/_dp_mutants.py; the mutants live in two spec files written with the tests and imported LAZILY
at run time:
    outputs/_ud_mutants_u1.py   MUTANTS_U1   U1, the urgency re-dispatch order (15.3)
    outputs/_ud_mutants_mv.py   MUTANTS_MV   the movement fixes (a), (b), (c) and ALL (22.6.2)
each a dict  id -> (description, [(file, old, new), ...], [pytest node ids]).  A missing spec file, a spec that
fails to import, a malformed entry or an id defined twice STOPS with a message naming it.

THE CONVENTION (15.3 / 15.4). Every test names its mutant in its docstring ("MUTANT: <id>"). A mutant is the
smallest exact-text source change that removes what the test guards: (file, old, new), where old matches the
CURRENT source EXACTLY ONCE (edits of one mutant apply in order, each to the text the previous ones left; "\\n" in
old / new stands for the file's own line ending). The test must FAIL on its mutant and PASS on the source.

THE ENGINE. For each mutant: copy the checkout's root *.py, src_extension/ and tests/ (no __pycache__) into a work
directory - the checkout itself is never touched - apply the mutant, and run ALL its listed tests in ONE pytest call
WITHOUT -x; each test's own outcome is read from the JUnit XML, so the record is PER TEST (15.4: "killed or
survived per test"). A node naming one parametrized case must fail itself; a node naming a whole parametrized
function is killed when at least one case fails (the record gives k/n). A mutant is KILLED only when EVERY listed
node is killed. A CONTROL copy (no mutant) must pass every listed node. Before any pytest call every chosen mutant
is applied once to the base copy (all edits must match exactly once - every failure is listed, then STOP).
An import check before any pytest call STOPS unless the copy's mutated modules import from the copy (and mesa is
1.2.1); inside every pytest call a plugin records where each mutated module was imported from, and a module
imported from outside the work copy fails that mutant (it would not have been exercised). PYTHONHASHSEED=0;
pytest runs with -p no:cacheprovider, --rootdir = the copy and an empty ini (no stray config can apply).
OUTCOME TYPES (review R2 m-3). Each case's JUnit outcome is recorded as failure / error / skipped / passed (a case
with an <error> child is "error" even if it also has a <failure>). Only a test-BODY failure is a kill. An error
(setup, teardown, fixture) is ERROR: never a kill, and the check is then NOT clean; a collection error leaves the
node uncollected (MISSING, not clean). The failure's exception type is recorded, and a kill by anything but an
AssertionError is noted (not a failure of the check).
BOUND TO ITS TREE (review R2 m-3). The result header and the JSON carry the sha256 of the files the check copied and
mutated against - every module a chosen mutant edits, every test file a chosen mutant lists, the round's test files
and tests/urgency_test_support.py, as copied into the work copy - plus a digest of the WHOLE copied tree (sha256 over
"<relative path> <sha256>" lines of every copied file, sorted), the sha256 of each spec file as loaded and of this
engine. A file that differs in the checkout at the end of the run is reported (CHANGED DURING THE RUN).
DOCSTRING CROSS-CHECK (lint): each listed test's docstring contains "MUTANT" and its mutant's id; a test in a listed
file whose docstring names a mutant id must be listed for it. Issues fail the check (--no-lint skips it).

usage (urgency worktree root, the urgency .venv python - mesa 1.2.1 is required):
  python outputs/_ud_mutants.py [--repo E:\\Projects\\SAS_wt\\urgency] [--work DIR] [--only id,id] [--jobs 3]
         [--out FILE] [--json FILE] [--timeout SEC] [--spec FILE ...] [--copy-extra REL ...]
         [--list | --preflight] [--no-lint]
  --work     scratch directory (default: a new temp dir, removed afterwards); never inside the checkout
  --jobs     concurrent pytest processes (default 3: with this process, 4 python processes at most)
  --timeout  seconds per pytest call (default 5400); a TIMEOUT is not a kill - the check is not clean
  --spec     use these spec files instead of the two above (each defines MUTANTS_U1, MUTANTS_MV or MUTANTS)
  --list     list the mutants and exit;  --preflight  copy, apply, lint and import-check only (no pytest)
exit: 0 clean (control passes, every mutant killed on every listed test, lint clean); 1 not clean; 2 STOP.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REPO = Path(r"E:\Projects\SAS_wt\urgency")
SPECS = (("_ud_mutants_u1.py", "MUTANTS_U1"), ("_ud_mutants_mv.py", "MUTANTS_MV"))
SPEC_NAMES = ("MUTANTS_U1", "MUTANTS_MV", "MUTANTS")
QUARANTINE_NAME = "_firemech_rewound_20260914"
REQUIRED_MESA = "1.2.1"
# always hashed when present (R2 m-3): the round's two test files and their shared helper module
BOUND_FILES = ("tests/test_urgency_dispatch.py", "tests/test_movement_fixes.py", "tests/urgency_test_support.py")
LOADED_SPECS: dict[str, str] = {}  # spec file (as given / resolved) -> sha256 of the bytes loaded
_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
_PLUGIN = '''"""_ud_mutants.py origin recorder: where each mutated module was imported from (written at session end)."""
import json
import os
import sys


def pytest_sessionfinish(session, exitstatus):
    names = [n for n in os.environ.get("UD_MUT_MODULES", "").split(",") if n]
    found = {}
    for name in names:
        mod = sys.modules.get(name)
        found[name] = getattr(mod, "__file__", None) if mod is not None else None
    with open(os.environ["UD_MUT_ORIGIN_OUT"], "w", encoding="utf-8") as fh:
        json.dump(found, fh)
'''


class Stop(Exception):
    pass


Mutant = tuple  # (description, [(file, old, new)], [nodes])


# --------------------------------------------------------------------------------------------------------- specs
def _load_module(path: Path, label: str):
    if not path.is_file():
        raise Stop("mutation spec %s is MISSING: %s (it is written with the tests; the engine cannot run "
                   "without it)" % (label, path))
    name = "_udmut_spec_%s" % re.sub(r"\W", "_", path.stem)
    LOADED_SPECS[str(path)] = _sha256(path)
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise Stop("mutation spec %s cannot be loaded: %s" % (label, path))
    module = importlib.util.module_from_spec(spec)
    added = str(path.parent) not in sys.path
    if added:
        sys.path.insert(0, str(path.parent))
    no_pyc = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # never leave a __pycache__ beside the specs in outputs/
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - reported verbatim
        raise Stop("mutation spec %s failed to import (%s: %s): %s" % (label, type(exc).__name__, exc, path))
    finally:
        sys.dont_write_bytecode = no_pyc
        if added:
            sys.path.remove(str(path.parent))
    if _sha256(path) != LOADED_SPECS[str(path)]:
        raise Stop("mutation spec %s changed while it was being loaded - re-run" % path)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tree_digest(root: Path) -> tuple[str, int]:
    """(sha256 over '<relative posix path> <sha256>' lines of every file under root, sorted; number of files)."""
    lines = sorted("%s %s" % (p.relative_to(root).as_posix(), _sha256(p)) for p in root.rglob("*") if p.is_file())
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest(), len(lines)


def _bound_files(base: Path, mutants: dict[str, Mutant], chosen: list[str]) -> list[str]:
    """The files a result is bound to (R2 m-3): every file a chosen mutant edits, every test file a chosen mutant lists,
    and BOUND_FILES - those present in the copy, sorted."""
    rels = set(BOUND_FILES)
    for mid in chosen:
        rels.update(e[0].replace("\\", "/") for e in mutants[mid][1])
        rels.update(n.split("::", 1)[0].replace("\\", "/") for n in mutants[mid][2])
    return sorted(r for r in rels if (base / r).is_file())


def _validate(mid: object, entry: object, source: str) -> list[str]:
    errs = []
    where = "%s[%r]" % (source, mid)
    if not isinstance(mid, str) or not _ID_RE.match(mid):
        return ["%s: the id must be a string of letters, digits, _ . -" % where]
    if not isinstance(entry, (tuple, list)) or len(entry) != 3:
        return ["%s: an entry is (description, [(file, old, new), ...], [node ids])" % where]
    desc, edits, nodes = entry
    if not isinstance(desc, str) or not desc.strip():
        errs.append("%s: empty description" % where)
    if not isinstance(edits, (list, tuple)) or not edits:
        errs.append("%s: no edits" % where)
    else:
        for i, edit in enumerate(edits):
            if not isinstance(edit, (list, tuple)) or len(edit) != 3 or not all(isinstance(x, str) for x in edit):
                errs.append("%s: edit %d is not (file, old, new) strings" % (where, i))
                continue
            rel, old, new = edit
            parts = rel.replace("\\", "/").split("/")
            if rel.startswith(("/", "\\")) or ":" in rel or ".." in parts or not rel.endswith(".py"):
                errs.append("%s: edit %d file %r must be a relative .py path in the checkout" % (where, i, rel))
            if not old:
                errs.append("%s: edit %d has an empty old text" % (where, i))
            if old == new:
                errs.append("%s: edit %d changes nothing (old == new)" % (where, i))
    if not isinstance(nodes, (list, tuple)) or not nodes:
        errs.append("%s: no test nodes" % where)
    else:
        for node in nodes:
            if not isinstance(node, str) or "::" not in node or not node.split("::", 1)[0].endswith(".py"):
                errs.append("%s: node %r is not <file.py>::<test>" % (where, node))
            elif not node.replace("\\", "/").startswith("tests/"):
                errs.append("%s: node %r is not under tests/" % (where, node))
        if len(set(nodes)) != len(nodes):
            errs.append("%s: a node is listed twice" % where)
    return errs


def load_mutants(spec_paths: list[str] | None) -> tuple[dict[str, Mutant], dict[str, str]]:
    """Every mutant, and the spec each came from. Lazy: called at run time, never at import."""
    sources: list[tuple[Path, tuple[str, ...]]]
    if spec_paths:
        sources = [(Path(p).resolve(), SPEC_NAMES) for p in spec_paths]
    else:
        sources = [(HERE / fname, (var,)) for fname, var in SPECS]
    mutants: dict[str, Mutant] = {}
    origin: dict[str, str] = {}
    errs: list[str] = []
    for path, names in sources:
        module = _load_module(path, "/".join(names) if len(names) == 1 else path.name)
        found = [n for n in names if hasattr(module, n)]
        if not found:
            raise Stop("mutation spec %s defines none of %s" % (path, ", ".join(names)))
        for var in found:
            table = getattr(module, var)
            label = "%s:%s" % (path.name, var)
            if not isinstance(table, dict) or not table:
                raise Stop("%s is not a non-empty dict" % label)
            for mid, entry in table.items():
                bad = _validate(mid, entry, label)
                errs += bad
                if bad:
                    continue
                if mid in mutants:
                    errs.append("mutant id %r is defined in %s and in %s" % (mid, origin[mid], label))
                    continue
                mutants[mid] = (entry[0], [tuple(e) for e in entry[1]], list(entry[2]))
                origin[mid] = label
    if errs:
        raise Stop("malformed mutation spec:\n  " + "\n  ".join(errs))
    return mutants, origin


# ---------------------------------------------------------------------------------------------------- copy, apply
def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _copy_tree(repo: Path, dest: Path, extra: list[str]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in repo.glob("*.py"):
        shutil.copy2(path, dest / path.name)
    shutil.copytree(repo / "src_extension", dest / "src_extension", ignore=_IGNORE)
    shutil.copytree(repo / "tests", dest / "tests", ignore=_IGNORE)
    for rel in extra:
        src = repo / rel
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, ignore=_IGNORE)
        else:
            shutil.copy2(src, target)


def _check_extra(repo: Path, extra: list[str]) -> None:
    for rel in extra:
        parts = Path(rel).parts
        if Path(rel).is_absolute() or ".." in parts or not parts:
            raise Stop("--copy-extra %r must be a relative path inside the checkout" % rel)
        if QUARANTINE_NAME in parts or parts[0] == ".git" or (parts[0] == "outputs" and len(parts) == 1):
            raise Stop("--copy-extra %r is refused (quarantine, .git or the whole outputs/)" % rel)
        if not (repo / rel).exists():
            raise Stop("--copy-extra %r does not exist in %s" % (rel, repo))


def _apply_text(raw: str, old: str, new: str) -> tuple[str | None, str]:
    """Replace old (written with \\n) by new in raw, in the file's own line ending. (result, '') or (None, why)."""
    old, new = old.replace("\r\n", "\n"), new.replace("\r\n", "\n")
    crlf = raw.count("\r\n")
    bare_lf = raw.count("\n") - crlf
    as_lf = (old, new)
    as_crlf = (old.replace("\n", "\r\n"), new.replace("\n", "\r\n"))
    if crlf and not bare_lf:
        pairs = [as_crlf]
    elif bare_lf and not crlf:
        pairs = [as_lf]
    else:  # mixed endings (or a one-line file): either spelling may be the one present; they never overlap
        pairs = [as_lf] if as_lf[0] == as_crlf[0] else [as_lf, as_crlf]
    counts = [raw.count(o) for o, _ in pairs]
    if sum(counts) != 1:
        return None, "old text matches %d times (must be exactly once)" % sum(counts)
    o, n = pairs[counts.index(1)]
    return raw.replace(o, n), ""


def apply_edits(dest: Path, edits: list[tuple[str, str, str]], write: bool = True) -> list[str]:
    """Apply in order; returns the errors (nothing is written when any edit fails)."""
    texts: dict[str, str] = {}
    errs = []
    for i, (rel, old, new) in enumerate(edits):
        path = dest / rel
        if rel not in texts:
            if not path.is_file():
                errs.append("edit %d: %s is not in the copy" % (i, rel))
                continue
            texts[rel] = path.read_bytes().decode("utf-8")
        result, why = _apply_text(texts[rel], old, new)
        if result is None:
            errs.append("edit %d in %s: %s: %r" % (i, rel, why, old[:90]))
            continue
        texts[rel] = result
    if write and not errs:
        for rel, text in texts.items():
            (dest / rel).write_bytes(text.encode("utf-8"))
    return errs


def _module_name(rel: str) -> str | None:
    rel = rel.replace("\\", "/")
    if rel.startswith("tests/") or not rel.endswith(".py"):
        return None
    mod = rel[:-3].replace("/", ".")
    return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod


# ----------------------------------------------------------------------------------------------------- pytest, xml
def _address(node: str) -> tuple[str, str]:
    """pytest junitxml's (classname, name) for a node id given relative to the rootdir (mangle_test_address)."""
    path, bracket, params = node.partition("[")
    names = path.split("::")
    names[0] = re.sub(r"\.py$", "", names[0].replace("\\", "/").replace("/", "."))
    names[-1] += bracket + params
    return ".".join(names[:-1]), names[-1]


OUTCOMES = ("failure", "error", "skipped", "passed")


def _exc_type(message: str, type_attr: str | None) -> str:
    """The exception type of a JUnit <failure>: its type attribute when pytest wrote one, else read from the message
    (pytest strips "AssertionError: " from a rewritten assert, whose message then starts with "assert")."""
    if type_attr:
        return type_attr.split(".")[-1]
    msg = (message or "").strip()
    if not msg or msg == "assert" or msg.startswith(("assert ", "assert\n", "AssertionError")):
        return "AssertionError"
    head = msg.split(":", 1)[0].strip()
    return head.split(".")[-1] if re.match(r"^[A-Za-z_][\w.]*$", head) else "?"


def _cases(xml_path: Path) -> dict[tuple[str, str], dict]:
    """(classname, name) -> {"outcome": failure | error | skipped | passed, "tags": the child tags seen, "exc": the
    failure's exception type (or None), "msg": the first error / failure message (120 chars)}. A case reported more
    than once (pytest writes a teardown error as its own entry) merges: error > failure > skipped > passed."""
    out: dict[tuple[str, str], dict] = {}
    if not xml_path.exists():
        return out
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        key = (str(case.get("classname", "")), str(case.get("name", "")))
        entry = out.setdefault(key, {"outcome": "passed", "tags": [], "exc": None, "msg": None})
        for child in case:
            if child.tag not in ("failure", "error", "skipped"):
                continue
            entry["tags"].append(child.tag)
            message = str(child.get("message", "") or "")
            if child.tag == "failure" and entry["exc"] is None:
                entry["exc"] = _exc_type(message, child.get("type"))
            if child.tag in ("failure", "error") and entry["msg"] is None:
                entry["msg"] = message[:120]
        tags = entry["tags"]
        entry["outcome"] = ("error" if "error" in tags else "failure" if "failure" in tags
                            else "skipped" if "skipped" in tags else "passed")
    return out


def _node_result(node: str, cases: dict[tuple[str, str], dict]) -> dict:
    """One listed node's cases: {"cases": n, "failed": test-body failures, "error": errors (setup / teardown),
    "skipped", "passed", "outcomes": [per case], "exc": [failure exception types], "error_msgs": [...]}."""
    classname, name = _address(node)
    whole = "[" not in name

    def match(cn: str, n: str, exact_class: bool) -> bool:
        if exact_class and cn != classname:
            return False
        if not exact_class and cn.split(".")[-1] != classname.split(".")[-1]:
            return False
        return n == name or (whole and n.startswith(name + "["))

    hits = [c for (cn, n), c in sorted(cases.items()) if match(cn, n, True)]
    if not hits:  # a different rootdir spelling: fall back to the module stem, as _dp_mutants did
        hits = [c for (cn, n), c in sorted(cases.items()) if match(cn, n, False)]
    count = {o: sum(1 for c in hits if c["outcome"] == o) for o in OUTCOMES}
    return {"cases": len(hits), "failed": count["failure"], "error": count["error"], "skipped": count["skipped"],
            "passed": count["passed"], "outcomes": [c["outcome"] for c in hits],
            "exc": sorted({c["exc"] for c in hits if c["outcome"] == "failure" and c["exc"]}),
            "error_msgs": [c["msg"] for c in hits if c["outcome"] == "error"][:3]}


def _collection_errors(cases: dict[tuple[str, str], dict]) -> list[str]:
    return sorted("%s::%s" % k for k, c in cases.items()
                  if c["outcome"] == "error" and "collection" in str(c.get("msg") or "").lower())


def _env(work: Path, modules: list[str], origin_out: Path) -> dict[str, str]:
    env = dict(os.environ, PYTHONHASHSEED="0", MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1",
               UD_MUT_MODULES=",".join(modules), UD_MUT_ORIGIN_OUT=str(origin_out))
    env["PYTHONPATH"] = str(work / "_plugin")  # the origin plugin only; the copy is first on sys.path (-m)
    return env


def _run(dest: Path, work: Path, py: str, nodes: list[str], modules: list[str], timeout: float) -> dict:
    xml_path = dest / "_junit.xml"
    origin_out = dest / "_origin.json"
    cmd = [py, "-m", "pytest", *nodes, "-q", "-p", "no:cacheprovider", "-p", "_udmut_origin",
           "-c", str(work / "_plugin" / "pytest.ini"), "--rootdir", str(dest),
           "--junitxml=%s" % xml_path, "-o", "junit_family=xunit2"]
    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.run(cmd, cwd=str(dest), env=_env(work, modules, origin_out), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
        rc, tail = proc.returncode, (proc.stdout + proc.stderr).splitlines()[-25:]
    except subprocess.TimeoutExpired as exc:
        timed_out, rc = True, None
        text = exc.stdout or ""
        if isinstance(text, bytes):
            text = text.decode("utf-8", "replace")
        tail = text.splitlines()[-25:]
    origin = None  # None = the plugin wrote no record
    if origin_out.exists():
        try:
            origin = json.loads(origin_out.read_text(encoding="utf-8"))
        except ValueError:
            origin = None
    return {"rc": rc, "cases": _cases(xml_path), "secs": time.time() - t0, "timeout": timed_out,
            "tail": tail, "origin": origin, "outside": _origin_problems(dest, origin or {})}


def _origin_problems(dest: Path, origin: dict) -> list[str]:
    bad = []
    for name, file in sorted(origin.items()):
        if file and not _inside(Path(file), dest):
            bad.append("%s imported from %s, OUTSIDE the work copy" % (name, file))
    return bad


def _import_check(base: Path, work: Path, py: str, modules: list[str]) -> list[str]:
    """Before any pytest: the copy's modules import from the copy, and mesa is 1.2.1."""
    code = ("import importlib, json, sys\nout = {}\nfor n in sys.argv[1:]:\n"
            "    out[n] = getattr(importlib.import_module(n), '__file__', None)\n"
            "import mesa\nout['mesa.__version__'] = mesa.__version__\nprint('UDMUT_ORIGIN ' + json.dumps(out))\n")
    proc = subprocess.run([py, "-c", code, *modules], cwd=str(base), env=_env(work, modules, base / "_x.json"),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    line = next((x for x in proc.stdout.splitlines() if x.startswith("UDMUT_ORIGIN ")), None)
    if proc.returncode != 0 or line is None:
        return ["import check failed (rc %s): %s" % (proc.returncode, (proc.stderr or proc.stdout)[-600:])]
    found = json.loads(line[len("UDMUT_ORIGIN "):])
    probs = []
    mesa_version = found.pop("mesa.__version__")
    if mesa_version != REQUIRED_MESA:
        probs.append("mesa %s, the project requires %s (use the urgency .venv python)" % (mesa_version,
                                                                                         REQUIRED_MESA))
    probs += _origin_problems(base, found)
    return probs


# ------------------------------------------------------------------------------------------------------------ lint
def _functions(tree: ast.Module) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out["%s::%s" % (node.name, sub.name)] = sub
    return out


def _names_id(doc: str, mid: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9_.\-])%s(?![A-Za-z0-9_\-])" % re.escape(mid), doc) is not None


def lint(base: Path, mutants: dict[str, Mutant], chosen: list[str]) -> list[str]:
    issues = []
    parsed: dict[str, dict[str, ast.AST] | None] = {}
    listed: dict[tuple[str, str], set[str]] = {}
    for mid in chosen:
        for node in mutants[mid][2]:
            path, name = node.split("::", 1)
            func = name.split("[", 1)[0]
            listed.setdefault((path, func), set()).add(mid)
    for path in sorted({p for p, _ in listed}):
        try:
            parsed[path] = _functions(ast.parse((base / path).read_bytes().decode("utf-8")))
        except (OSError, SyntaxError) as exc:
            parsed[path] = None
            issues.append("%s cannot be read or parsed: %s" % (path, exc))
    for (path, func), mids in sorted(listed.items()):
        funcs = parsed.get(path)
        if funcs is None:
            continue
        fn = funcs.get(func)
        if fn is None:
            issues.append("%s::%s is listed but not defined" % (path, func))
            continue
        doc = ast.get_docstring(fn) or ""
        if "MUTANT" not in doc:
            issues.append("%s::%s has no MUTANT line in its docstring" % (path, func))
            continue
        for mid in sorted(mids):
            if not _names_id(doc, mid):
                issues.append("%s::%s is listed for %s but its docstring does not name it" % (path, func, mid))
    all_ids = sorted(mutants)
    for path, funcs in sorted(parsed.items()):
        for func, fn in sorted((funcs or {}).items()):
            if not func.split("::")[-1].startswith("test"):
                continue
            doc = ast.get_docstring(fn) or ""
            if "MUTANT" not in doc:
                continue
            named = [m for m in all_ids if _names_id(doc, m)]
            if not named:
                issues.append("%s::%s has a MUTANT line naming no known mutant id" % (path, func))
            for mid in named:
                if mid in chosen and mid not in listed.get((path, func), set()):
                    issues.append("%s::%s names %s but is not listed for it" % (path, func, mid))
    return issues


# ------------------------------------------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--work", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--timeout", type=float, default=5400.0)
    ap.add_argument("--spec", action="append", default=[])
    ap.add_argument("--copy-extra", action="append", default=[])
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--no-lint", action="store_true")
    args = ap.parse_args(argv)
    try:
        return _main(args)
    except Stop as exc:
        print("STOP: %s" % exc, file=sys.stderr)
        return 2


def _main(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    if not (repo / "agents.py").is_file() or not (repo / "tests").is_dir() or not (repo / "src_extension").is_dir():
        raise Stop("%s is not a checkout (agents.py, src_extension/, tests/)" % repo)
    mutants, origin = load_mutants(args.spec or None)
    wanted = [m for m in args.only.split(",") if m]
    unknown = [m for m in wanted if m not in mutants]
    if unknown:
        raise Stop("--only names unknown mutants: %s" % ", ".join(unknown))
    chosen = [m for m in mutants if not wanted or m in wanted]
    if args.list:
        for mid in chosen:
            desc, edits, nodes = mutants[mid]
            print("%-16s %-24s %d edit(s) %d node(s)  %s" % (mid, origin[mid], len(edits), len(nodes), desc))
        print("%d mutants" % len(chosen))
        return 0
    _check_extra(repo, args.copy_extra)
    own_work = not args.work
    work = Path(args.work).resolve() if args.work else Path(tempfile.mkdtemp(prefix="udmut_"))
    if _inside(work, repo) or _inside(repo, work):
        raise Stop("--work %s overlaps the checkout %s (the checkout is never mutated)" % (work, repo))
    work.mkdir(parents=True, exist_ok=True)
    try:
        return _check(args, repo, work, mutants, origin, chosen)
    finally:
        shutil.rmtree(work / "_base", ignore_errors=True)
        shutil.rmtree(work / "_plugin", ignore_errors=True)
        if own_work:
            shutil.rmtree(work, ignore_errors=True)


def _check(args, repo: Path, work: Path, mutants: dict[str, Mutant], origin: dict[str, str],
           chosen: list[str]) -> int:
    py = str(Path(args.python))
    base = work / "_base"
    _copy_tree(repo, base, args.copy_extra)
    # R2 m-3: bind the result to the tree it ran on - hashed in the work copy right after the copy, before anything
    tree_sha, tree_n = _tree_digest(base)
    bound = _bound_files(base, mutants, chosen)
    copy_sha = {rel: _sha256(base / rel) for rel in bound}
    spec_sha = dict(LOADED_SPECS)
    engine_sha = _sha256(Path(__file__))
    plugin = work / "_plugin"
    plugin.mkdir(parents=True, exist_ok=True)
    (plugin / "_udmut_origin.py").write_text(_PLUGIN, encoding="utf-8")
    (plugin / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    # PREFLIGHT: every chosen mutant applies (exactly-once matches), on the base copy, in memory
    pre = []
    for mid in chosen:
        for err in apply_edits(base, mutants[mid][1], write=False):
            pre.append("%s (%s): %s" % (mid, origin[mid], err))
    if pre:
        raise Stop("mutant edits do not apply to the current source:\n  " + "\n  ".join(pre))
    modules_of = {mid: sorted({m for m in (_module_name(e[0]) for e in mutants[mid][1]) if m}) for mid in chosen}
    all_modules = sorted({m for ms in modules_of.values() for m in ms})
    probs = _import_check(base, work, py, all_modules)
    if probs:
        raise Stop("import check:\n  " + "\n  ".join(probs))
    issues = [] if args.no_lint else lint(base, mutants, chosen)
    head = ["urgency Part 2 mutation check - repo %s" % repo,
            "specs: %s" % ", ".join(sorted(set(origin[m] for m in chosen))),
            "%d mutants; one pytest call per mutant, no -x, per-test outcomes from the JUnit XML; PYTHONHASHSEED=0"
            % len(chosen),
            "preflight: every edit matches exactly once; modules import from the copy: %s" % (
                ", ".join(all_modules) or "(tests only)"),
            "docstring cross-check: %s" % ("skipped (--no-lint)" if args.no_lint else
                                           "clean" if not issues else "%d ISSUE(S)" % len(issues)),
            "outcome types per test from the JUnit XML: failure / error / skipped / passed; only a test-body failure "
            "kills; an error (setup / teardown) is ERROR - the check is then not clean",
            "bound to its tree (sha256, as copied into the work copy):",
            "    tree     %s  (%d files: root *.py, src_extension/, tests/%s)" % (
                tree_sha, tree_n, ", --copy-extra" if args.copy_extra else "")]
    head += ["    file     %s  %s" % (copy_sha[rel], rel) for rel in bound]
    head += ["    spec     %s  %s" % (sha, path) for path, sha in sorted(spec_sha.items())]
    head += ["    engine   %s  %s" % (engine_sha, Path(__file__).resolve())]
    head += ["    LINT     " + x for x in issues]
    sha_record = {"tree": tree_sha, "tree_files": tree_n, "files": copy_sha, "specs": spec_sha, "engine": engine_sha,
                  "tree_rule": "sha256 over sorted '<relative posix path> <sha256>' lines of every copied file, "
                               "joined by newlines with a final newline"}

    def changed_since() -> list[str]:
        """Bound files whose checkout bytes differ from the copy now (the checkout changed during the run)."""
        out = [rel for rel in bound if not (repo / rel).is_file() or _sha256(repo / rel) != copy_sha[rel]]
        out += [path for path, sha in spec_sha.items() if not Path(path).is_file() or _sha256(Path(path)) != sha]
        return out

    if args.preflight:
        moved = changed_since()
        print("\n".join(head + ["    CHANGED DURING THE RUN (checkout != copy): " + x for x in moved]
                        + ["PREFLIGHT ONLY - no pytest call was made"]))
        return 0 if not issues else 1

    def one(mid: str | None) -> tuple[str, dict, list[str]]:
        dest = work / (mid or "_control")
        if mid is None:
            nodes = sorted({n for m in chosen for n in mutants[m][2]})
            mods = all_modules
        else:
            nodes, mods = mutants[mid][2], modules_of[mid]
        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(base, dest)
            if mid is not None:
                errs = apply_edits(dest, mutants[mid][1])
                if errs:
                    return mid, {"apply_error": errs}, nodes
            return mid or "CONTROL", _run(dest, work, py, nodes, mods, args.timeout), nodes
        except Exception as exc:  # noqa: BLE001 - an engine failure is reported, never a silent pass
            return mid or "CONTROL", {"apply_error": ["ENGINE ERROR %s: %s" % (type(exc).__name__, exc)]}, nodes
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    results = []
    t_start = time.time()
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(one, None)] + [pool.submit(one, m) for m in chosen]
        for k, fut in enumerate(cf.as_completed(futures), 1):  # progress only; the record keeps queue order
            mid, res, _ = fut.result()
            print("[%d/%d] %s done (%.0fs elapsed)" % (k, len(futures), mid, time.time() - t_start),
                  file=sys.stderr, flush=True)
        for fut in futures:
            results.append(fut.result())
    lines = list(head) + [""]
    ok = True
    per_test = 0
    n_error = 0
    record = {"repo": str(repo), "mutants": {}, "lint": issues, "sha256": sha_record}
    for mid, res, nodes in results:
        rows = []
        entry = {"nodes": {}, "secs": round(res.get("secs", 0.0), 1), "rc": res.get("rc")}
        record["mutants"][mid] = entry
        if "apply_error" in res:
            ok = False
            entry["verdict"] = "APPLY ERROR"
            lines.append("%-16s APPLY ERROR" % mid)
            lines += ["    " + e for e in res["apply_error"]]
            continue
        outside = res["outside"]
        never = [m for m, f in (res["origin"] or {}).items() if f is None]
        if res["origin"] is None and not res["timeout"]:
            outside = outside + ["the origin plugin wrote no record (pytest did not reach session end)"]
        coll = _collection_errors(res["cases"])
        if coll:
            entry["collection_errors"] = coll
        killed_all = clean_all = True
        errored = False
        why = "a listed test passes!"
        for node in nodes:
            nr = _node_result(node, res["cases"])
            n, failed, error, skipped = nr["cases"], nr["failed"], nr["error"], nr["skipped"]
            name = node.split("::", 1)[1]
            entry["nodes"][node] = nr
            types = "[%s]" % ", ".join("%d %s" % (nr["outcomes"].count(o), o) for o in OUTCOMES
                                       if o in nr["outcomes"])
            if n == 0:
                nr["outcome"] = "MISSING"
                rows.append("    MISSING  %s (no case collected%s%s)" % (
                    name, ", TIMEOUT" if res["timeout"] else "", ", collection error(s) %s" % coll if coll else ""))
                killed_all = clean_all = False
                why = "a listed test was not collected - a collection error or a wrong node id"
                continue
            if mid == "CONTROL":
                good = failed == 0 and error == 0 and skipped == 0
                nr["outcome"] = "PASS" if good else "FAIL"
                clean_all &= good
                if not good:
                    rows.append("    FAIL     %s (%d/%d cases fail, %d error, %d skipped) %s" % (
                        name, failed, n, error, skipped, types))
                    rows += ["             error: %s" % m for m in nr["error_msgs"]]
                continue
            per_test += 1
            if error:
                # R2 m-3: a setup / teardown error is never a kill, and the check is not clean
                n_error += 1
                errored = True
                killed_all = False
                nr["outcome"] = "ERROR"
                rows.append("    ERROR    %s (%d/%d cases error; not a kill) %s" % (name, error, n, types))
                rows += ["             error: %s" % m for m in nr["error_msgs"]]
                continue
            killed = failed > 0
            nr["outcome"] = "KILLED" if killed else "SURVIVED"
            killed_all &= killed
            frac = " (%d/%d cases fail)" % (failed, n) if n > 1 else ""
            exc = " by %s" % "/".join(nr["exc"]) if killed and nr["exc"] else ""
            rows.append("    %s %s%s %s%s" % ("KILLED  " if killed else "SURVIVED", name, frac, types, exc))
            if killed and any(t != "AssertionError" for t in nr["exc"]):
                rows.append("    note     %s was killed by %s, not by an AssertionError" % (
                    name, "/".join(t for t in nr["exc"] if t != "AssertionError")))
        if res["timeout"]:
            killed_all = clean_all = False
            why = "TIMEOUT - per-test outcomes incomplete"
            rows.append("    TIMEOUT after %.0fs - per-test outcomes incomplete; not a kill" % res["secs"])
        if outside:
            killed_all = clean_all = False
            why = "a mutated module was imported from outside the copy"
            rows += ["    ORIGIN   " + x for x in outside]
        if never and mid != "CONTROL":
            rows += ["    note     the mutated module %s was never imported by the listed tests" % m for m in never]
        if mid == "CONTROL":
            verdict = ("PASS (all %d listed nodes pass)" % len(nodes)) if clean_all else "FAIL (control does not pass!)"
            ok &= clean_all
            lines.append("%-16s rc=%s %s  %6.1fs" % (mid, res["rc"], verdict, res["secs"]))
        else:
            survived = any(r.startswith("    SURVIVED") for r in rows)
            if survived:
                why = "a listed test passes!"
            verdict = "KILLED (every listed test fails)" if killed_all else "NOT KILLED (%s)" % why
            if errored:  # R2 m-3: never a kill, and the check is not clean
                other = why if (survived or why != "a listed test passes!") else ""
                verdict = "ERROR (a listed test errored in setup / teardown - not a kill%s)" % (
                    "; also " + other if other else "")
            ok &= killed_all and not errored
            lines.append("%-16s rc=%s %s  %6.1fs" % (mid, res["rc"], verdict, res["secs"]))
            lines.append("    mutant: %s [%s]" % (mutants[mid][0], origin[mid]))
        entry["verdict"] = verdict
        lines.extend(rows)
        if (not (killed_all if mid != "CONTROL" else clean_all)) and res["tail"]:
            lines += ["    | " + t for t in res["tail"][-12:]]
    moved = changed_since()
    record["sha256"]["changed_during_run"] = moved
    lines.append("")
    lines += ["CHANGED DURING THE RUN (the checkout no longer matches the copy this result is bound to): " + x
              for x in moved]
    lines.append("%d (mutant, test) records; %d ERROR (setup / teardown, not a kill)" % (per_test, n_error))
    lines.append("ALL MUTANTS KILLED ON EVERY LISTED TEST, CONTROL PASSES" if ok else "MUTATION CHECK NOT CLEAN")
    if not args.no_lint:
        lines.append("DOCSTRING CROSS-CHECK CLEAN" if not issues else "DOCSTRING CROSS-CHECK: %d ISSUE(S)" % len(issues))
    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_bytes((text + "\n").encode("utf-8"))
    if args.json:
        record["clean"] = ok and not issues
        Path(args.json).write_bytes((json.dumps(record, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    return 0 if ok and not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
