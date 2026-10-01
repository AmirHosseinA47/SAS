import sys, json, collections
sys.path.insert(0, r'E:\Projects\SAS\outputs')
sys.argv = ['x']
import _fb3_analyze as A

runs = A.load('fb3bdr')
print(len(runs), sorted(runs))
d = runs['C_S']
print(list(d.keys()))
print('rows_uav len', len(d['rows_uav']), 'rows_vic len', len(d['rows_vic']))
print('uav row0', d['rows_uav'][0])
print('vic row0', d['rows_vic'][0])
print('cov first', d['fb3']['coverage'][:3], d['fb3']['coverage'][-1])
print('issued first', d['fb3']['issued'][:5], len(d['fb3']['issued']))
print('stats', d['fb3']['stats'])
print('det', A.det_times(d))
print('spawn', d['fb3']['spawn'])
print('switches', d['fb3']['switches'])
print('terminal', d.get('terminal_step'))
labs = collections.Counter(u[8] for row in d['rows_uav'] for u in row)
print(labs.most_common(40))
roles = collections.Counter(u[3] for row in d['rows_uav'] for u in row)
print(roles)
vst = collections.Counter((v[3], v[4]) for row in d['rows_vic'] for v in row)
print(vst)
