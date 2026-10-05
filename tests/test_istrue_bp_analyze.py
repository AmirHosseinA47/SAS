"""isTrue round, the maintainer's rulings on outputs/isTrue_report.txt section 8: the measurement round's analyzer
(outputs/_bp_analyze.py, fix3b_part1.txt 19.10 (d)) implements prereg amendment 19.11's two new checks.

  19.11 (b)  a run whose head carries F-1 (MR1_TRUTHINESS_FIX, ships 1): the model's mr1_list must equal the probe's
             CORRECTED accumulation bit for bit, and the analyzer STOPS on a mismatch. Runs from heads without F-1 keep
             the literal rule (mr1_literal_ok), unchanged.
  19.11 (c)  a run that sets either isTrue switch (MR1_TRUTHINESS_FIX / NUMPY_SCALAR_FLAGS) is REFUSED by PROV.

Each test FAILS on the analyzer before the checks (verified red). The analyzer is imported by path with its own
argv; nothing in it imports the model, and every module it adds from outputs/ is removed again afterwards.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS = os.path.join(ROOT, "outputs")
F1 = "fef52103517d76b931366ed1951fbcf16ea5a410"          # isTrue F-1 (MR1_TRUTHINESS_FIX)
PRE = "f686e932751398d11b173b6adc05e880640e672d"         # main before the isTrue round (tag bayes-prep)
NOBS = 289.0


@pytest.fixture(scope="module")
def bpa():
    path = os.path.join(OUTPUTS, "_bp_analyze.py")
    saved_argv, saved_path, saved_mods = sys.argv, sys.path[:], set(sys.modules)
    sys.argv = [path]                       # the analyzer parses its own argv at import
    try:
        spec = importlib.util.spec_from_file_location("_bp_analyze_istrue_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.argv = saved_argv
        sys.path[:] = saved_path
        for name in set(sys.modules) - saved_mods:
            f = getattr(sys.modules[name], "__file__", None) or ""
            if os.path.normcase(os.path.abspath(f)).startswith(os.path.normcase(OUTPUTS) + os.sep):
                del sys.modules[name]


def _acc(steps, col, n):
    acc = [0.0] * n
    for row in steps:
        acc = [a + (float(c) / NOBS) * 1 - 0 for a, c in zip(acc, row[col])]
    return acc


# two UAVs; the literal count sees only the seeded cell (step 2), the corrected count every burning cell
STEPS = [[1, [0, 0], [0, 0]], [2, [1, 0], [1, 0]], [3, [0, 0], [3, 1]], [4, [0, 0], [2, 2]]]
CORRECTED = _acc(STEPS, 2, 2)
LITERAL = _acc(STEPS, 1, 2)


def _mr(model):
    return {"mr1_list": list(model), "mr1_steps": [list(r) for r in STEPS], "n_observations": NOBS}


# ============================================================================ 19.11 (b): the MR1 STOP
def test_19_11_b_stops_when_the_models_mr1_differs_from_the_corrected_count(bpa, monkeypatch):
    assert CORRECTED != LITERAL
    # the rule itself: at a head with F-1 the model must equal the CORRECTED accumulation, bit for bit
    ok = {"head": F1, "extra_params": {}}
    assert bpa.mr1_corrected_check(ok, _mr(CORRECTED), True) is True
    with pytest.raises(SystemExit) as stop:
        bpa.mr1_corrected_check(ok, _mr(LITERAL), True)          # the pre-fix model value at a fixed head
    assert "19.11 (b)" in str(stop.value)
    bumped = list(CORRECTED)
    bumped[1] += 1e-12                                            # bit-equal, not approximately equal
    with pytest.raises(SystemExit):
        bpa.mr1_corrected_check(ok, _mr(bumped), True)
    for broken in ({"mr1_list": list(CORRECTED), "n_observations": NOBS},          # no per-step record
                   {"mr1_steps": [list(r) for r in STEPS], "n_observations": NOBS},  # no model value
                   None):                                                          # no mr record at all
        with pytest.raises(SystemExit):
            bpa.mr1_corrected_check(ok, broken, True)
    # a head without F-1 keeps the literal rule (the bayesprep corpus): no STOP, not checked
    assert bpa.mr1_corrected_check({"head": PRE, "extra_params": {}}, _mr(LITERAL), False) is None
    # a head git cannot place: not checked when PROV refuses the run (not an analysis head) ...
    assert bpa.mr1_corrected_check({"head": "x", "extra_params": {}}, _mr(LITERAL), None) is None
    # ... but FAILS CLOSED when PROV accepts it (a git failure on the analysis head itself)
    with pytest.raises(SystemExit):
        bpa.mr1_corrected_check({"head": F1, "extra_params": {}}, _mr(CORRECTED), None, accepted=True)
    # a run that sets an isTrue switch is REFUSED by PROV (19.11 (c)), so the STOP does not fire on it
    assert bpa.mr1_corrected_check({"head": F1, "extra_params": {"MR1_TRUTHINESS_FIX": 0}}, _mr(LITERAL), True) is None

    # wired into the analyzer's MR1 digest (every digested run goes through it), with the run's OWN head
    seen = []

    def placed(h):
        seen.append(h)
        return True if h == F1 else False if h == PRE else None

    monkeypatch.setattr(bpa, "head_has_f1", placed)
    g = bpa.mr1_digest({"head": F1, "extra_params": {}}, _mr(CORRECTED), [], None)
    assert g["mr1_corrected_ok"] is True and g["mr1_literal_ok"] is False and seen[-1] == F1
    with pytest.raises(SystemExit):
        bpa.mr1_digest({"head": F1, "extra_params": {}}, _mr(LITERAL), [], None)
    with pytest.raises(SystemExit):
        bpa.mr1_digest({"head": F1, "extra_params": {}}, None, [], None)          # no MR1 record at all
    g = bpa.mr1_digest({"head": PRE, "extra_params": {}}, _mr(LITERAL), [], None)
    assert g["mr1_corrected_ok"] is None and g["mr1_literal_ok"] is True and seen[-1] == PRE   # the legacy rule
    # git cannot place the run's head: STOP if it is an analysis head PROV accepts, skipped (refused) otherwise
    head = bpa.EXPECTED_HEAD if bpa.EXPECTED_HEAD != "unknown" else "a" * 40
    monkeypatch.setattr(bpa, "EXPECTED_HEAD", head)
    with pytest.raises(SystemExit) as stop:
        bpa.mr1_digest({"head": head, "extra_params": {}}, _mr(CORRECTED), [], None)
    assert "cannot place" in str(stop.value)
    g = bpa.mr1_digest({"head": "not-an-analysis-head", "extra_params": {}}, _mr(LITERAL), [], None)
    assert g["mr1_corrected_ok"] is None


def test_19_11_b_head_placement_uses_git_history(bpa, monkeypatch):
    try:
        known = subprocess.run(["git", "-C", ROOT, "cat-file", "-e", F1 + "^{commit}"], capture_output=True).returncode
    except OSError:
        pytest.skip("git is not available")
    if known != 0:
        pytest.skip("this checkout does not hold the isTrue history")
    bpa._F1_PLACED.clear()
    real_run = bpa.subprocess.run

    def failing(cmd, *a, **kw):
        if "merge-base" in cmd:
            raise OSError("spawn failed")           # e.g. the commit charge is exhausted
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(bpa.subprocess, "run", failing)
    assert bpa.head_has_f1(F1) is None                  # git failed: unknown ...
    monkeypatch.setattr(bpa.subprocess, "run", real_run)
    assert bpa.head_has_f1(F1) is True                  # ... and not cached: the next call asks git again
    assert bpa.head_has_f1(PRE) is False
    assert bpa.head_has_f1("0" * 40) is None
    assert bpa.head_has_f1("") is None and bpa.head_has_f1(None) is None


# ============================================================================ 19.11 (c): the switch refusal
@pytest.mark.parametrize("extra", [{"MR1_TRUTHINESS_FIX": 0}, {"NUMPY_SCALAR_FLAGS": 0}, {"NUMPY_SCALAR_FLAGS": 1},
                                   {"MR1_TRUTHINESS_FIX": 1, "NUMPY_SCALAR_FLAGS": 0, "SEARCHER_TARGETING": 3}])
def test_19_11_c_refuses_a_run_that_sets_either_istrue_switch(bpa, tmp_path, monkeypatch, extra):
    # the rule: one reason per switch the run sets, whatever the value (no run may set them at all)
    reasons = bpa.istrue_switch_refusals({"extra_params": dict(extra)})
    assert sorted(r.split()[-1] for r in reasons) == sorted(k for k in extra if k in bpa.ISTRUE_SWITCHES)
    assert all("19.11 (c)" in r for r in reasons)
    assert bpa.istrue_switch_refusals({"extra_params": {"SEARCHER_TARGETING": 3}}) == []
    assert bpa.istrue_switch_refusals({}) == []
    # a switch recorded only in params (the cfv value the run applied) is refused as well
    assert bpa.istrue_switch_refusals({"extra_params": {}, "params": {"NUMPY_SCALAR_FLAGS": 0}})

    # wired into PROV: the same run is REFUSED with the 19.11 (c) reason iff it sets a switch
    e = next(iter(bpa.PROBE_E.values()))
    ex, _sd = bpa.expected_extra(e)
    path = str(tmp_path / "_sd_x.json")
    why_set, _k = bpa.prov_check({"extra_params": dict(ex, **extra)}, e, path)
    why_clean, _k = bpa.prov_check({"extra_params": dict(ex)}, e, path)
    assert any("19.11 (c)" in w for w in why_set)
    assert not any("19.11 (c)" in w for w in why_clean)

    # and into the rb shards' provenance (they record their --set in params; no file under outputs/ is touched)
    tag, rb_e = next(iter(bpa.RB_E.items()))
    for params, refused in ((dict(extra, SEARCHER_UNTUNED=1), True), ({"SEARCHER_UNTUNED": 1}, False)):
        shard = tmp_path / ("%s_%s.json" % (tag, int(refused)))
        shard.write_text(json.dumps({"tag": tag, "params": params}), encoding="utf-8")
        monkeypatch.setattr(bpa, "rb_path", lambda t, w, p=str(shard): p)
        monkeypatch.setattr(bpa, "RB_E", {tag: rb_e})
        bpa._RBPROV.clear()
        assert any("19.11 (c)" in w for w in bpa.rb_prov()[tag]) is refused
    bpa._RBPROV.clear()
