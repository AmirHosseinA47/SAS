"""Compare the fix14 matrix against fix8, fix12 and fix13.

Reuses _summarize_fix13.py's parser, terminal-status artifact rule and
per-victim accounting verbatim so the numbers stay directly comparable to the
figures already cited for fix12 and fix13. The only addition is the third
baseline and the ordering below.

WHY THE THIRD BASELINE MATTERS
------------------------------
fix14's working tree is fix12's code PLUS fix13's x-clamp change PLUS the new
target hold. So the three comparisons answer different questions:

  vs fix13  isolates the TARGET HOLD alone (fix13 already contains the
            x-clamp change, so the hold is the only delta). This is the
            single-variable A/B and the one that attributes the hold's effect.
  vs fix12  x-clamp AND hold together, i.e. the net effect of this line of
            work over the tree that is currently committed.
  vs fix8   everything since fix8, which still carries fix12's own measured
            regression. Confounded, and reported for continuity only.

fix13's code was reverted at 0bff40f; the fix13_* matrix files are retained as
the measurement of that tree, which is what makes it usable as a baseline here.
"""
from __future__ import annotations

import importlib.util
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_spec = importlib.util.spec_from_file_location(
    "_summarize_fix13", os.path.join(ROOT, "outputs", "_summarize_fix13.py")
)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

BASELINES = ("fix13", "fix12", "fix8")
NOTE = {
    "fix13": "isolates the TARGET HOLD (fix13 already has the x-clamp change)",
    "fix12": "x-clamp + hold together, over the currently committed tree",
    "fix8": "everything since fix8; carries fix12's own regression - confounded",
}


def main() -> int:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "fix14"
    lines: list = []

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        lines.append(msg)

    trees = {}
    for name in (prefix,) + BASELINES:
        trees[name] = S.parse(name)
        log("parsed %-6s %d runs" % (name, len(trees[name])))

    incomplete = [
        n for n in trees if n != prefix and len(trees[n]) != len(trees[prefix])
    ]
    if not trees[prefix]:
        # diagnostics() averages over the run set, so an empty tree would raise
        # rather than report. Mid-run this is normal: evaluate_scenarios.py
        # writes each combo's CSV block only when the combo finishes.
        log("")
        log("ABORT: no complete %s runs parsed yet. Combos write their CSV block"
            % prefix)
        log("only on completion, so this is expected while the matrix is running.")
        return 1
    if len(trees[prefix]) != 80:
        log("")
        log("WARNING: %s parsed %d runs, expected 80. Numbers are partial."
            % (prefix, len(trees[prefix])))
    if incomplete:
        log("WARNING: run-count mismatch against %s" % ", ".join(incomplete))

    log("")
    log("#" * 78)
    log("# %s headline, all three baselines" % prefix)
    log("#" * 78)
    log("")
    t = {n: S.totals(trees[n]) for n in trees}
    log("%-14s %8s %8s %8s %8s" % ("metric", "fix8", "fix12", "fix13", prefix))
    log("-" * 50)
    for key, label in (
        ("nd", "never_detected"),
        ("rescued", "rescued"),
        ("dead", "dead"),
        ("ff_deaths", "ff_deaths"),
        ("non_terminal", "non-terminal"),
    ):
        log("%-14s %8d %8d %8d %8d"
            % (label, t["fix8"][key], t["fix12"][key], t["fix13"][key], t[prefix][key]))

    for base in BASELINES:
        log("")
        log("#" * 78)
        log("# %s vs %s  -  %s" % (prefix, base, NOTE[base]))
        log("#" * 78)
        S.compare(trees[prefix], trees[base], prefix, base, log)
        # fix14's hold is gated on _coverage_mode_active, not on wind, so west
        # wind is a treated arm here rather than an untouched control. fix13's
        # default expectation of an unchanged west would be wrong for fix14.
        S.diagnostics(
            trees[prefix], trees[base], prefix, base, log,
            west_expected_unchanged=False,
        )

    # Not %s_report.txt: outputs/fix14_report.txt is the round writeup produced
    # before the matrix was started, and is kept.
    out = os.path.join(ROOT, "outputs", "%s_matrix_report.txt" % prefix)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    log("")
    log("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
