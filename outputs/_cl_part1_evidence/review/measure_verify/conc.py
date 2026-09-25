import re, os, math, statistics as st
OUT = r"E:\Projects\SAS\outputs"
LOGS = ["_ug_wave.log", "_ug_crn_wave.log", "_ug_rbC_wave.log", "_ug_rbD_wave.log", "_uh_wave.log", "_r3chk_wave.log"]
ts_re = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]")
launch_re = re.compile(r"LAUNCH (\S+) running=")
done_re = re.compile(r" DONE (\S+) rc=(\d+) (\d+)s")
wall_re = re.compile(r"wall=(\d+)s")

runs = {}  # name -> dict
for lg in LOGS:
    with open(os.path.join(OUT, lg), encoding="utf-8", errors="replace") as f:
        for line in f:
            m = ts_re.match(line)
            if not m: continue
            t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            l = launch_re.search(line)
            if l:
                runs.setdefault(l.group(1), {})["launch"] = t
                runs[l.group(1)]["log"] = lg
            d = done_re.search(line)
            if d:
                r = runs.setdefault(d.group(1), {})
                r["done"] = t
                w = wall_re.search(line)
                r["wall"] = int(w.group(1)) if w else int(d.group(3))
                r["log"] = lg
runs = {k: v for k, v in runs.items() if "launch" in v and "done" in v}
iv = [(v["launch"], v["done"]) for v in runs.values()]

def avg_conc(a, b):
    # time-average number of sims (including self) over [a,b]
    if b <= a: return 1
    tot = 0
    for (x, y) in iv:
        o = min(b, y) - max(a, x)
        if o > 0: tot += o
    return tot / (b - a)

for k, v in runs.items():
    v["conc"] = avg_conc(v["launch"], v["done"])

def arm_tuple(name):
    p = name.split("_")
    return p[0], "_".join(p[1:])

by = {}
for k, v in runs.items():
    arm, tup = arm_tuple(k)
    by.setdefault(arm, {})[tup] = v
for arm in sorted(by):
    ws = [v["wall"] for v in by[arm].values()]
    cs = [v["conc"] for v in by[arm].values()]
    print(f"{arm:8s} n={len(ws):3d} mean_wall={st.mean(ws):6.0f} med={st.median(ws):6.0f} mean_box_conc={st.mean(cs):5.2f}")

# per-tuple ratio uhD/ugD and uhC/ugC; ugKD/ugD (CRN overhead, same steps)
def ratios(a, b):
    rs = []
    for tup in by.get(a, {}):
        if tup in by.get(b, {}):
            rs.append((by[a][tup]["wall"] / by[b][tup]["wall"], by[a][tup]["conc"], by[b][tup]["conc"]))
    return rs
for a, b in [("uhD", "ugD"), ("uhC", "ugC"), ("ugKD", "ugD"), ("ugKC", "ugC"), ("ugKY", "ugY")]:
    rs = ratios(a, b)
    if rs:
        print(f"{a}/{b}: n={len(rs)} median ratio={st.median([r[0] for r in rs]):.3f} mean={st.mean([r[0] for r in rs]):.3f} "
              f"conc {st.mean([r[1] for r in rs]):.2f} vs {st.mean([r[2] for r in rs]):.2f}")

# regression: log(wall) = a + b*log(steps) + c*log(conc) + tuple FE  (ff runs only; rb shards excluded)
import itertools
rows = []
for k, v in runs.items():
    arm, tup = arm_tuple(k)
    if arm.startswith("ugG"): continue
    steps = 360 if arm.startswith("uh") else 240
    crn = 1 if arm.startswith("ugK") else 0
    rows.append((tup, math.log(v["wall"]), math.log(steps / 240), math.log(v["conc"]), crn))
tups = sorted(set(r[0] for r in rows))
# demean within tuple
import collections
g = collections.defaultdict(list)
for r in rows: g[r[0]].append(r)
Y = []; X = []
for t, rs in g.items():
    if len(rs) < 2: continue
    my = st.mean(r[1] for r in rs); ms = st.mean(r[2] for r in rs); mc = st.mean(r[3] for r in rs); mk = st.mean(r[4] for r in rs)
    for r in rs:
        Y.append(r[1] - my); X.append((r[2] - ms, r[3] - mc, r[4] - mk))
# OLS 3 vars
def ols(X, Y):
    n = len(X); k = len(X[0])
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    XtY = [sum(X[i][a] * Y[i] for i in range(n)) for a in range(k)]
    # gaussian elimination
    M = [row[:] + [XtY[i]] for i, row in enumerate(XtX)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c])); M[c], M[p] = M[p], M[c]
        for r in range(k):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [M[r][j] - f * M[c][j] for j in range(k + 1)]
    return [M[i][k] / M[i][i] for i in range(k)]
b = ols(X, Y)
print(f"within-tuple OLS: elasticity steps={b[0]:.3f} conc={b[1]:.3f} crn_logdiff={b[2]:.3f} (n={len(Y)})")
