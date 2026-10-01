"""fix3b Part 3 (read-only): searcher in-fire and smoke exposure split by the label of the PREVIOUS row (targeting step vs
any other) and by phase (pre = an undetected victim remains, post = every victim detected).
usage (repo root): .venv/Scripts/python.exe outputs/_fb3_exposure_split.py [tag ...]"""
import collections
import sys

sys.path.insert(0, r"E:\Projects\SAS\outputs")
TAGS, sys.argv = sys.argv[1:], sys.argv[:1]
import _fb3_analyze as A  # noqa: E402

for tag in TAGS or ("fx3mS", "fb3bf", "fx3mS2", "fb3bf2", "fb3bd2", "fb3vs0", "fb3vs3", "fb3lo"):
    C = collections.Counter()
    for d in A.load(tag).values():
        rows = d["rows_uav"]
        mf = (d.get("mf2") or {}).get("uav") or []
        times = A.det_times(d)
        t_all = max(times.values()) if all(t is not None for t in times.values()) else None
        for t, (r, m) in enumerate(zip(rows, mf)):
            prev = {x[0]: str(x[8]) for x in rows[t - 1]} if t > 0 else {}
            for u in m:
                if u[1] != "victim_searcher" or not isinstance(u[4], int):
                    continue
                k = "tgt" if prev.get(u[0]) == "victim_search_targeting" else "other"
                ph = "pre" if (t_all is None or t + 1 < t_all) else "post"
                C[(k, ph, "n")] += 1
                C[(k, ph, "f")] += u[4]
                C[(k, ph, "s")] += u[5] if isinstance(u[5], int) else 0
    parts = ["%s/%s fire %d/%d=%.2f%% smoke %d=%.2f%%" % (
        k, ph, C[(k, ph, "f")], C[(k, ph, "n")], 100.0 * C[(k, ph, "f")] / C[(k, ph, "n")], C[(k, ph, "s")],
        100.0 * C[(k, ph, "s")] / C[(k, ph, "n")]) for k in ("tgt", "other") for ph in ("pre", "post") if C[(k, ph, "n")]]
    print(tag, " | ".join(parts))
