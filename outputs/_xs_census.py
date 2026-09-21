"""Exit-stall round, Part 1: is "zero stalls with firefighting off" true beyond U30?

Read-only census of EVERY recorded harness run in outputs/ (non-recursive listing; the
quarantine entry is skipped by name before anything is done with it) that carries the
feature-2 observers (exit_starts + completions). For each completed rescue:
  leg      = completion step - the victim's last exit_start at or before it
  distance = manhattan(exit_start ff_pos, fixed exit_target)
  stalled  = leg > distance + 5   (the definition used in ungated_horizon_report.txt)
Runs are classed by whether the fire mechanic was ACTIVE in them:
  ON   firefight_log present and non-empty (the model only creates it when
       _firefight_prepare got past its feature/eligibility tests)
  OFF  firefight_log absent or empty
Distinct legs are counted once: many tags re-run the same (wind, roles, seed) at the
same configuration, so a leg is keyed by (wind, roles, seed, class, victim, ff, start
step, completion step, start cell, exit target) - the rbgate-sample-overlap lesson.

  .venv/Scripts/python.exe -B outputs/_xs_census.py   -> outputs/_xs_census.txt
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
QUAR = "_firemech_rewound_20260914"
OUT = []


def say(s=""):
    OUT.append(str(s))
    print(s)


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def legs(d):
    out = []
    starts = d.get("exit_starts") or []
    for c in d.get("completions") or []:
        st = [e for e in starts if e.get("victim") == c.get("victim") and e.get("step", 10 ** 9) <= c.get("step", -1)]
        if not st or not c.get("exit_target") or not st[-1].get("ff_pos"):
            continue
        s = st[-1]
        out.append((c["victim"], c.get("ff"), s["step"], c["step"], tuple(s["ff_pos"]), tuple(c["exit_target"]),
                    manhattan(s["ff_pos"], c["exit_target"])))
    return out


# Matched comparisons: arms run on the SAME (wind, roles, seed) tuples, fire mechanic
# OFF first. Counted over the tuples every arm of the group has.
GROUPS = [
    ("U30 stock, 360 steps (horizon follow-up)", ["uhC", "uhD", "uhY"]),
    ("U30 + canonical/fresh stock, 240 steps (ungated Part 3)", ["ugC", "ugD", "ugY"]),
    ("U30 CRN, 240 steps (ungated Part 3)", ["ugKC", "ugKD", "ugKY"]),
    ("canonical/fresh, fire mechanic round 1", ["fmOFF", "fmEFS", "fmDRY"]),
    ("canonical/fresh, fire mechanic round 2", ["f2cOFF", "f2cEFS", "f2cDRY"]),
]


def matched(names):
    by_tag = collections.defaultdict(dict)
    want = {t for _g, tags in GROUPS for t in tags}
    for n in names:
        m = re.match(r"^_ffr_(.+?)_(east|south|west|north)_(half|def)_(\d+)\.json$", n)
        if not m or m.group(1) not in want:
            continue
        by_tag[m.group(1)][(m.group(2), m.group(3), int(m.group(4)))] = n
    say("")
    say("MATCHED COMPARISONS (same tuples in every arm of a group; fire mechanic OFF arm first)")
    for title, tags in GROUPS:
        common = set.intersection(*(set(by_tag[t]) for t in tags)) if all(by_tag[t] for t in tags) else set()
        say("  %s - %d common tuples" % (title, len(common)))
        for t in tags:
            nl = ns = 0
            lst = []
            for tup in sorted(common):
                with open(os.path.join(HERE, by_tag[t][tup]), encoding="utf-8") as f:
                    d = json.load(f)
                for vid, ff, s0, s1, p0, tgt, dist in legs(d):
                    nl += 1
                    if s1 - s0 > dist + 5:
                        ns += 1
                        lst.append("%s/%s/%d %s %d steps for %d cells (%d-%d)" % (tup[0], tup[1], tup[2], vid, s1 - s0, dist, s0, s1))
            say("    %-6s stalled %d of %d legs%s" % (t, ns, nl, "".join("\n           " + x for x in lst)))


def main():
    sys.stdout.reconfigure(newline="\n")
    names = sorted(n for n in os.listdir(HERE) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json"))
    per_tag = collections.defaultdict(lambda: [0, 0, 0])      # runs, legs, stalled
    distinct = {}                                              # key -> (stalled, tag example)
    skipped = collections.Counter()
    for n in names:
        try:
            with open(os.path.join(HERE, n), encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            skipped["unreadable"] += 1
            continue
        if not isinstance(d, dict) or "exit_starts" not in d or "completions" not in d:
            skipped["no feature-2 observers"] += 1
            continue
        cls = "ON" if d.get("firefight_log") else "OFF"
        tag = str(d.get("tag") or re.sub(r"^_ffr_|_(east|south|west|north)_.*$", "", n))
        rec = per_tag[(cls, tag)]
        rec[0] += 1
        for vid, ff, s0, s1, p0, tgt, dist in legs(d):
            stalled = (s1 - s0) > dist + 5
            rec[1] += 1
            rec[2] += stalled
            key = (d.get("wind"), d.get("roles"), d.get("seed"), cls, vid, ff, s0, s1, p0, tgt)
            if key not in distinct:
                distinct[key] = (stalled, tag, s1 - s0, dist)
    say("EXIT-LEG STALL CENSUS over every recorded _ffr_*.json in outputs/ (non-recursive)")
    say("  files skipped: %s" % dict(skipped))
    for cls in ("OFF", "ON"):
        tags = sorted(t for (c, t) in per_tag if c == cls)
        runs = sum(per_tag[(cls, t)][0] for t in tags)
        nl = sum(per_tag[(cls, t)][1] for t in tags)
        ns = sum(per_tag[(cls, t)][2] for t in tags)
        dl = [v for k, v in distinct.items() if k[3] == cls]
        ds = [v for v in dl if v[0]]
        say("")
        say("FIRE MECHANIC %s: %d runs in %d tags; %d completed legs (%d stalled); DISTINCT legs %d, stalled %d" % (
            cls, runs, len(tags), nl, ns, len(dl), len(ds)))
        stalled_keys = sorted((k for k, v in distinct.items() if k[3] == cls and v[0]), key=lambda k: (str(k[0]), str(k[1]), k[2], k[6]))
        for k in stalled_keys:
            v = distinct[k]
            say("    STALL %s/%s/%s %s %s: %d steps for %d cells (%d-%d) from %s to %s  [first seen in tag %s]" % (
                k[0], k[1], k[2], k[4], k[5], v[2], v[3], k[6], k[7], list(k[8]), list(k[9]), v[1]))
        say("  per tag (runs / legs / stalled):")
        for t in tags:
            r = per_tag[(cls, t)]
            say("    %-24s %4d %5d %3d" % (t, r[0], r[1], r[2]))
    matched(names)
    with open(os.path.join(HERE, "_xs_census.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
