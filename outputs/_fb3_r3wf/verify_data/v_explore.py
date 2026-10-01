import sys, json
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv = ['x']
import _fb3_analyze as A
runs = A.load('fb3bdr')
d = runs['D_S']
print(sorted(d.keys()))
print('nsteps', len(d['rows_uav']), len(d['rows_vic']), d.get('terminal_step'))
print('uav row0', d['rows_uav'][0][:3])
print('vic row0', d['rows_vic'][0])
fb = d['fb3']
print(fb.keys())
print('cov', fb['coverage'][:3], fb['coverage'][-1])
print('issued', fb['issued'][:3], len(fb['issued']))
print('stats', list(fb['stats'].items())[:1])
print('spawn', fb['spawn'])
print('switches', fb['switches'])
print('det', A.det_times(d))
labels = set()
for row in d['rows_uav']:
    for u in row:
        labels.add((u[3], u[8]))
print(sorted(labels))
