import json, sys
def load(p):
    raw = open(p, 'rb').read()
    for enc in ('utf-8', 'utf-16', 'utf-8-sig'):
        try:
            return json.loads(raw.decode(enc))
        except Exception:
            pass
    raise SystemExit('cannot decode ' + p)
d = load(sys.argv[1])
for k, v in d.items():
    t = type(v).__name__
    n = len(v) if hasattr(v, '__len__') else ''
    sample = ''
    if isinstance(v, list) and v:
        sample = repr(v[0])[:200]
    elif isinstance(v, dict):
        sample = repr(list(v.items())[:2])[:200]
    else:
        sample = repr(v)[:200]
    print(k, t, n, sample)
