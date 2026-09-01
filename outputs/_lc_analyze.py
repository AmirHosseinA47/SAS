"""Re-analysis of the 62b4fbe post-fix 13-run sample for the last_cell guard.

Reads outputs/_ir_p3_POST_*.json (probe3 records _survival_move pre-state,
including free_cells / last_cell / origin / cur_dist) and reconstructs the
EFFECTIVE last_cell the filter chain actually saw, applying the 62b4fbe
leash re-anchor that runs before the candidate scan.

Read-only. No source is touched.
"""
from __future__ import annotations
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAXC = 6  # IDLE_RETREAT_MAX_CELLS


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def tup(x):
    return None if x is None else (int(x[0]), int(x[1]))


def effective_state(r):
    """Replicate _survival_move lines 764-787 (leash re-anchor) exactly."""
    cell = tup(r.get("pos"))
    origin = tup(r.get("origin"))
    last = tup(r.get("last_cell"))
    tgt = r.get("target_pos")
    if origin is None or ((not tgt) and man(cell, origin) > MAXC):
        return cell, None, True   # re-anchored: origin=cell, last_cell=None
    return origin, last, False


def chain(r):
    """Return (free, after_last, after_leash, eff_origin, eff_last, reanchored)."""
    cell = tup(r.get("pos"))
    eff_origin, eff_last, rean = effective_state(r)
    free = [tup(c) for c in (r.get("free_cells") or [])]
    after_last = [c for c in free if c != eff_last]
    after_leash = [c for c in after_last if man(c, eff_origin) <= MAXC]
    return free, after_last, after_leash, eff_origin, eff_last, rean


def main():
    files = sorted(glob.glob(os.path.join(HERE, "_ir_p3_POST_*.json")))
    if not files:
        print("no data"); return
    tot = {
        "runs": 0, "surv_calls": 0,
        "lc_excl_any": 0,          # last_cell removed >=1 free neighbour
        "lc_sole": 0,              # last_cell was the ONLY free neighbour
        "lc_sole_onfire": 0,       # ... and cur_dist == 0
        "lc_sole_notonfire": 0,
        "lc_emptied": 0,           # last_cell removal is what emptied the set
        "lc_emptied_onfire": 0,
        "empty_by_fire": 0,        # 0 free neighbours (enclosed)
        "empty_by_leash": 0,       # non-empty after last_cell, emptied by leash
    }
    sole_rows = []
    deaths_all = []
    for fp in files:
        d = json.load(open(fp))
        tot["runs"] += 1
        tag = os.path.basename(fp)[len("_ir_p3_POST_"):-len(".json")]
        deaths = d.get("deaths") or []
        for dd in deaths:
            dd = dict(dd); dd["tag"] = tag
            deaths_all.append(dd)
        for r in d.get("surv") or []:
            if r.get("pos") is None:
                continue
            tot["surv_calls"] += 1
            free, af_last, af_leash, eff_o, eff_l, rean = chain(r)
            cell = tup(r.get("pos"))
            cur = r.get("cur_dist")
            if not free:
                tot["empty_by_fire"] += 1
                continue
            n_removed_by_last = len(free) - len(af_last)
            if n_removed_by_last:
                tot["lc_excl_any"] += 1
            if len(free) == 1 and eff_l is not None and free[0] == eff_l:
                tot["lc_sole"] += 1
                if cur == 0:
                    tot["lc_sole_onfire"] += 1
                else:
                    tot["lc_sole_notonfire"] += 1
                sole_rows.append({
                    "tag": tag, "seed": r.get("seed"), "step": r.get("step"),
                    "ff": r.get("ff"), "pos": cell, "free": free,
                    "last_cell": eff_l, "cur_dist": cur,
                    "idle": r.get("idle"), "target": r.get("target_pos"),
                    "stalled_pre": r.get("stalled_pre"),
                    "moved": r.get("moved"), "post": tup(r.get("post_pos")),
                    "leash_d": man(free[0], eff_o),
                    "leash_ok": man(free[0], eff_o) <= MAXC,
                })
            if af_last == [] and free:
                tot["lc_emptied"] += 1
                if cur == 0:
                    tot["lc_emptied_onfire"] += 1
            elif af_last and not af_leash:
                tot["empty_by_leash"] += 1
    print("=" * 78)
    print("LAST_CELL GUARD - 13-RUN POST-62b4fbe SAMPLE (_ir_p3_POST_*.json)")
    print("=" * 78)
    for k in ("runs", "surv_calls", "empty_by_fire", "lc_excl_any",
              "lc_emptied", "lc_emptied_onfire", "empty_by_leash",
              "lc_sole", "lc_sole_onfire", "lc_sole_notonfire"):
        print("  %-22s %6d" % (k, tot[k]))
    print()
    print("EVERY CALL WHERE last_cell WAS THE ONLY FREE NEIGHBOUR")
    print("-" * 78)
    hdr = ("%-18s %5s %5s %-11s %-9s %-9s %4s %5s %6s %6s %5s"
           % ("combo", "seed", "step", "ff", "pos", "last=free",
              "cur", "idle", "stall", "moved", "lshOK"))
    print(hdr)
    for s in sorted(sole_rows, key=lambda x: (x["tag"], x["seed"], x["step"])):
        print("%-18s %5s %5s %-11s %-9s %-9s %4s %5s %6s %6s %5s" % (
            s["tag"], s["seed"], s["step"], s["ff"],
            "%d,%d" % s["pos"], "%d,%d" % s["last_cell"], s["cur_dist"],
            s["idle"], s["stalled_pre"], s["moved"], s["leash_ok"]))
    print()
    print("FIREFIGHTER DEATHS IN THE SAME SAMPLE (%d)" % len(deaths_all))
    print("-" * 78)
    for dd in sorted(deaths_all, key=lambda x: (x["tag"], x["seed"], x["step"])):
        print("  %-18s seed %-5s step %-4s %-11s pos %-9s stalled=%s cat=%s"
              % (dd["tag"], dd["seed"], dd["step"], dd["ff"],
                 "%s" % dd.get("pos"), dd.get("stalled"), dd.get("cat")))
    json.dump({"totals": tot, "sole_rows": sole_rows, "deaths": deaths_all},
              open(os.path.join(HERE, "_lc_analyze_out.json"), "w"),
              default=str, indent=1)


main()
