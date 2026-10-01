"""Read-only: DEAD-share trajectories and targeting counters per arm, burn-over 0.1 (re-screen) vs 0.5 (screen)."""
import sys, statistics as stt
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv=['x']
import _fb3_analyze as A
PAIRS = [("fb3bdr","fb3bd"),("fb3bfr","fb3bf"),("fb3bdr2","fb3bd2"),("fb3bfr2","fb3bf2"),("fb3vs3r","fb3vs3")]
STEPS = [50,100,150,200,250,300,360]
def traj(tag):
    runs = A.load(tag)
    out = {s: [] for s in STEPS}; cov = {s: [] for s in STEPS}
    ctr = {}
    for k, d in runs.items():
        for r in d['fb3']['coverage']:
            if isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict) and r[0] in out:
                out[r[0]].append(r[2]['dead_mass']); cov[r[0]].append(r[2]['coverage_share'])
        for uid, c in (d['fb3'].get('stats') or {}).items():
            for kk, v in c.items():
                if isinstance(v, (int, float)): ctr[kk] = ctr.get(kk, 0) + v
    return runs, out, cov, ctr
for new, old in PAIRS:
    for tag in (new, old):
        runs, out, cov, ctr = traj(tag)
        print(tag, 'n=%d' % len(runs))
        print('   median DEAD  ', ' '.join('%d:%.3f' % (s, stt.median(out[s])) if out[s] else '%d:-' % s for s in STEPS))
        print('   max DEAD     ', ' '.join('%d:%.3f' % (s, max(out[s])) if out[s] else '%d:-' % s for s in STEPS))
        print('   median cover ', ' '.join('%d:%.3f' % (s, stt.median(cov[s])) if cov[s] else '%d:-' % s for s in STEPS))
        print('   counters     ', {k: ctr[k] for k in sorted(ctr) if k in ('selections','drop_swept','drop_reached','giveup_unreachable','drop_battery','drop_all_detected','drop_return_leg','fallback_entries')})
