"""Count end-of-run route_blocked latches per committed harness arm.

A latch = a firefighter whose LAST recorded ff_steps row is status
route_blocked, not dead. ff_steps rows are
[unit_id, pos, status, assigned, exiting, dead].
Read-only.
"""
import glob, json, os, collections, re

BASE = os.path.dirname(os.path.abspath(__file__))
rows = []
for p in sorted(glob.glob(os.path.join(BASE, "_ffr_*.json"))):
    b = os.path.basename(p)[len("_ffr_"):-len(".json")]
    m = re.match(r"^([A-Za-z0-9]+)_(east|south|west|north)_([A-Za-z0-9]+)_(\d+)$", b)
    if not m:
        continue
    arm, wind, roles, seed = m.group(1), m.group(2), m.group(3), m.group(4)
    try:
        d = json.load(open(p))
    except Exception:
        continue
    ffs = d.get("ff_steps") or []
    if not ffs:
        continue
    last = ffs[-1]
    latched = []
    for r in last:
        try:
            uid, pos, status, assigned, exiting, dead = r[0], r[1], r[2], r[3], r[4], r[5]
        except Exception:
            continue
        if str(status).strip().lower() == "route_blocked" and not dead:
            latched.append((str(uid), tuple(pos) if pos else None))
    rows.append({
        "arm": arm, "wind": wind, "roles": roles, "seed": seed,
        "mode": (d.get("extra_params") or {}).get("BASE_STATION_MODE"),
        "retmech": (d.get("extra_params") or {}).get("BASE_STATION_RETURN_MECHANISM"),
        "latched": latched, "term": d.get("terminal_step"),
    })

by_arm = collections.defaultdict(lambda: {"runs": 0, "latch_runs": 0, "units": 0,
                                          "mode": None, "detail": []})
for r in rows:
    a = by_arm[r["arm"]]
    a["runs"] += 1
    a["mode"] = r["mode"] if a["mode"] is None else a["mode"]
    if r["latched"]:
        a["latch_runs"] += 1
        a["units"] += len(r["latched"])
        a["detail"].append("%s/%s/%s %s" % (r["wind"], r["roles"], r["seed"],
                                            ",".join("%s%s" % u for u in r["latched"])))

print("%-14s %-5s %-6s %-11s %-6s  %s" % ("arm", "mode", "runs", "latch_runs", "units", "detail"))
print("-" * 110)
for arm in sorted(by_arm, key=lambda k: (str(by_arm[k]["mode"]), k)):
    a = by_arm[arm]
    print("%-14s %-5s %-6d %-11d %-6d  %s" % (
        arm, a["mode"], a["runs"], a["latch_runs"], a["units"], "; ".join(a["detail"])))

print()
mode_tot = collections.defaultdict(lambda: {"runs": 0, "latch_runs": 0, "units": 0})
for r in rows:
    k = r["mode"]
    mode_tot[k]["runs"] += 1
    if r["latched"]:
        mode_tot[k]["latch_runs"] += 1
        mode_tot[k]["units"] += len(r["latched"])
print("BY BASE_STATION_MODE (extra_params; None = arm predates the feature)")
for k in sorted(mode_tot, key=lambda x: str(x)):
    v = mode_tot[k]
    print("  mode=%-5s runs=%-4d latch_runs=%-3d units=%-3d rate=%.3f" % (
        k, v["runs"], v["latch_runs"], v["units"], v["latch_runs"] / max(1, v["runs"])))
