"""Shape check: do the investigation's headline findings survive on a
DIFFERENT set of seeds?

Re-derives the four load-bearing ratios from any set of probe JSONs and prints
them next to the investigation's 13-run figures. The point is the SHAPE (large,
same-direction), not the exact percentages, which a small sample cannot pin
down.

usage: _ir_shape.py --label FRESH outputs/_ir_p2_FRESH_*.json
"""
import argparse, collections, glob, json


REFERENCE = {
    "latched_idle_calls": 92,
    "latched_idle_noop": 92,
    "latched_noop_free_cell": 82,
    "latched_noop_better_cell": 46,
    "zero_cand_idle": 30,
    "zero_cand_enclosed": 10,
    "zero_cand_artifact": 20,
    "zero_cand_leash": 17,
    "zero_cand_lastcell": 3,
    "leash_excl_stale_origin": 17,
    "deaths": 13,
    "deaths_latched_with_escape": 10,
}
MAX = 6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--label", default="SAMPLE")
    a = ap.parse_args()

    paths = []
    for f in a.files:
        paths.extend(sorted(glob.glob(f)) or [f])

    c = collections.Counter()
    seeds = set()
    deaths = []
    for p in paths:
        with open(p) as fh:
            d = json.load(fh)
        for s in str(d["seeds"]).split(","):
            seeds.add((d["wind"], d["roles"], int(s)))
        # per-call stats, idle only
        surv_by = collections.defaultdict(list)
        for s in d["surv"]:
            surv_by[(s["seed"], s["ff"])].append(s)
            if not s.get("idle"):
                continue
            if s.get("stalled_pre"):
                c["latched_idle_calls"] += 1
                if not s.get("moved"):
                    c["latched_idle_noop"] += 1
                    if (s.get("n_free") or 0) > 0:
                        c["latched_noop_free_cell"] += 1
                    if s.get("strictly_better_exists"):
                        c["latched_noop_better_cell"] += 1
            if s.get("n_candidates") == 0:
                c["zero_cand_idle"] += 1
                if (s.get("n_free") or 0) == 0:
                    c["zero_cand_enclosed"] += 1
                else:
                    c["zero_cand_artifact"] += 1
                    if (s.get("excl_leash") or 0) > 0:
                        c["zero_cand_leash"] += 1
                        org, pos = s.get("origin"), s.get("pos")
                        dd = (abs(pos[0] - org[0]) + abs(pos[1] - org[1])
                              if org else 0)
                        if dd > MAX:
                            c["leash_excl_stale_origin"] += 1
                    if (s.get("excl_lastcell") or 0) > 0:
                        c["zero_cand_lastcell"] += 1
        # deaths: was the unit latched with an escape at the lethal moment?
        for dth in d["deaths"]:
            c["deaths"] += 1
            key = (dth["seed"], dth["ff"])
            pre = sorted([s for s in surv_by[key] if s["step"] <= dth["step"]],
                         key=lambda s: s["step"])
            last = pre[-1] if pre else None
            latched_escape = bool(
                last and last.get("stalled_pre") and not last.get("moved")
                and (last.get("n_free") or 0) > 0)
            if latched_escape:
                c["deaths_latched_with_escape"] += 1
            deaths.append((d["wind"], d["roles"], dth["seed"], dth["ff"],
                           dth["step"], dth["pos"], latched_escape,
                           (last or {}).get("n_free"),
                           (last or {}).get("n_candidates"),
                           (last or {}).get("excl_leash")))

    print("=" * 78)
    print("SHAPE CHECK  label=%s   %d run(s), %d death(s)"
          % (a.label, len(seeds), c["deaths"]))
    print("  combos: %s" % ", ".join(
        sorted("%s/%s" % (w, r) for (w, r) in {(w, r) for (w, r, s) in seeds})))
    print("=" * 78)
    rows = [
        ("firefighter deaths", "deaths", None),
        ("  ...burned while LATCHED with a free escape cell",
         "deaths_latched_with_escape", "deaths"),
        ("latched idle _survival_move calls", "latched_idle_calls", None),
        ("  ...that did nothing", "latched_idle_noop", "latched_idle_calls"),
        ("  ...noop though a free cell existed",
         "latched_noop_free_cell", "latched_idle_calls"),
        ("  ...noop though a strictly BETTER cell existed",
         "latched_noop_better_cell", "latched_idle_calls"),
        ("idle zero-candidate verdicts", "zero_cand_idle", None),
        ("  ...genuine enclosure", "zero_cand_enclosed", "zero_cand_idle"),
        ("  ...filter artifact", "zero_cand_artifact", "zero_cand_idle"),
        ("      by the leash", "zero_cand_leash", "zero_cand_idle"),
        ("      by last_cell", "zero_cand_lastcell", "zero_cand_idle"),
        ("  leash exclusions with a PROVABLY STALE origin (d>6)",
         "leash_excl_stale_origin", "zero_cand_leash"),
    ]
    print("  %-52s %10s %12s" % ("", a.label, "13-run ref"))
    for label, key, denom in rows:
        v = c[key]
        r = REFERENCE[key]
        vs = str(v)
        rs = str(r)
        if denom:
            dv, dr = c[denom], REFERENCE[denom]
            vs = "%d/%d %s" % (v, dv, "(%d%%)" % round(100.0 * v / dv) if dv else "")
            rs = "%d/%d %s" % (r, dr, "(%d%%)" % round(100.0 * r / dr) if dr else "")
        print("  %-52s %10s %12s" % (label, vs, rs))

    print()
    print("  DEATHS IN THIS SAMPLE")
    print("  %-18s %5s %-9s %-8s %5s %5s %5s" % (
        "combo/seed/ff", "step", "pos", "latched+", "free", "cand", "xlsh"))
    for w, r, s, ff, st, pos, le, nf, nc, xl in sorted(deaths, key=lambda x: x[:5]):
        print("  %-18s %5d %-9s %-8s %5s %5s %5s" % (
            "%s/%s/%s/%s" % (w[0].upper(), r[0], s, ff[-6:]),
            st, str(tuple(pos)) if pos else "-", "ESCAPE" if le else "-",
            nf, nc, xl))


main()
