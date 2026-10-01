"""Recorded-run checks (read-only): mass invariant in belief summaries, and drop/selection counters per arm."""
import sys, collections
sys.path.insert(0, r'E:\Projects\SAS\outputs')
sys.argv = ['x']
import _fb3_analyze as A

ARMS = ['fb3bdr', 'fb3bfr', 'fb3bdr2', 'fb3bfr2', 'fb3vs3r', 'fb3bd', 'fb3bf', 'fb3bd2', 'fb3bf2', 'fb3vs3']
KEYS = ['selections', 'drop_reached', 'drop_swept', 'giveup_unreachable', 'drop_battery', 'drop_return_leg',
        'drop_all_detected', 'fallback_entries', 'lo_continuation_steps']
print('arm      runs  max|alive+dead-1|  max_dead  ' + '  '.join(KEYS))
for arm in ARMS:
    runs = A.load(arm)
    worst = 0.0
    maxdead = 0.0
    tot = collections.Counter()
    for key, d in runs.items():
        for row in d['fb3']['coverage']:
            s = row[2]
            if isinstance(s, dict):
                worst = max(worst, abs(s['alive_mass'] + s['dead_mass'] - 1.0))
                maxdead = max(maxdead, s['dead_mass'])
        for uid, c in (d['fb3'].get('stats') or {}).items():
            for k in KEYS:
                tot[k] += int(c.get(k, 0) or 0)
    print('%-8s %4d  %.2e        %.4f    ' % (arm, len(runs), worst, maxdead) + '  '.join('%s=%d' % (k, tot[k]) for k in KEYS))
