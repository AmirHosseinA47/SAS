"""Read-only: over every (run, sampled step, undetected non-rescued victim) triple with recorded DEAD share D > 0.5:
observed number truly alive vs the number a CALIBRATED DEAD share would produce (sum of 1 - D), and the Brier
score of D as a forecast of 'this undetected victim is dead' over ALL triples. Descriptive (triples correlated)."""
import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv=['x']
import _fb3_analyze as A
def go(label, tags):
    n = obs = 0; exp = 0.0; brier = 0.0; nall = 0; clim = []
    for tag in tags:
        for k, d in sorted(A.load(tag).items()):
            det = A.det_times(d)
            for r in d['fb3']['coverage']:
                if not (isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict)): continue
                s, D = r[0], r[2]['dead_mass']
                for x in d['rows_vic'][s - 1]:
                    if det.get(x[0]) is not None and s >= det[x[0]]: continue
                    if x[3] == 'rescued': continue
                    y = 1.0 if x[3] == 'dead' else 0.0
                    brier += (D - y) ** 2; nall += 1; clim.append(y)
                    if D > 0.5:
                        n += 1; obs += (y == 0.0); exp += 1.0 - D
    base = sum(clim) / len(clim)
    bref = sum((base - y) ** 2 for y in clim) / len(clim)
    print('%-34s D>0.5 triples %4d | truly alive %3d | calibrated expectation %.1f | Brier %.4f (climatology %.4f, n %d)'
          % (label, n, obs, exp, brier / nall, bref, nall))
go('BD-R 0.1 (fb3bdr, fb3bdr2)', ("fb3bdr", "fb3bdr2"))
go('BF-R 0.1 (fb3bfr, fb3bfr2, fb3vs3r)', ("fb3bfr", "fb3bfr2", "fb3vs3r"))
go('BD 0.5 (fb3bd, fb3bd2)', ("fb3bd", "fb3bd2"))
go('BF 0.5 (fb3bf, fb3bf2, fb3vs3)', ("fb3bf", "fb3bf2", "fb3vs3"))
