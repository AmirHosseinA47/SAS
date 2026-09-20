import json, hashlib, os
pre = json.load(open('E:/Projects/SAS/outputs/_bm/p3/pre/_sc_control_bmpre.json'))
post = json.load(open('E:/Projects/SAS/outputs/_sc_control_bmpost.json'))
print(type(pre), (list(pre.keys()) if isinstance(pre, dict) else len(pre)))
def walk(o, d=0, maxd=3, pref=''):
    if isinstance(o, dict):
        for k, v in o.items():
            t = type(v).__name__
            s = ''
            if isinstance(v, (str, int, float, bool)) or v is None:
                s = repr(v)[:100]
            elif isinstance(v, list):
                s = 'list len %d' % len(v)
            elif isinstance(v, dict):
                s = 'dict keys %d' % len(v)
            print(pref + str(k), t, s)
            if d < maxd and isinstance(v, dict):
                walk(v, d+1, maxd, pref + '   ')
walk(pre, 0, 3)
