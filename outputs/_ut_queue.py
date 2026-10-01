"""untune Part 3 screen queues (outputs/untune_part1.txt 7.1 and 11). Every cell's scenario / wind / seed is read
from the reference arm's own .argv (fx3mS = set 1, fx3mS2 = set 2), as _fb3_queue.py does; runs go through
outputs/_ut_probe.py (= _fb3_probe.py unchanged + read-only untune recorders).

usage: _ut_queue.py <wave> -> writes outputs/_ut_q_<wave>.jsonl
  id     utid   set 1, ring, every switch at default + explicit SEARCHER_UNTUNED=0, CRN off -> vs fb3idg
         utidu  set 1, VICTIM_SPAWN_MODE=1, SEARCHER_UNTUNED=0, CRN off            -> vs fb3vs0
  arms   CRN on: ut0r / ut1r (ring, set 1), ut0r2 / ut1r2 (ring, set 2), ut0u / ut1u (uniform, set 1),
         ut0u2 / ut1u2 (uniform, set 2); 0 / 1 = SEARCHER_UNTUNED
  rb     utg[a-d]: the four fx3gS route_blocked shards' argv + SEARCHER_UNTUNED=1 (240 steps)
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from _fb3_queue import cells  # noqa: E402

PROBE = os.path.join(HERE, "_ut_probe.py")


def probe_line(tag, key, scen, wind, seed, sets, crn=False):
    out = os.path.join(HERE, "_sd_%s_%s.json" % (tag, key))
    argv = [PROBE] + (["--crn"] if crn else []) + ["--hazard", "--", "--scenario", scen, "--wind", wind,
                                                   "--seed", seed, "--set", "GLOBAL_PLANNER_MODE=0"]
    for s in sets:
        argv += ["--set", s]
    argv += ["--steps", "360", "--set", "BATCH_SIZE=360", "--out", out, "--tag", "%s_%s" % (tag, key)]
    return {"name": "%s_%s" % (tag, key), "argv": argv, "out": out, "cwd": REPO}


def main() -> int:
    wave = sys.argv[1]
    lines = []
    set1, set2 = cells("fx3mS"), cells("fx3mS2")
    if wave == "id":
        lines += [probe_line("utid", *c, sets=["SEARCHER_UNTUNED=0"]) for c in set1]
        lines += [probe_line("utidu", *c, sets=["VICTIM_SPAWN_MODE=1", "SEARCHER_UNTUNED=0"]) for c in set1]
    elif wave == "arms":
        for spawn, place in ((0, "r"), (1, "u")):
            for unt in (0, 1):
                sets = ["VICTIM_SPAWN_MODE=%d" % spawn, "SEARCHER_UNTUNED=%d" % unt]
                lines += [probe_line("ut%d%s" % (unt, place), *c, sets=sets, crn=True) for c in set1]
                lines += [probe_line("ut%d%s2" % (unt, place), *c, sets=sets, crn=True) for c in set2]
    elif wave == "rb":
        q = [json.loads(ln) for ln in open(os.path.join(HERE, "_fx3_q_p3all.jsonl"), encoding="utf-8")]
        for item in q:
            if not re.fullmatch(r"fx3gS[a-z]", item["name"]):
                continue
            suffix = item["name"][-1]
            tag = "utg" + suffix
            argv = list(item["argv"])
            argv[argv.index("--tag") + 1] = tag
            argv += ["--set", "SEARCHER_UNTUNED=1"]
            lines.append({"name": tag, "argv": argv, "out": item["out"].replace("fx3gS" + suffix, tag), "cwd": REPO})
        if len(lines) != 4:
            raise SystemExit("expected the 4 fx3gS shards, found %d" % len(lines))
    else:
        raise SystemExit("unknown wave %r" % wave)
    path = os.path.join(HERE, "_ut_q_%s.jsonl" % wave)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")
    print("%s: %d lines" % (path, len(lines)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
