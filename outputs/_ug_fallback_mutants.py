"""Ungated round: prove the pins can FAIL - every changed literal, and the re-gating.

A pin that cannot fail is not a pin. Two kinds of mutant, neither touching disk:

  LITERAL MUTANTS - for each site the ungated flip changed in agents.py (a getattr
  default, a junk/None branch, and the _exact_integer guards), compile the function
  with the PRE-FLIP behaviour put back and swap it into the agents module. The named
  pin tests must then fail. Method copied from outputs/_flip_fallback_mutants.py.

  CONSTANT MUTANTS - put the pre-flip VALUE back into common_fixed_variables (the gate
  at 1; both actions at 0; the range at 3) and require the behavioural pins to fail:
  test_shipped_default_engages_before_terminal_step_on_a_canonical_seed is the test the
  maintainer asked for to catch an accidental re-gating.

The unmutated CONTROL must pass every listed test. Tests are called directly (no
pytest runner); a real _pytest MonkeyPatch is used and undone after each call, and the
module state the file's autouse fixture would restore is snapshotted and restored here.

  .venv/Scripts/python.exe -B outputs/_ug_fallback_mutants.py
"""
import inspect
import os
import re
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("MPLBACKEND", "Agg")

import agents  # noqa: E402
import common_fixed_variables as cfv  # noqa: E402
import wildfire_model as wf  # noqa: E402
from _pytest.monkeypatch import MonkeyPatch  # noqa: E402
import test_firefighter_fire_mechanic as T  # noqa: E402

SNAP_NAMES = ("FF_FIREFIGHT_EXTINGUISH", "FF_FIREFIGHT_FIREBREAK",
              "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", "FF_FIREFIGHT_DRY_RUN",
              "FF_FIREFIGHT_MISSION_GATE", "SYSTEM_RANDOM")


def params_of(fn):
    for mark in getattr(fn, "pytestmark", []):
        if mark.name == "parametrize":
            return list(mark.args[1])
    return None


def call(test):
    """Run one test function (all its parametrize cases). -> None if it passed, else a reason."""
    fn = getattr(T, test)
    cases = params_of(fn)
    snap = {m: {n: (hasattr(m, n), getattr(m, n, None)) for n in SNAP_NAMES} for m in (cfv, wf)}
    saved_random = agents.random
    try:
        for case in (cases if cases is not None else [None]):
            mp = MonkeyPatch()
            try:
                wants_mp = "monkeypatch" in inspect.signature(fn).parameters
                args = ([mp] if wants_mp else []) + (list(case) if case is not None else [])
                fn(*args)
            except BaseException as e:  # noqa: BLE001
                return "%s%s" % (type(e).__name__, (" case=%r" % (case,)) if case is not None else "")
            finally:
                mp.undo()
        return None
    finally:
        for m, names in snap.items():
            for n, (present, v) in names.items():
                if present:
                    setattr(m, n, v)
                elif hasattr(m, n):
                    delattr(m, n)
        agents.random = saved_random


def mutate(fname, pattern, repl):
    src = inspect.getsource(getattr(agents, fname))
    new, n = re.subn(pattern, repl, src, count=1)
    if n != 1:
        raise SystemExit("PATTERN NOT FOUND %s %r" % (fname, pattern))
    ns = {}
    exec(compile(new, "mutant:" + fname, "exec"), agents.__dict__, ns)
    return ns[fname]


D1 = "test_every_switch_ships_on_and_every_fallback_is_the_shipped_value"
D2 = "test_mission_gate_ships_off_missing_is_off_and_junk_closes_it"
D3 = "test_retreat_range_only_one_and_two_suppress"
HX = "test_exact_integer_accepts_only_exact_integers_and_never_raises"
E4 = "test_shipped_default_engages_while_every_victim_is_unresolved"
E5 = "test_shipped_default_engages_before_terminal_step_on_a_canonical_seed"
E3 = "test_fireproof_depot_cells_are_never_fuel_work_or_a_target"
E3b = "test_a_burning_cell_bordering_only_the_depot_is_not_front"
ALL = [D1, D2, D3, HX, E4, E5, E3, E3b]

LITERAL = [
    # (label, function, pattern, pre-flip replacement, tests that must fail)
    ("EXTINGUISH getattr default back to 0", "ff_firefight_extinguish",
     r'"FF_FIREFIGHT_EXTINGUISH", 1\)', '"FF_FIREFIGHT_EXTINGUISH", 0)', [D1]),
    ("EXTINGUISH junk back to OFF", "ff_firefight_extinguish",
     r"if value is None:\n        return True", "if value is None:\n        return False", [D1]),
    ("FIREBREAK getattr default back to 0", "ff_firefight_firebreak",
     r'"FF_FIREFIGHT_FIREBREAK", 1\)', '"FF_FIREFIGHT_FIREBREAK", 0)', [D1]),
    ("FIREBREAK junk back to OFF", "ff_firefight_firebreak",
     r"if value is None:\n        return True", "if value is None:\n        return False", [D1]),
    ("RANGE getattr default back to the buffer", "ff_firefight_engaged_retreat_range",
     r'"FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", 1\)',
     '"FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", IDLE_RETREAT_SAFETY_BUFFER)', [D1]),
    ("RANGE junk/negative back to the buffer", "ff_firefight_engaged_retreat_range",
     r"if value is None or value < 0:\n        return 1",
     "if value is None or value < 0:\n        return IDLE_RETREAT_SAFETY_BUFFER", [D3]),
    ("GATE getattr default back to 1", "ff_firefight_mission_gate",
     r'"FF_FIREFIGHT_MISSION_GATE", 0\)', '"FF_FIREFIGHT_MISSION_GATE", 1)', [D2]),
    ("GATE junk opens it", "ff_firefight_mission_gate",
     r"if value is None:\n        return True", "if value is None:\n        return False", [D2]),
    ("_exact_integer float truncates (bare int)", "_exact_integer",
     r"return float.__int__\(raw\) if float.is_integer\(raw\) else None", "return float.__int__(raw)", [HX, D1, D2, D3]),
    ("_exact_integer generic truncates (no equality test)", "_exact_integer",
     r"return value if raw == value else None", "return value", [HX, D1, D2, D3]),
    ("_exact_integer string accepts only int literals -> float(str) truncation",
     "_exact_integer", r"return int\(str.strip\(raw\)\)", "return int(float(str.strip(raw)))", [HX, D1, D2]),
    ("_exact_integer catch-all removed (an exotic __int__ raises through)", "_exact_integer",
     r"    except Exception:\n        return None\n?$", "    except Exception:\n        raise\n", [HX]),
]

CONSTANT = [
    ("RE-GATED: MISSION_GATE back to 1", {"FF_FIREFIGHT_MISSION_GATE": 1}, [D2, E4, E5]),
    ("SWITCHED OFF: EXTINGUISH 0 and FIREBREAK 0",
     {"FF_FIREFIGHT_EXTINGUISH": 0, "FF_FIREFIGHT_FIREBREAK": 0}, [D1, E4, E5]),
    ("SUPPRESSION OFF: RANGE back to 3", {"FF_FIREFIGHT_ENGAGED_RETREAT_RANGE": 3}, [D1, E4]),
    ("FULL PRE-FLIP CONFIGURATION", {"FF_FIREFIGHT_EXTINGUISH": 0, "FF_FIREFIGHT_FIREBREAK": 0,
                                     "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE": 3,
                                     "FF_FIREFIGHT_MISSION_GATE": 1}, [D1, D2, E4, E5]),
]


def main():
    sys.stdout.reconfigure(newline="\n")
    bad = 0
    print("CONTROL (unmutated): every listed test must pass")
    for t in ALL:
        r = call(t)
        print("  %-78s %s" % (t, "pass" if r is None else "FAIL " + r))
        bad += r is not None
    print("\nLITERAL MUTANTS: each must be KILLED by every test named")
    for label, fname, pat, repl, killers in LITERAL:
        original = getattr(agents, fname)
        setattr(agents, fname, mutate(fname, pat, repl))
        try:
            res = {t: call(t) for t in killers}
        finally:
            setattr(agents, fname, original)
        killed = all(r is not None for r in res.values())
        bad += not killed
        print("  %-8s %s" % ("KILLED" if killed else "SURVIVED", label))
        for t, r in res.items():
            print("           %-72s %s" % (t, r or "PASSED (should have failed)"))
    print("\nCONSTANT MUTANTS (pre-flip values put back): each must be KILLED by every test named")
    for label, values, killers in CONSTANT:
        saved = {k: getattr(cfv, k) for k in values}
        for k, v in values.items():
            setattr(cfv, k, v)
            setattr(wf, k, v)
        try:
            res = {t: call(t) for t in killers}
        finally:
            for k, v in saved.items():
                setattr(cfv, k, v)
                setattr(wf, k, v)
        killed = all(r is not None for r in res.values())
        bad += not killed
        print("  %-8s %s" % ("KILLED" if killed else "SURVIVED", label))
        for t, r in res.items():
            print("           %-72s %s" % (t, r or "PASSED (should have failed)"))
    print("\nVERDICT: %s" % ("PASS - control passes, every mutant killed" if bad == 0 else "FAIL (%d)" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(2)
