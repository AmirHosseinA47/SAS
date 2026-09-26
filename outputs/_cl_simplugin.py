"""Carrying-leg round, Part 2: run the test suite with the FF_EXIT_LEG_* switches ON
WITHOUT editing source (spec outputs/_cl_tooling_spec.txt section K).

Loaded as a pytest plugin:  python -B -m pytest tests -p outputs._cl_simplugin
  CL_SIM="" or "0"   patch nothing. The control for this plugin's own early import.
  CL_SIM="FF_EXIT_LEG_MODE=2,FF_EXIT_LEG_HOLD=1,FF_EXIT_LEG_SERVED=1"
                     a comma list of NAME=VALUE, set on the common_fixed_variables
                     MODULE at plugin import. -p plugins import before collection, so
                     every test module sees the values exactly as if the source said
                     so (the star-import copies in agents / wildfire_model included,
                     unless something preloaded them - printed below). A test's
                     monkeypatch.setattr restores to the patched value, as it would
                     after a real source change. The three accessors
                     agents.ff_exit_leg_mode/hold/served() read `cfv.<NAME>` at call
                     time, and they are the only readers in agents.py and
                     wildfire_model.py (checked at 2d5c292).
  Allowed: FF_EXIT_LEG_MODE 0/1/2, FF_EXIT_LEG_HOLD 0/1, FF_EXIT_LEG_SERVED 0/1, each
  name at most once, plain decimal integers, each item matched WHOLE (a trailing
  newline, CR or space is refused). SERVED=2 is REFUSED (maintainer D-1: rung 2 is
  not built; the accessor would silently map it to 1). A non-empty list whose values
  are all 0 is REFUSED too: it switches nothing on, so it is p0, not a sim. Anything
  else (unknown name, junk value, duplicate, empty item) raises SystemExit at import,
  so the pytest process stops before collection instead of running a mislabelled
  suite. The label-to-list mapping (SIMNAME) is enforced by outputs/_cl_pytest.sh.

The terminal summary prints the cfv values, the three ACCESSOR values, the
star-import copies, and a CHECK line: "CLSIM END CHECK OK" when the cfv values and
the accessor values at the end of the session are the ones set at import (so no test
leaked a change), else "CLSIM END CHECK MISMATCH ...". The pytest exit code is left
alone; outputs/_cl_pytest.sh records the CHECK result on its COMPLETE line.

Valid only because no test reloads a module, spawns a subprocess or ships a
conftest (re-checked 2026-09-26 on branch carryleg at 2d5c292: tests/ has no
conftest.py and no file matches reload( / subprocess / os.system / Popen; the repo
root has no conftest.py / pytest.ini / pyproject.toml / setup.cfg / tox.ini).
The agents.py accessor FALLBACKS (missing attribute -> shipped 0, junk -> 1/True/1)
are NOT simulated; they are source. With the constant present on the module a
fallback is only reached by a test that deletes or junks the attribute, i.e. by
exactly the deliberate-pin tests.
Copied from outputs/_ug_simplugin.py (ungated round), constants and parsing swapped.
"""
import os
import re
import sys

import common_fixed_variables as cfv

SWITCHES = ("FF_EXIT_LEG_MODE", "FF_EXIT_LEG_HOLD", "FF_EXIT_LEG_SERVED")
ALLOWED = {
    "FF_EXIT_LEG_MODE": (0, 1, 2),
    "FF_EXIT_LEG_HOLD": (0, 1),
    "FF_EXIT_LEG_SERVED": (0, 1),
}
# Printed for context only, never patched.
UNCHANGED = (
    "FF_FIREFIGHT_EXTINGUISH", "FF_FIREFIGHT_FIREBREAK",
    "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", "FF_FIREFIGHT_MISSION_GATE",
    "FF_FIREFIGHT_DRY_RUN",
    "BASE_STATION_MODE", "BASE_STATION_FIREPROOF", "BASE_STATION_SPAWN_FIREFIGHTERS",
    "VICTIM_SEARCHER_HAZARD_GATE_BOUNDS_FIX", "VICTIM_SEARCHER_HAZARD_RETREAT_RANGE",
)
# Matched with fullmatch, never match/$: "$" also matches before a final "\n", which let
# 'FF_EXIT_LEG_MODE=2\n' through (review finding 2).
_ITEM = re.compile(r"(FF_EXIT_LEG_[A-Z]+)=(0|[1-9][0-9]*)")


def _parse(raw):
    """CL_SIM -> tuple of (name, int). Loud on anything outside the contract."""
    if raw in ("", "0"):
        return ()
    out = []
    seen = set()
    for item in raw.split(","):
        m = _ITEM.fullmatch(item)
        if m is None:
            raise SystemExit(
                "CLSIM REFUSED: item %r of CL_SIM=%r is not NAME=INTEGER "
                "(no spaces, no empty items)" % (item, raw))
        name, value = m.group(1), int(m.group(2))
        if name not in ALLOWED:
            raise SystemExit(
                "CLSIM REFUSED: %s is not one of %s" % (name, ", ".join(SWITCHES)))
        if name in seen:
            raise SystemExit("CLSIM REFUSED: %s given twice in CL_SIM=%r" % (name, raw))
        if value not in ALLOWED[name]:
            extra = " (D-1: SERVED rung 2 is not built)" if name == "FF_EXIT_LEG_SERVED" else ""
            raise SystemExit(
                "CLSIM REFUSED: %s=%d not in %s%s" % (name, value, ALLOWED[name], extra))
        seen.add(name)
        out.append((name, value))
    return tuple(out)


RAW = os.environ.get("CL_SIM", "")
PATCH = _parse(RAW)
SIM = bool(PATCH)
# A list that turns nothing on is a control, not a sim; it must run as p0 (CL_SIM=0)
# so the log does not say sim=1 over an all-0 tree (review finding 3).
if SIM and all(_v == 0 for _n, _v in PATCH):
    raise SystemExit(
        "CLSIM REFUSED: CL_SIM=%r turns nothing on; that is p0 (CL_SIM=0)" % RAW)

_missing = [n for n in SWITCHES if not hasattr(cfv, n)]
if _missing:
    raise SystemExit(
        "CLSIM REFUSED: %s has no %s - not a carryleg checkout"
        % (cfv.__file__, ", ".join(_missing)))

PRELOADED = sorted(m for m in ("wildfire_model", "agents") if m in sys.modules)

for _name, _value in PATCH:
    setattr(cfv, _name, _value)

# What the session must still see at the end: the switch values right after patching.
EXPECTED_CFV = {n: getattr(cfv, n) for n in SWITCHES}
for _name, _value in EXPECTED_CFV.items():
    if type(_value) is not int or _value not in ALLOWED[_name]:
        raise SystemExit(
            "CLSIM REFUSED: cfv.%s=%r at plugin import is not an int in %s"
            % (_name, _value, ALLOWED[_name]))


def _expected_accessors():
    """What agents.ff_exit_leg_*() must return for EXPECTED_CFV (every value here is an
    exact integer inside the allowed range, so the accessor returns it directly)."""
    return (EXPECTED_CFV["FF_EXIT_LEG_MODE"],
            EXPECTED_CFV["FF_EXIT_LEG_HOLD"] != 0,
            EXPECTED_CFV["FF_EXIT_LEG_SERVED"])


def _snapshot(module, names):
    return " ".join("%s=%r" % (n, getattr(module, n, "<absent>")) for n in names)


print("CLSIM PLUGIN sim=%d CL_SIM=%r patch=%s preloaded=%s cfv=%s | %s | %s" % (
    int(SIM), RAW, ",".join("%s=%d" % p for p in PATCH) or "-", PRELOADED,
    cfv.__file__, _snapshot(cfv, SWITCHES), _snapshot(cfv, UNCHANGED)), flush=True)


def pytest_terminal_summary(terminalreporter):
    """After every test: prove the patch was still live at the end of the session."""
    tr = terminalreporter
    tr.write_line("CLSIM END sim=%d CL_SIM=%r" % (int(SIM), RAW))
    tr.write_line("CLSIM END cfv | " + _snapshot(cfv, SWITCHES) + " | "
                  + _snapshot(cfv, UNCHANGED))
    problems = []
    for n in SWITCHES:
        now = getattr(cfv, n, "<absent>")
        if now != EXPECTED_CFV[n] or type(now) is not type(EXPECTED_CFV[n]):
            problems.append("cfv.%s=%r expected %r" % (n, now, EXPECTED_CFV[n]))
    agents = sys.modules.get("agents")
    loaded_by = "tests"
    if agents is None:
        # No selected test imported agents; importing it now (after every test) cannot
        # change any outcome, and the accessor line must always print.
        import agents  # noqa: F401  (local import on purpose)
        loaded_by = "plugin_at_summary"
    got = (agents.ff_exit_leg_mode(), agents.ff_exit_leg_hold(),
           agents.ff_exit_leg_served())
    tr.write_line("CLSIM END accessors mode=%r hold=%r served=%r (agents loaded by %s)"
                  % (got[0], got[1], got[2], loaded_by))
    want = _expected_accessors()
    for label, g, w in zip(("mode", "hold", "served"), got, want):
        if g != w or type(g) is not type(w):
            problems.append("%s()=%r expected %r" % (label, g, w))
    wf = sys.modules.get("wildfire_model")
    tr.write_line("CLSIM END star agents | " + _snapshot(agents, SWITCHES))
    if wf is not None:
        tr.write_line("CLSIM END star wildfire_model | " + _snapshot(wf, SWITCHES))
    if problems:
        tr.write_line("CLSIM END CHECK MISMATCH " + "; ".join(problems))
    else:
        tr.write_line("CLSIM END CHECK OK")
