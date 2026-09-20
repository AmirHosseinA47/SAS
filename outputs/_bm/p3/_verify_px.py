import json, sys, os
sys.path.insert(0, 'E:/Projects/SAS/outputs')
from _bm_flag_geom import banner_pixels
from PIL import Image
F=(0x77,0,0x99)
def on_segment(c):
    ts=[(c[i]-F[i])/float(255-F[i]) for i in range(3)]
    t=sum(ts)/3.0
    return -0.01<=t<=1.01 and all(abs(c[i]-(F[i]+t*(255-F[i])))<=2.0 for i in range(3))
P3='E:/Projects/SAS/outputs/_bm/p3/'
def load(n): return Image.open(P3+n).convert('RGB').load()
for arm, fj in [('prob_w101_s105','f_west_101_s105.json'),('prob_n101_s192','f_north_101_s192.json'),('occluded_n101_s192','f_north_101_s192.json')]:
    blob=json.load(open(P3+fj)); W,H,cs=blob['width'],blob['height'],blob['cs']; fr=blob['frame']
    P={}
    per=[]
    for d in fr['depots']:
        bp=banner_pixels(d,W,H,cs); per.append((d,len(bp))); P.update(bp)
    pre,post=load('_pa_%s_pre.png'%arm),load('_pa_%s_post.png'%arm)
    unchanged=[q for q in P if pre[q]==post[q]]
    print(arm,'W,H,cs',W,H,cs,'P',len(P),'per depot',[(d['x'],d['y'],n) for d,n in per],'unchanged in P',len(unchanged))
    if len(unchanged)<=5:
        for q in unchanged:
            print('   px',q,'tone',P[q],'pre',pre[q],'post',post[q],'pre on_segment',on_segment(pre[q]))
    # old label ink per depot region: L = pre vs prenolabel
    pnl=load('_pa_%s_prenolabel.png'%arm)
    size=int(W*cs)
    L=[(x,y) for y in range(size) for x in range(size) if pre[(x,y)]!=pnl[(x,y)]]
    ys=[q[1] for q in L]; xs=[q[0] for q in L]
    print('   L',len(L),'x range',min(xs),max(xs),'y range',min(ys),max(ys))
