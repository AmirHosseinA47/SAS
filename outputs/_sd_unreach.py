"""sysdebug Part 3: the victim `unreachable` latch, from _sd_*.json rows + .stdout.txt.

Per victim: first detection step ([Victim Detection] stdout event - the path that sets
managed_victims[v].confirmed; see memory victim-candidate-not-undetected), first step the
managed status reads 'unreachable' and its cause (eval unreachable_causes), dispatches
([Dispatch] lines) before/after the mark, and the final status. A LATCH CASE is a victim that
is marked unreachable and afterwards is alive and detected (or detected again) with no further
dispatch, or a victim marked never_detected that WAS detected before the mark.
Read-only. usage: _sd_unreach.py <queue.jsonl> [...]
"""
import json
import os
import re
import sys

REPO = r"E:\Projects\SAS"
DET = re.compile(r"\[Victim Detection\] step=(\d+) UAV-(\S+) detected (\S+) at")
DISP = re.compile(r"\[Dispatch\] FF-(\S+) assigned to (\S+) reason=(\S+)")
CAS = re.compile(r"\[Casualty\] (victim_\d+) reached by fire")


def main():
    names = []
    for q in sys.argv[1:]:
        names += [json.loads(l)["name"] for l in open(q, encoding="utf-8") if l.strip()]
    n_unr = 0
    for n in names:
        jp = os.path.join(REPO, "outputs", "_sd_%s.json" % n)
        sp = os.path.join(REPO, "outputs", "_sd_%s.stdout.txt" % n)
        if not os.path.exists(jp):
            continue
        d = json.load(open(jp, encoding="utf-8"))
        text = open(sp, encoding="utf-8").read() if os.path.exists(sp) else ""
        det = {}
        for m in DET.finditer(text):
            det.setdefault(m.group(3), int(m.group(1)))
        # dispatch lines carry no step; order them against detection lines by position
        lines = text.splitlines()
        cur_step = 0
        disp = []
        for ln in lines:
            m = DET.search(ln)
            if m:
                cur_step = int(m.group(1))
            m2 = DISP.search(ln)
            if m2:
                disp.append((cur_step, m2.group(2), m2.group(3)))
        causes = dict(x.split(":", 1) for x in (d["eval"] or {}).get("unreachable_causes", "").split(";") if ":" in x)
        first_unr = {}
        final = {}
        for t, row in enumerate(d["rows_vic"], start=1):
            for r in row:
                if r[4] == "unreachable" and r[0] not in first_unr:
                    first_unr[r[0]] = t
                final[r[0]] = r[4]
        for v, t in sorted(first_unr.items()):
            n_unr += 1
            later_det = det.get(v) is not None and det[v] > t
            dsp = [x for x in disp if x[1] == v]
            print("%-18s %-9s unreachable@%-4d cause=%-24s detected@%-5s final=%-11s dispatches=%s%s" % (
                n, v, t, causes.get(v, "?"), det.get(v), final.get(v), [(s, r) for s, _, r in dsp],
                "  <-- DETECTED AFTER MARK" if later_det else ""))
    print("victims ever unreachable:", n_unr)


if __name__ == "__main__":
    main()
