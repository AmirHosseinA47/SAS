"""For the D2 convertible legs: was any OTHER live, on-grid, non-exiting unit present on
each step from pickup to the hold-replay completion? If none, the isolation streak runs
and a HOLD-alone arm (SERVED 0) is written off at pickup+29."""
import json
O = "E:/Projects/SAS/outputs/"
CASES = [
    ("_ffr_uhD_east_half_1291443119.json", "ff_unit_1", 84, 148, 163),
    ("_ffr_uhY_east_half_1291443119.json", "ff_unit_1", 84, 148, 163),
    ("_ffr_fmDRY_east_half_101.json", "ff_unit_0", 100, 135, 150),
    ("_ffr_f2cEFS_east_half_404.json", "ff_unit_1", 104, 133, 152),
]
for fn, carrier, pick, drop, comp in CASES:
    d = json.load(open(O + fn, encoding="utf-8"))
    fs = d["ff_steps"]
    print("==", fn, "carrier", carrier, "pickup", pick, "drop", drop, "hold-replay completion", comp)
    no_other = []
    for s in range(pick, min(comp, len(fs) + 1) + 1):
        row = fs[s - 1]   # event stamped s is in ff_steps[s-1]
        others = [r for r in row if r[0] != carrier]
        live = [r for r in others if (not r[5]) and r[1] is not None and (not r[4]) and str(r[2]).lower() != "dead"]
        if not live:
            no_other.append(s)
        if s in (pick, pick + 1, drop - 1, drop, drop + 1) or s == comp:
            print("  step", s, [(r[0], r[1], r[2], "asg" if r[3] else "-", "EXIT" if r[4] else "-", "DEAD" if r[5] else "") for r in others])
    # longest run of consecutive steps with no other live start, from pickup
    runs, cur, prev = [], [], None
    for s in no_other:
        if prev is not None and s == prev + 1:
            cur.append(s)
        else:
            if cur: runs.append(cur)
            cur = [s]
        prev = s
    if cur: runs.append(cur)
    print("  steps with no other live on-grid non-exiting unit:", len(no_other),
          " runs:", [(r[0], r[-1], len(r)) for r in runs])
    um = [u for u in d.get("unreachable_escape_log", []) if pick <= u["step"] <= comp + 30]
    print("  escape log in window:", um[:5])
