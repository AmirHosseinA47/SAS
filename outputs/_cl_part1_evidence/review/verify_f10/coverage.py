"""F10 verification: how many legs would a matched-leg 'none longer' check cover?

(1) Empirical matched coverage between recorded arm pairs that differ by one
    behavioural change (key = tuple, ff, victim, pickup step, pickup cell).
(2) For uhD / ugKD (U30, 360/240): share of legs picked up AFTER the completion of
    the first leg with any excess over d (the first leg a shorter exit rule could
    change) - a proxy for the legs a mode-2 arm would leave unmatched.
Reads only named _ffr_<tag>_*.json files in outputs/ (non-recursive listdir).
"""
import json
import os
import re
import sys

OUT = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
names = [n for n in os.listdir(OUT) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json")]
PAT = re.compile(r"^_ffr_([A-Za-z0-9]+)_(east|south|west|north)_([a-z]+)_(\d+)\.json$")
runs = {}
for n in names:
    m = PAT.match(n)
    if not m:
        continue
    runs.setdefault(m.group(1), {})[(m.group(2), m.group(3), m.group(4))] = n


def load(n):
    with open(os.path.join(OUT, n), encoding="utf-8") as f:
        return json.load(f)


def legs(d):
    """(ff, victim, pickup_step, pickup_cell) -> (duration or None, excess or None)"""
    comps = sorted(d.get("completions") or [], key=lambda c: c["step"])
    out = {}
    for s in d.get("exit_starts") or []:
        key = (s["ff"], s["victim"], s["step"], tuple(s["ff_pos"]))
        c = next((c for c in comps if c["ff"] == s["ff"] and c["victim"] == s["victim"] and c["step"] >= s["step"]), None)
        if c is None:
            out[key] = (None, None, None)
            continue
        dur = c["step"] - s["step"]
        et = c.get("exit_target") or c["pos"]
        dist = abs(et[0] - s["ff_pos"][0]) + abs(et[1] - s["ff_pos"][1])
        out[key] = (dur, dur - dist, c["step"])
    return out


PAIRS = [("sfOFF", "sfON"), ("uhC", "uhD"), ("ugKC", "ugKD"), ("fmOFF", "fmEFS"), ("f2cOFF", "f2cEFS")]
print("(1) matched-leg coverage between recorded arm pairs")
for a, b in PAIRS:
    if a not in runs or b not in runs:
        continue
    tuples = sorted(set(runs[a]) & set(runs[b]))
    na = nb = nm = 0
    longer = 0
    for t in tuples:
        la, lb = legs(load(runs[a][t])), legs(load(runs[b][t]))
        na += len(la)
        nb += len(lb)
        common = set(la) & set(lb)
        nm += len(common)
    print(f"  {a:6s} vs {b:6s}: tuples {len(tuples):3d}  ctrl legs {na:4d}  feat legs {nb:4d}  matched {nm:4d}  "
          f"coverage ctrl {nm/na if na else 0:.2f} feat {nm/nb if nb else 0:.2f}")

print("(2) legs picked up after the first leg with excess>0 completes (same run)")
for tag in ("uhD", "ugKD", "uhC", "ugKC"):
    if tag not in runs:
        continue
    tot = after = runs_div = 0
    for t, n in sorted(runs[tag].items()):
        L = legs(load(n))
        items = sorted(L.items(), key=lambda kv: kv[0][2])
        first = None
        for k, (dur, exc, cstep) in items:
            if exc is not None and exc > 0:
                first = cstep
                break
        tot += len(items)
        if first is not None:
            runs_div += 1
            after += sum(1 for k, v in items if k[2] > first)
    print(f"  {tag}: runs {len(runs[tag])} legs {tot} runs-with-an-excess-leg {runs_div} "
          f"legs picked up after that leg completes {after} ({after/tot if tot else 0:.2f})")
