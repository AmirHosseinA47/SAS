from PIL import Image, ImageChops
P3='E:/Projects/SAS/outputs/_bm/p3/'
arms=['quiet_e101_s0','nwburnt_w101_s105','sesmoke_s202_s99','occluded_n101_s192','prob_w101_s105','prob_n101_s192','trail_w101_s60','w101_s30','w101_s150','w101_s200','s202_s130','s202_s160']
for a in arms:
    pre=Image.open(P3+'_pa_%s_pre.png'%a).convert('RGB'); pnl=Image.open(P3+'_pa_%s_prenolabel.png'%a).convert('RGB')
    diff=ImageChops.difference(pre,pnl).convert('L').point(lambda v:255 if v else 0)
    bbox=diff.getbbox(); n=sum(1 for v in diff.getdata() if v)
    nw=sum(1 for v in diff.crop((0,0,280,280)).getdata() if v)
    print('%-22s L=%d bbox=%s px in NW quadrant=%d' % (a,n,bbox,nw))
