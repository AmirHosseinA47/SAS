import json, os
BASE = r"E:\Projects\SAS\outputs"
tups = [("east", s) for s in (101,111,202,222,303,333,404,444,505,606,707,808,909)] + [("south", s) for s in (101,202,303,404,505)]
tot = {"legs":0,"excess":0,"stalled":0,"drops":0,"iso":0,"offexit_boundary_touch":0}
for w, s in tups:
    p = os.path.join(BASE, "_ffr_ugD_%s_half_%d.json" % (w, s))
    d = json.load(open(p))
    H = W = 50
    comp = {(c["ff"], c["victim"]): c for c in d["completions"]}
    ff_by_step = d["ff_steps"]
    legs = []
    for e in d["exit_starts"]:
        x, y = e["ff_pos"]
        dd = min(x, H-1-x, y, W-1-y)
        c = None
        for cc in d["completions"]:
            if cc["ff"] == e["ff"] and cc["victim"] == e["victim"] and cc["step"] >= e["step"]:
                c = cc; break
        if c:
            L = c["step"] - e["step"]
            # touch non-exit boundary before completion?
            touch = 0
            for st in range(e["step"], c["step"]):
                if st-1 < len(ff_by_step):
                    for row in ff_by_step[st-1]:
                        if row[0] == e["ff"] and row[1]:
                            px, py = row[1]
                            if (px in (0, H-1) or py in (0, W-1)) and [px,py] != c["exit_target"]:
                                touch = 1
            legs.append((e["step"], e["ff"], e["victim"], dd, L, touch))
        else:
            legs.append((e["step"], e["ff"], e["victim"], dd, None, 0))
    drops = [u for u in d["unassigns"] if u["reason"] == "replacement_after_blocked"]
    # drops of exiting units: check ff exiting flag at step
    exdrops = 0
    for u in drops:
        st = u["step"]
        for e in d["exit_starts"]:
            if e["ff"] == u["ff"] and e["victim"] == u["vid"] and e["step"] <= st:
                c = [cc for cc in d["completions"] if cc["ff"] == u["ff"] and cc["victim"] == u["vid"] and cc["step"] >= e["step"]]
                if not c or c[0]["step"] > st:
                    exdrops += 1
    iso = len(d.get("unreachable_escape_log") or [])
    exc = [l for l in legs if l[4] is not None and l[4] > l[3]]
    stl = [l for l in legs if l[4] is not None and l[4] > l[3] + 5]
    brk = [l for l in legs if l[4] is None]
    tch = [l for l in legs if l[5]]
    print("%-5s %4d legs=%d excess>0=%d stalled=%d broken=%d offexit_touch=%d exiting_drops=%d esc_log=%d rescued=%s" % (
        w, s, len(legs), len(exc), len(stl), len(brk), len(tch), exdrops, iso, d["eval"]["rescued"]))
    for l in legs:
        if l[4] is None or l[4] > l[3] or l[5]:
            print("        ", l)
