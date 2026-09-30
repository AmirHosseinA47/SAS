"""fix3a merge check (read-only) - the maintainer's decision (iii): the shipped defaults are exactly Part 3's shipped
arm. Value identity of the merge runs against Part 3's shipped runs, and the traces of the two route_blocked losses
at the 240-step horizon (D/east 606, D/south 505) against Part 3's campaign shards fx3gS*.

usage (repo root): .venv/Scripts/python.exe outputs/_fx3m_check.py
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _fx3r_analyze as R  # noqa: E402

PAIRS = (("fx3S", "fx3mS"), ("fx3S2", "fx3mS2"), ("fx3B23", "fx3mB23"))
TRACES = (("fx3mTe606", "east", 606), ("fx3mTs505", "south", 505))


def sec_prov():
    print("=" * 100)
    print("PROVENANCE - heads and source hashes of the merge runs against this tree; fix3a switch values")
    for _, tag in PAIRS:
        runs = R.load(tag)
        heads = collections.Counter(str(d.get("head"))[:8] for d in runs.values())
        bad = 0
        for d in runs.values():
            for rel, sha in (d.get("src_sha") or {}).items():
                p = os.path.join(REPO, rel)
                if os.path.exists(p) and R.raw_sha(p) != sha:
                    bad += 1
        sw = collections.Counter()
        for d in runs.values():
            for n in R.NEW:
                sw[(n, (d.get("params") or {}).get(n))] += 1
        print("  %-8s runs %2d heads %s | src hashes differing from this tree: %d" % (tag, len(runs), dict(heads), bad))
        print("           switch values (name, value): runs %s" % sorted(sw.items()))


def sec_ident():
    print("=" * 100)
    print("VALUE IDENTITY - merge runs (HEAD) vs Part 3's shipped runs (a1373935); fields %s + mf2 sections"
          % (R.FIELDS,))
    total_same = total = 0
    for a, b in PAIRS:
        same, n, lines = R.probe_ident(a, b)
        total_same += same
        total += n
        print("  %-7s vs %-8s %2d / %2d identical (Part 3 runs %d, merge runs %d)" % (
            a, b, same, n, len(R.load(a)), len(R.load(b))))
        for ln in lines:
            print(ln)
    print("  TOTAL %d / %d" % (total_same, total))


def sec_trace():
    print("=" * 100)
    print("TRACES - the two route_blocked losses at 240 (Part 3, fx3gS vs fx3gR), the probe at 360 steps with the"
          " campaign's parameters; consistency = its statuses at step 240 reproduce the campaign's evaluation")
    for tag, w, seed in TRACES:
        f = os.path.join(HERE, "_sd_%s.json" % tag)
        d = R.load_one(f)
        camp = ref = None
        for g in sorted(glob.glob(os.path.join(HERE, "_rblatch_camp2_fx3gS*_D_%s.json" % w))):
            for e in json.load(open(g, encoding="utf-8")).get("evals") or []:
                if int(e["seed"]) == seed:
                    camp = (os.path.basename(g), e)
        for g in sorted(glob.glob(os.path.join(HERE, "_rblatch_camp2_fx3gR*_D_%s.json" % w))):
            for e in json.load(open(g, encoding="utf-8")).get("evals") or []:
                if int(e["seed"]) == seed:
                    ref = (os.path.basename(g), e)
        row240 = d["rows_vic"][239] if len(d["rows_vic"]) >= 240 else []
        st240 = collections.Counter((v[4] or v[3]) for v in row240)
        ce = camp[1] if camp else {}
        consistent = bool(camp) and st240.get("rescued", 0) == ce.get("rescued") and \
            st240.get("dead", 0) == ce.get("dead")
        print("  %s (D/%s %d) head %s terminal %s steps %s" % (tag, w, seed, str(d.get("head"))[:8],
                                                              d.get("terminal_step"), d.get("steps_done")))
        print("    campaign %s at 240: rescued %s dead %s candidate %s" % (
            camp and camp[0], ce.get("rescued"), ce.get("dead"), ce.get("candidate")))
        if ref:
            print("    reference %s at 240: rescued %s dead %s candidate %s terminal %s" % (
                ref[0], ref[1].get("rescued"), ref[1].get("dead"), ref[1].get("candidate"),
                ref[1].get("terminal_step")))
        print("    probe at 240: %s -> %s" % (dict(st240), "CONSISTENT" if consistent else "NOT CONSISTENT"))
        for v in d["rows_vic"][-1]:
            vid = v[0]
            s240 = next(((x[4] or x[3]) for x in row240 if x[0] == vid), None)
            rescued_at = next((t + 1 for t, row in enumerate(d["rows_vic"])
                               for x in row if x[0] == vid and (x[4] or x[3]) == "rescued"), None)
            print("    %s: detected %s | at 240 %s | at end %s | rescued at %s" % (
                vid, (d.get("_det") or {}).get(vid), s240, v[4] or v[3], rescued_at))


if __name__ == "__main__":
    sec_prov()
    sec_ident()
    sec_trace()
