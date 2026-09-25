import json, os, sys
OUT = r"E:\Projects\SAS\outputs"
cases = [("_ffr_fmES_east_half_101.json", "ff_unit_0", "victim_0", 126, 142),
         ("_ffr_dcC_east_half_909.json", "ff_unit_1", "victim_0", 123, 140)]
for fn, ff, vid, a, b in cases:
    d = json.load(open(os.path.join(OUT, fn), encoding="utf-8"))
    bi = d["burn_intervals"]
    # burn_intervals format probe
    print(fn, type(bi), (list(bi.items())[:2] if isinstance(bi, dict) else bi[:2]))
    burning = {}
    def is_burn(cell, s):
        k = "%d,%d" % cell
        iv = None
        if isinstance(bi, dict):
            iv = bi.get(k) or bi.get(str(tuple(cell)))
        if not iv:
            return False
        for x in iv:
            lo, hi = x[0], x[1]
            if lo <= s and (hi is None or s < hi):
                return True
        return False
    vs = d["victim_steps"]
    for s in range(a, b):
        row = d["ff_steps"][s - 1] if s - 1 < len(d["ff_steps"]) else []
        ffr = [r for r in row if r[0] == ff]
        vrow = vs[s - 1] if s - 1 < len(vs) else None
        vr = [r for r in (vrow or []) if isinstance(r, list) and r and r[0] == vid]
        print(s, ffr, vr)
    print("unassigns", [u for u in d["unassigns"] if a <= (u[0] if isinstance(u, list) else u.get("step", 0)) <= b])
    print("assigns", [u for u in d["assigns"] if a <= (u[0] if isinstance(u, list) else u.get("step", 0)) <= b])
    print("exit_starts", [u for u in d["exit_starts"] if a - 60 <= (u[0] if isinstance(u, list) else u.get("step", 0)) <= b])
