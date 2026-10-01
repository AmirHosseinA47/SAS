import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs')
sys.argv = ['x']
import _fb3_analyze as A

ARMS = ['fb3bdr', 'fb3bfr', 'fb3bdr2', 'fb3bfr2', 'fb3vs3r', 'fb3bd', 'fb3bf', 'fb3bd2', 'fb3bf2', 'fb3vs3']
for tag in ARMS:
    runs = A.load(tag)
    maxdev = 0.0
    nsum = 0
    drop_swept = 0
    lo_cont = 0
    zero_alive = 0
    nunf_match = 0
    unseen_dead_runs = []
    for key, d in sorted(runs.items()):
        cov = d['fb3']['coverage']
        last = None
        for row in cov:
            s = row[2]
            if s is None:
                continue
            nsum += 1
            maxdev = max(maxdev, abs(s['alive_mass'] + s['dead_mass'] - 1.0))
            if s['alive_mass'] == 0.0 and s['n_unfound'] > 0:
                zero_alive += 1
            last = s
        stats = d['fb3']['stats']
        for uid, c in stats.items():
            drop_swept += int(c.get('drop_swept', 0))
            lo_cont += int(c.get('lo_continuation_steps', 0))
        det = A.det_times(d)
        never = [v for v, t in det.items() if t is None]
        if last is not None and last['n_unfound'] == len(never):
            nunf_match += 1
        if never:
            # status of never-detected at last step
            lastvic = {v[0]: v[3] for v in d['rows_vic'][-1]}
            lo = sum(int(c.get('lo_continuation_steps', 0)) for c in stats.values())
            unseen_dead_runs.append((key, [lastvic.get(v) for v in never], lo, last['dead_mass'] if last else None, last['n_unfound'] if last else None))
    print(tag, 'runs', len(runs), 'samples', nsum, 'maxdev %.2e' % maxdev, 'drop_swept', drop_swept,
          'lo_cont', lo_cont, 'zero_alive', zero_alive, 'nunf_match %d/%d' % (nunf_match, len(runs)))
    for r in unseen_dead_runs:
        print('   never-detected', r)
