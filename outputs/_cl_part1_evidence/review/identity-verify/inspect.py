import json, os, sys, glob, collections

OUT = r"E:\Projects\SAS\outputs"


def load(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8", "utf-16"):
        try:
            return json.loads(raw.decode(enc))
        except Exception:
            pass
    raise RuntimeError(p)


def fam(prefix):
    # non-recursive: only files directly in outputs/
    names = [n for n in os.listdir(OUT) if n.startswith("_ffr_%s_" % prefix) and n.endswith(".json")]
    return sorted(os.path.join(OUT, n) for n in names)


for prefix in ("uhD", "ugD", "ugKD", "ugKC", "ugmD"):
    files = fam(prefix)
    summ = collections.Counter()
    keysets = collections.Counter()
    for p in files:
        d = load(p)
        keysets[len(d)] += 1
        ua = d.get("uav_actions")
        summ[(
            d.get("repo"), d.get("steps"), json.dumps(d.get("extra_params"), sort_keys=True),
            json.dumps(d.get("params"), sort_keys=True)[:400] if False else None,
            "fm2p" in d, (len(ua) if isinstance(ua, list) else ua is None and "None"),
            d.get("roles"), d.get("wind"),
        )] += 1
    print("==", prefix, len(files), "files; key counts", dict(keysets))
    for k, v in sorted(summ.items(), key=lambda kv: str(kv[0])):
        print("   ", v, k)
    if files:
        d = load(files[0])
        print("   params sample:", d.get("params"))
        print("   keys:", sorted(d.keys()))
