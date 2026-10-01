"""Read-only: is the recorded dead_mass non-decreasing over the sampled steps in every Bayes run (predicted by the
linearity argument: raw DEAD never shrinks, raw alive never grows, normalisation is a common scale)?"""
import sys
sys.path.insert(0, r'E:\Projects\SAS\outputs'); sys.argv=['x']
import _fb3_analyze as A
for tag in ("fb3bdr","fb3bfr","fb3bdr2","fb3bfr2","fb3vs3r","fb3bd","fb3bf","fb3bd2","fb3bf2","fb3vs3"):
    runs = A.load(tag); bad = 0; pairs = 0; worst = 0.0
    for k, d in runs.items():
        ds = [r[2]['dead_mass'] for r in d['fb3']['coverage'] if isinstance(r, list) and len(r) > 2 and isinstance(r[2], dict)]
        for a, b in zip(ds, ds[1:]):
            pairs += 1
            if b < a - 1e-6:
                bad += 1; worst = max(worst, a - b)
    print('%-8s runs %d sample pairs %d decreases %d (largest %.2g)' % (tag, len(runs), pairs, bad, worst))
