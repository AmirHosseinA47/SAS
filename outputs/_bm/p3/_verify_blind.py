import json, collections, statistics as st
B='E:/Projects/SAS/outputs/_bm/blind/'
def load(f): return json.load(open(B+f,encoding='utf-8'))
r1=load('_results.json'); r2=load('_results2.json'); r3=load('_results3.json')
print('counts',len(r1),len(r2),len(r3),'total',len(r1)+len(r2)+len(r3))
print('r1 keys',sorted(r1[0].keys()))
print('r2 keys',sorted(r2[0].keys()))
print('r3 keys',sorted(r3[0].keys()))
def grp(rows,keyf,tl,br):
    g=collections.defaultdict(list)
    for r in rows: g[keyf(r)].append(r)
    for k in sorted(g):
        v=g[k]
        print(' ',k,'n',len(v),'TL',[x[tl] for x in v],'BR',[x[br] for x in v],'meanTL %.2f meanBR %.2f'%(st.mean(x[tl] for x in v),st.mean(x[br] for x in v)))
    return g
print('--- round1 by variant')
g1=grp(r1,lambda r:r['variant'],'tl_conf','br_conf')
print('--- round1 by form')
grp(r1,lambda r:r['variant'].split('_')[1],'tl_conf','br_conf')
print('--- round2 by variant')
grp(r2,lambda r:r['variant'],'tl_conf','br_conf')
print('--- round2 by form')
grp(r2,lambda r:r['variant'].split('_')[1],'tl_conf','br_conf')
# sign pooled round1+2
allr=r1+r2
print('--- pooled r1+r2 by form')
grp(allr,lambda r:r['variant'].split('_')[1],'tl_conf','br_conf')
print('--- round3')
for r in r3:
    print({k:r[k] for k in r if k not in ('marks','top_left_desc','bottom_right_desc','top_left_meaning','bottom_right_meaning','home_answer','home_reason')})
