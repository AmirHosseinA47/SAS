"""Count how open carries end, per tag, from recorded _ffr_<tag>_*.json (read-only).

Non-recursive: glob only top-level files in outputs/ matching _ffr_<tag>_<wind>_<half|def>_<seed>.json.
"""
import glob
import json
import os
import re
import sys
from collections import Counter

OUT = r"E:\Projects\SAS\outputs"
PAT = re.compile(r"^_ffr_(?P<tag>[A-Za-z0-9]+)_(?P<wind>[a-z]+)_(?P<cls>half|def)_(?P<seed>\d+)\.json$")


def ends_for(path):
    d = json.load(open(path, encoding="utf-8"))
    ev = []
    for e in d.get("exit_starts") or []:
        ev.append((int(e["step"]), 0, "start", e["ff"], e.get("victim")))
    for c in d.get("completions") or []:
        ev.append((int(c["step"]), 1, "complete", c["ff"], c.get("victim")))
    for u in d.get("unassigns") or []:
        ev.append((int(u["step"]), 1, "unassign:" + str(u.get("reason")), u["ff"], u.get("vid")))
    ev.sort(key=lambda t: (t[0], t[1]))
    open_carry = {}
    out = []
    for step, _, kind, ff, vid in ev:
        if kind == "start":
            open_carry[ff] = (step, vid)
            continue
        if ff in open_carry:
            s0, v0 = open_carry[ff]
            if kind == "complete" or kind.startswith("unassign"):
                out.append((kind, ff, v0, s0, step, vid))
                del open_carry[ff]
    for ff, (s0, v0) in open_carry.items():
        out.append(("horizon", ff, v0, s0, None, None))
    return d, out


def main(tags):
    for tag in tags:
        files = [f for f in sorted(os.listdir(OUT)) if (m := PAT.match(f)) and m.group("tag") == tag]
        cnt = Counter()
        events = []
        steps = Counter()
        for f in files:
            d, out = ends_for(os.path.join(OUT, f))
            steps[d.get("steps")] += 1
            for kind, ff, v0, s0, s1, vid in out:
                cnt[kind] += 1
                if kind != "complete":
                    events.append((f, kind, ff, v0, s0, s1))
        print(f"== {tag}: {len(files)} files, steps={dict(steps)}")
        for k, v in sorted(cnt.items()):
            print(f"   {k}: {v}")
        for e in events:
            print("     ", e)


if __name__ == "__main__":
    main(sys.argv[1:])
