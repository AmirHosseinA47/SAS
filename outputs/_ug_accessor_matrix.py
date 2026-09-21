"""Ungated-firefighting round, Part 1: what every FF_FIREFIGHT_* accessor returns
for an edge-value matrix, measured on the live tree. READ-ONLY: values are set on the
common_fixed_variables MODULE in this process only; nothing on disk changes.

`--set NAME=v` reaches an accessor through outputs/_ffr_harness._parse_value, which
yields bool / None / int / float / str only; Decimal and Fraction are reachable only
through a direct apply_scenario_config call and are listed for completeness.

  .venv/Scripts/python.exe -B outputs/_ug_accessor_matrix.py [--proposed]

--proposed also evaluates the Part-1 PROPOSED accessors (defined below, not in the
tree) so the design table in outputs/ungated_part1.txt is measured, not hand-written.
"""
import math
import os
import sys
from decimal import Decimal
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("MPLBACKEND", "Agg")

import agents  # noqa: E402
import common_fixed_variables as cfv  # noqa: E402

MISSING = object()
VALUES = [MISSING, None, "off", "", 0, 0.0, "0", False, 1, 1.0, "1", True, -1, -1.0,
          0.5, -0.5, 2, 2.5, 3, 7, "0.5", "2.0", float("inf"), float("nan"),
          Decimal("0.5"), Fraction(1, 2), Decimal("0")]
NAMES = {
    "EXTINGUISH": ("FF_FIREFIGHT_EXTINGUISH", "ff_firefight_extinguish"),
    "FIREBREAK": ("FF_FIREFIGHT_FIREBREAK", "ff_firefight_firebreak"),
    "RANGE": ("FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", "ff_firefight_engaged_retreat_range"),
    "GATE": ("FF_FIREFIGHT_MISSION_GATE", "ff_firefight_mission_gate"),
    "DRY": ("FF_FIREFIGHT_DRY_RUN", "ff_firefight_dry_run"),
}
BUFFER = agents.IDLE_RETREAT_SAFETY_BUFFER


# ---- PROPOSED (Part 1 design, section 3). Not in the tree. ----------------------
def _exact_integer(raw):
    """raw as an int iff it denotes an exact integer; else None. Never raises."""
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw) if raw.is_integer() else None      # inf / nan -> None
    if isinstance(raw, str):
        try:
            return int(raw.strip())                        # "0.5", "off", "" -> None
        except ValueError:
            return None
    try:
        value = int(raw)                                   # Decimal, Fraction, numpy ...
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        return value if raw == value else None
    except Exception:
        return None


def p_switch(name, shipped):
    def acc():
        v = _exact_integer(getattr(cfv, name, shipped))
        return bool(shipped) if v is None else v != 0
    return acc


def p_range():
    raw = getattr(cfv, "FF_FIREFIGHT_ENGAGED_RETREAT_RANGE", 1)
    v = _exact_integer(raw)
    if v is None or v < 0:
        return 1
    if v == 0:
        return BUFFER
    return v if v < BUFFER else BUFFER


def p_gate():
    raw = getattr(cfv, "FF_FIREFIGHT_MISSION_GATE", 0)
    v = _exact_integer(raw)
    return True if v is None else v != 0


PROPOSED = {
    "EXTINGUISH": p_switch("FF_FIREFIGHT_EXTINGUISH", 1),
    "FIREBREAK": p_switch("FF_FIREFIGHT_FIREBREAK", 1),
    "RANGE": p_range,
    "GATE": p_gate,
}


def show(v):
    if v is MISSING:
        return "<missing>"
    return "%s(%r)" % (type(v).__name__, v)


def evaluate(fn, attr, v):
    saved = getattr(cfv, attr)
    try:
        if v is MISSING:
            delattr(cfv, attr)
        else:
            setattr(cfv, attr, v)
        try:
            return repr(fn())
        except Exception as e:  # noqa: BLE001
            return "RAISES " + type(e).__name__
    finally:
        setattr(cfv, attr, saved)


def main():
    sys.stdout.reconfigure(newline="\n")
    proposed = "--proposed" in sys.argv
    print("ACCESSOR MATRIX  live tree  shipped: %s" % ", ".join(
        "%s=%r" % (k, getattr(cfv, a)) for k, (a, _f) in NAMES.items()))
    for key, (attr, fname) in NAMES.items():
        fn = getattr(agents, fname)
        print("\n%s  (%s)  current%s" % (key, fname, "  |  proposed" if proposed and key in PROPOSED else ""))
        for v in VALUES:
            cur = evaluate(fn, attr, v)
            row = "  %-22s %-18s" % (show(v), cur)
            if proposed and key in PROPOSED:
                row += " | %s" % evaluate(PROPOSED[key], attr, v)
            print(row)


if __name__ == "__main__":
    main()
