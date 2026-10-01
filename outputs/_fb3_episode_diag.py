import sys, collections
_TAGS = sys.argv[1:]
sys.path.insert(0, r"E:\Projects\SAS\outputs"); sys.path.insert(0, r"E:\Projects\SAS")
sys.argv = ["x"]
import _fb3_analyze as A
for tag in _TAGS or ["fb3bd", "fb3bd2", "fb3bf2", "fb3vs3", "fx3mS", "fx3mS2", "fb3vs0", "fb3lo", "fb3lo2"]:
    runs = A.load(tag)
    for k, d in sorted(runs.items()):
        b, p, a = A.searcher_o(d)
        if not b:
            continue
        times = A.det_times(d)
        t_all = max(times.values()) if all(t is not None for t in times.values()) else None
        term = d.get("terminal_step")
        rows = d["rows_uav"]
        for e in b:
            uid, s0, s1 = e[0], e[1], e[2]
            prev = [str([u for u in rows[s - 1] if u[0] == uid][0][8]) for s in range(max(1, s0 - 6), s0)]
            und = sum(1 for t in times.values() if t is None or t > s0)
            print("%-7s %-4s %s %3d-%3d len %3d %-9s | term %s t_all %s undetected@start %d | before %s" % (
                tag, k, uid, s0, s1, e[3], e[4], term, t_all, und, collections.Counter(prev).most_common(2)))
