import sys, statistics
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv = ['x']
import _fb3_analyze as A
for fam, tags in (('diff', ('fb3bdr', 'fb3bdr2')), ('flee', ('fb3bfr', 'fb3bfr2', 'fb3vs3r'))):
    eua, frac_lo, frac_hi, slo, shi = [], [], [], [], []
    for tag in tags:
        for seed, d in A.load(tag).items():
            sm = [(r[0], r[2]) for r in d['fb3']['coverage'] if isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict)]
            det = A.det_times(d); nb = len(d['rows_vic'][0])
            for row in d['fb3']['issued']:
                if row[4] is None:
                    continue
                s = row[0]
                b = min(sm, key=lambda x: abs(x[0] - s))[1]
                nu = nb - sum(1 for t in det.values() if t is not None and t <= s - 1)
                x = nu * b['alive_mass']
                f = row[4] / x if x > 0 else None
                if b['dead_mass'] > 0.5:
                    eua.append(x); shi.append(row[5])
                    if f is not None: frac_hi.append(f)
                else:
                    slo.append(row[5])
                    if f is not None: frac_lo.append(f)
    print(fam, 'E[unfound alive] at DEAD>.5 issues med %.4f' % statistics.median(eua),
          'frac lo %.3f hi %.3f' % (statistics.median(frac_lo), statistics.median(frac_hi)),
          'S med lo %.4f hi %.4f' % (statistics.median(slo), statistics.median(shi)))
