"""Seed-matched equality check: does this round's probe reproduce 62b4fbe?

The Part 1 sample must be the SAME runs the idle-retreat round validated
(outputs/_ir_p3_POST_*.json), or every rate measured on top of it is measured
against a different world. The probe only wraps read-only methods, so the two
should agree row for row.

usage: _ui_basecheck.py
"""
import glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
COMBOS = [("east_half", "east", "half"), ("south_half", "south", "half"),
          ("east_default", "east", "default")]


def main():
    ok = True
    tot_new = tot_old = 0
    for tag, wind, roles in COMBOS:
        p = os.path.join(HERE, "_ui_p1_%s.json" % tag)
        if not os.path.exists(p):
            print("MISSING %s" % p)
            ok = False
            continue
        new = json.load(open(p))
        new_ev = {int(e["seed"]): e for e in new["evals"]}
        new_dt = {}
        for x in new["deaths"]:
            new_dt.setdefault(int(x["seed"]), []).append((x["step"], x["ff"],
                                                          tuple(x["pos"] or ())))
        for seed in sorted(new_ev):
            old_p = os.path.join(HERE, "_ir_p3_POST_%s_%s_%d.json"
                                 % (wind, roles, seed))
            if not os.path.exists(old_p):
                print("  %-13s %-4d  no 62b4fbe baseline file" % (tag, seed))
                ok = False
                continue
            old = json.load(open(old_p))
            oe = old["evals"][0]
            ne = new_ev[seed]
            od = sorted((x["step"], x["ff"], tuple(x["pos"] or ()))
                        for x in old["deaths"])
            nd = sorted(new_dt.get(seed, []))
            tot_new += len(nd)
            tot_old += len(od)
            same = True
            diffs = []
            for k in ("firefighter_deaths", "rescued", "dead", "rescue_rate",
                      "unreachable", "burnt_cells", "terminal_step"):
                if oe.get(k) != ne.get(k):
                    same = False
                    diffs.append("%s %s->%s" % (k, oe.get(k), ne.get(k)))
            if od != nd:
                same = False
                diffs.append("deaths %s -> %s" % (od, nd))
            print("  %-13s %-4d  %s%s" % (tag, seed, "MATCH" if same else "DIFF",
                                          ("  " + "; ".join(diffs)) if diffs else ""))
            ok = ok and same
    print()
    print("firefighter deaths: 62b4fbe baseline %d, this sample %d"
          % (tot_old, tot_new))
    print("RESULT: %s" % ("IDENTICAL - sample is the 62b4fbe sample"
                          if ok else "MISMATCH - investigate before using"))


main()
