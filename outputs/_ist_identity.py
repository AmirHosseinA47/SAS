"""isTrue round Part 1: the probe is record-only - harness JSON identity across a bare run and probe runs.

usage: _ist_identity.py <reference.json> <other.json> [...]

Compares every top-level field of each harness JSON with the reference's, ignoring only fields that cannot be equal
by construction: wall_s (wall time) and tag (the run label). Exit 0 iff every field of every file is equal.
"""
from __future__ import annotations

import json
import sys

IGNORED = ("wall_s", "tag")


def main() -> int:
    sys.stdout.reconfigure(newline="\n")
    paths = sys.argv[1:]
    if len(paths) < 2:
        print(__doc__)
        return 2
    with open(paths[0], encoding="utf-8") as f:
        ref = json.load(f)
    bad = 0
    for p in paths[1:]:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        keys = sorted(set(ref) | set(d))
        diff = [k for k in keys if k not in IGNORED and ref.get(k, "<absent>") != d.get(k, "<absent>")]
        same = [k for k in keys if k not in IGNORED and k not in diff]
        print("%s vs %s: %d fields equal, %d differ%s" % (p, paths[0], len(same), len(diff),
                                                       (": " + ", ".join(diff)) if diff else ""))
        print("    fire_final_digest %s | stdout_sha256 %s | eval %s" % (
            "equal" if ref.get("fire_final_digest") == d.get("fire_final_digest") else "DIFFERENT",
            "equal" if ref.get("stdout_sha256") == d.get("stdout_sha256") else "DIFFERENT",
            "equal" if ref.get("eval") == d.get("eval") else "DIFFERENT"))
        bad += 1 if diff else 0
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
