import json, os, collections
OUT = r"E:/Projects/SAS/outputs"
RUNS = ["xsTD_east_def_1749069988", "xsTD_east_half_2070841104", "xsTD_east_half_294124329",
        "xsTD_south_half_1048395951", "xsTK_east_def_1420331661", "xsTK_south_half_903347495",
        "xsTY_east_half_2070841104"]
MODE = ("_firefight_suspended", "_idle_retreat_origin", "_idle_retreat_steps", "_idle_retreat_stalled", "_idle_retreat_last_cell")
agg = collections.Counter()
persist = collections.Counter()
for r in RUNS:
    t = json.load(open(os.path.join(OUT, "_ffr_%s.xstrace.json" % r), encoding="utf-8"))
    carry_steps = {(a["step"], a["ff"]) for a in t["advances"] if a.get("carrying")}
    for a in t["advances"]:
        if not a.get("carrying"):
            continue
        agg["carrying_advances"] += 1
        agg["mode_reads"] += sum(1 for x in a.get("reads") or [] if x in MODE)
        agg["prepare_not_none"] += a.get("prepare") is not None
        chains = [m["chain"][0] for m in a.get("moves") or []]
        agg["moves"] += len(chains)
        agg["moves_not_move_toward"] += sum(1 for c in chains if c != "_move_toward")
        f = a["fields"]
        if f.get("_idle_retreat_origin") is not None or f.get("_idle_retreat_last_cell") is not None:
            persist["idle_state_set_while_carrying"] += 1
    agg["accessor_calls_on_carrying"] += sum(1 for c in t.get("accessor_calls") or [] if (c["step"], c["ff"]) in carry_steps)
    agg["outside_moves"] += len(t.get("outside_moves") or [])
print(dict(agg)); print(dict(persist))
