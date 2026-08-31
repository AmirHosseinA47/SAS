"""Per-death classification for the idle-retreat fix, keeping the RESIDUAL
visible instead of folding it into one pass/fail number.

Every firefighter death is put in exactly one bucket:

  A  not latched at death        - outside this fix's scope entirely
                                   (e.g. an assigned in-transit death)
  B  latched, an improving move existed, the unit TOOK it and still died
                                 - tried and was outrun
  C  latched, NO improving move existed, died
       C1  genuinely enclosed - every in-bounds neighbour burning
       C2  free neighbour(s) existed but none improved on standing still
           (the design deliberately declines these)
       C3  free neighbour(s) existed and were excluded by the LEASH
           (design doc 2.4 "accepted residual 2" - instrumented, not assumed)
       C4  free neighbour(s) existed and were excluded by last_cell only
  D  latched, an improving move existed, and the unit did NOT take it
                                 - this is a BUG. Must be zero post-fix.

and separately, the units that ESCAPED and were still alive at the end.

The "improving" test here is the distance half of the predicate
(cand_best_dist > cur_dist over cells that passed the real filter chain).
The risk half cannot be reconstructed offline, so bucket D is an UPPER bound
on real bugs and C2 a lower bound on genuine refusals; any D hit is inspected
by hand rather than trusted.

usage: _ir_residual.py --label POST "outputs/_ir_p3_POST_*.json"
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

    buckets = collections.Counter()
    rows = []
    escaped_alive, escaped_died = [], []
    total_escapes = 0

    for p in paths:
        with open(p) as fh:
            d = json.load(fh)
        combo = "%s/%s" % (d["wind"][0].upper(), d["roles"][0])
        surv = collections.defaultdict(list)
        for s in d["surv"]:
            surv[(s["seed"], s["ff"])].append(s)
        for k in surv:
            surv[k].sort(key=lambda s: s["step"])

        dead_keys = {(x["seed"], x["ff"]) for x in d["deaths"]}
        last_step = max((r["step"] for r in d["fftrace"]), default=0)

        # units that escaped a latched state at least once
        for k, calls in surv.items():
            esc = [s for s in calls
                   if s.get("idle") and s.get("stalled_pre") and s.get("moved")]
            if not esc:
                continue
            total_escapes += len(esc)
            rec = {"combo": combo, "seed": k[0], "ff": k[1],
                   "n_escapes": len(esc),
                   "first": esc[0]["step"], "last": esc[-1]["step"],
                   "dist_at_first": (esc[0].get("cur_dist"),
                                     esc[0].get("post_dist"))}
            # min-fire-distance 10 steps after the FIRST escape
            tr = {r["step"]: r for r in d["fftrace"]
                  if r["seed"] == k[0] and r["ff"] == k[1]}
            rec["mfd_after"] = [(tr.get(esc[0]["step"] + i) or {}).get("mfd")
                                for i in range(0, 11)]
            end = tr.get(last_step) or {}
            rec["alive_at_end"] = not end.get("dead", False)
            (escaped_alive if rec["alive_at_end"] else escaped_died).append(rec)

        for dth in d["deaths"]:
            key = (dth["seed"], dth["ff"])
            pre = [s for s in surv[key] if s["step"] <= dth["step"]]
            last = pre[-1] if pre else None
            base = {"combo": combo, "seed": dth["seed"], "ff": dth["ff"],
                    "step": dth["step"], "pos": dth["pos"]}
            if last is None or not (last.get("idle") and last.get("stalled_pre")):
                buckets["A"] += 1
                rows.append(dict(base, bucket="A", why="not latched at death"))
                continue
            cur = last.get("cur_dist")
            cbd = last.get("cand_best_dist")
            improving = (cbd is not None and cur is not None and cbd > cur)
            nfree = last.get("n_free") or 0
            xl = last.get("excl_leash") or 0
            xlc = last.get("excl_lastcell") or 0
            if improving and last.get("moved"):
                buckets["B"] += 1
                rows.append(dict(base, bucket="B",
                                 why="moved to a better cell, outrun anyway"))
            elif improving and not last.get("moved"):
                buckets["D"] += 1
                rows.append(dict(base, bucket="D",
                                 why="BUG: improving cell existed, did not move"))
            else:
                if nfree == 0:
                    b, why = "C1", "enclosed - every neighbour burning"
                elif xl > 0:
                    b, why = "C3", "free cell(s) excluded by the LEASH"
                elif xlc > 0 and (last.get("n_candidates") or 0) == 0:
                    b, why = "C4", "only free cell was last_cell"
                else:
                    b, why = "C2", "free cell(s) but none improving - declined"
                buckets[b] += 1
                rows.append(dict(base, bucket=b, why=why))
            rows[-1].update({"cur_d": cur, "cand_best": cbd, "free": nfree,
                             "cand": last.get("n_candidates"),
                             "xlsh": xl, "xlast": xlc,
                             "moved": last.get("moved")})

    n = sum(buckets.values())
    print("=" * 78)
    print("DEATH CLASSIFICATION - %s   (%d run(s), %d death(s))"
          % (a.label, len(paths), n))
    print("=" * 78)
    order = [("A", "not latched at death - outside this fix's scope"),
             ("B", "latched, TOOK a better cell, died anyway (outrun)"),
             ("C1", "latched, enclosed - every neighbour burning"),
             ("C2", "latched, free cell(s) but none improving - DECLINED"),
             ("C3", "latched, free cell(s) excluded by the LEASH"),
             ("C4", "latched, only free cell was last_cell"),
             ("D", "latched, improving cell existed, DID NOT MOVE  <-- BUG")]
    for k, lbl in order:
        v = buckets.get(k, 0)
        flag = "   *** MUST BE ZERO ***" if (k == "D" and v) else ""
        print("  %-3s %-58s %3d%s" % (k, lbl, v, flag))
    resid = sum(buckets.get(k, 0) for k in ("C1", "C2", "C3", "C4"))
    print("  %-62s %3d" % ("RESIDUAL (C1+C2+C3+C4): nothing better was reachable",
                           resid))
    print("  %-62s %3d" % ("IN SCOPE AND ACTED ON (B):", buckets.get("B", 0)))
    print()
    print("  per-death detail")
    print("  %-4s %-14s %5s %-9s %5s %5s %5s %5s %5s %5s  %s" % (
        "bkt", "combo/seed/ff", "step", "pos", "cur_d", "best", "free",
        "cand", "xlsh", "moved", "why"))
    for r in sorted(rows, key=lambda r: (r["bucket"], r["combo"], r["seed"])):
        print("  %-4s %-14s %5s %-9s %5s %5s %5s %5s %5s %5s  %s" % (
            r["bucket"], "%s/%s/%s" % (r["combo"], r["seed"], r["ff"][-6:]),
            r["step"], str(tuple(r["pos"])) if r["pos"] else "-",
            r.get("cur_d"), r.get("cand_best"), r.get("free"),
            r.get("cand"), r.get("xlsh"), r.get("moved"), r["why"]))

    print()
    print("=" * 78)
    print("ESCAPES - units that were latched and moved anyway")
    print("=" * 78)
    print("  escape events total                    : %d" % total_escapes)
    print("  units that escaped and were ALIVE at end: %d" % len(escaped_alive))
    print("  units that escaped and later DIED       : %d" % len(escaped_died))
    for title, group in (("ALIVE AT END", escaped_alive),
                         ("ESCAPED BUT LATER DIED", escaped_died)):
        if not group:
            continue
        print()
        print("  %s" % title)
        for r in group:
            print("    %s seed %-5s %-10s  %d escape(s), steps %d..%d, "
                  "fire-dist %s -> %s at the first"
                  % (r["combo"], r["seed"], r["ff"], r["n_escapes"],
                     r["first"], r["last"], r["dist_at_first"][0],
                     r["dist_at_first"][1]))
            print("       min-fire-dist t..t+10: %s" % ",".join(
                "-" if x is None else str(x) for x in r["mfd_after"]))


main()
