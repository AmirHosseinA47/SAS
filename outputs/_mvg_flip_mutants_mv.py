"""MVG round THE FLIP - the flip's mutation check spec (Part 1d 1d.6.3 THE FLIP; the maintainer's flip ruling
2026-10-07: FF_APPROACH_PATH = 1, FF_RETREAT_KEEP_APPROACH = 1, FF_FIX_STRANDING_GUARD = 1). It binds the FLIPPED tree
(HEAD 980d9338 "mvg THE FLIP"), where agents.ff_approach_path() and agents.ff_retreat_keep_approach() are
`return _fix2_switch(NAME)` ("off only on an exact 0", like the guard) and common_fixed_variables ships both fixes 1.
The Part 2d check (outputs/_mvg_mutants_mv.py, record outputs/_mvg_mutants_result.txt / .json) is FROZEN and binds the
pre-flip tree; this file does not change it. Run by the round's engine (unchanged):

    python -B outputs/_mvg_mutants.py --spec outputs/_mvg_flip_mutants_mv.py --work <scratch> \
        --copy-extra outputs/_mvg_guard_diag.py --jobs 3 \
        --out outputs/_mvg_flip_mutants_result.txt --json outputs/_mvg_flip_mutants_result.json

The docstring cross-check is ON. A first run (on the flip commit 980d9338) used --no-lint, because the flip's rewritten
tests did not yet name their mutants. The orchestrator then added the MUTANT lines (the flipped T-SW-M / T-ID-M tests,
test_ma1's fl_switch_a, test_shipped_defaults), and the record in outputs/ is the re-run with the cross-check on, on the
final tree. The kill record is per test, from the JUnit XML, exactly as in Part 2d.

MUTANTS_MV = {id: (description, [(file, old, new), ...], [pytest node ids])}, the Part 2d format.

HOW THE TABLE IS BUILT (71 mutants)
  - The frozen table is read from outputs/_mvg_mutants_mv.py ONLY if its bytes have the sha256 pinned below (the
    Part 2d record's spec hash); otherwise this module raises and the engine STOPs. The bytes hashed are the bytes
    executed.
  - KEPT, 56: every frozen mutant whose edit text still matches exactly once in the flipped tree (checked before
    writing this file, and again by the engine's preflight). Description and edits are the frozen entry's, byte for
    byte. 50 keep their frozen node list; 6 have it updated to the current node ids (NODES_UPDATED below):
      id_a_off        T-ID-M renamed: test_tidm_fixes_off_and_zero_are_identical_and_equal_the_base (the fixes-off
                      identity, pinned to 0; it still names id_a_off in its docstring)
      sw_enter_a/_b   test_tswm_off_never_enters_new_code re-parametrized over the exact-0 forms: [false], [str0],
                      [zero], each named on its own (the frozen node was the whole function over zero / missing)
      g_switch_first, g_eval_off, g_eval_off_b
                      T-G6 re-parametrized (fixes "zero" / "false" x guard 1 / 0 / missing): all six cases, each
                      named on its own (the frozen node was the whole function)
  - RE-ANCHORED, 9 frozen ids -> new fl_* ids. Their frozen edit texts edited the pre-flip accessor bodies
    `return _exact_integer(getattr(cfv, NAME, 0)) == 1` and the shipped `NAME = 0` lines, which no longer exist; the
    targets (the accessors, the shipped values) do, so none is dropped. Each frozen id keeps its frozen edit in the
    frozen record; in this record an id names one edit only (an id present in both records has a byte-identical
    edit). Mapping (frozen -> flip):
      ma1_switch   -> fl_switch_a     the accessor never reads the switch (always off)
      sw_truthy_a  -> fl_truthy_a     truthiness instead of the exact rule        (sw_truthy_b  -> fl_truthy_b)
      sw_strict_a  -> fl_strict_a     compared with the integer without the exact-integer parsing
                                                                                  (sw_strict_b  -> fl_strict_b)
      sw_import_a  -> fl_import_a     read once at import time                    (sw_import_b  -> fl_import_b)
      sw_shipped_a -> fl_shipped0_a   the wrong shipped value (now 0)             (sw_shipped_b -> fl_shipped0_b)
  - NEW, 6: fl_missing_a/_b (a MISSING switch read as OFF - the guard's sw_guard_default on the fix accessors),
    fl_exact1_a/_b (on only on an exact 1, the pre-flip RULE, with a missing switch still read on - the guard's
    sw_guard_exact1), fl_revert_a/_b (the accessor reverted to its literal pre-flip body, byte for byte: the union
    of the two previous, i.e. what an accidental revert of the flip in agents.py would be).
  DROPPED: none.

NODES OF THE FLIP'S SWITCH MUTANTS. Candidate set for an accessor X (one of the two fixes): every case of T-SW-M's
five functions that concerns X (test_tswm_on_for_everything_but_an_exact_zero[<v>-X], 12;
test_tswm_off_only_on_an_exact_zero[<v>-X], 5; test_tswm_read_at_call_time_and_shipped_one;
test_tswm_missing_switches_read_on_and_the_fixes_step; test_tswm_off_never_enters_new_code[false / str0 / zero]),
tests/test_base_station.py::test_shipped_defaults, test_tidm_absent_equals_shipped_and_the_fixes_act (for the
mutants that change how a missing switch or a 1 reads - fl_missing, fl_revert, fl_switch_a; for the others the
accessor returns the control's value on both of that test's inputs, missing and 1, so it cannot fail), and for
fl_switch_a its frozen node test_ma1_barrier_board_reaches_the_victim_in_d_steps. Each mutant lists EVERY candidate
that killed it in a measurement before this file was written (scratch, informational - not a record; this check's
record is the engine's output), each parametrized case named on its own, so each must fail itself.
Candidates measured NOT to kill (not listed):
  - fl_missing_b, fl_revert_b: test_tidm_absent_equals_shipped_and_the_fixes_act passes - with (b) read off the
    absent run's digest still equals the shipped run's: fix (b) does not change T-ID-M's pinned 20-step run (fix (a)
    does: fl_missing_a / fl_revert_a / fl_switch_a are killed there). Both are killed by the T-SW-M nodes listed.
  - sw_enter_a, sw_enter_b: all six T-G6 cases pass. T-G6 traps the guard (its switch, verdict, stranding_guard,
    FAE and the ported helpers), not the fixes' pure choices, which these mutants evaluate and discard before the
    guard; their killing nodes are the three test_tswm_off_never_enters_new_code cases, which trap the pure choices.
  - every other candidate not listed under a mutant passed on it (the reading the mutant leaves unchanged).
"""

from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

FROZEN_SPEC = Path(__file__).resolve().parent / "_mvg_mutants_mv.py"
FROZEN_SPEC_SHA256 = "4d245a31aab708271fc163b4646211f048b2e357de812066109fbd3557332565"  # Part 2d record's spec hash

AG = "agents.py"
CFV = "common_fixed_variables.py"
T = "tests/test_movement_fixes.py"
TG = "tests/test_stranding_guard.py"
TB = "tests/test_base_station.py"


def _t(name: str) -> str:
    return f"{T}::{name}"


def _g(name: str) -> str:
    return f"{TG}::{name}"


def _load_frozen() -> dict:
    raw = FROZEN_SPEC.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != FROZEN_SPEC_SHA256:
        raise RuntimeError("the frozen Part 2d spec %s has sha256 %s, not the pinned %s - the flip spec is built "
                           "from the frozen table only" % (FROZEN_SPEC, sha, FROZEN_SPEC_SHA256))
    module = types.ModuleType("_mvg_flip_frozen_mutants_mv")
    module.__file__ = str(FROZEN_SPEC)
    no_pyc = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        exec(compile(raw, str(FROZEN_SPEC), "exec", dont_inherit=True), module.__dict__)  # the hashed bytes
    finally:
        sys.dont_write_bytecode = no_pyc
    return module.MUTANTS_MV


# ---- the flipped accessors and shipped values (each matches the flipped tree exactly once) ---------------------------
NAME_A, NAME_B = "FF_APPROACH_PATH", "FF_RETREAT_KEEP_APPROACH"


def _acc(name: str) -> str:
    return f"    return _fix2_switch(\"{name}\")"


_ON = "test_tswm_on_for_everything_but_an_exact_zero"
_OFF = "test_tswm_off_only_on_an_exact_zero"
_CALL_TIME = _t("test_tswm_read_at_call_time_and_shipped_one")
_MISSING_ON = _t("test_tswm_missing_switches_read_on_and_the_fixes_step")
_TIDM_ON = _t("test_tidm_absent_equals_shipped_and_the_fixes_act")
_SHIPPED = f"{TB}::test_shipped_defaults"


def _on(name: str, *ids: str) -> list[str]:
    return [_t(f"{_ON}[{i}-{name}]") for i in ids]


def _off(name: str, *ids: str) -> list[str]:
    return [_t(f"{_OFF}[{i}-{name}]") for i in ids]


def _enters(*ids: str) -> list[str]:
    return [_t(f"test_tswm_off_never_enters_new_code[{i}]") for i in ids]


_JUNK = ("2", "0.5", "str2.0", "on", "empty", "None")  # not an integer 1, read ON since the flip

# id -> (description, [(file, old, new), ...], [pytest node ids]) - THE FLIP's switch mutants (15)
FLIP_MUTANTS: dict[str, tuple[str, list[tuple[str, str, str]], list[str]]] = {
    # ------------------------------------------------------------------ fix (a) FF_APPROACH_PATH
    "fl_switch_a": (
        "(a)'s switch ignored: ff_approach_path() never reads FF_APPROACH_PATH (always off) - ma1_switch re-anchored "
        "to the flipped accessor",
        [(AG, _acc(NAME_A), "    return False")],
        [_t("test_ma1_barrier_board_reaches_the_victim_in_d_steps")]
        + _on(NAME_A, "1", "True", "1.0", "str1", "str_1_", *_JUNK, "missing")
        + [_CALL_TIME, _MISSING_ON, _TIDM_ON],
    ),
    "fl_missing_a": (
        "ff_approach_path reads a MISSING FF_APPROACH_PATH as off (getattr default 0; every present value as shipped)",
        [(AG, _acc(NAME_A), "    return _exact_integer(getattr(cfv, \"FF_APPROACH_PATH\", 0)) != 0")],
        _on(NAME_A, "missing") + [_CALL_TIME, _MISSING_ON, _TIDM_ON],
    ),
    "fl_truthy_a": (
        "ff_approach_path reads truthiness instead of the exact-0 rule: bool(getattr(cfv, \"FF_APPROACH_PATH\", 1)) "
        "(\"0\" / \" 0 \" read on, \"\" / None read off) - sw_truthy_a re-anchored",
        [(AG, _acc(NAME_A), "    return bool(getattr(cfv, \"FF_APPROACH_PATH\", 1))")],
        _on(NAME_A, "empty", "None") + _off(NAME_A, "str0", "str_0_") + [_CALL_TIME] + _enters("str0"),
    ),
    "fl_strict_a": (
        "FF_APPROACH_PATH compared with 0 without the exact-integer parsing (\"0\" and \" 0 \" read on) - sw_strict_a "
        "re-anchored",
        [(AG, _acc(NAME_A), "    return getattr(cfv, \"FF_APPROACH_PATH\", 1) != 0")],
        _off(NAME_A, "str0", "str_0_") + [_CALL_TIME] + _enters("str0"),
    ),
    "fl_exact1_a": (
        "ff_approach_path on only on an exact 1 (the pre-flip rule; a missing switch still read on)",
        [(AG, _acc(NAME_A), "    return _exact_integer(getattr(cfv, \"FF_APPROACH_PATH\", 1)) == 1")],
        _on(NAME_A, *_JUNK),
    ),
    "fl_revert_a": (
        "ff_approach_path reverted to its literal pre-flip body (on only on an exact 1, missing = off)",
        [(AG, _acc(NAME_A), "    return _exact_integer(getattr(cfv, \"FF_APPROACH_PATH\", 0)) == 1")],
        _on(NAME_A, *_JUNK, "missing") + [_CALL_TIME, _MISSING_ON, _TIDM_ON],
    ),
    "fl_import_a": (
        "FF_APPROACH_PATH read once at import time (an import-time copy, not a call-time read) - sw_import_a "
        "re-anchored",
        [(AG, "def ff_approach_path() -> bool:",
          "_FF_APPROACH_PATH_AT_IMPORT = getattr(cfv, \"FF_APPROACH_PATH\", 1)\n\n\ndef ff_approach_path() -> bool:"),
         (AG, _acc(NAME_A), "    return _exact_integer(_FF_APPROACH_PATH_AT_IMPORT) != 0")],
        _off(NAME_A, "0", "False", "0.0", "str0", "str_0_") + [_CALL_TIME] + _enters("false", "str0", "zero"),
    ),
    "fl_shipped0_a": (
        "FF_APPROACH_PATH shipped 0 - sw_shipped_a re-anchored (the wrong shipped value is now 0)",
        [(CFV, "\nFF_APPROACH_PATH = 1\n", "\nFF_APPROACH_PATH = 0\n")],
        [_CALL_TIME, _SHIPPED],
    ),
    # ------------------------------------------------------------------ fix (b) FF_RETREAT_KEEP_APPROACH
    "fl_missing_b": (
        "ff_retreat_keep_approach reads a MISSING FF_RETREAT_KEEP_APPROACH as off (getattr default 0; every present "
        "value as shipped)",
        [(AG, _acc(NAME_B), "    return _exact_integer(getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 0)) != 0")],
        _on(NAME_B, "missing") + [_CALL_TIME, _MISSING_ON],
    ),
    "fl_truthy_b": (
        "ff_retreat_keep_approach reads truthiness instead of the exact-0 rule: bool(getattr(cfv, "
        "\"FF_RETREAT_KEEP_APPROACH\", 1)) (\"0\" / \" 0 \" read on, \"\" / None read off) - sw_truthy_b re-anchored",
        [(AG, _acc(NAME_B), "    return bool(getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 1))")],
        _on(NAME_B, "empty", "None") + _off(NAME_B, "str0", "str_0_") + [_CALL_TIME] + _enters("str0"),
    ),
    "fl_strict_b": (
        "FF_RETREAT_KEEP_APPROACH compared with 0 without the exact-integer parsing (\"0\" and \" 0 \" read on) - "
        "sw_strict_b re-anchored",
        [(AG, _acc(NAME_B), "    return getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 1) != 0")],
        _off(NAME_B, "str0", "str_0_") + [_CALL_TIME] + _enters("str0"),
    ),
    "fl_exact1_b": (
        "ff_retreat_keep_approach on only on an exact 1 (the pre-flip rule; a missing switch still read on)",
        [(AG, _acc(NAME_B), "    return _exact_integer(getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 1)) == 1")],
        _on(NAME_B, *_JUNK),
    ),
    "fl_revert_b": (
        "ff_retreat_keep_approach reverted to its literal pre-flip body (on only on an exact 1, missing = off)",
        [(AG, _acc(NAME_B), "    return _exact_integer(getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 0)) == 1")],
        _on(NAME_B, *_JUNK, "missing") + [_CALL_TIME, _MISSING_ON],
    ),
    "fl_import_b": (
        "FF_RETREAT_KEEP_APPROACH read once at import time (an import-time copy, not a call-time read) - sw_import_b "
        "re-anchored",
        [(AG, "def ff_retreat_keep_approach() -> bool:",
          "_FF_RETREAT_KEEP_APPROACH_AT_IMPORT = getattr(cfv, \"FF_RETREAT_KEEP_APPROACH\", 1)\n\n\n"
          "def ff_retreat_keep_approach() -> bool:"),
         (AG, _acc(NAME_B), "    return _exact_integer(_FF_RETREAT_KEEP_APPROACH_AT_IMPORT) != 0")],
        _off(NAME_B, "0", "False", "0.0", "str0", "str_0_") + [_CALL_TIME] + _enters("false", "str0", "zero"),
    ),
    "fl_shipped0_b": (
        "FF_RETREAT_KEEP_APPROACH shipped 0 - sw_shipped_b re-anchored (the wrong shipped value is now 0)",
        [(CFV, "\nFF_RETREAT_KEEP_APPROACH = 1\n", "\nFF_RETREAT_KEEP_APPROACH = 0\n")],
        [_CALL_TIME, _SHIPPED],
    ),
}

# frozen id -> the flip id that re-anchors it (its frozen edit text no longer matches the flipped tree)
REANCHORED = {
    "ma1_switch": "fl_switch_a",
    "sw_strict_a": "fl_strict_a", "sw_import_a": "fl_import_a", "sw_shipped_a": "fl_shipped0_a",
    "sw_strict_b": "fl_strict_b", "sw_import_b": "fl_import_b", "sw_shipped_b": "fl_shipped0_b",
    "sw_truthy_a": "fl_truthy_a", "sw_truthy_b": "fl_truthy_b",
}
NEW_IDS = ("fl_missing_a", "fl_missing_b", "fl_exact1_a", "fl_exact1_b", "fl_revert_a", "fl_revert_b")

_TG6 = [_g(f"test_tg6_with_both_fixes_at_0_the_guard_is_never_evaluated[{f}-{g}]")
        for f in ("zero", "false") for g in ("1", "0", "missing")]
# kept frozen mutants (edits byte for byte) whose node list moves to the current node ids
NODES_UPDATED = {
    "id_a_off": [_t("test_tidm_fixes_off_and_zero_are_identical_and_equal_the_base")],
    "sw_enter_a": _enters("false", "str0", "zero"),
    "sw_enter_b": _enters("false", "str0", "zero"),
    "g_switch_first": list(_TG6),
    "g_eval_off": list(_TG6),
    "g_eval_off_b": list(_TG6),
}


def _build() -> dict:
    frozen = _load_frozen()
    if set(REANCHORED.values()) | set(NEW_IDS) != set(FLIP_MUTANTS) or len(FLIP_MUTANTS) != len(REANCHORED) + len(
            NEW_IDS):
        raise RuntimeError("the flip mutants are not exactly the re-anchored + the new ids")
    unknown = (set(REANCHORED) | set(NODES_UPDATED)) - set(frozen)
    if unknown or set(REANCHORED) & set(NODES_UPDATED) or set(frozen) & set(FLIP_MUTANTS):
        raise RuntimeError("REANCHORED / NODES_UPDATED do not partition the frozen ids: %s" % sorted(unknown))
    table: dict = dict(FLIP_MUTANTS)
    for mid, (desc, edits, nodes) in frozen.items():  # frozen order
        if mid in REANCHORED:
            continue
        table[mid] = (desc, [tuple(e) for e in edits], list(NODES_UPDATED.get(mid, nodes)))
    if len(table) != len(frozen) - len(REANCHORED) + len(FLIP_MUTANTS):
        raise RuntimeError("the flip table has %d mutants" % len(table))
    return table


MUTANTS_MV = _build()


if __name__ == "__main__":
    for mid, (desc, edits, nodes) in MUTANTS_MV.items():
        kind = ("new" if mid in NEW_IDS else "re-anchored" if mid in FLIP_MUTANTS
                else "kept, nodes updated" if mid in NODES_UPDATED else "kept")
        print("%-18s %-20s %d edit(s) %2d node(s)  %s" % (mid, kind, len(edits), len(nodes), desc))
    print("%d mutants" % len(MUTANTS_MV))
