import json, sys, math
sys.path.insert(0, 'E:/Projects/SAS/outputs')
from _bm_flag_geom import banner_pixels
P3='E:/Projects/SAS/outputs/_bm/p3/'
blob=json.load(open(P3+'f_north_101_s192.json')); W,H,cs=blob['width'],blob['height'],blob['cs']; fr=blob['frame']
print('keys', sorted(fr.keys()))
P={}
for d in fr['depots']: P.update(banner_pixels(d,W,H,cs))
def box(x0,y0,w,h,pad=1.0):
    return {(u,v) for u in range(int(math.floor(x0-pad)),int(math.ceil(x0+w+pad))) for v in range(int(math.floor(y0-pad)),int(math.ceil(y0+h+pad)))}
for f in fr.get('firefighters',[]):
    b=box((f['x']+0.15)*cs,(H-1-f['y']+0.15)*cs,cs*0.7,cs*0.7); n=len(b & set(P))
    print('FF',{k:f[k] for k in f if k in('id','x','y','alive','status')}, 'banner px in footprint', n)
for u in fr.get('uavs',[]):
    b=box((u['x']+0.1)*cs,(H-1-u['y']+0.1)*cs,cs*0.8,cs*0.8); n=len(b & set(P))
    print('UAV',{k:u[k] for k in u if k in('id','x','y','role')}, 'banner px in footprint', n)
for v in fr.get('victims',[]):
    b=box(v['x']*cs,(H-1-v['y'])*cs,cs,cs); n=len(b & set(P))
    print('VIC',{k:v[k] for k in v if k in('id','x','y','status')}, 'banner px', n)
print('assignments', fr.get('assignments'))
print('panel ff view', [ (f.get('id'), f.get('position'), f.get('alive'), f.get('status')) for f in fr['panel']['firefighter_view']])
