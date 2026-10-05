"""Mutation testing of the COMMITTED isTrue tests (tests/test_mr1_truthiness.py + tests/test_numpy_scalar_flags.py)
against the COMMITTED source (6904b1f8). Every mutant is a fresh copy of mut2/base (copied from the detached
E:/Projects/SAS_wt/istrue_suite checkout at 6904b1f8) with exactly one edit. The unmutated base is run first and must
pass. Nothing in any checkout is touched."""
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mut2")
BASE = ROOT + "/base"
PY = "E:/Projects/SAS/.venv/Scripts/python.exe"
UE = "src_extension/planning/utility_evaluation.py"
NL = "\r\n"
TRUTHY_LINE = "    value = plain_scalar(value)  # isTrue round F-2 (NUMPY_SCALAR_FLAGS)" + NL
TESTS = ["tests/test_mr1_truthiness.py", "tests/test_numpy_scalar_flags.py"]


def lines(*parts):
    return NL.join(parts) + NL


MUTANTS = [
    ("M1", "agents.py UAV.surrounding_states truthy branch",
     "truthy branch appends int(agent.is_burning() is True)", "agents.py", "exact",
     ("                        surrounding_states.append(int(bool(agent.is_burning())))" + NL,
      "                        surrounding_states.append(int(agent.is_burning() is True))" + NL)),
    ("M2", "utility_evaluation.safe_float", "deleted 'value = plain_scalar(value)'", UE, "exact",
     (lines("def safe_float(value: object, default: float = 0.0) -> float:", "    value = plain_scalar(value)"),
      lines("def safe_float(value: object, default: float = 0.0) -> float:"))),
    ("M3", "fail_safe_planner._is_truthy", "deleted its plain_scalar line",
     "src_extension/planning/fail_safe_planner.py", "exact",
     ("def _is_truthy(value: object) -> bool:" + NL + TRUTHY_LINE, "def _is_truthy(value: object) -> bool:" + NL)),
    ("M4", "global_mission_planner._is_truthy", "deleted its plain_scalar line",
     "src_extension/planning/global_mission_planner.py", "exact",
     ("def _is_truthy(value: object) -> bool:" + NL + TRUTHY_LINE, "def _is_truthy(value: object) -> bool:" + NL)),
    ("M5", "local_uav_path_planner._is_truthy", "deleted its plain_scalar line",
     "src_extension/planning/local_uav_path_planner.py", "exact",
     ("def _is_truthy(value: object) -> bool:" + NL + TRUTHY_LINE, "def _is_truthy(value: object) -> bool:" + NL)),
    ("M6", "rescue_planner._is_truthy", "deleted its plain_scalar line",
     "src_extension/planning/rescue_planner.py", "exact",
     ("def _is_truthy(value: object) -> bool:" + NL + TRUTHY_LINE, "def _is_truthy(value: object) -> bool:" + NL)),
    ("M7", "planner_selection._is_maintain_option",
     "'value = plain_scalar(params.get(key))' -> 'value = params.get(key)'",
     "src_extension/planning/planner_selection.py", "exact",
     ("        value = plain_scalar(params.get(key))", "        value = params.get(key)")),
]
CLOSURES = [
    ("M8", "ptruth_s in UtilityEvaluation._compute_stability_bonus",
     "    def _compute_stability_bonus(self, option: object, context: object | None = None) -> float:" + NL,
     "        def ptruth_s(*keys: str) -> bool:" + NL),
    ("M9", "ptruth_p in UtilityEvaluation._apply_confidence_and_uncertainty_adjustment",
     "    def _apply_confidence_and_uncertainty_adjustment(" + NL, "        def ptruth_p(*keys: str) -> bool:" + NL),
    ("M10", "ptruth in UtilityEvaluation._evaluate_global_mission_option",
     "    def _evaluate_global_mission_option(" + NL, "        def ptruth(*keys: str) -> bool:" + NL),
    ("M11", "ptruth in UtilityEvaluation._evaluate_rescue_option",
     "    def _evaluate_rescue_option(" + NL, "        def ptruth(*keys: str) -> bool:" + NL),
    ("M12", "ptruth in UtilityEvaluation._evaluate_communication_option",
     "    def _evaluate_communication_option(" + NL, "        def ptruth(*keys: str) -> bool:" + NL),
    ("M13", "ptruth in UtilityEvaluation._evaluate_failsafe_option",
     "    def _evaluate_failsafe_option(" + NL, "        def ptruth(*keys: str) -> bool:" + NL),
]
for mid, site, anchor, closure_def in CLOSURES:
    MUTANTS.append((mid, site, "'v = plain_scalar(params.get(key))' -> 'v = params.get(key)' in this closure only",
                    UE, "anchored",
                    (anchor, closure_def, "                v = plain_scalar(params.get(key))" + NL,
                     "                v = params.get(key)" + NL)))
BODY = lines(
    "    if isinstance(value, _NUMPY_SCALAR_TYPES) and not isinstance(value, numpy.timedelta64):",
    "        import agents as _agents  # lazy: agents is a root module (as in _check_utility_feasibility)",
    "",
    "        if _agents.numpy_scalar_flags():",
    "            try:",
    "                if isinstance(value, numpy.bool_):",
    "                    return bool(value)",
    "                if isinstance(value, numpy.integer):",
    "                    return int(value)",
    "                return float(value)",
    "            except (TypeError, ValueError, OverflowError):",
    "                return value",
    "    return value")
MUTANTS += [
    ("M14", "utility_evaluation.plain_scalar body", "body replaced by 'return value' (never converts)", UE, "exact",
     (BODY, lines("    return value"))),
    ("M15", "agents.numpy_scalar_flags", "always returns True", "agents.py", "exact",
     ('    return _fix2_switch("NUMPY_SCALAR_FLAGS")' + NL, "    return True" + NL)),
    ("M16", "agents.mr1_truthiness_fix", "always returns True", "agents.py", "exact",
     ('    return _fix2_switch("MR1_TRUTHINESS_FIX")' + NL, "    return True" + NL)),
    ("M17", "utility_evaluation.plain_scalar numpy.floating branch", "converts numpy.floating with int()", UE, "exact",
     (lines("                    return int(value)", "                return float(value)"),
      lines("                    return int(value)", "                return int(value)"))),
    ("M18", "utility_evaluation.plain_scalar numpy.integer branch", "returns a numpy.integer unchanged", UE, "exact",
     (lines("                if isinstance(value, numpy.integer):", "                    return int(value)"),
      lines("                if isinstance(value, numpy.integer):", "                    return value"))),
    ("M19", "utility_evaluation.plain_scalar timedelta64 exclusion", "exclusion removed (timedelta64 converted)",
     UE, "exact",
     ("    if isinstance(value, _NUMPY_SCALAR_TYPES) and not isinstance(value, numpy.timedelta64):" + NL,
      "    if isinstance(value, _NUMPY_SCALAR_TYPES):" + NL)),
    ("M20", "utility_evaluation.plain_scalar try / except", "try / except removed (a raising conversion raises)",
     UE, "exact",
     (lines("            try:",
            "                if isinstance(value, numpy.bool_):",
            "                    return bool(value)",
            "                if isinstance(value, numpy.integer):",
            "                    return int(value)",
            "                return float(value)",
            "            except (TypeError, ValueError, OverflowError):",
            "                return value"),
      lines("            if isinstance(value, numpy.bool_):",
            "                return bool(value)",
            "            if isinstance(value, numpy.integer):",
            "                return int(value)",
            "            return float(value)"))),
    ("M21", "utility_evaluation.plain_scalar numpy.bool_ branch", "numpy.bool_ returned unchanged", UE, "exact",
     (lines("                if isinstance(value, numpy.bool_):", "                    return bool(value)"),
      lines("                if isinstance(value, numpy.bool_):", "                    return value"))),
    ("M22", "agents.surrounding_states switch read", "truthy = True (switch ignored)", "agents.py", "exact",
     ("        truthy = mr1_truthiness_fix()" + NL, "        truthy = True" + NL)),
    ("M23", "utility_evaluation.plain_scalar switch read", "converts whatever the switch says", UE, "exact",
     ("        if _agents.numpy_scalar_flags():" + NL, "        if True:" + NL)),
]


def apply(path, kind, args):
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8")
    assert "\r\n" in text and text.count("\n") == text.count("\r\n"), path + " not uniformly CRLF"
    if kind == "exact":
        old, new = args
        n = text.count(old)
        assert n == 1, (path, n, old)
        out = text.replace(old, new, 1)
    else:
        anchor, closure_def, old, new = args
        assert text.count(anchor) == 1, (path, "anchor", text.count(anchor), anchor)
        a = text.index(anchor)
        nxt = text.find("\r\n    def ", a + len(anchor))
        seg_end = nxt if nxt != -1 else len(text)
        seg = text[a:seg_end]
        assert seg.count(closure_def) == 1, (path, "closure", seg.count(closure_def))
        c = seg.index(closure_def)
        sub = seg[c:]
        m = re.search(r"\r\n        (?! )\S", sub[len(closure_def):])
        closure = sub[: len(closure_def) + (m.start() if m else len(sub))]
        assert closure.count(old) == 1, (path, "old in closure", closure.count(old))
        assert seg.count(old) == 1, (path, "old in method segment", seg.count(old))
        new_seg = seg[:c] + closure.replace(old, new, 1) + seg[c + len(closure):]
        out = text[:a] + new_seg + text[seg_end:]
    assert out != text
    with open(path, "wb") as fh:
        fh.write(out.encode("utf-8"))
    return len(text.splitlines()) - len(out.splitlines())


def run_tests(cwd):
    env = dict(os.environ, MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([PY, "-m", "pytest"] + TESTS + ["-q", "-p", "no:cacheprovider", "-rf", "--tb=line"], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    out = p.stdout + p.stderr
    failed = sorted(set(re.findall(r"^FAILED (\S+)", out, re.M)))
    errors = sorted(set(re.findall(r"^ERROR (\S+)", out, re.M)))
    summary = [l for l in out.splitlines() if re.search(r"\d+ (passed|failed|error)", l)]
    return p.returncode, failed, errors, summary[-1] if summary else "", out


def main():
    results = []
    rc, failed, errors, summ, out = run_tests(BASE)
    print(json.dumps(dict(id="BASE", rc=rc, failing_tests=failed + errors, summary=summ)), flush=True)
    assert rc == 0 and not failed and not errors, "unmutated base does not pass"
    for mid, site, how, rel, kind, args in MUTANTS:
        dst = ROOT + "/m_" + mid
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(BASE, dst, ignore=shutil.ignore_patterns("__pycache__"))
        dropped = apply(dst + "/" + rel, kind, args)
        rc, failed, errors, summ, out = run_tests(dst)
        with open(dst + "/_pytest_out.txt", "w", encoding="utf-8") as fh:
            fh.write(out)
        res = dict(id=mid, site=site, how=how, file=rel, lines_removed=dropped, rc=rc, failing_tests=failed + errors,
                   summary=summ, survived=(rc == 0 and not failed and not errors))
        results.append(res)
        print(json.dumps(res), flush=True)
    with open(ROOT + "/_results.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    print("KILLED %d / %d" % (sum(1 for r in results if not r["survived"]), len(results)))


if __name__ == "__main__":
    main()
