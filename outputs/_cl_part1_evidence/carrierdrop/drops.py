"""Read-only: rebuild every broken carrying leg of the matched arms from the recorded JSON.

Lists outputs/ NON-recursively and skips the quarantine name before touching anything.
Writes nothing under the repo; prints to stdout only.
"""
import collections
import json
import os
import re
import sys

OUT_DIR = r"E:\Projects\SAS\outputs"
QUAR = "_firemech_rewound_20260914"
H = W = 50

GROUPS = [
    ("uh", ["uhC", "uhD", "uhY"]),
    ("ug", ["ugC", "ugD", "ugY"]),
    ("ugK", ["ugKC", "ugKD", "ugKY"]),
    ("fm", ["fmOFF", "fmEFS", "fmDRY"]),
    ("f2c", ["f2cOFF", "f2cEFS", "f2cDRY"]),
]


def exit_target(p):
    x, y = p
    dists = {(0, y): x, (H - 1, y): H - 1 - x, (x, 0): y, (x, W - 1): W - 1 - y}
    return min(dists, key=dists.get)


def burning_at(bi, cell, s):
    for st, en in bi.get("%d,%d" % cell, []):
        if st <= s and (en is None or s < en):
            return True
    return False


def nbrs(c):
    out = []
    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (c[0] + ox, c[1] + oy)
        if 0 <= n[0] < W and 0 <= n[1] < H:
            out.append(n)
    return out


def on_boundary(c):
    return c is not None and (c[0] in (0, W - 1) or c[1] in (0, H - 1))


def ffrow(d, s, ff):
    """ff_steps row of unit ff at the END of step s (1-based)."""
    rows = d["ff_steps"]
    if s < 1 or s > len(rows):
        return None
    return next((r for r in rows[s - 1] if r[0] == ff), None)


def vrow(d, s, vid):
    rows = d["victim_steps"]
    if s < 1 or s > len(rows):
        return None
    return next((r for r in rows[s - 1] if r[0] == vid), None)


def bindrow(d, s, ff):
    rows = d.get("ff_bind_steps") or []
    if s < 1 or s > len(rows):
        return None
    return next((r for r in rows[s - 1] if r[0] == ff), None)


def tup(c):
    return None if c is None else (int(c[0]), int(c[1]))


def md(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def broken_legs(d):
    starts = d.get("exit_starts") or []
    comps = d.get("completions") or []
    nsteps = len(d["ff_steps"])
    out = []
    for i, e in enumerate(starts):
        nxt = next((x["step"] for x in starts[i + 1:] if x.get("victim") == e.get("victim")), 10 ** 9)
        if any(c.get("victim") == e.get("victim") and c.get("ff") == e.get("ff") and e["step"] <= c["step"] <= nxt
               for c in comps):
            continue
        end = None
        for s in range(e["step"] + 1, nsteps + 1):
            r = ffrow(d, s, e["ff"])
            if r is None or not r[4]:
                end = s
                break
        out.append((e, end))
    return out


def analyse(tag, name, d, e, end, verbose=True):
    ff, vid, s0 = e["ff"], e["victim"], e["step"]
    p0 = tup(e["ff_pos"])
    et = exit_target(p0)
    bi = d.get("burn_intervals") or {}
    nsteps = len(d["ff_steps"])
    res = {"tag": tag, "file": name, "ff": ff, "vid": vid, "s0": s0, "p0": p0, "exit": et, "end": end}
    if end is None:
        res["kind"] = "HORIZON"
        return res
    r_end = ffrow(d, end, ff)
    r_prev = ffrow(d, end - 1, ff)
    res["status_end"] = r_end[2] if r_end else None
    res["dead_end"] = bool(r_end[5]) if r_end else None
    res["cell_prev"] = tup(r_prev[1]) if r_prev else None
    res["cell_end"] = tup(r_end[1]) if r_end else None
    res["carry_len"] = end - s0
    res["dist_left"] = md(res["cell_prev"], et) if res["cell_prev"] else None
    # boundary visits during the carry
    bsteps = [s for s in range(s0, end) if on_boundary(tup(ffrow(d, s, ff)[1]))]
    res["carry_boundary_steps"] = (bsteps[0], bsteps[-1], len(bsteps)) if bsteps else None
    # unassign / assign records
    un = [u for u in d.get("unassigns") or [] if u["step"] >= s0 and (u["ff"] == ff or u["vid"] == vid)]
    res["unassigns"] = [(u["step"], u["ff"], u["vid"], u["reason"], u["ok"]) for u in un]
    asg = [a for a in d.get("assigns") or [] if a["step"] >= s0 and (a["vid"] == vid or a["ff"] == ff)]
    res["assigns"] = [(a["step"], a["ff"], a["vid"], a["reason"], a["ok"]) for a in asg]
    pl = [p for p in d.get("planner") or [] if p["step"] >= end - 1 and p["vid"] == vid]
    res["planner"] = [(p["step"], p["reason"], p["action"], p["ff"], p["n_available"], p["n_offgrid_alive"], p["n_dead"]) for p in pl][:8]
    # neighbours of the drop cell at the drop step (post-step burning state)
    cell = res["cell_prev"]
    res["own_burning_at_end"] = burning_at(bi, cell, end)
    res["nbrs_burning_at_end"] = [(n, burning_at(bi, n, end)) for n in nbrs(cell)]
    res["nbrs_burning_at_endm1"] = [(n, burning_at(bi, n, end - 1)) for n in nbrs(cell)]
    # carrier death
    ddeath = next((s for s in range(end, nsteps + 1) if ffrow(d, s, ff) and ffrow(d, s, ff)[5]), None)
    res["ff_death"] = ddeath
    res["ff_death_cell"] = tup(ffrow(d, ddeath, ff)[1]) if ddeath else None
    # ex-carrier path after the drop
    path = []
    for s in range(end, min(nsteps, (ddeath or nsteps) if ddeath else nsteps) + 1):
        r = ffrow(d, s, ff)
        b = bindrow(d, s, ff)
        path.append((s, tup(r[1]), r[2], r[3], r[4], r[5], b[1] if b else None))
        if len(path) > 40:
            break
    res["ff_path"] = path
    moved = next((p for p in path if p[1] != cell and not p[5]), None)
    res["ff_first_off_drop"] = (moved[0], moved[1]) if moved else None
    # victim
    vdeath = next((s for s in range(s0, nsteps + 1) if vrow(d, s, vid) and vrow(d, s, vid)[2] == "dead"), None)
    res["v_death"] = vdeath
    res["v_death_cell"] = tup(vrow(d, vdeath, vid)[1]) if vdeath else None
    vpath = []
    for s in range(end - 1, min(nsteps, vdeath or nsteps) + 1):
        r = vrow(d, s, vid)
        vpath.append((s, tup(r[1]), r[2]))
    res["v_path"] = vpath
    res["v_moved_after_drop"] = any(v[1] != cell for v in vpath if v[0] >= end)
    res["v_final"] = vrow(d, nsteps, vid)[2]
    # replacements after the drop
    reps = []
    for a in d.get("assigns") or []:
        if a["vid"] != vid or not a["ok"] or a["step"] < end:
            continue
        rff = a["ff"]
        best = None
        contact = None
        stop = None
        for s in range(a["step"], nsteps + 1):
            b = bindrow(d, s, rff)
            r = ffrow(d, s, rff)
            v = vrow(d, s, vid)
            if b is None or b[1] != vid or r is None or r[5]:
                stop = s
                break
            if r[1] is not None and v[1] is not None:
                dd = md(tup(r[1]), tup(v[1]))
                if best is None or dd < best[0]:
                    best = (dd, s)
                if dd == 0 and contact is None:
                    contact = s
        r0 = ffrow(d, a["step"], rff)
        v0 = vrow(d, a["step"], vid)
        reps.append({"step": a["step"], "ff": rff, "reason": a["reason"],
                     "dist_at_assign": md(tup(r0[1]), tup(v0[1])) if r0 and r0[1] and v0 and v0[1] else None,
                     "min_dist": best, "contact": contact, "bind_end": stop})
    res["replacements"] = reps
    res["completed_by"] = [(c["step"], c["ff"]) for c in d.get("completions") or [] if c["victim"] == vid]
    # classification
    if res["dead_end"] and vdeath == end:
        k = "A"
    elif ddeath is not None and res["ff_first_off_drop"] is None:
        k = "B"
    elif res["ff_first_off_drop"] is not None:
        k = "C"
    else:
        k = "D"
    res["kind"] = k
    return res


def main():
    names = sorted(n for n in os.listdir(OUT_DIR) if n != QUAR)
    by_tag = collections.defaultdict(dict)
    want = {t for _g, ts in GROUPS for t in ts}
    for n in names:
        m = re.match(r"^_ffr_(.+?)_(east|south|west|north)_(half|def)_(\d+)\.json$", n)
        if not m or m.group(1) not in want:
            continue
        by_tag[m.group(1)][(m.group(2), m.group(3), int(m.group(4)))] = n
    allres = []
    for g, ts in GROUPS:
        common = set.intersection(*(set(by_tag[t]) for t in ts))
        for t in ts:
            for tp in sorted(common):
                n = by_tag[t][tp]
                with open(os.path.join(OUT_DIR, n), encoding="utf-8") as f:
                    d = json.load(f)
                for e, end in broken_legs(d):
                    r = analyse(t, n, d, e, end)
                    r["group"] = g
                    r["tuple"] = tp
                    allres.append(r)
    for r in allres:
        print("=" * 100)
        print(r["group"], r["tag"], "%s/%s/%d" % r["tuple"], r["vid"], r["ff"], "KIND", r["kind"])
        for k in ("s0", "p0", "exit", "end", "carry_len", "status_end", "dead_end", "cell_prev", "cell_end", "dist_left",
                  "carry_boundary_steps", "own_burning_at_end", "nbrs_burning_at_end", "nbrs_burning_at_endm1",
                  "unassigns", "assigns", "planner", "ff_death", "ff_death_cell", "ff_first_off_drop",
                  "v_death", "v_death_cell", "v_moved_after_drop", "v_final", "v_path", "replacements", "completed_by"):
            if k in r:
                print("  %-22s %s" % (k, r[k]))
        if "ff_path" in r:
            print("  ff_path (step, cell, status, assigned, exiting, dead, bound):")
            for p in r["ff_path"][:25]:
                print("     ", p)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "drops.json"), "w", encoding="utf-8") as f:
        json.dump(allres, f, default=str, indent=1)


if __name__ == "__main__":
    main()
