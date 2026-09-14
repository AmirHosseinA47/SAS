"""Merge verification: are merged main's 8 failures the SAME failures as the flip round's?

Read-only. Compares the full suite on merged main (outputs/_merge_pytest_post.log/.xml)
with the flip round's post-flip suite (outputs/_flip2_pytest_post.log/.xml), test by
test, on two texts:
  - the junit <failure> message attribute and the junit failure body;
  - the log's FAILURES block for the test.
Each text is compared RAW and with CPython object addresses (0x...) masked, because
addresses change on every run. outputs/_flip_pytest_names.py compares only the first
200 characters of each junit message's first line, so it cannot see address-only
differences further in.

  python outputs/_merge_verify_failure_blocks.py
Exit 0 iff the failing name sets are equal and every text is equal after masking.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
NEW, REF = "_merge_pytest_post", "_flip2_pytest_post"
ADDR = re.compile(r"0x[0-9a-fA-F]+")


def junit(stem):
    out = {}
    for tc in ET.parse(os.path.join(HERE, stem + ".xml")).iter("testcase"):
        f = tc.find("failure")
        if f is None:
            f = tc.find("error")
        if f is not None:
            out["%s::%s" % (tc.get("classname"), tc.get("name"))] = (f.get("message") or "", f.text or "")
    return out


def log_blocks(stem):
    t = open(os.path.join(HERE, stem + ".log"), encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    t = t[t.index("= FAILURES ="):t.index("short test summary info")]
    parts = re.split(r"\n_{3,} (test_\w+) _{3,}\n", t)
    return {parts[i]: re.sub(r"\n=+ warnings summary.*", "", parts[i + 1], flags=re.S)
            for i in range(1, len(parts), 2)}


def main():
    jn, jr = junit(NEW), junit(REF)
    bn, br = log_blocks(NEW), log_blocks(REF)
    ok = True
    print("MERGED MAIN (%s) vs FLIP ROUND (%s)" % (NEW, REF))
    print("failing names: new %d, ref %d, sets %s" % (len(jn), len(jr), "EQUAL" if set(jn) == set(jr) else "DIFFER"))
    ok &= set(jn) == set(jr)
    print("%-100s %-22s %-22s %-22s" % ("test", "junit message", "junit body", "log FAILURES block"))
    address_only, identical, different = [], [], []
    for name in sorted(jn):
        short = name.split("::")[-1]
        cells, addr_only = [], False
        for a, b in ((jn[name][0], jr.get(name, ("", ""))[0]),
                     (jn[name][1], jr.get(name, ("", ""))[1]),
                     (bn.get(short, ""), br.get(short, ""))):
            if a == b:
                cells.append("identical")
            elif ADDR.sub("0x?", a) == ADDR.sub("0x?", b):
                cells.append("ADDRESSES ONLY")
                addr_only = True
            else:
                cells.append("DIFFERENT")
                ok = False
        if "DIFFERENT" in cells:
            different.append(name)
        elif addr_only:
            address_only.append(name)
        else:
            identical.append(name)
        print("%-100s %-22s %-22s %-22s" % (name, cells[0], cells[1], cells[2]))
    print("\nof %d failures: %d byte-identical in every text, %d differ only in masked object addresses, "
          "%d differ in content" % (len(jn), len(identical), len(address_only), len(different)))
    for label, names in (("addresses only", address_only), ("CONTENT DIFFERS", different)):
        for n in names:
            print("  %-16s %s" % (label, n))
    print("\n%s" % ("SAME FAILURES (equal after masking addresses)" if ok else "FAILURES DIFFER"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
