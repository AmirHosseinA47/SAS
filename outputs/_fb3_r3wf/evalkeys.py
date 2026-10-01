import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv=['x']
import _fb3_analyze as A
d = A.load('fb3bdr')['D_S']
print(d['eval'])
print(d['mf2'].keys() if isinstance(d['mf2'], dict) else d['mf2'])
print(d['fx3'].keys())
print(d['rows_trig'][100][:3] if d['rows_trig'][100] else None)
print(d['rows_dec'][100][:2] if d['rows_dec'][100] else None)
