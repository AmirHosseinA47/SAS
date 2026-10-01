"""fix3b Part 3 screen queues (outputs/fix3b_part1.txt section 9). Every cell's scenario / wind / seed is read
from the reference arm's own .argv (fx3mS = set 1, fx3mS2 = set 2), so the pairing is exact.

usage: _fb3_queue.py <wave> -> writes outputs/_fb3_q_<wave>.jsonl
  id     fb3id   set 1, every switch at default (identity vs fx3mS; the new probe with CRN off)
  arms   fb3lo/fb3bd/fb3bf (SEARCHER_TARGETING 1/2/3) sets 1 and 2 (tags ...2 for set 2), fb3rw (4) set 1,
         fb3vs0 / fb3vs3 (VICTIM_SPAWN_MODE 1 x {0, 3}) set 1
  rb     fb3g route_blocked shards (SEARCHER_TARGETING 3) = the fx3gS shards' argv + the switch
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PROBE = os.path.join(HERE, "_fb3_probe.py")


def cells(ref_tag):
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "_sd_%s_*.json.argv" % ref_tag))):
        key = os.path.basename(f)[len("_sd_%s_" % ref_tag):-len(".json.argv")]
        if not re.fullmatch(r"[ABCD]_[ENSW]", key):
            continue
        a = json.load(open(f, encoding="utf-8"))["argv"]
        sd = a[a.index("--") + 1:]
        out.append((key, sd[sd.index("--scenario") + 1], sd[sd.index("--wind") + 1], sd[sd.index("--seed") + 1]))
    if len(out) != 16:
        raise SystemExit("reference %s has %d cells, not 16" % (ref_tag, len(out)))
    return out


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
        lines += [probe_line("fb3id", *c, sets=[]) for c in set1]
    elif wave == "id2":                       # identity again at the final screen head (after the review fixes)
        lines += [probe_line("fb3idb", *c, sets=[]) for c in set1]
    elif wave == "arms":
        for tag, mode in (("fb3bf", 3), ("fb3lo", 1), ("fb3bd", 2)):
            lines += [probe_line(tag, *c, sets=["SEARCHER_TARGETING=%d" % mode]) for c in set1]
            lines += [probe_line(tag + "2", *c, sets=["SEARCHER_TARGETING=%d" % mode]) for c in set2]
        lines += [probe_line("fb3rw", *c, sets=["SEARCHER_TARGETING=4"]) for c in set1]
        lines += [probe_line("fb3vs0", *c, sets=["VICTIM_SPAWN_MODE=1"]) for c in set1]
        lines += [probe_line("fb3vs3", *c, sets=["VICTIM_SPAWN_MODE=1", "SEARCHER_TARGETING=3"]) for c in set1]
    elif wave == "rb":
        q = [json.loads(ln) for ln in open(os.path.join(HERE, "_fx3_q_p3all.jsonl"), encoding="utf-8")]
        for item in q:
            if not re.fullmatch(r"fx3gS[a-z]", item["name"]):
                continue
            suffix = item["name"][-1]
            tag = "fb3g" + suffix
            argv = list(item["argv"])
            argv[argv.index("--tag") + 1] = tag
            argv += ["--set", "SEARCHER_TARGETING=3"]
            out = item["out"].replace("fx3gS" + suffix, tag)
            lines.append({"name": tag, "argv": argv, "out": out, "cwd": REPO})
        if len(lines) != 4:
            raise SystemExit("expected the 4 fx3gS shards, found %d" % len(lines))
    else:
        raise SystemExit("unknown wave %r" % wave)
    path = os.path.join(HERE, "_fb3_q_%s.jsonl" % wave)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")
    print("%s: %d lines" % (path, len(lines)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
