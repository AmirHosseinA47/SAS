import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drops import streak_series
OUT = r"E:\Projects\SAS\outputs"
cases = [("east","half",606,115,"ff_unit_1"),("east","default",101,102,"ff_unit_1"),("east","half",404,133,"ff_unit_1")]
names = sorted(n for n in os.listdir(OUT) if n != "_firemech_rewound_20260914" and n.startswith("_ffr_") and n.endswith(".json"))
for w,r,seed,step,ff in cases:
    suf = "_%s_%s_%d.json" % (w, "def" if r=="default" else r, seed)
    for n in names:
        if not n.endswith(suf): continue
        raw = open(os.path.join(OUT,n),"rb").read()
        if b"replacement_after_blocked" not in raw: continue
        d = json.loads(raw)
        hits = [u for u in d.get("unassigns",[]) if u.get("reason")=="replacement_after_blocked" and int(u["step"])==step and u["ff"]==ff]
        if not hits: continue
        ss = streak_series(d, hits[0]["vid"], min(step+15, len(d["ff_steps"])))
        es = [e for e in d["exit_starts"] if e["ff"]==ff and e["victim"]==hits[0]["vid"] and e["step"]<=step]
        vdeath = next((s+1 for s,row in enumerate(d["victim_steps"]) if any(x[0]==hits[0]["vid"] and x[2]=="dead" for x in row)), None)
        others = [(x[0], x[1], x[2], x[4], x[5]) for x in d["ff_steps"][step-2] if x[0]!=ff]
        print(n, "pickup", es[-1]["step"] if es else None, "streak@drop-1", ss[step-1], "victim dead at", vdeath, "others@drop-1", others)
