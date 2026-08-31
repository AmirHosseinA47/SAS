"""Seed-matched comparison of the Part 2 what-if arms against stock (62b4fbe).

Stock outcomes come from the Part 1 sample (outputs/_ui_p1_*.json), which
_ui_basecheck.py already proved bit-identical to the 62b4fbe validation runs.

usage: _ui_wicompare.py
"""
import collections, glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
# (arm tag) -> (part1 combo file, wind, roles)
GROUPS = [("Eh", "east_half"), ("Ed", "east_default"), ("Sh", "south_half")]
ARMS = ["abort", "retreat"]


def load_stock():
    out = {}
    for tag, f in GROUPS:
        p = os.path.join(HERE, "_ui_p1_%s.json" % f)
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        for e in d["evals"]:
            out[(tag, int(e["seed"]))] = e
        tr = collections.defaultdict(dict)
        for r in d["fftrace"]:
            tr[(tag, int(r["seed"]), r["ff_id"])][r["step"]] = r["pos"]
        out.setdefault("_tr", {}).update(tr)
    return out


def main():
    stock = load_stock()
    print("=" * 78)
    print("PART 2 WHAT-IF - SEED-MATCHED AGAINST STOCK 62b4fbe")
    print("=" * 78)

    # harness neutrality control
    print()
    print("0. HARNESS NEUTRALITY (arm=none must reproduce stock exactly)")
    for tag, seeds in (("Eh404", [("Eh", 404)]), ("Ed101", [("Ed", 101)])):
        p = os.path.join(HERE, "_ui_wi_none_%s.json" % tag)
        if not os.path.exists(p):
            print("     %-8s MISSING" % tag)
            continue
        d = json.load(open(p))
        for e in d["evals"]:
            k = (seeds[0][0], int(e["seed"]))
            s = stock.get(k)
            if s is None:
                print("     %-8s no stock row" % tag)
                continue
            diffs = [kk for kk in ("firefighter_deaths", "rescued", "dead",
                                   "unreachable", "burnt_cells")
                     if s.get(kk) != e.get(kk)]
            print("     %-8s %s%s" % (tag, "MATCH" if not diffs else "DIFF",
                                      (" " + str(diffs)) if diffs else ""))

    for arm in ARMS:
        print()
        print("=" * 78)
        print("ARM = %s" % arm.upper())
        print("=" * 78)
        tot = collections.Counter()
        rows = []
        events = []
        for tag, _f in GROUPS:
            p = os.path.join(HERE, "_ui_wi_%s_%s.json" % (arm, tag))
            if not os.path.exists(p):
                continue
            d = json.load(open(p))
            events.extend([dict(e, combo=tag) for e in d["events"]])
            trn = collections.defaultdict(dict)
            for r in d["fftrace"]:
                trn[(tag, int(r["seed"]), r["ff_id"])][r["step"]] = r["pos"]
            for e in d["evals"]:
                seed = int(e["seed"])
                s = stock.get((tag, seed))
                if s is None:
                    continue
                row = {"combo": tag, "seed": seed}
                for k in ("firefighter_deaths", "rescued", "dead"):
                    row[k] = (s.get(k), e.get(k))
                    tot[k + "_stock"] += (s.get(k) or 0)
                    tot[k + "_arm"] += (e.get(k) or 0)
                # trajectory divergence
                div = None
                for key in [kk for kk in trn if kk[0] == tag and kk[1] == seed]:
                    a = stock["_tr"].get(key, {})
                    b = trn[key]
                    for st in sorted(set(a) & set(b)):
                        if a[st] != b[st]:
                            div = st if div is None else min(div, st)
                            break
                row["diverged_at"] = div
                rows.append(row)
        print("  combo seed | ff_deaths stock->arm | rescued | victims dead | "
              "trajectory diverges at step")
        for r in sorted(rows, key=lambda z: (z["combo"], z["seed"])):
            print("  %-5s %-4d | %8s -> %-3s | %2s -> %-3s | %2s -> %-3s | %s"
                  % (r["combo"], r["seed"], r["firefighter_deaths"][0],
                     r["firefighter_deaths"][1], r["rescued"][0], r["rescued"][1],
                     r["dead"][0], r["dead"][1],
                     r["diverged_at"] if r["diverged_at"] is not None else "never"))
        print("  ---")
        print("  TOTALS over these seeds: ff_deaths %d -> %d, rescued %d -> %d, "
              "victims dead %d -> %d"
              % (tot["firefighter_deaths_stock"], tot["firefighter_deaths_arm"],
                 tot["rescued_stock"], tot["rescued_arm"],
                 tot["dead_stock"], tot["dead_arm"]))
        print()
        print("  what the arm actually did at each release:")
        print("    combo seed ff          step pre        enc n_free | "
              "retreat_ran retreat_moved post       aborted")
        for e in sorted(events, key=lambda z: (z["combo"], z["seed"], z["step"])):
            print("    %-5s %-4s %-11s %4d %-10s %-3s %6s | %11s %13s %-10s %s"
                  % (e["combo"], e["seed"], e["ff"], e["step"], e["pre"],
                     "Y" if e["enclosed"] else "-", e["n_free"],
                     e["retreat_ran"], e["retreat_moved"], e["post"],
                     e["aborted"]))


main()
