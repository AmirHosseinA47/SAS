"""For each recorded D3 case: the co-marked victims' status just before the marking,
whether they were ever confirmed/assigned, and their end state. Named files only."""
import json, os

OUT = r"E:\Projects\SAS\outputs"
FILES = [
    "_ffr_dimA_east_def_101.json",
    "_ffr_dimB_east_def_101.json",
    "_ffr_f2cDRY_east_def_101.json",
    "_ffr_dimfreshbase_east_half_606.json",
    "_ffr_dimfreshbase_east_half_1010.json",
    "_ffr_d4off_east_half_1323590814.json",
    "_ffr_f2b404s12_south_half_404.json",
    "_ffr_dfpCB_west_half_303.json",
    "_ffr_dfpB_west_half_505.json",
    "_ffr_dcC_south_half_606.json",
    "_ffr_dfC_south_half_606.json",
]
tot = {}
for f in FILES:
    d = json.load(open(os.path.join(OUT, f)))
    esc = d["unreachable_escape_log"]
    steps = sorted({e["step"] for e in esc if e["cause"] == "geographically_isolated"})
    vs = d["victim_steps"]
    horizon = len(vs)
    carried = set()
    for s in steps:
        # carried victim at s-1 = victim bound to an exiting live unit at step s-1
        for r in d["ff_steps"][s - 2]:
            pass
    for s in steps:
        marked = [e["victim_id"] for e in esc if e["step"] == s and e["cause"] == "geographically_isolated"]
        before = {r[0]: r[2] for r in vs[s - 2]}
        ex = [e for e in d["exit_starts"] if e["step"] <= s]
        # carried = latest exit_start victim whose unit was exiting at s-1
        exiting_units = {r[0] for r in d["ff_steps"][s - 2] if r[4]}
        carried_v = {e["victim"] for e in ex if e["ff"] in exiting_units}
        live_units = [(r[0], r[1], r[2], r[4]) for r in d["ff_steps"][s - 2] if not r[5]]
        print(f, "mark step", s, "live units@s-1", live_units)
        for v in marked:
            ever_conf_after = sorted({r[2] for i in range(s - 1, horizon) for r in vs[i] if r[0] == v})
            end = [r for r in vs[-1] if r[0] == v][0]
            kind = "CARRIED" if v in carried_v else "other"
            print("   ", v, kind, "status@s-1=", before.get(v), "end=", end[2], end[1])
            if kind == "other":
                tot[before.get(v)] = tot.get(before.get(v), 0) + 1
print("other co-marked by status@s-1 (file-occurrences):", tot)
