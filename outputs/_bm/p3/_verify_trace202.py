import json, collections
d=json.load(open('E:/Projects/SAS/outputs/_bm/trace_south_202.json',encoding='utf-8'))
rows=d['rows']
per=collections.defaultdict(list)
for r in rows:
    for f in r['ffs']:
        per[f['id']].append((r['step'],f['state'],f['pos'],f['target'],f['exiting'],f['nearest_fire']))
for uid,seq in per.items():
    cnt=collections.Counter(s[1] for s in seq)
    print(uid,dict(cnt))
    ex=[s for s in seq if s[1]=='exiting']
    # episodes
    eps=[]; cur=[]
    for s in ex:
        if cur and s[0]!=cur[-1][0]+1: eps.append(cur); cur=[]
        cur.append(s)
    if cur: eps.append(cur)
    for e in eps:
        le3=sum(1 for s in e if s[5] is not None and s[5]<=3)
        le1=sum(1 for s in e if s[5] is not None and s[5]<=1)
        dist=collections.Counter(s[5] for s in e)
        print('   exiting episode steps %d-%d n=%d  d<=3: %d  d<=1: %d  dist hist %s'%(e[0][0],e[-1][0],len(e),le3,le1,dict(sorted(dist.items(), key=lambda kv:(kv[0] is None, kv[0])))))
        nxt=[s for s in seq if s[0]==e[-1][0]+1]
        print('      next step:',nxt)
        print('      last exiting row:',e[-1])
# total exiting / coloured in run
tot=sum(1 for seq in per.values() for s in seq if s[1]=='exiting')
col=sum(1 for seq in per.values() for s in seq if s[1]=='exiting' and s[5] is not None and s[5]<=3)
print('run exiting',tot,'coloured d<=3',col)
# step 160 for 2509
print([s for s in per['2509'] if s[0] in (99,130,160,176,177,178)])
# dead rows
for uid,seq in per.items():
    dd=[s for s in seq if s[1]=='dead']
    if dd: print(uid,'first dead',dd[0],'n dead',len(dd))
