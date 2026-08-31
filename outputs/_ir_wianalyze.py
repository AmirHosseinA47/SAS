"""Analyse outputs/_ir_wi_*.json from _ir_whatif.py.

observe mode: what the proposed logic WOULD have decided at each latched idle
              call, on a stock (unchanged) trajectory.
apply   mode: what actually happened with the proposed logic installed -
              escapes, oscillation, and min-fire-distance after an escape.
"""
import argparse, collections, json, os


def load(p):
    with open(p) as f:
        return json.load(f)


def observe(d, path):
    dec = d["decisions"]
    print("=" * 78)
    print("OBSERVE  %s   wind=%s roles=%s seeds=%s" % (
        os.path.basename(path), d["wind"], d["roles"], d["seeds"]))
    print("=" * 78)
    print("latched idle _survival_move calls seen : %d" % len(dec))
    if not dec:
        return []
    c = collections.Counter()
    for r in dec:
        c["calls"] += 1
        c["stock_moved"] += 1 if r.get("stock_moved") else 0
        c["stale_origin"] += 1 if r.get("stale_origin") else 0
        c["would_move"] += 1 if r.get("would_move") else 0
        if r.get("would_move"):
            c["  via_" + r["path"]] += 1
            if r.get("would_ideal"):
                c["  target_is_ideal_standoff"] += 1
            g = r.get("dist_gain") or 0
            if g > 0:
                c["  gains_fire_distance"] += 1
            elif g == 0:
                c["  same_distance_lower_risk"] += 1
            else:
                c["  closer_but_ideal_or_safer"] += 1
        else:
            if (r.get("n_free") or 0) == 0:
                c["  stay: genuinely enclosed"] += 1
            elif (r.get("n_candidates") or 0) == 0:
                c["  stay: no candidate survived the filters"] += 1
            else:
                c["  stay: candidates existed but none improving"] += 1
    print()
    print("  stock behaviour (unchanged run):")
    print("    calls where the stock code moved the unit : %d" % c["stock_moved"])
    print("    (expected 0 - the latched idle path is a bare return)")
    print()
    print("  what the FIX would have done at those same moments:")
    print("    would move                                : %d / %d" % (
        c["would_move"], c["calls"]))
    print("    would stay put (latch verdict re-confirmed): %d" % (
        c["calls"] - c["would_move"]))
    for k in sorted(c):
        if k.startswith("  "):
            print("      %-45s %d" % (k.strip(), c[k]))
    print("    of all calls, origin provably stale (d>6) : %d" % c["stale_origin"])

    # per-unit episode view
    print()
    print("  PER-UNIT LATCH EPISODES (consecutive latched idle calls):")
    by = collections.defaultdict(list)
    for r in dec:
        by[(r["seed"], r["ff"])].append(r)
    for k in sorted(by):
        rows = sorted(by[k], key=lambda r: r["step"])
        mv = [r for r in rows if r["would_move"]]
        print("    seed %s %s : %d latched calls, steps %d-%d, "
              "%d would-move, first at step %s" % (
                  k[0], k[1], len(rows), rows[0]["step"], rows[-1]["step"],
                  len(mv), mv[0]["step"] if mv else "-"))
        for r in rows:
            print("       step %3d pos %-9s d_org %2d %-20s free %d cand %d "
                  "cur_d %d %s" % (
                      r["step"], str(tuple(r["pos"])), r["d_origin"],
                      ("STALE:" + r["path"]) if r["stale_origin"] else r["path"],
                      r["n_free"], r["n_candidates"], r["cur_dist"],
                      ("-> MOVE %s d %d->%d risk %d->%d%s" % (
                          tuple(r["would_target"]), r["cur_dist"],
                          r["would_dist"], r["cur_risk"], r["would_risk"],
                          " IDEAL" if r["would_ideal"] else ""))
                      if r["would_move"] else "-> stay"))
    return dec


def apply_mode(d, path, baseline_deaths=None):
    print("=" * 78)
    print("APPLY  %s   wind=%s roles=%s seeds=%s" % (
        os.path.basename(path), d["wind"], d["roles"], d["seeds"]))
    print("=" * 78)
    print("firefighter deaths with the fix installed : %d" % len(d["deaths"]))
    for x in d["deaths"]:
        print("   seed %s step %s %s at %s stalled=%s cat=%s" % (
            x["seed"], x["step"], x["ff"], x["pos"], x["stalled"], x["cat"]))
    if baseline_deaths is not None:
        print("baseline (stock) deaths for the same seeds: %d" % len(baseline_deaths))
        for x in baseline_deaths:
            print("   seed %s step %s %s at %s" % (
                x["seed"], x["step"], x["ff"], x["pos"]))

    ml = d["movelog"]
    print()
    print("MOVES MADE INSIDE _survival_move : %d  (idle: %d, from a latched "
          "state: %d)" % (
              len(ml),
              sum(1 for m in ml if m["idle"]),
              sum(1 for m in ml if m["latched_pre"])))

    # oscillation: A -> B -> A in a unit's consecutive survival moves
    print()
    print("OSCILLATION CHECK (consecutive survival-move reversals A->B->A):")
    by = collections.defaultdict(list)
    for m in ml:
        by[(m["seed"], m["ff"])].append(m)
    total_rev = 0
    for k in sorted(by):
        rows = sorted(by[k], key=lambda m: m["step"])
        revs = []
        for i in range(1, len(rows)):
            if rows[i]["dst"] == rows[i - 1]["src"]:
                revs.append((rows[i - 1]["step"], rows[i]["step"],
                             tuple(rows[i - 1]["src"]), tuple(rows[i - 1]["dst"]),
                             rows[i - 1]["idle"], rows[i]["idle"],
                             rows[i - 1]["latched_pre"], rows[i]["latched_pre"]))
        total_rev += len(revs)
        if revs:
            print("   seed %s %s : %d reversal(s)" % (k[0], k[1], len(revs)))
            for r in revs:
                print("      steps %d->%d  %s <-> %s   idle=(%s,%s) "
                      "latched_pre=(%s,%s)" % r)
    print("   total reversals: %d" % total_rev)
    print("   NOTE: a reversal on an ASSIGNED move is _assigned_one_step_retreat,")
    print("         which has no anti-oscillation term and is unchanged by this fix.")

    # did escapes actually improve fire distance?
    print()
    print("ESCAPES FROM A LATCHED STATE - did fire distance actually improve?")
    esc = [m for m in ml if m["latched_pre"] and m["idle"]]
    if not esc:
        print("   none in this run")
    tr = collections.defaultdict(dict)
    for r in d["fftrace"]:
        tr[(r["seed"], r["ff"])][r["step"]] = r
    for m in esc:
        key = (m["seed"], m["ff"])
        after = []
        for k in range(1, 11):
            row = tr[key].get(m["step"] + k)
            after.append(row.get("mfd") if row else None)
        print("   seed %s %s step %d  %s -> %s  fire-dist %s -> %s ; next 10 "
              "steps: %s" % (
                  m["seed"], m["ff"], m["step"], tuple(m["src"]), tuple(m["dst"]),
                  m["pre_dist"], m["post_dist"],
                  ",".join("-" if a is None else str(a) for a in after)))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--baseline", default="",
                    help="optional _ir_p2_*.json to read stock deaths from")
    a = ap.parse_args()
    base_deaths = None
    if a.baseline and os.path.exists(a.baseline):
        base_deaths = load(a.baseline).get("deaths")
    for p in a.files:
        d = load(p)
        if d["mode"] == "observe":
            observe(d, p)
        else:
            apply_mode(d, p, base_deaths)
        print()


main()
