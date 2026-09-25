"""Read-only scan of EVERY recorded _ffr_*.json in outputs/ (non-recursive listing, the
quarantine name skipped before anything is done with it).

(c) carriers whose ff_steps row says exiting=True AND status=route_blocked at the end of a
    step (custody kept while blocked): what happened to them.
(d) carrier drops (an unassign of a unit that was exiting at the end of the previous step)
    and every replacement assignment for that victim afterwards: did it reach / rescue?
"""
import collections
import json
import os
import re
import sys

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


def md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def main():
    names = sorted(n for n in os.listdir(OUT_DIR)
                   if n != QUAR and n.startswith("_ffr_") and n.endswith(".json") and ".xstrace." not in n)
    stats = collections.Counter()
    kept = []        # (c)
    drops = []       # (d)
    for n in names:
        try:
            with open(os.path.join(OUT_DIR, n), encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            stats["unreadable"] += 1
            continue
        if not isinstance(d, dict) or not d.get("ff_steps"):
            stats["no ff_steps"] += 1
            continue
        stats["files"] += 1
        has_f2 = "exit_starts" in d and "completions" in d
        stats["files_f2"] += has_f2
        if not has_f2:
            continue
        tup = (d.get("wind"), d.get("roles"), d.get("seed"))
        cls = "ON" if d.get("firefight_log") else "OFF"
        nsteps = len(d["ff_steps"])
        comps = d.get("completions") or []
        starts = d.get("exit_starts") or []
        unassigns = d.get("unassigns") or []
        assigns = d.get("assigns") or []
        # ---- (c) exiting and route_blocked at a step end
        runs = collections.defaultdict(list)
        for s in range(1, nsteps + 1):
            for r in d["ff_steps"][s - 1]:
                if r[4] and r[2] == "route_blocked" and not r[5]:
                    runs[r[0]].append(s)
        for ff, steps in runs.items():
            # group into contiguous-ish episodes per carry leg
            leg_start = max((e["step"] for e in starts if e["ff"] == ff and e["step"] <= steps[0]), default=None)
            vid = next((e["victim"] for e in starts if e["ff"] == ff and e["step"] == leg_start), None)
            # outcome of that leg
            end = None
            for s in range(steps[0], nsteps + 1):
                r = row(d, s, ff)
                if r is None or not r[4]:
                    end = s
                    break
            comp = next((c for c in comps if c["ff"] == ff and c["victim"] == vid and c["step"] >= steps[0]), None)
            rend = row(d, end, ff) if end else None
            if comp is not None and (end is None or comp["step"] <= end):
                outcome = "COMPLETED at %d at %s" % (comp["step"], comp["pos"])
            elif end is None:
                outcome = "still carrying at horizon %d" % nsteps
            elif rend is None:
                outcome = "left grid at %d" % end
            elif rend[5]:
                outcome = "DIED at %d at %s" % (end, rend[1])
            else:
                outcome = "released at %d (status %s)" % (end, rend[2])
            # was the pair already attempted? any replacement_after_blocked unassign of (ff, vid) before
            prior = [u for u in unassigns if u["ff"] == ff and u["vid"] == vid and u["reason"] == "replacement_after_blocked" and u["step"] < steps[0]]
            ul = [u for u in unassigns if u["ff"] == ff and u["vid"] == vid and steps[0] <= u["step"] <= (end or nsteps)]
            # other units assigned to this victim during the blocked carry
            others = [a for a in assigns if a["vid"] == vid and a["ff"] != ff and a["ok"] and steps[0] <= a["step"] <= (end or nsteps)]
            kept.append(dict(file=n, tag=d.get("tag"), cls=cls, tup=tup, ff=ff, vid=vid, leg_start=leg_start,
                             blocked_steps=steps, outcome=outcome, prior_blocked_unassigns=[(u["step"], u["reason"]) for u in prior],
                             unassigns_during=[(u["step"], u["reason"]) for u in ul],
                             other_assigns_during=[(a["step"], a["ff"], a["reason"]) for a in others],
                             all_pair_assigns=[(a["step"], a["reason"], a["ok"]) for a in assigns if a["ff"] == ff and a["vid"] == vid]))
        # ---- (d) carrier drops
        for u in unassigns:
            if not u["ok"]:
                continue
            s = u["step"]
            rprev = row(d, s - 1, u["ff"])
            if rprev is None or not rprev[4]:
                continue
            bprev = bind(d, s - 1, u["ff"])
            if bprev is not None and bprev[1] and bprev[1] != u["vid"]:
                continue
            vid = u["vid"]
            rs = row(d, s, u["ff"])
            vdeath = next((k for k in range(s, nsteps + 1) if vrow(d, k, vid) and vrow(d, k, vid)[2] == "dead"), None)
            reps = []
            for a in assigns:
                if a["vid"] != vid or not a["ok"] or a["step"] < s:
                    continue
                rff = a["ff"]
                best = None
                contact = None
                for k in range(a["step"], nsteps + 1):
                    b = bind(d, k, rff)
                    r = row(d, k, rff)
                    v = vrow(d, k, vid)
                    if b is None or b[1] != vid or r is None or r[5]:
                        break
                    if r[1] is not None and v is not None and v[1] is not None:
                        dd = md(r[1], v[1])
                        if best is None or dd < best:
                            best = dd
                        if dd == 0 and contact is None:
                            contact = k
                r0 = row(d, a["step"], rff)
                v0 = vrow(d, a["step"], vid)
                d0 = md(r0[1], v0[1]) if r0 and r0[1] and v0 and v0[1] else None
                rescued = any(c["ff"] == rff and c["victim"] == vid and c["step"] >= a["step"] for c in comps)
                reps.append(dict(step=a["step"], ff=rff, reason=a["reason"], d0=d0, best=best, contact=contact, rescued=rescued))
            drops.append(dict(file=n, tag=d.get("tag"), cls=cls, tup=tup, ff=u["ff"], vid=vid, step=s, reason=u["reason"],
                              cell=rprev[1], ff_dead_at_drop=bool(rs and rs[5]), vdeath=vdeath,
                              vfinal=(vrow(d, nsteps, vid) or [None, None, None])[2],
                              rescued_by_any=[(c["step"], c["ff"]) for c in comps if c["victim"] == vid and c["step"] >= s],
                              reps=reps))
    print("stats", dict(stats))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan.json"), "w", encoding="utf-8") as f:
        json.dump({"kept": kept, "drops": drops, "stats": dict(stats)}, f, default=str)
    print("kept episodes", len(kept), "drops", len(drops))


if __name__ == "__main__":
    main()
