"""Flip round: compare full-suite runs by failing NAME SET, never by count alone.

dimension_report.txt:430-432 records counts that matched while the sets differed by
two; the FOV round saw the set swap while the count held at 8. So every comparison
here prints the set difference in both directions.

  python outputs/_flip_pytest_names.py LABEL=PATH [LABEL=PATH ...] [--ref LABEL]

PATH is a pytest log (-q output; UTF-8 or UTF-16) and, when a sibling .xml with the
same stem exists, its junit XML. From the log: the FAILED/ERROR lines of the short
summary and the final count line. From the XML: every testcase's outcome and first
message line. When both exist their failing sets must agree or the script says so.
The first LABEL is the reference unless --ref names another.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET


def read_text(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or raw[1:2] == b"\x00":
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def parse_log(path):
    text = read_text(path)
    failed, summary, complete = {}, None, None
    for line in text.splitlines():
        m = re.match(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$", line)
        if m:
            failed[m.group(2)] = (m.group(1), (m.group(3) or "").strip())
        if re.search(r"\d+ (passed|failed)", line) and " in " in line:
            summary = line.strip("= ").strip()
        if "FLIP_PYTEST_COMPLETE" in line or "COMPLETE rc=" in line:
            complete = line.strip()
    return failed, summary, complete


def parse_xml(path):
    outcomes, messages = {}, {}
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        parts = case.get("classname", "").split(".")
        # classname "tests.test_x" -> tests/test_x.py ; "tests.test_x.TestC" -> ::TestC
        node = "/".join(parts[:2]) + ".py"
        if len(parts) > 2:
            node += "::" + "::".join(parts[2:])
        node += "::" + case.get("name", "")
        outcome = "passed"
        for child in case:
            if child.tag in ("failure", "error"):
                outcome = "failed" if child.tag == "failure" else "error"
                messages[node] = (child.get("message") or "").splitlines()[0][:200] if child.get("message") else ""
                break
            if child.tag == "skipped":
                outcome = "skipped"
        outcomes[node] = outcome
    return outcomes, messages


def main(argv):
    ref = None
    runs = []
    it = iter(argv)
    for arg in it:
        if arg == "--ref":
            ref = next(it)
            continue
        label, _, path = arg.partition("=")
        runs.append((label, path))
    if not runs:
        print(__doc__)
        return 2
    data = {}
    for label, path in runs:
        failed, summary, complete = parse_log(path)
        xml = os.path.splitext(path)[0] + ".xml"
        entry = {"path": path, "failed": set(failed), "msgs": {k: v[1] for k, v in failed.items()},
                 "summary": summary, "complete": complete, "xml": None}
        if os.path.exists(xml):
            outcomes, messages = parse_xml(xml)
            xfail = {k for k, v in outcomes.items() if v in ("failed", "error")}
            entry["xml"] = {"n": len(outcomes), "failed": xfail, "msgs": messages,
                            "skipped": sorted(k for k, v in outcomes.items() if v == "skipped"),
                            "names": set(outcomes)}
        data[label] = entry
    ref = ref or runs[0][0]
    for label, _ in runs:
        e = data[label]
        print("=== %s  %s" % (label, e["path"]))
        print("    summary : %s" % e["summary"])
        print("    complete: %s" % e["complete"])
        print("    failing (log summary): %d" % len(e["failed"]))
        if e["xml"]:
            x = e["xml"]
            agree = "AGREE" if x["failed"] == e["failed"] else "DISAGREE log-only=%s xml-only=%s" % (
                sorted(e["failed"] - x["failed"]), sorted(x["failed"] - e["failed"]))
            print("    junit   : %d testcases, %d failing, %d skipped; log vs xml failing sets %s"
                  % (x["n"], len(x["failed"]), len(x["skipped"]), agree))
        for name in sorted(e["failed"]):
            print("      F %s" % name)
    r = data[ref]
    for label, _ in runs:
        if label == ref:
            continue
        e = data[label]
        new, gone = sorted(e["failed"] - r["failed"]), sorted(r["failed"] - e["failed"])
        same = "IDENTICAL NAME SET" if not new and not gone else "SETS DIFFER"
        print("\n--- %s vs %s: %s (counts %d vs %d)" % (label, ref, same, len(e["failed"]), len(r["failed"])))
        for name in new:
            msg = (e["xml"]["msgs"].get(name) if e["xml"] else None) or e["msgs"].get(name, "")
            print("   + NEW FAIL  %s\n       %s" % (name, msg))
        for name in gone:
            print("   - NO LONGER FAILS  %s" % name)
        for name in sorted(e["failed"] & r["failed"]):
            m_new = (e["xml"]["msgs"].get(name) if e["xml"] else None) or e["msgs"].get(name, "")
            m_ref = (r["xml"]["msgs"].get(name) if r["xml"] else None) or r["msgs"].get(name, "")
            if m_new and m_ref and m_new != m_ref:
                print("   ~ SAME NAME, DIFFERENT MESSAGE  %s\n       %s: %s\n       %s: %s"
                      % (name, ref, m_ref, label, m_new))
        if e["xml"] and r["xml"] and e["xml"]["names"] != r["xml"]["names"]:
            print("   ! COLLECTED TEST SETS DIFFER: +%s -%s" % (
                sorted(e["xml"]["names"] - r["xml"]["names"]), sorted(r["xml"]["names"] - e["xml"]["names"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
