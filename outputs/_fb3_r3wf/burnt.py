import sys, statistics as stt
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv=['x']
import _fb3_analyze as A
for tag in ("fb3bdr","fb3bfr","fb3bdr2","fb3bfr2","fb3vs3r"):
    runs = A.load(tag)
    b = sorted(d['eval']['burnt_cells'] for d in runs.values())
    print(tag, 'burnt_cells median %d min %d max %d (of 2500)' % (stt.median(b), b[0], b[-1]))
