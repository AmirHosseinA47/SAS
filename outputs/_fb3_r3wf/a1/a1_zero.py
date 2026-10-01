"""Any sampled belief with alive_mass exactly 0 (degenerate posterior) while n_unfound > 0? (recorded, read-only)"""
import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs')
sys.argv = ['x']
import _fb3_analyze as A
for arm in ['fb3bdr', 'fb3bfr', 'fb3bdr2', 'fb3bfr2', 'fb3vs3r', 'fb3bd', 'fb3bf', 'fb3bd2', 'fb3bf2', 'fb3vs3']:
    runs = A.load(arm)
    zero, minpos, n = [], 1.0, 0
    for key, d in sorted(runs.items()):
        for r in d['fb3']['coverage']:
            s = r[2]
            if isinstance(s, dict) and s['n_unfound'] > 0:
                n += 1
                if s['alive_mass'] == 0.0:
                    zero.append((key, r[0]))
                else:
                    minpos = min(minpos, s['alive_mass'])
    print('%-8s samples(n_unf>0)=%d  alive_mass==0 (rounded 1e-6): %d %s  min positive alive_mass=%.6f'
          % (arm, n, len(zero), zero[:6], minpos))
