"""Defect 1 census extension (read-only). Items 2, 3, 4 of the task.

Input: E:/Projects/SAS/outputs, non-recursive listing, same file selection as _xs_census.py.
Output: pickle of per-leg records in this scratch dir, and a text report on stdout.
"""
import collections
import json
import os
import pickle
import re
import sys

HERE = "E:/Projects/SAS/outputs"
QUAR = "_firemech_rewound_20260914"
SCR = os.path.dirname(os.path.abspath(__file__))
TRACKED = set(l.strip() for l in open(os.path.join(SCR, "tracked_80ca7b3.txt"), encoding="utf-8") if l.strip())
N = 50  # HEIGHT = WIDTH = 50 (common_fixed_variables.py:20-21)


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def on_boundary(p):
    return p is not None and (p[0] == 0 or p[0] == N - 1 or p[1] == 0 or p[1] == N - 1)


def nearest_boundary_dist(p):
    return min(p[0], N - 1 - p[0], p[1], N - 1 - p[1])


def unit_row(row, ff):
    for r in row:
        if r[0] == ff:
            return r
    return None


def main():
    names = sorted(n for n in os.listdir(HERE) if n != QUAR and n.startswith("_ffr_") and n.endswith(".json")
                   and not n.startswith("_ffr_xs") and ".xstrace." not in n)
    comp_legs = []      # one record per (file, completed leg)
    broken_legs = []    # one record per (file, broken leg)
    anomalies = collections.Counter()
    anomaly_ex = collections.defaultdict(list)
    runs = collections.Counter()
    grid_params = collections.Counter()
    for n in names:
        try:
            with open(os.path.join(HERE, n), encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            anomalies["unreadable"] += 1
            continue
        if not isinstance(d, dict) or "exit_starts" not in d or "completions" not in d:
            continue
        cls = "ON" if d.get("firefight_log") else "OFF"
        tag = str(d.get("tag") or re.sub(r"^_ffr_|_(east|south|west|north)_.*$", "", n))
        tracked = n in TRACKED
        runs[(cls, tracked)] += 1
        for pk in ("params", "extra_params"):
            p = d.get(pk) or {}
            if isinstance(p, dict):
                for k in ("HEIGHT", "WIDTH", "GRID_SIZE"):
                    if k in p:
                        grid_params[(pk, k, p[k])] += 1
        wind, roles, seed = d.get("wind"), d.get("roles"), d.get("seed")
        starts = d.get("exit_starts") or []
        comps = d.get("completions") or []
        ffs = d.get("ff_steps") or []
        vs = d.get("victim_steps") or []
        H = len(ffs)
        unas = d.get("unassigns") or []
        umarks = d.get("unreachable_marks") or []
        # ---- completed legs, exactly the census's legs() pairing
        for c in comps:
            st = [e for e in starts if e.get("victim") == c.get("victim") and e.get("step", 10 ** 9) <= c.get("step", -1)]
            if not st or not c.get("exit_target") or not st[-1].get("ff_pos"):
                anomalies["completion skipped by census pairing"] += 1
                anomaly_ex["completion skipped by census pairing"].append((n, c))
                continue
            s = st[-1]
            s0, s1 = s["step"], c["step"]
            p0, tgt = tuple(s["ff_pos"]), tuple(c["exit_target"])
            dist = manhattan(p0, tgt)
            nb = nearest_boundary_dist(p0)
            rec = dict(file=n, tag=tag, cls=cls, tracked=tracked, wind=wind, roles=roles, seed=seed, vid=c["victim"],
                       ff=c.get("ff"), start_ff=s.get("ff"), s0=s0, s1=s1, p0=p0, tgt=tgt, dist=dist, nbdist=nb,
                       cpos=tuple(c["pos"]) if c.get("pos") else None, contact=s.get("contact"), H=H)
            if s.get("ff") != c.get("ff"):
                anomalies["last exit_start ff != completion ff"] += 1
                anomaly_ex["last exit_start ff != completion ff"].append((n, s, c))
            if dist != nb:
                anomalies["distance != nearest-boundary distance"] += 1
                anomaly_ex["distance != nearest-boundary distance"].append((n, s, c, nb))
            if not on_boundary(tgt):
                anomalies["exit_target not on boundary"] += 1
                anomaly_ex["exit_target not on boundary"].append((n, c))
            if rec["cpos"] != tgt:
                anomalies["completion pos != exit_target"] += 1
                anomaly_ex["completion pos != exit_target"].append((n, c))
            # ff_steps consistency: post-state of step s0 (index s0-1) has the unit at p0, exiting
            r0 = unit_row(ffs[s0 - 1], s["ff"]) if 0 <= s0 - 1 < H else None
            if r0 is None or tuple(r0[1] or ()) != p0 or not r0[4]:
                anomalies["ff_steps[s0-1] != (p0, exiting)"] += 1
                anomaly_ex["ff_steps[s0-1] != (p0, exiting)"].append((n, s, r0))
            # position at the start of step s1's advance = post-state of step s1-1 = ff_steps[s1-2]
            r1 = unit_row(ffs[s1 - 2], c["ff"]) if 0 <= s1 - 2 < H else None
            if r1 is None or tuple(r1[1] or ()) != tgt:
                anomalies["ff_steps[s1-2] pos != exit_target"] += 1
                anomaly_ex["ff_steps[s1-2] pos != exit_target"].append((n, c, r1))
            # first step n_b > s0 at whose START the carrier stood on any boundary cell
            first_b = None
            first_b_cell = None
            exiting_gap = False
            for k in range(s0 - 1, min(s1 - 1, H)):
                r = unit_row(ffs[k], c["ff"])
                if r is None or r[1] is None:
                    exiting_gap = True
                    break
                if not r[4]:
                    exiting_gap = True
                if on_boundary(r[1]):
                    first_b = k + 2
                    first_b_cell = tuple(r[1])
                    break
            if exiting_gap:
                anomalies["carrier not exiting somewhere inside a completed leg"] += 1
                anomaly_ex["carrier not exiting somewhere inside a completed leg"].append((n, s, c))
            rec["first_b"] = first_b
            rec["first_b_cell"] = first_b_cell
            comp_legs.append(rec)
        # ---- broken legs: the census's broken() pairing, with the end scanned from the
        # post-state of the start step itself (index s0-1) as well as from index s0 (census)
        for i, e in enumerate(starts):
            nxt = next((x["step"] for x in starts[i + 1:] if x.get("victim") == e.get("victim")), 10 ** 9)
            if any(c.get("victim") == e.get("victim") and c.get("ff") == e.get("ff") and e["step"] <= c["step"] <= nxt
                   for c in comps):
                continue
            s0 = e["step"]
            ff = e.get("ff")
            vid = e.get("victim")

            def scan(k0):
                for k in range(k0, H):
                    row = unit_row(ffs[k], ff)
                    if row is None or row[1] is None or not row[4]:
                        return k + 1, row, k
                return None, None, None
            end_c, row_c, _ = scan(s0)          # census
            end, row, kend = scan(s0 - 1)       # from the start step's own post-state
            if end is None:
                cause = "horizon"
            elif row is None:
                cause = "left_grid(missing)"
            elif row[1] is None:
                cause = "left_grid(pos None)"
            elif row[5]:
                cause = "died"
            elif row[2] == "route_blocked":
                cause = "route_blocked"
            else:
                cause = "released:%s" % row[2]
            # unassign / unreachable records for this (unit, victim) in the carry window
            hi = end if end is not None else H
            ua = [(u["step"], u.get("reason")) for u in unas if u.get("ff") == ff and u.get("vid") == vid and s0 <= u["step"] <= hi]
            ua_end = [r for (st_, r) in ua if st_ == end]
            um = [(u["step"], u.get("reason")) for u in umarks if u.get("vid") == vid and s0 <= u["step"] <= hi]
            # first boundary arrival during the carry (start-of-advance convention), before the end
            first_b = None
            first_b_cell = None
            for k in range(s0 - 1, (kend if kend is not None else H)):
                r = unit_row(ffs[k], ff)
                if r is None or r[1] is None:
                    break
                if on_boundary(r[1]):
                    first_b = k + 2
                    first_b_cell = tuple(r[1])
                    break
            died = next((k + 1 for k, rw in enumerate(vs) for v in rw if v[0] == vid and v[2] == "dead"), None)
            fate = next((v[2] for v in (vs[-1] if vs else []) if v[0] == vid), "?")
            ff_dead = next((k + 1 for k in range(s0 - 1, H) for r in [unit_row(ffs[k], ff)] if r is not None and r[5]), None)
            # later completion of this victim (by anyone) in this run
            later_comp = [(c["step"], c.get("ff")) for c in comps if c.get("victim") == vid and c["step"] > s0]
            broken_legs.append(dict(file=n, tag=tag, cls=cls, tracked=tracked, wind=wind, roles=roles, seed=seed,
                                    vid=vid, ff=ff, s0=s0, p0=tuple(e["ff_pos"]) if e.get("ff_pos") else None,
                                    end=end, end_census=end_c, cause=cause, status_at_end=(row[2] if row else None),
                                    ua=ua, ua_end=ua_end, um=um, first_b=first_b, first_b_cell=first_b_cell,
                                    victim_dead=died, fate=fate, ff_dead=ff_dead, H=H, nxt=nxt, later_comp=later_comp))
    with open(os.path.join(SCR, "d1_legs.pkl"), "wb") as f:
        pickle.dump(dict(comp=comp_legs, broken=broken_legs, anomalies=anomalies, anomaly_ex=dict(anomaly_ex),
                         runs=runs, grid_params=grid_params), f)
    print("runs by (class, tracked@80ca7b3):", dict(runs))
    print("grid params seen:", dict(grid_params))
    print("anomalies:", dict(anomalies))
    for k, v in anomaly_ex.items():
        print("  ", k, len(v))
        for x in v[:8]:
            print("      ", x)
    print("completed-leg records:", len(comp_legs), " broken-leg records:", len(broken_legs))


if __name__ == "__main__":
    main()
