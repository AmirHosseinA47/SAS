"""searcherfix D5 OFFLINE PRE-CHECK. No simulation. Read-only over outputs/*.json.

QUESTION (searcherfix_part1.txt 8.6(i)): the legality guard pushes a pinned
searcher INWARD off the boundary. At the inward cell the guard does NOT fire,
because the upstream direction there is in bounds - so the pre-existing
in-bounds fall-through at uav_executor.py:2321 could hand back a direction
pointing back OUT, producing a two-cell alternation.

This bounds that risk from the RECORDED corpus, before spending a wave:

  A. ARRIVAL INTENT. For every pin, look at the step on which the searcher
     ARRIVED at the pin cell. Was it already holding the direction it would be
     pinned on (i.e. the off-grid direction was latched BEFORE arrival)? If so,
     the guard breaks the latch at the moment of substitution and the planner
     is not re-deciding outward each step.

  B. INWARD-CELL OUTWARD INTENT, the direct form of the question. At the
     predecessor cell (the inward neighbour the guard would send it back to),
     what direction was the searcher holding, and did it point outward toward
     the pin cell?

  C. HISTORICAL EXIT BEHAVIOUR. When a pin actually ends, does the searcher
     leave and STAY away, or does it come straight back to the pin cell? This
     is the closest recorded analogue of the post-guard step and is the
     strongest available evidence about the 2-cycle.

  D. BASE RATE OF EDGE 2-CYCLES today, for context: how often does any searcher
     alternate between exactly two cells for >= 4 steps, with at least one of
     them on the outermost ring?

Run:  cd outputs && E:\Projects\SAS\.venv\Scripts\python.exe _sfx_precheck.py
"""
import collections
import glob
import json
import os

from _sf_cat import load, categorise, cat_of

MX = [1, 0, -1, 0]
MY = [0, -1, 0, 1]
NAME = ["E", "S", "W", "N"]

SHIPPED_DEFAULT = ("_ffr_dcD_*.json", "_ffr_d4D_*.json", "_ffr_dfD_*.json",
                   "_ffr_drhD_*.json", "_ffr_flhD_*.json")


def dims(run):
    p = run.get("params") or {}
    h = int(p.get("HEIGHT") or run.get("HEIGHT") or 50)
    w = int(p.get("WIDTH") or run.get("WIDTH") or 50)
    return h, w


def in_grid(x, y, h, w):
    return 0 <= x < h and 0 <= y < w


def searcher_seq(run):
    """uid -> [(step, cell, selected_dir, refused, refused_oob)] for searchers.

    selected_dir[t] is the direction APPLIED in step t (written pre-move at
    uav_executor.py:144, consumed in advance() the same step). A refused move is
    detected as cell[t] == cell[t-1].
    """
    h, w = dims(run)
    steps = run["steps"]
    seq, prev = collections.defaultdict(list), {}
    for i in range(steps):
        for r in run["uav_steps"][i]:
            uid, cell, role, dirn = r[0], tuple(r[1]), r[2], r[3]
            if role != "victim_searcher" or dirn is None:
                continue
            refused = prev.get(uid) == cell
            oob = False
            if refused:
                tgt = (cell[0] + MX[dirn], cell[1] + MY[dirn])
                oob = not in_grid(tgt[0], tgt[1], h, w)
            seq[uid].append((i + 1, cell, int(dirn), refused, oob))
            prev[uid] = cell
    return seq


def pins_in(run):
    """Maximal same-cell runs of off-grid refusals. Same definition as
    _sf_analyze.pins(): cell unchanged AND intended cell off the grid."""
    out = []
    for uid, s in searcher_seq(run).items():
        i = 0
        while i < len(s):
            if not s[i][4]:
                i += 1
                continue
            j = i
            while j + 1 < len(s) and s[j + 1][4] and s[j + 1][1] == s[i][1]:
                j += 1
            out.append((uid, s, i, j))
            i = j + 1
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    files = []
    for pat in SHIPPED_DEFAULT:
        files.extend(sorted(glob.glob(pat)))

    A_latched = A_total = 0
    B_outward = B_total = 0
    C_returned = C_exit = 0
    C_gaps = []
    cyc_edge = cyc_all = 0
    rows = []
    tuples = set()
    seen_key = {}

    for p in files:
        try:
            run = load(p)
        except Exception:
            continue
        if "uav_steps" not in run or "burn_intervals" not in run:
            continue
        h, w = dims(run)
        key3 = (run["wind"], run["roles"], run["seed"])
        tuples.add(key3)
        steps, burning, firstburn, burnt_from = categorise(run)

        # --- A / B / C, per pin -------------------------------------------
        for uid, s, i, j in pins_in(run):
            cell = s[i][1]
            pinned_dir = s[i][2]
            key = (key3[0], key3[1], key3[2], uid, cell)
            length = j - i + 1
            if key in seen_key and seen_key[key] >= length:
                continue
            seen_key[key] = length

            # A: was the off-grid direction already held on the ARRIVAL step?
            arrival = s[i - 1] if i - 1 >= 0 else None
            A_total += 1
            latched = arrival is not None and arrival[2] == pinned_dir
            if latched:
                A_latched += 1

            # B: THE DECISIVE TEST. The guard sends the searcher back to the
            # cell it came FROM (recorded at i-2, since the cell at i-1 is
            # already the pin cell - the arrival move succeeded). Ask whether
            # the planner was ALREADY STARVED at that origin cell, evidenced by
            # the direction there being identical to the step before it. If it
            # was, then after the guard the latched direction is the INWARD one
            # and it is re-emitted -> the searcher keeps going inward and there
            # is no 2-cycle. If it was not, the planner re-decided at the origin
            # and could decide outward again.
            origin = s[i - 2] if i - 2 >= 0 else None
            before = s[i - 3] if i - 3 >= 0 else None
            starved_at_origin = (
                origin is not None and before is not None
                and origin[2] == before[2]
            )
            if origin is not None and before is not None:
                B_total += 1
                if starved_at_origin:
                    B_outward += 1
            outward = starved_at_origin

            # C: exit behaviour - after the pin ends, does it come back?
            back_in = None
            if j + 1 < len(s):
                C_exit += 1
                for k in range(j + 1, min(j + 21, len(s))):
                    if s[k][1] == cell:
                        back_in = s[k][0] - s[j][0]
                        break
                if back_in is not None:
                    C_returned += 1
                    C_gaps.append(back_in)

            cats = [cat_of("%d,%d" % s[t][1], s[t][0], burning, firstburn, burnt_from)
                    for t in range(i, j + 1)]
            rows.append((key3[0], key3[1], key3[2], uid, cell, length, s[i][0],
                         NAME[pinned_dir], cats.count("burning"),
                         "YES" if latched else "no",
                         (NAME[arrival[2]] if arrival else "-"),
                         "OUT" if outward else "in",
                         ("+%d" % back_in) if back_in is not None else "never"))

        # --- D: base rate of two-cell alternation today --------------------
        for uid, s in searcher_seq(run).items():
            cells = [x[1] for x in s]
            i = 0
            while i < len(cells):
                j = i
                while j + 1 < len(cells) and len(set(cells[i:j + 2])) <= 2:
                    j += 1
                run_cells = cells[i:j + 1]
                changes = sum(1 for a, b in zip(run_cells, run_cells[1:]) if a != b)
                if (j - i + 1) >= 4 and len(set(run_cells)) == 2 and changes >= 2:
                    cyc_all += 1
                    if any(c[0] in (0, h - 1) or c[1] in (0, w - 1) for c in set(run_cells)):
                        cyc_edge += 1
                i = j + 1 if j > i else i + 1

    print("=" * 78)
    print("searcherfix D5 OFFLINE PRE-CHECK - no simulation")
    print("=" * 78)
    print("files scanned            : %d" % len(files))
    print("distinct (wind,roles,seed): %d" % len(tuples))
    print("distinct pin events       : %d" % len(rows))
    print()
    print("%-6s %-5s %-11s %-5s %-8s %4s %5s %4s %4s %-8s %-6s %-4s %s"
          % ("wind", "roles", "seed", "uid", "cell", "len", "start", "dir",
             "burn", "latched", "arrdir", "pts", "returns"))
    for r in sorted(rows, key=lambda x: -x[5]):
        print("%-6s %-5s %-11s %-5s %-8s %4d %5d %4s %4d %-8s %-6s %-4s %s"
              % (r[0], r[1], str(r[2]), r[3], "(%d,%d)" % r[4], r[5], r[6],
                 r[7], r[8], r[9], r[10], r[11], r[12]))

    print()
    print("A. ARRIVAL INTENT - was the off-grid direction ALREADY held on the")
    print("   step the searcher arrived at the pin cell?")
    print("     %d of %d pins  (%.1f%%)" %
          (A_latched, A_total, 100.0 * A_latched / max(1, A_total)))
    print("   If high: the direction is latched BEFORE arrival, so the guard's")
    print("   substitution breaks the latch rather than fighting a planner that")
    print("   re-decides outward every step.")
    print()
    print("B. WAS THE PLANNER ALREADY STARVED AT THE ORIGIN CELL - the cell")
    print("   the guard sends the searcher back to? Evidenced by the direction")
    print("   there being identical to the step before it (the latch running).")
    print("     %d of %d  (%.1f%%)" %
          (B_outward, B_total, 100.0 * B_outward / max(1, B_total)))
    print("   HIGH means: after the guard, the LATCHED direction is the INWARD")
    print("   one and is re-emitted, so the searcher keeps going inward.")
    print("   LOW means the planner re-decides at the origin and could send it")
    print("   back out - that is the 2-cycle precondition.")
    print()
    print("C. HISTORICAL EXIT - when a pin ends, does the searcher return to the")
    print("   pin cell within 20 steps?")
    print("     %d of %d exits returned" % (C_returned, C_exit))
    if C_gaps:
        print("     gaps: %s" % sorted(C_gaps))
    print("   This is the closest recorded analogue of the post-guard step. Few")
    print("   or no returns is direct evidence against a sustained 2-cycle.")
    print()
    print("D. BASE RATE TODAY - two-cell alternations of >= 4 steps by searchers:")
    print("     %d total, %d of them touching the outermost ring" % (cyc_all, cyc_edge))
    print("   This is the population the fix must not grow.")


if __name__ == "__main__":
    main()
