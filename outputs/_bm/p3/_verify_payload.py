import json
pre = json.load(open('E:/Projects/SAS/outputs/_bm/p3/pre/_bm_payload_bmpre.json'))
post = json.load(open('E:/Projects/SAS/outputs/_bm_payload_bmpost.json'))
def show(o, pref='', d=0):
    if isinstance(o, dict):
        for k, v in list(o.items())[:12]:
            if isinstance(v, (dict,)):
                print(pref+str(k), 'dict', len(v)); 
                if d < 2: show(v, pref+'   ', d+1)
            elif isinstance(v, list):
                print(pref+str(k), 'list', len(v), repr(v[:2])[:160])
            else:
                print(pref+str(k), repr(v)[:160])
show(pre)
