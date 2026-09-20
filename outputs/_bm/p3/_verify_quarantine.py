import json,glob,os,re
for f in sorted(glob.glob('E:/Projects/SAS/outputs/_bm/verify_*.json'))+sorted(glob.glob('E:/Projects/SAS/outputs/_bm/audit_*.json')):
    d=json.load(open(f,encoding='utf-8'))
    def walk(o,path=''):
        if isinstance(o,dict):
            for k,v in o.items(): walk(v,path+'/'+str(k))
        elif isinstance(o,list):
            for i,v in enumerate(o): walk(v,path+'/%d'%i)
        elif isinstance(o,str):
            if re.search(r'rewound|grep -r|recursive', o, re.I):
                print(os.path.basename(f), path, '::', o[:1200]); print()
    walk(d)
