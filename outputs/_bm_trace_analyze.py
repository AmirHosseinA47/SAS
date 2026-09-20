"""Base-mark round: offline analysis of the _bm_trace.py runs.

Everything here is recomputed from recorded positions - no model import, so it
can be re-run in a second against any candidate geometry.

usage: _bm_trace_analyze.py outputs/_bm/trace_*.json
"""
from __future__ import annotations
import json, sys
from collections import Counter, defaultdict

W = H = 50
FOVR, VFR = 8, 3
RANGE = {"idle": 3, "assigned": 1}          # exiting / offgrid / dead: no range


def diamond(cx, cy, r):
    return {(cx + dx, cy + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
            if abs(dx) + abs(dy) <= r}


def on_grid(c):
    return 0 <= c[0] < W and 0 <= c[1] < H


def fov_block(u):
    return (max(0, u["x"] - FOVR), min(W - 1, u["x"] + FOVR),
            max(0, u["y"] - FOVR), min(H - 1, u["y"] + FOVR))


def fov_clipped(u):
    return (u["x"] - FOVR < 0 or u["x"] + FOVR > W - 1
            or u["y"] - FOVR < 0 or u["y"] + FOVR > H - 1)


def fov_edge_cells(u):
    """Cells whose BOUNDARY carries a frame stroke (both sides of each edge)."""
    xlo, xhi, ylo, yhi = fov_block(u)
    s = set()
    for x in range(xlo, xhi + 1):
        s |= {(x, ylo), (x, ylo - 1), (x, yhi), (x, yhi + 1)}
    for y in range(ylo, yhi + 1):
        s |= {(xlo, y), (xlo - 1, y), (xhi, y), (xhi + 1, y)}
    return {c for c in s if on_grid(c)}


def diamond_edge_cells(cx, cy, r):
    inside = {c for c in diamond(cx, cy, r) if on_grid(c)}
    s = set()
    for (x, y) in inside:
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in inside:
                s.add((x, y))
                if on_grid(n):
                    s.add(n)
    return s


def flag_cells(d):
    """Candidate flag footprint: the block's OUTER corner region.
    NW-type block (x==0): pole in column x, pennant along the top row.
    SE-type block (x+size==W): pole in the last column, pennant one cell inward on the top row."""
    x0, y0, n = d["x"], d["y"], d["size"]
    top = y0 + n - 1
    if x0 == 0:
        return {(x0, top), (x0, top - 1), (x0, top - 2), (x0 + 1, top), (x0 + 2, top)}
    return {(x0 + n - 1, top), (x0 + n - 1, top - 1), (x0 + n - 1, top - 2),
            (x0 + n - 2, top), (x0 + n - 3, top)}


def main() -> int:
    grand = defaultdict(Counter)
    disp_all = []
    for path in sys.argv[1:]:
        t = json.load(open(path))
        tag = "%s/%d" % (t["wind"], t["seed"])
        rows = t["rows"]; depots = t["depots"]
        n = len(rows)
        print("=" * 78)
        print("%s  steps 0..%d  mode=%s idle_buffer=%s engaged_T=%s extinguish=%s firebreak=%s"
              % (tag, t["steps"], t["base_station_mode"], t["idle_buffer"],
                 t["engaged_retreat_range"], t["ff_extinguish"], t["ff_firebreak"]))
        depot_cells = [{(x, y) for x in range(d["x"], d["x"] + d["size"])
                        for y in range(d["y"], d["y"] + d["size"])} for d in depots]
        flags = [flag_cells(d) for d in depots]

        # ---- firefighter state -------------------------------------------------
        st = Counter(); trans = Counter(); per_unit_prev = {}; dwell = defaultdict(list)
        run_len = {}; disagree = 0; binds = Counter(); unit_steps = 0
        ff_clip = Counter(); ff_tot = Counter()
        for r in rows:
            for f in r["ffs"]:
                s = f["state"]; st[s] += 1; unit_steps += 1
                if f["assigned_attr"] != (s == "assigned") and s in ("idle", "assigned"):
                    disagree += 1
                p = per_unit_prev.get(f["id"])
                if p is not None and p != s:
                    trans[(p, s)] += 1
                    dwell[p].append(run_len[f["id"]]); run_len[f["id"]] = 0
                run_len[f["id"]] = run_len.get(f["id"], 0) + 1
                per_unit_prev[f["id"]] = s
                if s in RANGE and f["pos"] is not None:
                    rr = RANGE[s]
                    ff_tot[s] += 1
                    if len([c for c in diamond(f["pos"][0], f["pos"][1], rr) if on_grid(c)]) \
                            < len(diamond(0, 0, rr)):
                        ff_clip[s] += 1
                    if f["nearest_fire"] is not None and f["nearest_fire"] <= rr:
                        binds[s] += 1
        print("FF unit-steps by range-selecting state:",
              {k: "%d (%.1f%%)" % (v, 100.0 * v / unit_steps) for k, v in st.most_common()})
        shape_changes = sum(v for (a, b), v in trans.items())
        print("  state transitions (any): %d   ->  per unit per 100 steps: %.2f"
              % (shape_changes, 100.0 * shape_changes / max(1, unit_steps)))
        print("  transitions:", {"%s->%s" % k: v for k, v in trans.most_common()})
        print("  mean dwell (steps) before a change:",
              {k: round(sum(v) / len(v), 1) for k, v in dwell.items()})
        print("  'assigned' attr disagrees with target_pos selector on %d unit-steps" % disagree)
        for s in ("idle", "assigned"):
            if ff_tot[s]:
                print("  %-8s range %d: fire inside the range on %d/%d unit-steps (%.1f%%); "
                      "diamond clipped by grid edge on %d (%.1f%%)"
                      % (s, RANGE[s], binds[s], ff_tot[s], 100.0 * binds[s] / ff_tot[s],
                         ff_clip[s], 100.0 * ff_clip[s] / ff_tot[s]))
        d = [x["manhattan"] for x in t["dispatches"]]
        disp_all += d
        print("  dispatch distances (manhattan):", sorted(d), " max", max(d) if d else None)

        # ---- existing marks at MODE 3 -----------------------------------------
        ov = clip = allov = 0
        fov_on_depot = Counter(); fov_on_flag = Counter()
        dia_on_depot = Counter(); dia_on_flag = Counter()
        unit_on_flag = Counter(); unit_in_depot = Counter()
        occ = [Counter(), Counter()]
        ffd_vs_vic = ffd_vs_fov = ffd_vs_ffd = ffd_steps = 0
        for r in rows:
            us = r["uavs"]
            pairs = [(a, b) for i, a in enumerate(us) for b in us[i + 1:]]
            o = [max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"])) <= 2 * FOVR for a, b in pairs]
            ov += any(o); allov += (all(o) if o else 0)
            clip += any(fov_clipped(u) for u in us)
            fe = set()
            for u in us:
                fe |= fov_edge_cells(u)
            de = set()
            for v in r["victims"]:
                if v["flee"]:
                    de |= diamond_edge_cells(v["x"], v["y"], VFR)
            units = [(u["x"], u["y"]) for u in us] + \
                    [tuple(f["pos"]) for f in r["ffs"] if f["pos"] is not None and f["state"] != "dead"]
            for i in range(len(depots)):
                fov_on_depot[i] += bool(fe & depot_cells[i])
                fov_on_flag[i] += bool(fe & flags[i])
                dia_on_depot[i] += bool(de & depot_cells[i])
                dia_on_flag[i] += bool(de & flags[i])
                unit_on_flag[i] += any(c in flags[i] for c in units)
                unit_in_depot[i] += any(c in depot_cells[i] for c in units)
                for c in units:
                    if c in depot_cells[i]:
                        occ[i][c] += 1
            # a state-dependent FF diamond vs the other overlays
            fds = [(f, diamond_edge_cells(f["pos"][0], f["pos"][1], RANGE[f["state"]]))
                   for f in r["ffs"] if f["state"] in RANGE and f["pos"] is not None]
            if fds:
                ffd_steps += 1
                allfd = set().union(*[s for _, s in fds])
                ffd_vs_vic += bool(allfd & de)
                ffd_vs_fov += bool(allfd & fe)
                ffd_vs_ffd += any(a[1] & b[1] for i, a in enumerate(fds) for b in fds[i + 1:])
        print("EXISTING MARKS at mode 3:  >=1 FOV pair overlapping %d/%d (%.1f%%); all pairs %d (%.1f%%); "
              ">=1 FOV block edge-clipped %d (%.1f%%)"
              % (ov, n, 100.0 * ov / n, allov, 100.0 * allov / n, clip, 100.0 * clip / n))
        for i, dd in enumerate(depots):
            nm = "NW" if dd["x"] == 0 else "SE"
            print("  depot %s: FOV stroke touches block %d/%d (%.1f%%), touches flag cells %d (%.1f%%); "
                  "victim-diamond stroke touches block %d (%.1f%%), flag %d (%.1f%%)"
                  % (nm, fov_on_depot[i], n, 100.0 * fov_on_depot[i] / n, fov_on_flag[i],
                     100.0 * fov_on_flag[i] / n, dia_on_depot[i], 100.0 * dia_on_depot[i] / n,
                     dia_on_flag[i], 100.0 * dia_on_flag[i] / n))
            print("           a unit inside the block %d/%d (%.1f%%); a unit ON a flag cell %d (%.1f%%)"
                  % (unit_in_depot[i], n, 100.0 * unit_in_depot[i] / n,
                     unit_on_flag[i], 100.0 * unit_on_flag[i] / n))
            print("           occupancy by cell:", dict(sorted(occ[i].items(), key=lambda kv: -kv[1])))
            g = Counter()
            for r in rows:
                for col, k in r["depot_ground"][i].items():
                    g[col] += k
            tot = sum(g.values())
            print("           ground under block (cell-steps):",
                  {k: "%.1f%%" % (100.0 * v / tot) for k, v in g.most_common(8)})
            for k, v in g.items():
                grand["ground_%s" % nm][k] += v
        if ffd_steps:
            print("HYPOTHETICAL state-dependent FF diamonds: on steps with >=1 drawn (%d): stroke shares a cell "
                  "with a victim diamond %.1f%%, with a FOV frame %.1f%%, with another FF diamond %.1f%%"
                  % (ffd_steps, 100.0 * ffd_vs_vic / ffd_steps, 100.0 * ffd_vs_fov / ffd_steps,
                     100.0 * ffd_vs_ffd / ffd_steps))
        for k, v in st.items():
            grand["state"][k] += v
        grand["trans"]["n"] += shape_changes
        grand["trans"]["unit_steps"] += unit_steps
        for s in ("idle", "assigned"):
            grand["binds"][s] += binds[s]; grand["tot"][s] += ff_tot[s]; grand["clip"][s] += ff_clip[s]

    print("=" * 78)
    print("POOLED over %d runs" % len(sys.argv[1:]))
    us = grand["trans"]["unit_steps"]
    print("  FF states:", {k: "%.1f%%" % (100.0 * v / us) for k, v in grand["state"].most_common()})
    print("  frame shape changes per unit per 100 steps: %.2f" % (100.0 * grand["trans"]["n"] / us))
    for s in ("idle", "assigned"):
        if grand["tot"][s]:
            print("  %-8s fire inside range %.1f%% of unit-steps; edge-clipped %.1f%%"
                  % (s, 100.0 * grand["binds"][s] / grand["tot"][s],
                     100.0 * grand["clip"][s] / grand["tot"][s]))
    print("  dispatch distances pooled: n=%d max=%d sorted=%s"
          % (len(disp_all), max(disp_all), sorted(disp_all)))
    for nm in ("NW", "SE"):
        g = grand["ground_%s" % nm]; tot = sum(g.values())
        print("  ground under %s block pooled:" % nm,
              {k: "%.2f%%" % (100.0 * v / tot) for k, v in g.most_common()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
