import glob, os
from PIL import Image
import numpy as np
P='E:/Projects/SAS/outputs/_bm/p3/'
pres=sorted(glob.glob(P+'_pa_*_pre.png'))
print(len(pres),'arms')
for pre in pres:
    nl=pre.replace('_pre.png','_prenolabel.png')
    a=np.array(Image.open(pre).convert('RGBA')).astype(int); b=np.array(Image.open(nl).convert('RGBA')).astype(int)
    diff=(a!=b).any(axis=2)
    ys,xs=np.nonzero(diff)
    nw=int(((ys<280)&(xs<280)).sum()); se=int(((ys>=280)&(xs>=280)).sum()); other=int(diff.sum())-nw-se
    bbox=(xs.min(),ys.min(),xs.max(),ys.max()) if len(xs) else None
    # fully inked #770099
    full=int(((a[...,0]==0x77)&(a[...,1]==0)&(a[...,2]==0x99)&diff).sum())
    print(os.path.basename(pre)[4:-8].ljust(24),'total',int(diff.sum()),'NW',nw,'SE',se,'other',other,'bbox',bbox,'fully #770099',full)
