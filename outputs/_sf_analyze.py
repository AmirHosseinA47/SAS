"""searcherfire round - reproduces every headline number in searcherfire_part1.txt.

READ-ONLY over the committed corpus. Runs no simulation.
Usage (from outputs/):   E:\\Projects\\SAS\\.venv\\Scripts\\python.exe _sf_analyze.py

Pairs with _sf_cat.py (the per-step ground categoriser). The categoriser is
validated in two independent implementations at 0 disagreements against the
harness's own live-recorded uav_actions burning bit - 85,440 UAV-steps / 89 runs
here, 291,840 / 304 runs in the round's second implementation.

TWO ALIGNMENT FACTS THIS MODULE DEPENDS ON, both established empirically and both
easy to get wrong (see searcherfire_part1.txt s.0):
  1. burn_interval step numbers are 1-based and uav_steps/uav_actions are
     0-indexed: cell is burning at uav_steps index i iff some interval covers
     i+1. An open interval (end None) is closed at steps+1, not steps.
  2. selected_dir recorded at index i is the direction ALREADY APPLIED during
     that step - it moved the UAV from p[i-1] to p[i]. It is NOT the next move.
     So a REFUSED move is detected as p[i] == p[i-1], and the refused target is
     p[i] + delta(dir[i]). 100% of UAV-steps are explained this way (93.3% landed
     on the intended cell, 6.7% refused, 0.0% unexplained).
"""
import collections
import glob
import sys

from _sf_cat import load, categorise, cat_of

MX = [1, 0, -1, 0]
MY = [0, -1, 0, 1]
GRID = 50

SHIPPED_DEFAULT = ("_ffr_dcD_*.json", "_ffr_d4D_*.json", "_ffr_dfD_*.json",
                   "_ffr_drhD_*.json", "_ffr_flhD_*.json")


def _in_grid(x, y):
    return 0 <= x < GRID and 0 <= y < GRID


def depot_cells(run):
    """Depot footprint: the size x size block anchored at each depot origin."""
    bs = run.get("base_station") or {}
    size = int(bs.get("size") or 0)
    out = set()
    for ox, oy in (bs.get("depots") or []):
        for x in range(ox, ox + size):
            for y in range(oy, oy + size):
                out.add((x, y))
    return out


def validate_burning(pats):
    """Reconstructed 'burning' vs the harness's independently recorded bit."""
    total = bad = runs = 0
    for pat in pats:
        for p in sorted(glob.glob(pat)):
            run = load(p)
            if "uav_actions" not in run or "burn_intervals" not in run:
                continue
            runs += 1
            steps, burning, _fb, _bf = categorise(run)
            for i in range(steps):
                amap = {r[0]: r for r in run["uav_actions"][i]}
                cur = burning.get(i + 1, ())
                for r in run["uav_steps"][i]:
                    a = amap.get(r[0])
                    if a is None or r[1] is None:
                        continue
                    total += 1
                    key = "%d,%d" % (r[1][0], r[1][1])
                    if int(key in cur) != int(a[2]):
                        bad += 1
    return runs, total, bad


def exposure_table(pat):
    """Per-role category exposure, plus the map-availability denominator."""
    agg = collections.defaultdict(collections.Counter)
    avail = collections.Counter()
    for p in sorted(glob.glob(pat)):
        run = load(p)
        if "burn_intervals" not in run:
            continue
        steps, burning, firstburn, burnt_from = categorise(run)
        for i in range(steps):
            t = i + 1
            for r in run["uav_steps"][i]:
                if r[1] is None:
                    continue
                key = "%d,%d" % (r[1][0], r[1][1])
                c = cat_of(key, t, burning, firstburn, burnt_from)
                agg[r[2] or "?"][c] += 1
                agg[r[2] or "?"]["_n"] += 1
            nb = len(burning.get(t, ()))
            nburnt = sum(1 for _c, bf in burnt_from.items() if t >= bf)
            nhb = sum(1 for _c, f in firstburn.items() if f <= t)
            avail["burning"] += nb
            avail["burnt"] += nburnt
            avail["scorched"] += nhb - nb - nburnt
            avail["virgin"] += GRID * GRID - nhb
            avail["_n"] += GRID * GRID
    return agg, avail


def burning_by_context(pat):
    """Searcher burning-steps split into depot / return leg / edge pin / search."""
    C = collections.Counter()
    for p in sorted(glob.glob(pat)):
        run = load(p)
        if "burn_intervals" not in run:
            continue
        steps, burning, firstburn, burnt_from = categorise(run)
        dep = depot_cells(run)
        seq = collections.defaultdict(list)
        for i in range(steps):
            for r in run["uav_steps"][i]:
                if r[1] is None or r[2] != "victim_searcher":
                    continue
                seq[r[0]].append((i + 1, tuple(r[1]), r[3],
                                  r[5] if len(r) > 5 else ""))
        for _uid, s in seq.items():
            pinned = [False] * len(s)
            for i, (_t, cell, dirn, _b) in enumerate(s):
                if dirn is None or i == 0 or s[i - 1][1] != cell:
                    continue
                if not _in_grid(cell[0] + MX[dirn], cell[1] + MY[dirn]):
                    pinned[i] = True
            for i, (t, cell, _d, base) in enumerate(s):
                if cat_of("%d,%d" % cell, t, burning, firstburn, burnt_from) != "burning":
                    continue
                if base in ("docked", "charging"):
                    C["DEPOT-parked"] += 1
                elif cell in dep:
                    C["DEPOT-inside"] += 1
                elif base == "returning":
                    C["RETURN-leg"] += 1
                elif pinned[i]:
                    C["PIN (edge livelock)"] += 1
                else:
                    C["SEARCH (other)"] += 1
                C["TOTAL"] += 1
    return C


def refusals(pat):
    """Refused moves split into off-grid vs blocked-by-another-UAV, per role."""
    C = collections.defaultdict(collections.Counter)
    labels = collections.defaultdict(collections.Counter)
    for p in sorted(glob.glob(pat)):
        run = load(p)
        if "uav_steps" not in run:
            continue
        prev = {}
        for i in range(run["steps"]):
            amap = ({r[0]: r for r in run["uav_actions"][i]}
                    if "uav_actions" in run else {})
            for r in run["uav_steps"][i]:
                uid, cell, dirn, role = r[0], tuple(r[1]), r[3], r[2]
                if uid in prev and dirn is not None:
                    C[role]["steps"] += 1
                    if cell == prev[uid]:                      # the move was refused
                        C[role]["refused"] += 1
                        tgt = (cell[0] + MX[dirn], cell[1] + MY[dirn])
                        if not _in_grid(*tgt):
                            C[role]["refused_offgrid"] += 1
                            labels[role][(amap.get(uid) or [None, ""])[1]] += 1
                        else:
                            C[role]["refused_uavblock"] += 1
                prev[uid] = cell
    return C, labels


def pins(pats):
    """Distinct edge-pin events, de-duplicated across arms sharing a tuple."""
    out, tuples = {}, set()
    for pat in pats:
        for p in sorted(glob.glob(pat)):
            run = load(p)
            if "burn_intervals" not in run:
                continue
            tuples.add((run["wind"], run["roles"], run["seed"]))
            steps, burning, firstburn, burnt_from = categorise(run)
            seq, prev = collections.defaultdict(list), {}
            for i in range(steps):
                amap = ({r[0]: r for r in run["uav_actions"][i]}
                        if "uav_actions" in run else {})
                for r in run["uav_steps"][i]:
                    uid, cell, dirn = r[0], tuple(r[1]), r[3]
                    if r[2] != "victim_searcher" or dirn is None:
                        continue
                    refused_oob = False
                    if prev.get(uid) == cell:
                        tgt = (cell[0] + MX[dirn], cell[1] + MY[dirn])
                        refused_oob = not _in_grid(*tgt)
                    seq[uid].append((i + 1, cell, refused_oob,
                                     cat_of("%d,%d" % cell, i + 1, burning,
                                            firstburn, burnt_from),
                                     (amap.get(uid) or [None, ""])[1]))
                    prev[uid] = cell
            for uid, s in seq.items():
                i = 0
                while i < len(s):
                    if not s[i][2]:
                        i += 1
                        continue
                    j = i
                    while j + 1 < len(s) and s[j + 1][2] and s[j + 1][1] == s[i][1]:
                        j += 1
                    cats = [x[3] for x in s[i:j + 1]]
                    key = (run["wind"], run["roles"], run["seed"], uid, s[i][1])
                    rec = (j - i + 1, cats.count("burning"), cats.count("scorched"),
                           sum(1 for a, b in zip(cats, cats[1:])
                               if a != "burning" and b == "burning"),
                           s[i][0], sorted(set(x[4] for x in s[i:j + 1])))
                    if key not in out or rec[0] > out[key][0]:
                        out[key] = rec
                    i = j + 1
    return out, tuples


def main():
    print("== V1  reconstruction vs the harness's live burning bit ==")
    runs, total, bad = validate_burning(
        ("_ffr_dcD_*.json", "_ffr_d4D_*.json", "_ffr_ihbase_*.json", "_ffr_dcoff_*.json"))
    print("   runs=%d  UAV-steps=%d  disagreements=%d" % (runs, total, bad))

    print("\n== 1  category exposure, by role, vs map availability ==")
    for name, pat in (("dcD  (MODE 3 shipped default)", "_ffr_dcD_*.json"),
                      ("dcoff (MODE 0, same commit)", "_ffr_dcoff_*.json"),
                      ("ihbase (8520706 canonical 13)", "_ffr_ihbase_*.json"),
                      ("ihbasefresh (8520706 fresh 10)", "_ffr_ihbasefresh_*.json")):
        agg, avail = exposure_table(pat)
        print("  %s" % name)
        for role in sorted(agg):
            c = agg[role]
            n = c["_n"]
            print("    %-16s n=%-6d burning %5.2f%%  scorched %5.2f%%  "
                  "burnt %5.2f%%  virgin %5.2f%%"
                  % (role, n, 100 * c["burning"] / n, 100 * c["scorched"] / n,
                     100 * c["burnt"] / n, 100 * c["virgin"] / n))
        a = avail["_n"]
        if a:
            print("    %-16s        MAP AVAIL burning %5.2f%%  scorched %5.2f%%  "
                  "burnt %5.2f%%  virgin %5.2f%%"
                  % ("", 100 * avail["burning"] / a, 100 * avail["scorched"] / a,
                     100 * avail["burnt"] / a, 100 * avail["virgin"] / a))

    print("\n== 2  searcher burning exposure by context, MODE 0 -> MODE 3 ==")
    off, on = burning_by_context("_ffr_dcoff_*.json"), burning_by_context("_ffr_dcD_*.json")
    delta = on["TOTAL"] - off["TOTAL"]
    for k in ("DEPOT-parked", "DEPOT-inside", "RETURN-leg",
              "PIN (edge livelock)", "SEARCH (other)"):
        print("   %-22s %6d -> %6d   %+5d  %5.1f%% of the rise"
              % (k, off[k], on[k], on[k] - off[k], 100 * (on[k] - off[k]) / delta))
    print("   %-22s %6d -> %6d   %+5d" % ("TOTAL", off["TOTAL"], on["TOTAL"], delta))

    print("\n== 6  refused moves: off-grid vs blocked by another UAV ==")
    for name, pat in (("dcD", "_ffr_dcD_*.json"), ("dcoff", "_ffr_dcoff_*.json")):
        C, labels = refusals(pat)
        for role in sorted(C):
            c = C[role]
            print("   %-6s %-16s steps %6d  refused %5d = OFF-GRID %4d + UAV-blocked %4d"
                  % (name, role, c["steps"], c["refused"],
                     c["refused_offgrid"], c["refused_uavblock"]))
            if labels[role]:
                print("          off-grid refusals by hooked action label: %s"
                      % ", ".join("%s=%d" % (a or "(none)", v)
                                  for a, v in labels[role].most_common(3)))

    print("\n== 3  de-duplicated edge-pin events (shipped-default arms) ==")
    out, tuples = pins(SHIPPED_DEFAULT)
    print("   distinct tuples scanned: %d | distinct pin events: %d | pinned steps: %d"
          % (len(tuples), len(out), sum(v[0] for v in out.values())))
    for key, v in sorted(out.items(), key=lambda kv: -kv[1][0]):
        w, ro, sd, uid, cell = key
        edge = "".join(c for c, t in (("W", cell[0] == 0), ("E", cell[0] == GRID - 1),
                                      ("S", cell[1] == 0), ("N", cell[1] == GRID - 1)) if t)
        print("   %-6s %-8s %-11s %-5s %-9s len=%2d burn=%2d scor=%2d reig=%d edge=%-3s %s"
              % (w, ro, sd, uid, str(cell), v[0], v[1], v[2], v[3], edge or "NONE",
                 ",".join(v[5])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
