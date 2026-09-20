import json
T='E:/Projects/SAS/outputs/_bm/'
runs=['east_101','east_202','north_101','south_101','south_202','west_101']
tot=0; hit=0; idle=0; idle_in=0; asg=0; asg_in=0; exi=0; exi_col=0
for r in runs:
    d=json.load(open(T+'trace_%s.json'%r,encoding='utf-8'))
    s_hit=0
    for row in d['rows']:
        any_=False
        for f in row['ffs']:
            st=f['state']; nf=f['nearest_fire']
            if st=='idle':
                idle+=1
                if nf is not None and nf<=3: idle_in+=1; any_=True
            elif st=='assigned':
                asg+=1
                if nf is not None and nf<=1: asg_in+=1; any_=True
            elif st=='exiting':
                exi+=1
                if nf is not None and nf<=3: exi_col+=1
        tot+=1; s_hit+=any_
    hit+=s_hit
    print(r,'steps',len(d['rows']),'>=1 frame encloses fire',s_hit,'%.1f%%'%(100*s_hit/len(d['rows'])))
print('POOLED steps',tot,'hit',hit,'%.2f%%'%(100*hit/tot),'none %.2f%%'%(100-100*hit/tot))
print('idle',idle_in,'/',idle,'%.2f%%'%(100*idle_in/idle),'assigned',asg_in,'/',asg,'%.2f%%'%(100*asg_in/asg),'exiting coloured',exi_col,'/',exi)
