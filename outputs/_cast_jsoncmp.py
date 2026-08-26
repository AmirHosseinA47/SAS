"""Field-by-field deep comparison of two _lane_matrix JSON dumps.

Provenance check: a re-run of the same combo/seeds against the same source
must reproduce every field exactly. Any difference at all means the existing
file was not produced by the source now in the tree.

    usage: _cast_jsoncmp.py <old.json> <new.json>
exit 0 = every field identical, 1 = at least one difference.
"""
from __future__ import annotations

import json
import sys


def walk(a, b, path, out):
    if type(a) is not type(b):
        out.append("%s: TYPE %s != %s" % (path, type(a).__name__, type(b).__name__))
        return
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append("%s.%s: MISSING in old (new=%r)" % (path, k, b[k]))
            elif k not in b:
                out.append("%s.%s: MISSING in new (old=%r)" % (path, k, a[k]))
            else:
                walk(a[k], b[k], "%s.%s" % (path, k), out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("%s: LEN %d != %d" % (path, len(a), len(b)))
        for i in range(min(len(a), len(b))):
            walk(a[i], b[i], "%s[%d]" % (path, i), out)
    else:
        if a != b:
            out.append("%s: %r != %r" % (path, a, b))


old = json.load(open(sys.argv[1], encoding="utf-8"))
new = json.load(open(sys.argv[2], encoding="utf-8"))

diffs: list[str] = []
walk(old, new, "root", diffs)


def leaves(o, n=0):
    if isinstance(o, dict):
        return sum(leaves(v) for v in o.values())
    if isinstance(o, list):
        return sum(leaves(v) for v in o)
    return 1


print("old: %s" % sys.argv[1])
print("new: %s" % sys.argv[2])
print("scalar fields compared: %d" % leaves(old))
if not diffs:
    print("RESULT: IDENTICAL - every field matches")
    sys.exit(0)
print("RESULT: %d DIFFERING FIELD(S)" % len(diffs))
for d in diffs[:200]:
    print("  " + d)
if len(diffs) > 200:
    print("  ... %d more" % (len(diffs) - 200))
sys.exit(1)
