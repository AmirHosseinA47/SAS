"""fix3a Part 1 - the hazard geometry at searcher pocket steps (read-only; needs _fx3_probe --hazard runs).

usage: _fx3_haz.py <tag> [<cfg> <uid> <from> <to>]
  no range: one summary line per searcher pocket episode (full run): on its steps, how often the route
  was vetoed (F != R), the nearest BURNING and nearest SMOKE distance at the veto steps (min / median /
  max), how many veto steps had NO burning cell within the near range (6) - i.e. vetoed on smoke alone -
  and whether any strict hazard lay inside a depot footprint.
  with a range: the per-step view.
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _fx3_pockets as P  # noqa: E402

D = "ESWN"


def step_view(d, s, uid):
    e = d["fx3"]["ev"].get(str(s), {}).get(uid, [])
    out = {"pos": None, "F": None, "R": None, "H": None, "X": None, "edge": None, "tgt": None, "meth": None}
    for x in e:
        if x[0] == "x":
            out["pos"] = x[1]
        elif x[0] == "F":
            out["F"], out["tgt"], out["meth"] = x[2], x[1], x[3]
        elif x[0] == "R":
            out["R"] = x[3][0] if x[3] else None
        elif x[0] == "H":
            out["H"] = x[1:]
        elif x[0] == "X":
            out["X"] = x[2]
        elif x[0] == "E":
            out["edge"] = x[1]
    return out


def main():
    tag = sys.argv[1]
    if len(sys.argv) > 2:
        cfg, uid, a, b = sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
        d = json.load(open(os.path.join(HERE, "_sd_%s_%s.json" % (tag, cfg)), encoding="utf-8"))
        for s in range(a, b + 1):
            v = step_view(d, s, uid)
            h = v["H"]
            print(s, v["pos"], "tgt", v["tgt"], "F", None if v["F"] is None else D[v["F"]], v["meth"],
                  "R", None if v["R"] is None else D[v["R"]], "| fire", h[0] if h else None,
                  "smoke", h[1] if h else None, "nb", h[2] if h else None, "|", v["X"])
        return
    for f in sorted(glob.glob(os.path.join(HERE, "_sd_%s_*.json" % tag))):
        d = json.load(open(f, encoding="utf-8"))
        depot = {tuple(c) for c in d["depots"]["cells"]}
        eps, term = P.pockets(d, pre_terminal=False)
        for e in eps:
            if e["role"] != "victim_searcher":
                continue
            vet = []
            haz_in_depot = 0
            for s in range(e["start"], e["end"] + 1):
                v = step_view(d, s, e["uid"])
                if v["H"]:
                    haz_in_depot += sum(1 for c in v["H"][3] if (c[0], c[1]) in depot)
                if v["F"] is not None and v["R"] is not None and v["F"] != v["R"] and v["H"]:
                    vet.append((v["H"][0], v["H"][1]))
            fire = [a for a, _ in vet]
            smoke = [b for _, b in vet]
            smoke_only = sum(1 for a, b in vet if a > 6 >= b)

            def st(xs):
                return "%s/%s/%s" % (min(xs), statistics.median(xs), max(xs)) if xs else "-"
            print("%s %s/%s term=%s %s %d-%d len %d | vetoed %d | fire d at veto %s | smoke d %s | "
                  "veto with no fire within 6: %d | hazard cells inside a depot (near list) %d" % (
                      tag, d["scenario"], d["wind"][0].upper(), term, e["uid"], e["start"], e["end"],
                      e["len"], len(vet), st(fire), st(smoke), smoke_only, haz_in_depot))


if __name__ == "__main__":
    main()
