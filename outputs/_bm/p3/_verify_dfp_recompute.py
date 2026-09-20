"""Independent recompute of the depot-fireproof Part 1 corpus numbers. Reads JSON only."""
import glob, json, os, statistics, hashlib

BASE = "E:/Projects/SAS/outputs"
files = sorted(glob.glob(os.path.join(BASE, "_ffr_f3OFF_*.json")))
print("files", len(files))
NW = {(x, y) for x in range(0, 5) for y in range(45, 50)}
SE = {(x, y) for x in range(45, 50) for y in range(0, 5)}
rows = []
first_keys = None
for fp in files:
    d = json.load(open(fp))
    if first_keys is None:
        first_keys = sorted(d.keys())
        print("top-level keys (%d):" % len(first_keys), first_keys)
    name = os.path.basename(fp)[len("_ffr_f3OFF_"):-5]
    bi = d.get("burn_intervals") or {}
    first = {}
    for k, iv in bi.items():
        x, y = map(int, k.split(","))
        if iv:
            first[(x, y)] = min(s for s, e in iv)
    nw = {c: first[c] for c in NW if c in first}
    se = {c: first[c] for c in SE if c in first}
    allf = list(nw.values()) + list(se.values())
    fd = min(allf) if allf else None
    term = d.get("terminal_step")
    ev = d.get("eval") or {}
    h = hashlib.md5(json.dumps(bi, sort_keys=True).encode()).hexdigest()[:10]
    rows.append(dict(name=name, steps=d.get("steps"), term=term, nw=len(nw), se=len(se),
                     nwf=min(nw.values()) if nw else None, sef=min(se.values()) if se else None,
                     fd=fd, n=len(nw) + len(se), burnt=ev.get("burnt_cells"), nbi=len(first), h=h,
                     ev=ev))
for r in rows:
    print("%-18s steps %s term %5s | NW %5s/%2d SE %5s/%2d | first %5s | n %2d | burnt %s | everburned cells %d | bi-hash %s"
          % (r["name"], r["steps"], r["term"], r["nwf"], r["nw"], r["sef"], r["se"], r["fd"], r["n"], r["burnt"], r["nbi"], r["h"]))

n = len(rows)
reach = [r for r in rows if r["fd"] is not None]
print("reach", len(reach), "of", n, "%.1f%%" % (100.0 * len(reach) / n))
print("SE reach", sum(1 for r in rows if r["se"] > 0), "NW reach", sum(1 for r in rows if r["nw"] > 0))
print("never", [r["name"] for r in rows if r["fd"] is None])
before_strict = [r for r in reach if r["term"] is not None and r["fd"] < r["term"]]
term_none = [r for r in reach if r["term"] is None]
after = [r for r in reach if r["term"] is not None and r["fd"] >= r["term"]]
equal = [r for r in reach if r["term"] is not None and r["fd"] == r["term"]]
print("before strict", len(before_strict), "term None", len(term_none), [r["name"] for r in term_none],
      "after", len(after), [r["name"] for r in after], "equal", len(equal))
print("before incl none: %d of %d = %.1f%%" % (len(before_strict) + len(term_none), n, 100.0 * (len(before_strict) + len(term_none)) / n))
fs = sorted(r["fd"] for r in reach)
print("first ignition: min", fs[0], "median(stat)", statistics.median(fs), "median(idx)", fs[len(fs) // 2], "max", fs[-1], "n", len(fs))
tc = sorted(r["n"] for r in rows)
print("cells: min", tc[0], "median", statistics.median(tc), "max", tc[-1], "mean", sum(tc) / len(tc), "total", sum(tc))
print("SE all 25:", sum(1 for r in rows if r["se"] == 25), "SE 24:", sum(1 for r in rows if r["se"] == 24),
      "other SE>0:", [(r["name"], r["se"]) for r in rows if 0 < r["se"] < 24])
print("NW counts:", [(r["name"], r["nw"], r["nwf"]) for r in rows if r["nw"] > 0])
# distinct fire histories
hs = {}
for r in rows:
    hs.setdefault(r["h"], []).append(r["name"])
print("distinct burn_interval histories:", len(hs))
for h, names in hs.items():
    if len(names) > 1:
        print("   shared:", names)
dist_reach = sum(1 for h, names in hs.items() if any(rr["fd"] is not None for rr in rows if rr["name"] == names[0]))
print("distinct histories reaching a depot:", dist_reach, "of", len(hs))
# the two never runs
for r in rows:
    if r["fd"] is None:
        print("NEVER run", r["name"], "ever-burned cells in whole grid:", r["nbi"], "eval burnt_cells", r["burnt"])
        print("   eval:", {k: v for k, v in r["ev"].items() if not isinstance(v, (list, dict))})
