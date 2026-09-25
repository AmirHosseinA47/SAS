"""Read-only: carry legs whose (unit, victim) pair was ALREADY in _blocked_replacement_attempted
(an earlier replacement_after_blocked unassign of that same pair), i.e. legs on which a
route_blocked would have returned early and kept custody. Also approach-phase kept episodes:
status route_blocked with assigned=True and exiting=False at a step end.
"""
import collections
import json
import os

OUT_DIR = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"


def row(d, s, ff):
    rows = d.get("ff_steps") or []
    if s < 1 or s > len(rows):
        return None
    return next((r for r in rows[s - 1] if r[0] == ff), None)


def vrow(d, s, vid):
    rows = d.get("victim_steps") or []
    if s < 1 or s > len(rows):
        return None
    return next((r for r in rows[s - 1] if r[0] == vid), None)


def bind(d, s, ff):
    rows = d.get("ff_bind_steps") or []
    if s < 1 or s > len(rows):
        return None
    return next((r for r in rows[s - 1] if r[0] == ff), None)


names = sorted(n for n in os.listdir(OUT_DIR)
               if n != QUAR and n.startswith("_ffr_") and n.endswith(".json") and ".xstrace." not in n
               and not n.startswith("_ffr_xs"))
armed = {}
approach = {}
for n in names:
    with open(os.path.join(OUT_DIR, n), encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict) or "exit_starts" not in d or not d.get("ff_steps"):
        continue
    tup = (d.get("wind"), d.get("roles"), d.get("seed"))
    cls = "ON" if d.get("firefight_log") else "OFF"
    nsteps = len(d["ff_steps"])
    un = d.get("unassigns") or []
    comps = d.get("completions") or []
    for e in d.get("exit_starts") or []:
        prior = [u for u in un if u["ff"] == e["ff"] and u["vid"] == e["victim"]
                 and u["reason"] == "replacement_after_blocked" and u["step"] < e["step"]]
        if not prior:
            continue
        end = None
        for s in range(e["step"] + 1, nsteps + 1):
            r = row(d, s, e["ff"])
            if r is None or not r[4]:
                end = s
                break
        comp = next((c for c in comps if c["ff"] == e["ff"] and c["victim"] == e["victim"] and c["step"] >= e["step"]), None)
        rb = [s for s in range(e["step"], (end or nsteps) + 1) if row(d, s, e["ff"]) and row(d, s, e["ff"])[2] == "route_blocked"]
        if comp is not None and (end is None or comp["step"] <= end):
            out = "COMPLETED %d" % comp["step"]
        elif end is None:
            out = "HORIZON"
        else:
            r = row(d, end, e["ff"])
            out = "ended %d: %s" % (end, "DIED" if r and r[5] else ("status " + str(r[2] if r else None)))
        key = (tup, cls, e["ff"], e["victim"], e["step"], tuple(e["ff_pos"]))
        armed.setdefault(key, []).append((d.get("tag"), prior[-1]["step"], out, rb))
    # approach-phase kept episodes
    seen_pairs = set()
    for s in range(1, nsteps + 1):
        for r in d["ff_steps"][s - 1]:
            if r[2] == "route_blocked" and r[3] and not r[4] and not r[5]:
                b = bind(d, s, r[0])
                vid = b[1] if b else None
                if (r[0], vid) in seen_pairs:
                    continue
                seen_pairs.add((r[0], vid))
                prior = [u for u in un if u["ff"] == r[0] and u["vid"] == vid and u["reason"] == "replacement_after_blocked" and u["step"] <= s]
                later_start = next((e for e in d.get("exit_starts") or [] if e["ff"] == r[0] and e["victim"] == vid and e["step"] >= s), None)
                comp = next((c for c in comps if c["ff"] == r[0] and c["victim"] == vid and c["step"] >= s), None)
                key = (tup, cls, r[0], vid, s)
                approach.setdefault(key, []).append((d.get("tag"), [u["step"] for u in prior],
                                                      later_start["step"] if later_start else None,
                                                      comp["step"] if comp else None))

print("ARMED carry legs (pair already attempted before the pickup): %d distinct, %d file-occurrences" % (
    len(armed), sum(len(v) for v in armed.values())))
for k, v in sorted(armed.items(), key=lambda kv: str(kv[0])):
    outs = collections.Counter(x[2] for x in v)
    rbs = sorted(set(len(x[3]) for x in v))
    print("  %s %s %s %s start %d at %s | prior blocked unassign %s | outcomes %s | route_blocked steps while carrying %s | tags %s" % (
        "/".join(map(str, k[0])), k[1], k[2], k[3], k[4], k[5], sorted(set(x[1] for x in v)), dict(outs), rbs,
        ",".join(sorted(set(x[0] for x in v)))[:150]))
print()
print("APPROACH-phase route_blocked-but-still-assigned episodes (first step per pair): %d distinct, %d file-occurrences" % (
    len(approach), sum(len(v) for v in approach.values())))
c = collections.Counter()
for k, v in approach.items():
    x = v[0]
    c[("prior_attempt" if x[1] else "no_prior"), ("picked_up" if x[2] else "no_pickup"), ("completed" if x[3] else "not_completed")] += 1
for kk, vv in sorted(c.items()):
    print("  ", kk, vv)
