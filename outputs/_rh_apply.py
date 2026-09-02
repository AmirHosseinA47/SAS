"""Apply the recovery-hysteresis deletion. Binary mode, exact line ranges.

Patches in binary so line endings cannot be rewritten as a side effect (the
#9-A2 round's precedent). Both target files are pure LF and must stay pure LF.

  src_extension/execution/mode_manager.py   (1-based, against the 350-line file)
     14- 44   seven module constants
     52- 53   stable_recovery_counter / required_stable_recovery_updates
    103-108   the _update_stable_recovery_counter(...) call inside update()
    119-227   six methods (should_return_to_normal + the five it owns)
                                                       -> 148 lines, 350 -> 202

  tests/test_failsafe_planner_mode.py       (1-based, against the 126-line file)
     86       "information_sufficiency_score": 0.7,   (provably never read)
     92       the should_return_to_normal assertion    (subject being deleted)
             plus line 91's trailing blank handling is untouched
                                                       ->   2 lines, 126 -> 124

usage: _rh_apply.py [--check]
"""
from __future__ import annotations
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PLAN = [
    (os.path.join(ROOT, "src_extension", "execution", "mode_manager.py"),
     350, 202, [(14, 44), (52, 53), (103, 108), (119, 227)]),
    (os.path.join(ROOT, "tests", "test_failsafe_planner_mode.py"),
     126, 124, [(86, 86), (92, 92)]),
]

# Guard strings: the first line of each range must start with these, or we are
# patching a file that has moved under us.
EXPECT = {
    (350, 14): "_INFORMATION_REASONS = frozenset(",
    (350, 52): "        self.stable_recovery_counter = 0",
    (350, 103): "        self._update_stable_recovery_counter(",
    (350, 119): "",
    (126, 86): '        "information_sufficiency_score": 0.7,',
    (126, 92): "    assert manager.should_return_to_normal(analysis_snapshot=recovery_context) is False",
}


def main(check_only: bool) -> int:
    rc = 0
    for path, n_before, n_after, ranges in PLAN:
        raw = open(path, "rb").read()
        if b"\r\n" in raw:
            print("ABORT: %s contains CRLF; refusing to patch" % path)
            return 2
        lines = raw.split(b"\n")
        # a trailing newline yields a final empty element; keep it out of the count
        trailing = lines and lines[-1] == b""
        body = lines[:-1] if trailing else lines
        if len(body) != n_before:
            print("ABORT: %s has %d lines, expected %d" % (path, len(body), n_before))
            return 2
        for start, _end in ranges:
            want = EXPECT.get((n_before, start))
            got = body[start - 1].decode("utf-8")
            if want is not None and got != want:
                print("ABORT: %s:%d is %r, expected %r" % (path, start, got, want))
                return 2
        drop = set()
        for start, end in ranges:
            drop.update(range(start, end + 1))
        kept = [ln for i, ln in enumerate(body, 1) if i not in drop]
        if len(kept) != n_after:
            print("ABORT: %s would become %d lines, expected %d"
                  % (path, len(kept), n_after))
            return 2
        print("%-52s %d -> %d lines (-%d)  guards OK"
              % (os.path.relpath(path, ROOT), n_before, len(kept), len(drop)))
        if not check_only:
            out = b"\n".join(kept) + (b"\n" if trailing else b"")
            open(path, "wb").write(out)
    if check_only:
        print("CHECK ONLY - nothing written")
    return rc


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
