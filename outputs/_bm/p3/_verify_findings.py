import json,glob,os
tot=0
for f in sorted(glob.glob('E:/Projects/SAS/outputs/_bm/verify_*.json')):
    d=json.load(open(f,encoding='utf-8'))
    items = (d.get('errors') or d.get('findings') or d.get('problems') or []) if isinstance(d,dict) else d
    print(os.path.basename(f), type(d).__name__, (list(d.keys()) if isinstance(d,dict) else ''), 'n items', len(items))
    tot+=len(items)
    for it in items:
        t=json.dumps(it)
        if '766' in t or 'brace' in t.lower():
            print('   >>', t[:1000])
print('total findings', tot)
