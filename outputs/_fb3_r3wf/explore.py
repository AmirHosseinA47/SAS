import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv=['x']
import _fb3_analyze as A
runs = A.load('fb3bdr')
k = sorted(runs)[0]; d = runs[k]
print(k, sorted(d.keys()))
print('fb3 keys', sorted(d['fb3'].keys()))
print('cov sample', d['fb3']['coverage'][:3])
print('rows_vic[0]', d['rows_vic'][0])
print('rows_uav[0][0]', d['rows_uav'][0][0])
for kk in d:
    v = d[kk]
    print(kk, type(v).__name__, (len(v) if hasattr(v,'__len__') else v) if not isinstance(v,(int,float,str)) else v)
