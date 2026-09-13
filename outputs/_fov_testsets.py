"""FOV-frame round Part 3: compare pytest FAILING NAME SETS, not counts.

This project has a recorded case of counts agreeing while sets differed, and it
recurred between the scorched round and 7f951cb (both 8, one name swapped). A
count comparison is therefore not evidence of anything; only the set is.

usage: _fov_testsets.py <pre.log> <post.log> [reference.log ...]
"""
from __future__ import annotations
import os, re, sys

FAIL = re.compile(r"^FAILED\s+(\S+)")


def names(path: str) -> set[str]:
    out = set()
    for line in open(path, encoding="utf-8", errors="replace"):
        m = FAIL.match(line.strip())
        if m:
            out.add(m.group(1).replace("tests/", "").strip())
    return out


def summary(path: str) -> str:
    last = ""
    for line in open(path, encoding="utf-8", errors="replace"):
        if re.search(r"\d+ (failed|passed)", line):
            last = line.strip()
    return last


def main() -> int:
    pre_p, post_p = sys.argv[1], sys.argv[2]
    refs = sys.argv[3:]
    pre, post = names(pre_p), names(post_p)
    bar = "=" * 78
    print(bar); print("PYTEST FAILING NAME SETS"); print(bar)
    for tag, p in (("PRE  (7f951cb)", pre_p), ("POST (patched)", post_p)):
        print("%-16s %s" % (tag, summary(p)))
        print("%-16s %s" % ("", os.path.relpath(p)))
    print("\nPRE  set (%d):" % len(pre))
    for n in sorted(pre): print("   ", n)
    print("\nPOST set (%d):" % len(post))
    for n in sorted(post): print("   ", n)

    new = post - pre
    fixed = pre - post
    print("\n" + bar); print("DELTA"); print(bar)
    print("  NEW failures   (post - pre) : %d" % len(new))
    for n in sorted(new): print("     + %s" % n)
    print("  Newly passing  (pre - post) : %d" % len(fixed))
    for n in sorted(fixed): print("     - %s" % n)
    print("  counts: pre=%d post=%d  %s" % (len(pre), len(post),
          "SETS EQUAL" if pre == post else "*** SETS DIFFER ***"))

    for r in refs:
        rn = names(r)
        print("\n  vs %s: %d names, %s"
              % (os.path.basename(r), len(rn),
                 "same set" if rn == post else "differs: +%s -%s"
                 % (sorted(post - rn), sorted(rn - post))))

    ok = not new
    print("\n" + bar)
    print("NO NEW TEST FAILURES: %s" % ("PASS" if ok else "FAIL"))
    print(bar)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
