import json, os, collections
OUT = r"E:\Projects\SAS\outputs"
def load(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8", "utf-16"):
        try: return json.loads(raw.decode(enc))
        except Exception: pass
for prefix in ("ugA", "ugX", "ugC", "mgD"):
    names = sorted(n for n in os.listdir(OUT) if n.startswith("_ffr_%s_" % prefix) and n.endswith(".json"))
    c = collections.Counter()
    for n in names:
        d = load(os.path.join(OUT, n))
        c[(d.get("repo"), d.get("steps"), json.dumps(d.get("extra_params"), sort_keys=True), "fm2p" in d, d.get("uav_actions") is not None)] += 1
    print(prefix, len(names), [n.replace("_ffr_%s_" % prefix, "").replace(".json", "") for n in names][:30])
    for k, v in c.items(): print("   ", v, k)
