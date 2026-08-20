import json, os, sys, collections
ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = [("D","north",101),("D","south",101),("A","west",505),("A","north",101)]

def load(s,w,sd,suf):
    p = os.path.join(ROOT, "_tf_%s_%s_%d%s.json" % (s,w,sd,suf))
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def metrics(d):
    sr = d["step_records"]
    cov_on = sum(1 for r in sr if r.get("coverage_active"))
    tgts = set()
    for r in sr:
        for key in ("gen_target_exec","gen_target_planner"):
            t = r.get(key)
            if t: tgts.add((int(t[0]), int(t[1])))
    dec = [r["decomp"] for r in sr
           if isinstance(r.get("decomp"), dict) and "error" not in r["decomp"]]
    rej = collections.Counter()
    vsteps = 0; vzero = 0; ncand_tot = 0
    for k in dec:
        for kk,vv in (k.get("rejected") or {}).items(): rej[kk] += vv
        for vid, pv in (k.get("posts") or {}).items():
            vsteps += 1
            n = int(pv.get("n_candidate", 0) or 0)
            ncand_tot += n
            if n == 0: vzero += 1
    return dict(
        steps=len(sr), cov_on=cov_on, cov_frac=cov_on/max(1,len(sr)),
        distinct=len(tgts), tgts=sorted(tgts),
        nd=d.get("nd"), ev=d.get("eval"),
        obs_s=d.get("obs_frac_searcher"), obs_a=d.get("obs_frac_all"),
        dec_steps=len(dec), vsteps=vsteps, vzero=vzero,
        vzero_pct=(100.0*vzero/vsteps if vsteps else 0.0),
        ncand_tot=ncand_tot, rej=dict(rej),
    )

suf = sys.argv[1] if len(sys.argv) > 1 else ""
label = sys.argv[2] if len(sys.argv) > 2 else ("PRE" if suf else "POST")
print("=== %s ===" % label)
hdr = "%-14s %6s %8s %9s %5s %8s %8s %7s %7s" % (
    "run","steps","cov_on","cov_frac","dist","obs_s","obs_a","vzero","vz%")
print(hdr)
tot_nd = 0
for s,w,sd in RUNS:
    d = load(s,w,sd,suf)
    if d is None:
        print("%-14s MISSING" % ("%s/%s %d"%(s,w,sd))); continue
    m = metrics(d)
    tot_nd += len(m["nd"] or [])
    print("%-14s %6d %8d %9.3f %5d %8.4f %8.4f %7s %7.1f" % (
        "%s/%s %d"%(s,w,sd), m["steps"], m["cov_on"], m["cov_frac"], m["distinct"],
        m["obs_s"], m["obs_a"], "%d/%d"%(m["vzero"],m["vsteps"]), m["vzero_pct"]))
    print("      nd=%s eval=%s" % (m["nd"], m["ev"]))
    print("      rejected=%s" % (m["rej"],))
    print("      targets=%s" % (m["tgts"],))
print("TOTAL never_detected marks across 4 runs: %d" % tot_nd)
