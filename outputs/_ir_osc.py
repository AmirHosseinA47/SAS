"""Oscillation audit, pre vs post.

A "reversal" in the coarse detector is any consecutive PAIR OF MOVES by one
unit where the second lands on the first's origin cell. That is not the same
as ping-ponging: two moves 80 steps apart are not an oscillation. This splits
reversals by the step gap and by whether either move came out of a latched
state (i.e. from the path this round adds), and separately counts direct
`last_cell` violations, which are the thing that would actually indicate the
anti-oscillation guard had been broken.

usage: _ir_osc.py --label POST "outputs/_ir_p3_POST_*.json"
"""
import argparse, collections, glob, json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--label", default="RUN")
    a = ap.parse_args()

    paths = []
    for f in a.files:
        paths.extend(sorted(glob.glob(f)) or [f])

    gaps = collections.Counter()
    from_latched = []
    tight = []
    viol = []
    n_moves = 0
    has_lc = False

    for p in paths:
        with open(p) as fh:
            d = json.load(fh)
        combo = "%s/%s" % (d["wind"][0].upper(), d["roles"][0])
        by = collections.defaultdict(list)
        for s in d["surv"]:
            if "last_cell" in s:
                has_lc = True
            if s.get("moved"):
                by[(s["seed"], s["ff"])].append(s)
                n_moves += 1
            lc = s.get("last_cell")
            if lc is not None and s.get("moved") and s.get("post_pos") == lc:
                viol.append((combo, s["seed"], s["ff"], s["step"],
                             tuple(s["pos"]), tuple(s["post_pos"])))
        for k, rows in by.items():
            rows.sort(key=lambda r: r["step"])
            for i in range(1, len(rows)):
                if rows[i]["post_pos"] != rows[i - 1]["pos"]:
                    continue
                gap = rows[i]["step"] - rows[i - 1]["step"]
                gaps[gap] += 1
                rec = (combo, k[0], k[1], rows[i - 1]["step"], rows[i]["step"],
                       gap, bool(rows[i - 1].get("stalled_pre")),
                       bool(rows[i].get("stalled_pre")))
                if gap == 1:
                    tight.append(rec)
                if rows[i - 1].get("stalled_pre") or rows[i].get("stalled_pre"):
                    from_latched.append(rec)

    total = sum(gaps.values())
    print("=" * 78)
    print("OSCILLATION AUDIT - %s   (%d run(s), %d survival-move moves)"
          % (a.label, len(paths), n_moves))
    print("=" * 78)
    print("  idle+assigned move reversals (any step gap) : %d" % total)
    print("  step-gap histogram                          : %s"
          % dict(sorted(gaps.items())))
    print("  TIGHT reversals (gap == 1, real ping-pong)  : %d" % len(tight))
    for t in tight:
        print("      %s seed %s %s steps %d->%d gap %d  latched_pre=(%s,%s)" % t)
    print("  reversals where EITHER move came from a latched state : %d"
          % len(from_latched))
    for t in from_latched:
        print("      %s seed %s %s steps %d->%d gap %d  latched_pre=(%s,%s)" % t)
    if has_lc:
        print("  DIRECT last_cell violations (the real guard test)      : %d"
              % len(viol))
        for v in viol:
            print("      %s seed %s %s step %s  %s -> %s" % v)
    else:
        print("  DIRECT last_cell violations                            : n/a "
              "(probe did not record last_cell)")


main()
