"""Part 1 measurement of the last_cell guard, from the direct _retreat_candidates hook.

Reads outputs/_lc_<arm>_<wind>_<roles>_<seed>.json produced by _lc_probe.py.
Arm 'none' is stock b6527f7; this script also control-checks it against the
two prior rounds' data (_ir_p3_POST_*.json).

Read-only.
"""
from __future__ import annotations
import glob, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE13 = [("east", "default", 101), ("east", "default", 202), ("east", "default", 303),
          ("east", "half", 101), ("east", "half", 202), ("east", "half", 303),
          ("east", "half", 404), ("east", "half", 505),
          ("south", "half", 101), ("south", "half", 202), ("south", "half", 303),
          ("south", "half", 404), ("south", "half", 505)]


def load(arm, wind, roles, seed):
    p = os.path.join(HERE, "_lc_%s_%s_%s_%d.json" % (arm, wind, roles, seed))
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p) as f:
        return json.load(f)


def tup(x):
    return None if x is None else (int(x[0]), int(x[1]))


def arm_rows(arm, cells):
    out = []
    for w, r, s in cells:
        d = load(arm, w, r, s)
        if d is not None:
            out.append((w, r, s, d))
    return out


def control_check():
    """Arm 'none' must reproduce the prior rounds' stock trajectories."""
    ref, refdeaths = {}, defaultdict(list)
    for p in glob.glob(os.path.join(HERE, "_ir_p3_POST_*.json")):
        d = json.load(open(p))
        for e in d["evals"]:
            ref[(d["wind"], d["roles"], int(e["seed"]))] = (
                e["rescued"], e["dead"], e["firefighter_deaths"])
        for x in d["deaths"]:
            refdeaths[(d["wind"], d["roles"], int(x["seed"]))].append(
                (int(x["step"]), str(x["ff"]), tuple(x["pos"]) if x["pos"] else None))
    lines, ok, bad = [], 0, 0
    for w, r, s, d in arm_rows("none", BASE13):
        e = d["evals"][0]
        key = (w, r, s)
        if key not in ref:
            lines.append("  %-6s %-7s %4d  NO REFERENCE" % (w, r, s))
            continue
        mine = (e["rescued"], e["dead"], e["firefighter_deaths"])
        theirs = ref[key]
        md = sorted((int(x["step"]), str(x["ff"]), tuple(x["pos"]) if x["pos"] else None)
                    for x in d["deaths"])
        td = sorted(refdeaths[key])
        same = (mine == theirs) and (md == td)
        ok += same
        bad += (not same)
        lines.append("  %-6s %-7s %4d  outcomes %s vs %s  deaths %s  %s"
                     % (w, r, s, mine, theirs, "same" if md == td else "DIFFER",
                        "MATCH" if same else "MISMATCH"))
    return lines, ok, bad


def predecessor_map(d):
    """(seed, ff, step) -> (previous distinct cell, cell) from end-of-step fftrace."""
    tr = defaultdict(list)
    for row in d["fftrace"]:
        tr[(int(row["seed"]), str(row["ff"]))].append(row)
    out = {}
    for k, rows in tr.items():
        rows.sort(key=lambda r: int(r["step"]))
        prev_distinct, cur = None, None
        for r in rows:
            p = tup(r["pos"])
            if cur is None:
                cur = p
            elif p != cur:
                prev_distinct, cur = cur, p
            out[(k[0], k[1], int(r["step"]))] = (prev_distinct, cur)
    return out


def measure(arm, cells, label):
    rows = arm_rows(arm, cells)
    tot = defaultdict(int)
    sole, emptied = [], []
    for w, r, s, d in rows:
        tot["runs"] += 1
        pred = predecessor_map(d)
        tag = "%s_%s_%d" % (w, r, s)
        for c in d["cand"]:
            tot["cand_calls"] += 1
            if c["lc_removed"]:
                tot["lc_excl_any"] += 1
            if c["n_stock"] == 0:
                tot["stock_empty"] += 1
                if c["n_free"] == 0:
                    tot["empty_enclosed"] += 1
                elif c["emptied_by_lc"]:
                    tot["empty_by_lc"] += 1
                else:
                    tot["empty_by_leash"] += 1
            key = (int(c["seed"]), str(c["ff"]), int(c["step"]) - 1)
            arrived_from = pred.get(key, (None, None))[0]
            rec = dict(c)
            rec["tag"] = tag
            rec["arrived_from"] = list(arrived_from) if arrived_from else None
            rec["lc_is_true_predecessor"] = (
                tup(c["last_cell"]) is not None and arrived_from == tup(c["last_cell"]))
            if c["sole_exit"]:
                tot["sole_exit"] += 1
                tot["sole_exit_d0"] += int(c["cur_dist"] == 0)
                tot["sole_exit_d1"] += int(c["cur_dist"] == 1)
                tot["sole_exit_stale"] += int(not rec["lc_is_true_predecessor"])
                sole.append(rec)
            if c["emptied_by_lc"]:
                tot["emptied_by_lc"] += 1
                tot["emptied_by_lc_d0"] += int(c["cur_dist"] == 0)
                emptied.append(rec)
    return {"label": label, "arm": arm, "totals": dict(tot),
            "sole": sole, "emptied": emptied,
            "present": ["%s_%s_%d" % (w, r, s) for w, r, s, _ in rows]}


def outcomes(arm, cells):
    out = {}
    for w, r, s, d in arm_rows(arm, cells):
        e = d["evals"][0]
        out["%s_%s_%d" % (w, r, s)] = {
            "rescued": e["rescued"], "dead": e["dead"],
            "ff_deaths": e["firefighter_deaths"],
            "deaths": sorted((int(x["step"]), str(x["ff"]),
                              tuple(x["pos"]) if x["pos"] else None)
                             for x in d["deaths"])}
    return out


def fresh_cells():
    cells = []
    for p in sorted(glob.glob(os.path.join(HERE, "_lc_none_*.json"))):
        b = os.path.basename(p)[len("_lc_none_"):-len(".json")]
        parts = b.split("_")
        w, r, s = parts[0], parts[1], int(parts[2])
        if (w, r, s) not in BASE13:
            cells.append((w, r, s))
    return cells


def report():
    print("=" * 78)
    print("CONTROL: arm 'none' vs prior-round stock data (_ir_p3_POST_*)")
    print("=" * 78)
    lines, ok, bad = control_check()
    print("\n".join(lines))
    print("  -> %d match, %d mismatch" % (ok, bad))

    for label, cells in (("BASELINE 13-RUN SAMPLE", BASE13),
                         ("FRESH SEEDS", fresh_cells())):
        m = measure("none", cells, label)
        print()
        print("=" * 78)
        print("%s  (arm none, %d runs present)" % (label, m["totals"].get("runs", 0)))
        print("  " + ",".join(m["present"]))
        print("=" * 78)
        for k in ("cand_calls", "lc_excl_any", "stock_empty", "empty_enclosed",
                  "empty_by_lc", "empty_by_leash", "sole_exit", "sole_exit_d0",
                  "sole_exit_d1", "sole_exit_stale", "emptied_by_lc",
                  "emptied_by_lc_d0"):
            print("  %-20s %5d" % (k, m["totals"].get(k, 0)))
        print("  --- sole-exit rows (last_cell was the ONLY free neighbour) ---")
        for r in m["sole"]:
            print("    %-18s s%-4d %-10s cell=%-9s lc=%-9s d=%d idle=%-5s stall=%-5s "
                  "onfire=%-5s pred=%-9s truepred=%s"
                  % (r["tag"], r["step"], r["ff"], tuple(r["cell"]),
                     tuple(r["last_cell"]) if r["last_cell"] else None,
                     r["cur_dist"], r["idle"], r["stalled"], r["on_fire"],
                     tuple(r["arrived_from"]) if r["arrived_from"] else None,
                     r["lc_is_true_predecessor"]))
        extra = [r for r in m["emptied"] if not r["sole_exit"]]
        if extra:
            print("  --- emptied-by-lc but NOT sole (others leash-excluded) ---")
            for r in extra:
                print("    %-18s s%-4d %-10s cell=%-9s lc=%-9s d=%d nfree=%d"
                      % (r["tag"], r["step"], r["ff"], tuple(r["cell"]),
                         tuple(r["last_cell"]) if r["last_cell"] else None,
                         r["cur_dist"], r["n_free"]))
        with open(os.path.join(HERE, "_lc_p1_%s.json"
                               % label.split()[0].lower()), "w") as f:
            json.dump(m, f, separators=(",", ":"), default=str)


if __name__ == "__main__":
    report()
