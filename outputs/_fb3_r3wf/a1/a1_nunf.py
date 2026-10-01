"""n_unfound at the end of each run vs victims never detected (recorded, read-only)."""
import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs')
sys.argv = ['x']
import _fb3_analyze as A

for arm in ['fb3bdr', 'fb3bfr', 'fb3bdr2', 'fb3bfr2', 'fb3vs3r']:
    runs = A.load(arm)
    agree = 0
    rows = []
    for key, d in sorted(runs.items()):
        last = [r for r in d['fb3']['coverage'] if isinstance(r[2], dict)][-1]
        n_unf = last[2]['n_unfound']
        det = A.det_times(d)
        never = sorted(v for v, t in det.items() if t is None)
        # final true status of never-detected victims
        final = {r[0]: r[3] for r in d['rows_vic'][-1]}
        st = [final.get(v) for v in never]
        lo = sum(int(c.get('lo_continuation_steps', 0) or 0) for c in (d['fb3'].get('stats') or {}).values())
        ok = (n_unf == len(never))
        agree += ok
        if never:
            rows.append('%s n_unf=%d never=%s status=%s lo_cont_steps=%d dead_mass=%.4f' % (key, n_unf, never, st, lo, last[2]['dead_mass']))
    print('%s: n_unfound(final) == #never-detected in %d/%d runs' % (arm, agree, len(runs)))
    for r in rows:
        print('   ', r)
