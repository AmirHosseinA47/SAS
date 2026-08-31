"""Seed-matched pre/post comparison for the idle-retreat latch + leash fix.

Reads per-seed probe JSONs (one seed per file) and reports, per combo:
  * rescued / victims dead / firefighter_deaths, seed-matched
  * latched-then-ESCAPED vs latched-and-still-DIED (the direct evidence axis)
  * whether an escape genuinely improved min-fire-distance, or merely moved
  * oscillation: A->B->A reversals, and direct last_cell violations where the
    probe recorded the anti-oscillation memory

usage: _ir_compare.py --pre "outputs/_ir_p2_BASE_*.json"
                      --post "outputs/_ir_p3_POST_*.json"
"""
import argparse, collections, glob, json, os


def load_many(pattern):
    """-> {(wind, roles, seed): run_dict}"""
    out = {}
    for p in sorted(glob.glob(pattern)):
        with open(p) as f:
            d = json.load(f)
        seeds = [int(s) for s in str(d["seeds"]).split(",")]
        assert len(seeds) == 1, "%s holds %d seeds; expected 1" % (p, len(seeds))
        out[(d["wind"], d["roles"], seeds[0])] = d
    return out


def ev_of(d):
    evs = d.get("evals") or []
    if not evs:
        return None
    e = evs[0]
    return (int(e.get("rescued") or 0), int(e.get("dead") or 0),
            int(e.get("firefighter_deaths") or 0))


def latch_metrics(d):
    """Escapes, stuck-latched calls and reversals, from the survival-move log."""
    m = collections.Counter()
    escapes = []
    by = collections.defaultdict(list)
    for s in d["surv"]:
        if not s.get("idle"):
            m["idle_calls_skipped_nonidle"] += 1
            continue
        m["idle_calls"] += 1
        if s.get("stalled_pre"):
            m["idle_calls_already_latched"] += 1
            if s.get("moved"):
                m["latched_ESCAPED"] += 1
                escapes.append(s)
            else:
                m["latched_stayed"] += 1
                if (s.get("n_free") or 0) > 0:
                    m["latched_stayed_though_free_cell_existed"] += 1
                    if s.get("strictly_better_exists"):
                        m["latched_stayed_though_BETTER_cell_existed"] += 1
        if s.get("moved"):
            by[(s["seed"], s["ff"])].append(s)
    # A->B->A reversals in consecutive idle survival moves
    rev = []
    for k, rows in by.items():
        rows.sort(key=lambda r: r["step"])
        for i in range(1, len(rows)):
            if rows[i]["post_pos"] == rows[i - 1]["pos"]:
                rev.append((k[0], k[1], rows[i - 1]["step"], rows[i]["step"],
                            tuple(rows[i - 1]["pos"]), tuple(rows[i - 1]["post_pos"])))
    m["idle_move_reversals"] = len(rev)
    # direct last_cell violations (probe3 only)
    viol = []
    for s in d["surv"]:
        lc = s.get("last_cell")
        if lc is not None and s.get("moved") and s.get("post_pos") == lc:
            viol.append((s["seed"], s["ff"], s["step"], tuple(s["pos"]),
                         tuple(s["post_pos"])))
    m["last_cell_violations"] = len(viol)
    m["last_cell_field_present"] = 1 if any(
        "last_cell" in s for s in d["surv"]) else 0
    return m, escapes, rev, viol


def death_latch_state(d):
    """Deaths split by whether the unit was latched when it died."""
    n_latched = sum(1 for x in d["deaths"] if x.get("stalled"))
    return len(d["deaths"]), n_latched


def mfd_after(d, seed, ff, step, horizon=10):
    tr = {r["step"]: r for r in d["fftrace"]
          if r["seed"] == seed and r["ff"] == ff}
    return [(tr.get(step + k) or {}).get("mfd") for k in range(0, horizon + 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre", required=True)
    ap.add_argument("--post", default="")
    ap.add_argument("--label-pre", default="pre-fix")
    ap.add_argument("--label-post", default="post-fix")
    a = ap.parse_args()

    pre = load_many(a.pre)
    post = load_many(a.post) if a.post else {}

    combos = sorted({(k[0], k[1]) for k in pre})
    grand = {"pre": [0, 0, 0], "post": [0, 0, 0]}

    for wind, roles in combos:
        seeds = sorted(s for (w, r, s) in pre if (w, r) == (wind, roles))
        print("=" * 78)
        print("D/%s  roles=%s   %d seed(s)" % (wind, roles, len(seeds)))
        print("=" * 78)
        if post:
            print("  seed |   rescued    | victims dead |  ff_deaths")
            print("  -----+--------------+--------------+--------------")
        else:
            print("  seed | rescued | victims dead | ff_deaths")
            print("  -----+---------+--------------+----------")
        sub = {"pre": [0, 0, 0], "post": [0, 0, 0]}
        for s in seeds:
            eb = ev_of(pre[(wind, roles, s)])
            ef = ev_of(post.get((wind, roles, s))) if post else None
            if eb is None:
                print("  %-5s NO EVAL DATA" % s)
                continue
            for i in range(3):
                sub["pre"][i] += eb[i]
            if ef is None and post:
                print("  %-5s %2d -> ???      | %2d -> ???     | %2d -> ???"
                      % (s, eb[0], eb[1], eb[2]))
                continue
            if ef is None:
                print("  %-5s %5d   | %10d   | %7d" % (s, eb[0], eb[1], eb[2]))
                continue
            for i in range(3):
                sub["post"][i] += ef[i]
            def cell(b, f):
                mark = ""
                if f > b:
                    mark = " (+%d)" % (f - b)
                elif f < b:
                    mark = " (-%d)" % (b - f)
                return "%2d -> %2d%-6s" % (b, f, mark)
            print("  %-5s %s| %s| %s" % (
                s, cell(eb[0], ef[0]), cell(eb[1], ef[1]), cell(eb[2], ef[2])))
        if post:
            print("  TOTAL %s| %s| %s" % (
                "%2d -> %2d%-6s" % (sub["pre"][0], sub["post"][0],
                                    " (%+d)" % (sub["post"][0] - sub["pre"][0])),
                "%2d -> %2d%-6s" % (sub["pre"][1], sub["post"][1],
                                    " (%+d)" % (sub["post"][1] - sub["pre"][1])),
                "%2d -> %2d%-6s" % (sub["pre"][2], sub["post"][2],
                                    " (%+d)" % (sub["post"][2] - sub["pre"][2]))))
        else:
            print("  TOTAL %5d   | %10d   | %7d" % tuple(sub["pre"]))
        for w in ("pre", "post"):
            for i in range(3):
                grand[w][i] += sub[w][i]
        print()

    print("=" * 78)
    print("GRAND TOTAL   rescued %d -> %d   victims dead %d -> %d   "
          "ff_deaths %d -> %d" % (
              grand["pre"][0], grand["post"][0],
              grand["pre"][1], grand["post"][1],
              grand["pre"][2], grand["post"][2]))
    print("=" * 78)
    print()

    for label, runs in (("PRE", pre), ("POST", post)):
        if not runs:
            continue
        agg = collections.Counter()
        all_rev, all_viol, all_esc = [], [], []
        tot_deaths = tot_latched_deaths = 0
        for k in sorted(runs):
            m, esc, rev, viol = latch_metrics(runs[k])
            agg.update(m)
            all_rev += rev
            all_viol += viol
            all_esc += [(k, e) for e in esc]
            nd, nl = death_latch_state(runs[k])
            tot_deaths += nd
            tot_latched_deaths += nl
        print("=" * 78)
        print("%s  LATCH BEHAVIOUR, all runs pooled" % label)
        print("=" * 78)
        print("  idle _survival_move calls                  : %d" % agg["idle_calls"])
        print("    already latched on entry                 : %d"
              % agg["idle_calls_already_latched"])
        print("      ESCAPED (latched and still moved)      : %d"
              % agg["latched_ESCAPED"])
        print("      stayed put                             : %d"
              % agg["latched_stayed"])
        print("        though a free cell existed           : %d"
              % agg["latched_stayed_though_free_cell_existed"])
        print("        though a strictly BETTER cell existed: %d"
              % agg["latched_stayed_though_BETTER_cell_existed"])
        print("  firefighter deaths                         : %d" % tot_deaths)
        print("    latched at the moment of death           : %d" % tot_latched_deaths)
        print("  idle A->B->A move reversals                : %d"
              % agg["idle_move_reversals"])
        for r in all_rev:
            print("      seed %s %s steps %d->%d  %s <-> %s" % r)
        if agg["last_cell_field_present"]:
            print("  direct last_cell violations               : %d"
                  % agg["last_cell_violations"])
            for v in all_viol:
                print("      seed %s %s step %d %s -> %s" % v)
        else:
            print("  direct last_cell violations               : n/a "
                  "(probe did not record last_cell)")
        if all_esc:
            print()
            print("  ESCAPES - min-fire-distance at the move and for 10 steps after")
            print("  (the test is 'escape', not merely 'moved')")
            for (k, e) in all_esc:
                seq = mfd_after(runs[k], e["seed"], e["ff"], e["step"])
                print("     %s/%s seed %s %s step %d  %s -> %s   dist %s -> %s"
                      % (k[0], k[1], e["seed"], e["ff"], e["step"],
                         tuple(e["pos"]), tuple(e["post_pos"]),
                         e.get("cur_dist"), e.get("post_dist")))
                print("        mfd t..t+10: %s" % ",".join(
                    "-" if x is None else str(x) for x in seq))
        print()


main()
